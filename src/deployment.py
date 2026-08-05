"""deployment.py — Deployment functions for Abvorn.

All functions that deploy pages to GitHub live here.
"""
import html as html_mod
import json
import logging
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from github import Github, Auth, InputGitTreeElement

from src.article_design import (ARTICLE_DESIGN_CSS, PROD_SHOT_CSS,
                                upgrade_product_image,
                                product_shot_html, info_dot,
                                sanitize_article_html, inject_product_photos,
                                build_faq, hero_pick_html, render_article_body,
                                price_floor_for)

logger = logging.getLogger(__name__)

# Helpers shared with run_cycle.py
SITE_BASE = "https://abvorn-media.github.io/abvorn"
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
@media (forced-colors: active) { .btn { border: 2px solid ButtonText; } .card { border: 1px solid ButtonText; } }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
:focus-visible { outline: 2px solid var(--clr-accent); outline-offset: 2px; }

/* ── Compare & Watchlist ──────────────────────────────────────── */
.av-compare-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: transparent; color: var(--clr-accent); border: 1px solid var(--clr-accent);
  padding: 4px 12px; border-radius: 100px; font-size: 0.78rem; font-weight: 700;
  cursor: pointer; font-family: var(--font-body); transition: all .15s; margin-top: 8px;
}
.av-compare-btn:hover { background: var(--clr-accent); color: var(--clr-white); }
.av-compare-btn.added { background: var(--clr-primary); color: var(--clr-white); border-color: var(--clr-primary); }
.av-compare-icon { font-size: 1rem; font-weight: 700; }
#av-compare-bar {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 90;
  background: var(--clr-black); color: var(--clr-white);
  padding: 12px 24px; display: none; align-items: center; justify-content: space-between;
  box-shadow: 0 -4px 20px rgba(0,0,0,.15); border-top: 2px solid var(--clr-accent);
  font-family: var(--font-body);
}
#av-compare-bar.show { display: flex; }
#av-compare-bar .av-compare-items { display: flex; gap: 12px; overflow-x: auto; flex: 1; align-items: center; }
#av-compare-bar .av-compare-pill {
  display: flex; align-items: center; gap: 8px; background: var(--clr-dark-gray);
  padding: 6px 12px; border-radius: 100px; font-size: 0.82rem; white-space: nowrap; min-width: fit-content;
}
#av-compare-bar .av-compare-pill img { width: 24px; height: 24px; border-radius: 4px; object-fit: contain; }
#av-compare-bar .av-compare-remove { background: none; border: none; color: var(--clr-mid-gray); cursor: pointer; font-size: 1rem; padding: 0 2px; }
#av-compare-bar .av-compare-remove:hover { color: #ff6b6b; }
#av-compare-bar .av-compare-cta {
  background: var(--clr-accent); color: var(--clr-black); border: none; padding: 8px 20px;
  border-radius: var(--radius-sm); font-weight: 700; font-size: 0.85rem; cursor: pointer; white-space: nowrap;
}
#av-compare-bar .av-compare-cta:hover { filter: brightness(1.1); }
#av-compare-bar .av-compare-clear { background: none; border: none; color: var(--clr-mid-gray); cursor: pointer; font-size: 0.8rem; text-decoration: underline; margin-right: 16px; white-space: nowrap; }
@media (max-width: 640px) {
  #av-compare-bar { flex-wrap: wrap; gap: 8px; padding: 10px 16px; }
  #av-compare-bar .av-compare-cta { width: 100%; justify-content: center; }
  #av-compare-bar .av-compare-clear { width: 100%; margin: 0; text-align: center; }
}

