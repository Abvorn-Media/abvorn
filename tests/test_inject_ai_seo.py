"""Tests for the post-build AI-SEO injector (scripts/inject_ai_seo.py)."""
import importlib.util
import json
import logging
import pathlib
import re

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "inject_ai_seo.py"
_spec = importlib.util.spec_from_file_location("inject_ai_seo", _SCRIPT)
seo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seo)


ARTICLE = """<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<meta name="description" content="Our picks for the best wireless headphones.">
<meta property="og:type" content="article">
<meta property="og:title" content="Best Wireless Headphones 2026">
<meta property="og:image" content="https://abvorn.com/assets/logo.png?v=2">
<link rel="canonical" href="https://abvorn.com/reviews/wireless-headphones/">
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
<div class="container review-layout">
<article class="article-body" id="main"><h1>Best Wireless Headphones</h1>
<p class="hero-meta"><span class="date">Published Aug 1, 2026</span> <span class="date">Updated Sep 6, 2026</span></p>
</article>
<aside class="hero-pick">Pick</aside>
</div>
</body></html>"""


def ld_blocks(html):
    return [
        json.loads(m.group(1))
        for m in re.finditer(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S
        )
    ]


def test_article_schema_uses_visible_dates():
    out = seo.process("reviews/wireless-headphones/best-2026-08-01.html", ARTICLE)
    article = next(b for b in ld_blocks(out) if b["@type"] == "Article")
    assert article["headline"] == "Best Wireless Headphones"
    assert article["datePublished"] == "2026-08-01"
    assert article["dateModified"] == "2026-09-06"
    assert article["articleSection"] == "Wireless Headphones"
    assert article["author"]["name"] == "Abvorn"
    assert article["publisher"]["logo"]["url"] == "https://abvorn.com/assets/logo.png"
    assert article["isAccessibleForFree"] is True


def test_dates_are_machine_readable_and_main_added():
    out = seo.process("reviews/wireless-headphones/best-2026-08-01.html", ARTICLE)
    assert '<time datetime="2026-08-01">Aug 1, 2026</time>' in out
    assert '<time datetime="2026-09-06">Sep 6, 2026</time>' in out
    assert '<main id="main"><article class="article-body">' in out
    assert "</article></main>" in out
    assert out.count("<main") == 1


def test_processing_is_idempotent():
    once = seo.process("reviews/wireless-headphones/best-2026-08-01.html", ARTICLE)
    twice = seo.process("reviews/wireless-headphones/best-2026-08-01.html", once)
    assert once == twice


def test_injected_jsonld_is_ascii_safe():
    html = ARTICLE.replace("Best Wireless Headphones", "Best Headphones \u2014 Top Picks")
    out = seo.process("reviews/wireless-headphones/best-2026-08-01.html", html)
    block = re.search(r'<!-- ai-seo:schema -->\s*<script[^>]*>(.*?)</script>', out, re.S)
    assert block
    assert all(ord(c) < 128 for c in block.group(1))
    assert json.loads(block.group(1))["headline"] == "Best Headphones \u2014 Top Picks"


def test_homepage_gets_organization_and_websiteschema():
    html = """<html><head><meta property="og:type" content="website">
<meta property="og:title" content="Abvorn">
<meta name="description" content="Reviews."></head><body>hi</body></html>"""
    out = seo.process("index.html", html)
    types = {b["@type"] for b in ld_blocks(out)}
    assert {"WebPage", "Organization", "WebSite"} <= types


def test_comparison_canonical_points_at_real_file():
    html = """<html><head>
<meta property="og:type" content="website">
<link rel="canonical" href="https://abvorn.com/comparisons/laptops/">
<meta property="og:url" content="https://abvorn.com/comparisons/laptops/">
</head><body>x</body></html>"""
    out = seo.process("comparisons/laptops.html", html)
    assert "https://abvorn.com/comparisons/laptops.html" in out
    assert "https://abvorn.com/comparisons/laptops/" not in out


def test_inject_tree_skips_verification_and_console(tmp_path):
    (tmp_path / "index.html").write_text(
        "<html><head><meta property='og:type' content='website'></head><body>x</body></html>",
        encoding="utf-8",
    )
    (tmp_path / "google123.html").write_text("<html><body>token</body></html>", encoding="utf-8")
    (tmp_path / "console.html").write_text("<html><body>dash</body></html>", encoding="utf-8")
    changed, _ = seo.inject_tree(tmp_path)
    assert changed == 1
    assert "ai-seo:schema" not in (tmp_path / "google123.html").read_text(encoding="utf-8")
    assert "ai-seo:schema" not in (tmp_path / "console.html").read_text(encoding="utf-8")


# --- JSON-LD normalization / de-duplication fixtures -----------------------

SITE = "https://abvorn.com"

