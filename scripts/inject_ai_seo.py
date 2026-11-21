#!/usr/bin/env python3
"""Post-build AI-SEO injector for docs/*.html.

Adds machine-readable structured data and freshness to already-built pages
*without* regenerating content, so the rich hand-tuned hubs are never rebuilt
by an ad-hoc tool (see AGENTS.md). Idempotent: re-running changes nothing.

Injected
--------
* Article JSON-LD on og:type=article pages: headline, description,
  datePublished/dateModified (from the visible Published/Updated dates),
  author + publisher (Organization "Abvorn"), image, mainEntityOfPage,
  articleSection, isAccessibleForFree.
* WebPage JSON-LD on the remaining pages (they shipped with zero JSON-LD).
* ItemList JSON-LD from real abvorn-rps-data products (no invented ratings) or
  from a hub's review/category links; Article/WebPage/ItemList are never
  injected twice when valid schema already exists.
* Concatenated JSON-LD objects are wrapped into one @graph; an injected
  Article duplicate is dropped once the graph contains a valid Article.
* Organization + WebSite JSON-LD on the homepage.
* <time datetime="..."> around the visible Published/Updated dates.
* <main> landmark on pages whose id="main" element is an <article>.
* Comparison pages: canonical / og:url / breadcrumb point at the real
  /comparisons/<slug>.html instead of the non-existent /comparisons/<slug>/.

Usage
-----
    python scripts/inject_ai_seo.py [--dry-run] [--check] [--root docs]

--check exits 1 if any page would change (for CI); --dry-run prints the files
that would change without writing.
"""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import re
import sys
from datetime import datetime
from html import unescape

logger = logging.getLogger(__name__)

SITE = "https://abvorn.com"
LOGO = f"{SITE}/assets/logo.png"
ORG = {
    "@type": "Organization",
    "name": "Abvorn",
    "url": f"{SITE}/",
    "logo": {"@type": "ImageObject", "url": LOGO},
}
SKIP = {"console.html", "google73aec0d1f1cc59ad.html"}

_DATE = r"([A-Z][a-z]{2} \d{1,2}, \d{4})"

_LD_SCRIPT_RE = re.compile(
    r'(<script\b[^>]*\btype="application/ld\+json"[^>]*>)(.*?)(</script>)',
    re.I | re.S,
)
_MARKED_LD_RE = re.compile(
    r'<!--\s*ai-seo:(?P<marker>[\w-]+)\s*-->[ \t]*(?:\r?\n)?'
    r'<script type="application/ld\+json">(?P<payload>.*?)</script>(?:\r?\n)?',
    re.S,
)
_RPS_DATA_RE = re.compile(
    r'<script id="abvorn-rps-data" type="application/json">(.*?)</script>', re.S
)
_HREF_RE = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
_CATEGORY_PATH_RE = re.compile(r"^/(?:reviews|categories)/[^\s\"'<>?]+/?$")
_REVIEW_CARD_PATH_RE = re.compile(r"^/reviews/[^/]+/.+")
# A few hubs list hundreds of archive links; exposing all of them would add a
# ~200 KB JSON-LD block. Keep the Listing useful but bounded.
_MAX_HUB_ITEMS = 50


def rel_url(rel: str) -> str:
    if rel == "index.html":
        return f"{SITE}/"
    if rel.endswith("/index.html"):
        return f"{SITE}/{rel[: -len('index.html')]}"
    return f"{SITE}/{rel}"


def iso_date(text: str) -> str:
    return datetime.strptime(text, "%b %d, %Y").date().isoformat()


def meta(html: str, key: str) -> str:
    for attr in ("property", "name"):
        m = re.search(
            rf'<meta[^>]*{attr}="{re.escape(key)}"[^>]*content="([^"]*)"', html
        )
        if m:
            return unescape(m.group(1))
    return ""


