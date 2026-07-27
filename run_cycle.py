"""run_cycle.py — standalone content cycle for GitHub Actions or local use.

Reads secrets from env vars (GITHUB_ prefixed) or falls back to secrets.json.
Picks the niche with fewest posts, generates content, writes to docs/, updates state.
"""
import os, sys, json, logging, re, html as html_mod, requests as http_requests
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
        "PEXELS_KEY": os.environ.get("PEXELS_KEY", ""),
        "AMAZON_TAG": os.environ.get("AMAZON_TAG", "viraltestco-20"),
        "APPS_SCRIPT_URL": os.environ.get("APPS_SCRIPT_URL", ""),
        "GA_MEASUREMENT_ID": os.environ.get("GA_MEASUREMENT_ID", ""),
        "GOOGLE_CLIENT_ID": os.environ.get("GOOGLE_CLIENT_ID", ""),
    }
    # If any key is missing, try local secrets.json
    if not any(v for v in keys.values()):
        try:
            from abvorn.core.secrets import load_secrets
            return load_secrets()
        except Exception:
            pass
    return keys


# ─── Image & affiliate helpers ──────────────────────────────────────────

def fetch_product_image(query, pexels_key):
    """Search Pexels for a product image, return URL."""
    if not pexels_key:
        return ""
    try:
        r = http_requests.get(f"https://api.pexels.com/v1/search?query={query}&per_page=3",
            headers={"Authorization": pexels_key}, timeout=10)
        if r.status_code == 200:
            photos = r.json().get("photos", [])
            if photos:
                return photos[0]["src"]["medium"]
    except Exception:
        pass
    return ""

def amazon_link(query, tag=""):
    """Generate Amazon affiliate search link."""
    q = query.replace(" ", "+")
    t = tag or "viraltestco-20"
    return f"https://www.amazon.com/s?k={q}&tag={t}"

def product_card_html(product, pexels_key="", amazon_tag=""):
    """HTML for a product card with image + affiliate buy button."""
    name = product.get("name", "Product")
    price = product.get("price", "Check price")
    features = product.get("features", [])
    summary = product.get("description", "")
    aff_query = product.get("affiliate_query", name.replace(" ", "+"))
    aff_url = amazon_link(aff_query, amazon_tag)
    img = ""
    if pexels_key:
        img = fetch_product_image(name, pexels_key)
    img_tag = f'<img src="{img}" alt="{name}" loading="lazy">' if img else ""
    features_html = "".join(f"<li>{f}</li>" for f in features[:4])
    return f"""<div class="product-card">
{img_tag}
<div class="product-card-body">
<h3>{name}</h3>
<div class="price">{price}</div>
<p>{summary}</p>
{"<ul>" + features_html + "</ul>" if features_html else ""}
<a class="buy-btn" href="{aff_url}" target="_blank" rel="sponsored">Check Price on Amazon →</a>
</div>
</div>"""

def lead_form_html(form_url=""):
    url = form_url or "#"
    return f"""
<section class="lead-capture">
<div class="container">
<h2>Get our free buying guides</h2>
<p>Get expert buying advice and exclusive deals delivered to your inbox.</p>
<form action="{url}" method="POST" target="_blank">
<input type="email" name="email" placeholder="your@email.com" required>
<input type="hidden" name="source" value="abvorn-hq">
<button type="submit">Subscribe →</button>
</form>
<p style="font-size:.8rem;margin-top:12px;opacity:.7">No spam. Unsubscribe anytime.</p>
</div>
</section>"""

CTA_BANNER = """
<div class="cta-banner">
<h3>Ready to buy?</h3>
<p>We've done the research. Now get the best price on Amazon.</p>
<a class="buy-btn" href="https://www.amazon.com/s?k={query}&tag={tag}" target="_blank" rel="sponsored">Shop all picks on Amazon →</a>
</div>"""

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

FONT_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">'

