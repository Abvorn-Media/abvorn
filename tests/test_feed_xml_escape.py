"""Tests for the RSS feed / sitemap XML-escaping fix.

Titles like "S2725QC & LG 27UP650K-W" previously wrote a raw ampersand into
feed.xml, making the whole feed malformed (and the domination cycle's
ContentIntelligence parse fail silently). The writer must XML-escape &, <, >, ", '.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

from src.deployment import write_site_metadata


def _run(items, tmp_path):
    docs_dir = tmp_path / "docs"
    write_site_metadata(str(docs_dir), items)
    return docs_dir


def test_feed_escapes_ampersand_in_title(tmp_path):
    items = [{"title": "S2725QS, S2725QC & LG 27UP650K-W Compared", "slug": "reviews/4k/", "date": "2026-09-01"}]
    docs = _run(items, tmp_path)
    feed = (docs / "feed.xml").read_text(encoding="utf-8")
    assert "&amp;" in feed
    assert " S2725QC & LG " not in feed
    # The feed must parse as well-formed XML.
    root = ET.fromstring(feed)
    titles = [t.text for t in root.findall(".//title")]
    assert titles and "S2725QS, S2725QC & LG 27UP650K-W Compared" in titles


def test_feed_escapes_lt_gt_quote(tmp_path):
    items = [{"title": '5 < 10 "best" > 2', "slug": "reviews/x/", "date": "2026-09-01"}]
    docs = _run(items, tmp_path)
    feed = (docs / "feed.xml").read_text(encoding="utf-8")
    root = ET.fromstring(feed)
    titles = [t.text for t in root.findall(".//title")]
    assert titles and '5 < 10 "best" > 2' in titles


def test_sitemap_is_well_formed_with_special_characters(tmp_path):
    items = [{"title": "A & B", "slug": "reviews/a-b/", "date": "2026-09-01"}]
    docs = _run(items, tmp_path)
    sitemap = (docs / "sitemap.xml").read_text(encoding="utf-8")
    ET.fromstring(sitemap)  # must not raise
    # URLs are slug-derived and contain no raw ampersand.
    assert "&amp;" in sitemap or " & " not in sitemap
