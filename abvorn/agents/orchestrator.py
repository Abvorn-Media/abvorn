import asyncio, logging, os, re
from datetime import datetime
from .base import AgentBase
from ..agents.researcher import research_niche
from ..core.models import ModelRouter
from ..core import bus_progress

logger = logging.getLogger("abvorn.orchestrator")

# Monotonic "highest content.drafted id already deployed" marker. See
# abvorn/core/bus_progress.py for why this is a position and not a set.
_DRAFTED_WATERMARK = "deployagent_drafted_watermark"

# Title -> article filename. ASCII-only by construction: titles arrive from the
# LLM carrying non-ASCII characters (non-breaking hyphens, smart quotes, e.g.
# "Mini\u2011LED"), which double-encode to mojibake when a path crosses the
# Windows ANSI codepage - the exact failure the publish-content guard exists to
# catch. Dropped rather than transliterated: an ugly path beats a broken one.
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def _slugify_article_title(title: str, max_len: int = 60) -> str:
    """Filesystem-safe, ASCII-only slug from an article title."""
    ascii_title = (title or "").encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_STRIP_RE.sub("-", ascii_title).strip("-")
    if len(slug) > max_len:
        # Truncate on a word boundary, never mid-word.
        slug = slug[:max_len].rsplit("-", 1)[0] or slug[:max_len]
    return slug.strip("-")


def _article_filename(post_title: str, taken: set) -> str:
    """Pick the article's own filename inside ``reviews/<niche>/``.

    A title always resolves to the same canonical file: ``{slug}.html``. The
    old code minted a numbered variant (``-2.html`` … ``-99.html`` then a
    timestamped file) whenever the filename was already recorded for the niche,
    so every re-deploy of the same buying guide spawned a brand-new near-
    identical page — that is the robot-vacuums flood (857 single-file commits,
    ``best-robot-vacuums-expert-review-90.html`` et al.). Volume is bounded by
    the daily per-niche publish cap in ``deploy_content``; here the slug is the
    identity, so the same review always refreshes its canonical URL instead of
    spawning siblings. ``taken`` is kept for call-site compatibility but is no
    longer consulted.
    """
    slug = _slugify_article_title(post_title) or "article"
    return f"{slug}.html"

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
# state.db deployment_status values that mean "this post is not a live review".
# "pending" is deliberately absent: it is the status the daemon writes for
# freshly generated articles that are already published.
_UNPUBLISHED_STATUSES = frozenset({"unpublished", "deleted", "archived", "removed"})