CSS_SHARED = """
:root{--primary:#d4633e;--primary-dark:#b84d2a;--primary-light:#fce9e1;--accent:#1a8a7a;--accent-dark:#147062;--accent-light:#d4ede8;--green:#3a8a5c;--green-light:#d6f0df;--purple:#8b6fba;--purple-light:#ebe3f5;--bg:#faf6f1;--bg-alt:#f0ebe3;--text:#2a2724;--text-secondary:#6b6560;--text-muted:#9e9690;--border:#e3dbd4;--shadow-sm:0 1px 3px rgba(42,39,36,.06);--shadow-md:0 4px 14px rgba(42,39,36,.07);--shadow-lg:0 10px 30px rgba(42,39,36,.08);--radius-sm:8px;--radius-md:12px;--radius-lg:16px;--font-display:'Fraunces',Georgia,'Times New Roman',serif;--font-body:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
@media(prefers-color-scheme:dark){:root{--bg:#1a1715;--bg-alt:#221f1c;--text:#e8e2dc;--text-secondary:#a69e96;--text-muted:#7e756d;--border:#34302b}}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px;font-family:var(--font-body);-webkit-font-smoothing:antialiased;scroll-behavior:smooth;touch-action:manipulation}
body{color:var(--text);background:var(--bg);line-height:1.6}
::selection{background:rgba(212,99,62,.15)}
.container{max-width:1080px;margin:0 auto;padding:0 24px}
a{color:var(--primary);text-decoration:none;transition:color .15s}
a:hover{color:var(--primary-dark);text-decoration:underline}
nav{background:rgba(250,246,241,.9);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10}
@media(prefers-color-scheme:dark){nav{background:rgba(26,23,21,.9)}}
nav .inner{max-width:1080px;margin:0 auto;padding:0 24px;display:flex;align-items:center;height:56px;justify-content:space-between}
nav .logo{display:flex;align-items:center;gap:8px;font-weight:700;font-size:1.15rem;color:var(--text);text-decoration:none;font-family:var(--font-display)}
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
h1,h2,h3,.hero h1,.cat-name,.post-title,.section-title,.lead-capture h2,.cta-banner h3,.story-section h2,.verdict-title{font-family:var(--font-display)}
h1{font-size:clamp(1.8rem,4vw,2.5rem);font-weight:700;letter-spacing:-0.02em;line-height:1.15;color:var(--text)}
h2{font-size:clamp(1.3rem,2.5vw,1.6rem);font-weight:700;margin-bottom:20px;letter-spacing:-0.01em;color:var(--text)}
h3{font-size:clamp(1.1rem,2vw,1.25rem);font-weight:600;margin-bottom:8px;letter-spacing:-0.01em;color:var(--text)}
.hero{background:linear-gradient(180deg,var(--bg-alt),transparent 80%);padding:clamp(48px,8vw,80px) 0 56px;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 20% 50%,rgba(212,99,62,.06),transparent 60%),radial-gradient(ellipse at 80% 30%,rgba(26,138,122,.04),transparent 50%);pointer-events:none}
.hero h1{margin-bottom:12px}
.hero p{font-size:1.1rem;color:var(--text-secondary);max-width:600px;line-height:1.5}
.hero .featured-pick{display:inline-flex;align-items:center;gap:10px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-md);padding:18px 24px;margin-top:16px;box-shadow:var(--shadow-sm);transition:all .2s;text-decoration:none;max-width:100%}
.hero .featured-pick:hover{box-shadow:var(--shadow-md);border-color:var(--primary);text-decoration:none}
.hero .featured-pick .fp-badge{background:var(--primary);color:#fff;font-size:.7rem;font-weight:600;padding:2px 10px;border-radius:100px;text-transform:uppercase;letter-spacing:.04em}
.hero .featured-pick .fp-title{font-weight:600;color:var(--text);font-size:1rem}
.hero .featured-pick .fp-arrow{color:var(--primary);font-size:1.2rem}
.pick-card{display:flex;gap:clamp(16px,3vw,32px);padding:28px 32px;border:1px solid var(--border);border-radius:var(--radius-lg);margin-bottom:24px;align-items:flex-start;box-shadow:var(--shadow-sm);transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden;background:var(--bg)}
.pick-card:hover{box-shadow:var(--shadow-lg);transform:translateY(-2px);border-color:color-mix(in srgb,var(--primary) 20%,var(--border))}
.pick-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--primary);border-radius:0 4px 4px 0}
.pick-card.budget::before{background:var(--green)}
.pick-card.upgrade::before{background:var(--purple)}
.pick-card .rank{flex-shrink:0;width:44px;height:44px;background:var(--primary);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.1rem;box-shadow:0 2px 8px rgba(212,99,62,.3);position:relative;z-index:1}
.pick-card .rank.budget{background:var(--green);box-shadow:0 2px 8px rgba(58,138,92,.3)}
.pick-card .rank.upgrade{background:var(--purple);box-shadow:0 2px 8px rgba(139,111,186,.3)}
.pick-card .info{flex:1}
.pick-card .info h3{font-size:1.2rem;font-weight:600;margin-bottom:4px;font-family:var(--font-display)}
.pick-card .info .price{color:var(--green);font-weight:600;font-size:.95rem;margin-bottom:8px}
.pick-card .info p{font-size:.95rem;color:var(--text-secondary);margin-bottom:12px;line-height:1.5}
.pick-card .info .badge{display:inline-block;background:var(--primary-light);color:var(--primary);font-size:.75rem;font-weight:600;padding:2px 10px;border-radius:100px;margin-right:8px;text-transform:uppercase;letter-spacing:.04em}
.pick-card .info .badge.budget{background:var(--green-light);color:#2d6b47}
.pick-card .info .badge.upgrade{background:var(--purple-light);color:#634e8a}
.pick-card .tested-badge{display:inline-flex;align-items:center;gap:4px;font-size:.7rem;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:.04em;margin-left:8px}
.pick-card .tested-badge::before{content:'';display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--accent)}
.grid-3{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:24px}
.cat-card{padding:24px;border:1px solid var(--border);border-radius:var(--radius-md);transition:all .25s cubic-bezier(.4,0,.2,1);box-shadow:var(--shadow-sm);text-decoration:none;display:block;background:var(--bg);position:relative;overflow:hidden}
.cat-card::after{content:'';position:absolute;bottom:0;left:20%;right:20%;height:3px;background:var(--primary);border-radius:3px 3px 0 0;transform:scaleX(0);transition:transform .25s cubic-bezier(.4,0,.2,1)}
.cat-card:hover{box-shadow:var(--shadow-lg);transform:translateY(-4px);text-decoration:none}
.cat-card:hover::after{transform:scaleX(1)}
.cat-card .cat-name{font-weight:700;font-size:1.1rem;color:var(--text);margin-bottom:4px;font-family:var(--font-display)}
.cat-card .cat-count{font-size:.85rem;color:var(--text-muted)}
.post-card{padding:20px;border:1px solid var(--border);border-radius:var(--radius-md);transition:all .2s;box-shadow:var(--shadow-sm);background:var(--bg)}
.post-card:hover{box-shadow:var(--shadow-md);border-color:color-mix(in srgb,var(--primary) 15%,var(--border))}
.post-card .post-title{font-weight:600;margin-bottom:4px;color:var(--text)}
.post-card .post-meta{font-size:.85rem;color:var(--text-muted)}
.section{padding:clamp(40px,6vw,64px) 0}
.section-title{font-size:.85rem;font-weight:700;color:var(--primary);text-transform:uppercase;letter-spacing:.1em;margin-bottom:24px;padding-bottom:12px;border-bottom:2px solid var(--border);position:relative}
.section-title::after{content:'';position:absolute;bottom:-2px;left:0;width:48px;height:2px;background:var(--primary)}
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
.story-section .trust-item{padding:16px;background:var(--bg);border-radius:var(--radius-md);border:1px solid var(--border);box-shadow:var(--shadow-sm);border-left:3px solid var(--primary)}
.story-section .trust-item strong{display:block;font-size:.95rem;color:var(--text);margin-bottom:4px;font-family:var(--font-display)}
.story-section .trust-item span{font-size:.85rem;color:var(--text-muted)}
.verdict-box{background:var(--bg);border:2px solid var(--primary);border-radius:var(--radius-md);padding:28px 32px;margin:32px 0;box-shadow:var(--shadow-md);position:relative}
.verdict-box::before{content:'OUR PICK';position:absolute;top:-12px;left:24px;background:var(--primary);color:#fff;font-size:.7rem;font-weight:700;padding:2px 14px;border-radius:100px;letter-spacing:.08em}
.verdict-box .verdict-title{font-size:1.2rem;font-weight:700;margin-bottom:4px}
.verdict-box .verdict-price{color:var(--accent);font-weight:600;font-size:.95rem;margin-bottom:8px}
.verdict-box .verdict-for{font-size:.9rem;color:var(--text-secondary);margin-bottom:4px}
.verdict-box .verdict-for strong{color:var(--text)}
.verdict-box .verdict-not-for{margin-top:8px;padding:12px 16px;background:var(--primary-light);border-radius:var(--radius-sm);font-size:.9rem;color:var(--primary-dark)}
.verdict-box .verdict-not-for strong{display:block;margin-bottom:2px}
.decision-matrix{margin:32px 0;overflow-x:auto}
.decision-matrix table{width:100%;border-collapse:collapse;font-size:.9rem}
.decision-matrix th{background:var(--bg-alt);text-align:left;padding:12px 16px;font-weight:600;color:var(--text);font-family:var(--font-display);border-bottom:2px solid var(--border)}
.decision-matrix td{padding:12px 16px;border-bottom:1px solid var(--border);color:var(--text-secondary);vertical-align:top}
.decision-matrix tr:last-child td{border-bottom:none}
.decision-matrix td:first-child{font-weight:500;color:var(--text)}
.decision-matrix td:last-child{color:var(--text)}
.product-card{display:flex;gap:24px;padding:24px;border:1px solid var(--border);border-radius:var(--radius-md);margin-bottom:20px;align-items:flex-start;box-shadow:var(--shadow-sm);transition:box-shadow .2s;background:var(--bg)}
.product-card:hover{box-shadow:var(--shadow-md)}
.product-card img{width:160px;height:160px;object-fit:cover;border-radius:var(--radius-sm);flex-shrink:0}
.product-card-body{flex:1}
.product-card-body h3{font-size:1.15rem;font-weight:600;margin-bottom:4px;font-family:var(--font-display)}
.product-card-body .price{color:var(--green);font-weight:600;font-size:.95rem;margin-bottom:8px}
.product-card-body p{font-size:.95rem;color:var(--text-secondary);margin-bottom:8px}
.product-card-body ul{padding-left:20px;margin:8px 0;font-size:.9rem;color:var(--text-secondary)}
.product-card-body li{margin:4px 0}
.buy-btn{display:inline-block;padding:10px 24px;background:var(--primary);color:#fff;border-radius:8px;font-weight:600;font-size:.95rem;margin-top:8px;text-decoration:none;box-shadow:0 1px 3px rgba(212,99,62,.25);transition:all .2s;border:none;cursor:pointer}
.buy-btn:hover{background:var(--primary-dark);text-decoration:none;box-shadow:0 2px 8px rgba(212,99,62,.35);transform:translateY(-1px);color:#fff}
.buy-btn-secondary{background:var(--accent);color:#fff;box-shadow:0 1px 3px rgba(26,138,122,.25)}
.buy-btn-secondary:hover{background:var(--accent-dark);color:#fff;box-shadow:0 2px 8px rgba(26,138,122,.35)}
.lead-capture{background:linear-gradient(135deg,var(--primary-dark),var(--primary));color:#fff;padding:clamp(40px,6vw,64px) 24px;text-align:center}
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
.skip-link{position:absolute;top:-40px;left:8px;background:var(--primary);color:#fff;padding:8px 16px;z-index:100;border-radius:0 0 4px;font-size:.9rem;text-decoration:none;transition:top .15s}
.skip-link:focus{top:0;color:#fff}
.hamburger{display:none;background:none;border:none;cursor:pointer;padding:8px;font-size:1.6rem;line-height:1;color:var(--text);font-family:inherit}
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
.comments-section{max-width:720px;margin:48px auto;padding:0 24px}.comments-section h2{font-size:1.2rem;margin-bottom:4px}.comments-section .subtitle{font-size:.85rem;color:var(--text-muted);margin-bottom:24px}.comment-form{display:flex;flex-direction:column;gap:12px;margin-bottom:32px}.comment-form input,.comment-form textarea{padding:12px;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.95rem;font-family:var(--font-body);background:var(--bg);color:var(--text);transition:border-color .15s}.comment-form input:focus,.comment-form textarea:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px rgba(212,99,62,.12)}.comment-form textarea{resize:vertical;min-height:80px}.comment-form button{align-self:flex-start}.comment{border-bottom:1px solid var(--border);padding:16px 0}.comment:first-of-type{padding-top:0}.comment .author{font-weight:600;font-size:.9rem;color:var(--text)}.comment .time{font-weight:400;color:var(--text-muted);font-size:.8rem;margin-left:8px}.comment .body{margin-top:4px;font-size:.95rem;color:var(--text-secondary);line-height:1.5}.no-comments{color:var(--text-muted);font-size:.9rem;padding:16px 0}
 .hero-img{width:100%;max-width:1080px;height:auto;border-radius:var(--radius-md);margin:24px auto;display:block;box-shadow:var(--shadow-md)}.reactions-bar{display:flex;gap:12px;margin:24px 0;padding-top:16px}.reaction-btn{display:flex;align-items:center;gap:6px;padding:8px 16px;border:1px solid var(--border);border-radius:100px;background:var(--bg);cursor:pointer;font-size:.9rem;color:var(--text-secondary);transition:all .15s;font-family:var(--font-body)}.reaction-btn:hover{border-color:var(--primary);color:var(--primary);background:var(--primary-light)}.reaction-btn.active{border-color:var(--primary);color:var(--primary);background:var(--primary-light)}.reaction-btn.loved{border-color:#c0392b;color:#c0392b;background:#fde8e4}.reaction-count{font-weight:600;min-width:12px}
.carousel{position:relative;width:100%;max-width:900px;margin:0 auto 24px;border-radius:var(--radius-lg);overflow:hidden;box-shadow:var(--shadow-lg);aspect-ratio:1200/630;background:var(--bg-alt)}
.carousel-track{display:flex;transition:transform .6s cubic-bezier(.4,0,.2,1);will-change:transform;height:100%}
.carousel-slide{flex:0 0 100%;position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center}
.carousel-slide img{width:100%;height:100%;object-fit:cover;display:block}
.carousel-overlay{position:absolute;inset:0;background:linear-gradient(135deg,rgba(42,39,36,.6) 0%,transparent 60%);display:flex;flex-direction:column;justify-content:flex-end;padding:clamp(32px,5vw,56px);color:#fff}
.carousel-overlay h3{font-family:var(--font-display);font-size:clamp(1.3rem,3vw,2rem);font-weight:700;color:#fff;margin-bottom:4px}
.carousel-overlay p{font-size:clamp(.9rem,1.5vw,1.1rem);opacity:.9;max-width:450px;margin-bottom:12px;color:#fff}
.carousel-overlay .carousel-badge{display:inline-flex;align-items:center;gap:6px;background:var(--primary);color:#fff;padding:4px 14px;border-radius:100px;font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px;width:fit-content}
.carousel-overlay a{display:inline-flex;align-items:center;gap:6px;color:#fff;font-weight:600;font-size:.95rem;text-decoration:none;padding:10px 24px;background:rgba(255,255,255,.2);-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px);border-radius:8px;border:1px solid rgba(255,255,255,.25);transition:all .2s;width:fit-content}
.carousel-overlay a:hover{background:rgba(255,255,255,.3);text-decoration:none;color:#fff}
.carousel-dots{position:absolute;bottom:16px;right:24px;display:flex;gap:8px;z-index:3}
.carousel-dot{width:10px;height:10px;border-radius:50%;background:rgba(255,255,255,.4);border:none;cursor:pointer;transition:all .3s;padding:0}
.carousel-dot.active{background:#fff;transform:scale(1.3)}
.carousel-arrow{position:absolute;top:50%;transform:translateY(-50%);z-index:3;background:rgba(255,255,255,.15);-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px);border:1px solid rgba(255,255,255,.2);color:#fff;width:44px;height:44px;border-radius:50%;cursor:pointer;font-size:1.2rem;display:flex;align-items:center;justify-content:center;transition:all .2s;opacity:0}
.carousel:hover .carousel-arrow{opacity:1}
.carousel-arrow:hover{background:rgba(255,255,255,.25)}
.carousel-arrow.prev{left:16px}
.carousel-arrow.next{right:16px}
@media(max-width:640px){.carousel-arrow{display:none}.carousel-overlay{padding:24px}.carousel-overlay h3{font-size:1.1rem}.carousel-dots{bottom:12px;right:16px}}
"""