def h1_text(html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()


def ld_block(obj: dict, marker: str, nl: str = "\n") -> str:
    payload = json.dumps(obj, ensure_ascii=True, separators=(",", ":"))
    return (
        f'<!-- ai-seo:{marker} -->{nl}'
        f'<script type="application/ld+json">{payload}</script>{nl}'
    )


def _parse_ld_fragments(text: str) -> list[dict] | None:
    """Split concatenated JSON objects; ``None`` if any fragment is invalid."""
    decoder = json.JSONDecoder()
    objects: list[dict] = []
    pos = 0
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            break
        try:
            obj, end = decoder.raw_decode(text, pos)
        except ValueError:
            return None
        if not isinstance(obj, dict):
            return None
        objects.append(obj)
        pos = end
    return objects or None


def _walk_types(obj, types: set[str]) -> None:
    if not isinstance(obj, dict):
        return
    graph = obj.get("@graph")
    if isinstance(graph, list):
        for node in graph:
            _walk_types(node, types)
    node_type = obj.get("@type")
    if isinstance(node_type, str):
        types.add(node_type)
    elif isinstance(node_type, list):
        types.update(t for t in node_type if isinstance(t, str))


def _existing_ld_types(html: str) -> set[str]:
    types: set[str] = set()
    for match in _LD_SCRIPT_RE.finditer(html):
        fragments = _parse_ld_fragments(match.group(2))
        if not fragments:
            continue  # invalid JSON-LD is never used to justify an injection
        for fragment in fragments:
            _walk_types(fragment, types)
    return types


def _normalize_ld_scripts(html: str) -> str:
    """Wrap multiple concatenated JSON objects in one ``@graph`` per script."""

    def repl(match: re.Match) -> str:
        content = match.group(2)
        fragments = _parse_ld_fragments(content)
        if fragments is None:
            if content.strip():
                logger.warning("Leaving unparseable JSON-LD script untouched")
            return match.group(0)
        if len(fragments) == 1:
            return match.group(0)
        nl = "\r\n" if "\r\n" in content else "\n"
        graph = {"@context": "https://schema.org", "@graph": fragments}
        payload = json.dumps(graph, ensure_ascii=True, separators=(",", ":"))
        return f"{match.group(1)}{nl}{payload}{nl}{match.group(3)}"

    return _LD_SCRIPT_RE.sub(repl, html)


def _is_injected_article(match: re.Match) -> bool:
    if match.group("marker") != "schema":
        return False
    try:
        own_types: set[str] = set()
        _walk_types(json.loads(match.group("payload")), own_types)
    except ValueError:
        return False
    return "Article" in own_types


def _drop_duplicate_injected_article(html: str) -> str:
    """Remove our own Article block once a real Article exists on the page.

    The seven affected blog pages carry both a valid Article (formerly one of
    three concatenated objects) and an injected duplicate. Only a marked
    schema block that is itself an Article is removed, and only when the page
    has a valid Article outside *all* such markers. Injected Articles must not
    validate each other: a page whose only Articles are markers keeps them so
    the injector stays idempotent.
    """

    def strip(match: re.Match) -> str:
        return "" if _is_injected_article(match) else match.group(0)

    real_types = _existing_ld_types(_MARKED_LD_RE.sub(strip, html))
    if "Article" not in real_types:
        return html
    return _MARKED_LD_RE.sub(strip, html)


def _plain_text(fragment: str) -> str:
    """Visible text of an HTML fragment, with tag boundaries kept as spaces.

    Stripping tags outright concatenates adjacent spans ("...2026" + "2026..."
    + "6.4" + "/10" + "→"), which produced unreadable ItemList names on hubs.
    """
    with_spaces = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", unescape(with_spaces)).strip()


_SMALL_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
    "nor", "of", "on", "or", "the", "to", "vs", "with",
}
_ACRONYMS = {"tv", "hd", "uhd", "led", "oled", "4k", "8k", "usb"}
_DATE_PREFIX_RE = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}\b")


def _readable_name(url: str) -> str:
    """Human-readable name from a URL's last path segment (URL itself untouched)."""
    segment = url.rstrip("/").rsplit("/", 1)[-1]
    if segment.lower().endswith(".html"):
        segment = segment[: -len(".html")]
    segment = re.sub(r"^\d{4}-", "", segment)  # leading publication year
    words = [word for word in re.split(r"[-_]+", segment) if word]
    titled = []
    for index, word in enumerate(words):
        low = word.lower()
        if low in _ACRONYMS:
            titled.append(low.upper())
        elif index and low in _SMALL_WORDS:
            titled.append(low)
        else:
            titled.append(low.capitalize())
    return " ".join(titled) or "Review"


def _is_clean_label(label: str) -> bool:
    """Reject decorative/compound anchor text; prefer a real visible title."""
    return bool(label) and "→" not in label and "/10" not in label and not _DATE_PREFIX_RE.match(label)


