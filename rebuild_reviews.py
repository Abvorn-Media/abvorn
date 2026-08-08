"""Rebuild all review pages through the fixed build pipeline.

Reconstructs the articles dict from the existing rendered pages (docs/reviews/*/index.html),
merges product details from products_cache.json, and calls run_cycle.build_article_page
for each canonical page so the P0/P1 design fixes ship consistently across all 10 niches.
"""
import re
import sys
import json
import html as html_lib
from pathlib import Path
from urllib.parse import unquote

import run_cycle
from src.deployment import _title_slug


def _fully_unescape(text):
    """Unescape until stable so pre-encoded &amp;amp; sequences collapse to &."""
    if not text:
        return text
    prev = None
    while prev != text:
        prev = text
        text = html_lib.unescape(text)
    return text

NICHES = [
    "4k-monitors",
    "fitness-trackers",
    "gaming-mice",
    "laptops",
    "mechanical-keyboards",
    "smart-home",
    "streaming-devices",
    "webcams",
    "wireless-earbuds",
    "wireless-headphones",
]

DOCS = Path("docs")


def extract_article(path):
    """Reverse-engineer the articles dict entry from a rendered article page."""
    c = Path(path).read_text(encoding="utf-8")

    m = re.search(r"<title>([^<]*?)\s*\|\s*Abvorn</title>", c)
    post_title = _fully_unescape(m.group(1).strip()) if m else ""

    m = re.search(r'<meta name="description" content="([^"]*)"', c)
    meta_desc = _fully_unescape(m.group(1)) if m else ""

    m = re.search(r'data-review="([^"]+)"', c)
    niche_slug = m.group(1) if m else ""

    m = re.search(r'<h3 class="av-product">(.*?)</h3>', c)
    product_name = _fully_unescape(m.group(1)) if m else ""

    body = re.search(r'<article class="article-body" id="main">(.*?)</article>', c, re.S)
    if not body:
        return None
    body = body.group(1)

    d_open = body.find('<div class="disclosure">')
    v_open = body.find('<div class="abvorn-verdict">')
    r_open = body.find('<div class="reactions-bar"')
    if r_open < 0:
        r_open = len(body)

    # Balance the verdict div to find where the prose region begins.
    verdict_close = None
    if v_open >= 0:
        depth = 0
        for mt in re.finditer(r"<div\b|</div>", body[v_open:]):
            if mt.group(0) == "<div":
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    verdict_close = v_open + mt.end()
                    break

    intro = ""
    article_html = ""

    # Legacy template: intro prose lives inside the article region under an
    # <h2>Introduction</h2> heading; the pre-verdict slot only holds the CTA
    # banner + decision matrix, so we take the hook paragraphs from the prose.
    intro_h2 = body.find("<h2>Introduction</h2>", v_open, r_open) if v_open >= 0 else -1
    if intro_h2 > 0:
        next_h2 = body.find("<h2>", intro_h2 + len("<h2>Introduction</h2>"), r_open)
        if next_h2 < 0:
            next_h2 = r_open
        intro = body[intro_h2:next_h2].strip()
        article_html = body[next_h2:r_open].strip()
    elif verdict_close is not None:
        if d_open >= 0 and v_open > d_open:
            d_close = body.find("</div>", d_open) + len("</div>")
            intro = body[d_close:v_open].strip()
            intro = re.sub(r"^(?:</div>\s*)+", "", intro)
        # Handle both old (verdict → prose → matrix) and new (verdict → matrix
        # → prose) orders: prose is the block between the verdict and the chart
        # that sits on the opposite side of the decision-matrix-wrap.
        prose_start = verdict_close
        prose_end = None
        mwrap = body.find('<div class="decision-matrix-wrap">', verdict_close)
        if mwrap >= 0:
            gap = body[verdict_close:mwrap]
            if re.search(r"<(?:p|h[1-6]|ul|ol|figure|table)\b", gap):
                prose_end = mwrap
            else:
                depth = 0
                for mt in re.finditer(r"<div\b|</div>", body[mwrap:]):
                    if mt.group(0) == "<div":
                        depth += 1
                    else:
                        depth -= 1
                        if depth == 0:
                            prose_start = mwrap + mt.end()
                            break
        ends = []
        for marker in ['<div class="chart-section">', '<div class="cta-banner">',
                       '<section class="faq-section"', '<div class="reactions-bar"']:
            j = body.find(marker, prose_start)
            if j >= 0:
                ends.append(j)
        stop = min(ends) if ends else r_open
        if prose_end is not None:
            stop = prose_end
        article_html = body[prose_start:stop].strip()
        # Drop stray non-structural fragments (e.g. leftover "User Safety: safe"
        # text) â€” real prose always contains block-level elements.
        if article_html and not re.search(r"<(?:p|h[1-6]|ul|ol|figure|table|div|section)\b", article_html):
            article_html = ""

    products = []
    card_re = re.compile(r'<div class="product-card">(.*?)(?=<div class="product-card">|$)', re.S)
    for card in card_re.finditer(body):
        seg = card.group(1)
        nm = re.search(r"<h3>(.*?)</h3>", seg, re.S)
        price = re.search(r'<div class="price">(.*?)</div>', seg, re.S)
        img = re.search(r'<img src="([^"]+)"', seg)
        desc = re.search(r"<p>(.*?)</p>", seg, re.S)
        url = ""
        comp = re.search(r'href="/abvorn/compare\?[^"]*url=([^&"]+)', seg)
        if comp:
            url = unquote(comp.group(1))
        else:
            clk = re.search(r'href="(https://abvorn\.com/click/[^"]+)"', seg)
            url = clk.group(1) if clk else ""
        asin = ""
        if url:
            m_asin = re.search(r"/dp/([A-Z0-9]{10})", url)
            if m_asin:
                asin = m_asin.group(1)
        products.append({
            "name": _fully_unescape(nm.group(1)).strip() if nm else "",
            "price": _fully_unescape(price.group(1)).strip() if price else "",
            "image": img.group(1) if img else "",
            "description": _fully_unescape(desc.group(1)).strip() if desc else "",
            "url": url,
            "asin": asin,
        })

    m = re.search(r"Published:\s*([0-9-]+)", c)
    published_date = m.group(1) if m else ""
    m = re.search(r"Updated:\s*([0-9-]+)", c)
    updated_date = m.group(1) if m else ""

    related_niches = []
    fr = re.search(r'class="further-reading".*?<ul>(.*?)</ul>', c, re.S)
    if fr:
        for m in re.finditer(r'href="/abvorn/reviews/([^"/]+)/"', fr.group(1)):
            rel_slug = m.group(1)
            if rel_slug != niche_slug:
                related_niches.append(rel_slug)

    return {
        "post_title": post_title,
        "meta_description": meta_desc,
        "intro": intro,
        "article_html": article_html,
        "product_name": product_name,
        "niche_slug": niche_slug,
        "products": products,
        "published_date": published_date,
        "updated_date": updated_date,
        "related_niches": related_niches,
    }