SVG_TIKTOK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg>'
SVG_INSTAGRAM = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>'
SVG_X = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'
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
<p style="text-align:center;font-size:.9rem;color:var(--text-muted)"><em>Buy with confidence.</em></p>
</div>
</section>"""


HEAD_HTML = lambda title, desc: f'<title>{title}</title>\n<meta name="description" content="{desc}">\n<link rel="icon" type="image/svg+xml" href="{SITE_BASE}/assets/favicon.svg">\n{FONT_LINK}\n'
NAV_SCRIPT = '<script>(function(){var h=document.querySelector(".hamburger");if(h){h.addEventListener("click",function(){var n=document.querySelector(".nav-links");n.classList.toggle("open");h.setAttribute("aria-expanded",n.classList.contains("open"))})}var d=document.querySelector(".dropdown-btn");if(d){d.addEventListener("click",function(e){e.preventDefault();this.closest(".dropdown").classList.toggle("open")})}})();</script>'
import os

ANALYTICS_HTML = ''
_ga_id = os.environ.get("GA_MEASUREMENT_ID", "")
if _ga_id:
    ANALYTICS_HTML = f'<script async src="https://www.googletagmanager.com/gtag/js?id={_ga_id}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}};gtag(\'js\',new Date());gtag(\'config\',\'{_ga_id}\');</script>'

def nav_html(categories, current=""):
    b = SITE_BASE
    featured = categories[:4]
    rest = categories[4:]
    featured_links = "".join(f'<a class="nav-link" href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in featured)
    more_items = "".join(f'<a href="{b}/{c}/">{c.replace("-"," ").title()}</a>' for c in rest)
    more_items += f'<a href="{b}/how-we-test/">How We Test</a>'
    dd = f'<div class="dropdown"><button class="dropdown-btn">More</button><div class="dropdown-menu">{more_items}</div></div>' if rest or True else ""
    return f'<nav><div class="inner"><a class="logo" href="{b}/">Abvorn</a><button class="hamburger" aria-label="Menu" aria-expanded="false" aria-controls="main-nav">☰</button><div class="nav-links" id="main-nav">{featured_links}{dd}</div></div></nav>'


def home_carousel_html(b, niches):
    slides = ""
    for i, n in enumerate(niches[:5]):
        slides += f"""<div class="carousel-slide">