ARTICLE_FRAG = json.dumps(
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "A Dispatch",
        "datePublished": "2026-10-30",
    },
    ensure_ascii=True,
)
FAQ_FRAG = json.dumps(
    {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "Why?",
                "acceptedAnswer": {"@type": "Answer", "text": "Because."},
            }
        ],
    },
    ensure_ascii=True,
)
BREADCRUMB_FRAG = json.dumps(
    {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"}
        ],
    },
    ensure_ascii=True,
)
CONCATENATED_FRAGMENTS = "\n" + "\n".join(
    (ARTICLE_FRAG, FAQ_FRAG, BREADCRUMB_FRAG)
) + "\n"


def _injected_article_block():
    return (
        "\n<!-- ai-seo:schema -->\n"
        f'<script type="application/ld+json">{ARTICLE_FRAG}</script>'
    )


def _blog_html(fragments, with_injected_article=False):
    injected = _injected_article_block() if with_injected_article else ""
    return (
        '<html><head><meta property="og:type" content="article">'
        '<meta property="og:title" content="A Dispatch">'
        f'<script type="application/ld+json">{fragments}</script>'
        f"{injected}</head><body><h1>A Dispatch</h1></body></html>"
    )


def _only_injected_articles_html(count):
    return (
        '<html><head><meta property="og:type" content="article">'
        '<meta property="og:title" content="A Dispatch">'
        + _injected_article_block() * count
        + "</head><body><h1>A Dispatch</h1></body></html>"
    )


LONE_INJECTED_ARTICLE_HTML = _only_injected_articles_html(1)
TWO_INJECTED_ARTICLES_HTML = _only_injected_articles_html(2)


def _all_ld_types(html):
    """Every @type in every LD script, flattening @graph nodes."""
    types = []
    for payload in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ):
        obj = json.loads(payload)
        nodes = obj.get("@graph", [obj]) if isinstance(obj, dict) else []
        for node in nodes:
            if isinstance(node, dict) and isinstance(node.get("@type"), str):
                types.append(node["@type"])
    return types


def _itemlist(html):
    return next(b for b in ld_blocks(html) if b["@type"] == "ItemList")


HUB_HTML = """<html><head><meta property="og:type" content="website">
<meta property="og:title" content="TV Reviews"></head><body>
<a href="/reviews/tv/one.html">One</a>
<a href="/reviews/tv/two.html">Two</a>
<a href="/categories/tv/">TV category</a>
<a href="https://abvorn.com/reviews/tv/one.html">One again</a>
</body></html>"""

REVIEW_HTML = ARTICLE.replace(
    "</head>",
    '<script id="abvorn-rps-data" type="application/json">'
    + json.dumps(
        {
            "products": [
                {
                    "name": "Alpha TV",
                    "price": "$199.99",
                    "url": "https://www.amazon.com/dp/B0ABCDEFGH",
                },
                {"name": "Beta TV", "url": "https://www.amazon.com/dp/B0IJKLMNOP"},
            ]
        }
    )
    + "</script>\n</head>",
)


def test_concatenated_ld_fragments_become_one_graph():
    out = seo.process("blog/a-dispatch/index.html", _blog_html(CONCATENATED_FRAGMENTS))
    payloads = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', out, re.S
    )
    assert len(payloads) == 1
    graph = json.loads(payloads[0])
    assert graph["@context"] == "https://schema.org"
    assert {node["@type"] for node in graph["@graph"]} == {
        "Article",
        "FAQPage",
        "BreadcrumbList",
    }


def test_existing_article_is_not_duplicated():
    single = (
        '<html><head><meta property="og:type" content="article">'
        f'<script type="application/ld+json">{ARTICLE_FRAG}</script>'
        "</head><body>x</body></html>"
    )
    assert _all_ld_types(seo.process("blog/a/index.html", single)).count("Article") == 1

    repaired = seo.process(
        "blog/a-dispatch/index.html",
        _blog_html(CONCATENATED_FRAGMENTS, with_injected_article=True),
    )
    assert _all_ld_types(repaired).count("Article") == 1
    assert "ai-seo:schema" not in repaired


def test_unparseable_ld_fragment_is_untouched_and_warned(caplog):
    broken = '{"@context": "https://schema.org", "@type": "Article", "headline": " cut'
    fragments = "\n" + ARTICLE_FRAG + "\n" + broken + "\n"
    html = _blog_html(fragments)
    before = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ).group(1)
    with caplog.at_level(logging.WARNING):
        out = seo.process("blog/broken/index.html", html)
    after = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', out, re.S
    ).group(1)
    assert after == before
    assert any("JSON-LD" in record.message for record in caplog.records)
    # Every injected block is still valid JSON; no new broken JSON is emitted.
    for payload in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', out, re.S
    ):
        if payload != before:
            json.loads(payload)


def test_hub_page_gets_webpage_and_canonical_itemlist():
    out = seo.process("tv/index.html", HUB_HTML)
    assert {"WebPage", "ItemList"} <= set(_all_ld_types(out))
    itemlist = _itemlist(out)
    urls = [element["item"] for element in itemlist["itemListElement"]]
    assert urls == [
        f"{SITE}/reviews/tv/one.html",
        f"{SITE}/reviews/tv/two.html",
        f"{SITE}/categories/tv/",
    ]
    assert all(url.startswith(SITE) for url in urls)


