import asyncio, logging, os, re
from datetime import datetime
from .base import AgentBase
from ..agents.researcher import research_niche
from ..core.models import ModelRouter

logger = logging.getLogger("abvorn.orchestrator")

# Centralized affiliate tag: AMAZON_TAG secret, falling back to the real tag.
def _amazon_tag() -> str:
    return os.environ.get("AMAZON_TAG") or "viraltestco-20"

# Publish-boundary guard for fabricated products. research_niche no longer
# injects a "Top <niche> Pick" stub, but a stub can still arrive from an older
# state row, a cached content dict, or a hand-edited payload. A product with no
# ASIN anywhere in its name/url is not buyable, so a page built only from such
# products is the product-less-hub regression (the tv hub shipped 1 fake
# product, 0 ASINs, and a ?tag=... search link) and must not be published.
_ASIN_RE = re.compile(r"B0[A-Z0-9]{8}")
_PLACEHOLDER_NAME_RE = re.compile(r"^top\b.*\bpick$", re.I)


def _product_is_placeholder(product: dict) -> bool:
    """True when a product carries no ASIN and reads like a generated stub."""
    if not isinstance(product, dict):
        return True
    blob = f"{product.get('name', '')} {product.get('url', '')} {product.get('asin', '')}"
    if _ASIN_RE.search(blob or ""):
        return False
    name = str(product.get("name") or "").strip()
    return bool(_PLACEHOLDER_NAME_RE.match(name)) or not name


def _products_are_placeholder(products: list) -> bool:
    return bool(products) and all(_product_is_placeholder(p) for p in products)

class ResearchAgent(AgentBase):
    """Performs product research when content is needed for a niche."""

    def __init__(self, bus, state, router: ModelRouter, brain=None, will=None, drive=None):
        super().__init__("ResearchAgent", bus, state, brain, will, drive)
        self.router = router

    async def perceive(self):
        queue = self.state.get_all_niches() if self.state else []
        low_posts = [n for n in queue if n["total_posts"] < 3]
        return {"under_researched": low_posts[:1]}

    async def decide(self, perception):
        if perception.get("under_researched"):
            target = perception['under_researched'][0]['slug']
            if not self.soul_check("research_niche", {"niche": target}):
                logger.info(f"[ResearchAgent] Soul blocked research for {target}")
                return "wait"
            return f"research:{target}"
        return "wait"

    async def act(self, decision):
        if decision.startswith("research:"):
            niche = decision.split(":", 1)[1]
            logger.info(f"[ResearchAgent] Researching niche: {niche}")
            products = await asyncio.to_thread(research_niche, niche, self.router)
            if products:
                self.bus.publish("content.researched", {"niche": niche, "products": products, "count": len(products)})
                return {"niche": niche, "products_count": len(products)}
            logger.warning(f"[ResearchAgent] No products found for {niche}")
            if self.drive:
                alt = self.drive.alternative_path("research_niche")
                logger.info(f"[ResearchAgent] Drive suggests alternative: {alt}")
            return {"niche": niche, "products_count": 0}

    async def reflect(self, outcome):
        if self.drive:
            succeeded = bool(outcome and outcome.get("products_count", 0) > 0)
            self.drive.log_outcome("research", succeeded=succeeded)
        if outcome and outcome.get("products_count", 0) == 0:
            logger.warning("[ResearchAgent] Zero products — consider switching search strategy")


class ContentAgent(AgentBase):
    """Generates content using the pipeline when research is ready."""

    def __init__(self, bus, state, router: ModelRouter, pipeline, brain=None, will=None, drive=None):
        super().__init__("ContentAgent", bus, state, brain, will, drive)
        self.router = router
        self.pipeline = pipeline

    async def perceive(self):
        return {"events": self.bus.get_recent_events("content.researched")}

    async def decide(self, perception):
        if perception.get("events"):
            last = max(perception["events"], key=lambda e: e["created_at"])
            envelope = last.get("message", {}) if isinstance(last.get("message"), dict) else last
            niche = envelope.get("niche") or ""
            if not niche:
                return "wait"
            if not self.soul_check("generate_content", {"niche": niche}):
                logger.info(f"[ContentAgent] Soul blocked content for {niche}")
                return "wait"
            return f"generate:{niche}"
        return "wait"

    async def act(self, decision):
        if decision.startswith("generate:"):
            niche = decision.split(":", 1)[1]
            logger.info(f"[ContentAgent] Generating content for: {niche}")
            result = await asyncio.to_thread(
                self.pipeline.run,
                niche,
                self.router,
                persona={},
            )
            if result:
                self.bus.publish("content.drafted", {"niche": niche, "result": result})
                if self.state:
                    self.state.add_post(niche, result.get("post_title", ""), "",
                                        quality_score=result.get("quality_score", 0))
                return {"niche": niche, "title": result.get("post_title", "")}
            return {"niche": niche, "error": "pipeline returned None"}

    async def reflect(self, outcome):
        if self.drive:
            succeeded = bool(outcome and outcome.get("title"))
            self.drive.log_outcome("content_generation", succeeded=succeeded)
        if outcome and outcome.get("error"):
            logger.warning(f"[ContentAgent] Content generation failed: {outcome['error']}")

