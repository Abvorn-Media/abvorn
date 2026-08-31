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
SITE_BASE = "https://abvorn.com"

# Canonical font link — every page type must use this exact string so the site
# loads one consistent type system (Libre Franklin display, Inter body,
# JetBrains Mono for data labels).
FONT_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">'

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
h1 { font-size: var(--text-4xl); letter-spacing: -0.02em; font-weight: 800; }
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
.skip-link { position: absolute; top: -100px; left: 8px; z-index: 200; background: var(--clr-accent); color: var(--clr-black); padding: 10px 18px; border-radius: 0 0 var(--radius-sm) var(--radius-sm); font-weight: 700; font-size: 0.85rem; text-decoration: none; transition: top var(--duration-fast) var(--ease-out); }
.skip-link:focus { top: 0; color: var(--clr-black); }

/* ── Compare & Watchlist ──────────────────────────────────────── */
.av-compare-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: transparent; color: var(--clr-accent); border: 1px solid var(--clr-accent);
  padding: 4px 12px; border-radius: 100px; font-size: 0.78rem; font-weight: 700;
  cursor: pointer; font-family: var(--font-body); transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); margin-top: 8px;
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
header { background:#0a0a0a; padding:18px 0; position:sticky; top:0; z-index:100; box-shadow:0 2px 10px rgba(0,0,0,0.25); }
.navbar { display:flex; justify-content:space-between; align-items:center; max-width:1200px; margin:0 auto; padding:0 20px; }
.logo img { max-height:44px; width:auto; }
.nav-links { display:flex; align-items:center; }
.nav-links > a, .nav-item > a { color:#fff; text-decoration:none; margin-left:28px; font-weight:600; font-size:0.9rem; }
.nav-links > a:hover, .nav-item > a:hover { color: var(--clr-accent); }
.nav-item { position:relative; margin-left:28px; }
.nav-item > a { margin-left:0; display:flex; align-items:center; gap:4px; }
.nav-item > a::after { content:'▾'; font-size:0.6rem; opacity:0.5; }
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
    .nav-item > a::after { display:none; }
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
.av-number{font-size:3rem;font-weight:700;font-family:var(--font-display);color:#1a1a1a;line-height:1;letter-spacing:-.03em}
.av-outof{font-size:1.2rem;color:#666;font-weight:600}
.av-label-row{display:flex;flex-direction:column;gap:2px}
.av-label{font-size:1.1rem;font-weight:700;color:var(--clr-accent-text,#996015);font-family:var(--font-display)}
.av-product{font-size:1.2rem;font-weight:800;color:#1a1a1a;font-family:var(--font-display);line-height:1.3;margin:0 0 4px}
.av-breakdown{display:flex;flex-direction:column;gap:8px;margin-bottom:20px}
.av-bar-row{display:flex;align-items:center;gap:12px}
.av-bar-label{flex:0 0 140px;font-size:.82rem;font-weight:600;color:#666;text-align:right}
.av-bar-track{flex:1;height:8px;background:#e8e8e8;border-radius:100px;overflow:hidden}
.av-bar-fill{height:100%;border-radius:100px;transition:width .6s cubic-bezier(.4,0,.2,1)}
.av-bar-score{flex:0 0 36px;font-size:.85rem;font-weight:700;color:#1a1a1a;text-align:right}
.av-summary{font-size:.95rem;color:#666;line-height:1.5;margin-bottom:20px}
.av-cta{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
@media(max-width:640px){.av-score-row{flex-direction:column;align-items:flex-start;gap:8px}.av-bar-label{flex:0 0 100px;font-size:.75rem}.abvorn-verdict{padding:20px 16px}}
"""

CLICK_DOMAIN = os.environ.get("CLICK_DOMAIN", "https://abvorn.com")
_SITE_URL = os.environ.get("SITE_URL", "https://abvorn.com").rstrip("/")
if "github.io" in _SITE_URL or not _SITE_URL.startswith("http"):
    # Stale GitHub Pages base leaked into committed canonicals (audit D1).
    # Never emit anything but the real domain, regardless of env.
    _SITE_URL = "https://abvorn.com"

CTA_BANNER = """
<div class="cta-banner">
<h3>Want this guide as a PDF?</h3>
<p>Enter your email and we'll send this review straight to your inbox as a clean, printable PDF — specs, scores, and buy links included.</p>
<form id="cta-lead-form" onsubmit="submitLead(event)" data-source="cta_banner">
    <input type="text" name="_gotcha" style="display:none" tabindex="-1" autocomplete="off">
    <div class="cta-lead-row">
        <input type="email" id="cta-email" placeholder="your@email.com" class="input" required>
        <button type="submit" class="btn">Send me the PDF</button>
    </div>
    <p class="lead-msg" style="font-size:0.8rem;margin-top:10px;"></p>
</form>
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
            f'href="/abvorn/compare.html?{qs}"><span class="av-compare-icon">⊕</span> Compare</a>'
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
    from src.click_tracker import record_product_url
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
        record_product_url(article_id, idx, original_url)
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
# The article body element, used to scope snippet extraction away from
# chrome like the cookie banner, nav, and footer.
_ARTICLE_RE = re.compile(r"<article[^>]*>(.*?)</article>", re.S)
# Paragraphs that are chrome rather than review copy.
_COOKIE_RE = re.compile(r"cook(ie|ies)|consent|privacy policy", re.I)
_UPDATED_RE = re.compile(r"^Updated:\s*\d{4}-\d{2}-\d{2}", re.I)
_SHARE_RE = re.compile(r"facebook|pinterest|related categories|share on|tweet", re.I)
_WIDGET_RE = re.compile(r"alert me|\$\d+\.\d{2}|price drop|track price", re.I)
# The "Our Choice" hero pick product photo rendered into the article hero.
_HERO_PICK_IMG_RE = re.compile(r'<aside class="hero-pick".*?hero-pick__media"><img src="([^"]+)"', re.S)
# Fallback: the article body's studio product shot (product-shot figure),
# which carries the reviewed product itself rather than a category illustration.
_NICHE_HERO_IMG_RE = re.compile(r'<figure class="product-shot[^"]*">\s*<img class="product-shot__img" src="([^"]+)"', re.S)
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
    if _COOKIE_RE.search(text) or _UPDATED_RE.search(text) or _SHARE_RE.search(text) or _WIDGET_RE.search(text):
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

    Extraction is scoped to the <article> element when present and skips
    boilerplate (cookie consent, navigation) so card snippets never show
    chrome text instead of review copy.
    """
    body = html
    m = _ARTICLE_RE.search(html)
    if m:
        body = m.group(1)
    m = _INTRO_RE.search(body)
    if m:
        text = _clean_snippet(m.group(1))
        if text:
            return text
    m = _EXCERPT_RE.search(body)
    if m:
        text = _clean_snippet(m.group(1))
        if text:
            return text
    for m in _ANY_P_RE.finditer(body):
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
            breakdown, bd_overall, bd_label, bd_product = _parse_verdict_data(html)
            # Dated article pages carry the niche's canonical verdict from
            # index.html as fallback, so hero cards always have criteria.
            if not breakdown:
                breakdown, bd_overall, bd_label, bd_product = index_breakdown, index_overall, index_label, index_product
            # Prefer the structured verdict JSON. Only fall back to the loose
            # prose regex when no structured overall exists, and only accept a
            # plausible 0-10 score — the regex otherwise latches onto product
            # model numbers in prose (e.g. "Sony WH-1000XM5" -> 1000).
            score = bd_overall
            if score is None:
                m_score = _VERDICT_OVERALL_RE.search(html)
                cand = float(m_score.group(1)) if m_score else None
                if cand is not None and 0 < cand <= 10:
                    score = cand
            elif not (isinstance(score, (int, float)) and 0 < float(score) <= 10):
                # Guard against corrupt structured data so cards never show a
                # nonsensical score.
                score = None
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


# Mojibake signatures: byte sequences that result from decoding UTF-8 text as
# the Windows ANSI codepage (cp1252) and re-encoding as UTF-8. Every double-
# encoded em dash / curly quote / box-drawing char starts with one of these
# prefixes. Matching against the raw UTF-8 bytes catches both the strict cp1252
# path (e.g. \u00c3\u00a2\u00e2\u0082\u00ac = "â€") and the latin-1 fallback
# path used for cp1252-undefined bytes (\u00c3\u00a2\u00c2\u0090 etc.).
MOJIBAKE_SIGNATURES = (
    b"\xc3\xa2",  # â  (every 3-byte UTF-8 char decoded via latin-1/cp1252)
    b"\xc3\x83\xc2",  # Ã  (2-byte chars decoded as latin-1 then re-encoded)
    b"\xc3\x82",  # Â  (C2-prefixed chars like nbsp via latin-1 fallback)
    b"\xef\xbf\xbd",  # U+FFFD replacement char
)

# Context: true mojibake also requires the bytes following the prefix to be
# part of the double-encoded run. To avoid false positives on genuine text
# (rare in English but possible in foreign-language snippets), only flag when
# the prefix is followed by a cp1252/latin-1 range byte.
_MOJIBAKE_PREFIX_RX = re.compile(
    b"(?:\xc3\xa2[\xe2\xc2\x80-\x9f\xa0-\xbf\x82\xac]"
    b"|\xc3\x83\xc2[\x80-\xbf]"
    b"|\xc3\x82[\x80-\xbf]"
    b"|\xef\xbf\xbd)"
)


def find_mojibake(text: str) -> list:
    """Return a list of mojibake byte signatures found in the given text.

    Text is encoded back to UTF-8 and scanned for double-encoded character
    signatures. An empty list means the content is clean.
    """
    encoded = text.encode("utf-8")
    found = []
    for m in _MOJIBAKE_PREFIX_RX.finditer(encoded):
        sig = m.group(0)
        ctx = encoded[max(0, m.start() - 12): m.end() + 8]
        found.append({"offset": m.start(), "sig": sig.hex(" "), "context": ctx.hex(" ")})
    return found


# Byte-level repair for the two codec-fallback variants that cannot round-trip
# through a single cp1252 pass (the corruption tool fell back to latin-1 for
# cp1252-undefined bytes 0x90/0x9D). Keyed by exact mojibake bytes observed in
# the wild; value is the correct UTF-8 encoding of the intended character.
MOJIBAKE_FIX_TABLE = {
    # \u00e2\u2022\u0090 -> U+2550 (box drawings double horizontal) CSS separator
    b"\xc3\xa2\xe2\x80\xa2\xc2\x90": "\u2550".encode("utf-8"),
    # \u00e2\u20ac\u009d -> U+201D (right double quotation mark)
    b"\xc3\xa2\xe2\x82\xac\xc2\x9d": "\u201d".encode("utf-8"),
}


def _reverse_cp1252_run(run: str) -> str:
    """Reverse one cp1252->utf8 double-encoded non-ASCII run.

    Original UTF-8 bytes B were decoded as cp1252 (chars C) then re-encoded as
    UTF-8. Reverse: C.encode('cp1252') -> B, B.decode('utf-8'). Returns the
    fixed string, or the original run when reversal is impossible.
    """
    try:
        return run.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return run


def repair_mojibake(text: str) -> str:
    """Return the text with double-encoded UTF-8 corruption repaired.

    First applies the byte-level fix table (codec-fallback variants), then
    reverses every remaining cp1252 double-encoding on non-ASCII runs.
    """
    data = text.encode("utf-8")
    changed = False
    for bad, good in MOJIBAKE_FIX_TABLE.items():
        if bad in data:
            data = data.replace(bad, good)
            changed = True
    chars = data.decode("utf-8")
    out = []
    i, n = 0, len(chars)
    while i < n:
        if ord(chars[i]) < 0x80:
            out.append(chars[i])
            i += 1
            continue
        j = i
        while j < n and ord(chars[j]) >= 0x80:
            j += 1
        run = chars[i:j]
        fixed = _reverse_cp1252_run(run)
        out.append(fixed)
        if fixed != run:
            changed = True
        i = j
    if not changed:
        return text
    return "".join(out)


def check_encoding(text: str, label: str = "page") -> bool:
    """Guard: raise ValueError if generated content contains mojibake.

    Runs before a page is written to disk so corrupted output is blocked at
    publish time instead of silently shipping to the site.
    """
    hits = find_mojibake(text)
    if hits:
        preview = ", ".join(h["sig"] for h in hits[:6])
        raise ValueError(
            f"Mojibake detected in {label}: {len(hits)} occurrence(s) "
            f"(signatures: {preview}). Fix the encoding before publishing."
        )
    return True


def write_checked(path: Path, text: str, label: str, state=None) -> None:
    """Write a page after validating its encoding.

    Blocks mojibake from reaching the published docs/ tree: raises ValueError
    if the content carries double-encoded UTF-8 signatures.

    When the content review gate is ON, the page is staged under
    data/review_queue/ instead of being written to docs/ so a human can approve
    it before it goes live.
    """
    check_encoding(text, label=label)
    try:
        from abvorn.core.review_gate import write_gated
    except Exception:
        write_gated = None
    if write_gated is not None:
        actual = write_gated(path, text, state=state)
        if Path(actual) != Path(path):
            logger.info(f"REVIEW GATE: staged {label} -> {actual}")
    else:
        path.write_text(text, encoding="utf-8")


def verify_page(html_content: str) -> bool:
    """Quick regression guard for generated article pages.

    Raises ValueError if a required asset is missing from the rendered HTML or
    if the page contains mojibake (double-encoded UTF-8).
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
    check_encoding(html_content, label="article page")
    return True


def review_card(item, category, b, featured=False):
    """One review card with a category+niche banner, verdict score, snippet, and bottom-aligned CTA.

    Uses the review's "Our Choice" studio product photo when available so the
    universal photography treatment carries through to cards; falls back to the
    generated niche hero image otherwise.
    """
    title = html_mod.escape(item["title"])
    _slug = item.get("slug", "")
    _rel = item.get("rel")
    if not _rel:
        _rel = f"/{_slug}/" if _slug.startswith("reviews/") else f"/reviews/{_slug}/"
    href = f'{b.rstrip("/")}{_rel if _rel.startswith("/") else "/" + _rel}'
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
        {score_html}
    </div>
    <div class="review-card__body">
        <span class="review-card__banner" style="background:{color}">{html_mod.escape(category)} · {html_mod.escape(item["name"])}</span>
        {updated_html}
        <h2><a href="{href}">{title}</a></h2>
        {snippet_html}
        <div class="review-card__footer">
            <div class="review-card__reactions" data-review="{item["slug"]}">
                <span class="reaction-btn is-counter" data-type="like"><span class="reaction-icon">&#x1F44D;</span><span class="reaction-count">0</span></span>
                <span class="reaction-btn is-counter" data-type="love"><span class="reaction-icon">&#x2764;&#xFE0F;</span><span class="reaction-count">0</span></span>
            </div>
            <a href="{href}" class="read-link">Read review →</a>
        </div>
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


def build_category_index(category_name, b="", niche_slugs=None, label=None):
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
        '<nav class="category-index" aria-label="Guides in this category" style="--cat:' + color + '">'
        '<div class="container category-index__inner">'
        f'<span class="category-index__label">{label or "In this category"}</span>'
        f'<div class="category-index__links">{"".join(links)}</div>'
        '</div></nav>'
    )


MEGA_MENU_CSS = """
.nav-item:hover .nav-dropdown.nav-dropdown--mega, .nav-item:focus-within .nav-dropdown.nav-dropdown--mega { display:flex; opacity:1; transform:translateY(0); transition:opacity var(--duration-fast) var(--ease-out),transform var(--duration-fast) var(--ease-out); }
@starting-style {
    .nav-item:hover .nav-dropdown.nav-dropdown--mega, .nav-item:focus-within .nav-dropdown.nav-dropdown--mega { opacity:0; transform:translateY(6px); }
}
.nav-dropdown.nav-dropdown--mega { flex-wrap:wrap; gap:6px 8px; min-width:600px; max-width:90vw; padding:14px 18px; right:0; left:auto; }
.nav-dropdown.nav-dropdown--mega .category-group { display:block; flex:1 1 200px; min-width:170px; }
.nav-dropdown.nav-dropdown--mega .category-label { display:block; color:var(--clr-accent-text,var(--clr-accent,#c98a2c)); font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; padding:4px 20px 2px; }
.nav-dropdown.nav-dropdown--mega a { padding:6px 20px; }
@media (max-width:640px) {
    .nav-dropdown.nav-dropdown--mega { display:block; min-width:0; max-width:none; padding:0; opacity:1; transform:none; }
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
        url = f"{SITE_BASE}/{page_path}"
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
    # Guard against placeholder product names ("Product", blank, generic) leaking
    # into the hero-verdict — fall back to the niche name so no slide shows a
    # literal placeholder to readers.
    _product = (product or "").strip()
    if not _product or _product.lower() in ("product", "n/a", "tbd", "coming soon", "placeholder", name.lower()):
        _product = name or _product
    title = _truncate(_product, 40)
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
    for cat_name, slugs in CATEGORY_MAP.items():
        cat_items = [r for r in review_list if r["slug"] in slugs]
        cat_items.sort(key=lambda r: r["updated"], reverse=True)
        top = cat_items[:3]
        if top:
            cards = "".join(review_card(r, cat_name, b) for r in top)
        else:
            cards = f'''<div class="niche-card" style="--cat:{category_color(cat_name)}">
    <div class="niche-card__media"><div class="niche-card__image-wrapper"><img src="{b}/assets/hero-home.svg" alt="Coming soon" loading="lazy"></div></div>
    <div class="review-card__body"><span class="review-card__banner" style="background:{category_color(cat_name)}">{html_mod.escape(cat_name)}</span><h2>Reviews coming soon</h2><p class="review-card__snippet">We're testing products in this category now.</p></div>
</div>'''
        cat_color = category_color(cat_name)
        cat_sections += f'''<div class="category-section" style="--cat:{cat_color}">
    <div class="category-section__header"><h2><span class="cat-tick" aria-hidden="true"></span>{cat_name}</h2><a href="{b}/categories/{_category_slug(cat_name)}/">View all in {cat_name} →</a></div>
    <div class="niche-grid">{cards}</div>
</div>'''
    if not cat_sections:
        cat_sections = '<div class="category-section"><div class="niche-card"><div class="niche-card__image-wrapper"><img src="' + b + '/assets/hero-home.svg" alt="Coming soon"></div><div class="niche-card__body"><h2>Our first guide is in testing</h2><p>Check back shortly for hands-on reviews.</p></div></div></div>'

    # Trending ticker items text. Drives off the actually-published reviews
    # rather than the gitignored cycle_state.json so the ticker survives a
    # fresh checkout (where every niche reports posts=0 and would render
    # "No reviews yet").
    published_slugs = {r["slug"] for r in review_list}
    ticker_items = " · ".join(
        f'<a href="{b}/{n["slug"]}/" class="trending-ticker__item">{n["name"]}</a>'
        for n in niches if n["slug"] in published_slugs
    )

    # Footer
    footer_cats = build_footer_categories(b)
    footer_social = render_footer_social()

    html = HOMEPAGE_TEMPLATE
    html = html.replace("__SITE_BASE__", b)
    html = html.replace("__SITE_URL__", _SITE_URL)
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
    """Niche hub page (e.g. /fitness-trackers/): a dark hero with the featured
    product photo, the published reviews as polished cards, and a method strip.
    One shared builder restyles every niche page identically."""
    b = SITE_BASE
    category = next((c for c, slugs in CATEGORY_MAP.items() if niche_slug in slugs), "")
    cat_color = category_color(category)
    cat_esc = html_mod.escape(category)

    posts = posts or []
    latest = posts[0] if posts else None

    def _hero_excerpt(text, n=170):
        text = html_mod.unescape(re.sub(r"<[^>]+>", "", text or ""))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= n:
            return html_mod.escape(text)
        return html_mod.escape(text[:n].rstrip()) + "…"

    hero_img = (latest or {}).get("image") or carousel_img(niche_slug, b)
    hero_img_alt = html_mod.escape((latest or {}).get("title") or niche_name)
    hero_excerpt = _hero_excerpt((latest or {}).get("snippet") or "")
    hero_link = f"{b}/reviews/{niche_slug}/" if latest else f"{b}/{niche_slug}/"

    comp_link = ""
    if os.path.exists(f"docs/comparisons/{niche_slug}.html"):
        comp_link = f'<a class="niche-hero__secondary" href="{b}/comparisons/{niche_slug}.html">Compare top picks →</a>'

    # Featured-first review cards — same markup as the homepage.
    if posts:
        post_cards = "".join(review_card(p, category, b, featured=(i == 0)) for i, p in enumerate(posts))
        grid_count = f'<span class="category-section__count">{len(posts)} review{"s" if len(posts) != 1 else ""} published</span>'
    else:
        post_cards = ('<div class="niche-card review-card"><div class="review-card__media"><div class="niche-card__image-wrapper">'
                      f'<img src="{b}/assets/hero-home.svg" alt="Coming soon" loading="lazy"></div>'
                      '</div><div class="review-card__body">'
                      f'<span class="review-card__banner" style="background:{cat_color}">{cat_esc}</span>'
                      '<h2>Reviews coming soon</h2>'
                      '<p class="review-card__snippet">We\'re testing products in this category now.</p></div></div>')
        grid_count = '<span class="category-section__count">Reviews coming soon</span>'

    # Nav dropdown (white mega-menu)
    nav_dd = build_category_dropdown(b)

    # Footer
    footer_chrome = build_site_footer(b)

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
    <link rel="canonical" href="{_SITE_URL}/{niche_slug}/">
    <meta property="og:title" content="{blog_title} | Abvorn">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:url" content="{_SITE_URL}/{niche_slug}/">
    <meta property="og:type" content="website">
    <meta property="og:image" content="{_SITE_URL}/assets/logo.png"><meta name="twitter:image" content="{_SITE_URL}/assets/logo.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{blog_title} | Abvorn">
    <meta name="twitter:description" content="{meta_desc}">
    {FONT_LINK}
    <style>
        :root {{ --niche-primary: #1a1a1a; --niche-accent: #c98a2c; --font-mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }}
        {DESIGN_SYSTEM_CSS}
        {PROD_SHOT_CSS}
        
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

        .niche-hero {{ background:#0a0a0a; color:#fff; padding: clamp(2rem, 4vh, 4rem) 0; position:relative; overflow:hidden; }}
        .niche-hero::before {{ content:''; position:absolute; top:-20%; right:-10%; width:560px; height:560px; border-radius:50%; background:radial-gradient(circle, rgba(201,138,44,0.16), transparent 65%); pointer-events:none; }}
        .niche-hero__grid {{ display:grid; grid-template-columns:1fr 1fr; gap: clamp(var(--space-md), 3vw, var(--space-xl)); align-items:center; position:relative; }}
        .niche-hero__eyebrow {{ display:inline-block; font-size:0.7rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; color:var(--clr-accent); margin-bottom: var(--space-sm); }}
        .niche-hero h1 {{ color:#fff; font-size: clamp(var(--text-3xl), 4vw, var(--text-4xl)); margin-bottom: var(--space-md); letter-spacing:-0.03em; }}
        .niche-hero__excerpt {{ font-size: var(--text-lg); color:#ccc; max-width:48ch; margin-bottom: var(--space-md); }}
        .niche-hero__trust {{ display:flex; flex-wrap:wrap; gap:16px; margin-bottom: var(--space-lg); }}
        .niche-hero__trust span {{ display:inline-flex; align-items:center; gap:7px; font-size:0.78rem; font-weight:600; color:#999; }}
        .niche-hero__trust svg {{ width:14px; height:14px; color:var(--clr-accent); }}
        .niche-hero__cta-row {{ display:flex; align-items:center; gap:14px; flex-wrap:wrap; }}
        .niche-hero__cta-row .btn {{ background:var(--clr-accent); color:#1a1200; font-weight:800; font-size:0.95rem; padding:0.8em 1.6em; box-shadow:0 6px 22px rgba(201,138,44,0.4); }}
        .niche-hero__cta-row .btn:hover {{ background:#e0a23f; transform:translateY(-2px); box-shadow:0 10px 30px rgba(201,138,44,0.55); }}
        .niche-hero__secondary {{ font-size:0.9rem; font-weight:700; color:#fff; text-decoration:none; border-bottom:2px solid rgba(201,138,44,0.6); padding-bottom:2px; }}
        .niche-hero__secondary:hover {{ color:var(--clr-accent); }}
        .niche-hero__visual {{ display:flex; flex-direction:column; gap: var(--space-md); }}
        .hero-product {{ position:relative; border-radius: var(--radius-lg); overflow:hidden; background:#ffffff; display:flex; align-items:center; justify-content:center; padding: clamp(var(--space-sm), 1.5vw, var(--space-lg)); min-height:0; }}
        .hero-product img {{ max-width:100%; max-height:min(460px, 40vh); width:auto; height:auto; object-fit:contain; }}
        .hero-product__badge {{ position:absolute; top:14px; left:14px; z-index:2; background:var(--clr-accent); color:#1a1200; font-size:0.7rem; font-weight:800; text-transform:uppercase; letter-spacing:0.07em; padding:4px 12px; border-radius:100px; box-shadow:var(--shadow-sm); }}
        @media (max-width:860px) {{ .niche-hero {{ padding: clamp(1.5rem, 3vh, 2.5rem) 0; }} .niche-hero__grid {{ grid-template-columns:1fr; gap: var(--space-md); }} .niche-hero__visual {{ order:-1; }} .hero-product {{ min-height:0; padding: var(--space-sm); }} .hero-product img {{ max-height:160px; }} .niche-hero h1 {{ font-size: var(--text-2xl); }} .niche-hero__excerpt {{ font-size: var(--text-base); }} }}

        .posts-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(320px,1fr)); gap: var(--space-lg); }}
        .category-section__header {{ display:flex; justify-content:space-between; align-items:flex-end; gap: var(--space-md); margin-bottom: var(--space-lg); border-bottom:2px solid var(--clr-black); padding-bottom: var(--space-sm); flex-wrap:wrap; }}
        .category-section__header h2 {{ font-size: var(--text-2xl); margin:0; flex:1 1 auto; min-width:0; }}
        .category-section__count {{ font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:var(--clr-mid-gray); }}
        .niche-reviews {{ padding: var(--space-2xl) 0; }}

        .how-we-test {{ background:#0a0a0a; color:#fff; padding: var(--space-2xl) 0; }}
        .how-we-test__inner {{ max-width:1200px; margin:0 auto; padding:0 var(--space-lg); }}
        .how-we-test__intro {{ margin-bottom: var(--space-xl); }}
        .how-we-test__intro h2 {{ color:#fff; font-size: var(--text-3xl); margin-bottom:8px; }}
        .how-we-test__intro p {{ color:#999; max-width:52ch; margin:0; }}
        .section-eyebrow {{ display:block; font-size:0.7rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; color:var(--clr-accent); margin-bottom:6px; }}
        .hwt-steps {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(220px,1fr)); gap: var(--space-lg); }}
        .hwt-step {{ border-left:2px solid rgba(201,138,44,0.5); padding:0 0 0 var(--space-lg); }}
        .hwt-step__num {{ font-family: var(--font-display); font-size: var(--text-xl); font-weight:800; color:var(--clr-accent); letter-spacing:-0.02em; }}
        .hwt-step h3 {{ color:#fff; font-size: var(--text-lg); margin:6px 0; }}
        .hwt-step p {{ color:#999; font-size:0.9rem; margin:0; line-height:1.55; }}

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

        .posts-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(320px,1fr)); gap: var(--space-lg); }}
        .niche-card {{ border:1px solid var(--clr-light-gray); border-radius:var(--radius-lg); overflow:hidden; transition: transform var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out); background:var(--clr-white); display:flex; flex-direction:column; }}
        .niche-card:hover {{ transform:translateY(-6px); box-shadow:var(--shadow-lg); }}
        .niche-card__image-wrapper {{ aspect-ratio: 4/3; overflow:hidden; background:var(--clr-white); padding:20px; }}
        .niche-card img {{ width:100%; height:100%; object-fit:contain; transition: transform var(--duration-slow) var(--ease-out); }}
        .niche-card:hover img {{ transform: scale(1.04); }}
        .review-card__media {{ position:relative; }}
        .review-card__banner {{ display:inline-block; padding:4px 12px; border-radius:6px; color:#1a1200; font-size:0.64rem; font-weight:800; text-transform:uppercase; letter-spacing:0.07em; margin-bottom:6px; }}
        .review-card__body {{ display:flex; flex-direction:column; flex:1; padding: var(--space-md); }}
        .review-card__body h2 {{ font-size: var(--text-lg); margin:0 0 8px; line-height:1.25; }}
        .review-card__body h2 a {{ color:inherit; text-decoration:none; }}
        .review-card__body h2 a:hover {{ color: var(--cat, var(--clr-accent-text)); color: color-mix(in srgb, var(--cat, var(--clr-accent-text)) 55%, #1a1200); }}
        .review-card__snippet {{ font-size:0.9rem; color:var(--clr-mid-gray); line-height:1.5; margin:0 0 var(--space-sm); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
        .review-card__footer {{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:auto; padding-top: var(--space-sm); }}
        .review-card__footer .read-link {{ font-weight:700; font-size:0.82rem; color:var(--clr-black); text-decoration:none; border-bottom:2px solid var(--cat, var(--clr-accent)); border-bottom-color: color-mix(in srgb, var(--cat, var(--clr-accent)) 55%, #1a1200); padding-bottom:1px; }}
        .review-card__footer .read-link:hover {{ color: var(--cat, var(--clr-accent-text)); color: color-mix(in srgb, var(--cat, var(--clr-accent-text)) 55%, #1a1200); }}
        .review-card__reactions {{ display:flex; gap:6px; }}
        .review-card__reactions .reaction-btn {{ display:inline-flex; align-items:center; gap:5px; padding:5px 12px; border:1px solid var(--clr-light-gray); border-radius:999px; background:#fff; color:var(--clr-mid-gray); font-size:0.78rem; font-weight:600; font-family:var(--font-body); }}
        .review-card__reactions .reaction-btn.is-counter {{ cursor:default; }}
        .review-card__reactions .reaction-icon {{ font-size:0.9rem; line-height:1; }}
        .review-card__reactions .reaction-count {{ font-weight:700; min-width:14px; text-align:center; }}
        .review-card__updated {{ display:block; font-size:0.72rem; color:#999; margin-bottom: var(--space-xs); }}
        .review-card__score {{ position:absolute; right:14px; bottom:14px; z-index:2; display:inline-flex; align-items:baseline; gap:3px; background:rgba(10,10,10,0.92); color:#fff; border-radius:100px; padding:6px 14px; border:1px solid rgba(201,138,44,0.6); backdrop-filter: blur(4px); }}
        .review-card__score-num {{ font-family: var(--font-display); font-size:1.15rem; font-weight:800; color: var(--clr-accent); letter-spacing:-0.02em; line-height:1; }}
        .review-card__score-out {{ font-size:0.7rem; color:#aaa; font-weight:600; }}
        .niche-card--featured {{ grid-column: 1 / -1; display:grid; grid-template-columns: 1.1fr 1fr; align-items:center; }}
        .niche-card--featured .niche-card__image-wrapper {{ aspect-ratio: 16/10; height:100%; }}
        .niche-card--featured .review-card__body {{ padding: var(--space-xl); }}
        .niche-card--featured h2 {{ font-size: var(--text-2xl); }}
        .niche-card--featured .review-card__score-num {{ font-size:1.5rem; }}
        .niche-card--featured .review-card__snippet {{ -webkit-line-clamp:3; }}
        @media (max-width: 760px) {{ .niche-card--featured {{ grid-template-columns: 1fr; }} .niche-card--featured .review-card__body {{ padding: var(--space-md); }} }}

        .footer {{ background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }}
        .footer-grid {{ display:grid; grid-template-columns:1.6fr 2fr 1fr; gap:var(--space-lg); margin-bottom:var(--space-xl); }}
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
<a class="skip-link" href="#main">Skip to content</a>
<header><div class="container navbar">
    <a href="{b}/" class="logo"><img src="{b}/logo.svg" alt="Abvorn"></a>
    <button class="nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav-links">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <nav class="nav-links" id="nav-links">
        <div class="nav-item"><a href="#">Categories</a><div class="nav-dropdown nav-dropdown--mega">{nav_dd}</div></div>
        <a href="{b}/">Home</a>
        <a href="{b}/about.html">About</a>
        <a href="{b}/journal/">Journal</a>
    </nav>
</div></header>

<main id="main">
<section class="niche-hero"><div class="container niche-hero__grid">
    <div>
        <span class="niche-hero__eyebrow">{cat_esc}</span>
        <h1>{blog_title}</h1>
        <p class="niche-hero__excerpt">{hero_excerpt}</p>
        <div class="niche-hero__trust">
            <span><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>Independently researched</span>
            <span><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>No sponsored placements</span>
            <span><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>Scored on 5 criteria</span>
        </div>
        <div class="niche-hero__cta-row">
            <a href="{hero_link}" class="btn">Read the full review →</a>
            {comp_link}
        </div>
    </div>
    <div class="niche-hero__visual">
        <div class="hero-product">
            <img src="{hero_img}" alt="{hero_img_alt}" loading="eager">
            <span class="hero-product__badge">Our pick</span>
        </div>
    </div>
</div></section>

<section class="container niche-reviews">
    <div class="category-section__header">
        <h2>Reviews &amp; Buying Guides</h2>
        {grid_count}
    </div>
    <div class="posts-grid">{post_list}</div>
</section>

<section class="how-we-test"><div class="how-we-test__inner">
    <div class="how-we-test__intro">
        <span class="section-eyebrow">Our method</span>
        <h2>How we test {title_escaped}</h2>
        <p>Every score follows the same repeatable process. No paid placements, no editorial bias — just a consistent method.</p>
    </div>
    <div class="hwt-steps">
        <div class="hwt-step"><div class="hwt-step__num">01</div><h3>Research</h3><p>We shortlist candidates on price, specs, and verified owner feedback across retailers.</p></div>
        <div class="hwt-step"><div class="hwt-step__num">02</div><h3>Score</h3><p>Every product is scored on the same 5 weighted criteria before any ranking is drawn.</p></div>
        <div class="hwt-step"><div class="hwt-step__num">03</div><h3>Recommend</h3><p>We recommend the one we'd actually buy — and say plainly when a product falls short.</p></div>
    </div>
</div></section>

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
</main>

{footer_chrome}

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
            method: 'POST', headers: {{'Content-Type': 'text/plain;charset=utf-8'}},
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


# ── Category hero (dark "showroom" band with per-category motif) ────────
# Tailored tagline per category; falls back to the generic promise.
CATEGORY_TAGLINES = {
    "audio": "Marketing copy calls everything 'studio-quality.' We check real prices and verified owner feedback to find the headphones and earbuds actually worth your ears.",
    "computing-and-monitors": "Spec sheets can't tell you what a laptop feels like at 2am before a deadline. We benchmark the monitors and machines that actually deserve your desk space.",
    "fitness-and-health": "Most fitness trackers count steps and little else. We check which ones measure what matters — heart, sleep, and recovery — and which are just jewelry.",
    "gaming": "Latency and build quality beat RGB every time. We test the mice and keyboards that survive the grind, not just the hype.",
    "home-and-lifestyle": "Streaming boxes and smart gadgets promise a better living room. We test which ones deliver without the subscription trap.",
    "webcams-and-accessories": "Your webcam is what eight hours of meetings sees. We test video, audio, and software so your calls look like you put effort in.",
}


def _hero_numerics(items):
    """Review count, niche count, highest valid score (<=10) and its breakdown."""
    count = len(items)
    niches = len({r.get("slug") for r in items})
    valid = [r for r in items if r.get("score")]
    valid = [r for r in valid if float(r["score"]) <= 10.0]
    top = max(valid, key=lambda r: float(r["score"])) if valid else None
    top_score = float(top["score"]) if top else None
    breakdown = (top or {}).get("breakdown") or {}
    return count, niches, top_score, breakdown


def _mono(text, x, y, size, fill, weight="600", anchor="start"):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="JetBrains Mono, monospace" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}">{text}</text>')


def _motif_audio(accent, breakdown):
    order = [("Sound Quality", "SND"), ("Comfort & Fit", "COMF"), ("Battery Life", "BATT"),
             ("Features & Tech", "FEAT"), ("Value for Money", "VAL")]
    rows = [(lab, min(max(float(breakdown[k]) / 10.0, 0.2), 1.0)) for k, lab in order if k in breakdown]
    if not rows:
        rows = [(lab, 0.7) for _, lab in order]
    bw, gap, base, maxh = 46, 26, 248, 178
    n = len(rows)
    total = n * bw + (n - 1) * gap
    x0 = (420 - total) / 2
    parts = ['<rect x="10" y="10" width="400" height="280" rx="20" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.1)"/>',
             f'<line x1="40" y1="{base}" x2="380" y2="{base}" stroke="rgba(255,255,255,0.14)" stroke-width="2"/>']
    for i, (lab, frac) in enumerate(rows):
        x = x0 + i * (bw + gap)
        h = max(24, round(frac * maxh))
        y = base - h
        parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{h}" rx="8" fill="{accent}" opacity="{0.55 + 0.45 * (i % 2)}"/>')
        parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="4" rx="2" fill="#fff" opacity="0.35"/>')
        parts.append(f'<text x="{x + bw / 2}" y="{base + 22}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="11" font-weight="600" letter-spacing="0.08em" fill="#8a8a86">{lab}</text>')
        parts.append(f'<text x="{x + bw / 2}" y="{y - 10}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="13" font-weight="700" fill="#fff">{frac:.1f}</text>')
    return '<svg viewBox="0 0 420 300" role="img" aria-label="Audio category review scores">' + "".join(parts) + "</svg>"


def _motif_computing(accent, breakdown, top_score):
    order = [("Performance", "PERF"), ("Display", "DISP"), ("Battery Life", "BATT"), ("Build & Portability", "BUILD")]
    rows = [(lab, min(max(float(breakdown[k]) / 10.0, 0.2), 1.0)) for k, lab in order if k in breakdown]
    parts = ['<rect x="10" y="10" width="400" height="280" rx="20" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.1)"/>',
             f'<rect x="70" y="46" width="280" height="182" rx="14" fill="#14161a" stroke="{accent}" stroke-width="2"/>',
             '<rect x="84" y="60" width="252" height="142" rx="8" fill="#0b0d10"/>']
    for yy in range(72, 202, 8):
        parts.append(f'<line x1="84" y1="{yy}" x2="336" y2="{yy}" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>')
    parts.append(_mono("LAPTOP BUYING GUIDE", 98, 86, 11, accent, weight="700", anchor="start"))
    score_txt = f"SCORE {top_score:.1f}/10" if top_score else "SCORE --/10"
    parts.append(_mono(score_txt, 98, 110, 20, "#ffffff", weight="700", anchor="start"))
    ry = 136
    for lab, frac in rows:
        parts.append(_mono(lab, 98, ry, 10, "#8a8a86", weight="600", anchor="start"))
        parts.append(f'<rect x="158" y="{ry - 12}" width="112" height="8" rx="4" fill="rgba(255,255,255,0.08)"/>')
        parts.append(f'<rect x="158" y="{ry - 12}" width="{int(112 * frac)}" height="8" rx="4" fill="{accent}"/>')
        parts.append(_mono(f"{frac:.1f}", 278, ry, 10, "#ffffff", weight="700", anchor="start"))
        ry += 26
    parts.append(f'<rect x="196" y="228" width="28" height="14" fill="{accent}" opacity="0.7"/>')
    parts.append(f'<rect x="150" y="242" width="120" height="8" rx="4" fill="rgba(255,255,255,0.15)"/>')
    return '<svg viewBox="0 0 420 300" role="img" aria-label="Computing category review scores">' + "".join(parts) + "</svg>"


def _motif_fitness(accent, breakdown):
    parts = ['<rect x="10" y="10" width="400" height="280" rx="20" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.1)"/>']
    for gx in range(50, 381, 44):
        parts.append(f'<line x1="{gx}" y1="60" x2="{gx}" y2="230" stroke="rgba(255,255,255,0.05)"/>')
    for gy in range(80, 221, 30):
        parts.append(f'<line x1="50" y1="{gy}" x2="380" y2="{gy}" stroke="rgba(255,255,255,0.05)"/>')
    ecg = ("M50,150 L78,150 L90,148 L100,146 L108,150 L118,150 L126,128 L132,104 L136,88 "
           "L142,150 L152,150 L164,150 L174,152 L184,150 L196,150 L224,150 L236,148 L246,146 "
           "L254,150 L264,150 L272,128 L278,104 L282,88 L288,150 L298,150 L310,150 L320,152 "
           "L330,150 L342,150 L370,150")
    parts.append(f'<path d="{ecg}" fill="none" stroke="{accent}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append(f'<circle cx="370" cy="150" r="4" fill="{accent}"/>')
    parts.append(f'<circle cx="370" cy="150" r="4" fill="{accent}" opacity="0.35"/>')
    acc = float(breakdown.get("Accuracy", 7.5))
    parts.append(_mono("HEART RATE", 60, 252, 13, accent, weight="700", anchor="start"))
    parts.append(_mono("72 BPM", 60, 274, 22, "#ffffff", weight="700", anchor="start"))
    parts.append(_mono("ACCURACY", 300, 252, 13, accent, weight="700", anchor="end"))
    parts.append(_mono(f"{acc:.1f}/10", 300, 274, 22, "#ffffff", weight="700", anchor="end"))
    return '<svg viewBox="0 0 420 300" role="img" aria-label="Fitness category review scores">' + "".join(parts) + "</svg>"


def _motif_gaming(accent, top_score):
    cx, cy = 210, 150
    parts = ['<rect x="10" y="10" width="400" height="280" rx="20" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.1)"/>',
             f'<circle cx="{cx}" cy="{cy}" r="96" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>',
             f'<line x1="{cx}" y1="44" x2="{cx}" y2="256" stroke="rgba(255,255,255,0.10)" stroke-width="1"/>',
             f'<line x1="104" y1="{cy}" x2="316" y2="{cy}" stroke="rgba(255,255,255,0.10)" stroke-width="1"/>',
             f'<circle cx="{cx}" cy="{cy}" r="20" fill="none" stroke="{accent}" stroke-width="2.5"/>',
             f'<line x1="{cx}" y1="112" x2="{cx}" y2="130" stroke="{accent}" stroke-width="2.5" stroke-linecap="round"/>',
             f'<line x1="{cx}" y1="170" x2="{cx}" y2="188" stroke="{accent}" stroke-width="2.5" stroke-linecap="round"/>',
             f'<line x1="172" y1="{cy}" x2="190" y2="{cy}" stroke="{accent}" stroke-width="2.5" stroke-linecap="round"/>',
             f'<line x1="230" y1="{cy}" x2="248" y2="{cy}" stroke="{accent}" stroke-width="2.5" stroke-linecap="round"/>',
             f'<circle cx="{cx}" cy="{cy}" r="4" fill="{accent}"/>']
    for x1, y1, x2, y2, x3, y3 in [(30, 30, 56, 30, 30, 56), (390, 30, 364, 30, 390, 56),
                                   (30, 270, 56, 270, 30, 244), (390, 270, 364, 270, 390, 244)]:
        parts.append(f'<path d="M{x1},{y1} L{x2},{y2} M{x1},{y1} L{x3},{y3}" stroke="rgba(255,255,255,0.25)" stroke-width="2" fill="none" stroke-linecap="round"/>')
    score_txt = f"{top_score:.1f}" if top_score else "--"
    parts.append(_mono("SENSOR", 60, 252, 13, accent, weight="700", anchor="start"))
    parts.append(_mono("26000 DPI", 60, 274, 22, "#ffffff", weight="700", anchor="start"))
    parts.append(_mono("TOP SCORE", 300, 252, 13, accent, weight="700", anchor="end"))
    parts.append(_mono(score_txt, 300, 274, 22, "#ffffff", weight="700", anchor="end"))
    return '<svg viewBox="0 0 420 300" role="img" aria-label="Gaming category review scores">' + "".join(parts) + "</svg>"


def _motif_home(accent, top_score):
    parts = ['<rect x="10" y="10" width="400" height="280" rx="20" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.1)"/>',
             '<defs><radialGradient id="homeglow" cx="50%" cy="50%" r="70%">'
             '<stop offset="0%" stop-color="#ffb95c" stop-opacity="0.9"/>'
             '<stop offset="100%" stop-color="#ffb95c" stop-opacity="0.3"/></radialGradient></defs>',
             '<rect x="110" y="40" width="200" height="200" rx="6" fill="#141619"/>',
             '<rect x="128" y="58" width="164" height="148" rx="4" fill="#2a1c08"/>',
             '<rect x="128" y="58" width="164" height="148" rx="4" fill="url(#homeglow)" opacity="0.55"/>',
             '<circle cx="170" cy="96" r="16" fill="#ffd9a0" opacity="0.95"/>',
             '<circle cx="177" cy="91" r="14" fill="#2a1c08"/>',
             '<circle cx="252" cy="80" r="2.5" fill="#ffd9a0" opacity="0.85"/>',
             '<circle cx="268" cy="112" r="1.8" fill="#ffd9a0" opacity="0.7"/>',
             '<circle cx="238" cy="140" r="1.8" fill="#ffd9a0" opacity="0.6"/>',
             '<path d="M252,206 l10,22 h-20 z" fill="#0b0d10"/>',
             '<ellipse cx="252" cy="196" rx="10" ry="14" fill="#0b0d10"/>',
             f'<rect x="128" y="58" width="164" height="148" rx="4" fill="none" stroke="{accent}" stroke-width="4" opacity="0.9"/>',
             f'<line x1="210" y1="58" x2="210" y2="206" stroke="{accent}" stroke-width="4" opacity="0.9"/>',
             f'<line x1="128" y1="132" x2="292" y2="132" stroke="{accent}" stroke-width="4" opacity="0.9"/>',
             f'<rect x="118" y="206" width="184" height="8" rx="3" fill="{accent}" opacity="0.55"/>']
    score_txt = f"{top_score:.1f}" if top_score else "--"
    parts.append(_mono("STREAMING", 60, 252, 13, accent, weight="700", anchor="start"))
    parts.append(_mono("4K HDR READY", 60, 274, 22, "#ffffff", weight="700", anchor="start"))
    parts.append(_mono("TOP SCORE", 300, 252, 13, accent, weight="700", anchor="end"))
    parts.append(_mono(score_txt, 300, 274, 22, "#ffffff", weight="700", anchor="end"))
    return '<svg viewBox="0 0 420 300" role="img" aria-label="Home and lifestyle category review scores">' + "".join(parts) + "</svg>"


def _motif_webcams(accent, top_score):
    parts = ['<rect x="10" y="10" width="400" height="280" rx="20" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.1)"/>',
             f'<rect x="96" y="120" width="228" height="92" rx="14" fill="#14161a" stroke="{accent}" stroke-width="2"/>',
             f'<circle cx="210" cy="166" r="34" fill="#0b0d10" stroke="{accent}" stroke-width="2"/>',
             '<circle cx="210" cy="166" r="22" fill="#0d0f12" stroke="rgba(255,255,255,0.18)" stroke-width="1.5"/>',
             '<circle cx="210" cy="166" r="10" fill="#161a1f" stroke="rgba(255,255,255,0.25)" stroke-width="1"/>',
             f'<circle cx="210" cy="166" r="3.5" fill="{accent}" opacity="0.9"/>',
             '<circle cx="128" cy="142" r="6" fill="#ff4b4b"/>',
             '<text x="140" y="146" font-family="JetBrains Mono, monospace" font-size="11" font-weight="700" letter-spacing="0.1em" fill="#ff4b4b">REC</text>']
    for x1, y1, x2, y2, x3, y3 in [(176, 132, 196, 132, 176, 152), (244, 132, 224, 132, 244, 152),
                                   (176, 200, 196, 200, 176, 180), (244, 200, 224, 200, 244, 180)]:
        parts.append(f'<path d="M{x1},{y1} L{x2},{y1} M{x1},{y1} L{x1},{y3}" stroke="{accent}" stroke-width="3" fill="none" stroke-linecap="round"/>')
    score_txt = f"{top_score:.1f}" if top_score else "--"
    parts.append(_mono("FOV", 60, 252, 13, accent, weight="700", anchor="start"))
    parts.append(_mono("90 DEG", 60, 274, 22, "#ffffff", weight="700", anchor="start"))
    parts.append(_mono("TOP SCORE", 300, 252, 13, accent, weight="700", anchor="end"))
    parts.append(_mono(score_txt, 300, 274, 22, "#ffffff", weight="700", anchor="end"))
    return '<svg viewBox="0 0 420 300" role="img" aria-label="Webcams category review scores">' + "".join(parts) + "</svg>"


def _cat_motif(category_slug, accent, breakdown, top_score):
    if category_slug == "audio":
        return _motif_audio(accent, breakdown)
    if category_slug == "computing-and-monitors":
        return _motif_computing(accent, breakdown, top_score)
    if category_slug == "fitness-and-health":
        return _motif_fitness(accent, breakdown)
    if category_slug == "gaming":
        return _motif_gaming(accent, top_score)
    if category_slug == "home-and-lifestyle":
        return _motif_home(accent, top_score)
    return _motif_webcams(accent, top_score)


def _build_category_hero(category_name, category_slug, items, accent, tagline, heading=None, eyebrow=None):
    """Dark 'showroom' hero: eyebrow, headline, tagline, data chips, CTA, motif stage."""
    count, niches, top_score, breakdown = _hero_numerics(items)
    top_txt = f"{top_score:.1f}" if top_score else "--"
    motif = _cat_motif(category_slug, accent, breakdown, top_score)
    eyebrow = eyebrow if eyebrow is not None else f"{html_mod.escape(category_name.upper())} · {count} review{'s' if count != 1 else ''} published"
    if items:
        cta = ('<a class="cat-hero__btn" href="#latest">Browse the reviews'
               '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12l7 7 7-7"/></svg></a>')
    else:
        cta = '<span class="cat-hero__coming">Reviews coming soon — subscribe below to be first.</span>'
    return f'''<section class="cat-hero" style="--cat:{accent}">
    <div class="cat-hero__bg" aria-hidden="true"></div>
    <div class="container cat-hero__grid">
        <div class="cat-hero__copy">
            <p class="cat-hero__eyebrow"><span class="cat-hero__dot" aria-hidden="true"></span>{eyebrow}</p>
            <h1 class="cat-hero__title">{html_mod.escape(heading if heading else category_name + ' Reviews')}</h1>
            <p class="cat-hero__tagline">{html_mod.escape(tagline)}</p>
            <div class="cat-hero__chips">
                <div class="cat-hero__chip"><span class="cat-hero__chip-num">{count}</span><span class="cat-hero__chip-label">reviews published</span></div>
                <div class="cat-hero__chip"><span class="cat-hero__chip-num"><em>{top_txt}</em>/10</span><span class="cat-hero__chip-label">best score</span></div>
                <div class="cat-hero__chip"><span class="cat-hero__chip-num">{niches}</span><span class="cat-hero__chip-label">niche{'' if niches == 1 else 's'} tested</span></div>
            </div>
            <div class="cat-hero__cta">{cta}<span class="cat-hero__hint">Independent · Tested · Updated weekly</span></div>
        </div>
        <div class="cat-hero__stage" aria-hidden="true">{motif}</div>
    </div>
</section>'''


def build_category_listing_page(category_name, category_slug, items, all_slugs, base=None, affiliate_tag=""):
    """Full page listing every review published in a category (e.g. /categories/audio/)."""
    b = base or SITE_BASE

    # Nav dropdown (white mega-menu)
    nav_dd = build_category_dropdown(b)

    # Footer
    footer_chrome = build_site_footer(b)

    # Subscribe form action
    form_url = os.environ.get("APPS_SCRIPT_URL", "")

    title_escaped = html_mod.escape(category_name)
    year_str = str(datetime.now().year)

    blog_title = f"{title_escaped} Reviews"
    meta_desc = f"Independent {category_name.lower()} reviews and buying guides. We test before we recommend."

    # Per-category hero tagline. Falls back to the generic promise.
    hero_tagline = CATEGORY_TAGLINES.get(
        category_slug.lower(),
        "Independent testing, real recommendations. We buy it, test it, and tell you what's actually worth your money.",
    )
    hero_accent = category_color(category_name)
    hero_html = _build_category_hero(category_name, category_slug, items, hero_accent, hero_tagline)

    # Group reviews by niche; sort niche sections alphabetically by display name.
    by_niche: dict = {}
    for r in items:
        by_niche.setdefault(r["slug"], []).append(r)
    for slug in by_niche:
        by_niche[slug].sort(key=lambda r: r.get("updated", ""), reverse=True)
    niche_order = sorted(by_niche, key=lambda s: _niche_name(s).lower())

    # "Our latest … Reviews" = the newest reviews across the category (max 4).
    latest_items = sorted(items, key=lambda r: r.get("updated", ""), reverse=True)[:4]

    # Subscribe CTA band — sits directly after the Latest reviews section so
    # the conversion prompt follows the freshest content, before the deeper
    # per-niche sections.
    subscribe_band = (
        '<section class="subscribe-band"><div class="container subscribe-inner">'
        '<div class="subscribe-copy">'
        f'<h2>Get alerted when we publish a new {title_escaped} review</h2>'
        '<p>One email whenever we publish a new guide in this category. No spam, unsubscribe anytime.</p>'
        '</div>'
        f'<form class="subscribe-form" id="category-subscribe-form" onsubmit="submitCategorySubscribe(event)">'
        '<input type="text" name="_gotcha" class="hp-field" tabindex="-1" autocomplete="off">'
        '<label for="category-subscribe-email" class="sr-only">Email address</label>'
        '<input type="email" class="input" id="category-subscribe-email" placeholder="you@example.com" required>'
        '<button type="submit" class="btn">Notify Me</button>'
        '<p class="subscribe-msg" id="category-subscribe-msg" aria-live="polite"></p>'
        '</form>'
        '</div></section>'
    )

    sections = []
    if items:
        # Latest review cards — same treatment as the homepage's "Latest
        # reviews" section: an eyebrow, then the newest review promoted to a
        # full-width featured spotlight card above the rest of the grid.
        latest_cards = "".join(
            review_card(r, category_name, b, featured=(i == 0))
            for i, r in enumerate(latest_items)
        )
        sections.append(
            f'<section class="category-section container" id="latest" style="--cat:{hero_accent}">'
            f'<span class="section-eyebrow">Fresh this week</span>'
            f'<div class="category-section__header"><h2>Latest {title_escaped} reviews</h2></div>'
            f'<div class="niche-grid">{latest_cards}</div></section>'
        )
        # The CTA band follows the latest reviews, before the niche sections.
        sections.append(subscribe_band)
        for slug in niche_order:
            n = len(by_niche[slug])
            niche_cards = "".join(review_card(r, category_name, b) for r in by_niche[slug])
            sections.append(
                f'<section class="category-section container" id="{slug}" style="--cat:{hero_accent}">'
                f'<div class="category-section__header"><h2>{html_mod.escape(_niche_name(slug))}</h2>'
                f'<span class="category-section__count">{n} review{"s" if n != 1 else ""}</span></div>'
                f'<div class="posts-grid">{niche_cards}</div></section>'
            )
    else:
        sections.append(
            '<p style="grid-column:1/-1;text-align:center;color:var(--clr-mid-gray);padding:40px 0">Reviews coming soon.</p>'
        )
        sections.append(subscribe_band)
    sections_html = "".join(sections)

    index_nav = build_category_index(category_name, b, niche_slugs=niche_order or None) if items else ""
    count = len(items)

    return f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="{b}/assets/favicon-32x32.png">
    <title>{blog_title} | Abvorn</title>
    <meta name="description" content="{meta_desc}">
    <link rel="canonical" href="{_SITE_URL}/categories/{category_slug}/">
    <meta property="og:title" content="{blog_title} | Abvorn">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:url" content="{_SITE_URL}/categories/{category_slug}/">
    <meta property="og:type" content="website">
    <meta property="og:image" content="{_SITE_URL}/assets/logo.png"><meta name="twitter:image" content="{_SITE_URL}/assets/logo.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{blog_title} | Abvorn">
    <meta name="twitter:description" content="{meta_desc}">
    {FONT_LINK}
    <style>
        :root {{ --niche-primary: #1a1a1a; --niche-accent: #c98a2c; --font-mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }}
        {DESIGN_SYSTEM_CSS}
        {PROD_SHOT_CSS}
        
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

        .cat-hero {{ position:relative; overflow:hidden; background:#0d0d0d; color:#fff; padding:clamp(44px,5.5vw,84px) 0; border-bottom:1px solid #222; }}
        .cat-hero__bg {{ position:absolute; inset:0; pointer-events:none; background:
            radial-gradient(900px 420px at 80% 12%, color-mix(in srgb, var(--cat) 16%, transparent), transparent 65%),
            radial-gradient(640px 380px at 8% 96%, color-mix(in srgb, var(--cat) 8%, transparent), transparent 60%); }}
        .cat-hero__grid {{ position:relative; display:grid; grid-template-columns:1.15fr 0.85fr; gap:clamp(24px,4vw,56px); align-items:center; }}
        .cat-hero__eyebrow {{ display:flex; align-items:center; gap:10px; margin:0 0 18px; font-family:var(--font-mono); font-size:0.74rem; font-weight:600; letter-spacing:0.14em; text-transform:uppercase; color:var(--cat); }}
        .cat-hero__dot {{ width:8px; height:8px; border-radius:2px; background:var(--cat); box-shadow:0 0 14px var(--cat); flex-shrink:0; }}
        .cat-hero__title {{ font-family:var(--font-display); font-weight:800; font-size:clamp(var(--text-3xl),4vw,var(--text-4xl)); line-height:1.06; letter-spacing:-0.02em; color:#fff; margin:0 0 16px; }}
        .cat-hero__tagline {{ font-family:var(--font-body); font-size:clamp(1rem,1.5vw,1.15rem); line-height:1.6; color:#b9b9b4; max-width:52ch; margin:0 0 26px; }}
        .cat-hero__chips {{ display:flex; flex-wrap:wrap; gap:12px; margin:0 0 28px; }}
        .cat-hero__chip {{ display:flex; flex-direction:column; gap:3px; min-width:104px; padding:12px 16px; border:1px solid rgba(255,255,255,0.12); border-radius:14px; background:rgba(255,255,255,0.03); }}
        .cat-hero__chip-num {{ font-family:var(--font-mono); font-size:1.5rem; font-weight:700; line-height:1; color:#fff; }}
        .cat-hero__chip-num em {{ font-style:normal; color:var(--cat); }}
        .cat-hero__chip-label {{ font-family:var(--font-body); font-size:0.68rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#8a8a86; }}
        .cat-hero__cta {{ display:flex; align-items:center; gap:18px; flex-wrap:wrap; }}
        .cat-hero__btn {{ display:inline-flex; align-items:center; gap:10px; background:var(--cat); color:#0a0a0a; font-family:var(--font-display); font-weight:800; font-size:1rem; text-decoration:none; padding:0.95em 1.6em; border-radius:12px; box-shadow:0 10px 34px color-mix(in srgb, var(--cat) 45%, transparent); transition:transform var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out); }}
        .cat-hero__btn:hover {{ transform:translateY(-2px); box-shadow:0 14px 44px color-mix(in srgb, var(--cat) 60%, transparent); }}
        .cat-hero__btn svg {{ width:18px; height:18px; }}
        .cat-hero__hint {{ font-family:var(--font-body); font-size:0.8rem; color:#8a8a86; }}
        .cat-hero__coming {{ font-family:var(--font-body); font-size:0.95rem; color:#b9b9b4; }}
        .cat-hero__stage {{ position:relative; display:flex; align-items:center; justify-content:center; }}
        .cat-hero__stage svg {{ width:100%; max-width:440px; height:auto; filter:drop-shadow(0 24px 60px rgba(0,0,0,0.5)); }}
        @media (max-width:900px) {{ .cat-hero__grid {{ grid-template-columns:1fr; }} .cat-hero__stage {{ order:-1; max-width:340px; margin:0 auto; }} }}

        .category-index {{ background:color-mix(in srgb, var(--cat) 12%, var(--clr-off-white)); border-bottom:1px solid color-mix(in srgb, var(--cat) 34%, var(--clr-light-gray)); padding:10px 0; }}
        .category-index__inner {{ display:flex; align-items:center; gap: var(--space-lg); flex-wrap:wrap; }}
        .category-index__label {{ font-size:0.72rem; font-weight:800; text-transform:uppercase; letter-spacing:0.08em; color:color-mix(in srgb, var(--cat) 44%, #0a0a0a); flex-shrink:0; }}
        .category-index__links {{ display:flex; flex-wrap:wrap; align-items:center; gap: var(--space-md); row-gap:8px; }}
        .category-index__link {{ font-family:var(--font-display); font-weight:600; font-size:0.95rem; color:var(--clr-black); text-decoration:none; display:inline-flex; align-items:center; gap:8px; padding:4px 0; border-bottom:2px solid transparent; transition: color var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out); }}
        .category-index__link:hover {{ color:color-mix(in srgb, var(--cat) 44%, #0a0a0a); border-color:var(--cat); }}
        .category-index__link.is-current {{ color:color-mix(in srgb, var(--cat) 44%, #0a0a0a); border-color:var(--cat); }}
        .category-index__tick {{ width:7px; height:7px; border-radius:1px; background:var(--cat, var(--clr-accent)); flex-shrink:0; }}

        .cat-tiles {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(220px,1fr)); gap: var(--space-lg); padding: var(--space-2xl) var(--space-lg); background:var(--clr-off-white); border-bottom:1px solid var(--clr-light-gray); }}
        .cat-tile {{ display:flex; align-items:center; gap:12px; padding:18px 20px; background:var(--clr-white); border:1px solid var(--clr-light-gray); border-radius:var(--radius-lg); color:var(--clr-black); text-decoration:none; transition: transform var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out), border-color var(--duration-base) var(--ease-out); }}
        .cat-tile:hover {{ transform:translateY(-4px); box-shadow:var(--shadow-lg); border-color:var(--cat, var(--clr-accent)); }}
        .cat-tile__tick {{ width:9px; height:9px; border-radius:2px; background:var(--cat, var(--clr-accent)); flex-shrink:0; }}
        .cat-tile__name {{ font-family:var(--font-display); font-weight:700; font-size:1rem; flex:1 1 auto; }}
        .cat-tile__arrow {{ color:var(--clr-mid-gray); font-size:0.9rem; transition: transform var(--duration-fast) var(--ease-out); }}
        .cat-tile:hover .cat-tile__arrow {{ transform:translateX(3px); color:var(--cat, var(--clr-accent)); }}
        @media (max-width:640px) {{ .cat-tiles {{ padding: var(--space-xl) var(--space-md); }} }}

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
        .niche-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(280px,1fr)); gap: var(--space-lg); }}
        .section-eyebrow {{ display:block; font-size:0.7rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; color:color-mix(in srgb, var(--cat, var(--clr-accent-text)) 50%, #0a0a0a); margin-bottom:6px; }}
        .category-section {{ padding-top: var(--space-2xl); scroll-margin-top: 90px; }}
        .category-section:last-of-type {{ padding-bottom: var(--space-2xl); }}
        #latest {{ margin-bottom: var(--space-xl); }}
        .category-section__header {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom: var(--space-lg); border-bottom:2px solid var(--clr-black); padding-bottom: var(--space-sm); flex-wrap:wrap; gap: var(--space-sm); }}
        .category-section__header h2 {{ font-size: var(--text-2xl); margin:0; flex:1 1 auto; min-width:0; }}
        .category-section__count {{ font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:var(--clr-mid-gray); }}
        html {{ scroll-behavior:smooth; }}
        @media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior:auto; }} }}
        .niche-card {{ border:1px solid var(--clr-light-gray); border-radius:var(--radius-lg); overflow:hidden; transition: transform var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out); background:var(--clr-white); display:flex; flex-direction:column; }}
        .niche-card:hover {{ transform:translateY(-6px); box-shadow:var(--shadow-lg); }}
        .niche-card__image-wrapper {{ aspect-ratio: 4/3; overflow:hidden; background:var(--clr-white); padding:20px; }}
        .niche-card img {{ width:100%; height:100%; object-fit:contain; transition: transform var(--duration-slow) var(--ease-out); }}
        .niche-card:hover img {{ transform: scale(1.04); }}
        .review-card__media {{ position:relative; }}
        .review-card__banner {{ display:inline-block; padding:4px 12px; border-radius:6px; color:#1a1200; font-size:0.64rem; font-weight:800; text-transform:uppercase; letter-spacing:0.07em; margin-bottom:6px; }}
        .review-card__score {{ position:absolute; right:14px; bottom:14px; z-index:2; display:inline-flex; align-items:baseline; gap:3px; background:rgba(10,10,10,0.92); color:#fff; border-radius:100px; padding:6px 14px; border:1px solid rgba(201,138,44,0.6); backdrop-filter: blur(4px); }}
        .review-card__score-num {{ font-family: var(--font-display); font-size:1.15rem; font-weight:800; color: var(--clr-accent); letter-spacing:-0.02em; line-height:1; }}
        .review-card__score-out {{ font-size:0.7rem; color:#aaa; font-weight:600; }}
        .review-card__body {{ display:flex; flex-direction:column; flex:1; padding: var(--space-md); }}
        .review-card__body h2 {{ font-size: var(--text-lg); margin:0 0 8px; line-height:1.25; }}
        .review-card__body h2 a {{ color:inherit; text-decoration:none; }}
        .review-card__body h2 a:hover {{ color: var(--cat, var(--clr-accent-text)); color: color-mix(in srgb, var(--cat, var(--clr-accent-text)) 55%, #1a1200); }}
        .review-card__snippet {{ font-size:0.9rem; color:var(--clr-mid-gray); line-height:1.5; margin:0 0 var(--space-sm); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
        .review-card__footer {{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:auto; padding-top: var(--space-sm); }}
        .review-card__footer .read-link {{ font-weight:700; font-size:0.82rem; color:var(--clr-black); text-decoration:none; border-bottom:2px solid var(--cat, var(--clr-accent)); border-bottom-color: color-mix(in srgb, var(--cat, var(--clr-accent)) 55%, #1a1200); padding-bottom:1px; }}
        .review-card__footer .read-link:hover {{ color: var(--cat, var(--clr-accent-text)); color: color-mix(in srgb, var(--cat, var(--clr-accent-text)) 55%, #1a1200); }}
        .review-card__reactions {{ display:flex; gap:6px; }}
        .review-card__reactions .reaction-btn {{ display:inline-flex; align-items:center; gap:5px; padding:5px 12px; border:1px solid var(--clr-light-gray); border-radius:999px; background:#fff; color:var(--clr-mid-gray); font-size:0.78rem; font-weight:600; font-family:var(--font-body); }}
        .review-card__reactions .reaction-btn.is-counter {{ cursor:default; }}
        .review-card__reactions .reaction-icon {{ font-size:0.9rem; line-height:1; }}
        .review-card__reactions .reaction-count {{ font-weight:700; min-width:14px; text-align:center; }}
        .review-card__updated {{ display:block; font-size:0.72rem; color:#999; margin-bottom: var(--space-xs); }}
        .niche-card--featured {{ grid-column: 1 / -1; display:grid; grid-template-columns: 1.1fr 1fr; align-items:center; }}
        .niche-card--featured .niche-card__image-wrapper {{ aspect-ratio: 16/10; height:100%; }}
        .niche-card--featured .review-card__body {{ padding: var(--space-xl); }}
        .niche-card--featured h2 {{ font-size: var(--text-2xl); }}
        .niche-card--featured .review-card__score-num {{ font-size:1.5rem; }}
        .niche-card--featured .review-card__snippet {{ -webkit-line-clamp:3; }}
        @media (max-width: 760px) {{ .niche-card--featured {{ grid-template-columns: 1fr; }} .niche-card--featured .review-card__body {{ padding: var(--space-md); }} }}

        .footer {{ background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }}
        .footer-grid {{ display:grid; grid-template-columns:1.6fr 2fr 1fr; gap:var(--space-lg); margin-bottom:var(--space-xl); }}
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
<a class="skip-link" href="#main">Skip to content</a>
<header><div class="container navbar">
    <a href="{b}/" class="logo"><img src="{b}/logo.svg" alt="Abvorn"></a>
    <button class="nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav-links">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <nav class="nav-links" id="nav-links">
        <div class="nav-item"><a href="#">Categories</a><div class="nav-dropdown nav-dropdown--mega">{nav_dd}</div></div>
        <a href="{b}/">Home</a>
        <a href="{b}/about.html">About</a>
        <a href="{b}/journal/">Journal</a>
    </nav>
</div></header>

<main id="main">
{hero_html}

{index_nav}

{sections_html}
</main>

{footer_chrome}

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
        .map(l => {{
            const href = l.getAttribute('href') || '';
            if (!href.startsWith('#')) return null;
            return document.getElementById(href.slice(1));
        }})
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
            method: 'POST', headers: {{'Content-Type': 'text/plain;charset=utf-8'}},
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


def _owner_category_for_niche(slug):
    """Reverse-lookup the parent category name for a niche slug."""
    for cat_name, slugs in CATEGORY_MAP.items():
        if slug in slugs:
            return cat_name
    return _niche_name(slug)


def _dedupe_reviews(reviews):
    """Collapse scan_published_reviews entries to one card per niche.

    Dated article files accumulate over time, so a niche yields many review
    entries that are only different publish dates of the same verdict. Keep
    one per niche: prefer the canonical /reviews/{slug}/ index entry, else
    the most recently updated dated file.
    """
    by_slug = {}
    for r in reviews:
        slug = r.get("slug", "")
        if not slug:
            continue
        if slug not in by_slug:
            by_slug[slug] = r
            continue
        cur = by_slug[slug]
        r_is_index = r.get("rel", "") == f"/reviews/{slug}/"
        cur_is_index = cur.get("rel", "") == f"/reviews/{slug}/"
        if r_is_index and not cur_is_index:
            by_slug[slug] = r
        elif r_is_index == cur_is_index and (r.get("updated", "") or "") > (cur.get("updated", "") or ""):
            by_slug[slug] = r
    return list(by_slug.values())


def _build_category_tiles(b="", accent=None):
    """Grid of tiles on the /categories/ hub, one per top-level category.

    Each tile links to its category landing page (/categories/<slug>/), so the
    hub stops being a dead end and routes browsers to the real category pages.
    """
    tiles = []
    for label in sorted(CATEGORY_MAP.keys(), key=lambda c: c.lower()):
        slug = _category_slug(label)
        color = category_color(label)
        tiles.append(
            f'<a class="cat-tile" href="{b}/categories/{slug}/" style="--cat:{color}">'
            f'<span class="cat-tile__tick" aria-hidden="true"></span>'
            f'<span class="cat-tile__name">{html_mod.escape(label)}</span>'
            f'<span class="cat-tile__arrow" aria-hidden="true">→</span></a>'
        )
    return f'<nav class="cat-tiles container" aria-label="All categories">{"".join(tiles)}</nav>'


def _hub_subscribe_band(accent, hook_text):
    return (
        '<section class="subscribe-band"><div class="container subscribe-inner">'
        '<div class="subscribe-copy">'
        f'<h2>Get alerted when we publish a {hook_text}</h2>'
        '<p>One email whenever we publish a new guide. No spam, unsubscribe anytime.</p>'
        '</div>'
        '<form class="subscribe-form" id="category-subscribe-form" onsubmit="submitCategorySubscribe(event)">'
        '<input type="text" name="_gotcha" class="hp-field" tabindex="-1" autocomplete="off">'
        '<label for="category-subscribe-email" class="sr-only">Email address</label>'
        '<input type="email" class="input" id="category-subscribe-email" placeholder="you@example.com" required>'
        '<button type="submit" class="btn">Notify Me</button>'
        '<p class="subscribe-msg" id="category-subscribe-msg" aria-live="polite"></p>'
        '</form>'
        '</div></section>'
    )


def _hub_sections(reviews, b, accent, group_key, group_label, group_id):
    """Group reviews into category-section blocks (by niche or by category).

    Emits a 'Latest reviews' feature strip, a subscribe band, then one section
    per group. group_key/reviews map a review to its group; group_label maps a
    group to its display name; group_id maps a group to its anchor slug.
    """
    groups = {}
    for r in reviews:
        k = group_key(r)
        groups.setdefault(k, []).append(r)
    for k in groups:
        groups[k].sort(key=lambda r: r.get("updated", ""), reverse=True)
    order = sorted(groups, key=lambda k: group_label(k).lower())
    latest_items = sorted(reviews, key=lambda r: r.get("updated", ""), reverse=True)[:4]
    sections = []
    if reviews:
        latest_cards = "".join(
            review_card(r, _owner_category_for_niche(r.get("slug", "")), b, featured=(i == 0))
            for i, r in enumerate(latest_items)
        )
        sections.append(
            f'<section class="category-section container" id="latest" style="--cat:{accent}">'
            '<span class="section-eyebrow">Fresh this week</span>'
            '<div class="category-section__header"><h2>Latest reviews</h2></div>'
            f'<div class="niche-grid">{latest_cards}</div></section>'
        )
        sections.append(_hub_subscribe_band(accent, "new guide"))
        for k in order:
            n = len(groups[k])
            cards = "".join(
                review_card(r, _owner_category_for_niche(r.get("slug", "")), b) for r in groups[k]
            )
            sections.append(
                f'<section class="category-section container" id="{html_mod.escape(group_id(k))}" style="--cat:{accent}">'
                f'<div class="category-section__header"><h2>{html_mod.escape(group_label(k))}</h2>'
                f'<span class="category-section__count">{n} review{"s" if n != 1 else ""}</span></div>'
                f'<div class="posts-grid">{cards}</div></section>'
            )
    else:
        sections.append(
            '<p style="grid-column:1/-1;text-align:center;color:var(--clr-mid-gray);padding:40px 0">Reviews coming soon.</p>'
        )
    return "".join(sections)


def _hub_page(b, meta_title, meta_desc, canonical_path, hero_html, index_nav, sections_html,
              footer_chrome, form_url, hub_slug, hub_name, accent):
    """Assemble a full top-level hub page (/reviews/, /categories/) in the same
    chrome as a category listing page: shared CSS, mega-menu header, hero, an
    optional contents rail, grouped review sections, footer and scripts."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="{b}/assets/favicon-32x32.png">
    <title>{meta_title} | Abvorn</title>
    <meta name="description" content="{meta_desc}">
    <link rel="canonical" href="{_SITE_URL}{canonical_path}">
    <meta property="og:title" content="{meta_title} | Abvorn">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:url" content="{_SITE_URL}{canonical_path}">
    <meta property="og:type" content="website">
    <meta property="og:image" content="{_SITE_URL}/assets/logo.png"><meta name="twitter:image" content="{_SITE_URL}/assets/logo.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{meta_title} | Abvorn">
    <meta name="twitter:description" content="{meta_desc}">
    {FONT_LINK}
    <style>
        :root {{ --niche-primary: #1a1a1a; --niche-accent: {accent}; --font-mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }}
        {DESIGN_SYSTEM_CSS}
        {PROD_SHOT_CSS}
        
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

        .cat-hero {{ position:relative; overflow:hidden; background:#0d0d0d; color:#fff; padding:clamp(44px,5.5vw,84px) 0; border-bottom:1px solid #222; }}
        .cat-hero__bg {{ position:absolute; inset:0; pointer-events:none; background:
            radial-gradient(900px 420px at 80% 12%, color-mix(in srgb, var(--cat) 16%, transparent), transparent 65%),
            radial-gradient(640px 380px at 8% 96%, color-mix(in srgb, var(--cat) 8%, transparent), transparent 60%); }}
        .cat-hero__grid {{ position:relative; display:grid; grid-template-columns:1.15fr 0.85fr; gap:clamp(24px,4vw,56px); align-items:center; }}
        .cat-hero__eyebrow {{ display:flex; align-items:center; gap:10px; margin:0 0 18px; font-family:var(--font-mono); font-size:0.74rem; font-weight:600; letter-spacing:0.14em; text-transform:uppercase; color:var(--cat); }}
        .cat-hero__dot {{ width:8px; height:8px; border-radius:2px; background:var(--cat); box-shadow:0 0 14px var(--cat); flex-shrink:0; }}
        .cat-hero__title {{ font-family:var(--font-display); font-weight:800; font-size:clamp(var(--text-3xl),4vw,var(--text-4xl)); line-height:1.06; letter-spacing:-0.02em; color:#fff; margin:0 0 16px; }}
        .cat-hero__tagline {{ font-family:var(--font-body); font-size:clamp(1rem,1.5vw,1.15rem); line-height:1.6; color:#b9b9b4; max-width:52ch; margin:0 0 26px; }}
        .cat-hero__chips {{ display:flex; flex-wrap:wrap; gap:12px; margin:0 0 28px; }}
        .cat-hero__chip {{ display:flex; flex-direction:column; gap:3px; min-width:104px; padding:12px 16px; border:1px solid rgba(255,255,255,0.12); border-radius:14px; background:rgba(255,255,255,0.03); }}
        .cat-hero__chip-num {{ font-family:var(--font-mono); font-size:1.5rem; font-weight:700; line-height:1; color:#fff; }}
        .cat-hero__chip-num em {{ font-style:normal; color:var(--cat); }}
        .cat-hero__chip-label {{ font-family:var(--font-body); font-size:0.68rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#8a8a86; }}
        .cat-hero__cta {{ display:flex; align-items:center; gap:18px; flex-wrap:wrap; }}
        .cat-hero__btn {{ display:inline-flex; align-items:center; gap:10px; background:var(--cat); color:#0a0a0a; font-family:var(--font-display); font-weight:800; font-size:1rem; text-decoration:none; padding:0.95em 1.6em; border-radius:12px; box-shadow:0 10px 34px color-mix(in srgb, var(--cat) 45%, transparent); transition:transform var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out); }}
        .cat-hero__btn:hover {{ transform:translateY(-2px); box-shadow:0 14px 44px color-mix(in srgb, var(--cat) 60%, transparent); }}
        .cat-hero__btn svg {{ width:18px; height:18px; }}
        .cat-hero__hint {{ font-family:var(--font-body); font-size:0.8rem; color:#8a8a86; }}
        .cat-hero__coming {{ font-family:var(--font-body); font-size:0.95rem; color:#b9b9b4; }}
        .cat-hero__stage {{ position:relative; display:flex; align-items:center; justify-content:center; }}
        .cat-hero__stage svg {{ width:100%; max-width:440px; height:auto; filter:drop-shadow(0 24px 60px rgba(0,0,0,0.5)); }}
        @media (max-width:900px) {{ .cat-hero__grid {{ grid-template-columns:1fr; }} .cat-hero__stage {{ order:-1; max-width:340px; margin:0 auto; }} }}

        .category-index {{ background:color-mix(in srgb, var(--cat) 12%, var(--clr-off-white)); border-bottom:1px solid color-mix(in srgb, var(--cat) 34%, var(--clr-light-gray)); padding:10px 0; }}
        .category-index__inner {{ display:flex; align-items:center; gap: var(--space-lg); flex-wrap:wrap; }}
        .category-index__label {{ font-size:0.72rem; font-weight:800; text-transform:uppercase; letter-spacing:0.08em; color:color-mix(in srgb, var(--cat) 44%, #0a0a0a); flex-shrink:0; }}
        .category-index__links {{ display:flex; flex-wrap:wrap; align-items:center; gap: var(--space-md); row-gap:8px; }}
        .category-index__link {{ font-family:var(--font-display); font-weight:600; font-size:0.95rem; color:var(--clr-black); text-decoration:none; display:inline-flex; align-items:center; gap:8px; padding:4px 0; border-bottom:2px solid transparent; transition: color var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out); }}
        .category-index__link:hover {{ color:color-mix(in srgb, var(--cat) 44%, #0a0a0a); border-color:var(--cat); }}
        .category-index__link.is-current {{ color:color-mix(in srgb, var(--cat) 44%, #0a0a0a); border-color:var(--cat); }}
        .category-index__tick {{ width:7px; height:7px; border-radius:1px; background:var(--cat, var(--clr-accent)); flex-shrink:0; }}

        .cat-tiles {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(220px,1fr)); gap: var(--space-lg); padding: var(--space-2xl) var(--space-lg); background:var(--clr-off-white); border-bottom:1px solid var(--clr-light-gray); }}
        .cat-tile {{ display:flex; align-items:center; gap:12px; padding:18px 20px; background:var(--clr-white); border:1px solid var(--clr-light-gray); border-radius:var(--radius-lg); color:var(--clr-black); text-decoration:none; transition: transform var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out), border-color var(--duration-base) var(--ease-out); }}
        .cat-tile:hover {{ transform:translateY(-4px); box-shadow:var(--shadow-lg); border-color:var(--cat, var(--clr-accent)); }}
        .cat-tile__tick {{ width:9px; height:9px; border-radius:2px; background:var(--cat, var(--clr-accent)); flex-shrink:0; }}
        .cat-tile__name {{ font-family:var(--font-display); font-weight:700; font-size:1rem; flex:1 1 auto; }}
        .cat-tile__arrow {{ color:var(--clr-mid-gray); font-size:0.9rem; transition: transform var(--duration-fast) var(--ease-out); }}
        .cat-tile:hover .cat-tile__arrow {{ transform:translateX(3px); color:var(--cat, var(--clr-accent)); }}
        @media (max-width:640px) {{ .cat-tiles {{ padding: var(--space-xl) var(--space-md); }} }}

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
        .niche-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(280px,1fr)); gap: var(--space-lg); }}
        .section-eyebrow {{ display:block; font-size:0.7rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; color:color-mix(in srgb, var(--cat, var(--clr-accent-text)) 50%, #0a0a0a); margin-bottom:6px; }}
        .category-section {{ padding-top: var(--space-2xl); scroll-margin-top: 90px; }}
        .category-section:last-of-type {{ padding-bottom: var(--space-2xl); }}
        #latest {{ margin-bottom: var(--space-xl); }}
        .category-section__header {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom: var(--space-lg); border-bottom:2px solid var(--clr-black); padding-bottom: var(--space-sm); flex-wrap:wrap; gap: var(--space-sm); }}
        .category-section__header h2 {{ font-size: var(--text-2xl); margin:0; flex:1 1 auto; min-width:0; }}
        .category-section__count {{ font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:var(--clr-mid-gray); }}
        html {{ scroll-behavior:smooth; }}
        @media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior:auto; }} }}
        .niche-card {{ border:1px solid var(--clr-light-gray); border-radius:var(--radius-lg); overflow:hidden; transition: transform var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out); background:var(--clr-white); display:flex; flex-direction:column; }}
        .niche-card:hover {{ transform:translateY(-6px); box-shadow:var(--shadow-lg); }}
        .niche-card__image-wrapper {{ aspect-ratio: 4/3; overflow:hidden; background:var(--clr-white); padding:20px; }}
        .niche-card img {{ width:100%; height:100%; object-fit:contain; transition: transform var(--duration-slow) var(--ease-out); }}
        .niche-card:hover img {{ transform: scale(1.04); }}
        .review-card__media {{ position:relative; }}
        .review-card__banner {{ display:inline-block; padding:4px 12px; border-radius:6px; color:#1a1200; font-size:0.64rem; font-weight:800; text-transform:uppercase; letter-spacing:0.07em; margin-bottom:6px; }}
        .review-card__score {{ position:absolute; right:14px; bottom:14px; z-index:2; display:inline-flex; align-items:baseline; gap:3px; background:rgba(10,10,10,0.92); color:#fff; border-radius:100px; padding:6px 14px; border:1px solid rgba(201,138,44,0.6); backdrop-filter: blur(4px); }}
        .review-card__score-num {{ font-family: var(--font-display); font-size:1.15rem; font-weight:800; color: var(--clr-accent); letter-spacing:-0.02em; line-height:1; }}
        .review-card__score-out {{ font-size:0.7rem; color:#aaa; font-weight:600; }}
        .review-card__body {{ display:flex; flex-direction:column; flex:1; padding: var(--space-md); }}
        .review-card__body h2 {{ font-size: var(--text-lg); margin:0 0 8px; line-height:1.25; }}
        .review-card__body h2 a {{ color:inherit; text-decoration:none; }}
        .review-card__body h2 a:hover {{ color: var(--cat, var(--clr-accent-text)); color: color-mix(in srgb, var(--cat, var(--clr-accent-text)) 55%, #1a1200); }}
        .review-card__snippet {{ font-size:0.9rem; color:var(--clr-mid-gray); line-height:1.5; margin:0 0 var(--space-sm); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
        .review-card__footer {{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:auto; padding-top: var(--space-sm); }}
        .review-card__footer .read-link {{ font-weight:700; font-size:0.82rem; color:var(--clr-black); text-decoration:none; border-bottom:2px solid var(--cat, var(--clr-accent)); border-bottom-color: color-mix(in srgb, var(--cat, var(--clr-accent)) 55%, #1a1200); padding-bottom:1px; }}
        .review-card__footer .read-link:hover {{ color: var(--cat, var(--clr-accent-text)); color: color-mix(in srgb, var(--cat, var(--clr-accent-text)) 55%, #1a1200); }}
        .review-card__reactions {{ display:flex; gap:6px; }}
        .review-card__reactions .reaction-btn {{ display:inline-flex; align-items:center; gap:5px; padding:5px 12px; border:1px solid var(--clr-light-gray); border-radius:999px; background:#fff; color:var(--clr-mid-gray); font-size:0.78rem; font-weight:600; font-family:var(--font-body); }}
        .review-card__reactions .reaction-btn.is-counter {{ cursor:default; }}
        .review-card__reactions .reaction-icon {{ font-size:0.9rem; line-height:1; }}
        .review-card__reactions .reaction-count {{ font-weight:700; min-width:14px; text-align:center; }}
        .review-card__updated {{ display:block; font-size:0.72rem; color:#999; margin-bottom: var(--space-xs); }}
        .niche-card--featured {{ grid-column: 1 / -1; display:grid; grid-template-columns: 1.1fr 1fr; align-items:center; }}
        .niche-card--featured .niche-card__image-wrapper {{ aspect-ratio: 16/10; height:100%; }}
        .niche-card--featured .review-card__body {{ padding: var(--space-xl); }}
        .niche-card--featured h2 {{ font-size: var(--text-2xl); }}
        .niche-card--featured .review-card__score-num {{ font-size:1.5rem; }}
        .niche-card--featured .review-card__snippet {{ -webkit-line-clamp:3; }}
        @media (max-width: 760px) {{ .niche-card--featured {{ grid-template-columns: 1fr; }} .niche-card--featured .review-card__body {{ padding: var(--space-md); }} }}

        .footer {{ background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }}
        .footer-grid {{ display:grid; grid-template-columns:1.6fr 2fr 1fr; gap:var(--space-lg); margin-bottom:var(--space-xl); }}
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
<a class="skip-link" href="#main">Skip to content</a>
<header><div class="container navbar">
    <a href="{b}/" class="logo"><img src="{b}/logo.svg" alt="Abvorn"></a>
    <button class="nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav-links">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <nav class="nav-links" id="nav-links">
        <div class="nav-item"><a href="#">Categories</a><div class="nav-dropdown nav-dropdown--mega">{build_category_dropdown(b)}</div></div>
        <a href="{b}/">Home</a>
        <a href="{b}/about.html">About</a>
        <a href="{b}/journal/">Journal</a>
    </nav>
</div></header>

<main id="main">
{hero_html}

{index_nav}

{sections_html}
</main>

{footer_chrome}

<script>
const APPS_SCRIPT_URL = "{form_url}";
const CATEGORY_SLUG = "{hub_slug}";
const CATEGORY_NAME = "{hub_name}";

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
        .map(l => {{
            const href = l.getAttribute('href') || '';
            if (!href.startsWith('#')) return null;
            return document.getElementById(href.slice(1));
        }})
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
            method: 'POST', headers: {{'Content-Type': 'text/plain;charset=utf-8'}},
            body: JSON.stringify({{ email: email, niche: CATEGORY_SLUG, source: 'hub_page', lead_magnet: `New ${{CATEGORY_NAME}} guides` }})
        }});
        const result = await response.json();
        msg.innerText = result.success ? 'Success! Check your inbox.' : (result.message || 'Oops, try again.');
    }} catch (err) {{ msg.innerText = 'Connection error. Please try later.'; }}
}}
{REACTIONS_JS_BODY}
</script>
</body>
</html>'''


def build_reviews_hub_page(reviews, all_slugs, base=None, affiliate_tag=""):
    """Full /reviews/ hub page listing every published review, grouped by niche."""
    b = base or SITE_BASE
    reviews = _dedupe_reviews(reviews)
    accent = CATEGORY_COLOR_FALLBACK
    tagline = ("Every product review and buying guide we've published — tested "
               "by hand, judged on real benchmarks, and free of spec-sheet fiction.")
    hero_html = _build_category_hero(
        "Reviews", "reviews", reviews, accent, tagline, heading="All Abvorn Reviews"
    )
    form_url = os.environ.get("APPS_SCRIPT_URL", "")
    sections_html = _hub_sections(
        reviews, b, accent,
        group_key=lambda r: r["slug"],
        group_label=_niche_name,
        group_id=lambda s: s,
    )
    niche_order = sorted({r["slug"] for r in reviews}, key=lambda s: _niche_name(s).lower())
    index_nav = build_category_index("Reviews", b, niche_slugs=niche_order or None, label="Browse the guides")
    return _hub_page(
        b=b,
        meta_title="All Reviews",
        meta_desc="Browse every Abvorn product review and buying guide. We test before we recommend.",
        canonical_path="/reviews/",
        hero_html=hero_html,
        index_nav=index_nav,
        sections_html=sections_html,
        footer_chrome=build_site_footer(b),
        form_url=form_url,
        hub_slug="reviews",
        hub_name=html_mod.escape("Reviews"),
        accent=accent,
    )


def build_categories_hub_page(reviews, all_slugs, base=None, affiliate_tag=""):
    """Full /categories/ hub page, one section per product category."""
    b = base or SITE_BASE
    reviews = _dedupe_reviews(reviews)
    accent = CATEGORY_COLOR_FALLBACK
    tagline = ("Whatever you're shopping for, there's a category built around it — "
               "every review filed under what the purchase is actually for.")
    hero_html = _build_category_hero(
        "Categories", "categories", reviews, accent, tagline, heading="Browse by Category"
    )
    form_url = os.environ.get("APPS_SCRIPT_URL", "")
    sections_html = _hub_sections(
        reviews, b, accent,
        group_key=lambda r: _owner_category_for_niche(r["slug"]),
        group_label=lambda c: c,
        group_id=_category_slug,
    )
    return _hub_page(
        b=b,
        meta_title="All Categories",
        meta_desc="Browse every Abvorn review category. Independent product reviews and buying guides, based on real testing.",
        canonical_path="/categories/",
        hero_html=hero_html,
        index_nav=_build_category_tiles(b, accent),
        sections_html=sections_html,
        footer_chrome=build_site_footer(b),
        form_url=form_url,
        hub_slug="categories",
        hub_name=html_mod.escape("Categories"),
        accent=accent,
    )


SHARE_HTML_T = """<div class="share-buttons" style="display:flex;gap:8px;margin:32px 0;padding-top:24px;border-top:1px solid var(--border);align-items:center;flex-wrap:wrap">
<span style="font-size:.85rem;font-weight:600;color:var(--text-secondary);margin-right:8px">Share:</span>
<a href="https://twitter.com/intent/tweet?text=TITLE_T&url=URL_T&via=Abvorn" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:background var(--duration-fast) var(--ease-out),color var(--duration-fast) var(--ease-out),border-color var(--duration-fast) var(--ease-out)" aria-label="Share on X"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>
<a href="https://www.facebook.com/sharer/sharer.php?u=URL_T" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:background var(--duration-fast) var(--ease-out),color var(--duration-fast) var(--ease-out),border-color var(--duration-fast) var(--ease-out)" aria-label="Share on Facebook"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg> Facebook</a>
<a href="https://pinterest.com/pin/create/button/?url=URL_T&description=TITLE_T" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:background var(--duration-fast) var(--ease-out),color var(--duration-fast) var(--ease-out),border-color var(--duration-fast) var(--ease-out)" aria-label="Share on Pinterest"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M12.017 0C5.396 0 .029 5.367.029 11.987c0 5.079 3.158 9.417 7.618 11.162-.105-.949-.199-2.403.041-3.439.219-.937 1.406-5.957 1.406-5.957s-.359-.72-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 01.083.345l-.333 1.36c-.053.22-.174.267-.402.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.631-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146 1.124.347 2.317.535 3.554.535 6.607 0 11.974-5.367 11.974-11.987C23.97 5.367 18.603.001 12.017.001z"/></svg> Pinterest</a>
<a href="mailto:?subject=TITLE_T&body=URL_T" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-alt);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.85rem;color:var(--text-secondary);text-decoration:none;transition:background var(--duration-fast) var(--ease-out),color var(--duration-fast) var(--ease-out),border-color var(--duration-fast) var(--ease-out)" aria-label="Share via Email"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg> Email</a>
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
fetch(URLS, {method:'POST', headers:{'Content-Type':'text/plain;charset=utf-8'}, body:JSON.stringify({action:'reactions', slugs:slugs})})
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
  fetch(URLS, {method:'POST', headers:{'Content-Type':'text/plain;charset=utf-8'},
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
    fetch(URLS, {method:'POST', headers:{'Content-Type':'text/plain;charset=utf-8'},
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
    moderate:'Some of your priorities don\\'t match this product.',
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
    """Warm-editorial article page.

    Single source of truth lives in run_cycle.build_article_page; this
    deployment-side entry point delegates so every builder ships the same
    verified warm design. Imported lazily to avoid a circular import.
    """
    from run_cycle import build_article_page as _canonical
    return _canonical(
        niche_slug, niche_name, post_title, article_html, intro, product_name,
        meta_desc, all_slugs, products=products, pexels_key=pexels_key,
        amazon_tag=amazon_tag, form_url=form_url, hero_img=hero_img,
        google_client_id=google_client_id, related_niches=related_niches,
        published_date=published_date, updated_date=updated_date,
        article_id=article_id,
    )


def build_comparison_page(niche_slug, niche_name, post_title, products, all_slugs, amazon_tag=""):
    """Delegates to run_cycle.build_comparison_page (single source of truth)."""
    from run_cycle import build_comparison_page as _canonical
    return _canonical(niche_slug, niche_name, post_title, products, all_slugs, amazon_tag)


def build_methodology_page(all_slugs, form_url=""):
    """Delegates to run_cycle.build_methodology_page (single source of truth)."""
    from run_cycle import build_methodology_page as _canonical
    return _canonical(all_slugs, form_url)


def _overlay_review(a, slug, niche_name, today):
    """Build a full review entry for a freshly-written article so its card shows
    the real product photo and verdict instead of the blank generated fallback.

    scan_published_reviews() reads published pages from disk, but an article
    written this cycle is not on disk yet when the homepage/category pages are
    built. The overlay entry carries the same image/score the published page
    will embed, so the newest review renders correctly immediately.
    """
    image = ""
    score = None
    breakdown = {}
    label = ""
    product_name = a.get("product_name", "")
    products = a.get("products") or []
    if products:
        p0 = products[0]
        image = p0.get("image", "")
        if image:
            image = upgrade_product_image(image)
        product_name = p0.get("name", product_name)
        try:
            from abvorn.core.verdict import AbvornVerdictEngine
            verdict = AbvornVerdictEngine(weight_overrides=load_verdict_weights()).score_product(slug, p0)
            if verdict:
                score = verdict.get("overall")
                label = verdict.get("label", "")
                breakdown = verdict.get("breakdown", {})
        except Exception:
            score = None
    return {
        "slug": slug,
        "name": niche_name,
        "title": a.get("post_title", ""),
        "updated": today,
        "rel": f"/reviews/{slug}/",
        "snippet": (a.get("intro") or "")[:160],
        "image": image,
        "score": score,
        "breakdown": breakdown,
        "label": label,
        "product_name": product_name,
    }


SITE_ROBOTS_TXT = """User-agent: *
Allow: /
Disallow: /assets/hero/
Disallow: /plans/
Disallow: /specs/

# Prevent scraping of article content by known content scrapers
User-agent: CCBot
Disallow: /

User-agent: Imagesiftbot
Disallow: /

User-agent: Diffbot
Disallow: /

# AI search and citation engines — we want Abvorn cited in AI answers
User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: Bingbot
Allow: /

Sitemap: https://abvorn.com/sitemap.xml
"""


def write_site_metadata(docs_dir, items):
    """Write robots.txt, llms.txt, feed.xml and sitemap.xml into the site root.

    robots.txt deliberately ALLOWS AI search bots (citation) and blocks only
    training-only crawlers (CCBot) plus known content scrapers.
    llms.txt is the machine-readable site map for AI agents (llmstxt.org).
    """
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(exist_ok=True)

    write_checked(docs_dir / "robots.txt", SITE_ROBOTS_TXT, "robots.txt")

    latest = "\n".join(
        f"- {it.get('title', 'Review')} — {SITE_BASE}/{it['slug'].lstrip('/')}"
        for it in items[:20]
    )
    llms_txt = (
        "# Abvorn\n\n"
        "> Independent product reviews and buying guides. We test before we recommend "
        "— verdicts are based on measured specs, real prices, and scored comparisons, not spec sheets.\n\n"
        "## Core pages\n"
        f"- Home — {SITE_BASE}/\n"
        f"- All Reviews — {SITE_BASE}/reviews/\n"
        f"- Categories — {SITE_BASE}/categories/\n"
        f"- How We Test — {SITE_BASE}/how-we-test/\n"
        f"- About — {SITE_BASE}/about/\n"
        f"- Journal — {SITE_BASE}/journal/\n\n"
        "## Latest reviews\n" + latest + "\n"
    )
    write_checked(docs_dir / "llms.txt", llms_txt, "llms.txt")

    rss_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Abvorn Reviews</title><link>https://abvorn.com</link><description>Product reviews you can trust</description>'
    for it in items:
        rss_xml += f'<item><title>{it["title"]}</title><link>https://abvorn.com/{it["slug"]}</link><guid>https://abvorn.com/{it["slug"]}</guid><pubDate>{it["date"]}</pubDate></item>'
    rss_xml += '</channel></rss>'
    (docs_dir / "feed.xml").write_text(rss_xml, encoding="utf-8")

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += '<url><loc>https://abvorn.com/</loc></url>\n'
    for it in items:
        sitemap += f'<url><loc>https://abvorn.com/{it["slug"]}</loc></url>\n'
    sitemap += '</urlset>'
    (docs_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    print("  Written: docs/feed.xml, docs/sitemap.xml, docs/robots.txt, docs/llms.txt")


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
            reviews.append(_overlay_review(
                a, slug,
                next((n["name"] for n in state["niches"] if n["slug"] == slug), slug.replace("-", " ").title()),
                today,
            ))

    # Collect all published posts across niches (drives feed, sitemap, niche pages)
    all_posts = [{"title": r["title"], "slug": r["rel"].lstrip("/")} for r in reviews]

    # Write root index (premium homepage)
    write_checked(docs / "index.html", build_homepage(state, form_url, reviews=reviews, base=SITE_BASE), "homepage")
    print(f"  Written: docs/index.html")

    # Write category listing pages (one per category, e.g. /categories/audio/)
    for cat_name, cat_slugs in CATEGORY_MAP.items():
        cat_slug = _category_slug(cat_name)
        cat_items = [r for r in reviews if r["slug"] in cat_slugs]
        cat_items.sort(key=lambda r: r["updated"], reverse=True)
        cat_dir = docs / "categories" / cat_slug
        cat_dir.mkdir(parents=True, exist_ok=True)
        write_checked(
            cat_dir / "index.html",
            build_category_listing_page(cat_name, cat_slug, cat_items, all_slugs, base=SITE_BASE, affiliate_tag=amazon_tag),
            f"category page {cat_slug}",
        )
        print(f"  Written: docs/categories/{cat_slug}/index.html")

    # Top-level hub pages — /reviews/ and /categories/ aggregate across niches.
    reviews_dir = docs / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    write_checked(
        reviews_dir / "index.html",
        build_reviews_hub_page(reviews, all_slugs, base=SITE_BASE, affiliate_tag=amazon_tag),
        "reviews hub page",
    )
    print("  Written: docs/reviews/index.html")
    write_checked(
        docs / "categories" / "index.html",
        build_categories_hub_page(reviews, all_slugs, base=SITE_BASE, affiliate_tag=amazon_tag),
        "categories hub page",
    )
    print("  Written: docs/categories/index.html")

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
{FONT_LINK}
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Inter',sans-serif;color:#333;line-height:1.6}}
.skip-link{{position:absolute;top:-100px;left:8px;background:var(--clr-accent,#c98a2c);color:#fff;padding:8px 16px;z-index:200;border-radius:0 0 4px;font-size:.9rem;text-decoration:none;transition:top .15s}}
.skip-link:focus{{top:0;color:#fff}}
header{{background:#0a0a0a;padding:18px 0;border-bottom:1px solid #2a2a2a;position:sticky;top:0;z-index:100}}
.header-inner{{display:flex;justify-content:space-between;align-items:center;max-width:1200px;margin:0 auto;padding:0 20px}}
.logo-img{{max-height:44px;width:auto}}
.main{{padding:60px 20px;max-width:800px;margin:0 auto}}
footer{{background:#0a0a0a;color:#888;padding:40px 0;text-align:center;border-top:1px solid #2a2a2a}}
footer a{{color:#aaa;text-decoration:none}}
</style></head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<header><div class="header-inner"><a href="{b}/"><img src="{b}/logo.svg" alt="Abvorn" class="logo-img"></a></div></header>
<main class="main" id="main"><h1>{title}</h1>{content}</main>
<footer><img src="{b}/logo.svg" alt="Abvorn" style="max-height:24px;width:auto;filter:brightness(0.8);margin-bottom:8px"><p>&copy; {year} Abvorn</p></footer>
</body></html>'''
            page_path.write_text(full_page, encoding="utf-8")
            print(f"  Written: docs/{page_name}")

    # Write category pages (post slugs point to reviews/{slug} for article pages)
    for n in state["niches"]:
        niche_reviews = [r for r in reviews if r["slug"] == n["slug"]]
        niche_reviews.sort(key=lambda r: r.get("updated", ""), reverse=True)
        if not niche_reviews:
            niche_reviews = [
                {"slug": n["slug"], "name": n["name"], "title": a.get("post_title", n["name"]),
                 "updated": "", "rel": f"/reviews/{n['slug']}/", "snippet": "",
                 "image": "", "score": None, "breakdown": {}, "label": "", "product_name": ""}
                for a in articles.get(n["slug"], [])
            ]
        cat_dir = docs / n["slug"]
        cat_dir.mkdir(exist_ok=True)
        write_checked(cat_dir / "index.html", build_category_page(n["slug"], n["name"], niche_reviews, all_slugs, amazon_tag), f"niche page {n['slug']}")

    # Write comparison pages
    comp_dir = docs / "comparisons"
    comp_dir.mkdir(exist_ok=True)
    for n in state["niches"]:
        prods = []
        for a in articles.get(n["slug"], []):
            prods.extend(a.get("products", []))
        if prods:
            title = f"Best {n['name']} Compared"
            write_checked(
                comp_dir / f"{n['slug']}.html",
                build_comparison_page(n["slug"], n["name"], title, prods, all_slugs, amazon_tag),
                f"comparison page {n['slug']}",
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
            date_str = datetime.now().strftime("%Y-%m-%d")
            suffix = "" if i == 0 else f"-{i}"
            fname = f"{_title_slug(a['post_title'])}-{date_str}{suffix}.html"
            # Persist the article's real publish date across cycles so a re-run
            # does not slide "Published" forward to today (see run_cycle copy).
            _publish_anchor = None
            _anchor_re = re.compile(r"-(\d{4}-\d{2}-\d{2})\.(?:html|pdf)$")
            for _existing in sorted(post_dir.glob("*.html")):
                if _title_slug(a["post_title"]) in _existing.name:
                    _m = _anchor_re.search(_existing.name)
                    if _m:
                        _publish_anchor = _m.group(1)
                        break
            if not _publish_anchor:
                try:
                    _idx_html = (post_dir / "index.html").read_text(encoding="utf-8")
                    _pm = re.search(r"Published ([A-Za-z]+ \d{1,2}, \d{4})", _idx_html)
                    if _pm:
                        _publish_anchor = datetime.strptime(_pm.group(1), "%b %d, %Y").strftime("%Y-%m-%d")
                except Exception:
                    _publish_anchor = None
            article_html = build_article_page(slug, niche_name, a["post_title"], a["article_html"],
                                              a["intro"], a["product_name"], a["meta_description"],
                                              all_slugs, a.get("products"), pexels_key, amazon_tag, form_url, hero_img_html, google_client_id,
                                              related_niches=related, article_id=f"{slug}-{i}",
                                              published_date=_publish_anchor or date_str, updated_date=date_str)
            try:
                verify_page(article_html)
            except ValueError as e:
                logger.error(f"❌ Page verification failed for {slug}/{fname}: {e}")
                raise
            write_checked(post_dir / fname, article_html, f"article {slug}/{fname}")
            print(f"  Written: docs/reviews/{slug}/{fname} (article)")
            if i == len(post_list) - 1:
                write_checked(post_dir / "index.html", article_html, f"article index {slug}")
                print(f"  Written: docs/reviews/{slug}/index.html (latest)")
            # Update the post slug in all_posts for root index links
            for p in all_posts:
                if p.get("title") == a.get("post_title") and p.get("slug") == slug:
                    p["slug"] = f"reviews/{slug}"

    # Write methodology page
    method_dir = docs / "how-we-test"
    method_dir.mkdir(exist_ok=True)
    write_checked(method_dir / "index.html", build_methodology_page(all_slugs, form_url), "methodology page")
    print(f"  Written: docs/how-we-test/index.html")

    # Write robots.txt, llms.txt, RSS feed and sitemap
    items = []
    for p in all_posts:
        title = p.get("title", "")
        slug_path = p.get("slug", "")
        if not slug_path.endswith("/"):
            slug_path = slug_path.rsplit("/", 1)[0] + "/"
        items.append({"title": title, "slug": slug_path,
                      "date": datetime.date.today().isoformat() if 'datetime' in dir() else "2025-01-01"})
    write_site_metadata(docs, items)


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
<header><div class="container navbar">
    <a href="{b}/" class="logo"><img src="{b}/logo.svg" alt="Abvorn" style="max-height:44px;width:auto"></a>
    <button class="nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav-links">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <nav class="nav-links" id="nav-links">
        {dropdown}
        <a href="{b}/">Home</a>
        <a href="{b}/about.html">About</a>
        <a href="{b}/journal/">Journal</a>
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


# ── Evolution Journal ─────────────────────────────────────────────
# Public-facing "Ab's Evolution Journal" page. Real data only: reads the
# Obsidian vault journal (via cortex_watcher), the Genesis lineage file,
# and the Neural Memory state file. The static page embeds a snapshot for
# GitHub Pages (no backend) and live-polls /api/evolution/public when the
# mobile server is reachable, gracefully falling back to the snapshot.


def _read_json_safe(path):
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _journal_entry_narrative(body: str) -> str:
    """Trim a vault journal body down to its narrative (drop the H1 heading)."""
    text = re.sub(r"^#\s+.*$", "", body, flags=re.M)
    text = re.sub(r"^-\s*$", "", text, flags=re.M)
    return text.strip()


def load_evolution_snapshot():
    """Build {summary, entries} from real local sources.

    summary: current_generation, total_entries, graph_nodes, graph_edges,
             last_update
    entries: [{timestamp, generation, narrative}] newest first.
    Never raises; falls back to zeros/empty when a source is missing.
    """
    entries = []
    try:
        from abvorn.core.cortex_watcher import get_vault_path

        vault = get_vault_path()
        if vault is not None:
            journal_dir = vault / "Journal"
            if journal_dir.exists():
                for f in sorted(journal_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True):
                    try:
                        raw = f.read_text(encoding="utf-8")
                    except Exception:
                        continue
                    fm = {}
                    body = raw
                    try:
                        import frontmatter as _fm

                        post = _fm.loads(raw)
                        fm = dict(post.metadata or {})
                        body = post.content or ""
                    except Exception:
                        pass
                    stamp = fm.get("date") or datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                    if not isinstance(stamp, str):
                        try:
                            stamp = stamp.isoformat()
                        except Exception:
                            stamp = str(stamp)
                    gen = fm.get("generation") or 1
                    sections = re.split(r"^##\s+Cycle\s+\d+", body, flags=re.M)
                    # First chunk (pre-Cycle) is the opening narrative; each
                    # "## Cycle N" chunk is a later entry from the same day.
                    for i, chunk in enumerate(sections):
                        narrative = _journal_entry_narrative(chunk)
                        if not narrative:
                            continue
                        entries.append({
                            "timestamp": stamp,
                            "generation": gen,
                            "narrative": narrative,
                        })
    except Exception:
        pass

    lineage = _read_json_safe("data/genesis/lineage.json") or {}
    current_generation = lineage.get("current_version", 1)

    memory = _read_json_safe("data/neural_memory_state.json") or {}
    graph_nodes = int(memory.get("entities") or 0)
    graph_edges = int(memory.get("relationships") or 0)

    last_update = ""
    if entries:
        last_update = max(e.get("timestamp", "") for e in entries)
    elif memory.get("last_ingestion"):
        last_update = memory["last_ingestion"]

    summary = {
        "current_generation": int(current_generation),
        "total_entries": len(entries),
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "last_update": last_update,
    }
    return {"summary": summary, "entries": entries}


def _read_previous_journal_snapshot():
    """Load the INITIAL snapshot embedded in the existing docs/journal/index.html.

    Used to avoid clobbering a real journal page with an empty snapshot when the
    build runs somewhere the local sources (Obsidian vault, lineage, memory
    state) are absent — e.g. CI content cycles, which have no vault access.
    Returns None when there is nothing sensible to preserve.
    """
    try:
        path = Path("docs/journal/index.html")
        if not path.exists():
            return None
        html = path.read_text(encoding="utf-8")
        m = re.search(r"const INITIAL = (\{.*?\});", html, re.S)
        if not m:
            return None
        prev = json.loads(m.group(1))
        if prev.get("entries"):
            return prev
        if prev.get("summary", {}).get("graph_nodes") or prev.get("summary", {}).get("graph_edges"):
            return prev
    except Exception:
        pass
    return None


def build_journal_page(b=""):
    """Full static journal page (docs/journal/index.html) in the site world.

    Embeds a build-time snapshot of Ab's evolution (vault journal + lineage +
    memory), then live-polls /api/evolution/public every 30s when reachable.
    No CTA: there is no working platform to send people to yet.
    """
    b = b or SITE_BASE
    data = load_evolution_snapshot()
    # Preserve the last known-good snapshot when this build has no local
    # sources (vault/lineage/memory missing, e.g. in CI) — otherwise an empty
    # snapshot would overwrite real journal entries on every cycle.
    if not data["entries"] and not (data["summary"]["graph_nodes"] or data["summary"]["graph_edges"]):
        prev = _read_previous_journal_snapshot()
        if prev is not None:
            data = prev
    summary = data["summary"]
    entries = data["entries"]
    snapshot_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    header_html = build_site_header(b)
    footer_html = build_site_footer(b)
    year_str = str(datetime.now().year)

    def _stat_chip(num, label, suffix=""):
        return (
            f'<div class="journal-stat"><span class="journal-stat__num" data-count="{num}">{num}</span>'
            f'<span class="journal-stat__label">{label}</span>{suffix}</div>'
        )

    chips = (
        _stat_chip(summary["current_generation"], "Generation", '<span class="journal-stat__gen">gen</span>')
        + _stat_chip(summary["total_entries"], "Journal entries")
        + _stat_chip(summary["graph_nodes"], "Graph nodes")
        + _stat_chip(summary["graph_edges"], "Graph edges")
    )

    # Timeline rows are rendered server-side from the snapshot; the poller
    # re-renders the same row template when a live payload arrives.
    timeline_rows = "".join(
        f'<li class="journal-entry">'
        f'<span class="journal-entry__rail" aria-hidden="true"></span>'
        f'<div class="journal-entry__body">'
        f'<span class="journal-entry__meta"><span class="journal-entry__gen">Gen {int(e["generation"])}</span>'
        f'<time class="journal-entry__time" datetime="{e["timestamp"]}">{e["timestamp"]}</time></span>'
        f'<p class="journal-entry__text">{html_mod.escape(e["narrative"])}</p>'
        f'</div></li>'
        for e in entries
    )
    if not timeline_rows:
        timeline_rows = (
            '<li class="journal-entry journal-entry--empty">'
            '<div class="journal-entry__body"><p class="journal-entry__text">No evolution entries yet — '
            'Ab writes its first journal entry the next time the core cycles.</p></div></li>'
        )

    last_update_txt = summary["last_update"] or "—"
    live_hint = (
        "Live on /api/evolution/public" if b.startswith("http") else "Polls the local evolution API"
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<!--
THESIS: A transparent, dark "core readout" for Ab's self-improvement — the
category-default "blog-style about page" it refuses is a static marketing wall.
OWN-WORLD: inherits the dark showroom — #0d0d0d hero, brand gold #c98a2c,
Libre Franklin display, Inter body, JetBrains Mono data. LIVE pulse, mono stat
chips, and a timeline rail make the system feel alive and honest.
STORY: a visitor understands Ab is an evolving system, sees its real counters
and journal, and watches the page refresh itself every 30s.
FIRST VIEWPORT: dark hero with the brand eyebrow + LIVE badge, a 2x2 stat grid
in mono, and the top of the timeline rail with its newest entry.
FORM: shaped directly inside the established world (precise request, no seed).
FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, and DESIGN.md
-->
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/png" href="{b}/assets/favicon-32x32.png">
<title>Ab's Evolution Journal | Abvorn</title>
<meta name="description" content="Watch Ab — Abvorn's AI — evolve, generation by generation. A live journal of the system writing itself smarter.">
<link rel="canonical" href="{_SITE_URL}/journal/">
<meta property="og:title" content="Ab's Evolution Journal | Abvorn">
<meta property="og:description" content="Watch Ab — Abvorn's AI — evolve, generation by generation. A live journal of the system writing itself smarter.">
<meta property="og:url" content="{_SITE_URL}/journal/">
<meta property="og:type" content="website">
<meta property="og:image" content="{_SITE_URL}/assets/logo.png"><meta name="twitter:image" content="{_SITE_URL}/assets/logo.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Ab's Evolution Journal | Abvorn">
<meta name="twitter:description" content="Watch Ab — Abvorn's AI — evolve, generation by generation. A live journal of the system writing itself smarter.">
{FONT_LINK}
<style>
:root {{ --font-mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }}
{DESIGN_SYSTEM_CSS}
{SITE_CHROME_CSS}
{MEGA_MENU_CSS}
.journal-hero {{ position:relative; overflow:hidden; background:#0d0d0d; color:#fff; padding:clamp(56px,7vw,96px) 0; border-bottom:1px solid #222; }}
.journal-hero__bg {{ position:absolute; inset:0; pointer-events:none; background:
  radial-gradient(900px 460px at 82% 8%, rgba(201,138,44,0.16), transparent 62%),
  radial-gradient(640px 400px at 6% 100%, rgba(201,138,44,0.07), transparent 58%); }}
.journal-hero__grid {{ position:relative; display:grid; grid-template-columns:1.15fr 0.85fr; gap:clamp(24px,4vw,56px); align-items:center; }}
.journal-hero__eyebrow {{ display:flex; align-items:center; gap:12px; margin:0 0 20px; font-family:var(--font-mono); font-size:0.74rem; font-weight:600; letter-spacing:0.14em; text-transform:uppercase; color:#c98a2c; }}
.journal-hero__dot {{ width:8px; height:8px; border-radius:2px; background:#c98a2c; box-shadow:0 0 14px #c98a2c; flex-shrink:0; }}
.journal-live {{ display:inline-flex; align-items:center; gap:8px; padding:5px 14px; border:1px solid rgba(201,138,44,0.5); border-radius:100px; font-size:0.7rem; font-weight:700; letter-spacing:0.12em; color:#e6c078; }}
.journal-live__dot {{ width:7px; height:7px; border-radius:50%; background:#7fbf7f; box-shadow:0 0 10px rgba(127,191,127,0.9); }}
.journal-live.is-polling .journal-live__dot {{ animation: live-pulse 2s ease-in-out infinite; }}
@keyframes live-pulse {{ 0%,100% {{ opacity:1; box-shadow:0 0 10px rgba(127,191,127,0.9); }} 50% {{ opacity:0.45; box-shadow:0 0 4px rgba(127,191,127,0.4); }} }}
.journal-hero__title {{ font-family:var(--font-display); font-weight:800; font-size:clamp(var(--text-3xl),4vw,var(--text-4xl)); line-height:1.04; letter-spacing:-0.02em; color:#fff; margin:0 0 18px; }}
.journal-hero__tagline {{ font-family:var(--font-body); font-size:clamp(1rem,1.5vw,1.15rem); line-height:1.65; color:#b9b9b4; max-width:50ch; margin:0 0 30px; }}
.journal-stats {{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:12px; margin-bottom:34px; }}
.journal-stat {{ position:relative; padding:16px 18px; border:1px solid rgba(255,255,255,0.12); border-radius:14px; background:rgba(255,255,255,0.03); }}
.journal-stat__num {{ font-family:var(--font-mono); font-size:clamp(1.5rem,2.6vw,2.1rem); font-weight:700; line-height:1; color:#fff; display:block; margin-bottom:8px; }}
.journal-stat__label {{ font-family:var(--font-body); font-size:0.66rem; font-weight:600; letter-spacing:0.09em; text-transform:uppercase; color:#8a8a86; display:block; }}
.journal-stat__gen {{ position:absolute; top:14px; right:14px; font-family:var(--font-mono); font-size:0.6rem; font-weight:700; letter-spacing:0.1em; color:#8a8a86; text-transform:uppercase; }}
.journal-hero__foot {{ display:flex; align-items:center; gap:16px; flex-wrap:wrap; }}
.journal-hero__hint {{ font-family:var(--font-mono); font-size:0.76rem; color:#8a8a86; }}
@media (max-width:900px) {{ .journal-hero__grid {{ grid-template-columns:1fr; }} .journal-stats {{ grid-template-columns:repeat(2, minmax(0,1fr)); }} }}
@media (max-width:480px) {{ .journal-stats {{ grid-template-columns:1fr 1fr; gap:10px; }} .journal-stat {{ padding:14px; }} }}

.journal-timeline {{ position:relative; }}
.journal-timeline__head {{ display:flex; align-items:baseline; justify-content:space-between; flex-wrap:wrap; gap:12px; margin-bottom: var(--space-lg); border-bottom:2px solid var(--clr-black); padding-bottom: var(--space-sm); }}
.journal-timeline__title {{ font-size: var(--text-2xl); margin:0; }}
.journal-timeline__controls {{ display:flex; align-items:center; gap:14px; }}
.journal-autoscroll {{ display:flex; align-items:center; gap:8px; font-size:0.8rem; font-weight:600; color:var(--clr-mid-gray); cursor:pointer; user-select:none; }}
.journal-autoscroll input {{ accent-color:#c98a2c; cursor:pointer; }}
.journal-timeline__list {{ list-style:none; display:flex; flex-direction:column; gap:0; margin:0; padding:0; }}
.journal-entry {{ position:relative; display:grid; grid-template-columns:34px minmax(0,1fr); gap:18px; padding:0 0 var(--space-lg); }}
.journal-entry__rail {{ position:relative; width:2px; background:var(--clr-light-gray); border-radius:2px; justify-self:center; }}
.journal-entry__rail::before {{ content:''; position:absolute; top:2px; left:50%; transform:translateX(-50%); width:12px; height:12px; border-radius:50%; background:var(--clr-white); border:3px solid #c98a2c; box-shadow:0 0 0 4px rgba(201,138,44,0.14); }}
.journal-entry:last-child .journal-entry__rail {{ background:linear-gradient(var(--clr-light-gray), transparent); }}
.journal-entry__meta {{ display:flex; align-items:center; gap:12px; margin-bottom:6px; flex-wrap:wrap; }}
.journal-entry__gen {{ font-family:var(--font-mono); font-size:0.68rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#1a1200; background:#c98a2c; padding:4px 10px; border-radius:100px; }}
.journal-entry__time {{ font-family:var(--font-mono); font-size:0.76rem; color:var(--clr-mid-gray); }}
.journal-entry__text {{ font-family:var(--font-body); font-size:1rem; line-height:1.65; color:var(--clr-off-black); margin:0; max-width:70ch; }}
.journal-entry--empty .journal-entry__text {{ color:var(--clr-mid-gray); }}
.journal-entry.is-new {{ animation: entry-in 600ms var(--ease-out); }}
@keyframes entry-in {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:none; }} }}
@media (max-width:640px) {{ .journal-entry {{ grid-template-columns:22px minmax(0,1fr); gap:12px; }} }}
</style>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
{header_html}

<main id="main">
<section class="journal-hero">
    <div class="journal-hero__bg" aria-hidden="true"></div>
    <div class="container journal-hero__grid">
        <div>
            <p class="journal-hero__eyebrow"><span class="journal-hero__dot" aria-hidden="true"></span>System readout · generation {summary["current_generation"]}</p>
            <h1 class="journal-hero__title">Ab's Evolution Journal</h1>
            <p class="journal-hero__tagline">Ab is the AI that runs Abvorn — it writes reviews, learns from real signals, and rewrites itself. This page watches it grow, generation by generation.</p>
            <div class="journal-stats">
                {chips}
            </div>
            <div class="journal-hero__foot">
                <span class="journal-live is-polling" id="journal-live" role="status"><span class="journal-live__dot" aria-hidden="true"></span><span id="journal-live-label">LIVE · 30s refresh</span></span>
                <span class="journal-hero__hint" id="journal-hint">Snapshot @ build · {html_mod.escape(live_hint)}</span>
            </div>
        </div>
        <div class="journal-hero__stage" aria-hidden="true">
            <svg viewBox="0 0 420 300" role="img" aria-label="Evolution graph motif">
                <rect x="10" y="10" width="400" height="280" rx="20" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.1)"/>
                <g stroke="rgba(201,138,44,0.35)" stroke-width="1.5" fill="none">
                    <path d="M120,120 L200,70 L300,130 L260,200 L170,190 Z"/>
                    <line x1="200" y1="70" x2="300" y2="130"/>
                    <line x1="120" y1="120" x2="170" y2="190"/>
                    <line x1="300" y1="130" x2="260" y2="200"/>
                    <line x1="170" y1="190" x2="260" y2="200"/>
                    <line x1="200" y1="70" x2="120" y2="120"/>
                </g>
                <g>
                    <circle cx="120" cy="120" r="6" fill="#c98a2c"/>
                    <circle cx="200" cy="70" r="6" fill="#c98a2c"/>
                    <circle cx="300" cy="130" r="6" fill="#c98a2c"/>
                    <circle cx="260" cy="200" r="6" fill="#c98a2c"/>
                    <circle cx="170" cy="190" r="6" fill="#c98a2c"/>
                    <circle cx="210" cy="140" r="3" fill="#e6c078"/>
                </g>
                <text x="40" y="250" font-family="JetBrains Mono, monospace" font-size="11" font-weight="600" letter-spacing="0.1em" fill="#8a8a86">EVOLUTION GRAPH</text>
                <text x="40" y="272" font-family="JetBrains Mono, monospace" font-size="16" font-weight="700" fill="#fff">{summary["graph_nodes"]} NODES</text>
                <text x="340" y="272" font-family="JetBrains Mono, monospace" font-size="16" font-weight="700" fill="#c98a2c" text-anchor="end">{summary["graph_edges"]} EDGES</text>
            </svg>
        </div>
    </div>
</section>

<section class="container" id="journal" style="padding-top:var(--space-2xl);">
    <div class="journal-timeline">
        <div class="journal-timeline__head">
            <h2 class="journal-timeline__title">The journal</h2>
            <div class="journal-timeline__controls">
                <label class="journal-autoscroll" for="journal-autoscroll">
                    <input type="checkbox" id="journal-autoscroll" checked>
                    <span>Auto-scroll to newest</span>
                </label>
            </div>
        </div>
        <ul class="journal-timeline__list" id="journal-timeline" aria-live="polite">
            {timeline_rows}
        </ul>
    </div>
</section>
</main>

{footer_html}

<script>
const SITE_BASE = {json.dumps(b, ensure_ascii=False)};
const INITIAL = {snapshot_json};
const $ = (s) => document.querySelector(s);

function rowHTML(e) {{
    const t = document.createElement('template');
    t.innerHTML = '<li class="journal-entry">'
        + '<span class="journal-entry__rail" aria-hidden="true"></span>'
        + '<div class="journal-entry__body">'
        + '<span class="journal-entry__meta"><span class="journal-entry__gen">Gen ' + (e.generation || 1) + '</span>'
        + '<time class="journal-entry__time" datetime="' + e.timestamp + '">' + e.timestamp + '</time></span>'
        + '<p class="journal-entry__text"></p></div></li>';
    t.content.querySelector('.journal-entry__text').textContent = e.narrative || '';
    return t.content.firstElementChild;
}}

function render(entries, {{newOnTop = false}} = {{}}) {{
    const list = $('#journal-timeline');
    if (!list) return;
    const existing = [...list.querySelectorAll('.journal-entry')];
    const known = new Set(existing.map(li => li.querySelector('.journal-entry__time')?.getAttribute('datetime')));
    list.textContent = '';
    for (const e of entries) {{
        const li = rowHTML(e);
        if (newOnTop) li.classList.add('is-new');
        list.appendChild(li);
    }}
    if (newOnTop && $('#journal-autoscroll')?.checked) {{
        $('#journal')?.scrollIntoView({{behavior:'smooth', block:'start'}});
    }}
}}

function fmtStamp() {{
    try {{
        return new Date().toLocaleString(undefined, {{dateStyle:'medium', timeStyle:'short'}});
    }} catch (e) {{ return new Date().toString(); }}
}}

function applyData(data) {{
    const s = data.summary || {{}};
    const el = (sel, v) => {{ const n = document.querySelector(sel); if (n) n.textContent = v; }};
    const nums = document.querySelectorAll('.journal-stat__num');
    if (nums.length >= 4) {{
        nums[0].textContent = s.current_generation ?? '0';
        nums[1].textContent = s.total_entries ?? '0';
        nums[2].textContent = s.graph_nodes ?? '0';
        nums[3].textContent = s.graph_edges ?? '0';
    }}
    render(data.entries || [], {{newOnTop:true}});
    const hint = $('#journal-hint');
    if (hint) hint.textContent = 'Last live sync · ' + fmtStamp();
    const live = $('#journal-live');
    const label = $('#journal-live-label');
    if (live) live.classList.add('is-polling');
    if (label) label.textContent = 'LIVE · updated just now';
}}

async function poll() {{
    const endpoint = SITE_BASE.replace(/\\/$/, '') + '/api/evolution/public';
    try {{
        const res = await fetch(endpoint, {{cache:'no-store'}});
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        if (data && data.summary) applyData(data);
    }} catch (err) {{
        const live = $('#journal-live');
        const label = $('#journal-live-label');
        if (live) live.classList.remove('is-polling');
        if (label) label.textContent = 'SNAPSHOT · live API unreachable';
    }}
}}

(function () {{
    render(INITIAL.entries || []);
    setInterval(poll, 30000);
    setTimeout(poll, 1500);
}})();
</script>
</body>
</html>'''


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
    <meta name="google-site-verification" content="hKduUnYJjstWTZehDR7W7YOEhx0NWKzujAXX_neehMk" />
    <link rel="icon" type="image/png" href="__SITE_BASE__/assets/favicon-32x32.png">
    <title>Abvorn – Reviews Based on Real Testing, Not Spec Sheets</title>
    <meta name="description" content="Independent product reviews and buying guides. We test before we recommend.">
    <link rel="canonical" href="__SITE_URL__/">
    <meta property="og:title" content="Abvorn – Reviews Based on Real Testing, Not Spec Sheets">
    <meta property="og:description" content="Independent product reviews and buying guides. We test before we recommend.">
    <meta property="og:url" content="__SITE_URL__/">
    <meta property="og:type" content="website">
    <meta property="og:image" content="__SITE_URL__/assets/logo.png"><meta name="twitter:image" content="__SITE_URL__/assets/logo.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Abvorn – Reviews Based on Real Testing, Not Spec Sheets">
    <meta name="twitter:description" content="Independent product reviews and buying guides. We test before we recommend.">
    ''' + FONT_LINK + '''
    <style>
        :root { --font-mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }
        ''' + DESIGN_SYSTEM_CSS + '''
        ''' + PROD_SHOT_CSS + '''
        /* FIX: header/hero/footer are fixed brand chrome, always black-on-white —
           they must NOT use the adaptive --clr-black/--clr-white/--clr-off-white
           tokens, which the dark-mode media query above intentionally flips for
           body content. Using those tokens here was the actual bug behind the
           invisible nav (white text on a header that turned white) and the
           invisible hero button (background and text both collapsing toward
           black). Hardcoded values below are deliberate, not an oversight. */
                header { background:#0a0a0a; padding:18px 0; position:sticky; top:0; z-index:100; box-shadow:0 2px 10px rgba(0,0,0,0.25); }
        .navbar { display:flex; justify-content:space-between; align-items:center; }
        .logo img { max-height:44px; width:auto; }
        .nav-links { display:flex; align-items:center; }
        .nav-links > a, .nav-item > a { color:#fff; text-decoration:none; margin-left:28px; font-weight:600; font-size:0.9rem; }
        .nav-links > a:hover, .nav-item > a:hover { color: var(--clr-accent); }
        .nav-item { position:relative; margin-left:28px; }
        .nav-item > a { margin-left:0; display:flex; align-items:center; gap:4px; }
        .nav-item > a::after { content:'▾'; font-size:0.6rem; opacity:0.5; }
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
            .nav-item > a::after { display:none; }
            .nav-dropdown { position:static; box-shadow:none; margin-top:0; padding-left:12px; display:block; background:transparent; }
            .nav-dropdown a { color:#ccc; padding:7px 0; }
            .nav-dropdown a:hover { background:transparent; }
        }
        .trending-ticker { background:var(--clr-accent); color:#1a1200; padding:9px 0; font-size:0.8rem; overflow:hidden; white-space:nowrap; }
        .trending-ticker__track { display:inline-flex; align-items:center; will-change:transform; animation: ticker-scroll 30s linear infinite; }
        .trending-ticker__label { font-family:var(--font-mono); font-weight:700; font-size:0.72rem; letter-spacing:0.1em; text-transform:uppercase; margin-right:14px; color:#1a1200; }
        .trending-ticker__inner { display:inline-flex; align-items:center; flex-shrink:0; }
        .trending-ticker__item { color:#1a1200; text-decoration:none; padding:0 10px; font-weight:600; }
        .trending-ticker__item:hover { color:#000; text-decoration:underline; }
        @keyframes ticker-scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
        .hero { background:#0d0d0d; color:#fff; padding: clamp(32px,4vw,56px) 0; position:relative; overflow:hidden; display:flex; align-items:center; border-bottom:1px solid #222; }
        .hero::before { content:''; position:absolute; inset:0; pointer-events:none; background:
            radial-gradient(900px 460px at 84% 8%, color-mix(in srgb, var(--clr-accent) 16%, transparent), transparent 65%),
            radial-gradient(640px 380px at 4% 100%, color-mix(in srgb, var(--clr-accent) 9%, transparent), transparent 60%); }
        .hero-grid { display:grid; grid-template-columns: 1.05fr 0.95fr; gap: clamp(24px,4vw,56px); align-items:center; position:relative; width:100%; }
        .hero-eyebrow { display:inline-flex; align-items:center; gap:10px; margin:0 0 18px; font-family:var(--font-mono); font-size:0.72rem; font-weight:600; letter-spacing:0.14em; text-transform:uppercase; color:var(--clr-accent); }
        .hero-dot { width:8px; height:8px; border-radius:2px; background:var(--clr-accent); box-shadow:0 0 14px var(--clr-accent); flex-shrink:0; }
        .hero h1 { font-family:var(--font-display); font-weight:800; font-size:clamp(var(--text-3xl),4vw,var(--text-4xl)); line-height:1.08; letter-spacing:-0.02em; color:#fff; margin:0 0 14px; }
        .hero-tagline { font-size:clamp(0.95rem,1.3vw,1.08rem); color:#b9b9b4; max-width:50ch; margin:0 0 22px; line-height:1.6; }
        .hero-trust { display:flex; flex-wrap:wrap; gap:8px 24px; }
        .hero-trust span { display:inline-flex; align-items:center; gap:7px; font-size:0.78rem; font-weight:600; color:#b9b9b4; }
        .hero-trust svg { width:15px; height:15px; color:var(--clr-accent); flex:none; }
        .hero-cta { display:flex; align-items:center; justify-content:center; gap:16px; flex-wrap:wrap; margin: 0 0 26px; }
        .hero-cta .btn { background:var(--clr-accent); color:#0a0a0a; border-radius:12px; font-family:var(--font-display); font-weight:800; font-size:1rem; text-transform:none; letter-spacing:0; padding:0.95em 1.6em; box-shadow:0 10px 34px color-mix(in srgb, var(--clr-accent) 45%, transparent); }
        .hero-cta .btn:hover { background:#e0a23f; transform:translateY(-2px); box-shadow:0 14px 44px color-mix(in srgb, var(--clr-accent) 60%, transparent); }
        .hero-slider { position:relative; border-radius:20px; overflow:hidden; box-shadow:0 24px 70px rgba(0,0,0,0.5); aspect-ratio: 4/3; max-height:360px; background:#fff; border:1px solid rgba(255,255,255,0.08); }
        .hero-slide { position:absolute; inset:0; opacity:0; transition:opacity 0.9s var(--ease-out); }
        .hero-slide.active { opacity:1; }
        .hero-slide img { width:100%; height:100%; object-fit:contain; display:block; padding: 8% 4%; box-sizing:border-box; }
        .hero-slide figcaption { position:absolute; left:0; right:0; bottom:0; background:linear-gradient(transparent, rgba(0,0,0,0.85)); color:#fff; padding: 52px var(--space-lg) var(--space-md); font-weight:600; font-size:0.95rem; }
        .hero-slide__scrim { position:absolute; inset:0; background:linear-gradient(to top, rgba(10,10,10,0.95) 0%, rgba(10,10,10,0.82) 38%, rgba(10,10,10,0.42) 62%, rgba(10,10,10,0.14) 74%, rgba(10,10,10,0) 80%); pointer-events:none; }
        .hero-slide .hero-verdict { position:absolute; left:10px; right:10px; bottom:10px; background:rgba(13,13,13,0.55); color:#fff; border:1px solid rgba(255,255,255,0.12); border-radius:10px; padding:8px 12px 10px; box-shadow:0 6px 20px rgba(0,0,0,0.35); }
        .hero-verdict__head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:6px; }
        .hero-verdict__eyebrow { display:block; font-family:var(--font-mono); font-size:0.5rem; font-weight:600; text-transform:uppercase; letter-spacing:0.14em; color:var(--clr-accent); margin-bottom:2px; }
        .hero-verdict__product { display:block; font-family:var(--font-display); font-size:0.76rem; font-weight:700; letter-spacing:-0.01em; line-height:1.2; color:#fff; }
        .hero-verdict__overall { text-align:right; flex:none; }
        .hero-verdict__num { font-family:var(--font-mono); font-size:1.4rem; font-weight:700; letter-spacing:-0.02em; line-height:1; display:block; color:var(--clr-accent); }
        .hero-verdict__num small { font-size:0.6rem; font-weight:600; color:#b9b9b4; letter-spacing:0; margin-left:2px; }
        .hero-verdict__label { font-size:0.5rem; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:#0a0a0a; background:var(--clr-accent); padding:2px 6px; border-radius:100px; display:inline-block; margin-top:3px; }
        .hero-verdict__bars { display:flex; flex-direction:column; gap:3px; border-top:1px solid rgba(255,255,255,0.1); padding-top:6px; }
        .hero-verdict__bar { display:grid; grid-template-columns:1fr 3fr 30px; align-items:center; gap:8px; font-size:0.56rem; }
        .hero-verdict__bar-label { font-weight:600; color:#c4c4bf; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-family:var(--font-mono); font-size:0.52rem; }
        .hero-verdict__bar-track { height:6px; background:rgba(255,255,255,0.12); border-radius:3px; overflow:hidden; }
        .hero-verdict__bar-fill { display:block; height:100%; background:#fff; border-radius:3px; transform:scaleX(0); transform-origin:left; transition: transform 0.75s var(--ease-out) 0.15s; }
        .hero-slide.active .hero-verdict__bar-fill { transform: scaleX(var(--score)); }
        .hero-verdict__bar.is-top .hero-verdict__bar-fill { background: var(--clr-accent); }
        .hero-verdict__bar.is-top .hero-verdict__bar-label { color:#fff; font-weight:700; }
        .hero-verdict__bar.is-weak .hero-verdict__bar-label { color:#6b6b68; }
        .hero-verdict__bar.is-weak .hero-verdict__bar-fill { background:#555; }
        .hero-verdict__bar-score { text-align:right; font-weight:700; font-variant-numeric: tabular-nums; color:#fff; font-family:var(--font-mono); font-size:0.68rem; }
        .hero-slider__dots { position:absolute; top:14px; right:14px; display:flex; gap:2px; z-index:6; }
        .hero-slider__dot { width:44px; height:44px; border:none; background:transparent; cursor:pointer; padding:0; display:flex; align-items:center; justify-content:center; }
        .hero-slider__dot::before { content:''; width:8px; height:8px; border-radius:2px; background:rgba(255,255,255,0.35); transition: background var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out); }
        .hero-slider__dot.active::before { background: var(--clr-accent); box-shadow:0 0 10px var(--clr-accent); }
        .hero-slider__dot:focus-visible { outline:2px solid var(--clr-accent); outline-offset:2px; border-radius:100px; }
        @media (max-width: 860px) { .hero-grid { grid-template-columns: minmax(0,1fr); } .hero-slider { order:-1; width:100%; margin:0 auto var(--space-lg); } .hero-trust { white-space:normal; } }

        .how-we-test { background:#0d0d0d; color:#fff; padding: var(--space-2xl) 0; border-top:1px solid #222; }
        .how-we-test__inner { max-width:1200px; margin:0 auto; padding:0 var(--space-lg); }
        .how-we-test__intro { margin-bottom: var(--space-xl); }
        .how-we-test__intro h2 { color:#fff; font-size: var(--text-3xl); margin-bottom:8px; letter-spacing:-0.02em; }
        .how-we-test__intro p { color:#b9b9b4; max-width:52ch; margin:0; }
        .how-we-test .section-eyebrow { color: var(--clr-accent); }
        .hwt-steps { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px,1fr)); gap: var(--space-lg); }
        .hwt-step { border:1px solid rgba(255,255,255,0.12); border-radius:14px; background:rgba(255,255,255,0.03); padding: var(--space-lg); }
        .hwt-step__num { font-family: var(--font-mono); font-size: var(--text-xl); font-weight:700; color: var(--clr-accent); letter-spacing:-0.02em; display:inline-flex; align-items:center; gap:10px; }
        .hwt-step__num::after { content:''; width:26px; height:2px; background:var(--clr-accent); opacity:0.6; }
        .hwt-step h3 { color:#fff; font-size: var(--text-lg); margin:10px 0 6px; }
        .hwt-step p { color:#b9b9b4; font-size:0.9rem; margin:0; line-height:1.55; }

        .stats-band { background:var(--clr-accent); color:var(--clr-black); padding: var(--space-lg) 0; }
        .stats-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(160px,1fr)); gap: var(--space-lg); text-align:center; }
        .stat-icon { width:28px; height:28px; margin:0 auto 10px; color: var(--clr-black); opacity:0.9; }
        .stat-icon svg { width:100%; height:100%; }
        .stat-number { font-family: var(--font-display); font-size: var(--text-3xl); font-weight:700; color: var(--clr-black); }
        .stat-label { font-family: var(--font-mono); font-size:0.7rem; color:rgba(10,10,10,0.8); text-transform:uppercase; letter-spacing:0.1em; margin-top:4px; }

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

        .guides-section { padding: var(--space-2xl) 0 var(--space-xl); }
        .latest-reviews-section { padding: var(--space-2xl) 0; }
        .section-eyebrow { display:block; font-size:0.7rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; color: var(--clr-accent-text); margin-bottom:6px; }
        .category-section { margin-bottom: var(--space-2xl); }
        .category-section:last-child { margin-bottom: 0; }
        .category-section__header { display:flex; justify-content:space-between; align-items:flex-end; gap: var(--space-md); margin-bottom: var(--space-lg); border-bottom:2px solid var(--clr-black); padding-bottom: var(--space-sm); flex-wrap:wrap; }
        .category-section__header h2 { font-size: var(--text-2xl); margin:0; display:flex; align-items:center; gap:12px; flex:1 1 auto; min-width:0; }
        .category-section__header h2 .cat-tick { width:10px; height:10px; border-radius:2px; background:var(--cat, var(--clr-accent)); box-shadow:0 0 0 4px color-mix(in srgb, var(--cat, var(--clr-accent)) 14%, transparent); flex-shrink:0; }
        .category-section__header a { font-size:0.85rem; font-weight:700; color: var(--clr-black); text-decoration:none; white-space:nowrap; display:inline-flex; align-items:center; flex-shrink:0; }
        .category-section__header a:hover { text-decoration:underline; }
        .niche-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px,1fr)); gap: var(--space-lg); }
        .niche-card { border:1px solid var(--clr-light-gray); border-radius:var(--radius-lg); overflow:hidden; transition: transform var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out); background:var(--clr-white); display:flex; flex-direction:column; }
        .niche-card:hover { transform:translateY(-6px); box-shadow:var(--shadow-lg); }
        .niche-card__image-wrapper { aspect-ratio: 4/3; overflow:hidden; background:var(--clr-white); padding:20px; }
        .niche-card img { width:100%; height:100%; object-fit:contain; transition: transform var(--duration-slow) var(--ease-out); }
        .niche-card:hover img { transform: scale(1.04); }
        .review-card__media { position:relative; }
        .review-card__banner { display:inline-block; padding:4px 12px; border-radius:6px; color:#1a1200; font-size:0.64rem; font-weight:800; text-transform:uppercase; letter-spacing:0.07em; margin-bottom:6px; }
        .review-card__score { position:absolute; right:14px; bottom:14px; z-index:2; display:inline-flex; align-items:baseline; gap:3px; background:rgba(10,10,10,0.92); color:#fff; border-radius:100px; padding:6px 14px; border:1px solid rgba(201,138,44,0.6); backdrop-filter: blur(4px); }
        .review-card__score-num { font-family: var(--font-display); font-size:1.15rem; font-weight:800; color: var(--clr-accent); letter-spacing:-0.02em; line-height:1; }
        .review-card__score-out { font-size:0.7rem; color:#aaa; font-weight:600; }
        .review-card__body { display:flex; flex-direction:column; flex:1; padding: var(--space-md); }
        .review-card__body h2 { font-size: var(--text-lg); margin:0 0 8px; line-height:1.25; }
        .review-card__body h2 a { color:inherit; text-decoration:none; }
        .review-card__body h2 a:hover { color: var(--cat, var(--clr-accent-text)); color: color-mix(in srgb, var(--cat, var(--clr-accent-text)) 55%, #1a1200); }
        .review-card__snippet { font-size:0.9rem; color:var(--clr-mid-gray); line-height:1.5; margin:0 0 var(--space-sm); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
        .review-card__footer { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:auto; padding-top: var(--space-sm); }
        .review-card__footer .read-link { font-weight:700; font-size:0.82rem; color:var(--clr-black); text-decoration:none; border-bottom:2px solid var(--cat, var(--clr-accent)); border-bottom-color: color-mix(in srgb, var(--cat, var(--clr-accent)) 55%, #1a1200); padding-bottom:1px; }
        .review-card__footer .read-link:hover { color: var(--cat, var(--clr-accent-text)); color: color-mix(in srgb, var(--cat, var(--clr-accent-text)) 55%, #1a1200); }
        .review-card__reactions { display:flex; gap:6px; }
        .review-card__reactions .reaction-btn { display:inline-flex; align-items:center; gap:5px; padding:5px 12px; border:1px solid var(--clr-light-gray); border-radius:999px; background:#fff; color:var(--clr-mid-gray); font-size:0.78rem; font-weight:600; font-family:var(--font-body); }
        .review-card__reactions .reaction-btn.is-counter { cursor:default; }
        .review-card__reactions .reaction-icon { font-size:0.9rem; line-height:1; }
        .review-card__reactions .reaction-count { font-weight:700; min-width:14px; text-align:center; }
        .review-card__updated { display:block; font-size:0.72rem; color:#999; margin-bottom: var(--space-xs); }
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
<a class="skip-link" href="#main">Skip to content</a>
<header><div class="container navbar">
    <a href="__SITE_BASE__/" class="logo"><img src="__SITE_BASE__/logo.svg" alt="Abvorn"></a>
    <button class="nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav-links">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <nav class="nav-links" id="nav-links">
        <div class="nav-item"><a href="#niches">Categories</a><div class="nav-dropdown nav-dropdown--mega">CATEGORY_DROPDOWN_PLACEHOLDER</div></div>
        <a href="__SITE_BASE__/">Home</a>
        <a href="__SITE_BASE__/about.html">About</a>
        <a href="__SITE_BASE__/journal/">Journal</a>
    </nav>
</div></header>
<div class="trending-ticker"><div class="container"><div class="trending-ticker__track"><div class="trending-ticker__inner"><span class="trending-ticker__label">Latest updates:</span><span id="trending-items">LATEST_UPDATES_PLACEHOLDER</span></div><div class="trending-ticker__inner" aria-hidden="true"><span class="trending-ticker__label">Latest updates:</span><span>LATEST_UPDATES_PLACEHOLDER</span></div></div></div></div>

<main id="main"><section class="hero"><div class="container hero-grid">
    <div>
        <span class="hero-eyebrow"><span class="hero-dot" aria-hidden="true"></span>Reviews scored on 5 criteria</span>
        <h1>Clear, honest guidance on what's actually worth your money.</h1>
        <p class="hero-tagline">We compare real prices, specifications, and verified customer feedback, then break down the trade-offs in plain language &mdash; so you can go from confused to confident in minutes.</p>
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
            <p>Independent product reviews and buying guides, based on real testing.</p>
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
</main>

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
            method: 'POST', headers: {'Content-Type': 'text/plain;charset=utf-8'},
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