def _product_is_placeholder(product: dict) -> bool:
    """True when a product cannot be linked or pictured (a generated stub).

    A real scrape (run_cycle.research_products) always yields an ASIN *and* a
    photo. The pure-LLM fallback in research_niche yields neither, so the card
    renders a "Product" text tile and the CTA degrades to a ?tag= search link.
    The name alone cannot be trusted: that fallback happily invents real-sounding
    models ("Sony Bravia XR90A9 65\" OLED TV"), which is how the tv hub shipped
    three unpictured, unbuyable products. Missing a photo is the reliable tell.
    """
    if not isinstance(product, dict):
        return True
    name = str(product.get("name") or "").strip()
    if not name:
        return True
    blob = f"{name} {product.get('url', '')} {product.get('asin', '')}"
    if _ASIN_RE.search(blob or ""):
        return False
    if not str(product.get("image") or "").strip():
        return True
    return bool(_PLACEHOLDER_NAME_RE.match(name))


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
                    from src.deployment import product_card_image
                    self.state.add_post(niche, result.get("post_title", ""), "",
                                        quality_score=result.get("quality_score", 0),
                                        image=product_card_image(result))
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

        A post with no article page (empty filename) or an explicitly
        unpublished status is skipped outright. Rendering those produced a
        card that pointed at the niche hub while keeping the post's stale
        title, and the empty filename also bypassed the file_exists gate
        above - which is how the robot-vacuum "hotel booking" rows stayed on
        the live homepage after their pages were deleted.
        """
        from src.deployment import scan_published_reviews, _overlay_review
        today = datetime.now().strftime("%Y-%m-%d")
        reviews = scan_published_reviews("docs")
        seen = {(r["slug"], r["title"]): i for i, r in enumerate(reviews)}
        seen_by_rel = {(r.get("rel") or ""): i for i, r in enumerate(reviews)}
        if self._last_content and self._last_niche:
            entry = _overlay_review(self._last_content, self._last_niche,
                                    self._niche_name(self._last_niche), today)
            key = (entry["slug"], entry["title"])
            if key in seen:
                # Keep the published page's snippet when the overlay has none.
                # A freshly generated article whose intro and meta description
                # are both unusable (an opening question, say) produces an empty
                # overlay snippet, and blindly replacing the scanned entry
                # shipped the newest review as a card with no description at
                # all -- even though the page on disk already had good copy.
                if not (entry.get("snippet") or "").strip():
                    entry["snippet"] = reviews[seen[key]].get("snippet") or ""
                reviews[seen[key]] = entry
            else:
                reviews.append(entry)
        for p in (posts or []):
            slug = p.get("niche_slug") or p.get("slug") or p.get("niche") or default_niche
            title = p.get("title") or p.get("post_title") or ""
            if not slug or not title or (slug, title) in seen:
                continue
            filename = (p.get("filename") or "").strip()
            if not filename:
                # No article page means this is not a published review. Emitting
                # it would render a card that points at the niche hub while
                # keeping the post's stale title - exactly what the
                # robot-vacuum "hotel booking" rows did. It also silently
                # bypassed the file_exists gate below, since that only ran when
                # a filename was present.
                logger.info("[SiteDeployer] Skipping card %r: no article page", title)
                seen[(slug, title)] = len(reviews)
                continue
            if (p.get("deployment_status") or "").strip().lower() in _UNPUBLISHED_STATUSES:
                logger.info("[SiteDeployer] Skipping card %r: unpublished", title)
                seen[(slug, title)] = len(reviews)
                continue
            rel = f"/reviews/{slug}/{filename}"
            if self.deployer is not None:
                try:
                    if not self.deployer.file_exists(f"reviews/{slug}/{filename}"):
                        logger.warning(
                            f"[SiteDeployer] Skipping card {title!r}: page {rel} "
                            "does not exist in the published tree"
                        )
                        seen[(slug, title)] = len(reviews)
                        continue
                except Exception as e:
                    logger.warning(f"[SiteDeployer] Could not verify {rel} (fail-open): {e}")
            quality = p.get("quality_score")
            # Match the scanned card by page path before appending. The state
            # row's title often differs from the page's own <h1>, so the
            # (slug, title) key missed and the row was appended as a second
            # card for a page already in the list -- one copy of which has
            # snippet="" and renders with no description at all. Enrich the
            # scanned card instead; its copy is already correct.
            scanned_i = seen_by_rel.get(rel)
            if scanned_i is not None:
                row = reviews[scanned_i]
                if p.get("image") and not row.get("image"):
                    row["image"] = p["image"]
                if p.get("product_name") and not row.get("product_name"):
                    row["product_name"] = p["product_name"]
                if quality and not row.get("score"):
                    row["score"] = quality
                seen[(slug, title)] = scanned_i
                continue
            reviews.append({
                "slug": slug,
                "name": self._niche_name(slug),
                "title": title,
                "updated": (p.get("created_at") or "")[:10] or today,
                "rel": f"/reviews/{slug}/{filename}",
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

    def deploy_category_hub(self, niche: str, posts: list = None, all_categories: list = None) -> str:
        """Deploy a brand-new category hub at its canonical /reviews/<niche>/ location.

        In the rich pipeline write_files makes reviews/<niche>/index.html mirror
        the newest article, so links to the reviews path land on a real review —
        not a duplicate category listing with a cross-canonical to /<niche>/.
        When the article this cycle just deployed belongs to this niche, mirror
        it; otherwise fall back to a premium category listing.

        Returns the path written (or "" on refusal), matching deploy_content.
        """
        try:
            all_categories = list(all_categories or [niche])
            if self._last_content and self._last_niche == niche:
                # _last_content is only ever assigned after the products checks
                # in deploy_content() pass, so the mirror is product-backed.
                return self.deploy_content(niche, self._last_content,
                                           all_categories=all_categories)
            posts = posts or []
            if not posts:
                logger.warning(f"[SiteDeployer] Skipping new category hub for {niche}: no posts available (would deploy placeholder)")
                return ""
            rich = [r for r in self._reviews([niche], posts, niche)
                    if r.get("slug") == niche]
            if not rich:
                rich = posts
            html = self._category_html(niche, rich, all_categories)
            path = f"reviews/{niche}/index.html"
            self.deployer.deploy_html(html, path)
            logger.info(f"[SiteDeployer] Deployed premium category hub for {niche}")
            return path
        except Exception as e:
            logger.error(f"[SiteDeployer] Category hub failed: {e}")
            return ""

    def _published_today(self, niche: str, today: str) -> int:
        """How many distinct article pages this niche shipped on ``today``.

        Counts post rows created today that carry a non-empty, non-index
        filename — a row only ever gets a filename after its article page
        shipped (add_post is called at publish time with the filename, and
        ``update_post_filename`` stamps it onto the newest empty-filename row).
        Distinct filenames, so at cap N the same canonical URL can still be
        refreshed N times without minting extra quota for identical slugs.
        """
        try:
            rows = self.state.get_posts_for_niche(niche) or []
        except Exception as e:
            logger.warning(f"[SiteDeployer] could not read posts for {niche!r}: {e}")
            return 0
        pages = set()
        for p in rows:
            filename = (p.get("filename") or "").strip()
            created = (p.get("created_at") or "")
            if filename and filename != "index.html" and created.startswith(today):
                pages.add(filename)
        return len(pages)

    def deploy_content(self, niche: str, content: dict, all_categories: list = None,
                       article_filename: str = None,
                       require_products: bool = False) -> str:
        """Deploy one premium review page for a niche.

        Returns the repo-relative path that was written, or "" on refusal or
        failure.

        The return value is the whole point. The page path is derived from
        post_title inside ``_title_slug()``, but callers passed no
        ``article_filename`` and only ever saw a bool, so the identity of the
        article that actually shipped was discarded at this boundary: the page
        went out as ``reviews/<niche>/index.html`` and every post row kept an
        empty ``filename``. That is why nothing downstream could address a
        specific article - social media resolved products by niche, and
        ``_reviews()`` could not verify a page existed for a post it had no
        filename for.

        require_products stays opt-in because the state-redeploy path
        (DeployAgent._deploy_site) rebuilds from state post metadata, which
        carries no products key at all. The fresh-publish path opts in - a
        payload with no products renders a product-less page whose cards all
        fall back to the generic category graphic instead of a product photo.
        """
        try:
            all_categories = all_categories or []
            from run_cycle import build_article_page, _SITE_URL, apply_ai_seo_page
            from src.deployment import niche_relevance
            today = datetime.now().strftime("%Y-%m-%d")
            products = content.get("products") or []
            # Daily per-niche publish cap: a niche may mint at most N article
            # pages per day (default 1). This is the single choke point
            # every publish path funnels through (the daemon's run_full_cycle
            # and DeployAgent._deploy_site), so a loopy trigger cannot keep
            # forging near-identical review URLs all day. Applies only to real
            # article files — hub/index.html writes (article_filename=None)
            # are page rebuilds, not new reviews, so they are never capped.
            cap = int(os.environ.get("ABVORN_MAX_NICHE_PUBLISHES_PER_DAY", "1") or "1")
            if (article_filename and cap > 0 and self.state
                    and self._published_today(niche, today) >= cap):
                logger.warning(
                    "[SiteDeployer] Refusing to publish %s: niche %s already "
                    "published %d article page(s) today (cap %d). Keeping the "
                    "live page instead of minting another near-identical "
                    "review URL.",
                    article_filename, niche,
                    self._published_today(niche, today), cap,
                )
                return ""
            if require_products and not products:
                logger.warning(
                    "[SiteDeployer] Refusing to publish %s: a fresh article "
                    "payload carried no products at all, which renders a "
                    "product-less hub — keeping the currently published page. "
                    "Product-less pages ship no product photo, so every card "
                    "falls back to the generic category graphic.",
                    niche,
                )
                return ""
            if _products_are_placeholder(products):
                logger.warning(
                    "[SiteDeployer] Refusing to publish %s: %d product(s) and "
                    "none carry an ASIN (placeholder payload) — keeping the "
                    "currently published page instead of shipping a "
                    "product-less hub",
                    niche, len(products),
                )
                return ""
            post_title = content.get("post_title", "") or ""
            relevance = niche_relevance(niche, post_title, products)
            if not relevance["relevant"]:
                logger.warning(
                    "[SiteDeployer] Refusing to publish %s: %s — title %r is "
                    "about something else, so it would ship as a real, "
                    "self-canonical review inside the wrong niche. Keeping "
                    "the currently published page.",
                    niche, relevance["reason"], post_title[:90],
                )
                return ""
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
                canonical_url=(
                    f"{_SITE_URL}/reviews/{niche}/{article_filename}"
                    if article_filename else ""
                ),
            )
            self._last_content = content
            self._last_niche = niche
            path = f"reviews/{niche}/{'index.html' if not article_filename else article_filename}"
            # run_cycle.write_files() injects AI-SEO after building, but this
            # path pushes straight to GitHub and never touches a local docs/
            # tree, so the page went out with no Article JSON-LD and no
            # <time datetime> on its dates. Inject in memory before shipping.
            html = apply_ai_seo_page(path, html)
            self.deployer.deploy_html(html, path)
            logger.info(f"[SiteDeployer] Deployed premium article for {niche} as {path}")
            return path
        except Exception as e:
            logger.error(f"[SiteDeployer] Article deploy failed: {e}")
            return ""


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
        # Watermark, not a truncated id set: a 200-entry window against a
        # ~460-deep backlog made every evicted id look unhandled forever, so
        # the same tv page was re-deployed and re-announced each cycle.
        fresh = bus_progress.fresh_events(self.state, _DRAFTED_WATERMARK, events)
        return {"events": fresh}

    def _mark_drafted_handled(self, event_ids):
        bus_progress.advance(self.state, _DRAFTED_WATERMARK, event_ids)

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
        """Deploy for a niche and return the page path that was written (or "").

        The path is the article's identity. It used to be thrown away, so every
        post row kept an empty ``filename`` and ``content.published`` carried no
        slug or url - which left social media unable to address a specific
        article and left ``_reviews()`` unable to verify a page existed.
        """
        all_niches_data = self.state.get_all_niches()
        all_slugs = [n["slug"] for n in all_niches_data]
        all_posts = []
        for slug in all_slugs:
            all_posts.extend(self.state.get_posts_for_niche(slug))
        deployed_path = ""
        # Filenames already spoken for in this niche, so a repeated title cannot
        # overwrite an earlier post's live page. Read this niche's posts directly
        # rather than filtering all_posts: all_posts is assembled from the
        # niches table, so a niche missing from it yields an empty set.
        try:
            niche_rows = self.state.get_posts_for_niche(niche) if self.state else []
        except Exception as e:
            logger.warning(f"[DeployAgent] could not read posts for {niche!r}: {e}")
            niche_rows = []
        taken = {(p.get("filename") or "").strip() for p in niche_rows} - {""}
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
            # Derive the article's own filename from its title. Without it the
            # page ships as the category index and the post can never be
            # addressed again.
            post_title_payload = str(deploy_content.get("post_title") or "").strip()
            if not post_title_payload and niche_rows:
                post_title_payload = str(niche_rows[0].get("title") or "").strip()
            deployed_path = self.site_deployer.deploy_content(
                niche,
                deploy_content,
                all_categories=all_slugs,
                article_filename=_article_filename(post_title_payload, taken),
                require_products=True,
            ) or ""
        else:
            posts = self.state.get_posts_for_niche(niche)
            if posts:
                latest = posts[0]
                content = {
                    "post_title": latest.get("title", ""),
                    "content": latest.get("filename", ""),
                    "product_name": latest.get("product_name", ""),
                }
                post_title_state = str(latest.get("title") or "").strip()
                deployed_path = self.site_deployer.deploy_content(
                    niche,
                    content,
                    all_categories=all_slugs,
                    article_filename=_article_filename(post_title_state, taken),
                ) or ""
        # Only rebuild nav/hubs when a page actually shipped. A refused deploy
        # (daily per-niche cap, product gate, relevance) leaves the posts list
        # untouched, so repushing index.html + every category page is churn with
        # no content change — a loopy trigger would otherwise keep forcing 4
        # near-identical index commits per refused cycle (the flood's commit
        # shape: one article + index + robot-vacuums/tv/laptops pages).
        if not deployed_path:
            logger.warning(
                "[DeployAgent] Refusing site rebuild for %s: no article page "
                "was written (cap/product/relevance gate).", niche,
            )
            return ""
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
        return deployed_path

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
            deployed_path = ""
            if self.site_deployer and self.state:
                deployed_path = await asyncio.to_thread(
                    self._deploy_site,
                    niche,
                    content_payload,
                ) or ""

            # Identity travels with the event. Without a title/slug the
            # Ambassador could only build "Just published our {niche} guide!"
            # from the niche, so every announcement of a given niche carried
            # byte-identical text and the same product card.
            published = {"niche": niche, "status": "deployed"}
            if content_payload:
                title = str(content_payload.get("post_title") or "").strip()
                products = content_payload.get("products") or []
                product_name = str(
                    content_payload.get("product_name")
                    or (products[0].get("name", "") if products else "")
                ).strip()
                if title:
                    published["title"] = title
                if product_name:
                    published["product_name"] = product_name
                slug = str(content_payload.get("slug") or "").strip()
                if slug:
                    published["slug"] = slug

            # The path is the only authoritative link to the page that shipped.
            # It carries the slug and the article filename, which is what lets
            # media selection address this article instead of the whole niche,
            # and what _reviews() needs to verify the page really exists.
            page_path = str(deployed_path or "").strip()
            if page_path:
                published["path"] = page_path
                filename = page_path.rsplit("/", 1)[-1]
                if filename and filename != "index.html":
                    published["filename"] = filename
                    from run_cycle import _SITE_URL
                    published["url"] = f"{_SITE_URL}/{page_path}"
                # The second path segment is the niche *directory*. Only use it
                # when nothing more specific arrived - overwriting a payload's
                # article slug with the niche would re-break per-article
                # targeting, which is the thing this whole path fixes.
                if not published.get("slug"):
                    path_parts = page_path.split("/")
                    if len(path_parts) >= 2 and path_parts[1]:
                        published["slug"] = path_parts[1]
                self._record_published_filename(niche, filename)

            if not page_path:
                logger.warning(
                    "[DeployAgent] Nothing was written for %s - publishing "
                    "content.published without a path, so no article identity "
                    "is available downstream.", niche,
                )

            self.bus.publish("content.published", published)
            if handled_id is not None:
                self._mark_drafted_handled([handled_id])
            return {"niche": niche, "status": "deployed", "path": page_path}

    def _record_published_filename(self, niche: str, filename: str) -> None:
        """Stamp the deployed filename onto the newest post row for the niche.

        Posts were created with an empty ``filename``, and
        ``SiteDeployer._reviews()`` skips any post without one because a post
        with no article page is not a published review. Recording it here means
        the next homepage build can see and verify the page.
        """
        if not self.state or not filename or filename == "index.html":
            return
        try:
            posts = self.state.get_posts_for_niche(niche) or []
        except Exception as e:
            logger.warning(f"[DeployAgent] could not read posts for {niche!r}: {e}")
            return
        for post in posts:
            if (post.get("filename") or "").strip() == filename:
                return
            title = str(post.get("title") or "").strip()
            if not title:
                continue
            try:
                self.state.update_post_filename(post.get("id"), filename)
                logger.info(
                    f"[DeployAgent] recorded filename {filename!r} for post "
                    f"{post.get('id')} ({title[:60]!r})"
                )
            except Exception as e:
                logger.warning(f"[DeployAgent] could not record filename: {e}")
            return

    async def reflect(self, outcome):
        if self.drive:
            succeeded = bool(outcome and outcome.get("status") == "deployed")
            self.drive.log_outcome("deploy", succeeded=succeeded)
