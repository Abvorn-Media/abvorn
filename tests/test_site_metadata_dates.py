"""Truthful freshness dates and one URL inventory for the site metadata files.

Every published page must advertise its own real date in feed.xml and sitemap.xml;
llms.txt must be ordered by recency and carry a generated timestamp; and the
machine-readable indexes must cover blog posts and comparison pages as well as
core pages, categories and reviews (while the RSS feed stays review-only).
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from src.deployment import write_site_metadata

SITE = "https://abvorn.com"
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _write(tmp_path, items, extras=()):
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    for rel, html in extras:
        target = docs / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
    write_site_metadata(str(docs), items, categories=[])
    return docs


def _sitemap_urls(docs):
    root = ET.fromstring((docs / "sitemap.xml").read_text(encoding="utf-8"))
    urls = {}
    for url in root.findall("s:url", SITEMAP_NS):
        loc = url.find("s:loc", SITEMAP_NS)
        lastmod = url.find("s:lastmod", SITEMAP_NS)
        urls[loc.text] = lastmod.text if lastmod is not None else None
    return urls


def test_llms_has_generated_date_and_recent_first_reviews(tmp_path):
    items = [
        {"title": "Zebra Review", "slug": "reviews/zebra/", "date": "2026-01-05"},
        {"title": "Alpha Review", "slug": "reviews/alpha/", "date": "2026-11-18"},
        {"title": "Middle Review", "slug": "reviews/middle/", "date": "2026-06-01"},
    ]
    docs = _write(tmp_path, items)

    llms = (docs / "llms.txt").read_text(encoding="utf-8")
    assert re.search(r"^Generated: \d{4}-\d{2}-\d{2}$", llms, re.M), llms
    assert "Generated: " in (docs / "llms-full.txt").read_text(encoding="utf-8")

    latest = llms.split("## Latest reviews", 1)[1]
    assert latest.index("Alpha Review") < latest.index("Middle Review")
    assert latest.index("Middle Review") < latest.index("Zebra Review")


def test_feed_pubdate_matches_each_item_date(tmp_path):
    older, newer = "2026-01-02", "2026-11-19"
    items = [
        {"title": "Older", "slug": "reviews/older/", "updated": older},
        {"title": "Newer", "slug": "reviews/newer/", "date": newer},
    ]
    docs = _write(tmp_path, items)

    root = ET.fromstring((docs / "feed.xml").read_text(encoding="utf-8"))
    pubdates = [node.text for node in root.findall(".//item/pubDate")]
    assert pubdates == [
        datetime.strptime(d, "%Y-%m-%d").strftime("%a, %d %b %Y 00:00:00 +0000")
        for d in (older, newer)
    ]
    assert len(set(pubdates)) == 2


def test_sitemap_lastmod_uses_own_date_and_newest_for_other_pages(tmp_path):
    newest = "2026-11-17"
    items = [
        {"title": "Older", "slug": "reviews/older/", "date": "2026-10-11"},
        {"title": "Newest", "slug": "reviews/newest/", "date": newest},
        {"title": "Undated", "slug": "reviews/undated/"},
    ]
    docs = _write(tmp_path, items)
    urls = _sitemap_urls(docs)

    assert urls[f"{SITE}/reviews/older/"] == "2026-10-11"
    assert urls[f"{SITE}/reviews/newest/"] == newest
    assert urls[f"{SITE}/reviews/undated/"] == newest
    # Core and category pages have no per-page date: use the newest known one.
    assert urls[SITE] == newest
    assert urls[f"{SITE}/reviews"] == newest
    assert urls[f"{SITE}/about.html"] == newest


def test_blog_and_comparisons_in_indexes_but_not_feed(tmp_path):
    extras = [
        ("blog/deep-dive/index.html", "<html><head><title>Blog A - Deep Dive</title></head><body></body></html>"),
        ("comparisons/x.html", '<html><head><meta property="og:title" content="X versus Y"></head><body></body></html>'),
    ]
    items = [{"title": "Review One", "slug": "reviews/one/", "date": "2026-09-01"}]
    docs = _write(tmp_path, items, extras)

    for name in ("sitemap.xml", "llms.txt", "llms-full.txt"):
        text = (docs / name).read_text(encoding="utf-8")
        assert f"{SITE}/blog/deep-dive/" in text, name
        assert f"{SITE}/comparisons/x.html" in text, name
        if name == "llms-full.txt":
            assert "Blog A - Deep Dive" in text
            assert "X versus Y" in text

    urls = _sitemap_urls(docs)
    assert urls[f"{SITE}/blog/deep-dive/"] == "2026-09-01"
    assert urls[f"{SITE}/comparisons/x.html"] == "2026-09-01"

    feed = ET.fromstring((docs / "feed.xml").read_text(encoding="utf-8"))
    links = [node.text for node in feed.findall(".//item/link")]
    assert links == [f"{SITE}/reviews/one/"]


def test_zero_items_still_writes_valid_empty_metadata(tmp_path):
    docs = _write(tmp_path, [])
    for name in ("robots.txt", "llms.txt", "llms-full.txt", "feed.xml", "sitemap.xml"):
        assert (docs / name).is_file()
    root = ET.fromstring((docs / "sitemap.xml").read_text(encoding="utf-8"))
    assert root.findall("s:url", SITEMAP_NS)[0].find("s:lastmod", SITEMAP_NS) is None
    ET.fromstring((docs / "feed.xml").read_text(encoding="utf-8"))
    assert Path(docs / "llms.txt").read_text(encoding="utf-8").startswith("# Abvorn")


def test_item_date_accepts_updated_or_date_key():
    from src.deployment import _item_date

    assert _item_date({"updated": "2026-03-01", "date": "2026-01-01"}) == "2026-03-01"
    assert _item_date({"date": "2026-01-01"}) == "2026-01-01"
    assert _item_date({}, "2026-02-02") == "2026-02-02"


def test_write_files_keeps_each_dated_article_date_and_url(tmp_path, monkeypatch):
    """The write_files call site must not collapse dated articles to the hub."""
    from src.deployment import write_files

    monkeypatch.chdir(tmp_path)
    review_dir = tmp_path / "docs" / "reviews" / "headphones"
    review_dir.mkdir(parents=True)

    def _page(title, updated):
        return (
            f"<html><head><title>{title}</title>"
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Product",'
            f'"name":"Headphones","dateModified":"{updated}"'
            "}</script></head>"
            f"<body><h1>{title}</h1></body></html>"
        )

    (review_dir / "index.html").write_text(
        _page("Headphones Hub", "2026-01-05"), encoding="utf-8")
    (review_dir / "old-review-2026-01-05.html").write_text(
        _page("Old Review", "2026-01-05"), encoding="utf-8")
    (review_dir / "new-review-2026-11-18.html").write_text(
        _page("New Review", "2026-11-18"), encoding="utf-8")

    state = {"niches": [{"slug": "headphones", "name": "Headphones"}]}
    write_files("headphones", {}, state)

    docs = tmp_path / "docs"
    feed = ET.fromstring((docs / "feed.xml").read_text(encoding="utf-8"))
    pubdates = {
        node.findtext("title"): node.findtext("pubDate")
        for node in feed.findall(".//item")
    }
    assert set(pubdates) == {"Old Review", "New Review"}
    for title, day in (("Old Review", "2026-01-05"), ("New Review", "2026-11-18")):
        assert pubdates[title] == datetime.strptime(day, "%Y-%m-%d").strftime(
            "%a, %d %b %Y 00:00:00 +0000")
    assert len(set(pubdates.values())) == 2

    urls = _sitemap_urls(docs)
    assert urls[f"{SITE}/reviews/headphones/old-review-2026-01-05.html"] == "2026-01-05"
    assert urls[f"{SITE}/reviews/headphones/new-review-2026-11-18.html"] == "2026-11-18"