def _canonical_link(href: str) -> str:
    """Absolute abvorn.com URL for a reviews/categories href, else ""."""
    href = unescape(href.strip())
    if href.startswith(SITE + "/"):
        path = href[len(SITE):]
    elif href.startswith("http://abvorn.com/"):
        path = href[len("http://abvorn.com"):]
    elif href.startswith("/"):
        path = href
    elif href.startswith(("reviews/", "categories/")):
        path = "/" + href
    else:
        return ""
    path = path.split("#", 1)[0].split("?", 1)[0]
    if not _CATEGORY_PATH_RE.match(path):
        return ""
    return rel_url(path.lstrip("/"))


def _rps_products(html: str) -> list[dict]:
    match = _RPS_DATA_RE.search(html)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return []
    if not isinstance(data, dict) or not isinstance(data.get("products"), list):
        return []
    return [
        product
        for product in data["products"]
        if isinstance(product, dict) and str(product.get("name") or "").strip()
    ]


def itemlist_obj(rel: str, html: str) -> dict | None:
    """ItemList for a review's real products, or a hub's review/category links."""
    products = _rps_products(html)
    if products:
        elements = []
        for position, product in enumerate(products, 1):
            node: dict = {"@type": "Product", "name": product["name"]}
            if product.get("url"):
                node["url"] = product["url"]
            if product.get("price"):
                node["offers"] = {"@type": "Offer", "price": product["price"]}
            if product.get("image"):
                node["image"] = product["image"]
            elements.append(
                {"@type": "ListItem", "position": position, "item": node}
            )
        name = meta(html, "og:title") or h1_text(html) or "Reviewed products"
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": name,
            "url": rel_url(rel),
            "numberOfItems": len(elements),
            "itemListElement": elements,
        }

    # One entry per URL. Image-only anchors carry no text, so prefer a later
    # clean visible title over the readable URL-derived fallback when available.
    seen: dict[str, tuple[str, bool]] = {}
    for match in _HREF_RE.finditer(html):
        url = _canonical_link(match.group(1))
        if not url:
            continue
        text = _plain_text(match.group(2))
        clean = _is_clean_label(text)
        if url in seen:
            label, from_text = seen[url]
            if clean and not from_text:
                seen[url] = (text, True)
            continue
        seen[url] = (text, True) if clean else (_readable_name(url), False)
    candidates = [(url, label) for url, (label, _) in seen.items()]
    # Require a real review-card link: "further reading" and nav links on
    # articles point at /reviews/<segment>/ only, so they do not make a hub.
    if not any(
        _REVIEW_CARD_PATH_RE.match(url[len(SITE):])
        for url, _ in candidates
        if url.startswith(SITE + "/reviews/")
    ):
        return None
    elements = [
        {
            "@type": "ListItem",
            "position": position,
            "name": label,
            "item": url,
        }
        for position, (url, label) in enumerate(candidates[:_MAX_HUB_ITEMS], 1)
    ]
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": meta(html, "og:title") or h1_text(html) or "Abvorn reviews",
        "url": rel_url(rel),
        "numberOfItems": len(elements),
        "itemListElement": elements,
    }


def article_obj(rel: str, html: str) -> dict:
    url = rel_url(rel)
    obj: dict = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": h1_text(html) or meta(html, "og:title"),
        "description": meta(html, "description") or meta(html, "og:description"),
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "url": url,
        "author": ORG,
        "publisher": ORG,
        "isAccessibleForFree": True,
    }
    image = meta(html, "og:image")
    if image:
        obj["image"] = image
    parts = rel.split("/")
    if parts[0] == "reviews" and len(parts) > 1:
        obj["articleSection"] = parts[1].replace("-", " ").title()
    pub = re.search(r"Published " + _DATE, html)
    upd = re.search(r"Updated " + _DATE, html)
    if pub:
        obj["datePublished"] = iso_date(pub.group(1))
    if upd:
        obj["dateModified"] = iso_date(upd.group(1))
    elif pub:
        obj["dateModified"] = obj["datePublished"]
    return obj


def webpage_obj(rel: str, html: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": meta(html, "og:title") or h1_text(html),
        "description": meta(html, "description"),
        "url": rel_url(rel),
        "isPartOf": {"@type": "WebSite", "name": "Abvorn", "url": f"{SITE}/"},
    }


