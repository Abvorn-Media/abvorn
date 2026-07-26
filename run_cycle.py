"""run_cycle.py — standalone content cycle for GitHub Actions or local use.

Reads secrets from env vars (GITHUB_ prefixed) or falls back to secrets.json.
Picks the niche with fewest posts, generates content, writes to docs/, updates state.
"""
import os, sys, json, logging, re, html as html_mod
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

# ─── Secrets ────────────────────────────────────────────────────────────
def get_secrets():
    """Get API secrets from env vars (GitHub Actions) or fallback to secrets.json."""
    keys = {
        "OPENAI_KEY": os.environ.get("OPENAI_KEY", ""),
        "DEEPSEEK_KEY": os.environ.get("DEEPSEEK_KEY", ""),
        "GEMINI_KEY": os.environ.get("GEMINI_KEY", ""),
        "GROQ_KEY": os.environ.get("GROQ_KEY", ""),
        "GLM_KEYS": os.environ.get("GLM_KEYS", ""),
        "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
        "GITHUB_REPO": os.environ.get("GITHUB_REPO", "Abvorn-Media/abvorn"),
    }
    # If any key is missing, try local secrets.json
    if not any(v for v in keys.values()):
        try:
            from abvorn.core.secrets import load_secrets
            return load_secrets()
        except Exception:
            pass
    return keys


# ─── State management ───────────────────────────────────────────────────
STATE_FILE = Path("cycle_state.json")

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    # Default state with all niches
    return {
        "niches": [
            {"slug": "wireless-headphones", "name": "Wireless Headphones", "posts": 0},
            {"slug": "gaming-mice", "name": "Gaming Mice", "posts": 0},
            {"slug": "4k-monitors", "name": "4K Monitors", "posts": 0},
            {"slug": "laptops", "name": "Laptops", "posts": 0},
            {"slug": "streaming-devices", "name": "Streaming Devices", "posts": 0},
            {"slug": "mechanical-keyboards", "name": "Mechanical Keyboards", "posts": 0},
            {"slug": "wireless-earbuds", "name": "Wireless Earbuds", "posts": 0},
            {"slug": "fitness-trackers", "name": "Fitness Trackers", "posts": 0},
            {"slug": "webcams", "name": "Webcams", "posts": 0},
            {"slug": "smart-home", "name": "Smart Home", "posts": 0},
        ],
        "last_processed": None,
        "updated_at": datetime.now().isoformat(),
    }

def save_state(state):
    state["updated_at"] = datetime.now().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def pick_niche(state):
    """Pick the niche with the fewest posts. Tie-break: round-robin from last."""
    niches = state["niches"]
    last = state.get("last_processed")
    # Find min posts
    min_posts = min(n["posts"] for n in niches)
    candidates = [n for n in niches if n["posts"] == min_posts]
    # Prefer a niche after the last processed one (round-robin)
    if last and len(candidates) > 1:
        slugs = [n["slug"] for n in niches]
        last_idx = slugs.index(last) if last in slugs else -1
        after_last = [n for n in candidates if slugs.index(n["slug"]) > last_idx]
        if after_last:
            return after_last[0]
    return candidates[0]


# ─── HTML template helpers ──────────────────────────────────────────────
SITE_BASE = "/abvorn"

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


