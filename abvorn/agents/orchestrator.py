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
nav .inner{max-width:1080px;margin:0 auto;padding:0 24px;display:flex;align-items:center;height:56px;justify-content:space-between}
nav .logo{display:flex;align-items:center;gap:8px;font-weight:700;font-size:1.1rem;color:#1f2937;text-decoration:none}
nav .logo img{height:28px;width:auto}
nav .logo:hover{text-decoration:none}
.nav-links{display:flex;align-items:center;gap:24px}
.dropdown{position:relative}
.dropdown-btn{background:none;border:none;cursor:pointer;font-size:.9rem;color:#6b7280;padding:4px 0;border-bottom:2px solid transparent;font-family:inherit;display:flex;align-items:center;gap:4px}
.dropdown-btn:hover{color:#1f2937;border-bottom-color:#2563eb}
.dropdown-btn::after{content:'';display:inline-block;width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-top:4px solid #6b7280;margin-left:4px}
.dropdown-menu{display:none;position:absolute;top:100%;left:0;background:#fff;border:1px solid #e5e7eb;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.08);min-width:200px;padding:8px;z-index:20;max-height:400px;overflow-y:auto}
.dropdown:hover .dropdown-menu{display:block}
.dropdown-menu a{display:block;padding:8px 12px;font-size:.9rem;color:#374151;border-radius:4px;text-decoration:none}
.dropdown-menu a:hover{background:#f3f4f6;color:#2563eb;text-decoration:none}
.nav-link{font-size:.9rem;color:#6b7280;text-decoration:none;padding:4px 0;border-bottom:2px solid transparent;white-space:nowrap}
.nav-link:hover{color:#1f2937;border-bottom-color:#2563eb;text-decoration:none}
.nav-link.current{color:#1f2937;border-bottom-color:#2563eb}
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
.social{margin-top:16px;display:flex;gap:20px;justify-content:center}
.social a{color:#9ca3af;text-decoration:none;display:flex;align-items:center}
.social a:hover{color:#1f2937}
.social svg{width:22px;height:22px;fill:currentColor}
.story-section{padding:48px 0;background:#f9fafb;border-top:1px solid #e5e7eb}
.story-section .container{max-width:680px;margin:0 auto;padding:0 24px}
.story-section h2{font-size:1.3rem;font-weight:600;margin-bottom:12px;text-align:center}
.story-section p{font-size:1rem;color:#555;line-height:1.7;margin-bottom:12px}
.story-section .trust-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin:24px 0;list-style:none}
.story-section .trust-item{padding:16px;background:#fff;border-radius:8px;border:1px solid #e5e7eb}
.story-section .trust-item strong{display:block;font-size:.95rem;color:#1f2937;margin-bottom:4px}
.story-section .trust-item span{font-size:.85rem;color:#6b7280}
@media(max-width:640px){.pick-card{flex-direction:column;gap:16px}.grid-3{grid-template-columns:1fr}}
"""

SVG_TIKTOK = '<svg viewBox="0 0 24 24"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg>'
SVG_INSTAGRAM = '<svg viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>'
SVG_X = '<svg viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'
SOCIAL_HTML = '<div class="social"><a href="https://www.tiktok.com/@abvorn" target="_blank" aria-label="TikTok">' + SVG_TIKTOK + '</a><a href="https://www.instagram.com/abvorn/" target="_blank" aria-label="Instagram">' + SVG_INSTAGRAM + '</a><a href="https://x.com/Abvorn" target="_blank" aria-label="X">' + SVG_X + '</a></div>'

STORY_HTML = """<section class="story-section">
<div class="container">
<h2>Why Abvorn?</h2>
<p>Most buying advice is paid, not earned. Sponsored placements, undisclosed commissions, and recycled press releases masquerading as reviews. We started Abvorn to fix that.</p>
<p>Every recommendation here comes from real testing, real research, and real opinions. We buy the products, we test them head-to-head, and we tell you which one to buy — no favours, no sponsorships, no compromises.</p>
<ul class="trust-list">
<li class="trust-item"><strong>Independent</strong><span>Zero sponsor influence. We buy what we test.</span></li>
<li class="trust-item"><strong>Transparent</strong><span>We show our work. Every pick has a reason.</span></li>
<li class="trust-item"><strong>Expert-led</strong><span>Specialist reviewers who know their categories.</span></li>
<li class="trust-item"><strong>Reader-first</strong><span>We recommend what we'd buy our own family.</span></li>
</ul>
<p style="text-align:center;font-size:.9rem;color:#888"><em>Buy with confidence.</em></p>
</div>
</section>"""

SITE_BASE = "/abvorn"
FORCE_LOGO = f'<link rel="icon" type="image/png" href="{SITE_BASE}/assets/favicon.png"><link rel="apple-touch-icon" href="{SITE_BASE}/assets/logo.png">'

class SiteDeployer:
    """Generates Wirecutter-style HTML pages and deploys to GitHub Pages."""

    def __init__(self, deployer, state):
        self.deployer = deployer
        self.state = state

    def _nav_html(self, current: str = "", categories: list = None) -> str:
        cats = categories or []
        featured = cats[:4]
        rest = cats[4:]
        b = SITE_BASE
        featured_links = "".join(f'<a class="nav-link" href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in featured)
        more_items = "".join(f'<a href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in rest)
        dropdown = f'<div class="dropdown"><button class="dropdown-btn">More</button><div class="dropdown-menu">{more_items}</div></div>' if rest else ""
        links = featured_links + dropdown
        return f'<nav><div class="inner"><a class="logo" href="{b}/"><img src="{b}/assets/logo.png" alt="Abvorn">Abvorn</a><div class="nav-links">{links}</div></div></nav>'

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
                cats += f'<a class="cat-card" href="{SITE_BASE}/{slug}/"><div class="cat-name">{slug.replace("-"," ").title()}</div>{count}</a>'

            recent = ""
            for p in posts[:6]:
                title = p.get("title") or p.get("post_title", "")
                slug = p.get("slug") or p.get("niche_slug", "")
                recent += f'<div class="post-card"><div class="post-title"><a href="{SITE_BASE}/{slug}/">{title}</a></div><div class="post-meta">{slug.replace("-"," ").title()}</div></div>'

            html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Abvorn — Product Reviews & Buying Guides</title>
<meta name="description" content="Independent, expert reviews across every category. We test so you can buy with confidence.">
{FORCE_LOGO}
<style>{CSS_SHARED}</style>
</head><body>
{self._nav_html("home", [n if isinstance(n,str) else n.get("slug","") for n in niches]) if niches else f'<nav><div class="inner"><a class="logo" href="{SITE_BASE}/"><img src="{SITE_BASE}/assets/logo.png" alt="Abvorn">Abvorn</a></div></nav>'}

<section class="hero">
<div class="container">
<h1>The best products, reviewed.</h1>
<p>We test hundreds of products across dozens of categories so you don't have to. Independent, honest, data-driven.</p>
</div>
</section>

{STORY_HTML}

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

<div class="container"><div class="affiliate-banner">When you buy through our links, we may earn a commission. Our opinions are our own.</div></div>

<footer><p>Abvorn · Independent reviews · Honest recommendations</p>{SOCIAL_HTML}</footer>
</body></html>"""
            self.deployer.deploy_html(html, "index.html")
            logger.info("[SiteDeployer] Deployed Wirecutter-style root index")
            return True
        except Exception as e:
            logger.error(f"[SiteDeployer] Root index failed: {e}")
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
<a href="{b}/{slug}/">Read full review →</a>
</div></div>"""

            b = SITE_BASE
            nav_links = "".join(f'<a class="nav-link" href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in all_categories[:4])
            more_items = "".join(f'<a href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in all_categories[4:])
            dropdown = f'<div class="dropdown"><button class="dropdown-btn">More</button><div class="dropdown-menu">{more_items}</div></div>' if all_categories[4:] else ""
            html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Best {niche.replace("-"," ").title()} — Abvorn</title>
<meta name="description" content="The best {niche.replace('-',' ')} reviewed and compared. Our expert picks after hours of testing.">
{FORCE_LOGO}
<style>{CSS_SHARED}</style>
</head><body>
<nav><div class="inner"><a class="logo" href="{b}/"><img src="{b}/assets/logo.png" alt="Abvorn">Abvorn</a><div class="nav-links">{nav_links}{dropdown}</div></div></nav>

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

<footer><p>Abvorn · Independent reviews</p>{SOCIAL_HTML}</footer>
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

            b = SITE_BASE
            nav_links = "".join(f'<a class="nav-link" href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in all_categories[:4])
            more_items = "".join(f'<a href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in all_categories[4:])
            dropdown = f'<div class="dropdown"><button class="dropdown-btn">More</button><div class="dropdown-menu">{more_items}</div></div>' if all_categories[4:] else ""
            html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{post_title} — Abvorn</title>
<meta name="description" content="{meta_desc}">
{FORCE_LOGO}
<style>{CSS_SHARED}</style>
</head><body>
<nav><div class="inner"><a class="logo" href="{b}/"><img src="{b}/assets/logo.png" alt="Abvorn">Abvorn</a><div class="nav-links">{nav_links}{dropdown}</div></div></nav>

<article>
<h1>{post_title}</h1>
<div class="meta">{product_name} · Updated 2026</div>
{intro}
<div class="content">{article_html}</div>
<div class="affiliate-banner">We earn a commission if you buy through our links, at no extra cost to you. Our opinions are our own.</div>
</article>

<footer><p>Abvorn · Independent reviews since 2026</p>{SOCIAL_HTML}</footer>
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
