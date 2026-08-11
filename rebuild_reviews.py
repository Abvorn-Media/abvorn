"""Rebuild all review pages through the warm-editorial build pipeline.

Reads every rendered review page under docs/reviews/*/ (dated articles and
index.html), reverse-engineers the articles dict for each, merges product
details from products_cache.json, and calls run_cycle.build_article_page so the
warm design ships consistently across every page.

Extraction is format-agnostic: it accepts legacy pages (``<div>`` verdict,
``.product-card`` grid, ``Published: YYYY-MM-DD``), warm builder output
(``<section>`` verdict, ``.warm-product-card`` grid, ``Published Mon DD,
YYYY``), and the hand-written pilot (``.product-review`` prose blocks).
"""
import re
import sys
import json
import html as html_lib
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, parse_qs, urlparse

import run_cycle
from src.deployment import _title_slug

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def _fully_unescape(text):
    """Unescape until stable so pre-encoded &amp;amp; sequences collapse to &."""
    if not text:
        return text
    prev = None
    while prev != text:
        prev = text
        text = html_lib.unescape(text)
    return text


def _parse_published(text):
    """Return an ISO date string from either page format."""
    if not text:
        return ""
    m = re.search(r"([0-9]{4})-([0-9]{2})-([0-9]{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+([0-9]{1,2}),\s*([0-9]{4})", text)
    if m:
        mon = MONTHS.get(m.group(1), 1)
        return f"{m.group(3)}-{mon:02d}-{int(m.group(2)):02d}"
    return ""


def _balanced_close(body, open_pos, tag):
    """Return the position just after the matching </tag> for open_pos."""
    depth = 0
    pat = re.compile(r"<%s\b|</%s>" % (tag, tag), re.I)
    for mt in pat.finditer(body, open_pos):
        if mt.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return mt.end()
        else:
            depth += 1
    return None


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

    # Locate the verdict element (legacy <div>, warm/pilot <section>).
    verdict_open = verdict_close = None
    vm = re.search(r'<(\w+)[^>]*class="abvorn-verdict"', body)
    if vm:
        tag = vm.group(1)
        verdict_open = vm.start()
        verdict_close = _balanced_close(body, verdict_open, tag)

    d_open = body.find('<div class="disclosure">')

    intro = ""
    article_html = ""

    # Legacy template: an explicit <h2>Introduction</h2> heads the prose region.
    intro_h2 = body.find("<h2>Introduction</h2>")
    if intro_h2 >= 0:
        next_h2 = body.find("<h2>", intro_h2 + len("<h2>Introduction</h2>"))
        intro_end = next_h2 if next_h2 > 0 else first_structural(intro_h2)
        intro = body[intro_h2:intro_end].strip()
        article_html = _clip_prose(body, intro_end)
    else:
        # Warm/pilot: hook paragraphs live between the disclosure and the verdict.
        if verdict_open is not None:
            if d_open >= 0 and verdict_open > d_open:
                d_close = body.find("</div>", d_open) + len("</div>")
                intro = body[d_close:verdict_open].strip()
                intro = re.sub(r"^(?:</div>\s*)+", "", intro)
            article_html = _clip_prose(body, verdict_close if verdict_close is not None else 0)

    # Products: warm grid, legacy grid, or the pilot's prose review blocks.
    products = []
    if "warm-product-card" in body:
        products = _extract_warm_cards(body)
    elif 'class="product-card"' in body:
        products = _extract_legacy_cards(body)
    elif 'class="product-review"' in body:
        products = _extract_review_blocks(body)

    published_date = _parse_published(c)
    m = re.search(r"Updated[^0-9]{0,12}([0-9]{4}-[0-9]{2}-[0-9]{2})", c)
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


def _clip_prose(body, start):
    """Return body[start:end] where end is the first structural marker."""
    if start is None or start < 0:
        return ""
    hits = [body.find(mk, start) for mk in [
        'decision-matrix-wrap',
        'class="table-wrap decision-matrix"',
        'class="chart-section"',
        'class="product-section"',
        'class="warm-product-section"',
        'class="product-review"',
        'class="cta-banner"',
        'class="faq-section"',
        'class="reactions-bar"',
        'class="related-cats"',
        'class="further-reading"',
    ]]
    hits = [h for h in hits if h >= 0]
    end = min(hits) if hits else len(body)
    seg = body[start:end].strip()
    # Drop stray non-structural fragments (e.g. leftover "User Safety: safe"
    # text) — real prose always contains block-level elements.
    if seg and not re.search(r"<(?:p|h[1-6]|ul|ol|figure|table|div|section)\b", seg):
        seg = ""
    return seg


def _extract_warm_cards(body):
    products = []
    card_re = re.compile(r'<div class="warm-product-card">(.*?)(?=<div class="warm-product-card">|</div>\s*</div>\s*<h2|$)', re.S)
    for card in card_re.finditer(body):
        seg = card.group(1)
        nm = re.search(r'<h3 class="warm-product-card__name">(.*?)</h3>', seg, re.S)
        price = re.search(r'class="warm-product-card__price">(.*?)</div>', seg, re.S)
        img = re.search(r'<img src="([^"]+)"', seg)
        desc = re.search(r'class="warm-product-card__summary">(.*?)</p>', seg, re.S)
        url, asin = "", ""
        clk = re.search(r'href="([^"]+)"[^>]*data-track="value"', seg)
        if not clk:
            clk = re.search(r'href="([^"]+)"', seg)
        if clk:
            url = unquote(clk.group(1))
        comp = re.search(r'compare\.html\?[^"]*', seg)
        if comp:
            qs = parse_qs(urlparse("http://x/" + comp.group(0)).query)
            if qs.get("asin"):
                asin = qs["asin"][0]
            if qs.get("url"):
                url = qs["url"][0]
        if not asin:
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
    return products


def _extract_legacy_cards(body):
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
    return products


def _extract_review_blocks(body):
    products = []
    block_re = re.compile(r'<section class="product-review"[^>]*>(.*?)</section>', re.S)
    for card in block_re.finditer(body):
        seg = card.group(1)
        nm = re.search(r'<h3>(.*?)</h3>', seg, re.S)
        price = re.search(r'class="price">(.*?)</span>', seg, re.S)
        img = re.search(r'<img src="([^"]+)"', seg)
        desc = re.search(r'class="product-review__desc">(.*?)</p>', seg, re.S)
        url, asin = "", ""
        clk = re.search(r'href="(https://www\.amazon\.com/[^"]+)"', seg)
        if clk:
            url = clk.group(1)
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
    return products


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
    by_slug = {n["slug"]: n for n in state["niches"]}

    pages = sorted(p for p in (DOCS / "reviews").glob("*/*.html"))
    built = 0
    for i, page in enumerate(pages):
        slug = page.parent.name
        if slug not in by_slug:
            print(f"  SKIP (unknown niche): {page}")
            continue
        a = extract_article(page)
        if not a:
            print(f"  SKIP (no article body): {page}")
            continue
        a["products"] = enrich_from_cache(a["products"], cache.get(slug, []))
        niche_name = by_slug[slug]["name"]
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
            article_id=f"{slug}-{i}",
        )
        page.write_text(html_out, encoding="utf-8")
        built += 1
        print(f"  Rebuilt: {page}  ({a['post_title'][:50]})".encode("ascii", "replace").decode("ascii"))

    print(f"Done. Rebuilt {built} review pages.")


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


if __name__ == "__main__":
    main()
