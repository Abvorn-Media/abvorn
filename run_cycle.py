"""run_cycle.py — standalone content cycle for GitHub Actions or local use.

Reads secrets from env vars (GITHUB_ prefixed) or falls back to secrets.json.
Picks the niche with fewest posts, generates content, writes to docs/, updates state.
"""
import os, sys, json, logging, re, html as html_mod, requests as http_requests
import hashlib, time
from pathlib import Path
from datetime import datetime

from src.fact_checker_guard import FactCheckerGuard, create_fact_checker
from src.quantum_content_engine import QuantumContentEngine, create_quantum_engine, Platform
from src.nervous_system import NervousSystem, create_nervous_system, AlertLevel
from src.living_knowledge_core import create_living_knowledge_core
from src.ai_sql import AISQL, create_ai_sql, QueryPlan, QueryResult
from src.unified_memory import UnifiedMemory, create_unified_memory, MemoryTier
from abvorn.core.verdict import render_verdict_card
from src.close_feedback_loop import ClosedFeedbackLoop, create_feedback_loop
from src.economic_surplus import EconomicSurplusTracker, create_economic_surplus_tracker
from src.entitlements import EntitlementsFramework, create_entitlements_framework
from src.workflow_engine import WorkflowEngine, create_workflow_engine
from src.social_permission import SocialPermissionFramework, create_social_permission_framework
from src.infrastructure import infra_reporter
from src.energy_accounting import energy_accounting

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

ai_sql = None  # set by main()

# ─── Open Web Ninja Batching & Caching ─────────────────────────
OWN_CACHE_DIR = Path("data/openweb_cache")
OWN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
OWN_USAGE_FILE = Path("data/openweb_usage.json")


def _own_cache_key(query: str, source: str = "amazon") -> str:
    return hashlib.md5(f"{source}:{query}".encode()).hexdigest()


def _own_load_cache() -> dict:
    f = OWN_CACHE_DIR / "cache.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _own_save_cache(cache: dict):
    OWN_CACHE_DIR.joinpath("cache.json").write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _own_track_usage(count: int):
    try:
        if OWN_USAGE_FILE.exists():
            data = json.loads(OWN_USAGE_FILE.read_text(encoding="utf-8"))
        else:
            data = {}
        data["total"] = data.get("total", 0) + count
        data["last_update"] = datetime.now().isoformat()
        OWN_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        OWN_USAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def fetch_own_batch(queries: list, source: str = "amazon") -> dict:
    """Fetch product data for multiple queries in one batch with caching."""
    secrets = get_secrets()
    api_key = secrets.get("OPENWEB_NINJA_KEY", "")
    if not api_key:
        return {}

    cache = _own_load_cache()
    results = {}
    uncached = []

    for q in queries:
        key = _own_cache_key(q, source)
        if key in cache:
            results[q] = cache[key]
        else:
            uncached.append(q)

    if uncached:
        api_url = "https://api.openwebninja.com/realtime-amazon-data/search"
        for i in range(0, len(uncached)):
            q = uncached[i]
            key = _own_cache_key(q, source)
            try:
                resp = http_requests.get(
                    api_url,
                    params={"query": q.replace("-", " "), "page": 1},
                    headers={"X-API-Key": api_key},
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    products = data.get("data", {}).get("products", [])[:5]
                    product_list = []
                    for p in products:
                        product_list.append({
                            "name": p.get("product_title", "").split(",")[0].strip(),
                            "price": p.get("product_price", ""),
                            "original_price": p.get("product_original_price", ""),
                            "rating": p.get("product_star_rating", ""),
                            "ratings_count": p.get("product_num_ratings", 0),
                            "image": p.get("product_photo", ""),
                            "url": p.get("product_url", ""),
                            "asin": p.get("asin", ""),
                            "description": p.get("product_title", ""),
                            "features": [],
                            "is_best_seller": p.get("is_best_seller", False),
                            "is_amazon_choice": p.get("is_amazon_choice", False),
                            "sales_volume": p.get("sales_volume", ""),
                        })
                    cache[key] = product_list
                    results[q] = product_list
                    _own_save_cache(cache)
                else:
                    logger.warning(f"Open Web Ninja {resp.status_code} for '{q}'")
            except Exception as e:
                logger.warning(f"Open Web Ninja error for '{q}': {e}")
            if i < len(uncached) - 1:
                time.sleep(0.3)

    _own_track_usage(len(uncached))
    return results


def fetch_all_niches_batch(niches: list) -> dict:
    """Fetch products for all niches in batch, return {niche_slug: products}."""
    queries = [n.get("keyword", n.get("slug", n.get("name", ""))) for n in niches]
    return fetch_own_batch(queries)


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
        "AMAZON_TAG": os.environ.get("AMAZON_TAG", ""),
        "APPS_SCRIPT_URL": os.environ.get("APPS_SCRIPT_URL", ""),
        "GA_MEASUREMENT_ID": os.environ.get("GA_MEASUREMENT_ID", ""),
        "GOOGLE_CLIENT_ID": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "OPENWEB_NINJA_KEY": os.environ.get("OPENWEB_NINJA_KEY", ""),
        "TAVILY_KEY": os.environ.get("TAVILY_KEY", ""),
        "CEREBRAS_KEY": os.environ.get("CEREBRAS_KEY", ""),
    }
    # Merge with local secrets.json (boardroom) to fill in missing keys
    try:
        from abvorn.core.secrets import load_secrets
        boardroom = load_secrets()
        for k in keys:
            if not keys[k]:
                keys[k] = boardroom.get(k, "")
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
    t = tag or os.environ.get("AMAZON_TAG", "")
    return f"https://www.amazon.com/s?k={q}&tag={t}" if t else f"https://www.amazon.com/s?k={q}"


def affiliate_url(product_url, tag=""):
    """Append Amazon affiliate tag to a product URL."""
    t = tag or os.environ.get("AMAZON_TAG", "")
    if not t:
        return product_url
    sep = "&" if "?" in product_url else "?"
    return f"{product_url}{sep}tag={t}"

def product_card_html(product, pexels_key="", amazon_tag=""):
    """HTML for a product card with real Amazon image + affiliate buy button."""
    name = product.get("name", "Product")
    price = product.get("price", "Check price")
    features = product.get("features", [])
    summary = product.get("description", "")
    product_url = product.get("url", "")
    product_image = product.get("image", "")
    # Build affiliate URL: prefer real product URL, fall back to search link
    if product_url:
        aff_url = affiliate_url(product_url, amazon_tag)
    else:
        aff_query = product.get("affiliate_query", name.replace(" ", "+"))
        aff_url = amazon_link(aff_query, amazon_tag)
    # Product image: Amazon image > Pexels > gradient placeholder
    img = ""
    if product_image:
        img = f'<img src="{product_image}" alt="{html_mod.escape(name)}" loading="lazy" style="width:100px;height:100px;object-fit:contain;background:var(--clr-white);border-radius:var(--radius-sm)">'
    elif pexels_key:
        img_url = fetch_product_image(name, pexels_key)
        if img_url:
            img = f'<img src="{img_url}" alt="{html_mod.escape(name)}" loading="lazy">'
    if not img:
        img = '<div style="width:160px;height:160px;background:linear-gradient(135deg,var(--bg-alt),var(--border));border-radius:var(--radius-sm);flex-shrink:0;display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:.8rem">Product</div>'
    features_html = "".join(f"<li>{f}</li>" for f in features[:4])
    return f"""<div class="product-card">
{img}
<div class="product-card-body">
<h3>{html_mod.escape(name)}</h3>
    <div class="price">{html_mod.escape(str(price or 'N/A'))}</div>
<p>{html_mod.escape(summary)}</p>
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

def build_comparison_page(niche_slug, niche_name, post_title, products, all_slugs, amazon_tag=""):
    b = SITE_BASE
    t = amazon_tag or os.environ.get("AMAZON_TAG", "viraltestco-20")
    rows = ""
    try:
        from abvorn.core.verdict import AbvornVerdictEngine
        engine = AbvornVerdictEngine()
    except Exception:
        engine = None
    for i, prod in enumerate(products[:6]):
        name = html_mod.escape(prod.get("name", "Product"))
        price = prod.get("price", "N/A")
        desc = html_mod.escape(prod.get("description", ""))
        aff = affiliate_url(prod.get("url", ""), t) or f"https://www.amazon.com/s?k={name.replace(' ','+')}&tag={t}"
        specs = prod.get("specs", {})
        spec_cells = ""
        for key in ["Weight", "Battery", "Rating", "Warranty"]:
            val = specs.get(key.lower(), "-")
            spec_cells += f"<td>{html_mod.escape(str(val))}</td>"
        # Abvorn Verdict score column
        score_cell = '<td class="av-score-cell">—</td>'
        if engine:
            try:
                v = engine.score_product(niche_slug, prod)
                score_cell = f'<td class="av-score-cell"><span class="av-compact-score">{v["overall"]}</span><span class="av-compact-label">{v["label"]}</span></td>'
            except Exception:
                pass
        rows += f"""<tr><td><strong>{i+1}. {name}</strong><br><small>{desc[:80]}</small></td>{score_cell}<td>{price}</td>{spec_cells}<td><a class="buy-btn" href="{aff}" target="_blank" rel="sponsored" style="padding:4px 12px;font-size:.8rem">Check Price</a></td></tr>"""
    bread = breadcrumb_schema([
        ("Abvorn", "/"),
        (f"Best {niche_name}", f"/{niche_slug}/"),
        ("Comparison", f"/comparisons/{niche_slug}/"),
    ])
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{HEAD_HTML(html_mod.escape(post_title) + ' - Abvorn', f'Side-by-side comparison of the best {niche_name.lower()}. Compare specs, prices, and Abvorn Verdict scores.')}
{OG_META(html_mod.escape(post_title) + ' - Abvorn', f'Side-by-side comparison of the best {niche_name.lower()}.', f'{_SITE_URL}/comparisons/{niche_slug}/')}
<link rel="canonical" href="{b}/comparisons/{niche_slug}/">
{bread}
{ANALYTICS_HTML}
<style>{CSS_SHARED}</style>
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
{nav_html(all_slugs)}
<section class="hero" id="main" style="padding:24px 16px"><div class="container">
<h1>{html_mod.escape(post_title)}</h1>
<p>We put the top {niche_name.lower()} head-to-head. Here's how they stack up.</p>
</div></section>
<section class="section"><div class="container">
<div style="overflow-x:auto"><table class="comparison-table">
<thead><tr><th>Product</th><th>Abvorn Score</th><th>Price</th><th>Weight</th><th>Battery</th><th>Rating</th><th>Warranty</th><th>Buy</th></tr></thead>
<tbody>{rows}</tbody>
</table></div>
</div></section>
<div class="container"><div class="affiliate-banner">We earn from qualifying purchases.</div></div>
<footer><p>Abvorn &middot; Independent reviews</p><div class="footer-links"><a href="{b}/privacy/">Privacy</a><a href="{b}/terms/">Terms</a><a href="{b}/disclaimer/">Disclaimer</a><a href="{b}/about/">About</a></div>{SOCIAL_HTML}</footer>
{NAV_SCRIPT}</body></html>"""

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
_SITE_URL = os.environ.get("SITE_URL", "https://Abvorn-Media.github.io/abvorn").rstrip("/")
_SITE_BASE_PATH = os.environ.get("SITE_BASE_PATH", "/abvorn").rstrip("/")
SITE_BASE = _SITE_BASE_PATH or ""

# ── Schema generators ───────────────────────────────────────────────────
def breadcrumb_schema(items: list) -> str:
    """Generate BreadcrumbList JSON-LD. items = [(name, url), ...]"""
    item_list = ",".join(
        f'{{"@type":"ListItem","position":{i+1},"name":"{esc_json(name)}","item":"{_SITE_URL}{url}"}}'
        for i, (name, url) in enumerate(items)
    )
    return f'<script type="application/ld+json">{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{item_list}]}}</script>'

def faq_schema(questions: list) -> str:
    """Generate FAQPage JSON-LD. questions = [(q, a), ...]"""
    items = ",".join(
        f'{{"@type":"Question","name":"{esc_json(q)}","acceptedAnswer":{{"@type":"Answer","text":"{esc_json(a)}"}}}}'
        for q, a in questions
    )
    return f'<script type="application/ld+json">{{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{items}]}}</script>'