def nav_html(categories, current=""):
    b = SITE_BASE
    featured = categories[:4]
    rest = categories[4:]
    featured_links = "".join(f'<a class="nav-link" href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in featured)
    more_items = "".join(f'<a href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in rest)
    dd = f'<div class="dropdown"><button class="dropdown-btn">More</button><div class="dropdown-menu">{more_items}</div></div>' if rest else ""
    return f'<nav><div class="inner"><a class="logo" href="{b}/"><img src="{b}/assets/logo.png" alt="Abvorn">Abvorn</a><div class="nav-links">{featured_links}{dd}</div></div></nav>'


def build_root_index(state, posts):
    niches = state["niches"]
    all_slugs = [n["slug"] for n in niches]
    b = SITE_BASE
    cats = "".join(f'<a class="cat-card" href="{b}/{n["slug"]}/"><div class="cat-name">{n["name"]}</div>{"<div class=cat-count>"+str(n["posts"])+" reviews</div>" if n["posts"] else ""}</a>' for n in niches)
    recent = ""
    for p in posts[:6]:
        title = p.get("title", "")
        slug = p.get("slug", "")
        # Map niche slug to reviews path for article pages
        link_slug = f"reviews/{slug}" if "/" not in slug else slug
        recent += f'<div class="post-card"><div class="post-title"><a href="{b}/{link_slug}/">{title}</a></div><div class="post-meta">{slug.replace("-"," ").title()}</div></div>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Abvorn — Product Reviews &amp; Buying Guides</title>
<meta name="description" content="Independent, expert reviews across every category. We test so you can buy with confidence.">
<link rel="icon" type="image/png" href="{b}/assets/favicon.png">
<style>{CSS_SHARED}</style>
</head><body>
{nav_html(all_slugs)}
<section class="hero"><div class="container">
<h1>The best products, reviewed.</h1>
<p>We test hundreds of products across dozens of categories so you don't have to. Independent, honest, data-driven.</p>
</div></section>
{STORY_HTML}
<section class="section"><div class="container">
<div class="section-title">All Categories</div>
<div class="grid-3">{cats}</div>
</div></section>
<section class="section"><div class="container">
<div class="section-title">Latest Reviews</div>
<div class="grid-3">{recent or '<div style="color:#9ca3af">Reviews coming soon</div>'}</div>
</div></section>
<div class="container"><div class="affiliate-banner">When you buy through our links, we may earn a commission. Our opinions are our own.</div></div>
<footer><p>Abvorn · Independent reviews · Honest recommendations</p>{SOCIAL_HTML}</footer>
</body></html>"""


def build_category_page(niche_slug, niche_name, posts, all_slugs):
    b = SITE_BASE
    post_rows = ""
    for i, p in enumerate(posts[:5]):
        title = p.get("title", "")
        review_slug = p.get("slug", f"reviews/{niche_slug}")
        rank_labels = ["Our pick", "Budget pick", "Upgrade pick", "Also great", "Also great"]
        rank_classes = ["", "budget", "upgrade", "", ""]
        ri = i if i < 5 else 4
        post_rows += f"""<div class="pick-card">
<div class="rank {rank_classes[ri]}">{i+1}</div>
<div class="info">
<div class="badge {rank_classes[ri]}">{rank_labels[ri]}</div>
<h3>{title}</h3>
<p>In-depth testing and honest comparison. See why this made our list.</p>
<a href="{b}/{review_slug}/">Read full review →</a>
</div></div>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Best {niche_name} — Abvorn</title>
<meta name="description" content="The best {niche_name.lower()} reviewed and compared. Our expert picks after hours of testing.">
<link rel="icon" type="image/png" href="{b}/assets/favicon.png">
<style>{CSS_SHARED}</style>
</head><body>
{nav_html(all_slugs)}
<section class="hero"><div class="container">
<h1>The Best {niche_name}</h1>
<p>We tested the top contenders to find the ones worth your money.</p>
</div></section>
<section class="section"><div class="container">
<div class="section-title">Our Top Picks</div>
{post_rows or '<div style="color:#9ca3af;padding:32px;text-align:center">Reviews for this category are being researched. Check back soon.</div>'}
</div></section>
<div class="container"><div class="affiliate-banner">We earn from qualifying purchases.</div></div>
<footer><p>Abvorn · Independent reviews</p>{SOCIAL_HTML}</footer>
</body></html>"""


def build_article_page(niche_slug, niche_name, post_title, article_html, intro, product_name, meta_desc, all_slugs):
    b = SITE_BASE
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html_mod.escape(post_title)} — Abvorn</title>
<meta name="description" content="{html_mod.escape(meta_desc)[:160]}">
<link rel="icon" type="image/png" href="{b}/assets/favicon.png">
<style>{CSS_SHARED}</style>
</head><body>
{nav_html(all_slugs)}
<article>
<h1>{html_mod.escape(post_title)}</h1>
<div class="meta">{html_mod.escape(product_name)} · Updated 2026</div>
{intro}
<div class="content">{article_html}</div>
<div class="affiliate-banner">We earn a commission if you buy through our links, at no extra cost to you. Our opinions are our own.</div>
</article>
<footer><p>Abvorn · Independent reviews since 2026</p>{SOCIAL_HTML}</footer>
</body></html>"""


# ─── AI Research (skip DDGS, use AI knowledge directly) ──────────────────
def research_products(niche, router):
    prompt = f"""You are a product expert. For the niche '{niche}', recommend exactly 3 specific real products with brand and model names. Use your knowledge of real products available on Amazon.

Return a JSON array. Each product must have:
- name: specific brand + model (e.g. "Sony WH-1000XM5")
- price: realistic price string
- description: 1-2 sentence highlight
- features: array of 3-4 key features
- category: "best_overall", "best_value", or "premium_pick"
- affiliate_query: search query for this product (e.g. "Sony+WH-1000XM5")"""
    result = router.ask(prompt, json_mode=True)
    if not result:
        return None
    try:
        products = json.loads(result)
    except json.JSONDecodeError:
        m = re.search(r'\[.*\]', result, re.DOTALL)
        if m:
            try:
                products = json.loads(m.group(0))
            except:
                products = None
        else:
            products = None
    return products if isinstance(products, list) else ([products] if isinstance(products, dict) else None)


# ─── Content generation ─────────────────────────────────────────────────
def generate_outline(niche, products, router):
    names = json.dumps([p.get("name", "") for p in products[:3]])
    prompt = f"""You are a content strategist planning a buying guide for '{niche}'.
Products: {names}

Return a JSON object with:
- outline: array of H2 section headings (e.g. ["Introduction", "What to Look For", "Product Reviews", "Buying Guide", "FAQ", "Conclusion"])
- selected_angle: one of: problem_solution, comparison, how_to, listicle, deep_dive, objection_buster
- primary_keyword: the main SEO keyword for this guide
- post_title: compelling title for the buying guide
- meta_description: 1-2 sentence SEO description"""
    result = router.ask(prompt, json_mode=True)
    if not result:
        return None
    try:
        return json.loads(result)
    except:
        m = re.search(r'\{.*\}', result, re.DOTALL)
        if m:
            try: return json.loads(m.group(0))
            except: pass
    return None


def write_draft(niche, products, outline, router):
    products_text = json.dumps(products, indent=2)
    post_title = outline.get("post_title", f"Best {niche} — Expert Review")
    meta_desc = outline.get("meta_description", f"Find the best {niche} with our expert guide.")
    angle = outline.get("selected_angle", "problem_solution")
    keyword = outline.get("primary_keyword", f"best {niche}")
    outline_sections = json.dumps(outline.get("outline", []))
    intro_prompt = f"""Write the introduction for a buying guide titled '{post_title}' about {niche}.
Angle: {angle}
Keyword: {keyword}
Products: {products_text}

Write 2-3 short paragraphs (as HTML) that hook the reader, state the problem, and introduce the solution.
Return ONLY the HTML paragraphs, wrapped in <p> tags."""
    intro_html = router.ask(intro_prompt, system="You write concise, honest product review copy.")
    if not intro_html:
        intro_html = "<p>We tested the top products to find the ones worth your money.</p>"

    article_prompt = f"""Write the full article body for '{post_title}' about {niche}.
Products: {products_text}
Outline sections: {outline_sections}
Angle: {angle}
Keyword: {keyword}

Write the COMPLETE article body as HTML. Follow the outline sections as <h2> headings.
For each product, include: a brief intro, key features, pros/cons, and a bottom-line recommendation.
Use <p> for paragraphs, <ul>/<li> for lists, <strong> for emphasis.
Be honest, specific (use real prices/numbers), and scannable.
Return ONLY the HTML."""
    article_html = router.ask(article_prompt, system="You write thorough, honest product reviews with specific details and real prices.")
    if not article_html:
        article_html = "<p>We're reviewing the top products in this category.</p>"

    return {
        "post_title": post_title,
        "meta_description": meta_desc,
        "intro": intro_html,
        "article_html": article_html,
        "product_name": products[0].get("name", ""),
    }


# ─── Document writer ────────────────────────────────────────────────────
def write_files(niche_slug, articles, state):
    """Write all HTML files to docs/ directory."""
    all_slugs = [n["slug"] for n in state["niches"]]
    niche_name = next((n["name"] for n in state["niches"] if n["slug"] == niche_slug), niche_slug.replace("-", " ").title())

    # Collect all posts across niches
    all_posts = []
    for n in state["niches"]:
        for p in articles.get(n["slug"], []):
            all_posts.append({"title": p.get("post_title", ""), "slug": n["slug"]})

    docs = Path("docs")
    docs.mkdir(exist_ok=True)

    # Write root index
    (docs / "index.html").write_text(build_root_index(state, all_posts), encoding="utf-8")
    print(f"  Written: docs/index.html")

    # Write category pages (post slugs point to reviews/{slug} for article pages)
    for n in state["niches"]:
        niche_posts = [{"title": a.get("post_title", ""), "slug": f"reviews/{n['slug']}"} for a in articles.get(n["slug"], [])]
        cat_dir = docs / n["slug"]
        cat_dir.mkdir(exist_ok=True)
        (cat_dir / "index.html").write_text(build_category_page(n["slug"], n["name"], niche_posts, all_slugs), encoding="utf-8")

    # Write article pages (under docs/reviews/{slug}/ to avoid overwriting category page)
    for slug, post_list in articles.items():
        for i, a in enumerate(post_list):
            post_dir = docs / "reviews" / slug
            post_dir.mkdir(parents=True, exist_ok=True)
            (post_dir / "index.html").write_text(
                build_article_page(slug, niche_name, a["post_title"], a["article_html"],
                                   a["intro"], a["product_name"], a["meta_description"], all_slugs),
                encoding="utf-8"
            )
            print(f"  Written: docs/reviews/{slug}/index.html (article)")
            # Update the post slug in all_posts for root index links
            for p in all_posts:
                if p.get("title") == a.get("post_title") and p.get("slug") == slug:
                    p["slug"] = f"reviews/{slug}"


# ─── Main ────────────────────────────────────────────────────────────────
def main(forced_niche=None, force=False):
    secrets = get_secrets()

    # Build ModelRouter from env
    from abvorn.core.models import ModelRouter
    router = ModelRouter(secrets)

    # Load state
    state = load_state()
    print(f"State loaded: {len(state['niches'])} niches")

    # Pick niche
    if forced_niche:
        niche = next((n for n in state["niches"] if n["slug"] == forced_niche), None)
        if not niche:
            print(f"ERROR: Unknown niche '{forced_niche}'")
            sys.exit(1)
        if not force and niche["posts"] >= 3:
            print(f"SKIP: {forced_niche} already has {niche['posts']} posts (use force=true to override)")
            sys.exit(0)
    else:
        niche = pick_niche(state)
    niche_slug = niche["slug"]
    niche_name = niche["name"]
    print(f"Picked: {niche_slug} ({niche['posts']} existing posts)")

    # 1. RESEARCH
    print(f"\n--- RESEARCH: {niche_slug} ---")
    products = research_products(niche_slug, router)
    if not products:
        print("ERROR: No products found")
        sys.exit(1)
    print(f"Found {len(products)} products: {[p.get('name','?') for p in products]}")

    # 2. OUTLINE
    print(f"\n--- OUTLINE: {niche_slug} ---")
    outline = generate_outline(niche_slug, products, router)
    if not outline:
        print("WARNING: Outline failed, using default")
        outline = {"post_title": f"Best {niche_name}", "meta_description": f"Find the best {niche_name}.",
                   "selected_angle": "problem_solution", "primary_keyword": f"best {niche_slug}",
                   "outline": ["Introduction", "Product Reviews", "Buying Guide", "FAQ", "Conclusion"]}
    print(f"Title: {outline.get('post_title','?')}")

    # 3. DRAFT
    print(f"\n--- DRAFT: {niche_slug} ---")
    draft = write_draft(niche_slug, products, outline, router)
    if not draft:
        print("ERROR: Draft failed")
        sys.exit(1)
    print(f"Article HTML: {len(draft.get('article_html',''))} chars")

    # 4. WRITE FILES
    print(f"\n--- WRITE: {niche_slug} ---")
    articles = {niche_slug: [draft]}
    write_files(niche_slug, articles, state)

    # 5. UPDATE STATE
    niche["posts"] += 1
    state["last_processed"] = niche_slug
    save_state(state)
    print(f"\nState updated: {niche_slug} now has {niche['posts']} posts")

    # Summary
    total = sum(n["posts"] for n in state["niches"])
    print(f"\n{'='*50}")
    print(f"✅ Cycle complete: {niche_slug}")
    print(f"   Total posts on site: {total}")
    print(f"   Next up: next niche in round-robin")
    print(f"{'='*50}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Abvorn content cycle")
    parser.add_argument("--niche", type=str, help="Niche slug to process (auto-pick if omitted)")
    parser.add_argument("--force", action="store_true", help="Force regenerate even if has posts")
    args = parser.parse_args()
    main(forced_niche=args.niche, force=args.force)