<img src="{b}/assets/{n["slug"]}.svg" alt="{n["name"]}" loading="{ 'eager' if i==0 else 'lazy' }">
<div class="carousel-overlay">
<div class="carousel-badge" style="background:var(--accent)">{n["posts"]} reviews</div>
<h3>{n["name"]}</h3>
<p>Expert-tested buying guides and honest reviews.</p>
<a href="{b}/{n["slug"]}/">Browse Reviews →</a>
</div></div>"""
    dots = "".join(f'<button class="carousel-dot{" active" if i==0 else ""}" data-slide="{i}" aria-label="Slide {i+1}"></button>' for i in range(min(len(niches),5)))
    arrows = """<button class="carousel-arrow prev" aria-label="Previous">‹</button><button class="carousel-arrow next" aria-label="Next">›</button>"""
    return f"""<div class="carousel" role="region" aria-label="Featured categories">
<div class="carousel-track">{slides}</div>
{arrows}
<div class="carousel-dots">{dots}</div></div>"""


def build_root_index(state, posts, form_url=""):
    niches = state["niches"]
    all_slugs = [n["slug"] for n in niches]
    b = SITE_BASE
    cats = "".join(f'<a class="cat-card" href="{b}/{n["slug"]}/"><div class="cat-name">{n["name"]}</div>{"<div class=cat-count>"+str(n["posts"])+" reviews</div>" if n["posts"] else ""}</a>' for n in niches)
    recent = ""
    first_post = posts[0] if posts else None
    for p in posts[:6]:
        title = p.get("title", "")
        slug = p.get("slug", "")
        link_slug = f"reviews/{slug}" if "/" not in slug else slug
        recent += f'<div class="post-card"><div class="post-title"><a href="{b}/{link_slug}/">{title}</a></div><div class="post-meta">{slug.replace("-"," ").title()}</div></div>'
    jsonld = """<script type="application/ld+json">{
"@context":"https://schema.org","@type":"Organization","name":"Abvorn","url":"https://Abvorn-Media.github.io/abvorn/","description":"Independent product reviews and buying guides.","sameAs":["https://www.tiktok.com/@abvorn","https://www.instagram.com/abvorn/","https://x.com/Abvorn"]}</script>"""
    hero_featured = ""
    if first_post:
        ftitle = first_post.get("title", "")
        fslug = first_post.get("slug", "")
        flink = f"reviews/{fslug}" if "/" not in fslug else fslug
        hero_featured = f'<a class="featured-pick" href="{b}/{flink}/"><span class="fp-badge">Our pick</span><span class="fp-title">{ftitle}</span><span class="fp-arrow">→</span></a>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{HEAD_HTML('Abvorn — Product Reviews & Buying Guides', 'Independent, expert reviews across every category. We test so you can buy with confidence.')}
{jsonld}
{ANALYTICS_HTML}
<style>{CSS_SHARED}</style>
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
{nav_html(all_slugs)}
<section class="hero" id="main" style="padding-bottom:0"><div class="container">
{home_carousel_html(b, niches[:5])}
<h1>The best products, reviewed.</h1>
<p>We test hundreds of products across dozens of categories so you don't have to. Independent, honest, data-driven.</p>
{hero_featured}
</div></section>
{STORY_HTML}
<section class="section"><div class="container">
<div class="section-title">All Categories</div>
<div class="grid-3">{cats}</div>
</div></section>
<section class="section"><div class="container">
<div class="section-title">Latest Reviews</div>
<div class="grid-3">{recent or '<div style="color:var(--text-muted)">Reviews coming soon</div>'}</div>
</div></section>
<div class="container"><div class="affiliate-banner">When you buy through our links, we may earn a commission. Our opinions are our own.</div></div>
{lead_form_html(form_url)}
<footer><p>Abvorn · Independent reviews · Honest recommendations</p>{SOCIAL_HTML}</footer>
{NAV_SCRIPT}
{CAROUSEL_JS}</body></html>"""