def enrich_from_cache(products, cache_products):
    """Merge richer fields (asin, features, original_price, rating) from the cache by URL."""
    by_url = {p.get("url", ""): p for p in cache_products if p.get("url")}
    enriched = []
    for p in products:
        p = dict(p)
        cache = by_url.get(p.get("url", ""))
        if not cache:
            for cp in cache_products:
                if cp.get("name") and cp["name"].strip().lower() == p.get("name", "").strip().lower():
                    cache = cp
                    break
        if cache:
            for key in ("asin", "features", "original_price", "rating", "ratings_count", "is_best_seller", "is_amazon_choice"):
                if key in cache and not p.get(key):
                    p[key] = cache[key]
        enriched.append(p)
    return enriched


def main():
    state = run_cycle.load_state()
    cache = {}
    cache_path = Path("products_cache.json")
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    all_slugs = sorted([n["slug"] for n in state["niches"]], key=lambda s: _title_slug(s).lower())
    _sorted_niches = sorted(state["niches"], key=lambda n: n["name"].lower())

    for slug in NICHES:
        page = DOCS / "reviews" / slug / "index.html"
        if not page.exists():
            print(f"  SKIP (missing): {page}")
            continue
        a = extract_article(page)
        if not a:
            print(f"  SKIP (no article body): {slug}")
            continue
        a["products"] = enrich_from_cache(a["products"], cache.get(slug, []))
        niche_name = next((n["name"] for n in state["niches"] if n["slug"] == slug), slug.replace("-", " ").title())
        by_slug = {n["slug"]: n for n in state["niches"]}
        rel_slugs = a.get("related_niches") or [n["slug"] for n in _sorted_niches if n["slug"] != slug][:4]
        related = [by_slug[s] for s in rel_slugs if s in by_slug]
        html_out = run_cycle.build_article_page(
            slug,
            niche_name,
            a["post_title"],
            a["article_html"],
            a["intro"],
            a["product_name"],
            a["meta_description"],
            all_slugs,
            a.get("products"),
            pexels_key="",
            amazon_tag="",
            form_url="",
            hero_img="",
            google_client_id="",
            related_niches=related,
            published_date=a.get("published_date"),
            updated_date=a.get("updated_date"),
            article_id=f"{slug}-0",
        )
        page.write_text(html_out, encoding="utf-8")
        title = a["post_title"][:60]
        print(f"  Rebuilt: reviews/{slug}/index.html  ({title})")

    print("Done.")


if __name__ == "__main__":
    main()