def wrap_time(html: str, label: str) -> str:
    pattern = rf'(<span class="date">){label} ({_DATE[1:-1]})(</span>)'

    def repl(m: re.Match) -> str:
        return (
            f"{m.group(1)}{label} "
            f'<time datetime="{iso_date(m.group(2))}">{m.group(2)}</time>'
            f"{m.group(3)}"
        )

    return re.sub(pattern, repl, html)


def add_main(html: str) -> str:
    if "<main" in html:
        return html
    m = re.search(r'<article([^>]*?)\sid="main"([^>]*)>', html)
    if not m:
        return html
    html = html.replace(
        m.group(0), f'<main id="main"><article{m.group(1)}{m.group(2)}>', 1
    )
    return html.replace("</article>", "</article></main>", 1)


def fix_comparison_canonical(rel: str, html: str) -> str:
    if not (rel.startswith("comparisons/") and rel.endswith(".html")):
        return html
    slug = rel[len("comparisons/"):-len(".html")]
    html = html.replace(
        f"{SITE}/comparisons/{slug}/", f"{SITE}/comparisons/{slug}.html"
    )
    html = html.replace(
        f'"/comparisons/{slug}/"', f'"/comparisons/{slug}.html"'
    )
    return html


def process(rel: str, html: str) -> str:
    # Build schema from the raw page first: wrap_time() rewrites the visible
    # dates, which would hide them from the date parser.
    html = _normalize_ld_scripts(html)
    types = _existing_ld_types(html)
    html = _drop_duplicate_injected_article(html)
    nl = "\r\n" if "\r\n" in html else "\n"
    is_article = (
        re.search(r'<meta[^>]*property="og:type"[^>]*content="article"', html)
        is not None
    )
    block = ""
    if "ai-seo:schema" not in html:
        if is_article:
            if "Article" not in types:
                block = ld_block(article_obj(rel, html), "schema", nl)
        else:
            if "WebPage" not in types:
                block = ld_block(webpage_obj(rel, html), "schema", nl)
            if rel == "index.html":
                if "Organization" not in types and "ai-seo:org" not in html:
                    block += ld_block(
                        ORG | {"@context": "https://schema.org"}, "org", nl
                    )
                if "WebSite" not in types and "ai-seo:website" not in html:
                    block += ld_block(
                        {"@context": "https://schema.org", "@type": "WebSite",
                         "name": "Abvorn", "url": f"{SITE}/"},
                        "website",
                        nl,
                    )
    # Rebuild our own ItemList from the current page so name-extraction fixes
    # propagate to hubs that already carry an injected block. Real (unmarked)
    # ItemList schema is never touched.
    marked_itemlist = next(
        (m for m in _MARKED_LD_RE.finditer(html) if m.group("marker") == "itemlist"),
        None,
    )
    listing = itemlist_obj(rel, html)
    if marked_itemlist is not None:
        replacement = ld_block(listing, "itemlist", nl) if listing else ""
        html = (
            html[: marked_itemlist.start()] + replacement + html[marked_itemlist.end():]
        )
    elif "ItemList" not in types and listing:
        block += ld_block(listing, "itemlist", nl)

    html = wrap_time(html, "Published")
    html = wrap_time(html, "Updated")
    html = fix_comparison_canonical(rel, html)
    html = add_main(html)
    if block:
        html = html.replace("</head>", block + "</head>", 1)
    return html


def inject_tree(root, dry_run: bool = False, check: bool = False) -> tuple[int, int]:
    """Apply :func:`process` to every HTML file under *root*.

    Returns ``(changed, added)`` where ``added`` counts pages that received a
    new JSON-LD block. With ``dry_run`` or ``check`` nothing is written.
    """
    root = pathlib.Path(root)
    changed = added = 0
    for f in sorted(root.rglob("*.html")):
        rel = f.relative_to(root).as_posix()
        if rel in SKIP:
            continue
        before = f.read_bytes().decode("utf-8")
        after = process(rel, before)
        if after == before:
            continue
        changed += 1
        if "ai-seo:schema" not in before and "ai-seo:schema" in after:
            added += 1
        if dry_run or check:
            print(f"  {'needs' if check else 'would change'}: {rel}")
        else:
            f.write_bytes(after.encode("utf-8"))
    return changed, added


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="docs")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    changed, added = inject_tree(args.root, dry_run=args.dry_run, check=args.check)
    verb = "would change" if (args.dry_run or args.check) else "updated"
    print(f"{changed} page(s) {verb}; {added} got new JSON-LD")
    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