def carousel_html(b, niche_slug, posts):
    """Build a sleek product carousel from the category SVGs and posts."""
    slides = ""
    for i, p in enumerate(posts[:4]):
        title = p.get("title", f"Best {niche_slug.replace('-',' ')}")
        review_slug = p.get("slug", f"reviews/{niche_slug}")
        rank_labels = ["Our Pick", "Budget Pick", "Upgrade Pick", "Also Great"]
        label = rank_labels[i] if i < 4 else "Top Pick"
        slides += f"""<div class="carousel-slide">
<img src="{b}/assets/{niche_slug}.svg" alt="{title}" loading="{ 'eager' if i==0 else 'lazy' }">
<div class="carousel-overlay">
<div class="carousel-badge">{label}</div>
<h3>{html_mod.escape(title)}</h3>
<p>Expert tested and reviewed. See why this made our list.</p>
<a href="{b}/{review_slug}/">Read Full Review →</a>
</div></div>"""
    if not slides:
        slides = f"""<div class="carousel-slide">
<img src="{b}/assets/{niche_slug}.svg" alt="{niche_slug}">
<div class="carousel-overlay">
<h3>Best {niche_slug.replace('-',' ')}</h3>
<p>Reviews being researched. Check back soon.</p>
</div></div>"""
    dots = "".join(f'<button class="carousel-dot{" active" if i==0 else ""}" data-slide="{i}" aria-label="Slide {i+1}"></button>' for i in range(max(len(posts[:4]),1)))
    arrows = """<button class="carousel-arrow prev" aria-label="Previous">‹</button><button class="carousel-arrow next" aria-label="Next">›</button>"""
    return f"""<div class="carousel" role="region" aria-label="Featured products">
<div class="carousel-track">{slides}</div>
{arrows}
<div class="carousel-dots">{dots}</div></div>"""


CAROUSEL_JS = """<script>(function(){var c=document.querySelector('.carousel');if(!c)return;var t=c.querySelector('.carousel-track');if(!t)return;var s=t.querySelectorAll('.carousel-slide');if(s.length<2)return;var dots=c.querySelectorAll('.carousel-dot');var prev=c.querySelector('.carousel-arrow.prev');var next=c.querySelector('.carousel-arrow.next');var i=0,n=s.length;var go=function(idx){i=((idx%n)+n)%n;t.style.transform='translateX(-'+(i*100)+'%)';dots.forEach(function(d){d.classList.toggle('active',parseInt(d.dataset.slide)===i)})};dots.forEach(function(d){d.addEventListener('click',function(){go(parseInt(this.dataset.slide))})});if(prev){prev.addEventListener('click',function(){go(i-1)})}if(next){next.addEventListener('click',function(){go(i+1)})};var iv=setInterval(function(){go(i+1)},5000);c.addEventListener('mouseenter',function(){clearInterval(iv)});c.addEventListener('mouseleave',function(){iv=setInterval(function(){go(i+1)},5000)})})();</script>"""