class SiteDeployer:
    """Deploys the premium Abvorn design to GitHub Pages by delegating to the
    same builders as the richer pipeline (run_cycle / src.deployment).

    The daemon must never emit its own minimal template — doing so clobbered
    the rich site before. Reviews are the published pages already on disk (the
    committed rich tree) plus anything deployed earlier in this cycle, which
    mirrors how run_cycle.write_files overlays freshly-written articles.
    """

    def __init__(self, deployer, state):
        self.deployer = deployer
        self.state = state
        self._last_content = None   # content dict deployed this cycle, for overlay
        self._last_niche = None

    def _niche_name(self, niche: str) -> str:
        if self.state:
            try:
                for n in self.state.get_all_niches():
                    if n.get("slug") == niche:
                        return n.get("name") or niche.replace("-", " ").title()
            except Exception:
                pass
        return niche.replace("-", " ").title()

    def _reviews(self, niches: list, posts: list, default_niche: str = "") -> list:
        """Published reviews for homepage + niche pages.

        Starts from the committed doc tree (so real product photos and verdicts
        carry through), overlays the article deployed earlier this cycle, then
        appends any state-recorded posts that are not yet on disk (the daemon
        pushes straight to GitHub without updating docs/ locally).

        State posts are only appended when their article page genuinely exists
        in the remote published tree (deploy_root_index passes deployer), so a
        post row whose page was never actually pushed (e.g. a stale/scanned
        "coffee-grinder" entry that 404s on the live site) cannot fabricate a
        dead card. API/transport errors fail open: real pages are kept rather
        than dropping every card during a GitHub outage.
        """
        from src.deployment import scan_published_reviews, _overlay_review
        today = datetime.now().strftime("%Y-%m-%d")
        reviews = scan_published_reviews("docs")
        seen = {(r["slug"], r["title"]): i for i, r in enumerate(reviews)}
        if self._last_content and self._last_niche:
            entry = _overlay_review(self._last_content, self._last_niche,
                                    self._niche_name(self._last_niche), today)
            key = (entry["slug"], entry["title"])
            if key in seen:
                reviews[seen[key]] = entry
            else:
                reviews.append(entry)
        for p in (posts or []):
            slug = p.get("niche_slug") or p.get("slug") or p.get("niche") or default_niche
            title = p.get("title") or p.get("post_title") or ""
            if not slug or not title or (slug, title) in seen:
                continue
            filename = p.get("filename", "")
            if filename and self.deployer is not None:
                rel = f"reviews/{slug}/{filename}"
                try:
                    if not self.deployer.file_exists(rel):
                        logger.warning(
                            f"[SiteDeployer] Skipping card {title!r}: page {rel} "
                            "does not exist in the published tree"
                        )
                        seen[(slug, title)] = len(reviews)
                        continue
                except Exception as e:
                    logger.warning(f"[SiteDeployer] Could not verify {rel} (fail-open): {e}")
            quality = p.get("quality_score")
            reviews.append({
                "slug": slug,
                "name": self._niche_name(slug),
                "title": title,
                "updated": (p.get("created_at") or "")[:10] or today,
                "rel": f"/reviews/{slug}/{filename}" if filename else f"/reviews/{slug}/",
                "snippet": "",
                "image": p.get("image") or "",
                "score": quality if quality else None,
                "breakdown": {},
                "label": "",
                "product_name": p.get("product_name", ""),
            })
            seen[(slug, title)] = len(reviews) - 1
        return reviews

    def _niche_reviews(self, niche: str, posts: list) -> list:
        """Review entries scoped to one niche, newest-first."""
        reviews = [r for r in self._reviews([niche], posts, default_niche=niche)
                   if r.get("slug") == niche]
        reviews.sort(key=lambda r: r.get("updated", ""), reverse=True)
        return reviews

    def deploy_root_index(self, niches: list = None, posts: list = None) -> bool:
        try:
            niches = niches or []
            posts = posts or []
            if not niches or not posts:
                logger.warning("[SiteDeployer] Skipping root index deploy: need both niches and posts (otherwise would deploy placeholder)")
                return False
            state = {"niches": [
                {"slug": (n if isinstance(n, str) else n.get("slug", "")),
                 "name": (n if isinstance(n, str) else n.get("name", "")).replace("-", " ").title()}
                for n in niches
            ]}
            reviews = self._reviews(niches, posts)
            from src.deployment import build_homepage
            html = build_homepage(state, form_url=os.environ.get("APPS_SCRIPT_URL", ""),
                                  reviews=reviews)
            self.deployer.deploy_html(html, "index.html")
            logger.info("[SiteDeployer] Deployed premium root index")
            return True
        except Exception as e:
            logger.error(f"[SiteDeployer] Root index failed: {e}")
            return False

    def _category_html(self, niche: str, posts: list, all_slugs: list) -> str:
        from run_cycle import build_category_page
        return build_category_page(
            niche, self._niche_name(niche), self._niche_reviews(niche, posts),
            all_slugs, _amazon_tag())

    def deploy_category_page(self, niche: str, posts: list = None, all_categories: list = None) -> bool:
        try:
            posts = posts or []
            if not posts:
                logger.warning(f"[SiteDeployer] Skipping category deploy for {niche}: no posts available (would deploy placeholder)")
                return False
            html = self._category_html(niche, posts, list(all_categories or [niche]))
            self.deployer.deploy_html(html, f"{niche}/index.html")
            logger.info(f"[SiteDeployer] Deployed premium category page for {niche}")
            return True
        except Exception as e:
            logger.error(f"[SiteDeployer] Category page failed: {e}")
            return False

    def deploy_category_hub(self, niche: str, posts: list = None, all_categories: list = None) -> bool:
        """Deploy a brand-new category hub at its canonical /reviews/<niche>/ location.

        In the rich pipeline write_files makes reviews/<niche>/index.html mirror
        the newest article, so links to the reviews path land on a real review —
        not a duplicate category listing with a cross-canonical to /<niche>/.
        When the article this cycle just deployed belongs to this niche, mirror
        it; otherwise fall back to a premium category listing.
        """
        try:
            all_categories = list(all_categories or [niche])
            if self._last_content and self._last_niche == niche:
                return self.deploy_content(niche, self._last_content,
                                           all_categories=all_categories)
            posts = posts or []
            if not posts:
                logger.warning(f"[SiteDeployer] Skipping new category hub for {niche}: no posts available (would deploy placeholder)")
                return False
            rich = [r for r in self._reviews([niche], posts, niche)
                    if r.get("slug") == niche]
            if not rich:
                rich = posts
            html = self._category_html(niche, rich, all_categories)
            self.deployer.deploy_html(html, f"reviews/{niche}/index.html")
            logger.info(f"[SiteDeployer] Deployed premium category hub for {niche}")
            return True
        except Exception as e:
            logger.error(f"[SiteDeployer] Category hub failed: {e}")
            return False

    def deploy_content(self, niche: str, content: dict, all_categories: list = None,
                       article_filename: str = None) -> bool:
        try:
            all_categories = all_categories or []
            from run_cycle import build_article_page
            today = datetime.now().strftime("%Y-%m-%d")
            products = content.get("products") or []
            if _products_are_placeholder(products):
                logger.warning(
                    "[SiteDeployer] Refusing to publish %s: %d product(s) and "
                    "none carry an ASIN (placeholder payload) — keeping the "
                    "currently published page instead of shipping a "
                    "product-less hub",
                    niche, len(products),
                )
                return False
            product_name = (content.get("product_name")
                            or (products[0].get("name", "") if products else ""))
            related = [{"slug": c, "name": self._niche_name(c)}
                       for c in all_categories if c != niche][:4]

            html = build_article_page(
                niche, self._niche_name(niche),
                content.get("post_title", niche),
                content.get("article_html", content.get("content", "")),
                content.get("intro", ""),
                product_name,
                content.get("meta_description", "")[:160],
                list(all_categories),
                products=products or None,
                amazon_tag=_amazon_tag(),
                form_url=os.environ.get("APPS_SCRIPT_URL", ""),
                related_niches=related,
                published_date=today,
                updated_date=today,
                article_id=f"{niche}-0",
            )
            self._last_content = content
            self._last_niche = niche
            path = f"reviews/{niche}/{'index.html' if not article_filename else article_filename}"
            self.deployer.deploy_html(html, path)
            logger.info(f"[SiteDeployer] Deployed premium article for {niche} as {path}")
            return True
        except Exception as e:
            logger.error(f"[SiteDeployer] Article deploy failed: {e}")
            return False