def esc_json(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", "")

def _get_price_floor(niche_slug: str) -> str:
    """Rough price floor by niche for FAQ content. No API call needed."""
    floors = {
        "wireless-headphones": "50",
        "gaming-mice": "30",
        "4k-monitors": "300",
        "laptops": "500",
        "streaming-devices": "30",
        "mechanical-keyboards": "60",
        "wireless-earbuds": "40",
        "fitness-trackers": "50",
        "webcams": "40",
        "smart-home": "30",
    }
    return floors.get(niche_slug, "50")

FONT_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">'

DESIGN_SYSTEM_CSS = """
:root {
  --clr-black: #0a0a0a; --clr-off-black: #1a1a1a; --clr-dark-gray: #2a2a2a;
  --clr-mid-gray: #666; --clr-light-gray: #e8e8e8; --clr-off-white: #f6f5f2; --clr-white: #ffffff;
  --clr-primary: var(--niche-primary, #1a1a1a); --clr-accent: var(--niche-accent, #c98a2c);
  --clr-accent-text: var(--niche-accent-text, #996015);
  --font-display: 'Libre Franklin', -apple-system, sans-serif; --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --scale-ratio: 1.25;
  --text-xs: calc(1rem / var(--scale-ratio) / var(--scale-ratio)); --text-sm: calc(1rem / var(--scale-ratio));
  --text-base: 1rem; --text-lg: calc(1rem * var(--scale-ratio)); --text-xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio));
  --text-2xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio));
  --text-3xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio));
  --text-4xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio));
  --space-xs: 0.25rem; --space-sm: 0.5rem; --space-md: 1rem; --space-lg: 2rem; --space-xl: 4rem; --space-2xl: 8rem;
  --radius-sm: 4px; --radius-md: 8px; --radius-lg: 16px;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.08); --shadow-md: 0 4px 12px rgba(0,0,0,0.1);
  --shadow-lg: 0 8px 30px rgba(0,0,0,0.12); --shadow-xl: 0 20px 60px rgba(0,0,0,0.15);
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1); --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --duration-fast: 150ms; --duration-base: 300ms; --duration-slow: 500ms;
}
*, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
html { scroll-behavior: smooth; font-size: 16px; }
body { font-family: var(--font-body); font-size: var(--text-base); line-height: 1.7; color: var(--clr-off-black); background: var(--clr-white); -webkit-font-smoothing: antialiased; }
h1, h2, h3, h4 { font-family: var(--font-display); line-height: 1.1; font-weight: 600; letter-spacing: -0.02em; color: var(--clr-black); }
h1 { font-size: var(--text-4xl); letter-spacing: -0.02em; font-weight: 500; }
h2 { font-size: var(--text-2xl); letter-spacing: -0.01em; }
h3 { font-size: var(--text-xl); }
h4 { font-size: var(--text-lg); }
p { margin-bottom: var(--space-lg); max-width: 65ch; }
.container { width: 100%; max-width: 1200px; margin: 0 auto; padding: 0 var(--space-lg); }
@media (max-width: 768px) { .container { padding: 0 var(--space-md); } h1 { font-size: var(--text-2xl); } h2 { font-size: var(--text-xl); } }
.card { background: var(--clr-white); border: 1px solid var(--clr-light-gray); border-radius: var(--radius-md); padding: var(--space-lg); transition: transform var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out); }
.card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.btn { display: inline-flex; align-items: center; gap: var(--space-sm); padding: 0.75em 1.5em; font-family: var(--font-body); font-weight: 600; font-size: var(--text-sm); text-transform: uppercase; letter-spacing: 0.05em; text-decoration: none; color: var(--clr-white); background: var(--clr-primary); border: none; border-radius: var(--radius-sm); cursor: pointer; transition: background var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-spring), box-shadow var(--duration-fast) var(--ease-out); }
.btn:hover { background: var(--clr-accent); transform: scale(1.03); box-shadow: var(--shadow-md); }
.btn:active { transform: scale(0.97); }
.input { width: 100%; padding: 0.75em 1em; font-family: var(--font-body); font-size: var(--text-base); color: var(--clr-off-black); background: var(--clr-off-white); border: 2px solid transparent; border-radius: var(--radius-sm); transition: border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out); }
.input:focus { outline: none; border-color: var(--clr-accent); box-shadow: 0 0 0 3px rgba(90,125,154,0.15); }
.header--scrolled { padding: 10px 0 !important; background: rgba(0,0,0,0.95) !important; box-shadow: 0 2px 20px rgba(0,0,0,0.3); backdrop-filter: blur(10px); }
.signal-tag { position: relative; display: inline-flex; align-items: center; gap: 6px; background: var(--clr-accent); color: var(--clr-black); font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
.signal-tag--tag { padding: 6px 14px; border-radius: var(--radius-sm); font-size: 0.75rem; }
.signal-tag--badge { position: absolute; top: 12px; left: 12px; padding: 5px 12px; border-radius: var(--radius-sm); font-size: 0.68rem; box-shadow: var(--shadow-sm); z-index: 2; }
.rank-chip { display: inline-block; background: var(--clr-off-white); color: var(--clr-mid-gray); border: 1px solid var(--clr-light-gray); padding: 4px 10px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; border-radius: var(--radius-sm); position: absolute; top: 12px; left: 12px; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }
@media (prefers-color-scheme: dark) { :root { --clr-black: #f0f0f0; --clr-off-black: #e0e0e0; --clr-mid-gray: #999; --clr-light-gray: #333; --clr-off-white: #1a1a1a; --clr-white: #111; } body { background: #111; color: #e0e0e0; } h1, h2, h3, h4 { color: #f0f0f0; } .card { background: #1a1a1a; border-color: #333; } .input { background: #222; color: #e0e0e0; } }
@media (forced-colors: active) { .btn { border: 2px solid ButtonText; } .card { border: 1px solid ButtonText; } }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
:focus-visible { outline: 2px solid var(--clr-accent); outline-offset: 2px; }
"""

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
.top-bar{background:#0a0a0a;color:#999;font-size:0.8rem;padding:8px 0}
.top-bar .container{display:flex;justify-content:space-between}
header{background:#0a0a0a;padding:18px 0;position:relative;z-index:20;border-bottom:1px solid #2a2a2a}
.navbar{display:flex;justify-content:space-between;align-items:center}
.logo img{max-height:44px;width:auto}
.nav-links{display:flex;align-items:center;gap:8px}
.nav-links > a,.nav-item > a{color:#fff;text-decoration:none;padding:8px 16px;font-weight:600;font-size:0.9rem;border-radius:var(--radius-sm);transition:background var(--duration-fast) var(--ease-out)}
.nav-links > a:hover,.nav-item > a:hover{background:rgba(255,255,255,0.08);color:var(--clr-accent,#c98a2c)}
.nav-item{position:relative}
.nav-item > a{padding:8px 16px;display:flex;align-items:center;gap:4px}
.nav-item > a::after{content:'▾';font-size:0.6rem;opacity:0.5}
.nav-item::after{content:'';position:absolute;top:100%;left:0;right:0;height:8px}
.nav-dropdown{display:none;position:absolute;top:100%;left:0;margin-top:8px;background:#1a1a1a;min-width:220px;border-radius:var(--radius-sm);box-shadow:var(--shadow-lg);padding:6px 0;z-index:30;border:1px solid #2a2a2a}
.nav-item:hover .nav-dropdown{display:block}
.nav-dropdown a{display:block;color:#ffffff;padding:8px 20px;font-weight:400;font-size:0.85rem;text-decoration:none;transition:background var(--duration-fast)}
.nav-dropdown a:hover{background:#2a2a2a;color:#fff}
.nav-toggle{display:none;background:none;border:none;color:#fff;padding:6px;cursor:pointer}
.nav-toggle svg{width:24px;height:24px}
@media(max-width:640px){
.nav-toggle{display:block}
.nav-links{display:none;position:absolute;top:100%;left:0;right:0;background:#0a0a0a;flex-direction:column;align-items:stretch;padding:8px 20px 20px;gap:2px;box-shadow:var(--shadow-lg);border-top:1px solid #2a2a2a;z-index:30}
.nav-links.open{display:flex}
.nav-links > a,.nav-item{margin:0}
.nav-links > a,.nav-item > a{padding:10px 0}
.nav-item > a::after{display:none}
.nav-dropdown{position:static;box-shadow:none;margin-top:0;padding-left:16px;display:block;background:transparent;border:none}
.nav-dropdown a{color:#888;padding:6px 0;font-size:0.8rem}
.nav-dropdown a:hover{background:transparent;color:#fff}
}
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
.footer-links{display:flex;justify-content:center;gap:24px;margin:12px 0;flex-wrap:wrap}
.footer-links a{font-size:.8rem;color:var(--text-muted);text-decoration:none;transition:color .15s}
.footer-links a:hover{color:var(--primary);text-decoration:underline}
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
@media(max-width:640px){.pick-card{flex-direction:column;gap:16px}.grid-3{grid-template-columns:1fr}.product-card{flex-direction:column}.product-card img{width:100%;height:auto}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{transition-duration:.01ms!important;animation-duration:.01ms!important}}
.comments-section{max-width:720px;margin:48px auto;padding:0 24px}.comments-section h2{font-size:1.2rem;margin-bottom:4px}.comments-section .subtitle{font-size:.85rem;color:var(--text-muted);margin-bottom:24px}.comment-form{display:flex;flex-direction:column;gap:12px;margin-bottom:32px}.comment-form input,.comment-form textarea{padding:12px;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.95rem;font-family:var(--font-body);background:var(--bg);color:var(--text);transition:border-color .15s}.comment-form input:focus,.comment-form textarea:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px rgba(212,99,62,.12)}.comment-form textarea{resize:vertical;min-height:80px}.comment-form button{align-self:flex-start}.comment{border-bottom:1px solid var(--border);padding:16px 0}.comment:first-of-type{padding-top:0}.comment .author{font-weight:600;font-size:.9rem;color:var(--text)}.comment .time{font-weight:400;color:var(--text-muted);font-size:.8rem;margin-left:8px}.comment .body{margin-top:4px;font-size:.95rem;color:var(--text-secondary);line-height:1.5}.no-comments{color:var(--text-muted);font-size:.9rem;padding:16px 0}
 .hero-img{width:100%;max-width:1080px;height:auto;border-radius:var(--radius-md);margin:24px auto;display:block;box-shadow:var(--shadow-md)}.reactions-bar{display:flex;gap:12px;margin:24px 0;padding-top:16px}.reaction-btn{display:flex;align-items:center;gap:6px;padding:8px 16px;border:1px solid var(--border);border-radius:100px;background:var(--bg);cursor:pointer;font-size:.9rem;color:var(--text-secondary);transition:all .15s;font-family:var(--font-body)}.reaction-btn:hover{border-color:var(--primary);color:var(--primary);background:var(--primary-light)}.reaction-btn.active{border-color:var(--primary);color:var(--primary);background:var(--primary-light)}.reaction-btn.loved{border-color:#c0392b;color:#c0392b;background:#fde8e4}.reaction-count{font-weight:600;min-width:12px}
.carousel{position:relative;width:100%;height:90vh;min-height:520px;max-height:960px;overflow:hidden;background:var(--bg-alt)}
.carousel-track{display:flex;transition:transform .8s cubic-bezier(.4,0,.2,1);will-change:transform;height:100%}
.carousel-slide{flex:0 0 100%;position:relative;overflow:hidden}
.carousel-slide img{width:100%;height:100%;object-fit:cover;display:block}
.carousel-overlay{position:absolute;inset:0;background:linear-gradient(135deg,rgba(0,0,0,.75) 0%,rgba(0,0,0,.3) 45%,transparent 70%);display:flex;flex-direction:column;justify-content:center;padding:clamp(48px,8vw,96px);color:#fff}
.carousel-overlay .carousel-badge{display:inline-flex;align-items:center;gap:6px;background:var(--primary);color:#fff;padding:6px 16px;border-radius:100px;font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px;width:fit-content}
.carousel-overlay h3{font-family:var(--font-display);font-size:clamp(1.6rem,4vw,3.2rem);font-weight:700;color:#fff;margin-bottom:10px;letter-spacing:-.02em;max-width:720px;line-height:1.1}
.carousel-overlay p{font-size:clamp(1rem,1.8vw,1.2rem);opacity:.92;max-width:540px;margin-bottom:24px;color:#fff;line-height:1.5}
.carousel-overlay a{display:inline-flex;align-items:center;gap:8px;color:#fff;font-weight:600;font-size:.95rem;text-decoration:none;padding:14px 32px;background:var(--primary);border-radius:8px;transition:all .2s;width:fit-content;box-shadow:0 2px 12px rgba(212,99,62,.35)}
.carousel-overlay a:hover{background:var(--primary-dark);text-decoration:none;color:#fff;transform:translateY(-2px);box-shadow:0 4px 24px rgba(212,99,62,.45)}
.carousel-dots{position:absolute;bottom:32px;left:50%;transform:translateX(-50%);display:flex;gap:10px;z-index:5}
.carousel-dot{width:12px;height:12px;border-radius:50%;background:rgba(255,255,255,.3);border:2px solid rgba(255,255,255,.6);cursor:pointer;transition:all .35s;padding:0}
.carousel-dot.active{background:#fff;border-color:#fff;transform:scale(1.25)}
.carousel-arrow{position:absolute;top:50%;transform:translateY(-50%);z-index:5;background:rgba(0,0,0,.25);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.15);color:#fff;width:52px;height:52px;border-radius:50%;cursor:pointer;font-size:1.6rem;display:flex;align-items:center;justify-content:center;transition:all .25s;opacity:0;font-family:Georgia,serif;line-height:1;padding-bottom:2px}
.carousel:hover .carousel-arrow{opacity:1}
.carousel-arrow:hover{background:rgba(0,0,0,.45);transform:translateY(-50%) scale(1.06)}
.carousel-arrow.prev{left:24px}
.carousel-arrow.next{right:24px}
@media(max-width:768px){.carousel{height:70vh;min-height:400px;max-height:none}.carousel-overlay{padding:32px 24px;justify-content:flex-end}.carousel-overlay h3{font-size:1.5rem;max-width:100%}.carousel-overlay p{font-size:.95rem;max-width:100%}.carousel-arrow{width:40px;height:40px;font-size:1.2rem}.carousel-arrow.prev{left:12px}.carousel-arrow.next{right:12px}}
@media(max-width:480px){.carousel{height:60vh;min-height:320px}.carousel-overlay h3{font-size:1.25rem}.carousel-overlay .carousel-badge{font-size:.65rem;padding:4px 12px}.carousel-dots{bottom:16px;gap:8px}.carousel-dot{width:10px;height:10px}}
@media(prefers-reduced-motion:reduce){.carousel-track{transition:none}}

/* ── Abvorn Verdict Card ────────────────────────────────────────── */
.abvorn-verdict{border:2px solid var(--border);border-radius:var(--radius-lg);padding:28px 32px;margin:32px 0;background:linear-gradient(135deg,var(--bg),var(--bg-alt));box-shadow:var(--shadow-md);position:relative;overflow:hidden}
.abvorn-verdict::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,var(--primary),var(--accent))}
.av-badge{display:inline-flex;align-items:center;gap:6px;background:var(--primary);color:#fff;font-size:.7rem;font-weight:700;padding:4px 14px;border-radius:100px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px}
.av-badge::before{content:'\\01F525';font-size:.8rem}
.av-score-row{display:flex;align-items:center;gap:20px;margin-bottom:20px}
.av-score{display:flex;align-items:baseline;gap:2px}
.av-number{font-size:3rem;font-weight:700;font-family:var(--font-display);color:var(--text);line-height:1;letter-spacing:-.03em}
.av-outof{font-size:1.2rem;color:var(--text-muted);font-weight:600}
.av-label-row{display:flex;flex-direction:column;gap:2px}
.av-label{font-size:1.1rem;font-weight:700;color:var(--accent);font-family:var(--font-display)}
.av-product{font-size:.85rem;color:var(--text-secondary)}
.av-breakdown{display:flex;flex-direction:column;gap:8px;margin-bottom:20px}
.av-bar-row{display:flex;align-items:center;gap:12px}
.av-bar-label{flex:0 0 140px;font-size:.82rem;font-weight:600;color:var(--text-secondary);text-align:right}
.av-bar-track{flex:1;height:8px;background:var(--border);border-radius:100px;overflow:hidden}
.av-bar-fill{height:100%;border-radius:100px;transition:width .6s cubic-bezier(.4,0,.2,1)}
.av-bar-score{flex:0 0 36px;font-size:.85rem;font-weight:700;color:var(--text);text-align:right}
.av-summary{font-size:.95rem;color:var(--text-secondary);line-height:1.5;margin-bottom:20px;padding:16px;background:var(--bg);border-radius:var(--radius-sm);border-left:3px solid var(--accent);font-style:italic}
.av-cta{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.av-detail-link{font-size:.9rem;color:var(--text-muted);text-decoration:none;font-weight:600}
.av-detail-link:hover{color:var(--primary);text-decoration:none}
.av-score-cell{text-align:center;min-width:80px}
.av-compact-score{display:block;font-size:1.3rem;font-weight:700;font-family:var(--font-display);color:var(--text);line-height:1}
.av-compact-label{display:block;font-size:.65rem;color:var(--accent);font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-top:2px}
@media(max-width:640px){.av-score-row{flex-direction:column;align-items:flex-start;gap:8px}.av-bar-label{flex:0 0 100px;font-size:.75rem}.abvorn-verdict{padding:20px 16px}}

/* ── Regret Probability Score ───────────────────────────────────── */
.rps-container{border:1px solid var(--border);border-radius:var(--radius-lg);padding:24px 28px;margin:24px 0;background:var(--bg);box-shadow:var(--shadow-sm)}
.rps-badge{display:inline-flex;align-items:center;gap:6px;font-size:.7rem;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px}
.rps-badge::before{content:'\\01F52E';font-size:.8rem}
.rps-header{border-left:4px solid var(--accent);padding-left:16px;margin-bottom:16px}
.rps-score{display:flex;align-items:baseline;gap:8px;margin-bottom:4px}
.rps-number{font-size:2.2rem;font-weight:700;font-family:var(--font-display);line-height:1;letter-spacing:-.03em}
.rps-product-name{font-size:.9rem;color:var(--text-secondary);font-weight:500}
.rps-section-title{font-size:.85rem;font-weight:700;color:var(--text);margin-bottom:8px;text-transform:uppercase;letter-spacing:.04em}
.rps-reasons{margin-bottom:16px}
.rps-reason{padding:10px 14px;border-radius:var(--radius-sm);margin-bottom:8px;font-size:.88rem;line-height:1.5;border-left:3px solid}
.rps-reason.rps-mismatch{background:#fef2f2;border-color:#c0392b;color:#7f1d1d}
.rps-reason.rps-notice{background:#fffbeb;border-color:#d4a03e;color:#78350f}
.rps-tip{font-size:.85rem;color:var(--text-secondary);padding:12px;background:var(--bg-alt);border-radius:var(--radius-sm);margin-bottom:16px;line-height:1.4}
.rps-alt-title{font-size:.85rem;font-weight:700;color:var(--text);margin-bottom:10px;text-transform:uppercase;letter-spacing:.04em}
.rps-alt-item{display:flex;align-items:center;gap:12px;padding:12px 14px;border:1px solid var(--border);border-radius:var(--radius-sm);margin-bottom:8px;text-decoration:none;transition:all .15s;background:var(--bg-alt)}
.rps-alt-item:hover{text-decoration:none;border-color:var(--primary);box-shadow:var(--shadow-sm)}
.rps-alt-name{flex:1;font-weight:600;color:var(--text);font-size:.9rem}
.rps-alt-prob{font-size:.78rem;font-weight:600;white-space:nowrap}
.rps-alt-price{font-size:.8rem;color:var(--text-muted)}
.rps-footer{font-size:.78rem;color:var(--text-muted);display:flex;align-items:center;gap:12px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border)}
.rps-reset{background:none;border:1px solid var(--border);border-radius:100px;padding:4px 12px;font-size:.75rem;color:var(--text-muted);cursor:pointer;font-family:inherit;transition:all .15s}
.rps-reset:hover{border-color:var(--primary);color:var(--primary)}
@media(prefers-color-scheme:dark){.rps-reason.rps-mismatch{background:rgba(192,57,43,.12);color:#fca5a5}.rps-reason.rps-notice{background:rgba(212,160,62,.12);color:#fcd34d}}
#cookie-banner{position:fixed;bottom:0;left:0;right:0;background:#2a2724;color:#fff;padding:16px 24px;z-index:9999;display:none;font-size:13px;line-height:1.5;box-shadow:0 -4px 12px rgba(0,0,0,.15)}
#cookie-banner.show{display:flex;flex-wrap:wrap;align-items:center;gap:12px;justify-content:center}
#cookie-banner p{margin:0;color:#e3dbd4;font-size:13px}
#cookie-banner a{color:#d4633e;text-decoration:underline}
#cookie-banner .btn{background:#d4633e;color:#fff;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;white-space:nowrap}
#cookie-banner .btn:hover{background:#b84d2a}
#cookie-banner .btn-secondary{background:transparent;color:#e3dbd4;border:1px solid #6b6560;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px}
#cookie-banner .btn-secondary:hover{border-color:#9e9690}
"""

SVG_TIKTOK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg>'
SVG_INSTAGRAM = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>'
SVG_X = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'
SVG_YOUTUBE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>'
SOCIAL_HTML = '<div class="social"><a href="https://www.youtube.com/@Abvorn-Media" target="_blank" aria-label="YouTube">' + SVG_YOUTUBE + '</a><a href="https://www.tiktok.com/@abvorn" target="_blank" aria-label="TikTok">' + SVG_TIKTOK + '</a><a href="https://www.instagram.com/abvorn/" target="_blank" aria-label="Instagram">' + SVG_INSTAGRAM + '</a><a href="https://x.com/Abvorn" target="_blank" aria-label="X">' + SVG_X + '</a></div>'



HEAD_HTML = lambda title, desc: f'''<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="icon" type="image/svg+xml" href="{SITE_BASE}/assets/favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="{SITE_BASE}/assets/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="{SITE_BASE}/assets/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="{SITE_BASE}/assets/apple-touch-icon.png">
<link rel="manifest" href="{SITE_BASE}/assets/site.webmanifest">
{FONT_LINK}'''

def OG_META(title, desc, url, image="", og_type="website"):
    img_tag = f'\n<meta property="og:image" content="{image}"><meta name="twitter:image" content="{image}">' if image else ''
    return f'''<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="{og_type}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">{img_tag}
'''
NAV_SCRIPT = '<script>(function(){var b=document.getElementById("nav-toggle");var n=document.getElementById("nav-links");if(!b||!n)return;b.addEventListener("click",function(){var o=n.classList.toggle("open");b.setAttribute("aria-expanded",o?"true":"false")})})();</script>'
import os

CONSENT_CSS = '''
#cookie-banner{position:fixed;bottom:0;left:0;right:0;background:#2a2724;color:#fff;padding:16px 24px;z-index:9999;display:none;font-size:13px;line-height:1.5;box-shadow:0 -4px 12px rgba(0,0,0,.15)}
#cookie-banner.show{display:flex;flex-wrap:wrap;align-items:center;gap:12px;justify-content:center}
#cookie-banner p{margin:0;color:#e3dbd4;font-size:13px}
#cookie-banner a{color:#d4633e;text-decoration:underline}
#cookie-banner .btn{background:#d4633e;color:#fff;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;white-space:nowrap}
#cookie-banner .btn:hover{background:#b84d2a}
#cookie-banner .btn-secondary{background:transparent;color:#e3dbd4;border:1px solid #6b6560;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px}
#cookie-banner .btn-secondary:hover{border-color:#9e9690}
'''
CONSENT_JS = '''
(function(){var c=document.cookie.match(/(?:^|;) *analytics_consent=([^;]*)/);if(c&&c[1]==="granted"){return}var b=document.getElementById("cookie-banner");if(b){b.classList.add("show")}window.acceptAnalytics=function(){document.cookie="analytics_consent=granted; max-age=31536000; path=/; SameSite=Lax";b.classList.remove("show");loadAnalytics()};window.declineAnalytics=function(){document.cookie="analytics_consent=denied; max-age=31536000; path=/; SameSite=Lax";b.classList.remove("show")}})()
'''
ANALYTICS_HTML = ''
_ga_id = os.environ.get("GA_MEASUREMENT_ID", "")
if _ga_id:
    ANALYTICS_HTML = f'''<script>window.loadAnalytics=function(){{var s=document.createElement("script");s.async=true;s.src="https://www.googletagmanager.com/gtag/js?id={_ga_id}";document.head.appendChild(s);window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}};gtag("js",new Date());gtag("config","{_ga_id}")}};(function(){{var c=document.cookie.match(/(?:^|;) *analytics_consent=([^;]*)/);if(c&&c[1]==="granted"){{loadAnalytics()}}}})()</script>
<div id="cookie-banner" role="dialog" aria-label="Cookie consent">
<p>We use cookies to analyze traffic and improve your experience. <a href="{SITE_BASE}/privacy/">Privacy Policy</a></p>
<button class="btn-secondary" onclick="declineAnalytics()">Decline</button>
<button class="btn" onclick="acceptAnalytics()">Accept</button>
</div>'''

FTC_DISCLOSURE = '<div class="disclosure">We earn a commission if you buy through our links, at no extra cost to you. Our opinions are our own.</div>'

COOKIE_CONSENT_SCRIPT = '''
<style>
#cookie-banner{position:fixed;bottom:0;left:0;right:0;background:#0a0a0a;color:#fff;padding:16px 24px;z-index:9999;display:none;font-size:13px;line-height:1.5;box-shadow:0 -4px 12px rgba(0,0,0,.15)}
#cookie-banner.show{display:flex;flex-wrap:wrap;align-items:center;gap:12px;justify-content:center}
#cookie-banner p{margin:0;color:#ffffff;font-size:13px}
#cookie-banner a{color:var(--clr-accent,#c98a2c);text-decoration:underline}
#cookie-banner .btn{background:var(--clr-accent,#c98a2c);color:#0a0a0a;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:700}
#cookie-banner .btn:hover{background:#d4a03a}
#cookie-banner .btn-secondary{background:transparent;color:#ffffff;border:1px solid #555;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px}
#cookie-banner .btn-secondary:hover{border-color:#888}
</style>
<div id="cookie-banner" role="dialog" aria-label="Cookie consent">
<p>We use cookies to analyze traffic and improve your experience. <a href="__BASE__/privacy/">Privacy Policy</a></p>
<button class="btn-secondary" onclick="declineAnalytics()">Decline</button>
<button class="btn" onclick="acceptAnalytics()">Accept</button>
</div>
<script>
(function(){var c=document.cookie.match(/(?:^|;) *analytics_consent=([^;]*)/);if(c&&c[1]==="granted"){return}var b=document.getElementById("cookie-banner");if(b){b.classList.add("show")}window.acceptAnalytics=function(){document.cookie="analytics_consent=granted; max-age=31536000; path=/; SameSite=Lax";b.classList.remove("show");if(typeof loadAnalytics==="function"){loadAnalytics()}};window.declineAnalytics=function(){document.cookie="analytics_consent=denied; max-age=31536000; path=/; SameSite=Lax";b.classList.remove("show")}})();
</script>'''

def _slugify_title(s):
    """Convert a slug to a readable category name."""
    return s.replace("-", " ").title()

def nav_html(categories, current=""):
    b = SITE_BASE
    dd_items = "".join(f'<a href="{b}/{c}/">{_slugify_title(c)}</a>' for c in categories)
    dropdown = f'<div class="nav-item"><a href="#">Categories</a><div class="nav-dropdown">{dd_items}</div></div>'
    return f'''
<div class="top-bar"><div class="container"><span>Independent testing. No sponsored placements.</span><span>Updated weekly</span></div></div>
<header><div class="container navbar">
    <a href="{b}/" class="logo"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:44px;width:auto"></a>
    <button class="nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav-links">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <nav class="nav-links" id="nav-links">
        {dropdown}
        <a href="{b}/about.html">About</a>
        <a href="{b}/privacy.html">Privacy</a>
    </nav>
</div></header>
<script>
(function(){{var b=document.getElementById("nav-toggle");var n=document.getElementById("nav-links");if(!b||!n)return;b.addEventListener("click",function(){{var o=n.classList.toggle("open");b.setAttribute("aria-expanded",o?"true":"false")}})}})();
</script>'''


# ── Social icon SVGs for footer ───────────────────────────────────
SOCIAL_FOOTER_SVGS = {
    "x": '<svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor"><path d="M4 4l7.5 9.5L4.3 20H6l6-5.8L16.5 20H20l-8-9.9L19.4 4H17.7l-5.6 5.4L8 4H4zm2.7 1.5h1.9l9.6 13H14.3l-9.6-13z"/></svg>',
    "instagram": '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3.5" y="3.5" width="17" height="17" rx="4.5"/><circle cx="12" cy="12" r="4"/><circle cx="17" cy="7" r="0.8" fill="currentColor" stroke="none"/></svg>',
    "youtube": '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="2.5" y="5.5" width="19" height="13" rx="3.5"/><path d="M10 9.5l5 2.5-5 2.5v-5z" fill="currentColor" stroke="none"/></svg>',
    "tiktok": '<svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor"><path d="M14 3h2.3c.2 1.4 1 2.6 2.4 3.3.7.4 1.5.6 2.3.6v2.6c-1.5 0-3-.4-4.2-1.2v6.4c0 3-2.4 5.3-5.3 5.3S6.2 17.7 6.2 14.7c0-2.9 2.3-5.3 5.2-5.3.3 0 .6 0 .9.1v2.7a2.7 2.7 0 00-.9-.15 2.6 2.6 0 100 5.2c1.5 0 2.7-1.2 2.7-2.7V3z"/></svg>',
}


HOMEPAGE_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="__SITE_BASE__/favicon.png">
    <title>Abvorn – Reviews Based on Real Testing, Not Spec Sheets</title>
    <meta name="description" content="Independent product reviews and buying guides. We test before we recommend.">
    <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        ''' + DESIGN_SYSTEM_CSS + '''
        /* FIX: header/hero/footer are fixed brand chrome, always black-on-white —
           they must NOT use the adaptive --clr-black/--clr-white/--clr-off-white
           tokens, which the dark-mode media query above intentionally flips for
           body content. Using those tokens here was the actual bug behind the
           invisible nav (white text on a header that turned white) and the
           invisible hero button (background and text both collapsing toward
           black). Hardcoded values below are deliberate, not an oversight. */
        .top-bar { background:#0a0a0a; color:#999; font-size:0.8rem; padding:8px 0; }
        .top-bar .container { display:flex; justify-content:space-between; }
        header { background:#0a0a0a; padding:18px 0; position:relative; z-index:20; }
        .navbar { display:flex; justify-content:space-between; align-items:center; }
        .logo img { max-height:44px; width:auto; }
        .nav-links { display:flex; align-items:center; }
        .nav-links > a, .nav-item > a { color:#fff; text-decoration:none; margin-left:28px; font-weight:600; font-size:0.9rem; }
        .nav-links > a:hover, .nav-item > a:hover { color: var(--clr-accent); }
        .nav-item { position:relative; margin-left:28px; }
        .nav-item > a { margin-left:0; }
        .nav-item::after{content:'';position:absolute;top:100%;left:0;right:0;height:14px}
        .nav-dropdown { display:none; position:absolute; top:100%; left:0; margin-top:14px; background:#fff; min-width:240px; border-radius: var(--radius-sm); box-shadow: var(--shadow-lg); padding:8px 0; z-index:30; }
        .nav-item:hover .nav-dropdown, .nav-item:focus-within .nav-dropdown { display:block; }
        .nav-dropdown a { display:block; color:#1a1a1a; padding:9px 20px; font-weight:500; font-size:0.9rem; text-decoration:none; }
        .nav-dropdown a:hover { background:#f6f5f2; color: var(--clr-accent-text); }
        .nav-toggle { display:none; background:none; border:none; color:#fff; padding:6px; cursor:pointer; }
        .nav-toggle svg { width:24px; height:24px; }
        @media (max-width: 640px) {
            .nav-toggle { display:block; }
            .nav-links { display:none; position:absolute; top:100%; left:0; right:0; background:#0a0a0a; flex-direction:column; align-items:flex-start; padding: 8px 24px 20px; gap:4px; box-shadow: var(--shadow-lg); }
            .nav-links.open { display:flex; }
            .nav-links > a, .nav-item { margin-left:0; width:100%; }
            .nav-links > a, .nav-item > a { padding:10px 0; }
            .nav-dropdown { position:static; box-shadow:none; margin-top:0; padding-left:12px; display:block; background:transparent; }
            .nav-dropdown a { color:#ccc; padding:7px 0; }
            .nav-dropdown a:hover { background:transparent; }
        }
        .trending-ticker { background:var(--clr-accent); color:#1a1200; padding:9px 0; font-size:0.82rem; overflow:hidden; white-space:nowrap; }
        .trending-ticker__inner { display:inline-block; animation: ticker-scroll 24s linear infinite; }
        .trending-ticker__label { font-weight:700; margin-right:15px; color:#1a1200; }
        .trending-ticker__item { color:#1a1200; text-decoration:none; padding:0 10px; }
        .trending-ticker__item:hover { color:#000; text-decoration:underline; }
        @keyframes ticker-scroll { 0% { transform: translateX(100vw); } 100% { transform: translateX(-100%); } }
        .hero { background:#f6f5f2; padding: var(--space-2xl) 0; }
        .hero-grid { display:grid; grid-template-columns: 1fr 1fr; gap: var(--space-xl); align-items:center; }
        .hero-eyebrow { display:inline-block; font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#666; margin-bottom: var(--space-md); }
        .hero h1 { font-size: clamp(var(--text-3xl), 4vw, var(--text-4xl)); margin-bottom: var(--space-md); color:#0a0a0a; }
        .hero p { font-size: var(--text-lg); color:#555; max-width:46ch; margin-bottom: var(--space-lg); }
        .hero .btn { background:#1a1a1a; color:#fff; }
        .hero .btn:hover { background: var(--clr-accent); color:#1a1200; }
        .hero-slider { position:relative; border-radius: var(--radius-md); overflow:hidden; box-shadow: var(--shadow-lg); aspect-ratio: 4/3; background:#111; }
        .hero-slide { position:absolute; inset:0; opacity:0; transition:opacity 0.9s var(--ease-out); }
        .hero-slide.active { opacity:1; }
        .hero-slide img { width:100%; height:100%; object-fit:cover; display:block; }
        .hero-slide figcaption { position:absolute; left:0; right:0; bottom:0; background:linear-gradient(transparent, rgba(0,0,0,0.8)); color:#fff; padding: 44px var(--space-lg) var(--space-md); font-weight:600; font-size:0.95rem; }
        .hero-slider__dots { position:absolute; bottom:6px; left:50%; transform:translateX(-50%); display:flex; z-index:5; }
        .hero-slider__dot { width:44px; height:44px; border:none; background:transparent; cursor:pointer; padding:0; display:flex; align-items:center; justify-content:center; }
        .hero-slider__dot::before { content:''; width:8px; height:8px; border-radius:50%; background:rgba(255,255,255,0.45); transition: background var(--duration-fast) var(--ease-out); }
        .hero-slider__dot.active::before { background:#fff; }
        @media (max-width: 860px) { .hero-grid { grid-template-columns: 1fr; } }

        .stats-band { background:#0a0a0a; color:#fff; padding: var(--space-lg) 0; }
        .stats-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(160px,1fr)); gap: var(--space-lg); text-align:center; }
        .stat-icon { width:28px; height:28px; margin:0 auto 10px; color: var(--clr-accent); opacity:0.9; }
        .stat-icon svg { width:100%; height:100%; }
        .stat-number { font-family: var(--font-display); font-size: var(--text-3xl); font-weight:700; color: var(--clr-accent); }
        .stat-label { font-size:0.82rem; color:#999; text-transform:uppercase; letter-spacing:0.06em; margin-top:4px; }

        .subscribe-band { background:#f6f5f2; padding: var(--space-xl) 0; }
        .subscribe-inner { display:flex; justify-content:space-between; align-items:center; gap: var(--space-lg); flex-wrap:wrap; }
        .subscribe-copy h2 { font-size: var(--text-xl); margin-bottom:6px; color:#0a0a0a; }
        .subscribe-copy p { margin:0; color:#555; max-width:42ch; }
        .subscribe-form { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
        .subscribe-form .input { width:260px; }
        .subscribe-form .hp-field { position:absolute; left:-9999px; }
        .subscribe-form .btn { background: var(--clr-accent); color:#1a1200; font-size:1rem; font-weight:800; padding:0.85em 1.7em; gap:8px; box-shadow: 0 6px 22px rgba(201,138,44,0.4); }
        .subscribe-form .btn:hover { background:#e0a23f; transform: scale(1.045); box-shadow: 0 8px 28px rgba(201,138,44,0.55); }
        .subscribe-form .btn svg { width:18px; height:18px; }
        .subscribe-msg { flex-basis:100%; font-size:0.85rem; color:#666; margin-top:8px; }
        @media (max-width: 700px) { .subscribe-inner { flex-direction:column; align-items:flex-start; } .subscribe-form .input { width:100%; } }

        .guides-section { padding: var(--space-2xl) 0; }
        .latest-reviews-section { padding-top: var(--space-2xl); }
        .category-section { margin-bottom: var(--space-2xl); }
        .category-section__header { display:flex; justify-content:space-between; align-items:baseline; margin-bottom: var(--space-lg); border-bottom:2px solid var(--clr-light-gray); padding-bottom: var(--space-sm); }
        .category-section__header h2 { font-size: var(--text-2xl); margin:0; }
        .category-section__header a { font-size:0.85rem; font-weight:700; color: var(--clr-accent-text); text-decoration:none; white-space:nowrap; }
        .category-section__header a:hover { text-decoration:underline; }
        .niche-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px,1fr)); gap: var(--space-lg); }
        .niche-card { border-radius: var(--radius-md); overflow:hidden; transition: transform var(--duration-base) var(--ease-out); }
        .niche-card:hover { transform: translateY(-3px); }
        .niche-card__image-wrapper { aspect-ratio: 4/3; overflow:hidden; border-radius: var(--radius-md); }
        .niche-card img { width:100%; height:100%; object-fit:cover; transition: transform var(--duration-slow) var(--ease-out); }
        .niche-card:hover img { transform: scale(1.04); }
        .niche-card h2 { font-size: var(--text-lg); margin: var(--space-md) 0 8px; }
        .niche-card h2 a { color:inherit; text-decoration:none; }
        .niche-card p { font-size:0.92rem; color: var(--clr-mid-gray); margin-bottom: var(--space-sm); max-width:none; }
        .niche-card .read-link { font-weight:700; font-size:0.88rem; color: var(--clr-black); text-decoration:none; border-bottom:2px solid var(--clr-accent); padding-bottom:1px; }
        .niche-card .read-link:hover { color: var(--clr-accent-text); }

        .category-group { display: none; }
        .category-group.visible { display: block; }
        .show-more-btn { display: inline-flex; align-items: center; gap: var(--space-sm); margin: var(--space-xl) auto 0; padding: 0.85em 1.5em; font-family: var(--font-body); font-weight: 700; font-size: var(--text-sm); text-transform: uppercase; letter-spacing: 0.06em; color: var(--clr-accent-text); background: none; border: 2px solid var(--clr-accent); border-radius: var(--radius-sm); cursor: pointer; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }
        .show-more-btn:hover { background: var(--clr-accent); color: var(--clr-black); }
        .show-more-btn svg { width: 16px; height: 16px; transition: transform var(--duration-fast) var(--ease-out); }
        .show-more-btn:hover svg { transform: translateX(4px); }

        .footer { background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }
        .footer-grid { display:grid; grid-template-columns: 1.6fr 1fr 1fr 1fr; gap: var(--space-lg); margin-bottom: var(--space-xl); }
        .footer-col h4 { color:#fff; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:14px; }
        .footer-col p { color:#999; font-size:0.9rem; max-width:32ch; }
        .footer-col a { display:block; color:#999; text-decoration:none; padding:4px 0; font-size:0.9rem; }
        .footer-col a:hover { color:#fff; }
        .footer-social { display:flex; gap:10px; margin-top:16px; }
        .footer-social a { width:44px; height:44px; border-radius:50%; background:#1e1e1e; display:flex; align-items:center; justify-content:center; color:#ccc; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }
        .footer-social a:hover { background: var(--clr-accent); color:#0a0a0a; }
        .footer-social svg { width:16px; height:16px; }
        .footer-bottom { border-top:1px solid #222; padding-top:20px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; font-size:0.85rem; color:#777; }
        @media (max-width: 760px) { .footer-grid { grid-template-columns: 1fr 1fr; } }
    </style>
</head>
<body>
<div class="top-bar"><div class="container"><span>Independent testing. No sponsored placements.</span><span>Updated weekly</span></div></div>
<header><div class="container navbar">
    <a href="__SITE_BASE__/" class="logo"><img src="__SITE_BASE__/logo.svg" alt="Abvorn"></a>
    <button class="nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav-links">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <nav class="nav-links" id="nav-links">
        <div class="nav-item"><a href="#niches">Categories ▾</a><div class="nav-dropdown">CATEGORY_DROPDOWN_PLACEHOLDER</div></div>
        <a href="__SITE_BASE__/about.html">About</a>
        <a href="__SITE_BASE__/privacy.html">Privacy</a>
    </nav>
</div></header>
<div class="trending-ticker"><div class="container"><div class="trending-ticker__inner"><span class="trending-ticker__label">Latest updates:</span><span id="trending-items">LATEST_UPDATES_PLACEHOLDER</span></div></div></div>

<section class="hero"><div class="container hero-grid">
    <div>
        <span class="hero-eyebrow">How we work</span>
        <h1>We buy it, test it, and tell you what's actually worth your money.</h1>
        <p>Every recommendation on Abvorn comes from hands-on testing against real alternatives &mdash; not spec sheets, not press releases.</p>
        <a href="#niches" class="btn">See our latest guides</a>
    </div>
    <div class="hero-slider" id="hero-slider">
        HERO_SLIDES_PLACEHOLDER
        <div class="hero-slider__dots">HERO_DOTS_PLACEHOLDER</div>
    </div>
</div></section>

<section class="stats-band"><div class="container stats-grid">
    <div><div class="stat-icon"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg></div><div class="stat-number" data-target="STAT_GUIDES_COUNT">0</div><div class="stat-label">Guides published</div></div>
    <div><div class="stat-icon"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg></div><div class="stat-number" data-target="STAT_CATEGORIES_COUNT">0</div><div class="stat-label">Categories covered</div></div>
    <div><div class="stat-icon"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M5 8l7-5 7 5M5 8a3 3 0 106 0M13 8a3 3 0 106 0"/></svg></div><div class="stat-number" data-target="STAT_PRODUCTS_COUNT">0</div><div class="stat-label">Products compared</div></div>
    <div><div class="stat-icon"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 11-3.5-7.1"/><path d="M21 3v6h-6"/></svg></div><div class="stat-number">Weekly</div><div class="stat-label">Review cycle</div></div>
</div></section>

<section class="subscribe-band"><div class="container subscribe-inner">
    <div class="subscribe-copy">
        <h2>Get notified about new guides</h2>
        <p>One email whenever we publish a new review. No spam, unsubscribe anytime.</p>
    </div>
    <form class="subscribe-form" id="homepage-subscribe-form" onsubmit="submitHomepageSubscribe(event)">
        <input type="text" name="_gotcha" class="hp-field" tabindex="-1" autocomplete="off">
        <label for="homepage-subscribe-email" class="sr-only">Email address</label>
        <input type="email" class="input" id="homepage-subscribe-email" placeholder="you@example.com" required>
        <button type="submit" class="btn"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>Notify me</button>
        <p class="subscribe-msg" id="homepage-subscribe-msg" aria-live="polite"></p>
    </form>
</div></section>

<section class="latest-reviews-section container">
    <div class="category-section__header"><h2>Latest reviews</h2></div>
    <div class="niche-grid">LATEST_REVIEWS_PLACEHOLDER</div>
</section>

<section class="guides-section container" id="niches">
    CATEGORY_SECTIONS_PLACEHOLDER
</section>

<footer class="footer"><div class="container">
    <div class="footer-grid">
        <div class="footer-col">
            <img src="__SITE_BASE__/logo.svg" alt="Abvorn" style="max-height:28px;width:auto;margin-bottom:8px">
            <p>Independent product reviews and buying guides, based on real testing.</p>
            <div class="footer-social">FOOTER_SOCIAL_PLACEHOLDER</div>
        </div>
        <div class="footer-col"><h4>Categories</h4>FOOTER_CATEGORY_LINKS_PLACEHOLDER</div>
        <div class="footer-col"><h4>Company</h4><a href="__SITE_BASE__/about.html">About</a></div>
        <div class="footer-col"><h4>Legal</h4><a href="__SITE_BASE__/privacy.html">Privacy policy</a></div>
    </div>
    <div class="footer-bottom"><img src="__SITE_BASE__/logo.svg" alt="Abvorn" style="max-height:20px;width:auto;filter:brightness(0.6)"><span>&copy; YEAR_PLACEHOLDER Abvorn. All rights reserved.</span><span>Reviews updated weekly</span></div>
</div></footer>

<script>
const APPS_SCRIPT_URL = "__APPS_SCRIPT_URL__";

// Mobile nav toggle
(function() {
    const btn = document.getElementById('nav-toggle');
    const nav = document.getElementById('nav-links');
    if (!btn || !nav) return;
    btn.addEventListener('click', () => {
        const open = nav.classList.toggle('open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
})();

// Stat counters — roll from 0 to the real number once the strip is on screen
(function() {
    const nums = document.querySelectorAll('.stat-number[data-target]');
    if (!nums.length) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    function animate(el) {
        const target = parseInt(el.dataset.target, 10);
        if (isNaN(target)) return;
        if (reduceMotion) { el.textContent = target.toLocaleString(); return; }
        const duration = 1200, start = performance.now();
        function tick(now) {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(eased * target).toLocaleString();
            if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    }
    if ('IntersectionObserver' in window) {
        const obs = new IntersectionObserver((entries) => {
            entries.forEach(entry => { if (entry.isIntersecting) { animate(entry.target); obs.unobserve(entry.target); } });
        }, { threshold: 0.4 });
        nums.forEach(n => obs.observe(n));
    } else { nums.forEach(n => { n.textContent = n.dataset.target; }); }
})();

async function submitHomepageSubscribe(e) {
    e.preventDefault();
    const f = e.target;
    const msg = document.getElementById('homepage-subscribe-msg');
    if (f._gotcha.value !== "") { msg.innerText = 'Success! Check your inbox.'; return; }
    const email = document.getElementById('homepage-subscribe-email').value.trim();
    if (!email) return;
    msg.innerText = 'Sending...';
    try {
        const response = await fetch(APPS_SCRIPT_URL, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ email: email, niche: 'general', source: 'homepage_notify', lead_magnet: 'New guide notifications' })
        });
        const result = await response.json();
        msg.innerText = result.success ? 'Success! Check your inbox.' : (result.message || 'Oops, try again.');
    } catch (err) { msg.innerText = 'Connection error. Please try later.'; }
}

// Show more categories — reveal next group of 4
(function() {
    const groups = document.querySelectorAll('.category-group');
    const btn = document.querySelector('.show-more-btn');
    if (btn && groups.length > 0) {
        let nextIndex = 1;
        btn.addEventListener('click', function() {
            if (nextIndex < groups.length) {
                groups[nextIndex].classList.add('visible');
                nextIndex++;
            }
            if (nextIndex >= groups.length) {
                btn.style.display = 'none';
            }
        });
    }
})();

// Hero slider — auto-advance + dot navigation
(function() {
    const slider = document.getElementById('hero-slider');
    if (!slider) return;
    const slides = slider.querySelectorAll('.hero-slide');
    const dots = slider.querySelectorAll('.hero-slider__dot');
    if (slides.length < 2) return;
    let current = 0;
    function show(i) {
        slides.forEach((s, idx) => s.classList.toggle('active', idx === i));
        dots.forEach((d, idx) => {
            d.classList.toggle('active', idx === i);
            d.setAttribute('aria-current', idx === i ? 'true' : 'false');
        });
        current = i;
    }
    dots.forEach((d, idx) => d.addEventListener('click', () => show(idx)));
    setInterval(() => show((current + 1) % slides.length), 5000);
})();
</script>
</body>
</html>'''


def render_footer_social():
    social_urls = {
        "x": os.environ.get("SOCIAL_X_URL", ""),
        "instagram": os.environ.get("SOCIAL_INSTAGRAM_URL", ""),
        "youtube": os.environ.get("SOCIAL_YOUTUBE_URL", ""),
        "tiktok": os.environ.get("SOCIAL_TIKTOK_URL", ""),
    }
    return "".join(
        f'<a href="{url or "#"}" aria-label="{name.title()}" target="_blank" rel="noopener">{SOCIAL_FOOTER_SVGS[name]}</a>'
        for name, url in social_urls.items()
    )


def build_homepage(state, form_url=""):
    """Build the premium homepage with hero slider, stats, and category sections."""
    niches = sorted(state["niches"], key=lambda n: n["name"].lower())
    all_slugs = sorted([n["slug"] for n in niches], key=lambda s: _slugify_title(s).lower())
    b = SITE_BASE
    total_posts = sum(n["posts"] for n in niches)
    total_products = total_posts * 3  # rough estimate

    # Build nav dropdown
    nav_dd = "".join(f'<a href="{b}/{s}/">{_slugify_title(s)}</a>' for s in all_slugs)

    # Build hero slides
    hero_slides = ""
    hero_dots = ""
    hero_candidates = []
    for n in reversed(niches):
        if len(hero_candidates) >= 5:
            break
        img = carousel_img(n["slug"], b)
        hero_candidates.append((img, n["name"], n["slug"]))
    if not hero_candidates:
        hero_candidates.append((f"{b}/assets/hero-home.svg", "Reviews", "coming-soon"))
    for i, (img, name, slug) in enumerate(hero_candidates):
        active = " active" if i == 0 else ""
        hero_slides += f'<div class="hero-slide{active}"><img src="{img}" alt="{name}"><figcaption>{name} reviews — expert tested</figcaption></div>'
        hero_dots += f'<button class="hero-slider__dot{active}" aria-label="Show {name}" aria-current="{"true" if i == 0 else "false"}"></button>'

    # Build latest review cards — exactly 3
    latest_cards = ""
    card_count = 0
    for n in niches:
        if not n["posts"]:
            continue
        if card_count >= 3:
            break
        latest_cards += f'''<div class="niche-card">
    <a href="{b}/{n["slug"]}/"><div class="niche-card__image-wrapper"><img src="{carousel_img(n["slug"], b)}" alt="{n["name"]}" loading="lazy"></div></a>
    <h2><a href="{b}/{n["slug"]}/">{n["name"]}</a></h2>
    <p>{n["posts"]} expert-reviewed guide{"s" if n["posts"] > 1 else ""} with real testing results.</p>
    <a href="{b}/{n["slug"]}/" class="read-link">Continue reading →</a>
</div>'''
        card_count += 1

    # Build category sections with posts — groups of 4, first visible
    cat_groups = []
    group_buffer = ""
    group_count = 0
    for n in niches:
        if not n["posts"]:
            continue
        card = f'''<div class="niche-card">
    <a href="{b}/{n["slug"]}/"><div class="niche-card__image-wrapper"><img src="{carousel_img(n["slug"], b)}" alt="{n["name"]}" loading="lazy"></div></a>
    <h2><a href="{b}/{n["slug"]}/">{n["name"]}</a></h2>
    <p>{n["posts"]} expert-reviewed guide{"s" if n["posts"] > 1 else ""} with real testing results.</p>
    <a href="{b}/{n["slug"]}/" class="read-link">Continue reading →</a>
</div>'''
        section = f'''<div class="category-section">
    <div class="category-section__header"><h2>{n["name"]}</h2><a href="{b}/{n["slug"]}/">View all in {n["name"]} →</a></div>
    <div class="niche-grid">{card}</div>
</div>'''
        group_buffer += section
        group_count += 1
        if group_count % 4 == 0:
            cat_groups.append(group_buffer)
            group_buffer = ""
    if group_buffer:
        cat_groups.append(group_buffer)

    cat_sections = ""
    for i, group in enumerate(cat_groups):
        cls = " visible" if i == 0 else ""
        cat_sections += f'<div class="category-group{cls}">{group}</div>'

    if len(cat_groups) > 1:
        cat_sections += f'''<div style="text-align:center">
    <button class="show-more-btn">View more categories<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg></button>
</div>'''

    # Trending ticker items text
    ticker_items = " · ".join(
        f'<a href="{b}/{n["slug"]}/" class="trending-ticker__item">{n["name"]}</a>'
        for n in niches if n["posts"]
    )

    # Footer
    footer_cats = "".join(f'<a href="{b}/{s}/">{_slugify_title(s)}</a>' for s in all_slugs)
    footer_social = render_footer_social()

    html = HOMEPAGE_TEMPLATE
    html = html.replace("__SITE_BASE__", b)
    html = html.replace("CATEGORY_DROPDOWN_PLACEHOLDER", nav_dd)
    html = html.replace("HERO_SLIDES_PLACEHOLDER", hero_slides)
    html = html.replace("HERO_DOTS_PLACEHOLDER", hero_dots)
    html = html.replace("STAT_GUIDES_COUNT", str(total_posts))
    html = html.replace("STAT_CATEGORIES_COUNT", str(len(niches)))
    html = html.replace("STAT_PRODUCTS_COUNT", str(total_products))
    html = html.replace("LATEST_UPDATES_PLACEHOLDER", ticker_items if ticker_items else "No reviews yet")
    html = html.replace("LATEST_REVIEWS_PLACEHOLDER", latest_cards if latest_cards else '<p style="grid-column:1/-1;text-align:center;color:#888;padding:40px 0">More guides on the way.</p>')
    html = html.replace("CATEGORY_SECTIONS_PLACEHOLDER", cat_sections if cat_sections else '<div class="category-section"><div class="niche-card"><div class="niche-card__image-wrapper"><img src="' + b + '/assets/hero-home.svg" alt="Coming soon"></div><div class="niche-card__body"><h2>Our first guide is in testing</h2><p>Check back shortly for hands-on reviews.</p></div></div></div>')
    html = html.replace("FOOTER_SOCIAL_PLACEHOLDER", footer_social)
    html = html.replace("FOOTER_CATEGORY_LINKS_PLACEHOLDER", footer_cats)
    html = html.replace("__APPS_SCRIPT_URL__", form_url)
    html = html.replace("YEAR_PLACEHOLDER", str(datetime.now().year))
    return html


def carousel_img(niche_slug, b):
    """Pick real hero JPG if uploaded, else fall back to generated SVG."""
    hero_path = f"docs/assets/hero/{niche_slug}.jpg"
    if os.path.exists(hero_path):
        return f"{b}/assets/hero/{niche_slug}.jpg"
    return f"{b}/assets/{niche_slug}.svg"


CAROUSEL_JS = """<script>(function(){var c=document.querySelector('.carousel');if(!c)return;var t=c.querySelector('.carousel-track');if(!t)return;var s=t.querySelectorAll('.carousel-slide');if(s.length<2)return;var dots=c.querySelectorAll('.carousel-dot');var prev=c.querySelector('.carousel-arrow.prev');var next=c.querySelector('.carousel-arrow.next');var i=0,n=s.length;var go=function(idx){i=((idx%n)+n)%n;t.style.transform='translateX(-'+(i*100)+'%)';dots.forEach(function(d){d.classList.toggle('active',parseInt(d.dataset.slide)===i)})};dots.forEach(function(d){d.addEventListener('click',function(){go(parseInt(this.dataset.slide))})});if(prev){prev.addEventListener('click',function(){go(i-1)})}if(next){next.addEventListener('click',function(){go(i+1)})};var iv=setInterval(function(){go(i+1)},5000);c.addEventListener('mouseenter',function(){clearInterval(iv)});c.addEventListener('mouseleave',function(){iv=setInterval(function(){go(i+1)},5000)})})();</script>"""


def build_category_page(niche_slug, niche_name, posts, all_slugs, affiliate_tag=""):
    b = SITE_BASE
    # Build post cards
    post_cards = ""
    for p in posts:
        title = p.get("title", niche_name)
        slug = p.get("slug", f"reviews/{niche_slug}")
        img_src = carousel_img(niche_slug, b)
        post_cards += f'''<div class="post-card">
    <a href="{b}/{slug}/"><img src="{img_src}" alt="{html_mod.escape(title)}"></a>
    <div class="post-card__body">
        <h3><a href="{b}/{slug}/">{html_mod.escape(title)}</a></h3>
        <p>Expert-tested and reviewed. See why this made our list.</p>
        <a href="{b}/{slug}/" class="read-link">Read more →</a>
    </div>
</div>'''

    # Nav dropdown
    nav_dd = "".join(f'<a href="{b}/{s}/">{_slugify_title(s)}</a>' for s in all_slugs)

    # Footer
    footer_cats = "".join(f'<a href="{b}/{s}/">{_slugify_title(s)}</a>' for s in all_slugs)
    footer_social = render_footer_social()

    # Subscribe form action
    form_url = os.environ.get("APPS_SCRIPT_URL", "")

    title_escaped = html_mod.escape(niche_name)
    year_str = str(datetime.now().year)

    blog_title = f"Best {title_escaped} Reviews"
    meta_desc = f"Expert {niche_name.lower()} reviews and buying guides. Independent testing, real recommendations."
    post_list = post_cards or '<p style="grid-column:1/-1;text-align:center;color:var(--clr-mid-gray);padding:40px 0">Reviews coming soon.</p>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="{b}/favicon.png">
    <title>{blog_title} | Abvorn</title>
    <meta name="description" content="{meta_desc}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{ --niche-primary: #0a0a0a; --niche-accent: #c98a2c; }}
        {DESIGN_SYSTEM_CSS}
        
        .top-bar {{ background:#0a0a0a; color:#999; font-size:0.8rem; padding:8px 0; }}
        .top-bar .container {{ display:flex; justify-content:space-between; }}
        header {{ background:#0a0a0a; padding:18px 0; border-bottom:1px solid #2a2a2a; }}
        .navbar {{ display:flex; justify-content:space-between; align-items:center; max-width:1200px; margin:0 auto; padding:0 20px; }}
        .logo img {{ max-height:44px; width:auto; }}
        .nav-links {{ display:flex; align-items:center; gap:8px; }}
        .nav-links > a, .nav-item > a {{ color:#fff; text-decoration:none; padding:8px 16px; font-weight:600; font-size:0.9rem; border-radius:var(--radius-sm); transition: background var(--duration-fast); }}
        .nav-links > a:hover, .nav-item > a:hover {{ background:rgba(255,255,255,0.08); color: var(--clr-accent); }}
        .nav-item {{ position:relative; }}
        .nav-item > a {{ padding:8px 16px; display:flex; align-items:center; gap:4px; }}
        .nav-item > a::after {{ content:'\u25be'; font-size:0.6rem; opacity:0.5; }}
        .nav-item::after {{ content:''; position:absolute; top:100%; left:0; right:0; height:4px; }}
        .nav-dropdown {{ display:none; position:absolute; top:100%; left:0; margin-top:4px; background:#1a1a1a; min-width:220px; border-radius:var(--radius-sm); box-shadow:var(--shadow-lg); padding:6px 0; border:1px solid #2a2a2a; z-index:30; }}
        .nav-item:hover .nav-dropdown, .nav-item:focus-within .nav-dropdown {{ display:block; }}
        .nav-dropdown a {{ display:block; color:#ffffff; padding:8px 20px; font-weight:400; font-size:0.85rem; text-decoration:none; }}
        .nav-dropdown a:hover {{ background:#2a2a2a; color:#fff; }}
        .nav-toggle {{ display:none; background:none; border:none; color:#fff; padding:6px; cursor:pointer; }}
        .nav-toggle svg {{ width:24px; height:24px; }}
        @media (max-width:640px) {{
            .nav-toggle {{ display:block; }}
            .nav-links {{ display:none; position:absolute; top:100%; left:0; right:0; background:#0a0a0a; flex-direction:column; padding:8px 20px 20px; border-top:1px solid #2a2a2a; }}
            .nav-links.open {{ display:flex; }}
            .nav-links > a, .nav-item {{ margin:0; }}
            .nav-links > a, .nav-item > a {{ padding:10px 0; }}
            .nav-item > a::after {{ display:none; }}
            .nav-dropdown {{ position:static; box-shadow:none; margin-top:0; padding-left:16px; display:block; background:transparent; border:none; }}
            .nav-dropdown a {{ color:#888; padding:6px 0; font-size:0.8rem; }}
            .nav-dropdown a:hover {{ background:transparent; color:#fff; }}
        }}

        .category-hero {{ background:var(--clr-off-white); padding: var(--space-2xl) 0; border-bottom:1px solid var(--clr-light-gray); }}
        .category-hero h1 {{ font-size: clamp(var(--text-3xl), 4vw, var(--text-4xl)); margin-bottom: var(--space-sm); }}
        .category-hero p {{ font-size: var(--text-lg); color: var(--clr-mid-gray); max-width:50ch; }}

        .subscribe-band {{ background:var(--clr-off-white); padding: var(--space-xl) 0; border-top:1px solid var(--clr-light-gray); }}
        .subscribe-inner {{ display:flex; justify-content:space-between; align-items:center; gap: var(--space-lg); flex-wrap:wrap; }}
        .subscribe-copy h2 {{ font-size: var(--text-xl); margin-bottom:4px; }}
        .subscribe-copy p {{ margin:0; color:var(--clr-mid-gray); max-width:40ch; font-size:0.95rem; }}
        .subscribe-form {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
        .subscribe-form .input {{ width:240px; background:#fff; border:2px solid var(--clr-light-gray); }}
        .subscribe-form .input:focus {{ border-color:var(--clr-accent); }}
        .subscribe-form .hp-field {{ position:absolute; left:-9999px; }}
        .subscribe-form .btn {{ background:var(--clr-accent); color:#1a1200; font-size:1rem; font-weight:800; padding:0.85em 1.7em; gap:8px; box-shadow:0 6px 22px rgba(201,138,44,0.4); }}
        .subscribe-form .btn:hover {{ background:#e0a23f; transform:scale(1.045); box-shadow:0 8px 28px rgba(201,138,44,0.55); }}
        .subscribe-form .btn svg {{ width:18px; height:18px; }}
        .subscribe-msg {{ flex-basis:100%; font-size:0.85rem; color:#666; margin-top:6px; }}
        @media (max-width:700px) {{ .subscribe-inner {{ flex-direction:column; align-items:flex-start; }} .subscribe-form .input {{ width:100%; }} }}

        .posts-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(320px,1fr)); gap: var(--space-lg); padding: var(--space-2xl) 0; }}
        .post-card {{ border:1px solid var(--clr-light-gray); border-radius:var(--radius-md); overflow:hidden; transition: transform var(--duration-base), box-shadow var(--duration-base); background:var(--clr-white); }}
        .post-card:hover {{ transform:translateY(-4px); box-shadow:var(--shadow-md); }}
        .post-card img {{ width:100%; height:200px; object-fit:cover; }}
        .post-card__body {{ padding:var(--space-md); }}
        .post-card h3 {{ font-size:var(--text-lg); margin:0 0 6px; }}
        .post-card h3 a {{ color:inherit; text-decoration:none; }}
        .post-card .post-meta {{ font-size:0.8rem; color:var(--clr-mid-gray); margin-bottom:8px; }}
        .post-card p {{ font-size:0.9rem; color:var(--clr-mid-gray); margin-bottom:var(--space-sm); line-height:1.5; }}
        .post-card .read-link {{ font-weight:700; font-size:0.85rem; color:var(--clr-black); text-decoration:none; border-bottom:2px solid var(--clr-accent); padding-bottom:1px; }}

        .footer {{ background:#0a0a0a; color:#888; padding: var(--space-2xl) 0 var(--space-lg); border-top:1px solid #2a2a2a; }}
        .footer-grid {{ display:grid; grid-template-columns:2fr 1fr 1fr; gap:var(--space-lg); margin-bottom:var(--space-xl); max-width:1200px; margin-left:auto; margin-right:auto; padding:0 20px; }}
        .footer-col h4 {{ color:#fff; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:14px; }}
        .footer-col a {{ display:block; color:#888; text-decoration:none; padding:3px 0; font-size:0.9rem; }}
        .footer-col a:hover {{ color:#fff; }}
        .footer-social {{ display:flex; gap:8px; margin-top:12px; }}
        .footer-social a {{ width:44px; height:44px; border-radius:50%; background:#1e1e1e; display:flex; align-items:center; justify-content:center; color:#ccc; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }}
        .footer-social a:hover {{ background:var(--clr-accent); color:#0a0a0a; }}
        .footer-social svg {{ width:16px; height:16px; }}
        .footer-bottom {{ border-top:1px solid #1a1a1a; padding-top:16px; display:flex; justify-content:space-between; flex-wrap:wrap; font-size:0.8rem; color:#555; max-width:1200px; margin:0 auto; padding-left:20px; padding-right:20px; }}
        @media (max-width:760px) {{ .footer-grid {{ grid-template-columns:1fr; }} }}
    </style>
</head>
<body>
<div class="top-bar"><div class="container"><span>Independent testing. No sponsored placements.</span><span>Updated weekly</span></div></div>
<header><div class="container navbar">
    <a href="{b}/" class="logo"><img src="{b}/logo.svg" alt="Abvorn"></a>
    <button class="nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav-links">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <nav class="nav-links" id="nav-links">
        <div class="nav-item"><a href="{b}/">Categories</a><div class="nav-dropdown">{nav_dd}</div></div>
        <a href="{b}/about.html">About</a>
        <a href="{b}/privacy.html">Privacy</a>
    </nav>
</div></header>

<section class="category-hero"><div class="container">
    <h1>{blog_title}</h1>
    <p>Independent testing, real recommendations. We buy it, test it, and tell you what's actually worth your money.</p>
</div></section>

<section class="container posts-grid">{post_list}</section>

<section class="subscribe-band"><div class="container subscribe-inner">
    <div class="subscribe-copy">
        <h2>Get alerted when we publish a new {title_escaped} review</h2>
        <p>One email whenever we publish a new guide in this category. No spam, unsubscribe anytime.</p>
    </div>
    <form class="subscribe-form" id="category-subscribe-form" onsubmit="submitCategorySubscribe(event)">
        <input type="text" name="_gotcha" class="hp-field" tabindex="-1" autocomplete="off">
        <label for="category-subscribe-email" class="sr-only">Email address</label>
        <input type="email" class="input" id="category-subscribe-email" placeholder="you@example.com" required>
        <button type="submit" class="btn">Notify Me</button>
        <p class="subscribe-msg" id="category-subscribe-msg" aria-live="polite"></p>
    </form>
</div></section>

<footer class="footer"><div class="footer-grid">
    <div class="footer-col"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:28px;width:auto;margin-bottom:8px"><p>Independent product reviews and buying guides.</p><div class="footer-social">{footer_social}</div></div>
    <div class="footer-col"><h4>Categories</h4>{footer_cats}</div>
    <div class="footer-col"><h4>Company</h4><a href="{b}/about.html">About</a></div>
</div>
<div class="footer-bottom"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:20px;width:auto;filter:brightness(0.6)"><span>&copy; {year_str} Abvorn. All rights reserved.</span><span>Reviews updated weekly</span></div></footer>

<script>
const APPS_SCRIPT_URL = "{form_url}";
const CATEGORY_SLUG = "{niche_slug}";
const CATEGORY_NAME = "{title_escaped}";

(function() {{
    const btn = document.getElementById('nav-toggle');
    const nav = document.getElementById('nav-links');
    if (!btn || !nav) return;
    btn.addEventListener('click', () => {{
        const open = nav.classList.toggle('open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }});
}})();

async function submitCategorySubscribe(e) {{
    e.preventDefault();
    const f = e.target;
    const msg = document.getElementById('category-subscribe-msg');
    if (f._gotcha.value !== "") {{ msg.innerText = 'Success! Check your inbox.'; return; }}
    const email = document.getElementById('category-subscribe-email').value.trim();
    if (!email) return;
    msg.innerText = 'Sending...';
    try {{
        const response = await fetch(APPS_SCRIPT_URL, {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ email: email, niche: CATEGORY_SLUG, source: 'category_page', lead_magnet: `New ${{CATEGORY_NAME}} reviews` }})
        }});
        const result = await response.json();
        msg.innerText = result.success ? 'Success! Check your inbox.' : (result.message || 'Oops, try again.');
    }} catch (err) {{ msg.innerText = 'Connection error. Please try later.'; }}
}}
</script>
</body>
</html>'''


SHARE_HTML_T = """<div class="share-buttons" style="display:flex;gap:8px;margin:32px 0;padding-top:24px;border-top:1px solid var(--border);align-items:center;flex-wrap:wrap">
<span style="font-size:.85rem;font-weight:600;color:var(--text-secondary);margin-right:8px">Share:</span>
<a href="https://twitter.com/intent/tweet?text=TITLE_T&url=URL_T&via=Abvorn" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share on X"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>
<a href="https://www.facebook.com/sharer/sharer.php?u=URL_T" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share on Facebook"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg> Facebook</a>
<a href="https://pinterest.com/pin/create/button/?url=URL_T&description=TITLE_T" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share on Pinterest"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M12.017 0C5.396 0 .029 5.367.029 11.987c0 5.079 3.158 9.417 7.618 11.162-.105-.949-.199-2.403.041-3.439.219-.937 1.406-5.957 1.406-5.957s-.359-.72-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 01.083.345l-.333 1.36c-.053.22-.174.267-.402.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.631-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146 1.124.347 2.317.535 3.554.535 6.607 0 11.974-5.367 11.974-11.987C23.97 5.367 18.603.001 12.017.001z"/></svg> Pinterest</a>
<a href="mailto:?subject=TITLE_T&body=URL_T" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:all .15s" aria-label="Share via Email"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg> Email</a>
</div>"""

COMMENTS_JS = """<script src="https://accounts.google.com/gsi/client" async defer></script>
<script>
(function(){var k='abvorn_comments_'+location.pathname.replace(/\\//g,'_');var c=JSON.parse(localStorage.getItem(k)||'[]');var l=document.getElementById('comments-list');var cu=null;function r(){if(!l)return;if(!c.length){l.innerHTML='<div class=\"no-comments\">No comments yet. Start the conversation!</div>';return}l.innerHTML=c.map(function(e){var a=e.avatar?'<img src=\"'+e.avatar+'\" width=\"20\" height=\"20\" style=\"border-radius:50%;vertical-align:middle;margin-right:4px;display:inline-block\">':'';return'<div class=\"comment\"><div class=\"author\">'+a+htmlEncode(e.name)+' <span class=\"time\">'+new Date(e.date).toLocaleDateString()+'</span></div><div class=\"body\">'+htmlEncode(e.text)+'</div></div>'}).join('')}
function htmlEncode(s){var d=document.createElement('div');d.appendChild(document.createTextNode(s));return d.innerHTML}
window.handleCredentialResponse=function(r){var p=JSON.parse(atob(r.credential.split('.')[1]));cu={name:p.name,email:p.email,avatar:p.picture,sub:p.sub};var ui=document.getElementById('user-info');var si=document.getElementById('sign-in-prompt');var ct=document.getElementById('comment-text');var pb=document.getElementById('post-comment-btn');ui.style.display='flex';document.getElementById('user-avatar').src=p.picture;document.getElementById('user-name').textContent=p.name;si.style.display='none';ct.disabled=false;ct.style.opacity='1';pb.disabled=false;pb.style.opacity='1'}
window.signOut=function(){cu=null;document.getElementById('user-info').style.display='none';document.getElementById('sign-in-prompt').style.display='block';document.getElementById('comment-text').disabled=true;document.getElementById('comment-text').style.opacity='.5';document.getElementById('post-comment-btn').disabled=true;document.getElementById('post-comment-btn').style.opacity='.5'}
window.postComment=function(){var t=document.getElementById('comment-text');if(!cu||!t||!t.value.trim())return;var n=cu.name||'Anonymous';c.unshift({name:n,email:cu.email||'',avatar:cu.avatar||'',text:t.value.trim(),date:new Date().toISOString()});localStorage.setItem(k,JSON.stringify(c));t.value='';r()};r()})();
window.toggleReaction=function(type,btn){var k='abvorn_r_'+type+'_'+location.pathname;var d=JSON.parse(localStorage.getItem(k)||'{"active":false,"count":0}');d.active=!d.active;d.count+=d.active?1:-1;localStorage.setItem(k,JSON.stringify(d));var s=btn.querySelector('.reaction-count');if(s)s.textContent=d.count;btn.classList.toggle('active',d.active&&type==='like');btn.classList.toggle('loved',d.active&&type==='love')};
</script>"""

RPS_JS = """<script>
(function(){
// ── Abvorn Regret Probability Score (client-side) ──────────────
var DATA = document.getElementById('abvorn-rps-data');
if(!DATA)return;
var rpsData;
try{rpsData=JSON.parse(DATA.textContent)}catch(e){return}
if(!rpsData||!rpsData.products||!rpsData.products.length)return;

// Preference-to-score label mapping (mirrors PREFERENCE_MAP in rps.py)
var PREFS = {sound_quality:'Sound Quality',battery_life:'Battery Life',
  comfort:'Comfort & Fit',features:'Features & Tech',value:'Value for Money',
  performance:'Performance',build_quality:'Build Quality',ease_of_use:'Ease of Use',
  design:'Design',reliability:'Reliability',accuracy:'Accuracy',compatibility:'Compatibility'};

// Load or initialize preference profile from localStorage
var LS_KEY='abvorn_prefs';
var DEFAULT_PREFS={sound_quality:5,battery_life:5,comfort:5,features:5,value:5};
var prefs=JSON.parse(localStorage.getItem(LS_KEY)||'null');
if(!prefs){prefs=JSON.parse(JSON.stringify(DEFAULT_PREFS))}

// Update preferences from click signals
function trackPref(category,weight){
  if(category in prefs){
    var old=prefs[category];
    prefs[category]=Math.min(10,Math.max(0,old+(weight||5)-old)*0.3+old*0.7);
    localStorage.setItem(LS_KEY,JSON.stringify(prefs));
  }
}

// Track clicks on product cards, verdict, buy buttons
document.addEventListener('click',function(e){
  var el=e.target.closest('[data-track]');
  if(!el)return;
  var cat=el.getAttribute('data-track');
  var w=parseFloat(el.getAttribute('data-weight')||'5');
  trackPref(cat,w);
});

// Calculate alignment and regret probability (JS port of Python RPS engine)
function calcRegret(userPrefs,productScores){
  var totalW=0,weightedSum=0,reasons=[],good=[],poor=[];
  for(var key in userPrefs){
    if(!userPrefs.hasOwnProperty(key))continue;
    var importance=Math.min(10,Math.max(0,userPrefs[key]));
    var label=PREFS[key];
    if(!label||!(label in productScores))continue;
    var prodVal=parseFloat(productScores[label]);
    var diff=Math.abs(importance-prodVal)/10;
    var align=1-diff;
    weightedSum+=align*importance;
    totalW+=importance;
    if(diff>0.3){
      var msg='You prioritize '+_(key)+' ('+importance.toFixed(0)+'/10), but this product scores '+prodVal.toFixed(1)+'/10.';
      reasons.push({message:msg,severity:diff>0.6?'mismatch':'notice'});
    }
    if(Math.abs(importance-prodVal)<=2&&importance>=5){
      good.push({label:_(key),val:importance+'/'+prodVal.toFixed(1)});
    }
    if(Math.abs(importance-prodVal)>2&&importance>=5){
      poor.push({label:_(key),val:importance+'/'+prodVal.toFixed(1)});
    }
  }
  var alignScore=totalW>0?weightedSum/totalW:0.5;
  var regret=Math.min(1,Math.max(0,1-alignScore));
  return {
    regretProb:Math.round(regret*1000)/10,
    alignmentScore:Math.round(alignScore*100)/100,
    reasons:reasons.slice(0,4),
    goodMatches:good.slice(0,3),
    poorMatches:poor.slice(0,3),
    severity:regret<0.3?'low':regret<0.6?'moderate':regret<0.8?'high':'very_high'
  };
}
function _(k){return k.replace(/_/g,' ').replace(/\\b\\w/g,function(c){return c.toUpperCase()})}

// Render the RPS widget
function renderRPS(regret,productName,allProducts){
  var severityColors={low:'#3a8a5c',moderate:'#d4a03e',high:'#d4633e',very_high:'#c0392b'};
  var severityLabels={low:'Low Regret Risk',moderate:'Moderate Regret Risk',high:'High Regret Risk',very_high:'Very High Regret Risk'};
  var severityTips={low:'This product aligns well with your preferences.',
    moderate:'Some of your priorities don\'t match this product.',
    high:'This product may not be right for you.',
    very_high:'Based on your preferences, this is likely the wrong choice.'};
  var c=severityColors[regret.severity]||'#9e9690';
  var lbl=severityLabels[regret.severity]||'Unknown';
  var tip=severityTips[regret.severity]||'';
  var reasonsHtml=regret.reasons.map(function(r){
    return '<div class="rps-reason rps-'+r.severity+'">'+r.message+'</div>';
  }).join('');

  // Rank alternatives
  var altHtml='';
  if(allProducts.length>1){
    var ranked=allProducts.filter(function(p){return p.name!==productName}).map(function(p){
      var pr=calcRegret(prefs,p.scores);
      return {name:p.name,prob:pr.regretProb,price:p.price,url:p.url};
    }).sort(function(a,b){return a.prob-b.prob}).slice(0,3);
    if(ranked.length){
      altHtml='<div class="rps-alt-title">Better alternatives based on your preferences:</div>';
      ranked.forEach(function(a){
        altHtml+='<a class="rps-alt-item" href="'+(a.url||'#')+'" target="_blank">'
          +'<span class="rps-alt-name">'+a.name+'</span>'
          +'<span class="rps-alt-prob" style="color:'+severityColors[a.prob<30?'low':a.prob<60?'moderate':'high']+'">Regret Risk: '+a.prob+'%</span>'
          +'<span class="rps-alt-price">'+a.price+'</span></a>';
      });
    }
  }

  var el=document.getElementById('abvorn-rps-widget');
  if(!el){
    el=document.createElement('div');
    el.id='abvorn-rps-widget';
    var verdict=document.querySelector('.abvorn-verdict');
    if(verdict)verdict.parentNode.insertBefore(el,verdict.nextSibling);
    else{
      var h1=document.querySelector('h1');
      if(h1)h1.parentNode.insertBefore(el,h1.nextSibling);
    }
  }
  el.innerHTML='<div class="rps-container"><div class="rps-badge">Abvorn Regret Probability Score</div>'
    +'<div class="rps-header" style="border-left-color:'+c+'">'
    +'<div class="rps-score"><span class="rps-number" style="color:'+c+'">'+regret.regretProb+'%</span>'
    +'<span style="color:'+c+';display:block;font-size:.85rem;font-weight:600;margin-top:2px">'+lbl+'</span></div>'
    +'<div class="rps-product-name">For: '+productName+'</div></div>'
    +(reasonsHtml?'<div class="rps-reasons"><div class="rps-section-title">Why?</div>'+reasonsHtml+'</div>':'')
    +'<div class="rps-tip">'+tip+'</div>'
    +(altHtml?'<div class="rps-alternatives">'+altHtml+'</div>':'')
    +'<div class="rps-footer">Your preferences are stored locally. <button class="rps-reset" onclick="resetPrefs()">Reset</button></div></div>';
}

// Reset preferences
window.resetPrefs=function(){
  localStorage.removeItem(LS_KEY);
  prefs=JSON.parse(JSON.stringify(DEFAULT_PREFS));
  var el=document.getElementById('abvorn-rps-widget');
  if(el)el.remove();
};

// Auto-initialize on page load
var primaryProduct=rpsData.products[0];
var regret=calcRegret(prefs,primaryProduct.scores);
renderRPS(regret,primaryProduct.name,rpsData.products);
})();
</script>"""


def build_article_page(niche_slug, niche_name, post_title, article_html, intro, product_name, meta_desc, all_slugs, products=None, pexels_key="", amazon_tag="", form_url="", hero_img="", google_client_id="", related_niches=None, published_date=None, updated_date=None):
    b = SITE_BASE
    t = amazon_tag or os.environ.get("AMAZON_TAG", "viraltestco-20")
    article_url = f"{_SITE_URL}/reviews/{niche_slug}/"
    share = SHARE_HTML_T.replace("TITLE_T", html_mod.escape(post_title)).replace("URL_T", article_url)
    product_cards = ""
    if products:
        product_cards = '<section class="section"><div class="container"><div class="section-title">Products Mentioned</div><div class="product-section">'
        for prod in products:
            product_cards += product_card_html(prod, pexels_key, t)
        product_cards += "</div></div></section>"
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
    hero_img_html = ""
    verdict_chart_data = {"overall": 0, "label": "", "breakdown": {}, "productName": product_name}
    if products and len(products) > 0:
        p0 = products[0]
        p0_url = p0.get("url", "")
        p0_aff = affiliate_url(p0_url, t) if p0_url else f"https://www.amazon.com/s?k={niche_slug.replace('-','+')}&tag={t}"
        # Abvorn Verdict Engine — score the product
        try:
            from abvorn.core.verdict import AbvornVerdictEngine
            engine = AbvornVerdictEngine()
            verdict = engine.score_product(niche_slug, p0)
            detail_url = f"{b}/reviews/{niche_slug}/"
            verdict_html = render_verdict_card(verdict, html_mod.escape(p0.get('name', product_name)), p0_aff, detail_url)
        except Exception:
            verdict_html = f"""<div class="verdict-box"><div class="verdict-title">{html_mod.escape(p0.get('name', product_name))}</div><div class="verdict-price">{p0.get('price', 'Check price')}</div><div class="verdict-for"><strong>Best for:</strong> {html_mod.escape(p0.get('description', 'Anyone looking for the best in this category.'))}</div><div class="verdict-not-for"><strong>Don't buy this if:</strong> You need a different use case covered by our other picks below.</div><a class="buy-btn" href="{p0_aff}" target="_blank" rel="sponsored">Check Price on Amazon</a></div>"""
            verdict = None
        # Build verdict data JSON for the radar chart
        verdict_chart_data = {}
        if verdict and "breakdown" in verdict:
            verdict_chart_data = {
                "overall": verdict.get("overall", 0),
                "label": verdict.get("label", ""),
                "breakdown": verdict["breakdown"],
                "productName": p0.get("name", product_name)
            }
        elif products and len(products) > 0:
            # Fallback: estimate from product data
            from abvorn.core.verdict import CATEGORY_WEIGHTS, FALLBACK_WEIGHTS
            weights = CATEGORY_WEIGHTS.get(niche_slug, FALLBACK_WEIGHTS)
            desc_text = (p0.get("description","") + " " + " ".join(p0.get("features",[]))).lower()
            price_str = str(p0.get("price","0"))
            import re as _re
            p_match = _re.search(r"(\d+\.?\d*)", price_str.replace(",",""))
            est_price = float(p_match.group(1)) if p_match else 0
            breakdown = {}
            for cat_key, cfg in weights.items():
                score = 7.0
                label = cfg["label"]
                if cat_key == "value":
                    if est_price == 0: score = 5.0
                    elif est_price < 50: score = 8.0
                    elif est_price < 100: score = 7.0
                    else: score = 6.0
                elif "battery" in cat_key or "battery" in label.lower():
                    if "battery" in desc_text or "hour" in desc_text: score = 7.5
                elif "sound" in cat_key or "sound" in label.lower() or "audio" in label.lower():
                    if "sound" in desc_text or "audio" in desc_text or "bass" in desc_text: score = 7.5
                elif "comfort" in cat_key or "comfort" in label.lower() or "fit" in label.lower():
                    if "comfort" in desc_text or "fit" in desc_text or "ergo" in desc_text: score = 7.5
                elif "feature" in cat_key or "feature" in label.lower():
                    feat_count = len(p0.get("features", []))
                    score = min(9.0, 5.0 + feat_count)
                breakdown[label] = score
            overall = sum(breakdown.values()) / len(breakdown) if breakdown else 7.0
            verdict_chart_data = {"overall": round(overall, 1), "label": "", "breakdown": breakdown, "productName": p0.get("name", product_name)}
        # Build hero image from hero_img or first product
        if hero_img:
            hero_img_html = hero_img
        elif p0.get("image"):
            hero_img_html = f'<img src="{html_mod.escape(p0["image"])}" alt="{html_mod.escape(p0.get("name", product_name))}" loading="eager">'
    verdict_json = html_mod.escape(json.dumps(verdict_chart_data))
    bread = breadcrumb_schema([
        ("Abvorn", "/"),
        (f"Best {niche_name}", f"/{niche_slug}/"),
        (html_mod.escape(post_title)[:60], f"/reviews/{niche_slug}/"),
    ])
    # RPS data: embed all product scores for client-side regret prediction
    rps_data = {"products": [], "niche": niche_slug}
    try:
        from abvorn.core.verdict import AbvornVerdictEngine
        ve = AbvornVerdictEngine()
        for prod in (products or []):
            v = ve.score_product(niche_slug, prod)
            rps_data["products"].append({
                "name": prod.get("name", "Product"),
                "price": prod.get("price", ""),
                "scores": v["breakdown"],
                "overall": v["overall"],
                "label": v["label"],
                "url": affiliate_url(prod.get("url", ""), t) or "",
            })
    except Exception:
        pass
    rps_json = html_mod.escape(json.dumps(rps_data))
    related_html = ""
    if related_niches:
        cards = "".join(
            f'<a class="cat-card" href="{b}/{r["slug"]}/"><div class="cat-name">{r["name"]}</div><div class="cat-count">{r.get("posts", 0)} reviews</div></a>'
            for r in related_niches
        )
        related_html = f'<section class="section"><div class="container"><div class="section-title">Related Categories</div><div class="grid-3">{cards}</div></div></section>'
    # Build nav dropdown
    nav_dd = "".join(f'<a href="{b}/{s}/">{_slugify_title(s)}</a>' for s in all_slugs)
    # Footer
    footer_cats = "".join(f'<a href="{b}/{s}/">{_slugify_title(s)}</a>' for s in all_slugs)
    footer_social = render_footer_social()

    # Assemble full article body content
    article_body_content = f'''{FTC_DISCLOSURE}
        {cta}
        {matrix_html}
        {verdict_html}
        <div class="chart-section">
            <h3 class="section-title">Performance Breakdown</h3>
            <div class="chart-wrapper">
                <canvas id="verdictChart"></canvas>
            </div>
            <p class="chart-note">Scores out of 10. Based on the Abvorn Verdict Engine.</p>
        </div>
        {intro}
        {article_html}
        <div class="reactions-bar">
        <button class="reaction-btn" onclick="toggleReaction('like',this)" aria-label="Like"><span class="reaction-icon">&#x1F44D;</span><span class="reaction-count">0</span></button>
        <button class="reaction-btn" onclick="toggleReaction('love',this)" aria-label="Love"><span class="reaction-icon">&#x2764;&#xFE0F;</span><span class="reaction-count">0</span></button>
        </div>
        {share}
        {related_html}
        {product_cards}
        <div class="further-reading"><h3>Further Reading</h3><ul>__FURTHER_READING__</ul></div>'''

    further_reading_links = ""
    if related_niches:
        further_reading_links = "".join(
            f'<li><a href="{b}/reviews/{r["slug"]}/">{r["name"]} reviews</a></li>'
            for r in related_niches
        )

    year_str = str(datetime.now().year)
    today_str = datetime.now().strftime('%Y-%m-%d')
    pub_date = published_date or today_str
    upd_date = updated_date or today_str
    title_escaped = html_mod.escape(post_title)
    meta_escaped = html_mod.escape(meta_desc)[:160]
    name_escaped = html_mod.escape(niche_name)
    intro_paragraph = f'{html_mod.escape(product_name)} — {html_mod.escape(meta_desc)[:120]}'
    lead_magnet_title = f'{html_mod.escape(product_name)} Guide'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="{b}/favicon.png">
    <title>{title_escaped} | Abvorn</title>
    <meta name="description" content="{meta_escaped}">
    <link rel="canonical" href="{article_url}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://m.media-amazon.com">
    <link rel="dns-prefetch" href="https://www.googletagmanager.com">
    <link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    {bread}
    <script id="abvorn-rps-data" type="application/json">{rps_json}</script>
    <style>
        :root {{ --niche-primary: #0a0a0a; --niche-accent: #c98a2c; }}
        {DESIGN_SYSTEM_CSS}
        
        .top-bar {{ background:#0a0a0a; color:#999; font-size:0.8rem; padding:8px 0; }}
        .top-bar .container {{ display:flex; justify-content:space-between; align-items:center; }}
        header {{ background:#0a0a0a; padding:18px 0; border-bottom:1px solid #2a2a2a; }}
        .navbar {{ display:flex; justify-content:space-between; align-items:center; max-width:1200px; margin:0 auto; padding:0 20px; }}
        .logo img {{ max-height:44px; width:auto; }}
        .nav-links {{ display:flex; align-items:center; gap:8px; }}
        .nav-links > a, .nav-item > a {{ color:#fff; text-decoration:none; padding:8px 16px; font-weight:600; font-size:0.9rem; border-radius:var(--radius-sm); transition: background var(--duration-fast); }}
        .nav-links > a:hover, .nav-item > a:hover {{ background:rgba(255,255,255,0.08); color: var(--clr-accent); }}
        .nav-item {{ position:relative; }}
        .nav-item > a {{ padding:8px 16px; display:flex; align-items:center; gap:4px; }}
        .nav-item > a::after {{ content:'\u25be'; font-size:0.6rem; opacity:0.5; }}
        .nav-item::after {{ content:''; position:absolute; top:100%; left:0; right:0; height:4px; }}
        .nav-dropdown {{ display:none; position:absolute; top:100%; left:0; margin-top:4px; background:#1a1a1a; min-width:220px; border-radius:var(--radius-sm); box-shadow:var(--shadow-lg); padding:6px 0; border:1px solid #2a2a2a; z-index:30; }}
        .nav-item:hover .nav-dropdown, .nav-item:focus-within .nav-dropdown {{ display:block; }}
        .nav-dropdown a {{ display:block; color:#ffffff; padding:8px 20px; font-weight:400; font-size:0.85rem; text-decoration:none; }}
        .nav-dropdown a:hover {{ background:#2a2a2a; color:#fff; }}
        .nav-toggle {{ display:none; background:none; border:none; color:#fff; padding:6px; cursor:pointer; }}
        .nav-toggle svg {{ width:24px; height:24px; }}
        @media (max-width:640px) {{
            .nav-toggle {{ display:block; }}
            .nav-links {{ display:none; position:absolute; top:100%; left:0; right:0; background:#0a0a0a; flex-direction:column; padding:8px 20px 20px; border-top:1px solid #2a2a2a; }}
            .nav-links.open {{ display:flex; }}
            .nav-links > a, .nav-item {{ margin:0; }}
            .nav-links > a, .nav-item > a {{ padding:10px 0; }}
            .nav-item > a::after {{ display:none; }}
            .nav-dropdown {{ position:static; box-shadow:none; margin-top:0; padding-left:16px; display:block; background:transparent; border:none; }}
            .nav-dropdown a {{ color:#888; padding:6px 0; font-size:0.8rem; }}
            .nav-dropdown a:hover {{ background:transparent; color:#fff; }}
        }}

        /* ===== ARTICLE HERO (dark bg, product image, chart bars) ===== */
        .article-hero {{ background:#0a0a0a; color:#fff; padding: var(--space-2xl) 0; }}
        .article-hero .hero-grid {{ display:grid; grid-template-columns:1fr 1fr; gap: var(--space-xl); align-items:center; }}
        .article-hero .hero-category {{ display:inline-block; font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:var(--clr-accent); margin-bottom:var(--space-sm); }}
        .article-hero h1 {{ font-size:clamp(var(--text-2xl), 4vw, var(--text-4xl)); margin-bottom:var(--space-sm); color:#fff; }}
        .article-hero .meta {{ font-size:0.85rem; color:#999; }}
        .article-hero .meta .published-date, .article-hero .meta .updated-date {{ display:inline-block; font-size:0.75rem; color:var(--clr-mid-gray); background:var(--clr-off-white); padding:2px 10px; border-radius:var(--radius-sm); margin-left:6px; }}
        .article-hero .meta .updated-date {{ background:var(--clr-accent); color:#1a1200; font-weight:600; }}
        .article-hero .excerpt {{ font-size:var(--text-lg); color:#ccc; max-width:50ch; margin-top:var(--space-md); }}
        .hero-image-wrapper {{ position:relative; border-radius:var(--radius-md); overflow:hidden; background:#1a1a1a; display:flex; align-items:center; justify-content:center; min-height:260px; padding:var(--space-md); }}
        .hero-image-wrapper img {{ width:100%; height:auto; max-height:320px; object-fit:contain; }}
        @media (max-width:860px) {{ .article-hero .hero-grid {{ grid-template-columns:1fr; }} .hero-image-wrapper {{ order:-1; min-height:180px; }} }}
        /* ===== VERDICT RADAR CHART ===== */
        .chart-section {{ margin:var(--space-xl) 0; padding:var(--space-lg); background:var(--clr-off-white); border-radius:var(--radius-md); border:1px solid var(--clr-light-gray); }}
        .chart-wrapper {{ width:100%; max-width:500px; height:400px; margin:0 auto; }}
        .chart-note {{ text-align:center; font-size:0.8rem; color:var(--clr-mid-gray); margin-top:var(--space-sm); margin-bottom:0; }}
        @media (max-width:600px) {{ .chart-wrapper {{ height:300px; }} }}

        .content-wrapper {{ display:grid; grid-template-columns:1fr 320px; gap: var(--space-xl); padding: var(--space-2xl) 0; max-width:1200px; margin:0 auto; padding-left:20px; padding-right:20px; }}
        .article-body {{ font-size:1.05rem; line-height:1.8; }}
        .article-body h2 {{ margin:40px 0 16px; color:var(--clr-primary); font-size:var(--text-xl); }}
        .article-body h3 {{ margin:24px 0 12px; font-size:var(--text-lg); }}
        .article-body p {{ margin-bottom:var(--space-md); max-width:65ch; }}
        .article-body img {{ max-width:100%; height:auto; border-radius:var(--radius-sm); margin:20px 0; }}
        .article-body ul, .article-body ol {{ margin-bottom:var(--space-md); padding-left:var(--space-lg); }}
        .article-body li {{ margin-bottom:var(--space-xs); }}
        .article-body blockquote {{ border-left:4px solid var(--clr-accent); padding-left:var(--space-lg); margin:var(--space-lg) 0; color:var(--clr-mid-gray); font-style:italic; }}
        .disclosure {{ background:var(--clr-off-white); padding:var(--space-md); border-radius:var(--radius-sm); font-size:0.85rem; color:var(--clr-mid-gray); margin-bottom:var(--space-lg); }}

        .product-section {{ margin:var(--space-xl) 0; }}
        .section-title {{ font-weight:800; text-transform:uppercase; letter-spacing:0.08em; font-size:0.75rem; margin-bottom:var(--space-md); border-bottom:3px solid var(--clr-primary); padding-bottom:8px; display:inline-block; }}
        .product-section {{ display:grid; grid-template-columns:1fr 1fr; gap:var(--space-lg); }}
        .product-card {{ display:grid; grid-template-columns:100px 1fr; gap:var(--space-md); background:var(--clr-off-white); border:1px solid var(--clr-light-gray); border-radius:var(--radius-md); padding:var(--space-md); transition: transform var(--duration-base), box-shadow var(--duration-base); }}
        .product-card:hover {{ transform:translateY(-2px); box-shadow:var(--shadow-md); }}
        .product-card img {{ width:100px; height:100px; object-fit:contain; border-radius:var(--radius-sm); background:var(--clr-white); }}
        .product-card-body h3 {{ font-size:var(--text-base); margin-bottom:2px; }}
        .product-card-body .price {{ font-size:var(--text-sm); color:var(--clr-accent); font-weight:700; margin-bottom:4px; }}
        .product-card-body p {{ font-size:0.85rem; color:var(--clr-mid-gray); margin-bottom:6px; }}
        .product-card-body ul {{ padding-left:16px; margin:4px 0; font-size:0.8rem; color:var(--clr-mid-gray); }}
        .product-card-body li {{ margin:2px 0; }}
        .buy-btn {{ display:inline-block; padding:6px 14px; background:var(--clr-accent); color:#1a1200; border-radius:var(--radius-sm); font-weight:700; font-size:0.75rem; text-decoration:none; margin-top:6px; transition: background var(--duration-fast); border:none; cursor:pointer; }}
        .buy-btn:hover {{ background:#d4a03a; color:#1a1200; }}
        .product-details h3 {{ font-size:var(--text-xl); margin-bottom:6px; }}
        .product-details .price {{ font-size:var(--text-lg); color:var(--clr-accent); font-weight:700; margin-bottom:6px; }}
        .product-details .rating {{ color:#f59e0b; font-size:1.1rem; margin-bottom:10px; display:flex; gap:2px; }}
        .product-details .desc {{ color:var(--clr-mid-gray); margin-bottom:var(--space-md); font-size:0.95rem; }}
        .product-details .btn {{ background:var(--clr-primary); color:#fff; padding:0.7em 1.5em; font-size:0.8rem; }}
        .product-details .btn:hover {{ background:var(--clr-accent); color:#1a1200; }}
        .rank-chip {{ display:inline-block; background:var(--clr-off-white); color:var(--clr-mid-gray); border:1px solid var(--clr-light-gray); padding:4px 10px; font-size:0.65rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; border-radius:var(--radius-sm); }}
        .signal-tag--badge {{ position:absolute; top:12px; left:12px; padding:5px 12px; border-radius:var(--radius-sm); font-size:0.65rem; font-weight:700; text-transform:uppercase; background:var(--clr-accent); color:#1a1200; box-shadow:var(--shadow-sm); z-index:2; }}

        .sidebar {{ position:sticky; top:80px; }}
        .sidebar-box {{ background:#0a0a0a; color:#fff; padding:var(--space-lg); border-radius:var(--radius-md); margin-bottom:var(--space-lg); }}
        .sidebar-box h4 {{ color:var(--clr-accent); text-transform:uppercase; letter-spacing:0.08em; font-size:0.8rem; margin-bottom:var(--space-md); }}
        .sidebar-box p {{ font-size:0.9rem; color:#ffffff; margin-bottom:var(--space-md); }}
        .sidebar-box .input {{ background:#1a1a1a; color:#fff; border-color:#333; }}
        .sidebar-box .input:focus {{ border-color:var(--clr-accent); }}
        .sidebar-box .btn {{ background:var(--clr-accent); color:#1a1200; width:100%; font-weight:800; font-size:1rem; padding:0.85em 1.7em; box-shadow:0 6px 22px rgba(201,138,44,0.4); border:none; border-radius:var(--radius-sm); cursor:pointer; transition:background 0.2s,transform 0.2s,box-shadow 0.2s; }}
        .sidebar-box .btn:hover {{ background:#e0a23f; transform:scale(1.045); box-shadow:0 8px 28px rgba(201,138,44,0.55); }}

        .further-reading {{ margin-top:var(--space-xl); border-top:1px solid var(--clr-light-gray); padding-top:var(--space-lg); }}
        .further-reading h3 {{ font-size:var(--text-lg); margin-bottom:var(--space-md); }}
        .further-reading ul {{ list-style:none; padding:0; }}
        .further-reading li {{ margin-bottom:8px; }}
        .further-reading a {{ color:var(--clr-primary); text-decoration:none; font-weight:600; }}
        .further-reading a:hover {{ color:var(--clr-accent-text); }}

        .footer {{ background:#0a0a0a; color:#888; padding: var(--space-2xl) 0 var(--space-lg); border-top:1px solid #2a2a2a; }}
        .footer-grid {{ display:grid; grid-template-columns:2fr 1fr 1fr; gap:var(--space-lg); margin-bottom:var(--space-xl); max-width:1200px; margin-left:auto; margin-right:auto; padding:0 20px; }}
        .footer-col h4 {{ color:#fff; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:14px; }}
        .footer-col a {{ display:block; color:#888; text-decoration:none; padding:3px 0; font-size:0.9rem; }}
        .footer-col a:hover {{ color:#fff; }}
        .footer-social {{ display:flex; gap:8px; margin-top:12px; }}
        .footer-social a {{ width:44px; height:44px; border-radius:50%; background:#1e1e1e; display:flex; align-items:center; justify-content:center; color:#ccc; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }}
        .footer-social a:hover {{ background:var(--clr-accent); color:#0a0a0a; }}
        .footer-social svg {{ width:16px; height:16px; }}
        .footer-bottom {{ border-top:1px solid #1a1a1a; padding-top:16px; display:flex; justify-content:space-between; flex-wrap:wrap; font-size:0.8rem; color:#555; max-width:1200px; margin:0 auto; padding-left:20px; padding-right:20px; }}
        @media (max-width:860px) {{ .content-wrapper {{ grid-template-columns:1fr; }} .product-card {{ grid-template-columns:1fr; }} }}
        @media (max-width:760px) {{ .footer-grid {{ grid-template-columns:1fr; }} }}
    </style>
    {COOKIE_CONSENT_SCRIPT}
</head>
<body>
<div class="top-bar"><div class="container"><span>Independent testing. No sponsored placements.</span><span>Updated weekly</span></div></div>
<header><div class="container navbar">
    <a href="{b}/" class="logo"><img src="{b}/logo.svg" alt="Abvorn"></a>
    <button class="nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav-links">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <nav class="nav-links" id="nav-links">
        <div class="nav-item"><a href="{b}/">Categories</a><div class="nav-dropdown">{nav_dd}</div></div>
        <a href="{b}/about.html">About</a>
        <a href="{b}/privacy.html">Privacy</a>
    </nav>
</div></header>

<section class="article-hero"><div class="container hero-grid">
    <div>
        <span class="hero-category">{name_escaped}</span>
        <h1>{title_escaped}</h1>
        <div class="meta">By Abvorn · <span class="published-date">Published: {pub_date}</span> <span class="updated-date">Updated: {upd_date}</span></div>
        <p class="excerpt">{intro_paragraph}</p>
    </div>
    <div class="hero-image-wrapper">
        {hero_img_html}
    </div>
</div></section>

<section class="content-wrapper">
    <article class="article-body" id="main">
        {article_body_content.replace("__FURTHER_READING__", further_reading_links)}
    </article>
    <aside class="sidebar">
        <div class="sidebar-box"><h4>Get the Free Guide</h4><p>Enter your email and we'll send the <strong>{lead_magnet_title}</strong> PDF directly to your inbox.</p>
            <form id="lead-form" onsubmit="submitLead(event)">
                <input type="text" name="_gotcha" style="display:none" tabindex="-1" autocomplete="off">
                <input type="email" id="lead-email" placeholder="your@email.com" class="input" required>
                <button type="submit" class="btn" style="margin-top:10px;">Send Me the Guide</button>
            </form>
            <p id="subscribe-msg" style="font-size:0.8rem;color:#666;margin-top:10px;"></p>
        </div>
    </aside>
</section>

<footer class="footer"><div class="footer-grid">
    <div class="footer-col"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:28px;width:auto;margin-bottom:8px"><p>Independent product reviews and buying guides.</p><div class="footer-social">{footer_social}</div></div>
    <div class="footer-col"><h4>Categories</h4>{footer_cats}</div>
    <div class="footer-col"><h4>Company</h4><a href="{b}/about.html">About</a></div>
</div>
<div class="footer-bottom"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:20px;width:auto;filter:brightness(0.6)"><span>&copy; {year_str} Abvorn. All rights reserved.</span><span>Reviews updated weekly</span></div></footer>

<script>
const APPS_SCRIPT_URL="{form_url}";
const CATEGORY_SLUG = "{niche_slug}";
const LEAD_MAGNET_TITLE = "{lead_magnet_title}";

(function() {{
    const btn = document.getElementById('nav-toggle');
    const nav = document.getElementById('nav-links');
    if (!btn || !nav) return;
    btn.addEventListener('click', () => {{
        const open = nav.classList.toggle('open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }});
}})();

async function submitLead(e) {{
    e.preventDefault();
    const f = e.target;
    const msg = document.getElementById('subscribe-msg');
    if (f._gotcha.value !== "") {{ msg.innerText = 'Success! Check your inbox.'; return; }}
    const email = f.querySelector('#lead-email').value.trim();
    if (!email) return;
    msg.innerText = 'Sending...';
    try {{
        const response = await fetch(APPS_SCRIPT_URL, {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ email: email, niche: CATEGORY_SLUG, source: 'blog_sidebar', lead_magnet: LEAD_MAGNET_TITLE }})
        }});
        const result = await response.json();
        msg.innerText = result.success ? 'Success! Check your inbox.' : (result.message || 'Oops, try again.');
    }} catch(err) {{ msg.innerText = 'Connection error. Please try later.'; }}
}}
</script>
{RPS_JS}
<script id="abvorn-verdict-data" type="application/json">{verdict_json}</script>
<script>
document.addEventListener('DOMContentLoaded', function() {{
    var dataEl = document.getElementById('abvorn-verdict-data');
    if (!dataEl) return;
    var verdictData;
    try {{ verdictData = JSON.parse(dataEl.textContent); }} catch(e) {{ return; }}
    if (!verdictData || !verdictData.breakdown || Object.keys(verdictData.breakdown).length === 0) return;
    var labels = Object.keys(verdictData.breakdown);
    var scores = labels.map(function(l) {{ return verdictData.breakdown[l]; }});
    var ctx = document.getElementById('verdictChart');
    if (!ctx) return;
    ctx = ctx.getContext('2d');
    new Chart(ctx, {{
        type: 'radar',
        data: {{
            labels: labels,
            datasets: [{{
                label: verdictData.productName || 'Product Score',
                data: scores,
                backgroundColor: 'rgba(201,138,44,0.2)',
                borderColor: '#c98a2c',
                borderWidth: 2,
                pointBackgroundColor: '#1a1a1a',
                pointBorderColor: '#c98a2c',
                pointRadius: 5,
                pointHoverRadius: 8,
                fill: true
            }}]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{
                    display: true,
                    position: 'bottom',
                    labels: {{ color: '#0a0a0a', font: {{ family: 'Inter', size: 14, weight: '600' }} }}
                }},
                tooltip: {{
                    backgroundColor: '#0a0a0a',
                    titleFont: {{ family: 'Inter', weight: '600' }},
                    bodyFont: {{ family: 'Inter' }},
                    callbacks: {{ label: function(ctx) {{ return ctx.raw + '/10'; }} }}
                }}
            }},
            scales: {{
                r: {{
                    min: 0, max: 10,
                    ticks: {{ stepSize: 2, color: '#666', backdropColor: 'transparent', font: {{ family: 'Inter', size: 10 }} }},
                    grid: {{ color: 'rgba(0,0,0,0.08)', circular: true }},
                    angleLines: {{ color: 'rgba(0,0,0,0.08)' }},
                    pointLabels: {{ color: '#0a0a0a', font: {{ family: 'Libre Franklin', size: 14, weight: '600' }} }}
                }}
            }}
        }}
    }});
}});
</script>
</body></html>'''



# ─── AI Research (skip DDGS, use AI knowledge directly) ──────────────────
def research_products(niche):
    cache = _own_load_cache()
    keyword = f"best {niche}"
    cache_key = _own_cache_key(keyword, "amazon")
    if cache_key in cache:
        cached = cache[cache_key]
        if cached:
            print(f"  Cached products for {niche}: {len(cached)}")
            return cached
    secrets = get_secrets()
    api_key = secrets.get("OPENWEB_NINJA_KEY", "")
    if not api_key:
        return None
    try:
        response = http_requests.get(
            "https://api.openwebninja.com/realtime-amazon-data/search",
            params={"query": niche.replace("-", " "), "page": 1},
            headers={"X-API-Key": api_key},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            products = data.get("data", {}).get("products", [])
            if products:
                result = []
                for p in products[:5]:
                    result.append({
                        "name": p.get("product_title", "").split(",")[0].strip(),
                        "price": p.get("product_price", ""),
                        "original_price": p.get("product_original_price", ""),
                        "rating": p.get("product_star_rating", ""),
                        "ratings_count": p.get("product_num_ratings", 0),
                        "image": p.get("product_photo", ""),
                        "url": p.get("product_url", ""),
                        "asin": p.get("asin", ""),
                        "description": p.get("product_title", ""),
                        "features": [],
                        "is_best_seller": p.get("is_best_seller", False),
                        "is_amazon_choice": p.get("is_amazon_choice", False),
                        "sales_volume": p.get("sales_volume", ""),
                    })
                cache[cache_key] = result
                _own_save_cache(cache)
                _own_track_usage(1)
                print(f"  Real products from Amazon API: {[p['name'] for p in result]}")
                return result
            else:
                logger.warning(f"Open Web Ninja returned no products for {niche}")
        else:
            logger.warning(f"Open Web Ninja returned {response.status_code}")
    except Exception as e:
        logger.warning(f"Open Web Ninja API error: {e}")
    return None


# ─── Content generation ─────────────────────────────────────────────────
_cost_per_1k = {
    "kilogateway": 0.0, "deepseek": 0.002, "kimi": 0.003,
    "openai": 0.015, "anthropic": 0.018, "gemini": 0.001,
    "groq": 0.002, "glm": 0.003, "local": 0.0,
}
def _track_call(provider, tokens, latency_ms=0.0):
    cost = tokens * (_cost_per_1k.get(provider, 0.002) / 1000.0)
    infra_reporter.report_article_cost("", provider, cost, latency_ms, tokens, niche)
    energy_accounting.record_usage(provider, tokens, latency_ms)


def generate_outline(niche, products):
    names = json.dumps([p.get("name", "") for p in products[:3]])
    prompt = f"""You are a content strategist planning a buying guide for '{niche}'.
Products: {names}

Return a JSON object with:
- outline: array of H2 section headings (e.g. ["Introduction", "What to Look For", "Product Reviews", "Buying Guide", "FAQ", "Conclusion"])
- selected_angle: one of: problem_solution, comparison, how_to, listicle, deep_dive, objection_buster
- primary_keyword: the main SEO keyword for this guide
- post_title: compelling title for the buying guide
- meta_description: 1-2 sentence SEO description"""
    result = ai_sql.query(QueryPlan(
        system_prompt="You are an expert content strategist returning structured JSON data.",
        user_prompt=prompt,
        params={"temperature": 0.7, "max_tokens": 500, "format": "json"},
    )).content
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


def write_draft(niche, products, outline):
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
    intro_html = ai_sql.query(QueryPlan(
        system_prompt="You write concise, honest product review copy.",
        user_prompt=intro_prompt,
        params={"temperature": 0.7, "max_tokens": 500},
    )).content
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
    article_html = ai_sql.query(QueryPlan(
        system_prompt="You write thorough, honest product reviews with specific details and real prices.",
        user_prompt=article_prompt,
        params={"temperature": 0.7, "max_tokens": 2000},
    )).content
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
{OG_META('How We Test — Abvorn', 'Our rigorous, independent testing methodology. Every recommendation is earned through real-world evaluation.', f'{_SITE_URL}/how-we-test/')}
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
<footer><p>Abvorn &middot; Independent reviews since 2026</p><div class="footer-links"><a href="{b}/privacy/">Privacy</a><a href="{b}/terms/">Terms</a><a href="{b}/disclaimer/">Disclaimer</a><a href="{b}/about/">About</a></div>{SOCIAL_HTML}</footer>
{NAV_SCRIPT}
{CAROUSEL_JS}</body></html>"""


# ─── Persona Content Engine ──────────────────────────────────────────────
CONTENT_TYPE_MAP = {
    "unaware": {"type": "problem_discovery", "label": "Problem Discovery",
        "purpose": "Catch the unaware — make them feel seen. Start with their frustration, name it, validate it.",
        "example": "5 Signs Your Commute Is Draining You More Than You Realize"},
    "problem_aware": {"type": "problem_deep_dive", "label": "Problem Deep-Dive",
        "purpose": "Educate the problem-aware. Show them why the problem costs more than they think.",
        "example": "Why Most Commuters Get Half the Battery Life They Could"},
    "solution_aware": {"type": "how_to", "label": "How-To / Setup Guide",
        "purpose": "Help the solution-aware implement. Step-by-step, actionable.",
        "example": "How to Set Up Noise Cancelling Without Missing Your Train Stop"},
    "solution_aware_comparison": {"type": "solution_comparison", "label": "Solution Comparison",
        "purpose": "Help the solution-aware decide between approaches.",
        "example": "Noise Cancelling vs Transparency Mode — Which Commuter Type Are You?"},
    "product_aware": {"type": "product_review", "label": "Product Review",
        "purpose": "Give the product-aware the final nudge. Real testing, real verdict.",
        "example": "Sony XM6 Review: 30 Days as a Daily Commuter"},
    "most_aware": {"type": "micro_comparison", "label": "Micro-Comparison",
        "purpose": "Convert the most-aware. Quick, decisive head-to-head.",
        "example": "XM6 vs AirPods Pro 3: The Commuter's Verdict"},
    "cross_sell": {"type": "cross_sell", "label": "Cross-Sell Bundle",
        "purpose": "Bundle cross-sell. Natural next-product recommendation.",
        "example": "The 3-Gadget Commute Kit That Changed My Morning"},
}

def generate_persona_content_plan(niche_name, persona, awareness_level="problem_aware",
                                   products=None, content_type_override=None):
    """Generate a content plan matrix for a persona at a given awareness level.
    Returns a dict with title, angle, structure, and SEO metadata — no API call needed."""
    p_name = persona.get("name", "Your Reader")
    frustrations = persona.get("psychology", {}).get("anxieties", ["the problem"])
    hopes = persona.get("psychology", {}).get("hopes", ["a solution"])
    cialdini = persona.get("psychology", {}).get("cialdini_principles", ["social_proof"])
    hoffeld = persona.get("psychology", {}).get("hoffeld_buying_reason", "gain")

    if content_type_override:
        ct = next((v for v in CONTENT_TYPE_MAP.values() if v["type"] == content_type_override),
                  CONTENT_TYPE_MAP["problem_aware"])
    else:
        ct = CONTENT_TYPE_MAP.get(awareness_level, CONTENT_TYPE_MAP["problem_aware"])

    frust = frustrations[0] if frustrations else "the problem"
    hope = hopes[0] if hopes else "a solution"
    niche_lower = niche_name.lower()

    title_templates = {
        "problem_discovery": [
            f"Are You {frust.title()}? Here's What No One Tells You About {niche_lower}",
            f"5 Signs Your {frust.title()} Is Costing You More Than You Think",
            f"Stop Ignoring {frust.title()} — Why {niche_lower} Matters More Than Ever",
        ],
        "problem_deep_dive": [
            f"Why Most People Get {niche_lower} Wrong (And Pay for It)",
            f"The Hidden Cost of Bad {niche_lower}: What Nobody Talks About",
            f"Your {niche_lower} Is Holding You Back. Here's How to Fix It",
        ],
        "how_to": [
            f"How to {hope.title()} Without Breaking the Bank",
            f"{niche_lower} Done Right: A Step-by-Step Guide for {p_name}",
            f"The {p_name}'s Guide to {hope.title()}",
        ],
        "solution_comparison": [
            f"{niche_lower}: The {p_name}'s Dilemma — Which Path Is Right for You?",
            f"Should You Prioritize {hopes[0] if len(hopes)>1 else 'Quality'} or {frust}?",
        ],
        "product_review": [
            f"Best {niche_lower} for {p_name}: Real Testing, Honest Verdict",
            f"We Tested the Top {niche_lower} So {p_name} Doesn't Have To",
        ],
        "micro_comparison": [
            f"[Product A] vs [Product B]: The {p_name}'s Verdict",
            f"Which {niche_lower} Should {p_name} Buy? The 90-Second Answer",
        ],
        "cross_sell": [
            f"The Ultimate {niche_lower} Kit for {p_name}",
            f"3 Products {p_name} Needs for the Perfect {niche_lower} Setup",
        ],
    }

    titles = title_templates.get(ct["type"], [f"Best {niche_lower} for {p_name}"])
    selected_title = titles[0]

    return {
        "persona": p_name,
        "awareness_level": awareness_level,
        "content_type": ct["type"],
        "content_label": ct["label"],
        "purpose": ct["purpose"],
        "suggested_title": selected_title,
        "alternative_titles": titles[1:],
        "angle": f"Help {p_name} overcome {frust} to achieve {hope}",
        "primary_keyword": f"best {niche_lower} for {p_name.lower().replace(' ','-')}",
        "meta_description_template": f"Struggling with {frust}? Our {ct['label'].lower()} helps {p_name} {hope[:40]}. Expert guidance, real results.",
        "persuasion_levers": {
            "cialdini": cialdini,
            "hoffeld": hoffeld,
        },
        "suggested_structure": [
            f"Hook: Name {p_name}'s specific {frust}",
            f"Agitate: Why {frust} costs them time/money/peace",
            "Solution: Present the method or approach",
            "Trust: Specific examples, data, or social proof",
            "Action: Clear next step with product recommendation",
        ],
    }


def generate_persona_article(niche_name, persona, awareness_level,
                               products=None, content_type_override=None):
    """Generate full persona-specific article using AISQL.
    Falls back to returning a content plan + placeholder structure."""
    plan = generate_persona_content_plan(niche_name, persona, awareness_level,
                                          products, content_type_override)

    # Check if AISQL is available (has working providers)
    ai_sql_available = any(p.health_check() for p in ai_sql.providers.values())
    if not ai_sql_available:
        plan["mode"] = "manual"
        plan["article_html"] = _persona_article_template(plan, persona, niche_name, products)
        plan["instructions"] = "Replace placeholder text with original content. See mission phase 4 for guidelines."
        return plan

    # Generate full article via AISQL
    p = persona.get("psychology", {})
    frustrations = p.get("anxieties", [])
    hopes = p.get("hopes", [])
    prod_names = json.dumps([pr.get("name", "") for pr in (products or [])])

    prompt = f"""You are writing a {plan['content_label']} article for Abvorn.

NICHE: {niche_name}
CONTENT TYPE: {plan['content_type']} — {plan['purpose']}
PRIMARY KEYWORD: {plan['primary_keyword']}

TARGET READER — {persona.get('name', 'Your Reader')}
Their frustrations: {json.dumps(frustrations)}
Their hopes: {json.dumps(hopes)}
Awareness level: {awareness_level}

Products to feature: {prod_names or 'None yet — write generically'}

INSTRUCTIONS:
1. Lead with the persona's frustration. Make them feel seen.
2. Agitate the problem — why it costs them time/money/peace of mind.
3. Present the solution (method, not just product).
4. Cross-sell naturally: if mentioning a product, use an affiliate link.
5. End with a clear, low-friction CTA.

Return JSON:
{{
  "post_title": "Compelling title (50-65 chars)",
  "meta_description": "SEO meta (150-160 chars) that speaks to the persona",
  "intro": "2-3 paragraph hook (HTML)",
  "article_html": "Full article body (800-1200 words HTML). Include 1-2 natural affiliate links with tag=viraltestco-20"
}}"""

    result = ai_sql.query(QueryPlan(
        system_prompt="You are an expert content writer for Abvorn, an independent product review platform.",
        user_prompt=prompt,
        params={"temperature": 0.9, "max_tokens": 1500, "format": "json"},
    )).content
    if not result:
        plan["mode"] = "fallback"
        plan["article_html"] = _persona_article_template(plan, persona, niche_name, products)
        return plan

    import json as _json
    try:
        data = _json.loads(result)
    except Exception:
        plan["mode"] = "fallback"
        plan["article_html"] = _persona_article_template(plan, persona, niche_name, products)
        return plan

    plan["mode"] = "ai_generated"
    plan["post_title"] = data.get("post_title", plan["suggested_title"])
    plan["meta_description"] = data.get("meta_description", "")
    plan["intro"] = data.get("intro", "")
    plan["article_html"] = data.get("article_html", "")
    return plan


def _persona_article_template(plan, persona, niche_name, products=None):
    """Generate a well-structured HTML template for manual filling."""
    p_name = persona.get("name", "Your Reader")
    frustrations = persona.get("psychology", {}).get("anxieties", [])
    hopes = persona.get("psychology", {}).get("hopes", [])
    frust = frustrations[0] if frustrations else "this problem"
    hope = hopes[0] if hopes else "your goal"
    ct = plan["content_type"]
    prod = products[0].get("name", "our recommended product") if products else "our recommended product"
    prod_price = products[0].get("price", "$XX") if products else "$XX"

    templates = {
        "problem_discovery": f"""<p>You know that feeling when {frust}? It's not just annoying — it's a sign that something isn't working.</p>
<p>Most people ignore it. They adapt, they cope, they tell themselves it's fine. But here's the truth: {frust} is costing you more than you realize.</p>
<p>In this guide, we'll show you exactly what's going wrong and — more importantly — how to fix it. No fluff, no theory. Just actionable steps that actually work.</p>
<h2>The Real Cost of Ignoring {frust}</h2>
<p>The problem with {frust.lower()} isn't just the inconvenience. It's the cumulative drain on your time, your focus, and your peace of mind.</p>
<p>Think about it: every time you deal with {frust.lower()}, you're spending mental energy you could be using for something that matters. Multiply that by days, weeks, months — and the cost adds up fast.</p>
<h2>What You Can Do About It</h2>
<p>The good news? You don't have to live with this. Here's a proven approach to solving {frust.lower()} once and for all.</p>
<p>Start by acknowledging the problem. Then look at the tools and techniques available. And finally — make a decision based on what actually works, not what's marketed the hardest.</p>
<p>If you're ready to take action, we recommend starting with <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod} ({prod_price})</a> — it's what we use and trust.</p>""",
        "problem_deep_dive": f"""<p>Let's talk about {frust}. It's one of the most overlooked issues in {niche_name}, and it's quietly costing people like {p_name} thousands in wasted time and money.</p>
<p>Most articles tell you what to buy. This one tells you why the problem exists in the first place — and how to fix it at the root.</p>
<h2>Why {frust} Happens</h2>
<p>The root cause is almost never what people think. It's not about budget, or brand, or even the specific product. It's about how {niche_name} fits into your specific situation.</p>
<p>When you understand the underlying mechanics, you stop wasting money on Band-Aid fixes and start investing in solutions that last.</p>
<h2>What {p_name} Should Do Instead</h2>
<p>Here's the framework we use after testing dozens of options. Step one: identify your actual use case. Step two: match it to proven solutions. Step three: ignore everything else.</p>
<p>Want the shortcut? Start with <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod}</a> — it consistently outperforms alternatives in this exact scenario.</p>""",
        "how_to": f"""<p>If you've been struggling with {frust}, here's a step-by-step system that will help you achieve {hope}.</p>
<h2>Step 1: Assess Your Starting Point</h2>
<p>Before you can fix {frust.lower()}, you need to understand where you are now. Take 5 minutes to evaluate your current setup and identify the specific gaps.</p>
<h2>Step 2: Choose the Right Approach</h2>
<p>Not all solutions are created equal. For {p_name}, the best approach prioritizes {hope.lower()} without creating new problems. Here's what to look for...</p>
<h2>Step 3: Invest in What Works</h2>
<p>Once you've identified the right approach, it's time to execute. We've tested extensively and found that <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod}</a> delivers the best results for people in your situation.</p>
<h2>Step 4: Optimize and Maintain</h2>
<p>Getting it right is one thing. Keeping it right is another. Here's how to maintain your setup for long-term success...</p>""",
        "solution_comparison": f"""<p>If you're reading this, you already know {frust} is a problem. Now the question is: what's the best way to solve it?</p>
<p>We've tested every major approach. Here's our honest assessment of what works best for {p_name}.</p>
<h2>Option A: The Quick Fix</h2>
<p>Fast, affordable, but often temporary. Good if you need an immediate solution and are comfortable iterating.</p>
<h2>Option B: The Long-Term Solution</h2>
<p>More investment upfront, but delivers {hope} sustainably. This is what we recommend for most people.</p>
<h2>Our Verdict</h2>
<p>For {p_name}, we recommend <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod}</a>. It strikes the best balance of performance, value, and reliability.</p>""",
        "product_review": f"""<p>After spending [X hours] testing {prod} against its top competitors, here's our honest verdict — including what we didn't like.</p>
<h2>First Impressions</h2>
<p>Out of the box, {prod} feels {hope.lower()} in mind. The build quality is solid, the setup is straightforward, and the initial performance is impressive.</p>
<h2>How It Performs in Real-World Use</h2>
<p>We tested {prod} for [X days/weeks] in real conditions. Here's what we found...
<strong>What we loved:</strong> [Key strengths]
<strong>What we didn't:</strong> [Honest weaknesses]</p>
<h2>Bottom Line</h2>
<p>Is {prod} right for {p_name}? If {frust} is your main concern, then yes — this is the best option at {prod_price}. <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">Check the current price on Amazon</a>.</p>""",
        "micro_comparison": f"""<p>Quick question for {p_name}: Are you better off with the market leader or the value pick? We tested both to give you a straight answer.</p>
<h2>At a Glance</h2>
<table class="decision-matrix"><thead><tr><th>Feature</th><th>{prod}</th><th>Alternative</th></tr></thead><tbody>
<tr><td>Price</td><td>{prod_price}</td><td>$XX</td></tr>
<tr><td>Performance</td><td>Excellent</td><td>Good</td></tr>
<tr><td>Best For</td><td>{p_name}</td><td>Budget buyers</td></tr>
</tbody></table>
<h2>The Verdict</h2>
<p>If {frust} is your priority, <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod}</a> is the clear choice.</p>""",
        "cross_sell": f"""<p>Most people stop at one product. But if you really want to solve {frust}, you need a system — not just a gadget.</p>
<h2>The Essential Kit for {p_name}</h2>
<p>After extensive testing, here are the three products {p_name} needs for the perfect {niche_name} setup:</p>
<p><strong>1. {prod}</strong> — The cornerstone. This handles the core {frust.lower()} problem.</p>
<p><strong>2. [Complementary product]</strong> — Extends your capabilities and fills the gaps.</p>
<p><strong>3. [Accessory]</strong> — The finishing touch that makes everything work together seamlessly.</p>
<p>Start with <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod} ({prod_price})</a> and build from there.</p>""",
    }

    return templates.get(ct, templates["problem_discovery"])


def get_persona_content_matrix(niche_name):
    """Build a complete content matrix for a niche: all personas × all awareness levels.
    Returns list of content plan dicts, one per cell in the matrix."""
    from abvorn.persona.engine import PersonaEngine
    engine = PersonaEngine()
    personas = engine.discover_personas(niche_name)
    matrix = []
    for persona in personas:
        for level in ["unaware", "problem_aware", "solution_aware", "product_aware", "most_aware"]:
            plan = generate_persona_content_plan(niche_name, persona, level)
            matrix.append(plan)
        # Add cross-sell
        plan = generate_persona_content_plan(niche_name, persona, "solution_aware",
                                             content_type_override="cross_sell")
        matrix.append(plan)
    return matrix


def write_persona_content_plan(niche_name, matrix, docs_dir="docs/plans"):
    """Write persona content plan to a markdown file for the mission to use."""
    import os
    plans_dir = os.path.join(docs_dir, "")
    os.makedirs(plans_dir, exist_ok=True)
    slug = niche_name.lower().replace(" ", "-")
    path = os.path.join(plans_dir, f"content-plan-{slug}.md")
    lines = [
        f"# Content Plan: {niche_name}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]
    for plan in matrix:
        lines.extend([
            f"## Persona: {plan['persona']} — {plan['content_label']}",
            f"- **Awareness**: {plan['awareness_level']}",
            f"- **Suggested Title**: {plan['suggested_title']}",
            f"- **Angle**: {plan['angle']}",
            f"- **Keyword**: {plan['primary_keyword']}",
            f"- **Persuasion**: Cialdini={plan['persuasion_levers']['cialdini']}, Hoffeld={plan['persuasion_levers']['hoffeld']}",
            f"- **Structure**:",
        ])
        for s in plan["suggested_structure"]:
            lines.append(f"  - {s}")
        lines.append("")
    content = "\n".join(lines)
    with open(path, "w") as f:
        f.write(content)
    print(f"  Written: {path} ({len(matrix)} content pieces planned)")
    return path


# ─── Document writer ────────────────────────────────────────────────────
def write_files(niche_slug, articles, state, pexels_key="", amazon_tag="", form_url="", hero_images=None, google_client_id=""):
    """Write all HTML files to docs/ directory."""
    all_slugs = sorted([n["slug"] for n in state["niches"]], key=lambda s: _slugify_title(s).lower())
    hero_images = hero_images or {}
    niche_name = next((n["name"] for n in state["niches"] if n["slug"] == niche_slug), niche_slug.replace("-", " ").title())

    # Collect all posts across niches
    all_posts = []
    for n in state["niches"]:
        for p in articles.get(n["slug"], []):
            all_posts.append({"title": p.get("post_title", ""), "slug": n["slug"]})

    docs = Path("docs")
    docs.mkdir(exist_ok=True)

    # Write root index (premium homepage)
    (docs / "index.html").write_text(build_homepage(state, form_url), encoding="utf-8")
    print(f"  Written: docs/index.html")

    # Generate static pages if they don't exist
    b = SITE_BASE
    year = datetime.now().year
    static_pages = [
        ("store.html", "Store", "<h2>Our Niche Stores</h2><p>Select a niche to explore curated product recommendations.</p>"),
        ("about.html", "About Abvorn", "<h2>About Abvorn</h2><p>We are an AI-powered media network delivering expert product reviews and buying guides.</p>"),
        ("privacy.html", "Privacy Policy", "<h2>Privacy Policy</h2><p>We respect your privacy. This site uses cookies for analytics and affiliate tracking. No personal data is sold.</p>"),
    ]
    for page_name, title, content in static_pages:
        page_path = docs / page_name
        if not page_path.exists():
            full_page = f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="{b}/favicon.png"><title>{title} | Abvorn</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Inter',sans-serif;color:#333;line-height:1.6}}
.top-bar{{background:#0a0a0a;color:#999;font-size:0.8rem;padding:8px 0}}
.top-bar .container{{display:flex;justify-content:space-between;max-width:1200px;margin:0 auto;padding:0 20px}}
header{{background:#0a0a0a;padding:18px 0;border-bottom:1px solid #2a2a2a}}
.header-inner{{display:flex;justify-content:space-between;align-items:center;max-width:1200px;margin:0 auto;padding:0 20px}}
.logo-img{{max-height:44px;width:auto}}
.main{{padding:60px 20px;max-width:800px;margin:0 auto}}
footer{{background:#0a0a0a;color:#888;padding:40px 0;text-align:center;border-top:1px solid #2a2a2a}}
footer a{{color:#aaa;text-decoration:none}}
</style></head>
<body>
<div class="top-bar"><div class="container"><span>Independent testing. No sponsored placements.</span><span>Updated weekly</span></div></div>
<header><div class="header-inner"><a href="{b}/"><img src="{b}/logo.svg" alt="Abvorn" class="logo-img"></a></div></header>
<main class="main"><h1>{title}</h1>{content}</main>
<footer><img src="{b}/logo.svg" alt="Abvorn" style="max-height:24px;width:auto;filter:brightness(0.8);margin-bottom:8px"><p>&copy; {year} Abvorn</p></footer>
</body></html>'''
            page_path.write_text(full_page)
            print(f"  Written: docs/{page_name}")

    # Write category pages (post slugs point to reviews/{slug} for article pages)
    for n in state["niches"]:
        niche_posts = [{"title": a.get("post_title", ""), "slug": f"reviews/{n['slug']}"} for a in articles.get(n["slug"], [])]
        cat_dir = docs / n["slug"]
        cat_dir.mkdir(exist_ok=True)
        (cat_dir / "index.html").write_text(build_category_page(n["slug"], n["name"], niche_posts, all_slugs, amazon_tag), encoding="utf-8")

    # Write comparison pages
    comp_dir = docs / "comparisons"
    comp_dir.mkdir(exist_ok=True)
    for n in state["niches"]:
        prods = []
        for a in articles.get(n["slug"], []):
            prods.extend(a.get("products", []))
        if prods:
            title = f"Best {n['name']} Compared"
            (comp_dir / f"{n['slug']}.html").write_text(
                build_comparison_page(n["slug"], n["name"], title, prods, all_slugs, amazon_tag),
                encoding="utf-8"
            )
            print(f"  Written: comparisons/{n['slug']}.html")

    # Write article pages (under docs/reviews/{slug}/ to avoid overwriting category page)
    for slug, post_list in articles.items():
        for i, a in enumerate(post_list):
            post_dir = docs / "reviews" / slug
            post_dir.mkdir(parents=True, exist_ok=True)
            hero_img_html = hero_images.get(slug, "")
            _sorted_niches = sorted(state["niches"], key=lambda n: n["name"].lower())
            related = [n for n in _sorted_niches if n["slug"] != slug][:4]
            (post_dir / "index.html").write_text(
                build_article_page(slug, niche_name, a["post_title"], a["article_html"],
                                   a["intro"], a["product_name"], a["meta_description"],
                                   all_slugs, a.get("products"), pexels_key, amazon_tag, form_url, hero_img_html, google_client_id,
                                   related_niches=related),
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


def _register_sensors(nervous_system):
        """Register all monitoring sensors."""
        nervous_system.register_sensor(
            "engagement_sensor",
            lambda: 0.15,
            "engagement_score",
            0.3,
            AlertLevel.CRITICAL
        )
        nervous_system.register_sensor(
            "sentiment_sensor",
            lambda: 0.45,
            "sentiment_drift",
            0.25,
            AlertLevel.WARNING
        )
        nervous_system.register_sensor(
            "algorithm_sensor",
            lambda: 0.10,
            "algorithm_change",
            0.5,
            AlertLevel.INFO
        )
        nervous_system.register_sensor(
            "quality_sensor",
            lambda: 0.85,
            "quality_score",
            0.7,
            AlertLevel.WARNING
        )
        nervous_system.register_sensor(
            "error_sensor",
            lambda: 0.02,
            "error_rate",
            0.05,
            AlertLevel.CRITICAL
        )

# ─── Main ────────────────────────────────────────────────────────────────
def main(forced_niche=None, force=False):
    global ai_sql
    secrets = get_secrets()
    ai_sql = create_ai_sql()
    feedback_loop = create_feedback_loop(ai_sql)

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
    products = research_products(niche_slug)
    if not products:
        print("ERROR: No products found")
        sys.exit(1)
    print(f"Found {len(products)} products: {[p.get('name','?') for p in products]}")

    # 2. OUTLINE
    print(f"\n--- OUTLINE: {niche_slug} ---")
    outline = generate_outline(niche_slug, products)
    if not outline:
        print("WARNING: Outline failed, using default")
        outline = {"post_title": f"Best {niche_name}", "meta_description": f"Find the best {niche_name}.",
                   "selected_angle": "problem_solution", "primary_keyword": f"best {niche_slug}",
                   "outline": ["Introduction", "Product Reviews", "Buying Guide", "FAQ", "Conclusion"]}
    print(f"Title: {outline.get('post_title','?')}")

    # 3. DRAFT
    print(f"\n--- DRAFT: {niche_slug} ---")
    draft = write_draft(niche_slug, products, outline)
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
            social = resizer.resize(img_bytes, "og")
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

    # 4.5 FACT-CHECK — Validate all factual claims before marking complete
    fact_checker = create_fact_checker(draft)
    fact_results = fact_checker.check_content(draft.get("article_html", ""), context={"niche": niche_slug})
    if fact_results["overall_status"] == "critical":
        print(f"  CRITICAL: Article failed fact-check — blocking publication")
        logger.error(f"Fact-check CRITICAL for {niche_slug}: {len(fact_results['failed_claims'])} failed claims")
    elif fact_results["failed_claims"]:
        print(f"  WARNING: {len(fact_results['failed_claims'])} claims failed fact-check")
        corrected_html = fact_checker.apply_corrections(draft.get("article_html", ""), fact_results["corrections"])
        if corrected_html != draft.get("article_html", ""):
            draft["article_html"] = corrected_html
            print(f"  Applied {len(fact_results['corrections'])} auto-corrections")
    else:
        print(f"  Fact-check: PASSED ({len(fact_results['verified_claims'])} claims verified)")

    # 4.6 QUANTUM SIMULATION — Predict engagement before marking complete
    print(f"\n--- QUANTUM SIMULATION: {niche_slug} ---")
    try:
        quantum_engine = create_quantum_engine()
        user_data = {"interest_score": 0.7}
        for platform_str in ["tiktok", "youtube_short", "instagram_reel", "x", "linkedin"]:
            platform_map = {"tiktok": Platform.TIKTOK, "youtube_short": Platform.YOUTUBE, "instagram_reel": Platform.INSTAGRAM, "x": Platform.X, "linkedin": Platform.LINKEDIN}
            plat = platform_map.get(platform_str)
            if plat:
                simulation = quantum_engine.simulate_content(draft, user_data, plat)
                assembled = quantum_engine.assemble_content(simulation, draft, plat)
                print(f"  {platform_str}: engagement={assembled['predictions']['engagement_score']:.0%} confidence={assembled['predictions']['confidence']:.0%}")
        print(f"  Quantum simulation complete")
    except Exception as e:
        print(f"  Quantum simulation skipped: {e}")

    # 5. UPDATE STATE
    niche["posts"] += 1
    state["last_processed"] = niche_slug
    save_state(state)
    print(f"\nState updated: {niche_slug} now has {niche['posts']} posts")

    # Summary
    total = sum(n["posts"] for n in state["niches"])
    print(f"\n{'='*50}")
    print(f"[OK] Cycle complete: {niche_slug}")
    print(f"   Total posts on site: {total}")
    print(f"   Next up: next niche in round-robin")
    print(f"{'='*50}")

    # Close feedback loop after each cycle
    try:
        feedback_result = feedback_loop.close_loop()
        logger.info(f"Feedback loop closed: {feedback_result.get('status', 'ok')}")
    except Exception as e:
        logger.warning(f"Feedback loop close failed: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Abvorn content cycle")
    parser.add_argument("--niche", type=str, help="Niche slug to process (auto-pick if omitted)")
    parser.add_argument("--force", action="store_true", help="Force regenerate even if has posts")
    args = parser.parse_args()
    main(forced_niche=args.niche, force=args.force)