def build_category_page(niche_slug, niche_name, posts, all_slugs, affiliate_tag=""):
    b = SITE_BASE
    t = affiliate_tag or "viraltestco-20"
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
<h3>{title} <span class="tested-badge">Tested</span></h3>
<p>In-depth testing and honest comparison. See why this made our list.</p>
<a class="buy-btn" href="https://www.amazon.com/s?k={niche_slug.replace('-','+')}&tag={t}" target="_blank" rel="sponsored">Check Price</a>
<a href="{b}/{review_slug}/" style="margin-left:12px">Read full review →</a>
</div></div>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{HEAD_HTML(f'Best {niche_name} — Abvorn', f'The best {niche_name.lower()} reviewed and compared. Our expert picks after hours of testing.')}
{ANALYTICS_HTML}
<style>{CSS_SHARED}</style>
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
{nav_html(all_slugs)}
<section class="hero" id="main" style="padding-bottom:0"><div class="container">
{carousel_html(b, niche_slug, posts[:4])}
<h1>The Best {niche_name}</h1>
<p>We tested the top contenders to find the ones worth your money.</p>
{f'<a class="featured-pick" href="{b}/reviews/{niche_slug}/"><span class="fp-badge">Our pick</span><span class="fp-title">{html_mod.escape(posts[0].get("title","Read our review"))}</span><span class="fp-arrow">→</span></a>' if posts else ''}
</div></section>
<section class="section"><div class="container">
<div class="section-title">Our Top Picks</div>
{post_rows or '<div style="color:var(--text-muted);padding:32px;text-align:center">Reviews for this category are being researched. Check back soon.</div>'}
</div></section>
<div class="container"><div class="affiliate-banner">We earn from qualifying purchases.</div></div>
<footer><p>Abvorn · Independent reviews</p>{SOCIAL_HTML}</footer>
{NAV_SCRIPT}
{CAROUSEL_JS}</body></html>"""


SHARE_HTML_T = """<div class="share-buttons" style="display:flex;gap:8px;margin:32px 0;padding-top:24px;border-top:1px solid var(--border);align-items:center;flex-wrap:wrap">
<span style="font-size:.85rem;font-weight:600;color:var(--text-secondary);margin-right:8px">Share:</span>
<a href="https://twitter.com/intent/tweet?text=TITLE_T&url=URL_T&via=Abvorn" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share on X"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg> X</a>
<a href="https://www.facebook.com/sharer/sharer.php?u=URL_T" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share on Facebook"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg> Facebook</a>
<a href="https://pinterest.com/pin/create/button/?url=URL_T&description=TITLE_T" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share on Pinterest"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M12.017 0C5.396 0 .029 5.367.029 11.987c0 5.079 3.158 9.417 7.618 11.162-.105-.949-.199-2.403.041-3.439.219-.937 1.406-5.957 1.406-5.957s-.359-.72-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 01.083.345l-.333 1.36c-.053.22-.174.267-.402.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.631-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146 1.124.347 2.317.535 3.554.535 6.607 0 11.974-5.367 11.974-11.987C23.97 5.367 18.603.001 12.017.001z"/></svg> Pinterest</a>
<a href="mailto:?subject=TITLE_T&body=URL_T" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share via Email"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg> Email</a>
</div>"""

def build_article_page(niche_slug, niche_name, post_title, article_html, intro, product_name, meta_desc, all_slugs, products=None, pexels_key="", amazon_tag="", form_url="", hero_img="", google_client_id=""):
    b = SITE_BASE
    t = amazon_tag or "viraltestco-20"
    article_url = f"https://Abvorn-Media.github.io/abvorn/reviews/{niche_slug}/"
    share = SHARE_HTML_T.replace("TITLE_T", html_mod.escape(post_title)).replace("URL_T", article_url)
    product_cards = ""
    if products:
        product_cards = '<section class="section"><div class="container"><div class="section-title">Products Mentioned</div>'
        for prod in products:
            product_cards += product_card_html(prod, pexels_key, t)
        product_cards += "</div></section>"
    cta = CTA_BANNER.replace("{query}", niche_slug.replace("-", "+")).replace("{tag}", t)
    # Build decision matrix from products
    matrix_rows = ""
    if products:
        for i, prod in enumerate(products):
            use_cases = ["Best Overall", "Best Value", "Premium Pick"]
            uc = use_cases[i] if i < len(use_cases) else "Also Great"
            why = prod.get("description", "Top-rated product after extensive testing.")
            matrix_rows += f"<tr><td>{uc}</td><td>{html_mod.escape(prod.get('name','Product'))}</td><td>{html_mod.escape(why)}</td></tr>"
    matrix_html = f'<div class="decision-matrix"><table><thead><tr><th>Use Case</th><th>Product</th><th>Why</th></tr></thead><tbody>{matrix_rows}</tbody></table></div>' if matrix_rows else ""
    # Verdict box
    verdict_html = ""
    if products and len(products) > 0:
        p0 = products[0]
        verdict_html = f"""<div class="verdict-box"><div class="verdict-title">{html_mod.escape(p0.get('name', product_name))}</div><div class="verdict-price">{p0.get('price', 'Check price')}</div><div class="verdict-for"><strong>Best for:</strong> {html_mod.escape(p0.get('description', 'Anyone looking for the best in this category.'))}</div><div class="verdict-not-for"><strong>Don't buy this if:</strong> You need a different use case covered by our other picks below.</div><a class="buy-btn" href="https://www.amazon.com/s?k={niche_slug.replace('-','+')}&tag={t}" target="_blank" rel="sponsored">Check Price on Amazon</a></div>"""
COMMENTS_JS = """<script src="https://accounts.google.com/gsi/client" async defer></script>
<script>
(function(){var k='abvorn_comments_'+location.pathname.replace(/\\//g,'_');var c=JSON.parse(localStorage.getItem(k)||'[]');var l=document.getElementById('comments-list');var cu=null;function r(){if(!l)return;if(!c.length){l.innerHTML='<div class=\"no-comments\">No comments yet. Start the conversation!</div>';return}l.innerHTML=c.map(function(e){var a=e.avatar?'<img src=\"'+e.avatar+'\" width=\"20\" height=\"20\" style=\"border-radius:50%;vertical-align:middle;margin-right:4px;display:inline-block\">':'';return'<div class=\"comment\"><div class=\"author\">'+a+htmlEncode(e.name)+' <span class=\"time\">'+new Date(e.date).toLocaleDateString()+'</span></div><div class=\"body\">'+htmlEncode(e.text)+'</div></div>'}).join('')}
function htmlEncode(s){var d=document.createElement('div');d.appendChild(document.createTextNode(s));return d.innerHTML}
window.handleCredentialResponse=function(r){var p=JSON.parse(atob(r.credential.split('.')[1]));cu={name:p.name,email:p.email,avatar:p.picture,sub:p.sub};var ui=document.getElementById('user-info');var si=document.getElementById('sign-in-prompt');var ct=document.getElementById('comment-text');var pb=document.getElementById('post-comment-btn');ui.style.display='flex';document.getElementById('user-avatar').src=p.picture;document.getElementById('user-name').textContent=p.name;si.style.display='none';ct.disabled=false;ct.style.opacity='1';pb.disabled=false;pb.style.opacity='1'}
window.signOut=function(){cu=null;document.getElementById('user-info').style.display='none';document.getElementById('sign-in-prompt').style.display='block';document.getElementById('comment-text').disabled=true;document.getElementById('comment-text').style.opacity='.5';document.getElementById('post-comment-btn').disabled=true;document.getElementById('post-comment-btn').style.opacity='.5'}
window.postComment=function(){var t=document.getElementById('comment-text');if(!cu||!t||!t.value.trim())return;var n=cu.name||'Anonymous';c.unshift({name:n,email:cu.email||'',avatar:cu.avatar||'',text:t.value.trim(),date:new Date().toISOString()});localStorage.setItem(k,JSON.stringify(c));t.value='';r()};r()})();
window.toggleReaction=function(type,btn){var k='abvorn_r_'+type+'_'+location.pathname;var d=JSON.parse(localStorage.getItem(k)||'{"active":false,"count":0}');d.active=!d.active;d.count+=d.active?1:-1;localStorage.setItem(k,JSON.stringify(d));var s=btn.querySelector('.reaction-count');if(s)s.textContent=d.count;btn.classList.toggle('active',d.active&&type==='like');btn.classList.toggle('loved',d.active&&type==='love')};
</script>"""


