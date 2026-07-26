import asyncio, json, logging
from datetime import datetime
from .base import AgentBase
from ..brain.retriever import KnowledgeRetriever
from ..agents.researcher import research_niche
from ..core.models import ModelRouter

logger = logging.getLogger("abvorn.orchestrator")

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
            products = research_niche(niche, self.router)
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
            logger.warning(f"[ResearchAgent] Zero products — consider switching search strategy")


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
            niche = last['niche']
            if not self.soul_check("generate_content", {"niche": niche}):
                logger.info(f"[ContentAgent] Soul blocked content for {niche}")
                return "wait"
            return f"generate:{niche}"
        return "wait"

    async def act(self, decision):
        if decision.startswith("generate:"):
            niche = decision.split(":", 1)[1]
            logger.info(f"[ContentAgent] Generating content for: {niche}")
            result = self.pipeline.run(niche, self.router, persona={})
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


CSS_SHARED = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;-webkit-font-smoothing:antialiased}
body{color:#1f2937;background:#fff;line-height:1.6}
.container{max-width:1080px;margin:0 auto;padding:0 24px}
a{color:#2563eb;text-decoration:none}
a:hover{text-decoration:underline}
nav{background:#fff;border-bottom:1px solid #e5e7eb;position:sticky;top:0;z-index:10}
nav .inner{max-width:1080px;margin:0 auto;padding:0 24px;display:flex;align-items:center;height:56px;gap:32px}
nav .logo{font-weight:700;font-size:1.1rem;color:#1f2937;text-decoration:none}
nav .logo:hover{text-decoration:none}
nav .nav-link{font-size:.9rem;color:#6b7280;text-decoration:none;padding:4px 0;border-bottom:2px solid transparent}
nav .nav-link:hover{color:#1f2937;border-bottom-color:#2563eb;text-decoration:none}
nav .nav-link.current{color:#1f2937;border-bottom-color:#2563eb}
h1{font-size:2rem;font-weight:700;letter-spacing:-0.02em;line-height:1.2}
h2{font-size:1.4rem;font-weight:600;margin-bottom:24px;letter-spacing:-0.01em}
.hero{padding:64px 0 48px}
.hero h1{margin-bottom:12px}
.hero p{font-size:1.1rem;color:#6b7280;max-width:600px}
.pick-card{display:flex;gap:32px;padding:32px;border:1px solid #e5e7eb;border-radius:12px;margin-bottom:24px;align-items:flex-start}
.pick-card .rank{flex-shrink:0;width:48px;height:48px;background:#2563eb;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.2rem}
.pick-card .rank.budget{background:#059669}
.pick-card .rank.upgrade{background:#7c3aed}
.pick-card .info{flex:1}
.pick-card .info h3{font-size:1.2rem;font-weight:600;margin-bottom:4px}
.pick-card .info .price{color:#059669;font-weight:600;font-size:.95rem;margin-bottom:8px}
.pick-card .info p{font-size:.95rem;color:#6b7280;margin-bottom:12px}
.pick-card .info .badge{display:inline-block;background:#dbeafe;color:#1d4ed8;font-size:.75rem;font-weight:600;padding:2px 10px;border-radius:100px;margin-right:8px}
.pick-card .info .badge.budget{background:#d1fae5;color:#065f46}
.pick-card .info .badge.upgrade{background:#ede9fe;color:#5b21b6}
.grid-3{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:24px}
.cat-card{padding:24px;border:1px solid #e5e7eb;border-radius:8px;transition:box-shadow .2s,transform .15s}
.cat-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.06);transform:translateY(-2px);text-decoration:none}
.cat-card .cat-name{font-weight:600;font-size:1.05rem;color:#1f2937;margin-bottom:4px}
.cat-card .cat-count{font-size:.85rem;color:#9ca3af}
.post-card{padding:20px;border:1px solid #e5e7eb;border-radius:8px;transition:box-shadow .2s}
.post-card:hover{box-shadow:0 2px 12px rgba(0,0,0,.04)}
.post-card .post-title{font-weight:600;margin-bottom:4px;color:#1f2937}
.post-card .post-meta{font-size:.85rem;color:#9ca3af}
.section{padding:48px 0}
.section-title{font-size:1.1rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:24px}
.affiliate-banner{background:#fefce8;border:1px solid #fde68a;border-radius:8px;padding:16px 20px;font-size:.85rem;color:#92400e;margin:32px 0;text-align:center}
article{max-width:720px;margin:0 auto;padding:32px 0}
article h1{font-size:1.8rem;margin-bottom:8px}
article .meta{color:#6b7280;font-size:.9rem;margin-bottom:32px;padding-bottom:16px;border-bottom:1px solid #e5e7eb}
article .content p{margin:16px 0;font-size:1.05rem;color:#374151}
article .content h2{margin:32px 0 12px;font-size:1.25rem}
article .content ul{padding-left:24px;margin:12px 0}
article .content li{margin:6px 0;color:#374151}
footer{padding:40px 0;border-top:1px solid #e5e7eb;text-align:center}
footer p{font-size:.85rem;color:#9ca3af;margin-bottom:4px}
@media(max-width:640px){.pick-card{flex-direction:column;gap:16px}.grid-3{grid-template-columns:1fr}}
"""

class SiteDeployer:
    """Generates Wirecutter-style HTML pages and deploys to GitHub Pages."""

    def __init__(self, deployer, state):
        self.deployer = deployer
        self.state = state

    def _nav_html(self, current: str = "", categories: list = None) -> str:
        cats = categories or []
        links = "".join(f'<a class="nav-link{f" current" if c == current else ""}" href="/{c}/">{c.replace("-"," ").title()}</a>' for c in cats)
        return f'<nav><div class="inner"><a class="logo" href="/">Tech & Gadgets</a>{links}</div></nav>'

    def deploy_root_index(self, niches: list = None, posts: list = None) -> bool:
        try:
            niches = niches or []
            posts = posts or []
            cats = ""
            for n in niches:
                slug = n if isinstance(n, str) else n.get("slug", "")
                count = ""
                if not isinstance(n, str):
                    cnt = n.get("total_posts", 0)
                    if cnt:
                        count = f'<div class="cat-count">{cnt} review{"s" if cnt!=1 else ""}</div>'
                cats += f'<a class="cat-card" href="/{slug}/"><div class="cat-name">{slug.replace("-"," ").title()}</div>{count}</a>'

            recent = ""
            for p in posts[:6]:
                title = p.get("title") or p.get("post_title", "")
                slug = p.get("slug") or p.get("niche_slug", "")
                recent += f'<div class="post-card"><div class="post-title"><a href="/{slug}/">{title}</a></div><div class="post-meta">{slug.replace("-"," ").title()}</div></div>'

            html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tech & Gadgets — Expert Reviews for Smart Shoppers</title>
<meta name="description" content="Independent, expert reviews of the best tech products. We test and compare so you can buy with confidence.">
<style>{CSS_SHARED}</style>
</head><body>
{self._nav_html("home", niches)}

<section class="hero">
<div class="container">
<h1>The best tech, reviewed.</h1>
<p>We test hundreds of products so you don't have to. Independent, honest, data-driven reviews across every category.</p>
</div>
</section>

<section class="section">
<div class="container">
<div class="section-title">All Categories</div>
<div class="grid-3">{cats or '<div style="color:#9ca3af">Categories coming soon</div>'}</div>
</div>
</section>

<section class="section">
<div class="container">
<div class="section-title">Latest Reviews</div>
<div class="grid-3">{recent or '<div style="color:#9ca3af">Reviews coming soon</div>'}</div>
</div>
</section>

<div class="container"><div class="affiliate-banner">When you buy through our links, we may earn a commission. As an Amazon Associate we earn from qualifying purchases.</div></div>

<footer><p>Tech & Gadgets is part of the Abvorn network.</p><p>Independent reviews. Honest recommendations.</p></footer>
</body></html>"""
            self.deployer.deploy_html(html, "index.html")
            logger.info("[SiteDeployer] Deployed Wirecutter-style root index")
            return True
        except Exception as e:
            logger.error(f"[SiteDeployer] Root index failed: {e}")
            return False

    def deploy_homepage(self, site_slug: str = "tech-gadgets",
                         niches: list = None, posts: list = None) -> bool:
        try:
            niches = niches or []
            posts = posts or []
            cat_list = "".join(f'<a class="cat-card" href="/{n}/"><div class="cat-name">{n.replace("-"," ").title()}</div></a>' for n in niches)

            # Build top-picks section from recent posts
            picks = ""
            for i, p in enumerate(posts[:3]):
                title = p.get("title") or p.get("post_title", "")
                slug = p.get("slug") or p.get("niche_slug", "")
                rank_class = ["", "budget", "upgrade"][i] if i < 3 else ""
                rank_label = ["Our pick", "Budget pick", "Upgrade pick"][i] if i < 3 else f"#{i+1}"
                picks += f"""<div class="pick-card">
<div class="rank {rank_class}">{i+1}</div>
<div class="info">
<div class="badge {rank_class}">{rank_label}</div>
<h3>{title}</h3>
<p>A detailed look at why this stands above the competition in our testing.</p>
<a href="/{slug}/">Read the review →</a>
</div></div>"""

            html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tech & Gadgets — Reviews</title>
<meta name="description" content="Expert reviews across tech categories.">
<style>{CSS_SHARED}</style>
</head><body>
{self._nav_html("", niches)}

<section class="hero">
<div class="container">
<h1>Our latest reviews</h1>
<p>Every product tested head-to-head. No fluff, just what you need to know.</p>
</div>
</section>

<section class="section">
<div class="container">
<div class="section-title">Top Picks</div>
{picks or '<div style="color:#9ca3af">No reviews yet — first one coming soon</div>'}

<div class="section-title" style="margin-top:48px">Categories</div>
<div class="grid-3">{cat_list or '<div style="color:#9ca3af">No categories yet</div>'}</div>
</div>
</section>

<div class="container"><div class="affiliate-banner">When you buy through our links, we may earn a commission.</div></div>

<footer><p>Tech & Gadgets · Independent reviews · Part of the Abvorn network</p></footer>
</body></html>"""
            self.deployer.deploy_html(html, f"{site_slug}/index.html")
            logger.info(f"[SiteDeployer] Deployed site homepage for {site_slug}")
            return True
        except Exception as e:
            logger.error(f"[SiteDeployer] Homepage failed: {e}")
            return False

    def deploy_category_page(self, niche: str, posts: list = None, all_categories: list = None) -> bool:
        try:
            posts = posts or []
            all_categories = all_categories or []
            post_rows = ""
            for i, p in enumerate(posts[:5]):
                title = p.get("title") or p.get("post_title", "")
                slug = p.get("slug") or niche
                rank_label = ["Our pick", "Budget pick", "Upgrade pick", f"Also great", f"Also great"][i] if i < 5 else ""
                rank_class = ["", "budget", "upgrade", "", ""][i] if i < 5 else ""
                post_rows += f"""<div class="pick-card">
<div class="rank {rank_class}">{i+1}</div>
<div class="info">
<div class="badge {rank_class}">{rank_label}</div>
<h3>{title}</h3>
<p>In-depth testing and honest comparison. See why this made our list.</p>
<a href="/{slug}/">Read full review →</a>
</div></div>"""

            nav_links = "".join(f'<a class="nav-link{f" current" if c == niche else ""}" href="/{c}/">{c.replace("-"," ").title()}</a>' for c in all_categories)
            html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Best {niche.replace("-"," ").title()} — Tech & Gadgets</title>
<meta name="description" content="The best {niche.replace('-',' ')} reviewed and compared. Our expert picks after hours of testing.">
<style>{CSS_SHARED}</style>
</head><body>
<nav><div class="inner"><a class="logo" href="/">Tech & Gadgets</a>{nav_links}</div></nav>

<section class="hero">
<div class="container">
<h1>The Best {niche.replace("-"," ").title()}</h1>
<p>We tested the top contenders to find the ones worth your money.</p>
</div>
</section>

<section class="section">
<div class="container">
<div class="section-title">Our Top Picks</div>
{post_rows or '<div style="color:#9ca3af;padding:32px;text-align:center">Reviews for this category are being researched. Check back soon.</div>'}
</div>
</section>

<div class="container"><div class="affiliate-banner">We earn from qualifying purchases.</div></div>

<footer><p>Tech & Gadgets · Independent reviews</p></footer>
</body></html>"""
            self.deployer.deploy_html(html, f"{niche}/index.html")
            logger.info(f"[SiteDeployer] Deployed category page for {niche}")
            return True
        except Exception as e:
            logger.error(f"[SiteDeployer] Category page failed: {e}")
            return False

    def deploy_content(self, niche: str, content: dict, all_categories: list = None) -> bool:
        try:
            all_categories = all_categories or []
            post_title = content.get("post_title", niche)
            article_html = content.get("article_html", content.get("content", ""))
            intro = content.get("intro", "")
            meta_desc = content.get("meta_description", "")[:160]
            product_name = content.get("product_name", "")

            nav_links = "".join(f'<a class="nav-link{f" current" if c == niche else ""}" href="/{c}/">{c.replace("-"," ").title()}</a>' for c in all_categories)
            html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{post_title} — Tech & Gadgets</title>
<meta name="description" content="{meta_desc}">
<style>{CSS_SHARED}</style>
</head><body>
<nav><div class="inner"><a class="logo" href="/">Tech & Gadgets</a>{nav_links}</div></nav>

<article>
<h1>{post_title}</h1>
<div class="meta">{product_name} · Updated 2026</div>
{intro}
<div class="content">{article_html}</div>
<div class="affiliate-banner">We earn a commission if you buy through our links, at no extra cost to you. Our opinions are our own.</div>
</article>

<footer><p>Tech & Gadgets · Independent reviews since 2026</p></footer>
</body></html>"""
            self.deployer.deploy_html(html, f"{niche}/index.html")
            logger.info(f"[SiteDeployer] Deployed article for {niche}")
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
        return {"events": self.bus.get_recent_events("content.drafted")}

    async def decide(self, perception):
        if perception.get("events"):
            last = max(perception["events"], key=lambda e: e["created_at"])
            niche = last['niche']
            if not self.soul_check("deploy_content", {"niche": niche}):
                logger.info(f"[DeployAgent] Soul blocked deploy for {niche}")
                return "wait"
            return f"deploy:{niche}"
        return "wait"

    async def act(self, decision):
        if decision.startswith("deploy:"):
            niche = decision.split(":", 1)[1]
            logger.info(f"[DeployAgent] Deploying content for: {niche}")
            if self.site_deployer and self.state:
                all_niches_data = self.state.get_all_niches()
                all_slugs = [n["slug"] for n in all_niches_data]
                all_posts = []
                for s in all_slugs:
                    all_posts.extend(self.state.get_posts_for_niche(s))
                posts = self.state.get_posts_for_niche(niche)
                if posts:
                    latest = posts[0]
                    content = {
                        "post_title": latest.get("title", ""),
                        "content": latest.get("filename", ""),
                        "product_name": latest.get("product_name", ""),
                    }
                    self.site_deployer.deploy_content(niche, content, all_categories=all_slugs)
                self.site_deployer.deploy_root_index(niches=all_niches_data, posts=all_posts)
                self.site_deployer.deploy_homepage(niches=all_slugs, posts=all_posts)
                for slug in all_slugs:
                    niche_posts = [p for p in all_posts if p.get("niche_slug") == slug]
                    self.site_deployer.deploy_category_page(slug, posts=niche_posts, all_categories=all_slugs)
            self.bus.publish("content.published", {"niche": niche, "status": "deployed"})
            return {"niche": niche, "status": "deployed"}

    async def reflect(self, outcome):
        if self.drive:
            succeeded = bool(outcome and outcome.get("status") == "deployed")
            self.drive.log_outcome("deploy", succeeded=succeeded)
