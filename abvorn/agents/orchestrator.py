import asyncio, json, logging, os
from datetime import datetime
from .base import AgentBase
from ..brain.retriever import KnowledgeRetriever
from ..agents.researcher import research_niche
from ..core.models import ModelRouter

logger = logging.getLogger("abvorn.orchestrator")

# Centralized affiliate tag: AMAZON_TAG secret, falling back to the real tag.
def _amazon_tag() -> str:
    return os.environ.get("AMAZON_TAG") or "viraltestco-20"

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
:root{--primary:#1a1a1a;--primary-dark:#0a0a0a;--primary-light:#f6f5f2;--accent:#c98a2c;--accent-dark:#996015;--green:#059669;--green-light:#d1fae5;--purple:#7c3aed;--purple-light:#ede9fe;--bg:#fff;--bg-alt:#f6f5f2;--text:#1a1a1a;--text-secondary:#666;--text-muted:#666;--border:#e8e8e8;--shadow-sm:0 1px 2px rgba(0,0,0,.04);--shadow-md:0 4px 12px rgba(0,0,0,.06);--shadow-lg:0 8px 24px rgba(0,0,0,.08);--radius-sm:8px;--radius-md:12px;--radius-lg:16px;--font-display:'Libre Franklin',-apple-system,sans-serif;--font-body:'Inter',-apple-system,BlinkMacSystemFont,sans-serif}
@media(prefers-color-scheme:dark){:root{--bg:#0a0a0a;--bg-alt:#1a1a1a;--text:#e2e8f0;--text-secondary:#94a3b8;--text-muted:#666;--border:#2a2a2a;--shadow-sm:0 1px 2px rgba(0,0,0,.2);--shadow-md:0 4px 12px rgba(0,0,0,.3);--shadow-lg:0 8px 24px rgba(0,0,0,.4)}}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px;font-family:var(--font-body);-webkit-font-smoothing:antialiased;scroll-behavior:smooth;touch-action:manipulation}
body{color:var(--text);background:var(--bg);line-height:1.6}
::selection{background:rgba(201,138,44,.15)}
.container{max-width:1080px;margin:0 auto;padding:0 24px}
a{color:var(--primary);text-decoration:none;transition:color .15s}
a:hover{color:var(--primary-dark);text-decoration:underline}
nav{background:rgba(255,255,255,.88);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10}
@media(prefers-color-scheme:dark){nav{background:rgba(10,10,10,.92)}}
nav .inner{max-width:1080px;margin:0 auto;padding:0 24px;display:flex;align-items:center;height:56px;justify-content:space-between}
nav .logo{display:flex;align-items:center;gap:8px;font-weight:700;font-size:1.1rem;color:var(--text);text-decoration:none}
nav .logo img{height:28px;width:auto}
nav .logo:hover{text-decoration:none}
.nav-links{display:flex;align-items:center;gap:24px}
.dropdown{position:relative}
.dropdown-btn{background:none;border:none;cursor:pointer;font-size:.9rem;color:var(--text-secondary);padding:4px 0;border-bottom:2px solid transparent;font-family:inherit;display:flex;align-items:center;gap:4px;transition:color .15s}
.dropdown-btn:hover{color:var(--text);border-bottom-color:var(--primary)}
.dropdown-btn::after{content:'';display:inline-block;width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-top:4px solid var(--text-muted);margin-left:4px;transition:transform .2s}
.dropdown.open .dropdown-btn::after{transform:rotate(180deg)}
.dropdown-menu{display:none;position:absolute;top:100%;left:0;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);box-shadow:var(--shadow-lg);min-width:200px;padding:8px;z-index:20;max-height:400px;overflow-y:auto}
.dropdown:hover .dropdown-menu,.dropdown.open .dropdown-menu{display:block}
.dropdown-menu a{display:block;padding:8px 12px;font-size:.9rem;color:var(--text-secondary);border-radius:4px;text-decoration:none;transition:all .15s}
.dropdown-menu a:hover{background:var(--bg-alt);color:var(--primary);text-decoration:none}
.nav-link{font-size:.9rem;color:var(--text-secondary);text-decoration:none;padding:4px 0;border-bottom:2px solid transparent;white-space:nowrap;transition:all .15s}
.nav-link:hover{color:var(--text);border-bottom-color:var(--primary);text-decoration:none}
.nav-link.current{color:var(--text);border-bottom-color:var(--primary)}
h1,h2,h3,.hero h1,.cat-name,.post-title,.section-title,.lead-capture h2,.cta-banner h3,.story-section h2{font-family:var(--font-display)}
h1{font-size:clamp(1.8rem,4vw,2.5rem);font-weight:700;letter-spacing:-0.02em;line-height:1.15;color:var(--text)}
h2{font-size:clamp(1.3rem,2.5vw,1.6rem);font-weight:700;margin-bottom:20px;letter-spacing:-0.01em;color:var(--text)}
h3{font-size:clamp(1.1rem,2vw,1.25rem);font-weight:600;margin-bottom:8px;letter-spacing:-0.01em;color:var(--text)}
.hero{background:linear-gradient(180deg,var(--bg-alt),transparent 80%);padding:clamp(48px,8vw,80px) 0 56px;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 20% 50%,rgba(201,138,44,.08),transparent 60%),radial-gradient(ellipse at 80% 30%,rgba(124,58,237,.04),transparent 50%);pointer-events:none}
.hero h1{margin-bottom:12px}
.hero p{font-size:1.1rem;color:var(--text-secondary);max-width:600px;line-height:1.5}
.pick-card{display:flex;gap:clamp(16px,3vw,32px);padding:28px 32px;border:1px solid var(--border);border-radius:var(--radius-lg);margin-bottom:24px;align-items:flex-start;box-shadow:var(--shadow-sm);transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden;background:var(--bg)}
.pick-card:hover{box-shadow:var(--shadow-lg);transform:translateY(-2px);border-color:color-mix(in srgb,var(--primary) 20%,var(--border))}
.pick-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--primary);border-radius:0 4px 4px 0}
.pick-card.budget::before{background:var(--green)}
.pick-card.upgrade::before{background:var(--purple)}
.pick-card .rank{flex-shrink:0;width:44px;height:44px;background:var(--primary);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.1rem;box-shadow:0 2px 8px rgba(201,138,44,.35);position:relative;z-index:1}
.pick-card .rank.budget{background:var(--green);box-shadow:0 2px 8px rgba(5,150,105,.3)}
.pick-card .rank.upgrade{background:var(--purple);box-shadow:0 2px 8px rgba(124,58,237,.3)}
.pick-card .info{flex:1}
.pick-card .info h3{font-size:1.2rem;font-weight:600;margin-bottom:4px;font-family:var(--font-display)}
.pick-card .info .price{color:var(--green);font-weight:600;font-size:.95rem;margin-bottom:8px}
.pick-card .info p{font-size:.95rem;color:var(--text-secondary);margin-bottom:12px;line-height:1.5}
.pick-card .info .badge{display:inline-block;background:var(--primary-light);color:var(--primary);font-size:.75rem;font-weight:600;padding:2px 10px;border-radius:100px;margin-right:8px;text-transform:uppercase;letter-spacing:.04em}
.pick-card .info .badge.budget{background:var(--green-light);color:#065f46}
.pick-card .info .badge.upgrade{background:var(--purple-light);color:#5b21b6}
.grid-3{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:24px}
.cat-card{padding:24px;border:1px solid var(--border);border-radius:var(--radius-md);transition:all .25s cubic-bezier(.4,0,.2,1);box-shadow:var(--shadow-sm);text-decoration:none;display:block;background:var(--bg);position:relative;overflow:hidden}
.cat-card::after{content:'';position:absolute;bottom:0;left:20%;right:20%;height:3px;background:var(--primary);border-radius:3px 3px 0 0;transform:scaleX(0);transition:transform .25s cubic-bezier(.4,0,.2,1)}
.cat-card:hover{box-shadow:var(--shadow-lg);transform:translateY(-4px);text-decoration:none}
.cat-card:hover::after{transform:scaleX(1)}
.cat-card .cat-name{font-weight:700;font-size:1.1rem;color:var(--text);margin-bottom:4px}
.cat-card .cat-count{font-size:.85rem;color:var(--text-muted)}
.post-card{padding:20px;border:1px solid var(--border);border-radius:var(--radius-md);transition:all .2s;box-shadow:var(--shadow-sm);background:var(--bg)}
.post-card:hover{box-shadow:var(--shadow-md);border-color:color-mix(in srgb,var(--primary) 15%,var(--border))}
.post-card .post-title{font-weight:600;margin-bottom:4px;color:var(--text)}
.post-card .post-meta{font-size:.85rem;color:var(--text-muted)}
.section{padding:clamp(40px,6vw,64px) 0}
.section-title{font-size:1.1rem;font-weight:700;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.08em;margin-bottom:24px;padding-bottom:12px;border-bottom:3px solid var(--primary)}
.affiliate-banner{background:#fefce8;border:1px solid #fde68a;border-radius:var(--radius-sm);padding:16px 20px;font-size:.85rem;color:#92400e;margin:32px 0;text-align:center}
article{max-width:720px;margin:0 auto;padding:32px 0}
article h1{font-size:1.8rem;margin-bottom:8px}
article .meta{color:var(--text-secondary);font-size:.9rem;margin-bottom:32px;padding-bottom:16px;border-bottom:1px solid var(--border)}
article .content p{margin:16px 0;font-size:1.05rem;color:var(--text)}
article .content h2{margin:32px 0 12px;font-size:1.35rem}
article .content ul{padding-left:24px;margin:12px 0}
article .content li{margin:6px 0;color:var(--text)}
footer{padding:48px 0;border-top:1px solid var(--border);text-align:center}
footer p{font-size:.85rem;color:var(--text-muted);margin-bottom:4px}
.social{margin-top:16px;display:flex;gap:20px;justify-content:center}
.social a{color:var(--text-muted);text-decoration:none;display:flex;align-items:center;transition:color .15s}
.social a:hover{color:var(--text)}
.social svg{width:22px;height:22px;fill:currentColor}
.story-section{padding:clamp(40px,6vw,64px) 0;background:var(--bg-alt);border-top:1px solid var(--border)}
.story-section .container{max-width:680px;margin:0 auto;padding:0 24px}
.story-section h2{font-size:1.4rem;font-weight:700;margin-bottom:12px;text-align:center}
.story-section p{font-size:1rem;color:var(--text-secondary);line-height:1.7;margin-bottom:12px}
.story-section .trust-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin:24px 0;list-style:none}
.story-section .trust-item{padding:16px;background:var(--bg);border-radius:var(--radius-md);border:1px solid var(--border);box-shadow:var(--shadow-sm)}
.story-section .trust-item strong{display:block;font-size:.95rem;color:var(--text);margin-bottom:4px}
.story-section .trust-item span{font-size:.85rem;color:var(--text-muted)}
.product-card{display:flex;gap:24px;padding:24px;border:1px solid var(--border);border-radius:var(--radius-md);margin-bottom:20px;align-items:flex-start;box-shadow:var(--shadow-sm);transition:box-shadow .2s;background:var(--bg)}
.product-card:hover{box-shadow:var(--shadow-md)}
.product-card img{width:160px;height:160px;object-fit:cover;border-radius:var(--radius-sm);flex-shrink:0}
.product-card-body{flex:1}
.product-card-body h3{font-size:1.15rem;font-weight:600;margin-bottom:4px}
.product-card-body .price{color:var(--green);font-weight:600;font-size:.95rem;margin-bottom:8px}
.product-card-body p{font-size:.95rem;color:var(--text-secondary);margin-bottom:8px}
.product-card-body ul{padding-left:20px;margin:8px 0;font-size:.9rem;color:var(--text-secondary)}
.product-card-body li{margin:4px 0}
.buy-btn{display:inline-block;padding:10px 24px;background:var(--accent);color:#1f2937;border-radius:8px;font-weight:600;font-size:.95rem;margin-top:8px;text-decoration:none;box-shadow:0 1px 3px rgba(0,0,0,.12);transition:all .2s}
.buy-btn:hover{background:var(--accent-dark);text-decoration:none;box-shadow:0 2px 8px rgba(0,0,0,.2);transform:translateY(-1px);color:#1f2937}
.lead-capture{background:var(--text);color:#fff;padding:clamp(40px,6vw,64px) 24px;text-align:center}
.lead-capture h2{font-size:1.4rem;margin-bottom:8px;color:#fff}
.lead-capture p{font-size:1rem;margin-bottom:20px;opacity:.9;color:#fff}
.lead-capture form{display:flex;gap:12px;max-width:480px;margin:0 auto;flex-wrap:wrap;justify-content:center}
.lead-capture input{padding:12px 16px;border-radius:var(--radius-sm);border:none;font-size:1rem;flex:1;min-width:220px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.lead-capture button{padding:12px 28px;background:var(--primary);color:#fff;border:none;border-radius:var(--radius-sm);font-size:1rem;font-weight:600;cursor:pointer;transition:background .15s}
.lead-capture button:hover{background:var(--primary-dark)}
.cta-banner{background:linear-gradient(135deg,var(--primary),var(--purple));color:#fff;padding:clamp(32px,5vw,48px) 24px;border-radius:var(--radius-lg);text-align:center;margin:32px 0;position:relative;overflow:hidden}
.cta-banner::before{content:'';position:absolute;inset:0;background:radial-gradient(circle at 30% 50%,rgba(255,255,255,.08),transparent 50%);pointer-events:none}
.cta-banner h3{font-size:1.3rem;margin-bottom:8px;color:#fff}
.cta-banner p{font-size:.95rem;margin-bottom:16px;opacity:.9;color:#fff}
.cta-banner .buy-btn{background:#fff;color:var(--text);box-shadow:0 2px 8px rgba(0,0,0,.15)}
.cta-banner .buy-btn:hover{background:#f1f5f9;color:var(--text);box-shadow:0 4px 16px rgba(0,0,0,.2);transform:translateY(-2px)}
:focus-visible{outline:2px solid var(--primary);outline-offset:2px}
.hamburger{display:none;background:none;border:none;cursor:pointer;padding:8px;font-size:1.6rem;line-height:1;color:var(--text);font-family:inherit}
.skip-link{position:absolute;top:-100px;left:8px;background:var(--primary);color:#fff;padding:8px 16px;z-index:100;border-radius:0 0 4px;font-size:.9rem;text-decoration:none;transition:top .15s}
.skip-link:focus{top:0;color:#fff}
@media(max-width:768px){
.hamburger{display:block}
.nav-links{display:none;position:absolute;top:56px;left:0;right:0;background:var(--bg);border-bottom:1px solid var(--border);flex-direction:column;padding:16px 24px;gap:12px;box-shadow:var(--shadow-lg)}
.nav-links.open{display:flex}
.dropdown{width:100%}
.dropdown-menu{position:static;border:none;box-shadow:none;padding:0 0 0 16px;max-height:none}
.dropdown:hover .dropdown-menu{display:none}
.dropdown.open .dropdown-menu{display:block}
.dropdown-btn{width:100%;justify-content:space-between}
}
@media(max-width:640px){.pick-card{flex-direction:column;gap:16px}.grid-3{grid-template-columns:1fr}.product-card{flex-direction:column}.product-card img{width:100%;height:auto}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{transition-duration:.01ms!important;animation-duration:.01ms!important}}
.comments-section{max-width:720px;margin:48px auto;padding:0 24px}.comments-section h2{font-size:1.2rem;margin-bottom:4px}.comments-section .subtitle{font-size:.85rem;color:var(--text-muted);margin-bottom:24px}.comment-form{display:flex;flex-direction:column;gap:12px;margin-bottom:32px}.comment-form input,.comment-form textarea{padding:12px;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.95rem;font-family:var(--font-body);background:var(--bg);color:var(--text);transition:border-color .15s}.comment-form input:focus,.comment-form textarea:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px rgba(201,138,44,.15)}.comment-form textarea{resize:vertical;min-height:80px}.comment-form button{align-self:flex-start}.comment{border-bottom:1px solid var(--border);padding:16px 0}.comment:first-of-type{padding-top:0}.comment .author{font-weight:600;font-size:.9rem;color:var(--text)}.comment .time{font-weight:400;color:var(--text-muted);font-size:.8rem;margin-left:8px}.comment .body{margin-top:4px;font-size:.95rem;color:var(--text-secondary);line-height:1.5}.no-comments{color:var(--text-muted);font-size:.9rem;padding:16px 0}
"""

SVG_TIKTOK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg>'
SVG_INSTAGRAM = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>'
SVG_X = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'
SOCIAL_HTML = '<div class="social"><a href="https://www.tiktok.com/@abvorn" target="_blank" aria-label="TikTok">' + SVG_TIKTOK + '</a><a href="https://www.instagram.com/abvorn/" target="_blank" aria-label="Instagram">' + SVG_INSTAGRAM + '</a><a href="https://x.com/Abvorn" target="_blank" aria-label="X">' + SVG_X + '</a></div>'
NAV_SCRIPT = '<script>(function(){var h=document.querySelector(".hamburger");if(h){h.addEventListener("click",function(){var n=document.querySelector(".nav-links");n.classList.toggle("open");h.setAttribute("aria-expanded",n.classList.contains("open"))})}var d=document.querySelector(".dropdown-btn");if(d){d.addEventListener("click",function(e){e.preventDefault();this.closest(".dropdown").classList.toggle("open")})}})();</script>'

SHARE_HTML = """
<div class="share-buttons" style="display:flex;gap:8px;margin:32px 0;padding-top:24px;border-top:1px solid var(--border);align-items:center;flex-wrap:wrap">
<span style="font-size:.85rem;font-weight:600;color:var(--text-secondary);margin-right:8px">Share:</span>
<a href="https://twitter.com/intent/tweet?text=TITLE_PLACEHOLDER&url=URL_PLACEHOLDER&via=Abvorn" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share on X"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg> X</a>
<a href="https://www.facebook.com/sharer/sharer.php?u=URL_PLACEHOLDER" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share on Facebook"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg> Facebook</a>
<a href="https://pinterest.com/pin/create/button/?url=URL_PLACEHOLDER&description=TITLE_PLACEHOLDER" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share on Pinterest"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M12.017 0C5.396 0 .029 5.367.029 11.987c0 5.079 3.158 9.417 7.618 11.162-.105-.949-.199-2.403.041-3.439.219-.937 1.406-5.957 1.406-5.957s-.359-.72-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 01.083.345l-.333 1.36c-.053.22-.174.267-.402.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.631-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146 1.124.347 2.317.535 3.554.535 6.607 0 11.974-5.367 11.974-11.987C23.97 5.367 18.603.001 12.017.001z"/></svg> Pinterest</a>
<a href="mailto:?subject=TITLE_PLACEHOLDER&body=URL_PLACEHOLDER" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share via Email"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg> Email</a>
</div>"""

ANALYTICS_SCRIPT = """
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)};gtag('js',new Date());gtag('config','G-XXXXXXXXXX');</script>
"""

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
<p style="text-align:center;font-size:.9rem;color:var(--text-muted)"><em>Buy with confidence.</em></p>
</div>
</section>"""

SITE_BASE = "/abvorn"
FORCE_LOGO = f'<link rel="icon" type="image/png" href="{SITE_BASE}/assets/favicon-32x32.png">'

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
        return f'<nav><div class="inner"><a class="logo" href="{b}/">Abvorn</a><button class="hamburger" aria-label="Menu" aria-expanded="false" aria-controls="main-nav">☰</button><div class="nav-links" id="main-nav">{links}</div></div></nav>'

    def deploy_root_index(self, niches: list = None, posts: list = None) -> bool:
        try:
            niches = niches or []
            posts = posts or []
            if not niches or not posts:
                logger.warning("[SiteDeployer] Skipping root index deploy: need both niches and posts (otherwise would deploy placeholder)")
                return False
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
                recent += f'<div class="post-card"><div class="post-title"><a href="{SITE_BASE}/reviews/{slug}/">{title}</a></div><div class="post-meta">{slug.replace("-"," ").title()}</div></div>'

            jsonld = """<script type="application/ld+json">{
"@context":"https://schema.org","@type":"Organization","name":"Abvorn","url":"https://Abvorn-Media.github.io/abvorn/","description":"Independent product reviews and buying guides.","sameAs":["https://www.tiktok.com/@abvorn","https://www.instagram.com/abvorn/","https://x.com/Abvorn"]}</script>"""
            html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Abvorn — Product Reviews & Buying Guides</title>
<meta name="description" content="Independent, expert reviews across every category. We test so you can buy with confidence.">
{FORCE_LOGO}
{jsonld}
{ANALYTICS_SCRIPT}
<style>{CSS_SHARED}</style>
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
{self._nav_html("home", [n if isinstance(n,str) else n.get("slug","") for n in niches]) if niches else f'<nav><div class="inner"><a class="logo" href="{SITE_BASE}/">Abvorn</a></div></nav>'}

<section class="hero" id="main">
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
{NAV_SCRIPT}</body></html>"""
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
            if not posts:
                logger.warning(f"[SiteDeployer] Skipping category deploy for {niche}: no posts available (would deploy placeholder)")
                return False
            b = SITE_BASE
            post_rows = ""
            for i, p in enumerate(posts[:5]):
                title = p.get("title") or p.get("post_title", "")
                slug = p.get("slug") or niche
                product_name = p.get("product_name", "")
                query = product_name.replace(" ", "+").replace("'","") if product_name else niche.replace("-","+")
                rank_label = ["Our pick", "Budget pick", "Upgrade pick", f"Also great", f"Also great"][i] if i < 5 else ""
                rank_class = ["", "budget", "upgrade", "", ""][i] if i < 5 else ""
                post_rows += f"""<div class="pick-card">
<div class="rank {rank_class}">{i+1}</div>
<div class="info">
<div class="badge {rank_class}">{rank_label}</div>
<h3>{title}</h3>
<p>In-depth testing and honest comparison. See why this made our list.</p>
<a class="buy-btn" href="https://www.amazon.com/s?k={query}&tag={_amazon_tag()}" target="_blank" rel="sponsored">Check Price</a>
<a href="{b}/{slug}/" style="margin-left:12px">Read full review →</a>
</div></div>"""

            nav_links = "".join(f'<a class="nav-link" href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in all_categories[:4])
            more_items = "".join(f'<a href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in all_categories[4:])
            dropdown = f'<div class="dropdown"><button class="dropdown-btn">More</button><div class="dropdown-menu">{more_items}</div></div>' if all_categories[4:] else ""
            html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Best {niche.replace("-"," ").title()} — Abvorn</title>
<meta name="description" content="The best {niche.replace('-',' ')} reviewed and compared. Our expert picks after hours of testing.">
{FORCE_LOGO}
{ANALYTICS_SCRIPT}
<style>{CSS_SHARED}</style>
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
<nav><div class="inner"><a class="logo" href="{b}/">Abvorn</a><button class="hamburger" aria-label="Menu" aria-expanded="false" aria-controls="main-nav">☰</button><div class="nav-links" id="main-nav">{nav_links}{dropdown}</div></div></nav>

<section class="hero" id="main">
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
{NAV_SCRIPT}</body></html>"""
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

            article_url = f"https://Abvorn-Media.github.io/abvorn/reviews/{niche}/"
            share = SHARE_HTML.replace("TITLE_PLACEHOLDER", post_title).replace("URL_PLACEHOLDER", article_url)

            b = SITE_BASE
            nav_links = "".join(f'<a class="nav-link" href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in all_categories[:4])
            more_items = "".join(f'<a href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in all_categories[4:])
            dropdown = f'<div class="dropdown"><button class="dropdown-btn">More</button><div class="dropdown-menu">{more_items}</div></div>' if all_categories[4:] else ""

            product_cards = ""
            if product_name:
                query = product_name.replace(" ", "+").replace("'","")
                product_cards = f'<div class="product-card"><div class="product-card-body"><h3>{product_name}</h3><a class="buy-btn" href="https://www.amazon.com/s?k={query}&tag={_amazon_tag()}" target="_blank" rel="sponsored">Check Price on Amazon</a></div></div>'

            html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{post_title} — Abvorn</title>
<meta name="description" content="{meta_desc}">
<link rel="canonical" href="{article_url}">
{FORCE_LOGO}
{ANALYTICS_SCRIPT}
<style>{CSS_SHARED}</style>
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
<nav><div class="inner"><a class="logo" href="{b}/"><img src="{b}/assets/logo.png" alt="Abvorn">Abvorn</a><button class="hamburger" aria-label="Menu" aria-expanded="false" aria-controls="main-nav">☰</button><div class="nav-links" id="main-nav">{nav_links}{dropdown}</div></div></nav>

<article id="main">
<h1>{post_title}</h1>
<div class="meta">{product_name} · Updated 2026</div>
{intro}
<div class="content">{article_html}</div>

{share}

<div class="affiliate-banner">We earn a commission if you buy through our links, at no extra cost to you. Our opinions are our own.</div>
</article>

<section class="comments-section">
<h2>Share Your Thoughts</h2>
<p class="subtitle">Join the conversation — your email stays private, only your name appears.</p>
<div class="comment-form">
<input type="text" id="comment-name" placeholder="Your name" maxlength="50" aria-label="Your name">
<textarea id="comment-text" placeholder="What do you think? Share your experience..." rows="3" aria-label="Your comment"></textarea>
<button class="buy-btn" onclick="postComment()">Post Comment</button>
</div>
<div id="comments-list"></div>
</section>

<script>
(function(){{var k='abvorn_comments_'+location.pathname.replace(/\\//g,'_');var c=JSON.parse(localStorage.getItem(k)||'[]');var l=document.getElementById('comments-list');function r(){{if(!l)return;if(!c.length){{l.innerHTML='<div class="no-comments">No comments yet. Start the conversation!</div>';return}}l.innerHTML=c.map(function(e){{return'<div class="comment"><div class="author">'+e.name+' <span class="time">'+new Date(e.date).toLocaleDateString()+'</span></div><div class="body">'+e.text+'</div></div>'}}).join('')}}
window.postComment=function(){{var n=document.getElementById('comment-name');var t=document.getElementById('comment-text');if(!n||!t||!n.value.trim()||!t.value.trim())return;c.unshift({{name:n.value.trim(),text:t.value.trim(),date:new Date().toISOString()}});localStorage.setItem(k,JSON.stringify(c));n.value='';t.value='';r()}};r()}})();
</script>

{product_cards}

<div class="container">
<div class="cta-banner">
<h3>Ready to buy?</h3>
<p>We've done the research. Now get the best price on Amazon.</p>
<a class="buy-btn" href="https://www.amazon.com/s?k={niche.replace('-','+')}&tag={_amazon_tag()}" target="_blank" rel="sponsored">Shop all picks on Amazon</a>
</div></div>

<section class="lead-capture">
<div class="container">
<h2>Get our free buying guides</h2>
<p>Get expert buying advice and exclusive deals delivered to your inbox.</p>
<form action="#" method="POST" target="_blank">
<input type="email" name="email" placeholder="your@email.com" required>
<input type="hidden" name="source" value="abvorn-hq">
<button type="submit">Subscribe</button>
</form>
<p style="font-size:.8rem;margin-top:12px;opacity:.7">No spam. Unsubscribe anytime.</p>
</div>
</section>

<footer><p>Abvorn · Independent reviews since 2026</p>{SOCIAL_HTML}</footer>
{NAV_SCRIPT}</body></html>"""
            self.deployer.deploy_html(html, f"reviews/{niche}/index.html")
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
        events = self.bus.get_recent_events("content.drafted")
        return {"events": events}

    async def decide(self, perception):
        if perception.get("events"):
            last = max(perception["events"], key=lambda e: e["created_at"])
            niche = last['message']['niche']
            if not self.soul_check("deploy_content", {"niche": niche}):
                logger.info(f"[DeployAgent] Soul blocked deploy for {niche}")
                return "wait"
            return f"deploy:{niche}"
        return "wait"

    async def act(self, decision):
        if decision.startswith("deploy:"):
            niche = decision.split(":", 1)[1]
            logger.info(f"[DeployAgent] Deploying content for: {niche}")
            events = self.bus.get_recent_events("content.drafted")
            content_payload = {}
            for e in events:
                if e['message'].get('niche') == niche and 'result' in e['message']:
                    content_payload = e['message']['result']
                    break
            if self.site_deployer and self.state:
                all_niches_data = self.state.get_all_niches()
                all_slugs = [n["slug"] for n in all_niches_data]
                all_posts = []
                for s in all_slugs:
                    all_posts.extend(self.state.get_posts_for_niche(s))
                if content_payload:
                    deploy_content = {
                        "post_title": content_payload.get("post_title", ""),
                        "article_html": content_payload.get("article_html", ""),
                        "meta_description": content_payload.get("meta_description", ""),
                        "product_name": content_payload.get("product_name", ""),
                    }
                    self.site_deployer.deploy_content(niche, deploy_content, all_categories=all_slugs)
                else:
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
                for slug in all_slugs:
                    niche_posts = [p for p in all_posts if p.get("niche_slug") == slug]
                    self.site_deployer.deploy_category_page(slug, posts=niche_posts, all_categories=all_slugs)
            self.bus.publish("content.published", {"niche": niche, "status": "deployed"})
            return {"niche": niche, "status": "deployed"}

    async def reflect(self, outcome):
        if self.drive:
            succeeded = bool(outcome and outcome.get("status") == "deployed")
            self.drive.log_outcome("deploy", succeeded=succeeded)