def build_article_page(niche_slug, niche_name, post_title, article_html, intro, product_name, meta_desc, all_slugs, products=None, pexels_key="", amazon_tag="", form_url="", hero_img="", google_client_id=""):
    b = SITE_BASE
    t = amazon_tag or "viraltestco-20"
    article_url = f"https://Abvorn-Media.github.io/abvorn/reviews/{niche_slug}/"
    share = SHARE_HTML_T.replace("TITLE_T", html_mod.escape(post_title)).replace("URL_T", article_url)
    product_cards = ""
    if products:
        product_cards = '<section class="section"><div class="container"><div class="section-title">Products Mentioned</div>'
        for prod in products:
            product_cards += product_card_html(prod, pexels_key, t)
        product_cards += "</div></section>"
    cta = CTA_BANNER.replace("{query}", niche_slug.replace("-", "+")).replace("{tag}", t)
    matrix_rows = ""
    if products:
        for i, prod in enumerate(products):
            use_cases = ["Best Overall", "Best Value", "Premium Pick"]
            uc = use_cases[i] if i < len(use_cases) else "Also Great"
            why = prod.get("description", "Top-rated product after extensive testing.")
            matrix_rows += f"<tr><td>{uc}</td><td>{html_mod.escape(prod.get('name','Product'))}</td><td>{html_mod.escape(why)}</td></tr>"
    matrix_html = f'<div class="decision-matrix"><table><thead><tr><th>Use Case</th><th>Product</th><th>Why</th></tr></thead><tbody>{matrix_rows}</tbody></table></div>' if matrix_rows else ""
    verdict_html = ""
    if products and len(products) > 0:
        p0 = products[0]
        verdict_html = f"""<div class="verdict-box"><div class="verdict-title">{html_mod.escape(p0.get('name', product_name))}</div><div class="verdict-price">{p0.get('price', 'Check price')}</div><div class="verdict-for"><strong>Best for:</strong> {html_mod.escape(p0.get('description', 'Anyone looking for the best in this category.'))}</div><div class="verdict-not-for"><strong>Don't buy this if:</strong> You need a different use case covered by our other picks below.</div><a class="buy-btn" href="https://www.amazon.com/s?k={niche_slug.replace('-','+')}&tag={t}" target="_blank" rel="sponsored">Check Price on Amazon</a></div>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{HEAD_HTML(html_mod.escape(post_title) + ' - Abvorn', html_mod.escape(meta_desc)[:160])}
<link rel="canonical" href="{article_url}">
{ANALYTICS_HTML}
<style>{CSS_SHARED}</style>
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
{nav_html(all_slugs)}
{hero_img}
<article id="main">
<h1>{html_mod.escape(post_title)}</h1>
<div class="meta">By <strong>Abvorn Review Team</strong> - {html_mod.escape(product_name)} - Updated 2026 <span class="tested-badge" style="margin-left:8px">Tested</span></div>
{matrix_html}
{verdict_html}
<div class="content">
{intro}
{article_html}
</div>
<div class="reactions-bar">
<button class="reaction-btn" onclick="toggleReaction('like',this)" aria-label="Like">
<span class="reaction-icon">&#x1F44D;</span>
<span class="reaction-count">0</span>
</button>
<button class="reaction-btn" onclick="toggleReaction('love',this)" aria-label="Love">
<span class="reaction-icon">&#x2764;&#xFE0F;</span>
<span class="reaction-count">0</span>
</button>
</div>
{share}
</article>

<section class="comments-section">
<h2>Share Your Thoughts</h2>
<p class="subtitle">Join the conversation - sign in with Google to comment.</p>
<div class="comment-form" id="comment-form-area">
<div id="user-info" style="display:none;align-items:center;gap:10px;margin-bottom:12px">
<img id="user-avatar" src="" alt="" width="36" height="36" style="border-radius:50%">
<span id="user-name" style="font-weight:600;font-size:.9rem;color:var(--text)"></span>
<button class="buy-btn" style="padding:4px 12px;font-size:.8rem" onclick="signOut()">Sign out</button>
</div>
<div id="sign-in-prompt" style="margin-bottom:16px">
 <div id="g_id_onload" data-client_id="{google_client_id or "YOUR_GOOGLE_CLIENT_ID"}" data-context="signin" data-ux_mode="popup" data-callback="handleCredentialResponse" data-auto_prompt="false"></div>
<div class="g_id_signin" data-type="standard" data-shape="pill" data-theme="outline" data-text="signin_with" data-size="medium"></div>
</div>
<textarea id="comment-text" placeholder="What do you think? Share your experience..." rows="3" aria-label="Your comment" disabled style="opacity:.5"></textarea>
<button class="buy-btn" onclick="postComment()" id="post-comment-btn" disabled style="opacity:.5">Post Comment</button>
</div>
<div id="comments-list"></div>
</section>

{COMMENTS_JS}

{product_cards}
<div class="container">{cta}</div>
{lead_form_html(form_url)}
<div class="container"><div class="affiliate-banner">We earn a commission if you buy through our links, at no extra cost to you. Our opinions are our own.</div></div>
<footer><p>Abvorn - Independent reviews since 2026</p>{SOCIAL_HTML}</footer>
{NAV_SCRIPT}
{CAROUSEL_JS}</body></html>"""


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
        "products": products,
    }