/* ── Footer category columns ──────────────────────────────────── */
.footer-cat-cols { display: flex; gap: var(--space-xl); }
.footer-cat-col { display: flex; flex-direction: column; }
.footer-col h4 + a + h4 { margin-top: var(--space-lg); }
"""

SITE_CHROME_CSS = """
/* ── Site-wide chrome (header + footer), used on every page ───── */
.top-bar { background:#0a0a0a; color:#999; font-size:0.8rem; padding:8px 0; }
.top-bar .container { display:flex; justify-content:space-between; }
header { background:#0a0a0a; padding:18px 0; position:sticky; top:0; z-index:100; box-shadow:0 2px 10px rgba(0,0,0,0.25); }
.navbar { display:flex; justify-content:space-between; align-items:center; max-width:1200px; margin:0 auto; padding:0 20px; }
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
.footer { background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }
.footer-grid { display:grid; grid-template-columns: 1.6fr 2fr 1fr; gap: var(--space-lg); margin-bottom: var(--space-xl); }
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
"""

VERDICT_CARD_CSS = """
.abvorn-verdict{padding:28px 32px;margin:32px 0;border-top:1px solid #e8e8e8;border-bottom:1px solid #e8e8e8;background:transparent;position:relative}
.av-badge{display:inline-flex;align-items:center;gap:6px;background:#1a1a1a;color:#fff;font-size:.7rem;font-weight:700;padding:4px 14px;border-radius:100px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px}
.av-badge::before{content:'\\01F525';font-size:.8rem}
.av-score-row{display:flex;align-items:center;gap:20px;margin-bottom:20px}
.av-score{display:flex;align-items:baseline;gap:2px}
.av-number{font-size:3rem;font-weight:700;font-family:'Libre Franklin',Georgia,sans-serif;color:#1a1a1a;line-height:1;letter-spacing:-.03em}
.av-outof{font-size:1.2rem;color:#666;font-weight:600}
.av-label-row{display:flex;flex-direction:column;gap:2px}
.av-label{font-size:1.1rem;font-weight:700;color:#c98a2c;font-family:'Libre Franklin',Georgia,sans-serif}
.av-product{font-size:1.2rem;font-weight:800;color:#1a1a1a;font-family:'Libre Franklin',Georgia,sans-serif;line-height:1.3;margin:0 0 4px}
.av-breakdown{display:flex;flex-direction:column;gap:8px;margin-bottom:20px}
.av-bar-row{display:flex;align-items:center;gap:12px}
.av-bar-label{flex:0 0 140px;font-size:.82rem;font-weight:600;color:#888;text-align:right}
.av-bar-track{flex:1;height:8px;background:#e8e8e8;border-radius:100px;overflow:hidden}
.av-bar-fill{height:100%;border-radius:100px;transition:width .6s cubic-bezier(.4,0,.2,1)}
.av-bar-score{flex:0 0 36px;font-size:.85rem;font-weight:700;color:#1a1a1a;text-align:right}
.av-summary{font-size:.95rem;color:#888;line-height:1.5;margin-bottom:20px}
.av-cta{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
@media(max-width:640px){.av-score-row{flex-direction:column;align-items:flex-start;gap:8px}.av-bar-label{flex:0 0 100px;font-size:.75rem}.abvorn-verdict{padding:20px 16px}}
"""

CLICK_DOMAIN = os.environ.get("CLICK_DOMAIN", "https://abvorn.com")
_SITE_URL = os.environ.get("SITE_URL", "https://abvorn-media.github.io/abvorn").rstrip("/")

CTA_BANNER = """
<div class="cta-banner">
<h3>Ready to buy?</h3>
<p>We've done the research. Now get the best price on Amazon.</p>
<a class="buy-btn" href="https://www.amazon.com/s?k={query}&tag={tag}" target="_blank" rel="sponsored">Shop all picks on Amazon &rarr;</a>
</div>"""


def affiliate_url(product_url, tag=""):
    """Append Amazon affiliate tag to a product URL."""
    t = tag or os.environ.get("AMAZON_TAG", "")
    if not t:
        return product_url
    sep = "&" if "?" in product_url else "?"
    return f"{product_url}{sep}tag={t}"


def extract_asin(product_url: str) -> str:
    """Extract Amazon ASIN from a product URL."""
    if not product_url:
        return ""
    m = re.search(r"/dp/([A-Z0-9]{10})", product_url)
    return (m.group(1) if m else "").upper()


def product_card_html(product, pexels_key="", amazon_tag="", include_compare: bool = True):
    """Minimal product card HTML for standalone deployment use."""
    from abvorn.core.verdict import clean_product_name
    name = clean_product_name(product.get("name", "Product"))
    price = product.get("price", "Check price")
    features = product.get("features", [])
    summary = product.get("description", "")
    product_url = product.get("url", "")
    product_image = product.get("image", "")
    verdict_score = product.get("verdict_score", "")
    verdict_label = product.get("verdict_label", "")
    asin = extract_asin(product_url)
    data_attrs = (
        f' data-asin="{asin}" data-name="{html_mod.escape(name)}" '
        f'data-price="{html_mod.escape(str(price or ""))}" '
        f'data-image="{html_mod.escape(product_image or "")}" '
        f'data-url="{html_mod.escape(product_url or "")}" '
        f'data-score="{html_mod.escape(str(verdict_score or ""))}" '
        f'data-label="{html_mod.escape(verdict_label or "")}"'
    )
    img = ""
    if product_image:
        img = f'<img src="{product_image}" alt="{html_mod.escape(name)}" loading="lazy" style="width:100%;max-height:360px;object-fit:contain;background:var(--clr-white);border-radius:var(--radius-sm)">'
    else:
        img = '<div style="width:100%;max-height:360px;background:linear-gradient(135deg,var(--bg-alt),var(--border));border-radius:var(--radius-sm);display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:.8rem;padding:40px 0">Product</div>'
    compare_btn = ""
    if include_compare and asin:
        from urllib.parse import urlencode
        qs = urlencode({
            "asin": asin,
            "name": name,
            "price": price or "",
            "image": product_image or "",
            "url": product_url or "",
            "score": verdict_score or "",
            "label": verdict_label or "",
        })
        compare_btn = (
            f'<a class="av-compare-btn" data-asin="{asin}" '
            f'data-name="{html_mod.escape(name)}" data-price="{html_mod.escape(str(price or ""))}" '
            f'data-image="{html_mod.escape(product_image or "")}" data-url="{html_mod.escape(product_url or "")}" '
            f'data-score="{html_mod.escape(str(verdict_score or ""))}" data-label="{html_mod.escape(verdict_label or "")}" '
            f'href="/abvorn/compare?{qs}"><span class="av-compare-icon">⊕</span> Compare</a>'
        )
    summary_escaped = html_mod.escape(summary)
    return f"""<div class="product-card"{data_attrs}>
{img}
<div class="product-card-body">
<h3>{html_mod.escape(name)}</h3>
<div class="price">{html_mod.escape(str(price or 'N/A'))}</div>
<p>{summary_escaped}</p>
{compare_btn}
<a class="buy-btn" href="{affiliate_url(product_url, amazon_tag) or '#'}" target="_blank" rel="sponsored">Check Price on Amazon &rarr;</a>
</div>
</div>"""


def render_verdict_card(verdict: dict, product_name: str, affiliate_url: str = "", detail_url: str = "") -> str:
    """Render the full Abvorn Verdict card (single source of truth in abvorn.core.verdict)."""
    from abvorn.core.verdict import render_verdict_card as _render
    return _render(verdict, product_name, affiliate_url, detail_url)

def render_compare_bar(product: dict, include_compare: bool = True) -> str:
    return ""


def generate_click_url(article_id: str, product_index: int, product_url: str = "") -> str:
    return f"{CLICK_DOMAIN}/click/{article_id}/{product_index}"


def rewrite_affiliate_urls(html: str, article_id: str) -> str:
    import re, html as html_mod
    pattern = re.compile(r'(<a\s[^>]*href=")(https?://[^"]*(?:amazon|amzn)[^"]*?)("[^>]*>)', re.IGNORECASE)
    product_index = 0
    seen_indices = {}

    def replace_match(match):
        nonlocal product_index
        prefix, original_url, suffix = match.group(1), match.group(2), match.group(3)
        if "abvorn.com/click/" in original_url:
            return match.group(0)
        if original_url in seen_indices:
            idx = seen_indices[original_url]
        else:
            idx = product_index
            seen_indices[original_url] = idx
            product_index += 1
        click_url = generate_click_url(article_id, idx)
        return f'{prefix}{click_url}{suffix}'

    return pattern.sub(replace_match, html)


def _slugify_title(s):
    """Convert a slug to a readable category name."""
    return s.replace("-", " ").title()


# ── Category navigation (mega-menu + footer) ────────────────────────────
CATEGORY_MAP = {
    "Audio": ["wireless-earbuds", "wireless-headphones"],
    "Computing & Monitors": ["4k-monitors", "laptops"],
    "Fitness & Health": ["fitness-trackers"],
    "Gaming": ["gaming-mice", "mechanical-keyboards"],
    "Home & Lifestyle": ["smart-home", "streaming-devices"],
    "Webcams & Accessories": ["webcams"],
}

# One light, distinguishable banner color per category. Each is light enough
# that the dark banner text (#1a1200) stays clearly readable (~9:1+ contrast),
# and each reads distinctly so viewers can identify a category by color alone.
CATEGORY_COLORS = {
    "Audio": "#c98a2c",                    # gold/amber — brand anchor, kept
    "Computing & Monitors": "#a7c3e8",     # steel blue — screens & tech
    "Fitness & Health": "#b7ddc0",         # leaf green — health & vitality
    "Gaming": "#cfc0ee",                   # periwinkle — energy & play
    "Home & Lifestyle": "#f0c8b6",         # soft peach — warmth & comfort
    "Webcams & Accessories": "#a8d7d2",    # light teal — optics & capture
}

CATEGORY_COLOR_FALLBACK = "#c98a2c"


def category_color(name):
    """Resolve a category to its banner color, with a brand-gold fallback."""
    return CATEGORY_COLORS.get(name, CATEGORY_COLOR_FALLBACK)

CATEGORY_NAMES = {
    "4k-monitors": "4K Monitors",
    "fitness-trackers": "Fitness Trackers",
    "gaming-mice": "Gaming Mice",
    "laptops": "Laptops",
    "mechanical-keyboards": "Mechanical Keyboards",
    "smart-home": "Smart Home",
    "streaming-devices": "Streaming Devices",
    "webcams": "Webcams",
    "wireless-earbuds": "Wireless Earbuds",
    "wireless-headphones": "Wireless Headphones",
}


def _niche_name(slug):
    return CATEGORY_NAMES.get(slug, _slugify_title(slug))


def _category_slug(name):
    """Slugify a category name for URLs. 'Computing & Monitors' -> 'computing-and-monitors'."""
    return name.lower().replace(" & ", "-and-").replace("&", "and").replace(" ", "-").replace("--", "-")


def _title_slug(title):
    """Slugify a review title for its filename. 'Best Wireless Earbuds' -> 'best-wireless-earbuds'."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "review"


def review_img(niche_slug, b):
    """Pick the generated PNG hero for a review card, else fall back to the SVG."""
    png = f"docs/assets/{niche_slug}.png"
    if os.path.exists(png):
        return f"{b}/assets/{niche_slug}.png"
    return carousel_img(niche_slug, b)


def load_verdict_weights() -> dict:
    """Load persisted Verdict Engine weight overrides from data/verdict_weights.json."""
    try:
        path = Path("data/verdict_weights.json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


_INTRO_RE = re.compile(r"<h2>\s*Introduction\s*</h2>\s*<p[^>]*>(.*?)</p>", re.S)
# The one-line excerpt rendered in the article hero (carries the real thesis).
_EXCERPT_RE = re.compile(r'<p[^>]*class="[^"]*excerpt[^"]*"[^>]*>(.*?)</p>', re.S)
# Any non-empty paragraph, to catch pages that skip an explicit introduction.
_ANY_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
# The "Our Choice" hero pick product photo rendered into the article hero.
_HERO_PICK_IMG_RE = re.compile(r'<div class="hero-pick".*?<img class="product-shot__img" src="([^"]+)"', re.S)
# Fallback: the niche page's hero product photo (hero-image-wrapper > img),
# which carries the reviewed product itself rather than a category illustration.
_NICHE_HERO_IMG_RE = re.compile(r'<div class="hero-image-wrapper">\s*<img src="([^"]+)"', re.S)
# Abvorn Verdict overall score embedded on published review pages (either plain
# JSON or the HTML-entity-escaped variant), e.g. '"overall": 7.0'.
_VERDICT_OVERALL_RE = re.compile(r'overall.{0,40}?([0-9]+(?:\.[0-9]+)?)')
# The full Abvorn Verdict JSON block embedded on published review pages
# ({overall, label, breakdown: {criterion: score}, productName}).
_VERDICT_DATA_RE = re.compile(r'id="abvorn-verdict-data"[^>]*>(.*?)</script>', re.S)
_BOILERPLATE_RE = re.compile(
    r"^(we'?ve done the research|scores out of 10|we tested the top products|we'?re reviewing the top products)",
    re.I,
)


def _parse_verdict_data(html):
    """Parse the Abvorn Verdict JSON block from a review page.

    Returns (breakdown dict, overall float|None, label str|"", productName str|"").
    Tolerant of HTML-entity-escaped JSON. Never raises.
    """
    try:
        m = _VERDICT_DATA_RE.search(html)
        if not m:
            return {}, None, "", ""
        data = json.loads(html_mod.unescape(m.group(1)))
        if not isinstance(data, dict):
            return {}, None, "", ""
        breakdown = data.get("breakdown") or {}
        if not isinstance(breakdown, dict):
            breakdown = {}
        return (
            breakdown,
            data.get("overall"),
            data.get("label", "") or "",
            data.get("productName", "") or "",
        )
    except Exception:
        return {}, None, "", ""


def _clean_snippet(raw):
    """Unescape, flatten whitespace, reject boilerplate/too-short text."""
    text = html_mod.unescape(re.sub(r"<[^>]+>", "", raw))
    text = re.sub(r"\s+", " ", text).strip()
    # Excerpts sometimes lead with the long product name + em dash
    # (e.g. "Dell 27 Monitor S2725QS — Discover the best 4K…"); keep the part
    # after the dash so the card reads as a snippet, not a title repeat.
    # Some dated articles render the dash mojibake'd as "â€"" (UTF-8 bytes read
    # as latin-1), so match both.
    for dash in (" — ", " â€” ", " â€"" "):
        if dash in text:
            after = text.split(dash, 1)[1].strip()
            if len(after) >= 25:
                text = after
            break
    if len(text) < 40 or _BOILERPLATE_RE.search(text):
        return ""
    if len(text) > 180:
        cut = text.rfind(" ", 0, 180)
        text = text[:cut].rstrip(" ,.;:") + "…"
    return text


def review_snippet(html):
    """First real paragraph of a review page, for card snippets ("" if none).

    Tries, in order: the Introduction block, the article's excerpt line, then
    the first substantial paragraph. Pages without an explicit Introduction
    (e.g. wireless-headphones, 4k-monitors) still get a snippet this way.
    """
    m = _INTRO_RE.search(html)
    if m:
        text = _clean_snippet(m.group(1))
        if text:
            return text
    m = _EXCERPT_RE.search(html)
    if m:
        text = _clean_snippet(m.group(1))
        if text:
            return text
    for m in _ANY_P_RE.finditer(html):
        text = _clean_snippet(m.group(1))
        if text:
            return text
    return ""


def scan_published_reviews(docs_dir="docs"):
    """Enumerate every published review page under docs/reviews/*.

    Each directory is one niche. When a niche has per-article pages (dated
    files) they are returned (and its index.html is skipped so the latest
    review is not double-counted); otherwise index.html is the single card.
    Returns a list of dicts: {slug, name, title, updated, rel, snippet}.
    """
    base = Path(docs_dir) / "reviews"
    reviews = []
    if not base.is_dir():
        return reviews
    for niche_dir in sorted(base.iterdir()):
        if not niche_dir.is_dir():
            continue
        slug = niche_dir.name
        pages = sorted(p for p in niche_dir.glob("*.html") if p.name != "index.html")
        if not pages:
            index = niche_dir / "index.html"
            pages = [index] if index.exists() else []
        index_snippet = ""
        index_hero = ""
        # Canonical niche verdict lives in index.html; use it as the fallback
        # for dated article pages so the hero verdict card always has data.
        index_breakdown = {}
        index_label = ""
        index_product = ""
        index_overall = None
        if (niche_dir / "index.html").exists():
            index_html = (niche_dir / "index.html").read_text(encoding="utf-8")
            index_snippet = review_snippet(index_html)
            m = _HERO_PICK_IMG_RE.search(index_html)
            if not m:
                m = _NICHE_HERO_IMG_RE.search(index_html)
            if m:
                index_hero = html_mod.unescape(m.group(1))
            index_breakdown, index_overall, index_label, index_product = _parse_verdict_data(index_html)
        for p in pages:
            html = p.read_text(encoding="utf-8")
            h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
            title = html_mod.unescape(re.sub(r"<[^>]+>", "", h1.group(1))).strip() if h1 else ""
            upd = re.search(r"Updated:\s*(\d{4}-\d{2}-\d{2})", html)
            rel = f"/reviews/{slug}/" if p.name == "index.html" else f"/reviews/{slug}/{p.name}"
            hero_img = index_hero
            if p.name != "index.html":
                m = _HERO_PICK_IMG_RE.search(html)
                if not m:
                    m = _NICHE_HERO_IMG_RE.search(html)
                if m:
                    hero_img = html_mod.unescape(m.group(1))
            m_score = _VERDICT_OVERALL_RE.search(html)
            score = float(m_score.group(1)) if m_score else None
            breakdown, bd_overall, bd_label, bd_product = _parse_verdict_data(html)
            # Dated article pages carry the niche's canonical verdict from
            # index.html as fallback, so hero cards always have criteria.
            if not breakdown:
                breakdown, bd_overall, bd_label, bd_product = index_breakdown, index_overall, index_label, index_product
                score = score if score else index_overall
            reviews.append({
                "slug": slug,
                "name": _niche_name(slug),
                "title": title or _niche_name(slug),
                "updated": upd.group(1) if upd else "",
                "rel": rel,
                "snippet": review_snippet(html) or index_snippet,
                "image": hero_img or "",
                "score": score,
                "breakdown": breakdown,
                "label": bd_label,
                "product_name": bd_product,
            })
    return reviews


def verify_page(html_content: str) -> bool:
    """Quick regression guard for generated article pages.

    Raises ValueError if a required asset is missing from the rendered HTML.
    """
    missing = []
    if 'id="abvorn-rps-data"' not in html_content:
        missing.append("abvorn-rps-data")
    if 'cdn.jsdelivr.net/npm/chart.js' not in html_content:
        missing.append("chart.js")
    if 'class="av-bar-row"' not in html_content:
        missing.append("av-bar-row")
    if missing:
        raise ValueError(f"Missing required page assets: {', '.join(missing)}")
    return True


def review_card(item, category, b, featured=False):
    """One review card with a category+niche banner, verdict score, snippet, and bottom-aligned CTA.

    Uses the review's "Our Choice" studio product photo when available so the
    universal photography treatment carries through to cards; falls back to the
    generated niche hero image otherwise.
    """
    title = html_mod.escape(item["title"])
    href = f'{b}/reviews/{item["slug"]}/'
    color = category_color(category)
    snippet = item.get("snippet", "")
    snippet_html = (
        f'<p class="review-card__snippet">{html_mod.escape(snippet)}</p>' if snippet else ""
    )
    if item.get("image"):
        card_img = product_shot_html(item["image"], item["title"], size="card")
    else:
        card_img = f'<img src="{review_img(item["slug"], b)}" alt="{title}" loading="lazy">'

    # Verdict score badge — the single strongest trust signal on the card.
    score = item.get("score")
    if score:
        score_html = f'<span class="review-card__score" aria-label="Abvorn Verdict {score:.1f} out of 10"><span class="review-card__score-num">{score:.1f}</span><span class="review-card__score-out">/10</span></span>'
    else:
        score_html = ''

    # Freshness line (only when the page records an update date).
    updated_html = ""
    if item.get("updated"):
        try:
            d = datetime.strptime(item["updated"], "%Y-%m-%d")
            label = f'Updated {d.strftime("%b %Y")}'
        except ValueError:
            label = f'Updated {html_mod.escape(item["updated"])}'
        updated_html = f'<span class="review-card__updated">{label}</span>'

    cls = " niche-card--featured" if featured else ""
    return f'''<div class="niche-card review-card{cls}" style="--cat:{color}">
    <div class="review-card__media">
        <a href="{href}" tabindex="-1" aria-hidden="true" class="review-card__media-link"><div class="niche-card__image-wrapper">{card_img}</div></a>
        <span class="review-card__banner" style="background:{color}">{html_mod.escape(category)} · {html_mod.escape(item["name"])}</span>
        {score_html}
    </div>
    <div class="review-card__body">
        <h2><a href="{href}">{title}</a></h2>
        {snippet_html}
        <div class="review-card__footer">
            <div class="review-card__reactions" data-review="{item["slug"]}">
                <span class="reaction-btn is-counter" data-type="like"><span class="reaction-icon">&#x1F44D;</span><span class="reaction-count">0</span></span>
                <span class="reaction-btn is-counter" data-type="love"><span class="reaction-icon">&#x2764;&#xFE0F;</span><span class="reaction-count">0</span></span>
            </div>
            <a href="{href}" class="read-link">Read review →</a>
        </div>
        {updated_html}
    </div>
</div>'''


def build_category_dropdown(b=""):
    """White multi-column mega-menu markup (the inner .nav-dropdown content).

    Each category label is itself a link to its category listing page, so the
    main categories are clickable, not just their niches.
    """
    groups = ""
    for label, slugs in CATEGORY_MAP.items():
        links = "".join(f'<a href="{b}/{s}/">{_niche_name(s)}</a>' for s in slugs)
        cat_href = f'{b}/categories/{_category_slug(label)}/'
        groups += f'<div class="category-group"><a class="category-label" href="{cat_href}">{html_mod.escape(label)}</a>{links}</div>'
    return groups


def build_footer_categories(b=""):
    """Main-category links for the footer Categories column.

    Lists only the top-level categories (keys of CATEGORY_MAP), sorted
    alphabetically, capped at 8 links per sub-column so the list fills
    down the first column before starting a new one as the catalogue grows.
    """
    cats = sorted(CATEGORY_MAP.keys(), key=lambda c: c.lower())
    cols = [cats[i:i + 8] for i in range(0, len(cats), 8)]
    cols_html = "".join(
        '<div class="footer-cat-col">' + "".join(
            f'<a href="{b}/categories/{_category_slug(name)}/">{html_mod.escape(name)}</a>'
            for name in col
        ) + '</div>'
        for col in cols
    )
    return f'<div class="footer-cat-cols">{cols_html}</div>'


def build_category_index(category_name, b="", niche_slugs=None):
    """Contents rail under the hero; each link scrolls to its section.

    "All reviews" jumps to the latest section (#latest); each niche jumps to
    its own section (#<slug>). Every link carries a tick in the category's
    banner color, tying the rail to the site's per-category color language.
    Only niches with a section on the page are listed, so every anchor lands.
    As niches grow the rail fills out and is the seam to graduate into a
    dropdown.
    """
    slugs = niche_slugs if niche_slugs is not None else CATEGORY_MAP.get(category_name, [])
    color = category_color(category_name)
    links = [
        f'<a class="category-index__link is-current" aria-current="true" href="#latest"><span class="category-index__tick" style="--cat:{color}"></span>All reviews</a>'
    ]
    for s in slugs:
        links.append(
            f'<a class="category-index__link" href="#{s}"><span class="category-index__tick" style="--cat:{color}"></span>{html_mod.escape(_niche_name(s))}</a>'
        )
    return (
        '<nav class="category-index" aria-label="Guides in this category">'
        '<div class="container category-index__inner">'
        f'<span class="category-index__label">In this category</span>'
        f'<div class="category-index__links">{"".join(links)}</div>'
        '</div></nav>'
    )


MEGA_MENU_CSS = """
.nav-item:hover .nav-dropdown.nav-dropdown--mega, .nav-item:focus-within .nav-dropdown.nav-dropdown--mega { display:flex; }
.nav-dropdown.nav-dropdown--mega { flex-wrap:wrap; gap:6px 8px; min-width:600px; max-width:90vw; padding:14px 18px; right:0; left:auto; }
.nav-dropdown.nav-dropdown--mega .category-group { display:block; flex:1 1 200px; min-width:170px; }
.nav-dropdown.nav-dropdown--mega .category-label { display:block; color:var(--clr-accent,#c98a2c); font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; padding:4px 20px 2px; }
.nav-dropdown.nav-dropdown--mega a { padding:6px 20px; }
@media (max-width:640px) {
    .nav-dropdown.nav-dropdown--mega { display:block; min-width:0; max-width:none; padding:0; }
    .nav-dropdown.nav-dropdown--mega .category-group { display:block; flex:1 1 auto; }
    .nav-dropdown.nav-dropdown--mega .category-label { padding:8px 0 2px; }
    .nav-dropdown.nav-dropdown--mega a { padding:5px 0; }
}
"""


def carousel_img(niche_slug, b):
    """Pick real hero JPG if uploaded, else fall back to generated SVG."""
    hero_path = f"docs/assets/hero/{niche_slug}.jpg"
    if os.path.exists(hero_path):
        return f"{b}/assets/hero/{niche_slug}.jpg"
    return f"{b}/assets/{niche_slug}.svg"


def HEAD_HTML(title, description):
    return f"""<title>{title}</title><meta name="description" content="{description}">"""


def OG_META(title, description, url):
    return f"""<meta property="og:title" content="{title}"><meta property="og:description" content="{description}"><meta property="og:url" content="{url}">"""


ANALYTICS_HTML = ""


CSS_SHARED = """"""


FOOTER_HTML = ""


# Duplicate docstring/imports cleanup
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def push_single_file(path: str, content: str) -> None:
    """Push a single file to GitHub via the configured remote."""
    try:
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            logger.warning("GITHUB_TOKEN not set; cannot push to GitHub")
            return
        from github import Github
        g = Github(token)
        repo = g.get_repo("Abvorn-Media/abvorn")
        # Extract branch and file path
        branch = "main"
        file_path = path.lstrip("/")
        contents = repo.get_contents(file_path, ref=branch)
        repo.update_file(contents.path, f"Update {file_path}", content, contents.sha, branch=branch)
        logger.info(f"Pushed {file_path} to GitHub")
    except Exception as e:
        logger.error(f"Failed to push {path}: {e}")


def deploy_single_page(page_path: str, content: str) -> Dict[str, Any]:
    """Deploy a single page and return deployment result."""
    try:
        push_single_file(page_path, content)
        url = f"https://abvorn-media.github.io/abvorn/{page_path}"
        logger.info(f"Deployed {page_path} -> {url}")
        return {"status": "deployed", "url": url, "path": page_path}
    except Exception as e:
        logger.error(f"Deploy failed for {page_path}: {e}")
        return {"status": "failed", "path": page_path, "error": str(e)}
def _truncate(text, n=40):
    """Truncate a long product title to n chars with an ellipsis."""
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def _hero_slide_verdict(breakdown, overall, label, product, name):
    """Build the 5-criterion verdict scorecard inside a hero slide.

    The card is the site's proof of the "Scored on 5 criteria" claim: the
    real breakdown with the top criterion in amber and the weakest muted.
    Returns "" when no breakdown data exists (caller falls back to a caption).
    """
    if not breakdown:
        return ""
    criteria = list(breakdown.items())[:5]
    srt = sorted(criteria, key=lambda kv: kv[1], reverse=True)
    top = srt[0][0]
    weak = srt[-1][0] if len(srt) > 1 else None
    bars = ""
    for crit, score in criteria:
        pct = int(round(score * 10))
        cls = " is-top" if crit == top else (" is-weak" if crit == weak else "")
        bars += (
            f'<div class="hero-verdict__bar{cls}">'
            f'<span class="hero-verdict__bar-label">{html_mod.escape(crit)}</span>'
            f'<span class="hero-verdict__bar-track"><span class="hero-verdict__bar-fill" style="--score:{pct}%"></span></span>'
            f'<span class="hero-verdict__bar-score">{score:.1f}</span></div>'
        )
    overall_html = f"{overall:.1f}<small>/10</small>" if overall else "—"
    label_html = f'<span class="hero-verdict__label">{html_mod.escape(label or "Scored")}</span>'
    title = _truncate(product or name, 40)
    return f'''<div class="hero-verdict">
        <div class="hero-verdict__head">
            <div class="hero-verdict__title">
                <span class="hero-verdict__eyebrow">{html_mod.escape(name)} · Abvorn Verdict</span>
                <span class="hero-verdict__product">{html_mod.escape(title)}</span>
            </div>
            <div class="hero-verdict__overall"><span class="hero-verdict__num">{overall_html}</span>{label_html}</div>
        </div>
        <div class="hero-verdict__bars">{bars}</div>
    </div>'''


def build_homepage(state, form_url="", reviews=None, base=None):
    """Build the premium homepage with hero slider, stats, and category sections."""
    niches = sorted(state["niches"], key=lambda n: n["name"].lower())
    all_slugs = sorted([n["slug"] for n in niches], key=lambda s: _slugify_title(s).lower())
    b = base or SITE_BASE
    total_posts = sum(n["posts"] for n in niches)
    total_products = total_posts * 3  # rough estimate

    # Published reviews — one card per review page (up to 3 per category).
    review_list = reviews if reviews is not None else scan_published_reviews()

    # Build nav dropdown (white mega-menu)
    nav_dd = build_category_dropdown(b)

    # Build hero slides — each slide is a live verdict scorecard proving the
    # "Scored on 5 criteria" promise, with the reviewed product photo as backdrop.
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
    review_by_slug = {r["slug"]: r for r in review_list}
    for i, (img, name, slug) in enumerate(hero_candidates):
        active = " active" if i == 0 else ""
        review = review_by_slug.get(slug, {})
        # Prefer the real reviewed product photo when one is published; fall
        # back to the generated niche illustration otherwise.
        backdrop = review.get("image") or img
        verdict = _hero_slide_verdict(
            review.get("breakdown") or {},
            review.get("score"),
            review.get("label"),
            review.get("product_name"),
            name,
        )
        caption = verdict or f"{name} reviews — expert tested"
        if verdict:
            overlay = f'<div class="hero-slide__scrim" aria-hidden="true"></div>{caption}'
        else:
            overlay = f"<figcaption>{caption}</figcaption>"
        hero_slides += f'<div class="hero-slide{active}"><img src="{backdrop}" alt="{name}">{overlay}</div>'
        hero_dots += f'<button class="hero-slider__dot{active}" aria-label="Show {name}" aria-current="{"true" if i == 0 else "false"}"></button>'

    # Build latest review cards — the 3 most recently updated reviews, with
    # the same Category · Niche banner as the category sections. The newest
    # review is promoted to a full-width featured spotlight card.
    latest_list = sorted(review_list, key=lambda x: x["updated"], reverse=True)[:3]
    latest_cards = ""
    for i, r in enumerate(latest_list):
        cat_name = next((c for c, slugs in CATEGORY_MAP.items() if r["slug"] in slugs), "")
        latest_cards += review_card(r, cat_name, b, featured=(i == 0))

    # Build category sections — one per category, alphabetical, latest 3 reviews each.
    cat_sections = ""
    for sec_idx, (cat_name, slugs) in enumerate(CATEGORY_MAP.items(), start=1):
        cat_items = [r for r in review_list if r["slug"] in slugs]
        cat_items.sort(key=lambda r: r["updated"], reverse=True)
        top = cat_items[:3]
        if top:
            cards = "".join(review_card(r, cat_name, b) for r in top)
        else:
            cards = f'''<div class="niche-card" style="--cat:{category_color(cat_name)}">
    <div class="niche-card__media"><div class="niche-card__image-wrapper"><img src="{b}/assets/hero-home.svg" alt="Coming soon" loading="lazy"></div><span class="review-card__banner" style="background:{category_color(cat_name)}">{html_mod.escape(cat_name)}</span></div>
    <div class="review-card__body"><h2>Reviews coming soon</h2><p class="review-card__snippet">We're testing products in this category now.</p></div>
</div>'''
        cat_color = category_color(cat_name)
        cat_sections += f'''<div class="category-section" style="--cat:{cat_color}">
    <div class="category-section__header"><h2><span class="sec-num">{sec_idx:02d}</span>{cat_name}</h2><a href="{b}/categories/{_category_slug(cat_name)}/">View all in {cat_name} →</a></div>
    <div class="niche-grid">{cards}</div>
</div>'''
    if not cat_sections:
        cat_sections = '<div class="category-section"><div class="niche-card"><div class="niche-card__image-wrapper"><img src="' + b + '/assets/hero-home.svg" alt="Coming soon"></div><div class="niche-card__body"><h2>Our first guide is in testing</h2><p>Check back shortly for hands-on reviews.</p></div></div></div>'

    # Trending ticker items text
    ticker_items = " · ".join(
        f'<a href="{b}/{n["slug"]}/" class="trending-ticker__item">{n["name"]}</a>'
        for n in niches if n["posts"]
    )

    # Footer
    footer_cats = build_footer_categories(b)
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
    html = html.replace("MEGA_MENU_CSS_PLACEHOLDER", MEGA_MENU_CSS)
    html = html.replace("__APPS_SCRIPT_URL__", form_url)
    html = html.replace("YEAR_PLACEHOLDER", str(datetime.now().year))
    html = html.replace("REACTIONS_JS_PLACEHOLDER", REACTIONS_JS)
    return html



def build_category_page(niche_slug, niche_name, posts, all_slugs, affiliate_tag=""):
    b = SITE_BASE
    # Build post cards — same .niche-card standard as the homepage and
    # category listing pages.
    category = next((c for c, slugs in CATEGORY_MAP.items() if niche_slug in slugs), "")
    post_cards = ""
    for p in posts:
        title = p.get("title", niche_name)
        link = f"{b}/reviews/{niche_slug}/"
        img_src = carousel_img(niche_slug, b)
        post_cards += f'''<div class="niche-card review-card" style="--cat:{category_color(category)}">
    <div class="review-card__media">
        <a href="{link}" tabindex="-1" aria-hidden="true" class="review-card__media-link"><div class="niche-card__image-wrapper"><img src="{img_src}" alt="{html_mod.escape(title)}" loading="lazy"></div></a>
        <span class="review-card__banner" style="background:{category_color(category)}">{category} · {html_mod.escape(niche_name)}</span>
    </div>
    <div class="review-card__body">
        <h2><a href="{link}">{html_mod.escape(title)}</a></h2>
        <p class="review-card__snippet">Expert-tested and reviewed. See why this made our list.</p>
        <div class="review-card__footer">
            <div class="review-card__reactions" data-review="{niche_slug}">
                <span class="reaction-btn is-counter" data-type="like"><span class="reaction-icon">&#x1F44D;</span><span class="reaction-count">0</span></span>
                <span class="reaction-btn is-counter" data-type="love"><span class="reaction-icon">&#x2764;&#xFE0F;</span><span class="reaction-count">0</span></span>
            </div>
            <a href="{link}" class="read-link">Read more →</a>
        </div>
    </div>
</div>'''

    # Nav dropdown (white mega-menu)
    nav_dd = build_category_dropdown(b)

    # Footer
    footer_cats = build_footer_categories(b)
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
    <link rel="icon" type="image/png" href="{b}/assets/favicon-32x32.png">
    <title>{blog_title} | Abvorn</title>
    <meta name="description" content="{meta_desc}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{ --niche-primary: #0a0a0a; --niche-accent: #c98a2c; }}
        {DESIGN_SYSTEM_CSS}
        {PROD_SHOT_CSS}
        
        .top-bar {{ background:#0a0a0a; color:#999; font-size:0.8rem; padding:8px 0; }}
        .top-bar .container {{ display:flex; justify-content:space-between; }}
        header {{ background:#0a0a0a; padding:18px 0; border-bottom:1px solid #2a2a2a; position:sticky; top:0; z-index:100; }}
        .navbar {{ display:flex; justify-content:space-between; align-items:center; max-width:1200px; margin:0 auto; padding:0 20px; }}
        .logo img {{ max-height:44px; width:auto; }}
        .nav-links {{ display:flex; align-items:center; gap:8px; }}
        .nav-links > a, .nav-item > a {{ color:#fff; text-decoration:none; padding:8px 16px; font-weight:600; font-size:0.9rem; border-radius:var(--radius-sm); transition: background var(--duration-fast); }}
        .nav-links > a:hover, .nav-item > a:hover {{ background:rgba(255,255,255,0.08); color: var(--clr-accent); }}
        .nav-item {{ position:relative; }}
        .nav-item > a {{ padding:8px 16px; display:flex; align-items:center; gap:4px; }}
        .nav-item > a::after {{ content:'\u25be'; font-size:0.6rem; opacity:0.5; }}
        .nav-item::after {{ content:''; position:absolute; top:100%; left:0; right:0; height:4px; }}
        .nav-dropdown {{ display:none; position:absolute; top:100%; left:0; margin-top:4px; background:#ffffff; min-width:240px; border-radius:var(--radius-sm); box-shadow:var(--shadow-lg); padding:8px 0; z-index:30; }}
        .nav-item:hover .nav-dropdown, .nav-item:focus-within .nav-dropdown {{ display:block; }}
        .nav-dropdown a {{ display:block; color:#1a1a1a; padding:8px 20px; font-weight:400; font-size:0.85rem; text-decoration:none; }}
        .nav-dropdown a:hover {{ background:#f6f5f2; color: var(--clr-accent-text); }}
        {MEGA_MENU_CSS}
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
        .niche-card {{ border:1px solid var(--clr-light-gray); border-radius:var(--radius-lg); overflow:hidden; transition: transform var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out); background:var(--clr-white); display:flex; flex-direction:column; }}
        .niche-card:hover {{ transform:translateY(-6px); box-shadow:var(--shadow-lg); }}
        .niche-card__image-wrapper {{ aspect-ratio: 4/3; overflow:hidden; background:var(--clr-off-white); }}
        .niche-card img {{ width:100%; height:100%; object-fit:contain; transition: transform var(--duration-slow) var(--ease-out); }}
        .niche-card:hover img {{ transform: scale(1.04); }}
        .review-card__media {{ position:relative; }}
        .review-card__banner {{ position:absolute; top:14px; left:14px; z-index:2; display:inline-block; padding:4px 12px; border-radius:100px; color:#1a1200; font-size:0.64rem; font-weight:800; text-transform:uppercase; letter-spacing:0.07em; box-shadow: var(--shadow-sm); }}
        .review-card__body {{ display:flex; flex-direction:column; flex:1; padding: var(--space-md); }}
        .review-card__body h2 {{ font-size: var(--text-lg); margin:0 0 8px; line-height:1.25; }}
        .review-card__body h2 a {{ color:inherit; text-decoration:none; }}
        .review-card__body h2 a:hover {{ color: var(--clr-accent-text); }}
        .review-card__snippet {{ font-size:0.9rem; color:var(--clr-mid-gray); line-height:1.5; margin:0 0 var(--space-sm); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
        .review-card__footer {{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:auto; padding-top: var(--space-sm); }}
        .review-card__footer .read-link {{ font-weight:700; font-size:0.82rem; color:var(--clr-black); text-decoration:none; border-bottom:2px solid var(--cat, var(--clr-accent)); border-bottom-color: color-mix(in srgb, var(--cat, var(--clr-accent)) 55%, #1a1200); padding-bottom:1px; }}
        .review-card__footer .read-link:hover {{ color: var(--cat, var(--clr-accent-text)); color: color-mix(in srgb, var(--cat, var(--clr-accent-text)) 55%, #1a1200); }}
        .review-card__reactions {{ display:flex; gap:6px; }}
        .review-card__reactions .reaction-btn {{ display:inline-flex; align-items:center; gap:5px; padding:5px 12px; border:1px solid var(--clr-light-gray); border-radius:999px; background:#fff; color:var(--clr-mid-gray); font-size:0.78rem; font-weight:600; font-family:var(--font-body); }}
        .review-card__reactions .reaction-btn.is-counter {{ cursor:default; }}
        .review-card__reactions .reaction-icon {{ font-size:0.9rem; line-height:1; }}
        .review-card__reactions .reaction-count {{ font-weight:700; min-width:14px; text-align:center; }}
        .review-card__updated {{ display:block; font-size:0.72rem; color:#999; margin-top: var(--space-sm); }}

        .footer {{ background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }}
        .footer-grid {{ display:grid; grid-template-columns:1.6fr 1fr 1fr 1fr; gap:var(--space-lg); margin-bottom:var(--space-xl); }}
        .footer-col h4 {{ color:#fff; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:14px; }}
        .footer-col p {{ color:#999; font-size:0.9rem; max-width:32ch; }}
        .footer-col a {{ display:block; color:#999; text-decoration:none; padding:4px 0; font-size:0.9rem; }}
        .footer-col a:hover {{ color:#fff; }}
        .footer-social {{ display:flex; gap:10px; margin-top:16px; }}
        .footer-social a {{ width:44px; height:44px; border-radius:50%; background:#1e1e1e; display:flex; align-items:center; justify-content:center; color:#ccc; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }}
        .footer-social a:hover {{ background:var(--clr-accent); color:#0a0a0a; }}
        .footer-social svg {{ width:16px; height:16px; }}
        .footer-bottom {{ border-top:1px solid #222; padding-top:20px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; font-size:0.85rem; color:#777; }}
        @media (max-width:760px) {{ .footer-grid {{ grid-template-columns:1fr 1fr; }} }}
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
        <div class="nav-item"><a href="{b}/">Categories</a><div class="nav-dropdown nav-dropdown--mega">{nav_dd}</div></div>
        <a href="{b}/">Home</a>
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

<footer class="footer"><div class="container">
    <div class="footer-grid">
        <div class="footer-col"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:28px;width:auto;margin-bottom:8px"><p>Independent product reviews and buying guides, based on real testing.</p><div class="footer-social">{footer_social}</div></div>
        <div class="footer-col"><h4>Categories</h4>{footer_cats}</div>
        <div class="footer-col"><h4>Company</h4><a href="{b}/about.html">About</a></div>
        <div class="footer-col"><h4>Legal</h4><a href="{b}/privacy.html">Privacy policy</a></div>
    </div>
    <div class="footer-bottom"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:20px;width:auto;filter:brightness(0.6)"><span>&copy; {year_str} Abvorn. All rights reserved.</span><span>Reviews updated weekly</span></div>
</div></footer>

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
{REACTIONS_JS_BODY}
</script>
</body>
</html>'''


def build_category_listing_page(category_name, category_slug, items, all_slugs, base=None, affiliate_tag=""):
    """Full page listing every review published in a category (e.g. /categories/audio/)."""
    b = base or SITE_BASE

    # Nav dropdown (white mega-menu)
    nav_dd = build_category_dropdown(b)

    # Footer
    footer_cats = build_footer_categories(b)
    footer_social = render_footer_social()

    # Subscribe form action
    form_url = os.environ.get("APPS_SCRIPT_URL", "")

    title_escaped = html_mod.escape(category_name)
    year_str = str(datetime.now().year)

    blog_title = f"{title_escaped} Reviews"
    meta_desc = f"Independent {category_name.lower()} reviews and buying guides. We test before we recommend."

    # Per-category hero taglines. Falls back to the generic promise.
    CATEGORY_HERO = {
        "audio": "Marketing copy calls everything 'studio-quality.' We check real prices and verified owner feedback to find the headphones and earbuds actually worth your ears.",
    }
    hero_tagline = CATEGORY_HERO.get(category_slug.lower(), "Independent testing, real recommendations. We buy it, test it, and tell you what's actually worth your money.")

    # Group reviews by niche; sort niche sections alphabetically by display name.
    by_niche: dict = {}
    for r in items:
        by_niche.setdefault(r["slug"], []).append(r)
    for slug in by_niche:
        by_niche[slug].sort(key=lambda r: r.get("updated", ""), reverse=True)
    niche_order = sorted(by_niche, key=lambda s: _niche_name(s).lower())

    # "Our latest … Reviews" = the newest reviews across the category (max 4).
    latest_items = sorted(items, key=lambda r: r.get("updated", ""), reverse=True)[:4]

    sections = []
    if items:
        latest_cards = "".join(review_card(r, category_name, b) for r in latest_items)
        sections.append(
            f'<section class="category-section container" id="latest">'
            f'<div class="category-section__header"><h2>Our latest {title_escaped} Reviews</h2></div>'
            f'<div class="posts-grid">{latest_cards}</div></section>'
        )
        for slug in niche_order:
            n = len(by_niche[slug])
            niche_cards = "".join(review_card(r, category_name, b) for r in by_niche[slug])
            sections.append(
                f'<section class="category-section container" id="{slug}">'
                f'<div class="category-section__header"><h2>{html_mod.escape(_niche_name(slug))}</h2>'
                f'<span class="category-section__count">{n} review{"s" if n != 1 else ""}</span></div>'
                f'<div class="posts-grid">{niche_cards}</div></section>'
            )
    else:
        sections.append(
            '<p style="grid-column:1/-1;text-align:center;color:var(--clr-mid-gray);padding:40px 0">Reviews coming soon.</p>'
        )
    sections_html = "".join(sections)

    index_nav = build_category_index(category_name, b, niche_slugs=niche_order or None) if items else ""
    count = len(items)
    count_label = f"{count} review{'s' if count != 1 else ''} published"

    return f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="{b}/assets/favicon-32x32.png">
    <title>{blog_title} | Abvorn</title>
    <meta name="description" content="{meta_desc}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{ --niche-primary: #0a0a0a; --niche-accent: #c98a2c; }}
        {DESIGN_SYSTEM_CSS}
        {PROD_SHOT_CSS}
        
        .top-bar {{ background:#0a0a0a; color:#999; font-size:0.8rem; padding:8px 0; }}
        .top-bar .container {{ display:flex; justify-content:space-between; }}
        header {{ background:#0a0a0a; padding:18px 0; border-bottom:1px solid #2a2a2a; position:sticky; top:0; z-index:100; }}
        .navbar {{ display:flex; justify-content:space-between; align-items:center; max-width:1200px; margin:0 auto; padding:0 20px; }}
        .logo img {{ max-height:44px; width:auto; }}
        .nav-links {{ display:flex; align-items:center; gap:8px; }}
        .nav-links > a, .nav-item > a {{ color:#fff; text-decoration:none; padding:8px 16px; font-weight:600; font-size:0.9rem; border-radius:var(--radius-sm); transition: background var(--duration-fast); }}
        .nav-links > a:hover, .nav-item > a:hover {{ background:rgba(255,255,255,0.08); color: var(--clr-accent); }}
        .nav-item {{ position:relative; }}
        .nav-item > a {{ padding:8px 16px; display:flex; align-items:center; gap:4px; }}
        .nav-item > a::after {{ content:'\\25be'; font-size:0.6rem; opacity:0.5; }}
        .nav-item::after {{ content:''; position:absolute; top:100%; left:0; right:0; height:4px; }}
        .nav-dropdown {{ display:none; position:absolute; top:100%; left:0; margin-top:4px; background:#ffffff; min-width:240px; border-radius:var(--radius-sm); box-shadow:var(--shadow-lg); padding:8px 0; z-index:30; }}
        .nav-item:hover .nav-dropdown, .nav-item:focus-within .nav-dropdown {{ display:block; }}
        .nav-dropdown a {{ display:block; color:#1a1a1a; padding:8px 20px; font-weight:400; font-size:0.85rem; text-decoration:none; }}
        .nav-dropdown a:hover {{ background:#f6f5f2; color: var(--clr-accent-text); }}
        {MEGA_MENU_CSS}
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
        .category-hero__meta {{ display:inline-block; font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:var(--clr-accent-text); margin-bottom: var(--space-md); }}

        .category-index {{ background:var(--clr-off-white); border-bottom:1px solid var(--clr-light-gray); padding:10px 0; }}
        .category-index__inner {{ display:flex; align-items:center; gap: var(--space-lg); flex-wrap:wrap; }}
        .category-index__label {{ font-size:0.72rem; font-weight:800; text-transform:uppercase; letter-spacing:0.08em; color:var(--clr-accent-text); flex-shrink:0; }}
        .category-index__links {{ display:flex; flex-wrap:wrap; align-items:center; gap: var(--space-md); row-gap:8px; }}
        .category-index__link {{ font-family:var(--font-display); font-weight:600; font-size:0.95rem; color:var(--clr-black); text-decoration:none; display:inline-flex; align-items:center; gap:8px; padding:4px 0; border-bottom:2px solid transparent; transition: color var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out); }}
        .category-index__link:hover {{ color:var(--clr-accent-text); border-color:var(--clr-accent); }}
        .category-index__link.is-current {{ color:var(--clr-accent-text); border-color:var(--clr-accent); }}
        .category-index__tick {{ width:7px; height:7px; border-radius:1px; background:var(--cat, var(--clr-accent)); flex-shrink:0; }}

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

        .posts-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(280px,1fr)); gap: var(--space-lg); }}
        .category-section {{ padding-top: var(--space-2xl); scroll-margin-top: 90px; }}
        .category-section__header {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom: var(--space-lg); border-bottom:2px solid var(--clr-black); padding-bottom: var(--space-sm); flex-wrap:wrap; gap: var(--space-sm); }}
        .category-section__header h2 {{ font-size: var(--text-2xl); margin:0; flex:1 1 auto; min-width:0; }}
        .category-section__count {{ font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:var(--clr-mid-gray); }}
        html {{ scroll-behavior:smooth; }}
        @media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior:auto; }} }}
        .niche-card {{ border:1px solid var(--clr-light-gray); border-radius:var(--radius-lg); overflow:hidden; transition: transform var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out); background:var(--clr-white); display:flex; flex-direction:column; }}
        .niche-card:hover {{ transform:translateY(-6px); box-shadow:var(--shadow-lg); }}
        .niche-card__image-wrapper {{ aspect-ratio: 4/3; overflow:hidden; background:var(--clr-off-white); }}
        .niche-card img {{ width:100%; height:100%; object-fit:contain; transition: transform var(--duration-slow) var(--ease-out); }}
        .niche-card:hover img {{ transform: scale(1.04); }}
        .review-card__media {{ position:relative; }}
        .review-card__banner {{ position:absolute; top:14px; left:14px; z-index:2; display:inline-block; padding:4px 12px; border-radius:100px; color:#1a1200; font-size:0.64rem; font-weight:800; text-transform:uppercase; letter-spacing:0.07em; box-shadow: var(--shadow-sm); }}
        .review-card__score {{ position:absolute; right:14px; bottom:14px; z-index:2; display:inline-flex; align-items:baseline; gap:3px; background:rgba(10,10,10,0.92); color:#fff; border-radius:100px; padding:6px 14px; border:1px solid rgba(201,138,44,0.6); backdrop-filter: blur(4px); }}
        .review-card__score-num {{ font-family: var(--font-display); font-size:1.15rem; font-weight:800; color: var(--clr-accent); letter-spacing:-0.02em; line-height:1; }}
        .review-card__score-out {{ font-size:0.7rem; color:#aaa; font-weight:600; }}
        .review-card__body {{ display:flex; flex-direction:column; flex:1; padding: var(--space-md); }}
        .review-card__body h2 {{ font-size: var(--text-lg); margin:0 0 8px; line-height:1.25; }}
        .review-card__body h2 a {{ color:inherit; text-decoration:none; }}
        .review-card__body h2 a:hover {{ color: var(--clr-accent-text); }}
        .review-card__snippet {{ font-size:0.9rem; color:var(--clr-mid-gray); line-height:1.5; margin:0 0 var(--space-sm); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
        .review-card__footer {{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:auto; padding-top: var(--space-sm); }}
        .review-card__footer .read-link {{ font-weight:700; font-size:0.82rem; color:var(--clr-black); text-decoration:none; border-bottom:2px solid var(--cat, var(--clr-accent)); border-bottom-color: color-mix(in srgb, var(--cat, var(--clr-accent)) 55%, #1a1200); padding-bottom:1px; }}
        .review-card__footer .read-link:hover {{ color: var(--cat, var(--clr-accent-text)); color: color-mix(in srgb, var(--cat, var(--clr-accent-text)) 55%, #1a1200); }}
        .review-card__reactions {{ display:flex; gap:6px; }}
        .review-card__reactions .reaction-btn {{ display:inline-flex; align-items:center; gap:5px; padding:5px 12px; border:1px solid var(--clr-light-gray); border-radius:999px; background:#fff; color:var(--clr-mid-gray); font-size:0.78rem; font-weight:600; font-family:var(--font-body); }}
        .review-card__reactions .reaction-btn.is-counter {{ cursor:default; }}
        .review-card__reactions .reaction-icon {{ font-size:0.9rem; line-height:1; }}
        .review-card__reactions .reaction-count {{ font-weight:700; min-width:14px; text-align:center; }}
        .review-card__updated {{ display:block; font-size:0.72rem; color:#999; margin-top: var(--space-sm); }}
        .niche-card--featured {{ grid-column: 1 / -1; display:grid; grid-template-columns: 1.1fr 1fr; align-items:center; }}
        .niche-card--featured .niche-card__image-wrapper {{ aspect-ratio: 16/10; height:100%; }}
        .niche-card--featured .review-card__body {{ padding: var(--space-xl); }}
        .niche-card--featured h2 {{ font-size: var(--text-2xl); }}
        .niche-card--featured .review-card__score-num {{ font-size:1.5rem; }}
        .niche-card--featured .review-card__snippet {{ -webkit-line-clamp:3; }}
        @media (max-width: 760px) {{ .niche-card--featured {{ grid-template-columns: 1fr; }} .niche-card--featured .review-card__body {{ padding: var(--space-md); }} }}

        .footer {{ background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }}
        .footer-grid {{ display:grid; grid-template-columns:1.6fr 1fr 1fr 1fr; gap:var(--space-lg); margin-bottom:var(--space-xl); }}
        .footer-col h4 {{ color:#fff; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:14px; }}
        .footer-col p {{ color:#999; font-size:0.9rem; max-width:32ch; }}
        .footer-col a {{ display:block; color:#999; text-decoration:none; padding:4px 0; font-size:0.9rem; }}
        .footer-col a:hover {{ color:#fff; }}
        .footer-social {{ display:flex; gap:10px; margin-top:16px; }}
        .footer-social a {{ width:44px; height:44px; border-radius:50%; background:#1e1e1e; display:flex; align-items:center; justify-content:center; color:#ccc; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }}
        .footer-social a:hover {{ background:var(--clr-accent); color:#0a0a0a; }}
        .footer-social svg {{ width:16px; height:16px; }}
        .footer-bottom {{ border-top:1px solid #222; padding-top:20px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; font-size:0.85rem; color:#777; }}
        @media (max-width:760px) {{ .footer-grid {{ grid-template-columns:1fr 1fr; }} }}
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
        <div class="nav-item"><a href="{b}/">Categories</a><div class="nav-dropdown nav-dropdown--mega">{nav_dd}</div></div>
        <a href="{b}/">Home</a>
        <a href="{b}/about.html">About</a>
        <a href="{b}/privacy.html">Privacy</a>
    </nav>
</div></header>

<section class="category-hero"><div class="container">
    <span class="category-hero__meta">{title_escaped} · {count_label}</span>
    <h1>{blog_title}</h1>
    <p>{hero_tagline}</p>
</div></section>

{index_nav}

{sections_html}

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

<footer class="footer"><div class="container">
    <div class="footer-grid">
        <div class="footer-col"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:28px;width:auto;margin-bottom:8px"><p>Independent product reviews and buying guides, based on real testing.</p><div class="footer-social">{footer_social}</div></div>
        <div class="footer-col"><h4>Categories</h4>{footer_cats}</div>
        <div class="footer-col"><h4>Company</h4><a href="{b}/about.html">About</a></div>
        <div class="footer-col"><h4>Legal</h4><a href="{b}/privacy.html">Privacy policy</a></div>
    </div>
    <div class="footer-bottom"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:20px;width:auto;filter:brightness(0.6)"><span>&copy; {year_str} Abvorn. All rights reserved.</span><span>Reviews updated weekly</span></div>
</div></footer>

<script>
const APPS_SCRIPT_URL = "{form_url}";
const CATEGORY_SLUG = "{category_slug}";
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

(function() {{
    const links = [...document.querySelectorAll('.category-index__link')];
    if (!links.length || !('IntersectionObserver' in window)) return;
    const targets = links
        .map(l => document.querySelector(l.getAttribute('href')))
        .filter(Boolean);
    if (!targets.length) return;
    const io = new IntersectionObserver((entries) => {{
        for (const e of entries) {{
            if (!e.isIntersecting) continue;
            links.forEach(l => {{
                const active = l.getAttribute('href') === '#' + e.target.id;
                l.classList.toggle('is-current', active);
                if (active) l.setAttribute('aria-current', 'true');
                else l.removeAttribute('aria-current');
            }});
            return;
        }}
    }}, {{ rootMargin: '-10% 0px -70% 0px', threshold: 0 }});
    targets.forEach(t => io.observe(t));
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
{REACTIONS_JS_BODY}
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
</script>"""

REACTIONS_JS_BODY = """(function(){
// Read-only aggregate like/love counters on review cards.
// Visitors react on the individual review page; cards only display the totals.
var URLS = (typeof APPS_SCRIPT_URL !== 'undefined') ? APPS_SCRIPT_URL : '';
var boxes = document.querySelectorAll('.review-card__reactions[data-review]');
if (!boxes.length || !URLS) return;
var slugs = [];
boxes.forEach(function(b){ var s = b.getAttribute('data-review'); if (s && slugs.indexOf(s) === -1) slugs.push(s); });
if (!slugs.length) return;
fetch(URLS, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'reactions', slugs:slugs})})
  .then(function(r){ return r.json(); })
  .then(function(data){
    if (!data || !data.success || !data.reactions) return;
    var byReview = {};
    (data.reactions||[]).forEach(function(r){ byReview[r.slug] = r; });
    for (var i=0;i<boxes.length;i++){
      var slug = boxes[i].getAttribute('data-review');
      var row = byReview[slug]; if (!row) continue;
      var like = boxes[i].querySelector('.reaction-btn[data-type="like"] .reaction-count');
      var love = boxes[i].querySelector('.reaction-btn[data-type="love"] .reaction-count');
      if (like) like.textContent = (row.like||0);
      if (love) love.textContent = (row.love||0);
    }
  })
  .catch(function(){});
})();"""
REACTIONS_JS = "<script>\n" + REACTIONS_JS_BODY + "\n</script>"

ARTICLE_REACTIONS_JS = """<script>
(function(){
// Interactive like/love on the review page. Records to the aggregate endpoint
// and shows the current total. The visitor's own vote is remembered locally.
var bar = document.querySelector('.reactions-bar[data-review]');
if (!bar) return;
var URLS = (typeof APPS_SCRIPT_URL !== 'undefined') ? APPS_SCRIPT_URL : '';
var slug = bar.getAttribute('data-review');
var btns = [].slice.call(bar.querySelectorAll('.reaction-btn'));
var VID_KEY = 'abvorn_visitor_id';
if (!localStorage.getItem(VID_KEY)) localStorage.setItem(VID_KEY, 'v' + Math.random().toString(36).slice(2));
var vid = localStorage.getItem(VID_KEY);
var RKEY = 'abvorn_reactions_' + slug;
var mine = {};
try { mine = JSON.parse(localStorage.getItem(RKEY) || '{}'); } catch(e) {}
function paint(){
  btns.forEach(function(btn){
    var type = btn.getAttribute('data-type');
    btn.classList.toggle('active', type === 'like' && !!mine.like);
    btn.classList.toggle('loved', type === 'love' && !!mine.love);
  });
}
function refresh(){
  if (!URLS) return;
  fetch(URLS, {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'reactions', slugs:[slug]})})
    .then(function(r){ return r.json(); })
    .then(function(data){
      if (!data || !data.success) return;
      (data.reactions||[]).forEach(function(row){
        if (row.slug !== slug) return;
        var like = bar.querySelector('.reaction-btn[data-type="like"] .reaction-count');
        var love = bar.querySelector('.reaction-btn[data-type="love"] .reaction-count');
        if (like) like.textContent = (row.like||0);
        if (love) love.textContent = (row.love||0);
      });
    })
    .catch(function(){});
}
btns.forEach(function(btn){
  btn.addEventListener('click', function(){
    if (!URLS) return;
    var type = btn.getAttribute('data-type');
    var on = !(mine[type]||false);
    btn.disabled = true;
    fetch(URLS, {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action:'reaction', slug:slug, type:type, visitor:vid})})
      .then(function(r){ return r.json(); })
      .then(function(data){
        btn.disabled = false;
        if (!data || !data.success) return;
        mine[type] = on;
        localStorage.setItem(RKEY, JSON.stringify(mine));
        paint();
        refresh();
      })
      .catch(function(){ btn.disabled = false; });
  });
});
paint();
setTimeout(refresh, 300);
})();
</script>"""

RPS_JS = """<script>
(function(){
// ── Abvorn Regret Probability Score (client-side) ──────────────
var DATA = document.getElementById('abvorn-rps-data');
if(!DATA)return;
var rpsData;
try{rpsData=JSON.parse(DATA.textContent.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&'))}catch(e){return}
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



def build_article_page(niche_slug, niche_name, post_title, article_html, intro, product_name, meta_desc, all_slugs, products=None, pexels_key="", amazon_tag="", form_url="", hero_img="", google_client_id="", related_niches=None, published_date=None, updated_date=None, article_id=None):
    from abvorn.core.verdict import clean_product_name
    b = SITE_BASE
    t = amazon_tag or os.environ.get("AMAZON_TAG", "viraltestco-20")
    article_url = f"{_SITE_URL}/reviews/{niche_slug}/"
    share = SHARE_HTML_T.replace("TITLE_T", html_mod.escape(post_title)).replace("URL_T", article_url)
    # Sanitize AI-generated content up front: strip duplicated chart fragments,
    # embedded document wrappers, mojibake, and duplicated Introduction headings.
    intro = sanitize_article_html(intro)
    article_html = sanitize_article_html(article_html)
    # Guarantee per-product photography even when the AI writer omits images.
    article_html = inject_product_photos(article_html, products or [])
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
            matrix_rows += f"<tr><td>{uc}</td><td>{html_mod.escape(clean_product_name(prod.get('name','Product')))}</td><td>{html_mod.escape(why)}</td></tr>"
    matrix_html = f'<div class="decision-matrix"><table><thead><tr><th>Use Case</th><th>Product</th><th>Why</th></tr></thead><tbody>{matrix_rows}</tbody></table></div>' if matrix_rows else ""
    verdict_html = ""
    hero_img_html = ""
    _verdict_summary = None
    verdict_chart_data = {"overall": 0, "label": "", "breakdown": {}, "productName": product_name}
    if products and len(products) > 0:
        p0 = products[0]
        p0_url = p0.get("url", "")
        p0_aff = affiliate_url(p0_url, t) if p0_url else f"https://www.amazon.com/s?k={niche_slug.replace('-','+')}&tag={t}"
        # Abvorn Verdict Engine — score the product
        try:
            from abvorn.core.verdict import AbvornVerdictEngine
            engine = AbvornVerdictEngine(weight_overrides=load_verdict_weights())
            verdict = engine.score_product(niche_slug, p0)
            detail_url = f"{b}/reviews/{niche_slug}/"
            verdict_html = render_verdict_card(verdict, p0.get('name', product_name), p0_aff, detail_url)
            _verdict_summary = verdict.get("summary")
        except Exception:
            verdict_html = f"""<div class="verdict-box"><div class="verdict-title">{html_mod.escape(clean_product_name(p0.get('name', product_name)))}</div><div class="verdict-price">{p0.get('price', 'Check price')}</div><div class="verdict-for"><strong>Best for:</strong> {html_mod.escape(p0.get('description', 'Anyone looking for the best in this category.'))}</div><div class="verdict-not-for"><strong>Don't buy this if:</strong> You need a different use case covered by our other picks below.</div><a class="buy-btn" href="{p0_aff}" target="_blank" rel="sponsored">Check Price on Amazon</a></div>"""
            verdict = None
        # Build verdict data JSON for the radar chart
        verdict_chart_data = {}
        if verdict and "breakdown" in verdict:
            verdict_chart_data = {
                "overall": verdict.get("overall", 0),
                "label": verdict.get("label", ""),
                "breakdown": verdict["breakdown"],
                "productName": clean_product_name(p0.get("name", product_name))
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
            verdict_chart_data = {"overall": round(overall, 1), "label": "", "breakdown": breakdown, "productName": clean_product_name(p0.get("name", product_name))}
        # Hero visual: the "Our Choice" pick on a studio backdrop. Fall back to
        # the passed hero_img (legacy) then the raw product thumbnail.
        hero_pick = ""
        if products:
            hero_pick = hero_pick_html(p0, verdict_chart_data.get("overall", ""), verdict_chart_data.get("label", ""), p0_aff, b, niche_slug)
        if hero_pick:
            hero_img_html = hero_pick
        elif hero_img:
            hero_img_html = hero_img
        elif p0.get("image"):
            hero_img_html = f'<img class="hero-plain" src="{html_mod.escape(upgrade_product_image(p0["image"]))}" alt="{html_mod.escape(clean_product_name(p0.get("name", product_name)))}" loading="eager">'
    verdict_json = json.dumps(verdict_chart_data, ensure_ascii=False).replace('<', '\\u003c')
    bread = breadcrumb_schema([
        ("Abvorn", "/"),
        (f"Best {niche_name}", f"/{niche_slug}/"),
        (html_mod.escape(post_title)[:60], f"/reviews/{niche_slug}/"),
    ])
    # RPS data: embed all product scores for client-side regret prediction
    rps_data = {"products": [], "niche": niche_slug}
    try:
        from abvorn.core.verdict import AbvornVerdictEngine
        ve = AbvornVerdictEngine(weight_overrides=load_verdict_weights())
        for prod in (products or []):
            v = ve.score_product(niche_slug, prod)
            rps_data["products"].append({
                "name": clean_product_name(prod.get("name", "Product")),
                "price": prod.get("price", ""),
                "scores": v["breakdown"],
                "overall": v["overall"],
                "label": v["label"],
                "url": affiliate_url(prod.get("url", ""), t) or "",
            })
    except Exception:
        pass
    rps_json = json.dumps(rps_data, ensure_ascii=False).replace('<', '\\u003c')
    related_html = ""
    if related_niches:
        cards = "".join(
            f'<a class="cat-card" href="{b}/{r["slug"]}/"><div class="cat-name">{r["name"]}</div><div class="cat-count">{r.get("posts", 0)} reviews</div></a>'
            for r in related_niches
        )
        related_html = f'<section class="section"><div class="container"><div class="section-title">Related Categories</div><div class="grid-3">{cards}</div></div></section>'
    # Guaranteed FAQ section + FAQPage JSON-LD (generated from rubric + products).
    faq_html = ""
    faq_jsonld = ""
    try:
        faq_html, faq_questions = build_faq(
            niche_slug, niche_name, products or [], product_name,
            price_floor_for(niche_slug),
            verdict_summary=_verdict_summary,
            top_score=verdict_chart_data.get("overall"),
        )
        faq_jsonld = faq_schema(faq_questions) if faq_questions else ""
    except Exception:
        pass
    # Build nav dropdown (white mega-menu)
    nav_dd = build_category_dropdown(b)
    # Footer
    footer_cats = build_footer_categories(b)
    footer_social = render_footer_social()

    if article_id:
        article_html = rewrite_affiliate_urls(article_html, article_id)
        product_cards = rewrite_affiliate_urls(product_cards, article_id)

    # Strategic flow: hook first, then the verdict, then the evidence, then FAQ.
    verdict_explainer = info_dot(
        "The Abvorn Verdict Engine scores every product out of 10 across the "
        "criteria that matter most for this category — the weighted rubric is "
        "shown in the chart below. Scores are data-driven, not sponsored."
    )
    chart_explainer = info_dot(
        "Each spoke is one weighted criterion for this category. The closer the "
        "line reaches 10, the better that product scored — so you can see at a "
        "glance where it wins and where it falls short."
    )
    matrix_explainer = info_dot(
        "Every pick below is scored with the same rubric on the same data — the "
        "table lets you compare use cases before you read the full breakdown."
    )
    verdict_html = verdict_html.replace(
        '<div class="av-badge">Abvorn Verdict</div>',
        f'<div class="av-badge">Abvorn Verdict</div>{verdict_explainer}',
        1,
    ) if '<div class="av-badge">' in verdict_html else verdict_html
    chart_html = (
        '<div class="chart-section">'
        f'<h3 class="section-title">Performance Breakdown {chart_explainer}</h3>'
        '<div class="chart-wrapper"><canvas id="verdictChart"></canvas></div>'
        '<p class="chart-note">Scores out of 10. Based on the Abvorn Verdict Engine.</p>'
        '</div>'
    )
    if matrix_html:
        matrix_html = (
            '<div class="decision-matrix-wrap">'
            f'<h3 class="section-title">At a glance {matrix_explainer}</h3>'
            f'{matrix_html}</div>'
        )

    article_body_content = render_article_body(
        disclosure=FTC_DISCLOSURE,
        intro=intro,
        verdict_html=verdict_html,
        chart_html=chart_html,
        article_html=article_html,
        matrix_html=matrix_html,
        faq_html=faq_html,
        reactions=(
            f'<div class="reactions-bar" data-review="{niche_slug}">'
            '<span class="reactions-label">Did this review help?</span>'
            '<button type="button" class="reaction-btn" data-type="like" aria-label="Like this review"><span class="reaction-icon">&#x1F44D;</span><span class="reaction-count">0</span></button>'
            '<button type="button" class="reaction-btn" data-type="love" aria-label="Love this review"><span class="reaction-icon">&#x2764;&#xFE0F;</span><span class="reaction-count">0</span></button>'
            '</div>'
        ),
        share=share,
        related_html=related_html,
        product_cards=product_cards,
        further_reading='<div class="further-reading"><h3>Further Reading</h3><ul>__FURTHER_READING__</ul></div>',
        cta=cta,
    )

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
    <link rel="icon" type="image/png" href="{b}/assets/favicon-32x32.png">
    <title>{title_escaped} | Abvorn</title>
    <meta name="description" content="{meta_escaped}">
    <link rel="canonical" href="{article_url}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://m.media-amazon.com">
    <link rel="dns-prefetch" href="https://www.googletagmanager.com">
    <link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    {bread}
    {faq_jsonld}
    <script id="abvorn-rps-data" type="application/json">{rps_json}</script>
    <style>
        :root {{ --niche-primary: #0a0a0a; --niche-accent: #c98a2c; }}
        {DESIGN_SYSTEM_CSS}
        {VERDICT_CARD_CSS}
        {ARTICLE_DESIGN_CSS}
        
        .top-bar {{ background:#0a0a0a; color:#999; font-size:0.8rem; padding:8px 0; }}
        .top-bar .container {{ display:flex; justify-content:space-between; align-items:center; }}
        header {{ background:#0a0a0a; padding:18px 0; border-bottom:1px solid #2a2a2a; position:sticky; top:0; z-index:100; }}
        .navbar {{ display:flex; justify-content:space-between; align-items:center; max-width:1200px; margin:0 auto; padding:0 20px; }}
        .logo img {{ max-height:44px; width:auto; }}
        .nav-links {{ display:flex; align-items:center; gap:8px; }}
        .nav-links > a, .nav-item > a {{ color:#fff; text-decoration:none; padding:8px 16px; font-weight:600; font-size:0.9rem; border-radius:var(--radius-sm); transition: background var(--duration-fast); }}
        .nav-links > a:hover, .nav-item > a:hover {{ background:rgba(255,255,255,0.08); color: var(--clr-accent); }}
        .nav-item {{ position:relative; }}
        .nav-item > a {{ padding:8px 16px; display:flex; align-items:center; gap:4px; }}
        .nav-item > a::after {{ content:'\u25be'; font-size:0.6rem; opacity:0.5; }}
        .nav-item::after {{ content:''; position:absolute; top:100%; left:0; right:0; height:4px; }}
        .nav-dropdown {{ display:none; position:absolute; top:100%; left:0; margin-top:4px; background:#ffffff; min-width:240px; border-radius:var(--radius-sm); box-shadow:var(--shadow-lg); padding:8px 0; z-index:30; }}
        .nav-item:hover .nav-dropdown, .nav-item:focus-within .nav-dropdown {{ display:block; }}
        .nav-dropdown a {{ display:block; color:#1a1a1a; padding:8px 20px; font-weight:400; font-size:0.85rem; text-decoration:none; }}
        .nav-dropdown a:hover {{ background:#f6f5f2; color: var(--clr-accent-text); }}
        {MEGA_MENU_CSS}
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
        .hero-image-wrapper {{ position:relative; border-radius:var(--radius-md); display:flex; align-items:center; justify-content:center; min-height:260px; padding:var(--space-md); }}
        .hero-image-wrapper img.hero-plain {{ width:100%; height:auto; max-height:320px; object-fit:contain; border-radius:var(--radius-md); }}
        @media (max-width:860px) {{ .article-hero .hero-grid {{ grid-template-columns:1fr; }} .hero-image-wrapper {{ order:-1; min-height:auto; padding:0; }} }}
        /* ===== VERDICT RADAR CHART ===== */
        .chart-section {{ margin:var(--space-xl) 0; padding:var(--space-lg); background:var(--clr-white); border-radius:var(--radius-md); border:1px solid var(--clr-light-gray); }}
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
        .product-section {{ display:grid; grid-template-columns:1fr; gap:var(--space-xl); }}
        .product-card {{ display:grid; grid-template-columns:1fr; gap:var(--space-md); background:var(--clr-white); border:1px solid var(--clr-light-gray); border-radius:var(--radius-md); padding:var(--space-lg); transition: transform var(--duration-base), box-shadow var(--duration-base); }}
        .product-card:hover {{ transform:translateY(-4px); box-shadow:var(--shadow-md); }}
        .product-card img {{ width:100%; height:auto; max-height:360px; object-fit:contain; border-radius:var(--radius-sm); background:var(--clr-white); }}
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

        .reactions-bar {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin:var(--space-xl) 0; padding-top:var(--space-lg); border-top:1px solid var(--clr-light-gray); }}
        .reactions-bar .reactions-label {{ font-size:0.8rem; font-weight:700; color:var(--clr-mid-gray); margin-right:4px; }}
        .reactions-bar .reaction-btn {{ display:inline-flex; align-items:center; gap:6px; padding:7px 16px; border:1px solid var(--clr-light-gray); border-radius:999px; background:#fff; color:var(--clr-mid-gray); font-size:0.85rem; font-weight:600; font-family:var(--font-body); cursor:pointer; transition:all var(--duration-fast) var(--ease-out); }}
        .reactions-bar .reaction-btn:hover {{ border-color:var(--clr-accent); color:var(--clr-accent-text); }}
        .reactions-bar .reaction-btn.active {{ border-color:var(--clr-accent); background:var(--clr-accent); color:#1a1200; }}
        .reactions-bar .reaction-btn.loved {{ border-color:#c0392b; color:#c0392b; background:#fde8e4; }}
        .reactions-bar .reaction-icon {{ font-size:1rem; line-height:1; }}
        .reactions-bar .reaction-count {{ font-weight:700; min-width:16px; text-align:center; }}

        .further-reading {{ margin-top:var(--space-xl); border-top:1px solid var(--clr-light-gray); padding-top:var(--space-lg); }}
        .further-reading h3 {{ font-size:var(--text-lg); margin-bottom:var(--space-md); }}
        .further-reading ul {{ list-style:none; padding:0; }}
        .further-reading li {{ margin-bottom:8px; }}
        .further-reading a {{ color:var(--clr-primary); text-decoration:none; font-weight:600; }}
        .further-reading a:hover {{ color:var(--clr-accent-text); }}

        .decision-matrix-wrap {{ margin:var(--space-xl) 0; }}
        .decision-matrix {{ margin:var(--space-lg) 0; overflow-x:auto; background:var(--clr-white); border:1px solid var(--clr-light-gray); border-radius:var(--radius-md); padding:var(--space-lg); }}
        .decision-matrix table {{ width:100%; border-collapse:collapse; font-size:var(--text-sm); }}
        .decision-matrix th {{ background:var(--clr-white); text-align:left; padding:12px 16px; font-weight:700; color:var(--clr-black); font-family:var(--font-display); border-bottom:2px solid var(--clr-light-gray); }}
        .decision-matrix td {{ padding:12px 16px; border-bottom:1px solid var(--clr-light-gray); color:var(--clr-mid-gray); vertical-align:top; }}
        .decision-matrix tr:last-child td {{ border-bottom:none; }}
        .decision-matrix td:first-child {{ font-weight:700; color:var(--clr-black); white-space:nowrap; }}
        .decision-matrix td:last-child {{ color:var(--clr-off-black); }}

        .grid-3 {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:var(--space-lg); }}
        .cat-card {{ padding:var(--space-lg); border:1px solid var(--clr-light-gray); border-radius:var(--radius-md); transition:all .25s cubic-bezier(.4,0,.2,1); box-shadow:var(--shadow-sm); text-decoration:none; display:block; background:var(--clr-off-white); position:relative; overflow:hidden; }}
        .cat-card::after {{ content:''; position:absolute; bottom:0; left:20%; right:20%; height:3px; background:var(--clr-accent); border-radius:3px 3px 0 0; transform:scaleX(0); transition:transform .25s cubic-bezier(.4,0,.2,1); }}
        .cat-card:hover {{ box-shadow:var(--shadow-md); transform:translateY(-4px); text-decoration:none; }}
        .cat-card:hover::after {{ transform:scaleX(1); }}
        .cat-card .cat-name {{ font-weight:700; font-size:1.1rem; color:var(--clr-black); margin-bottom:4px; font-family:var(--font-display); }}
        .cat-card .cat-count {{ font-size:.85rem; color:var(--clr-mid-gray); }}

        .product-shot {{ max-width:100%; }}
        .article-body .product-shot--body img {{ max-width:100%; margin:0; height:100%; object-fit:contain; }}
        .product-shot img {{ margin:0 !important; }}

        .footer {{ background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }}
        .footer-grid {{ display:grid; grid-template-columns:1.6fr 1fr 1fr 1fr; gap:var(--space-lg); margin-bottom:var(--space-xl); }}
        .footer-col h4 {{ color:#fff; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:14px; }}
        .footer-col p {{ color:#999; font-size:0.9rem; max-width:32ch; }}
        .footer-col a {{ display:block; color:#999; text-decoration:none; padding:4px 0; font-size:0.9rem; }}
        .footer-col a:hover {{ color:#fff; }}
        .footer-social {{ display:flex; gap:10px; margin-top:16px; }}
        .footer-social a {{ width:44px; height:44px; border-radius:50%; background:#1e1e1e; display:flex; align-items:center; justify-content:center; color:#ccc; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }}
        .footer-social a:hover {{ background:var(--clr-accent); color:#0a0a0a; }}
        .footer-social svg {{ width:16px; height:16px; }}
        .footer-bottom {{ border-top:1px solid #222; padding-top:20px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; font-size:0.85rem; color:#777; }}
        @media (max-width:860px) {{ .content-wrapper {{ grid-template-columns:1fr; }} .product-card {{ grid-template-columns:1fr; }} }}
        @media (max-width:760px) {{ .footer-grid {{ grid-template-columns:1fr 1fr; }} }}
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
        <div class="nav-item"><a href="{b}/">Categories</a><div class="nav-dropdown nav-dropdown--mega">{nav_dd}</div></div>
        <a href="{b}/">Home</a>
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

<footer class="footer"><div class="container">
    <div class="footer-grid">
        <div class="footer-col"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:28px;width:auto;margin-bottom:8px"><p>Independent product reviews and buying guides, based on real testing.</p><div class="footer-social">{footer_social}</div></div>
        <div class="footer-col"><h4>Categories</h4>{footer_cats}</div>
        <div class="footer-col"><h4>Company</h4><a href="{b}/about.html">About</a></div>
        <div class="footer-col"><h4>Legal</h4><a href="{b}/privacy.html">Privacy policy</a></div>
    </div>
    <div class="footer-bottom"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:20px;width:auto;filter:brightness(0.6)"><span>&copy; {year_str} Abvorn. All rights reserved.</span><span>Reviews updated weekly</span></div>
</div></footer>

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
{ARTICLE_REACTIONS_JS}
<script id="abvorn-verdict-data" type="application/json">{verdict_json}</script>
<script>
document.addEventListener('DOMContentLoaded', function() {{
    var dataEl = document.getElementById('abvorn-verdict-data');
    if (!dataEl) return;
    var verdictData;
    try {{ verdictData = JSON.parse(dataEl.textContent.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&')); }} catch(e) {{ return; }}
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

def write_files(niche_slug, articles, state, pexels_key="", amazon_tag="", form_url="", hero_images=None, google_client_id=""):
    """Write all HTML files to docs/ directory."""
    all_slugs = sorted([n["slug"] for n in state["niches"]], key=lambda s: _slugify_title(s).lower())
    hero_images = hero_images or {}
    niche_name = next((n["name"] for n in state["niches"] if n["slug"] == niche_slug), niche_slug.replace("-", " ").title())

    # Published reviews for homepage + category listing pages.
    reviews = scan_published_reviews("docs")
    today = datetime.now().strftime("%Y-%m-%d")

    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    for slug, post_list in articles.items():
        for a in post_list:
            reviews.append({
                "slug": slug,
                "name": next((n["name"] for n in state["niches"] if n["slug"] == slug), slug.replace("-", " ").title()),
                "title": a.get("post_title", ""),
                "updated": today,
                "rel": f"/reviews/{slug}/",
            })

    # Collect all published posts across niches (drives feed, sitemap, niche pages)
    all_posts = [{"title": r["title"], "slug": r["rel"].lstrip("/")} for r in reviews]

    # Write root index (premium homepage)
    (docs / "index.html").write_text(build_homepage(state, form_url, reviews=reviews, base=SITE_BASE), encoding="utf-8")
    print(f"  Written: docs/index.html")

    # Write category listing pages (one per category, e.g. /categories/audio/)
    for cat_name, cat_slugs in CATEGORY_MAP.items():
        cat_slug = _category_slug(cat_name)
        cat_items = [r for r in reviews if r["slug"] in cat_slugs]
        cat_items.sort(key=lambda r: r["updated"], reverse=True)
        cat_dir = docs / "categories" / cat_slug
        cat_dir.mkdir(parents=True, exist_ok=True)
        (cat_dir / "index.html").write_text(
            build_category_listing_page(cat_name, cat_slug, cat_items, all_slugs, base=SITE_BASE, affiliate_tag=amazon_tag),
            encoding="utf-8",
        )
        print(f"  Written: docs/categories/{cat_slug}/index.html")

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
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="{b}/assets/favicon-32x32.png"><title>{title} | Abvorn</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Inter',sans-serif;color:#333;line-height:1.6}}
.top-bar{{background:#0a0a0a;color:#999;font-size:0.8rem;padding:8px 0}}
.top-bar .container{{display:flex;justify-content:space-between;max-width:1200px;margin:0 auto;padding:0 20px}}
header{{background:#0a0a0a;padding:18px 0;border-bottom:1px solid #2a2a2a;position:sticky;top:0;z-index:100}}
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
            page_path.write_text(full_page, encoding="utf-8")
            print(f"  Written: docs/{page_name}")

    # Write category pages (post slugs point to reviews/{slug} for article pages)
    for n in state["niches"]:
        niche_reviews = [r for r in reviews if r["slug"] == n["slug"]]
        latest = max(niche_reviews, key=lambda r: r.get("updated", "")) if niche_reviews else None
        niche_posts = [{"title": latest["title"], "slug": f"reviews/{n['slug']}"}] if latest else \
                      [{"title": a.get("post_title", ""), "slug": f"reviews/{n['slug']}"} for a in articles.get(n["slug"], [])]
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

    # Write article pages (under docs/reviews/{slug}/). Each article gets its own
    # dated file so published reviews accumulate; index.html always mirrors the
    # latest so existing links (and category pages) keep working.
    for slug, post_list in articles.items():
        for i, a in enumerate(post_list):
            post_dir = docs / "reviews" / slug
            post_dir.mkdir(parents=True, exist_ok=True)
            hero_img_html = hero_images.get(slug, "")
            _sorted_niches = sorted(state["niches"], key=lambda n: n["name"].lower())
            related = [n for n in _sorted_niches if n["slug"] != slug][:4]
            article_html = build_article_page(slug, niche_name, a["post_title"], a["article_html"],
                                              a["intro"], a["product_name"], a["meta_description"],
                                              all_slugs, a.get("products"), pexels_key, amazon_tag, form_url, hero_img_html, google_client_id,
                                              related_niches=related, article_id=f"{slug}-{i}")
            try:
                verify_page(article_html)
            except ValueError as e:
                logger.error(f"❌ Page verification failed for {slug}/{fname}: {e}")
                raise
            date_str = datetime.now().strftime("%Y-%m-%d")
            suffix = "" if i == 0 else f"-{i}"
            fname = f"{_title_slug(a['post_title'])}-{date_str}{suffix}.html"
            (post_dir / fname).write_text(article_html, encoding="utf-8")
            print(f"  Written: docs/reviews/{slug}/{fname} (article)")
            if i == len(post_list) - 1:
                (post_dir / "index.html").write_text(article_html, encoding="utf-8")
                print(f"  Written: docs/reviews/{slug}/index.html (latest)")
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
        if not slug_path.endswith("/"):
            slug_path = slug_path.rsplit("/", 1)[0] + "/"
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
_ga_id = os.environ.get("GA_MEASUREMENT_ID", "G-J0GTXLC86C")
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
<p>We use cookies to analyze traffic and improve your experience. <a href="/abvorn/privacy/">Privacy Policy</a></p>
<button class="btn-secondary" onclick="declineAnalytics()">Decline</button>
<button class="btn" onclick="acceptAnalytics()">Accept</button>
</div>
<script>
(function(){var c=document.cookie.match(/(?:^|;) *analytics_consent=([^;]*)/);if(c&&c[1]==="granted"){return}var b=document.getElementById("cookie-banner");if(b){b.classList.add("show")}window.acceptAnalytics=function(){document.cookie="analytics_consent=granted; max-age=31536000; path=/; SameSite=Lax";b.classList.remove("show");if(typeof loadAnalytics==="function"){loadAnalytics()}};window.declineAnalytics=function(){document.cookie="analytics_consent=denied; max-age=31536000; path=/; SameSite=Lax";b.classList.remove("show")}})();
</script>'''


def esc_json(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", "")


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


def build_site_header(b="", all_slugs=None):
    """Site-wide header: top bar + sticky navbar with clickable category mega-menu.

    Single source of truth so every page (home, category, niche, article, static)
    renders the exact same header. Uses SITE_BASE when b is empty.
    """
    b = b or SITE_BASE
    dd_items = build_category_dropdown(b)
    dropdown = f'<div class="nav-item"><a href="#">Categories</a><div class="nav-dropdown nav-dropdown--mega">{dd_items}</div></div>'
    return f'''
<div class="top-bar"><div class="container"><span>Independent testing. No sponsored placements.</span><span>Updated weekly</span></div></div>
<header><div class="container navbar">
    <a href="{b}/" class="logo"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:44px;width:auto"></a>
    <button class="nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav-links">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <nav class="nav-links" id="nav-links">
        {dropdown}
        <a href="{b}/">Home</a>
        <a href="{b}/about.html">About</a>
        <a href="{b}/privacy.html">Privacy</a>
    </nav>
</div></header>
<script>
(function(){{var b=document.getElementById("nav-toggle");var n=document.getElementById("nav-links");if(!b||!n)return;b.addEventListener("click",function(){{var o=n.classList.toggle("open");b.setAttribute("aria-expanded",o?"true":"false")}})}})();
</script>'''


def build_site_footer(b=""):
    """Site-wide footer: brand + social, wide Categories column, Company & Legal.

    Single source of truth so every page renders the exact same footer. Company
    and Legal share the last column; Categories gets the wide 2fr column.
    Uses SITE_BASE when b is empty.
    """
    b = b or SITE_BASE
    year_str = str(datetime.now().year)
    return f'''<footer class="footer"><div class="container">
    <div class="footer-grid">
        <div class="footer-col"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:28px;width:auto;margin-bottom:8px"><p>Independent product reviews and buying guides, based on real testing.</p><div class="footer-social">{render_footer_social()}</div></div>
        <div class="footer-col"><h4>Categories</h4>{build_footer_categories(b)}</div>
        <div class="footer-col">
            <h4>Company</h4><a href="{b}/about.html">About</a>
            <h4>Legal</h4><a href="{b}/privacy.html">Privacy policy</a>
        </div>
    </div>
    <div class="footer-bottom"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:20px;width:auto;filter:brightness(0.6)"><span>&copy; {year_str} Abvorn. All rights reserved.</span><span>Reviews updated weekly</span></div>
</div></footer>'''


def nav_html(categories, current=""):
    return build_site_header()


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
    <link rel="icon" type="image/png" href="__SITE_BASE__/assets/favicon-32x32.png">
    <title>Abvorn – Reviews Based on Real Testing, Not Spec Sheets</title>
    <meta name="description" content="Independent product reviews and buying guides. We test before we recommend.">
    <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        ''' + DESIGN_SYSTEM_CSS + '''
        ''' + PROD_SHOT_CSS + '''
        /* FIX: header/hero/footer are fixed brand chrome, always black-on-white —
           they must NOT use the adaptive --clr-black/--clr-white/--clr-off-white
           tokens, which the dark-mode media query above intentionally flips for
           body content. Using those tokens here was the actual bug behind the
           invisible nav (white text on a header that turned white) and the
           invisible hero button (background and text both collapsing toward
           black). Hardcoded values below are deliberate, not an oversight. */
        .top-bar { background:#0a0a0a; color:#999; font-size:0.8rem; padding:8px 0; }
        .top-bar .container { display:flex; justify-content:space-between; }
        header { background:#0a0a0a; padding:18px 0; position:sticky; top:0; z-index:100; box-shadow:0 2px 10px rgba(0,0,0,0.25); }
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
        MEGA_MENU_CSS_PLACEHOLDER
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
        .trending-ticker__track { display:inline-flex; align-items:center; will-change:transform; animation: ticker-scroll 30s linear infinite; }
        .trending-ticker__label { font-weight:700; margin-right:15px; color:#1a1200; }
        .trending-ticker__inner { display:inline-flex; align-items:center; flex-shrink:0; }
        .trending-ticker__item { color:#1a1200; text-decoration:none; padding:0 10px; }
        .trending-ticker__item:hover { color:#000; text-decoration:underline; }
        @keyframes ticker-scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
        .hero { background:#f6f5f2; padding: var(--space-2xl) 0; position:relative; overflow:hidden; }
        .hero::before { content:''; position:absolute; top:-20%; right:-8%; width:560px; height:560px; border-radius:50%; background:radial-gradient(circle, rgba(201,138,44,0.14), transparent 65%); pointer-events:none; }
        .hero-grid { display:grid; grid-template-columns: 1fr 1fr; gap: var(--space-xl); align-items:center; position:relative; }
        .hero-eyebrow { display:inline-flex; align-items:center; gap:8px; font-size:0.72rem; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color: var(--clr-accent-text); background:rgba(201,138,44,0.12); border:1px solid rgba(201,138,44,0.32); padding:6px 14px; border-radius:100px; margin-bottom: var(--space-md); }
        .hero h1 { font-size: clamp(2.1rem, 4.4vw, var(--text-4xl)); margin-bottom: var(--space-md); color:#0a0a0a; letter-spacing:-0.03em; font-weight:700; }
        .hero p { font-size: var(--text-lg); color:#555; max-width:46ch; margin-bottom: var(--space-lg); }
        .hero .btn { background:#1a1a1a; color:#fff; }
        .hero .btn:hover { background: var(--clr-accent); color:#1a1200; }
        .hero-cta { width:100%; display:flex; justify-content:center; margin-bottom: var(--space-lg); }
        .hero-cta .btn { margin: 0; }
        .hero-trust { display:flex; flex-wrap:wrap; justify-content:center; gap:8px 22px; margin-top: var(--space-lg); }
        .hero-trust span { display:inline-flex; align-items:center; gap:7px; font-size:0.78rem; font-weight:600; color:#666; }
        .hero-trust svg { width:15px; height:15px; color: var(--clr-accent); flex:none; }
        .hero-slider { position:relative; border-radius: var(--radius-lg); overflow:hidden; box-shadow: var(--shadow-xl); aspect-ratio: 4/3; background:#fff; }
        .hero-slide { position:absolute; inset:0; opacity:0; transition:opacity 0.9s var(--ease-out); }
        .hero-slide.active { opacity:1; }
        .hero-slide img { width:100%; height:100%; object-fit:contain; display:block; }
        .hero-slide figcaption { position:absolute; left:0; right:0; bottom:0; background:linear-gradient(transparent, rgba(0,0,0,0.85)); color:#fff; padding: 52px var(--space-lg) var(--space-md); font-weight:600; font-size:0.95rem; }
        .hero-slide__scrim { position:absolute; inset:0; background:linear-gradient(to top, rgba(10,10,10,0.96) 0%, rgba(10,10,10,0.62) 34%, rgba(10,10,10,0.18) 52%, rgba(10,10,10,0) 60%); pointer-events:none; }
        .hero-slide .hero-verdict { position:absolute; left: var(--space-md); right: var(--space-md); bottom: var(--space-md); background:#fff; color:#0a0a0a; border-radius: var(--radius-md); box-shadow: 0 10px 30px rgba(0,0,0,0.35); padding: var(--space-sm) var(--space-md) var(--space-sm); }
        .hero-verdict__head { display:flex; justify-content:space-between; align-items:center; gap: var(--space-md); margin-bottom:6px; }
        .hero-verdict__eyebrow { display:block; font-size:0.55rem; font-weight:800; text-transform:uppercase; letter-spacing:0.14em; color: var(--clr-accent-text); margin-bottom:2px; }
        .hero-verdict__product { display:block; font-family: var(--font-display); font-size:0.88rem; font-weight:700; letter-spacing:-0.01em; line-height:1.2; color:#0a0a0a; }
        .hero-verdict__overall { text-align:right; flex:none; }
        .hero-verdict__num { font-family: var(--font-display); font-size:1.9rem; font-weight:800; letter-spacing:-0.03em; line-height:1; display:block; color:#0a0a0a; }
        .hero-verdict__num small { font-size:0.75rem; font-weight:600; color:#888; letter-spacing:0; margin-left:2px; }
        .hero-verdict__label { font-size:0.55rem; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:#fff; background:#0a0a0a; padding:2px 8px; border-radius:100px; display:inline-block; margin-top:3px; }
        .hero-verdict__bars { display:flex; flex-direction:column; gap:5px; border-top:1.5px solid #0a0a0a; padding-top: var(--space-sm); }
        .hero-verdict__bar { display:grid; grid-template-columns: 1fr 3fr 30px; align-items:center; gap:10px; font-size:0.66rem; }
        .hero-verdict__bar-label { font-weight:600; color:#555; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .hero-verdict__bar-track { height:6px; background:#e7e3da; border-radius:3px; overflow:hidden; }
        .hero-verdict__bar-fill { display:block; height:100%; width:0; background:#0a0a0a; border-radius:3px; transition: width 0.75s var(--ease-out) 0.15s; }
        .hero-slide.active .hero-verdict__bar-fill { width: var(--score); }
        .hero-verdict__bar.is-top .hero-verdict__bar-fill { background: var(--clr-accent); }
        .hero-verdict__bar.is-top .hero-verdict__bar-label { color:#0a0a0a; font-weight:700; }
        .hero-verdict__bar.is-weak .hero-verdict__bar-label { color:#a0988a; }
        .hero-verdict__bar.is-weak .hero-verdict__bar-fill { background:#cfc9bd; }
        .hero-verdict__bar-score { text-align:right; font-weight:700; font-variant-numeric: tabular-nums; color:#0a0a0a; }
        .hero-slider__dots { position:absolute; top: var(--space-sm); right: var(--space-sm); left:auto; bottom:auto; transform:none; display:flex; z-index:6; }
        .hero-slider__dot { width:44px; height:44px; border:none; background:transparent; cursor:pointer; padding:0; display:flex; align-items:center; justify-content:center; }
        .hero-slider__dot::before { content:''; width:8px; height:8px; border-radius:50%; background:rgba(10,10,10,0.38); transition: background var(--duration-fast) var(--ease-out); }
        .hero-slider__dot.active::before { background: var(--clr-accent); }
        .hero-slider__dot:focus-visible { outline:2px solid var(--clr-accent); outline-offset:2px; border-radius:100px; }
        @media (max-width: 860px) { .hero-grid { grid-template-columns: 1fr; } }

        .how-we-test { background:#0a0a0a; color:#fff; padding: var(--space-2xl) 0; }
        .how-we-test__inner { max-width:1200px; margin:0 auto; padding:0 var(--space-lg); }
        .how-we-test__intro { margin-bottom: var(--space-xl); }
        .how-we-test__intro h2 { color:#fff; font-size: var(--text-3xl); margin-bottom:8px; }
        .how-we-test__intro p { color:#999; max-width:52ch; margin:0; }
        .hwt-steps { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px,1fr)); gap: var(--space-lg); }
        .hwt-step { border-left:2px solid rgba(201,138,44,0.5); padding:0 0 0 var(--space-lg); }
        .hwt-step__num { font-family: var(--font-display); font-size: var(--text-xl); font-weight:800; color: var(--clr-accent); letter-spacing:-0.02em; }
        .hwt-step h3 { color:#fff; font-size: var(--text-lg); margin:6px 0; }
        .hwt-step p { color:#999; font-size:0.9rem; margin:0; line-height:1.55; }

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
        .subscribe-form .input { width:260px; background:#fff; border:2px solid var(--clr-light-gray); color:#1a1a1a; }
        .subscribe-form .input::placeholder { color:#8a8a8a; }
        .subscribe-form .input:focus { border-color:var(--clr-accent); }
        .subscribe-form .hp-field { position:absolute; left:-9999px; }
        .subscribe-form .btn { background: var(--clr-accent); color:#1a1200; font-size:1rem; font-weight:800; padding:0.85em 1.7em; gap:8px; box-shadow: 0 6px 22px rgba(201,138,44,0.4); }
        .subscribe-form .btn:hover { background:#e0a23f; transform: scale(1.045); box-shadow: 0 8px 28px rgba(201,138,44,0.55); }
        .subscribe-form .btn svg { width:18px; height:18px; }
        .subscribe-msg { flex-basis:100%; font-size:0.85rem; color:#666; margin-top:8px; }
        @media (max-width: 700px) { .subscribe-inner { flex-direction:column; align-items:flex-start; } .subscribe-form .input { width:100%; } }

        .guides-section { padding: var(--space-2xl) 0; }
        .latest-reviews-section { padding: var(--space-2xl) 0; }
        .section-eyebrow { display:block; font-size:0.7rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; color: var(--clr-accent-text); margin-bottom:6px; }
        .category-section { margin-bottom: var(--space-2xl); }
        .category-section__header { display:flex; justify-content:space-between; align-items:flex-end; gap: var(--space-md); margin-bottom: var(--space-lg); border-bottom:2px solid var(--clr-black); padding-bottom: var(--space-sm); flex-wrap:wrap; }
        .category-section__header h2 { font-size: var(--text-2xl); margin:0; display:flex; align-items:baseline; gap:12px; flex:1 1 auto; min-width:0; }
        .category-section__header h2 .sec-num { font-size:0.8rem; font-weight:800; color: var(--cat, var(--clr-accent-text)); letter-spacing:0.04em; }
        .category-section__header a { font-size:0.85rem; font-weight:700; color: var(--clr-black); text-decoration:none; white-space:nowrap; display:inline-flex; align-items:center; flex-shrink:0; }
        .category-section__header a:hover { text-decoration:underline; }
        .niche-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px,1fr)); gap: var(--space-lg); }
        .niche-card { border:1px solid var(--clr-light-gray); border-radius:var(--radius-lg); overflow:hidden; transition: transform var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out); background:var(--clr-white); display:flex; flex-direction:column; }
        .niche-card:hover { transform:translateY(-6px); box-shadow:var(--shadow-lg); }
        .niche-card__image-wrapper { aspect-ratio: 4/3; overflow:hidden; background:var(--clr-off-white); }
        .niche-card img { width:100%; height:100%; object-fit:contain; transition: transform var(--duration-slow) var(--ease-out); }
        .niche-card:hover img { transform: scale(1.04); }
        .review-card__media { position:relative; }
        .review-card__banner { position:absolute; top:14px; left:14px; z-index:2; display:inline-block; padding:4px 12px; border-radius:100px; color:#1a1200; font-size:0.64rem; font-weight:800; text-transform:uppercase; letter-spacing:0.07em; box-shadow: var(--shadow-sm); }
        .review-card__score { position:absolute; right:14px; bottom:14px; z-index:2; display:inline-flex; align-items:baseline; gap:3px; background:rgba(10,10,10,0.92); color:#fff; border-radius:100px; padding:6px 14px; border:1px solid rgba(201,138,44,0.6); backdrop-filter: blur(4px); }
        .review-card__score-num { font-family: var(--font-display); font-size:1.15rem; font-weight:800; color: var(--clr-accent); letter-spacing:-0.02em; line-height:1; }
        .review-card__score-out { font-size:0.7rem; color:#aaa; font-weight:600; }
        .review-card__body { display:flex; flex-direction:column; flex:1; padding: var(--space-md); }
        .review-card__body h2 { font-size: var(--text-lg); margin:0 0 8px; line-height:1.25; }
        .review-card__body h2 a { color:inherit; text-decoration:none; }
        .review-card__body h2 a:hover { color: var(--clr-accent-text); }
        .review-card__snippet { font-size:0.9rem; color:var(--clr-mid-gray); line-height:1.5; margin:0 0 var(--space-sm); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
        .review-card__footer { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:auto; padding-top: var(--space-sm); }
        .review-card__footer .read-link { font-weight:700; font-size:0.82rem; color:var(--clr-black); text-decoration:none; border-bottom:2px solid var(--cat, var(--clr-accent)); border-bottom-color: color-mix(in srgb, var(--cat, var(--clr-accent)) 55%, #1a1200); padding-bottom:1px; }
        .review-card__footer .read-link:hover { color: var(--cat, var(--clr-accent-text)); color: color-mix(in srgb, var(--cat, var(--clr-accent-text)) 55%, #1a1200); }
        .review-card__reactions { display:flex; gap:6px; }
        .review-card__reactions .reaction-btn { display:inline-flex; align-items:center; gap:5px; padding:5px 12px; border:1px solid var(--clr-light-gray); border-radius:999px; background:#fff; color:var(--clr-mid-gray); font-size:0.78rem; font-weight:600; font-family:var(--font-body); }
        .review-card__reactions .reaction-btn.is-counter { cursor:default; }
        .review-card__reactions .reaction-icon { font-size:0.9rem; line-height:1; }
        .review-card__reactions .reaction-count { font-weight:700; min-width:14px; text-align:center; }
        .review-card__updated { display:block; font-size:0.72rem; color:#999; margin-top: var(--space-sm); }
        .niche-card--featured { grid-column: 1 / -1; display:grid; grid-template-columns: 1.1fr 1fr; align-items:center; }
        .niche-card--featured .niche-card__image-wrapper { aspect-ratio: 16/10; height:100%; }
        .niche-card--featured .review-card__body { padding: var(--space-xl); }
        .niche-card--featured h2 { font-size: var(--text-2xl); }
        .niche-card--featured .review-card__score-num { font-size:1.5rem; }
        .niche-card--featured .review-card__snippet { -webkit-line-clamp:3; }
        @media (max-width: 760px) { .niche-card--featured { grid-template-columns: 1fr; } .niche-card--featured .review-card__body { padding: var(--space-md); } }

        .category-group { display: none; }
        .category-group.visible { display: block; }
        .show-more-btn { display: inline-flex; align-items: center; gap: var(--space-sm); margin: var(--space-xl) auto 0; padding: 0.85em 1.5em; font-family: var(--font-body); font-weight: 700; font-size: var(--text-sm); text-transform: uppercase; letter-spacing: 0.06em; color: var(--clr-accent-text); background: none; border: 2px solid var(--clr-accent); border-radius: var(--radius-sm); cursor: pointer; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }
        .show-more-btn:hover { background: var(--clr-accent); color: var(--clr-black); }
        .show-more-btn svg { width: 16px; height: 16px; transition: transform var(--duration-fast) var(--ease-out); }
        .show-more-btn:hover svg { transform: translateX(4px); }

        .footer { background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }
        .footer-grid { display:grid; grid-template-columns: 1.6fr 2fr 1fr; gap: var(--space-lg); margin-bottom: var(--space-xl); }
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
        <div class="nav-item"><a href="#niches">Categories ▾</a><div class="nav-dropdown nav-dropdown--mega">CATEGORY_DROPDOWN_PLACEHOLDER</div></div>
        <a href="__SITE_BASE__/">Home</a>
        <a href="__SITE_BASE__/about.html">About</a>
        <a href="__SITE_BASE__/privacy.html">Privacy</a>
    </nav>
</div></header>
<div class="trending-ticker"><div class="container"><div class="trending-ticker__track"><div class="trending-ticker__inner"><span class="trending-ticker__label">Latest updates:</span><span id="trending-items">LATEST_UPDATES_PLACEHOLDER</span></div><div class="trending-ticker__inner" aria-hidden="true"><span class="trending-ticker__label">Latest updates:</span><span>LATEST_UPDATES_PLACEHOLDER</span></div></div></div></div>

<section class="hero"><div class="container hero-grid">
    <div>
        <span class="hero-eyebrow"><svg aria-hidden="true" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>How we work</span>
        <h1>Clear, honest guidance on what's actually worth your money.</h1>
        <p>Every guide starts with the same question: what would actually be worth buying? We compare real prices, specifications, and verified customer feedback, then break down the trade-offs in plain language &mdash; so you can go from confused to confident in minutes, not hours.</p>
        <div class="hero-cta"><a href="#latest-reviews" class="btn">See our latest guides</a></div>
        <div class="hero-trust">
            <span><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>Independently researched</span>
            <span><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>No sponsored placements</span>
            <span><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>Scored on 5 criteria</span>
        </div>
    </div>
    <div class="hero-slider" id="hero-slider">
        HERO_SLIDES_PLACEHOLDER
        <div class="hero-slider__dots">HERO_DOTS_PLACEHOLDER</div>
    </div>
</div></section>

<section class="how-we-test"><div class="how-we-test__inner">
    <div class="how-we-test__intro">
        <span class="section-eyebrow">Our method</span>
        <h2>Reviews based on real prices and real feedback — not spec sheets.</h2>
        <p>Every score you see on this site follows the same repeatable process. No paid placements, no editorial bias &mdash; just a consistent method.</p>
    </div>
    <div class="hwt-steps">
        <div class="hwt-step"><div class="hwt-step__num">01</div><h3>Research</h3><p>We shortlist candidates on price, specs, and verified owner feedback across retailers.</p></div>
        <div class="hwt-step"><div class="hwt-step__num">02</div><h3>Score</h3><p>Every product is scored on the same 5 weighted criteria before any ranking is drawn.</p></div>
        <div class="hwt-step"><div class="hwt-step__num">03</div><h3>Recommend</h3><p>We recommend the one we'd actually buy &mdash; and say plainly when a product falls short.</p></div>
    </div>
</div></section>

<section class="stats-band"><div class="container stats-grid">
    <div><div class="stat-icon"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg></div><div class="stat-number" data-target="STAT_GUIDES_COUNT">0</div><div class="stat-label">Guides published</div></div>
    <div><div class="stat-icon"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg></div><div class="stat-number" data-target="STAT_CATEGORIES_COUNT">0</div><div class="stat-label">Categories covered</div></div>
    <div><div class="stat-icon"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M5 8l7-5 7 5M5 8a3 3 0 106 0M13 8a3 3 0 106 0"/></svg></div><div class="stat-number" data-target="STAT_PRODUCTS_COUNT">0</div><div class="stat-label">Products compared</div></div>
    <div><div class="stat-icon"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 11-3.5-7.1"/><path d="M21 3v6h-6"/></svg></div><div class="stat-number">Weekly</div><div class="stat-label">Review cycle</div></div>
</div></section>

<section class="latest-reviews-section container" id="latest-reviews">
    <span class="section-eyebrow">Fresh this week</span>
    <div class="category-section__header"><h2>Latest reviews</h2></div>
    <div class="niche-grid">LATEST_REVIEWS_PLACEHOLDER</div>
</section>

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

<section class="guides-section container" id="niches">
    CATEGORY_SECTIONS_PLACEHOLDER
</section>

<footer class="footer"><div class="container">
    <div class="footer-grid">
        <div class="footer-col">
            <img src="__SITE_BASE__/logo.svg" alt="Abvorn" style="max-height:28px;width:auto;margin-bottom:8px">
            <p>Independent product research and buying guides, built to help you decide faster.</p>
            <div class="footer-social">FOOTER_SOCIAL_PLACEHOLDER</div>
        </div>
        <div class="footer-col"><h4>Categories</h4>FOOTER_CATEGORY_LINKS_PLACEHOLDER</div>
        <div class="footer-col">
            <h4>Company</h4><a href="__SITE_BASE__/about.html">About</a>
            <h4>Legal</h4><a href="__SITE_BASE__/privacy.html">Privacy policy</a>
        </div>
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
REACTIONS_JS_PLACEHOLDER
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