NAMES_HUB_HTML = """<html><head><meta property="og:type" content="website">
<meta property="og:title" content="TV Reviews"></head><body>
<a href="/reviews/tv/2026-tv-buying-guide-best-picks.html"><img src="/x.jpg" alt="pic"></a>
<h2><a href="/reviews/tv/2026-tv-buying-guide-best-picks.html">2026 TV Buying Guide: Best Picks</a></h2>
<a class="archive-row" href="/reviews/tv/another-guide.html"><span>Oct 04, 2026</span><span>Another Guide</span><span>6.4<span>/10</span></span><span>&#8594;</span></a>
<a href="/reviews/tv/no-visible-title-2026.html"><img src="/y.jpg" alt="pic"></a>
</body></html>"""


def test_hub_itemlist_names_are_readable():
    itemlist = _itemlist(seo.process("tv/index.html", NAMES_HUB_HTML))
    names = [element["name"] for element in itemlist["itemListElement"]]
    assert names == [
        "2026 TV Buying Guide: Best Picks",  # visible title beats image-only anchor
        "Another Guide",  # readable URL fallback beats date/score/arrow concatenation
        "No Visible Title 2026",
    ]
    for name in names:
        assert "→" not in name and "/10" not in name and ".html" not in name
        assert not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", name)  # not a bare slug


def test_injected_itemlist_is_refreshed_from_current_markup():
    first = seo.process("tv/index.html", HUB_HTML)
    stale = first.replace('"name":"One"', '"name":"stale-name.html"')
    assert "stale-name.html" in stale
    refreshed = seo.process("tv/index.html", stale)
    assert [e["name"] for e in _itemlist(refreshed)["itemListElement"]] == [
        "One", "Two", "TV category"
    ]
    assert "stale-name.html" not in refreshed
    assert seo.process("tv/index.html", refreshed) == refreshed


def test_review_products_become_itemlist_without_fabricated_ratings():
    out = seo.process("reviews/tv/best.html", REVIEW_HTML)
    itemlist = _itemlist(out)
    assert itemlist["url"] == f"{SITE}/reviews/tv/best.html"
    products = [element["item"] for element in itemlist["itemListElement"]]
    assert [product["@type"] for product in products] == ["Product", "Product"]
    assert products[0]["name"] == "Alpha TV"
    assert products[0]["url"] == "https://www.amazon.com/dp/B0ABCDEFGH"
    assert products[0]["offers"]["price"] == "$199.99"
    assert "image" not in products[0]
    assert products[1]["name"] == "Beta TV"
    assert "offers" not in products[1]
    assert "aggregateRating" not in out


def test_hub_itemlist_is_bounded_and_deduplicated():
    links = "".join(
        f'<a href="/reviews/tv/review-{i}.html">Review {i}</a>' for i in range(60)
    )
    html = (
        '<html><head><meta property="og:type" content="website"></head><body>'
        + links
        + '<a href="/reviews/tv/review-0.html">Review 0 again</a></body></html>'
    )
    itemlist = _itemlist(seo.process("tv/index.html", html))
    assert itemlist["numberOfItems"] == 50
    assert len(itemlist["itemListElement"]) == 50
    assert len({element["item"] for element in itemlist["itemListElement"]}) == 50


def test_article_further_reading_links_do_not_create_itemlist():
    html = ARTICLE.replace(
        "</body>", '<div><a href="/reviews/tv/">TV reviews</a></div></body>'
    )
    out = seo.process("reviews/tv/single-article.html", html)
    assert "ItemList" not in _all_ld_types(out)


@pytest.mark.parametrize(
    "html, count",
    [
        (LONE_INJECTED_ARTICLE_HTML, 1),
        (TWO_INJECTED_ARTICLES_HTML, 2),
    ],
)
def test_injected_article_markers_survive_without_a_real_article(html, count):
    out = seo.process("blog/only-injected/index.html", html)
    assert out.count("ai-seo:schema") == count
    assert _all_ld_types(out).count("Article") == count


@pytest.mark.parametrize(
    "rel, html, expected_markers",
    [
        ("blog/a-dispatch/index.html", _blog_html(CONCATENATED_FRAGMENTS), None),
        (
            "blog/a-dispatch/index.html",
            _blog_html(CONCATENATED_FRAGMENTS, with_injected_article=True),
            None,
        ),
        (
            "blog/broken/index.html",
            _blog_html("\n" + ARTICLE_FRAG + '\n{"broken":\n'),
            None,
        ),
        ("tv/index.html", HUB_HTML, None),
        ("reviews/tv/best.html", REVIEW_HTML, None),
        ("blog/only-injected/index.html", LONE_INJECTED_ARTICLE_HTML, 1),
        ("blog/only-injected/index.html", TWO_INJECTED_ARTICLES_HTML, 2),
    ],
)
def test_new_cases_are_idempotent(rel, html, expected_markers):
    once = seo.process(rel, html)
    assert seo.process(rel, once) == once
    if expected_markers is not None:
        assert once.count("ai-seo:schema") == expected_markers