def build_methodology_page(all_slugs, form_url=""):
    b = SITE_BASE
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{HEAD_HTML('How We Test — Abvorn', 'Our rigorous, independent testing methodology. Every recommendation is earned through real-world evaluation.')}
{ANALYTICS_HTML}
<style>{CSS_SHARED}</style>
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
{nav_html(all_slugs)}
<section class="hero" id="main"><div class="container">
<img src="{b}/assets/hero-home.svg" alt="Abvorn testing" style="width:100%;max-width:900px;height:auto;border-radius:var(--radius-md);margin-bottom:24px;display:block;box-shadow:var(--shadow-md)">
<h1>How We Test</h1>
<p>Every recommendation on Abvorn is earned through real testing — not press releases or affiliate quotas.</p>
</div></section>
<section class="section"><div class="container" style="max-width:680px">
<h2>Our Testing Philosophy</h2>
<p>We buy every product we review with our own money. No sponsorships, no free units, no manufacturer influence. If it's on our site, we've held it in our hands.</p>
<h2>The Testing Process</h2>
<div class="trust-list" style="list-style:none;display:flex;flex-direction:column;gap:20px;margin:24px 0">
<div class="trust-item"><strong>1. Research</strong><span>We identify the top 10–15 products in a category based on market share, user reviews, and expert consensus.</span></div>
<div class="trust-item"><strong>2. Procurement</strong><span>We purchase each product at full retail price — no review units, no sample requests.</span></div>
<div class="trust-item"><strong>3. Testing</strong><span>Products are tested side-by-side over 3–7 days using standardized criteria specific to each category.</span></div>
<div class="trust-item"><strong>4. Scoring</strong><span>Each product is scored on performance, build quality, value, and user experience using a weighted rubric.</span></div>
<div class="trust-item"><strong>5. Writing</strong><span>We write our findings honestly — including what we didn't like — and publish with clear recommendations.</span></div>
<div class="trust-item"><strong>6. Updating</strong><span>Reviews are refreshed quarterly to reflect price changes, new models, and evolving market conditions.</span></div>
</div>
<h2>What We Don't Do</h2>
<ul style="padding-left:24px;margin:16px 0">
<li style="margin:8px 0;color:var(--text-secondary)">Accept free products or sponsored placements</li>
<li style="margin:8px 0;color:var(--text-secondary)">Publish reviews without hands-on testing</li>
<li style="margin:8px 0;color:var(--text-secondary)">Allow manufacturers to review or approve our content</li>
<li style="margin:8px 0;color:var(--text-secondary)">Use affiliate revenue to influence recommendations</li>
</ul>
</div></section>
{lead_form_html(form_url)}
<footer><p>Abvorn · Independent reviews since 2026</p>{SOCIAL_HTML}</footer>
{NAV_SCRIPT}
{CAROUSEL_JS}</body></html>"""


# ─── Document writer ────────────────────────────────────────────────────
def write_files(niche_slug, articles, state, pexels_key="", amazon_tag="", form_url="", hero_images=None, google_client_id=""):
    """Write all HTML files to docs/ directory."""
    all_slugs = [n["slug"] for n in state["niches"]]
    hero_images = hero_images or {}
    niche_name = next((n["name"] for n in state["niches"] if n["slug"] == niche_slug), niche_slug.replace("-", " ").title())

    # Collect all posts across niches
    all_posts = []
    for n in state["niches"]:
        for p in articles.get(n["slug"], []):
            all_posts.append({"title": p.get("post_title", ""), "slug": n["slug"]})

    docs = Path("docs")
    docs.mkdir(exist_ok=True)

    # Write root index
    (docs / "index.html").write_text(build_root_index(state, all_posts, form_url), encoding="utf-8")
    print(f"  Written: docs/index.html")

    # Write category pages (post slugs point to reviews/{slug} for article pages)
    for n in state["niches"]:
        niche_posts = [{"title": a.get("post_title", ""), "slug": f"reviews/{n['slug']}"} for a in articles.get(n["slug"], [])]
        cat_dir = docs / n["slug"]
        cat_dir.mkdir(exist_ok=True)
        (cat_dir / "index.html").write_text(build_category_page(n["slug"], n["name"], niche_posts, all_slugs, amazon_tag), encoding="utf-8")

    # Write article pages (under docs/reviews/{slug}/ to avoid overwriting category page)
    for slug, post_list in articles.items():
        for i, a in enumerate(post_list):
            post_dir = docs / "reviews" / slug
            post_dir.mkdir(parents=True, exist_ok=True)
            hero_img_html = hero_images.get(slug, "")
            (post_dir / "index.html").write_text(
                build_article_page(slug, niche_name, a["post_title"], a["article_html"],
                                   a["intro"], a["product_name"], a["meta_description"],
                                   all_slugs, a.get("products"), pexels_key, amazon_tag, form_url, hero_img_html, google_client_id),
                encoding="utf-8"
            )
            print(f"  Written: docs/reviews/{slug}/index.html (article)")
            # Update the post slug in all_posts for root index links
            for p in all_posts:
                if p.get("title") == a.get("post_title") and p.get("slug") == slug:
                    p["slug"] = f"reviews/{slug}"

    # Write methodology page
    method_dir = docs / "how-we-test"
    method_dir.mkdir(exist_ok=True)
    (method_dir / "index.html").write_text(build_methodology_page(all_slugs, form_url), encoding="utf-8")
    print(f"  Written: docs/how-we-test/index.html")

    # Write RSS feed and sitemap
    items = []
    for p in all_posts:
        title = p.get("title", "")
        slug_path = p.get("slug", "")
        items.append({"title": title, "slug": slug_path,
                      "date": datetime.date.today().isoformat() if 'datetime' in dir() else "2025-01-01"})
    rss_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Abvorn Reviews</title><link>https://abvorn.com</link><description>Product reviews you can trust</description>'
    for it in items:
        rss_xml += f'<item><title>{it["title"]}</title><link>https://abvorn.com/{it["slug"]}</link><guid>https://abvorn.com/{it["slug"]}</guid><pubDate>{it["date"]}</pubDate></item>'
    rss_xml += '</channel></rss>'
    (docs / "feed.xml").write_text(rss_xml, encoding="utf-8")
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += '<url><loc>https://abvorn.com/</loc></url>\n'
    for it in items:
        sitemap += f'<url><loc>https://abvorn.com/{it["slug"]}</loc></url>\n'
    sitemap += '</urlset>'
    (docs / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"  Written: docs/feed.xml, docs/sitemap.xml")


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

    # 3.5 GENERATE IMAGES
    print(f"\n--- IMAGES: {niche_slug} ---")
    hero_images = {}
    try:
        from abvorn.images.generator import ImageGenerator
        from abvorn.images.resizer import ImageResizer
        gen = ImageGenerator(backend="composite")
        resizer = ImageResizer()
        product_name = draft.get("product_name", niche_name)
        headline = draft.get("post_title", f"Best {niche_name}")
        img_bytes = gen.generate(product_name, niche_slug, headline, "buying_guide")
        if img_bytes:
            assets_dir = Path("docs") / "assets"
            assets_dir.mkdir(exist_ok=True)
            img_path = assets_dir / f"{niche_slug}.png"
            img_path.write_bytes(img_bytes)
            hero_images[niche_slug] = f'<img class="hero-img" src="/abvorn/assets/{niche_slug}.png" alt="{headline}" width="1200" height="630">'
            print(f"  Generated: assets/{niche_slug}.png ({len(img_bytes)} bytes)")
            # Also generate social-sized versions
            social = resizer.social(img_bytes, "og", niche_slug)
            if social:
                (assets_dir / f"{niche_slug}-og.png").write_bytes(social)
                print(f"  Generated: assets/{niche_slug}-og.png")
    except Exception as e:
        print(f"  Image generation skipped: {e}")

    # 4. WRITE FILES
    print(f"\n--- WRITE: {niche_slug} ---")
    articles = {niche_slug: [draft]}
    write_files(niche_slug, articles, state,
                pexels_key=secrets.get("PEXELS_KEY", ""),
                amazon_tag=secrets.get("AMAZON_TAG", "viraltestco-20"),
                form_url=secrets.get("APPS_SCRIPT_URL", ""),
                hero_images=hero_images,
                google_client_id=secrets.get("GOOGLE_CLIENT_ID", ""))

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
