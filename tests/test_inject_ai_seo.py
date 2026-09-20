"""Tests for the post-build AI-SEO injector (scripts/inject_ai_seo.py)."""
import importlib.util
import json
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