class DeployAgent(AgentBase):
    """Deploys drafted content to GitHub Pages."""

    def __init__(self, bus, state, deployer, will=None, drive=None):
        super().__init__("DeployAgent", bus, state, will=will, drive=drive)
        self.deployer = deployer
        self.site_deployer = SiteDeployer(deployer, state) if state else None

    async def perceive(self):
        events = self.bus.get_recent_events("content.drafted")
        if not events:
            return {"events": []}
        try:
            stored = self.state.get_meta("handled_drafted_event_ids", []) if self.state else []
            handled = set(stored)
        except Exception:
            handled = set()
        fresh = [e for e in events if e["id"] not in handled]
        return {"events": fresh}

    def _mark_drafted_handled(self, event_ids):
        try:
            stored = self.state.get_meta("handled_drafted_event_ids", []) if self.state else []
            updated = sorted(set(stored) | set(event_ids))
            self.state.set_meta("handled_drafted_event_ids", updated[-200:])
        except Exception as e:
            logger.error(f"[DeployAgent] failed to mark drafted events handled: {e}")

    async def decide(self, perception):
        if perception.get("events"):
            last = max(perception["events"], key=lambda e: e["created_at"])
            niche = last['message']['niche']
            if not self.soul_check("deploy_content", {"niche": niche}):
                logger.info(f"[DeployAgent] Soul blocked deploy for {niche}")
                return "wait"
            return f"deploy:{niche}"
        return "wait"

    def _deploy_site(self, niche, content_payload):
        all_niches_data = self.state.get_all_niches()
        all_slugs = [n["slug"] for n in all_niches_data]
        all_posts = []
        for slug in all_slugs:
            all_posts.extend(self.state.get_posts_for_niche(slug))
        if content_payload:
            payload_products = content_payload.get("products") or []
            deploy_content = {
                "post_title": content_payload.get("post_title", ""),
                "intro": content_payload.get("intro", ""),
                "article_html": content_payload.get("article_html", ""),
                "meta_description": content_payload.get("meta_description", ""),
                "product_name": (
                    content_payload.get("product_name")
                    or (payload_products[0].get("name", "") if payload_products else "")
                ),
                "products": payload_products,
            }
            self.site_deployer.deploy_content(
                niche,
                deploy_content,
                all_categories=all_slugs,
            )
        else:
            posts = self.state.get_posts_for_niche(niche)
            if posts:
                latest = posts[0]
                content = {
                    "post_title": latest.get("title", ""),
                    "content": latest.get("filename", ""),
                    "product_name": latest.get("product_name", ""),
                }
                self.site_deployer.deploy_content(
                    niche,
                    content,
                    all_categories=all_slugs,
                )
        self.site_deployer.deploy_root_index(
            niches=all_niches_data,
            posts=all_posts,
        )
        for slug in all_slugs:
            niche_posts = [
                post for post in all_posts
                if post.get("niche_slug") == slug
            ]
            self.site_deployer.deploy_category_page(
                slug,
                posts=niche_posts,
                all_categories=all_slugs,
            )

    async def act(self, decision):
        if decision.startswith("deploy:"):
            niche = decision.split(":", 1)[1]
            logger.info(f"[DeployAgent] Deploying content for: {niche}")
            events = self.bus.get_recent_events("content.drafted")
            content_payload = None
            handled_id = None
            for event in events:
                if event['message'].get('niche') == niche:
                    if handled_id is None:
                        handled_id = event["id"]
                    if content_payload is None and 'result' in event['message']:
                        content_payload = event['message']['result']
            if self.site_deployer and self.state:
                await asyncio.to_thread(
                    self._deploy_site,
                    niche,
                    content_payload,
                )
            self.bus.publish("content.published", {"niche": niche, "status": "deployed"})
            if handled_id is not None:
                self._mark_drafted_handled([handled_id])
            return {"niche": niche, "status": "deployed"}

    async def reflect(self, outcome):
        if self.drive:
            succeeded = bool(outcome and outcome.get("status") == "deployed")
            self.drive.log_outcome("deploy", succeeded=succeeded)
