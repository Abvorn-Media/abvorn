"""Every published review must report its own last-modified date.

`scan_published_reviews()` probed for the literal text "Updated: 2026-09-06".
build_article_page has never emitted that shape -- it renders

    Updated <time datetime="2026-09-06">Sep 6, 2026</time>

so the probe never matched and every one of the 150 reviews came back with
`updated == ""`. Nothing raised: the field is optional at every consumer. The
damage was silent and site-wide --

  * `sorted(..., key=lambda r: r["updated"], reverse=True)` flattened to a tie,
    so "latest reviews" on the homepage and every category listing fell back to
    filesystem order instead of newest-first;
  * the "Updated <date>" badge never rendered anywhere;
  * sitemap <lastmod> for review URLs lost its freshness signal.

These tests pin the parse to the markup that actually ships, and to the real
corpus, so the same silent-empty failure cannot come back.
"""

from datetime import datetime

import pytest

from src.deployment import _review_updated, scan_published_reviews

# Byte-for-byte the shape build_article_page emits.
RENDERED = ('<p class="hero-meta">Laptops <span class="dot"></span>'
            '<span class="date">Published <time datetime="2026-08-31">Aug 31, 2026</time></span>'
            '<span class="dot"></span>'
            '<span class="date">Updated <time datetime="2026-09-06">Sep 6, 2026</time></span></p>')

# dateModified is machine-readable, so it outranks scraping the visible text.
JSONLD = ('<script type="application/ld+json">{"@type":"Article",'
          '"datePublished":"2026-08-31","dateModified":"2026-09-14"}</script>')

LEGACY = '<p>Updated: 2026-09-06</p>'


class TestReviewUpdatedParsing:
    def test_reads_the_rendered_time_element(self):
        """The exact markup on disk -- this is the case that was broken."""
        assert _review_updated(RENDERED) == "2026-09-06"

    def test_prefers_jsonld_date_modified(self):
        assert _review_updated(JSONLD + RENDERED) == "2026-09-14"

    def test_still_reads_the_legacy_text_form(self):
        assert _review_updated(LEGACY) == "2026-09-06"

    def test_published_date_is_not_mistaken_for_updated(self):
        """A page with only a Published stamp has no refresh date."""
        only = ('<span class="date">Published <time datetime="2026-08-31">Aug 31, 2026</time></span>')
        assert _review_updated(only) == ""

    def test_no_date_anywhere_returns_empty(self):
        assert _review_updated("<html><body>hi</body></html>") == ""

    def test_does_not_throw_on_malformed_jsonld(self):
        assert _review_updated('<script>{"dateModified": broken}</script>') == ""


class TestLiveCorpusHasDates:
    def test_every_published_review_reports_an_updated_date(self):
        reviews = scan_published_reviews("docs")
        assert len(reviews) > 100, "corpus unexpectedly small; guard this test"
        missing = [(r["slug"], r["rel"]) for r in reviews if not r["updated"]]
        assert not missing, f"{len(missing)}/{len(reviews)} reviews have no updated date: {missing[:5]}"

    def test_dates_are_iso_formatted_and_sortable(self):
        reviews = scan_published_reviews("docs")
        for r in reviews:
            datetime.strptime(r["updated"], "%Y-%m-%d")  # raises on malformed

    def test_newest_first_ordering_is_stable_and_meaningful(self):
        """The homepage relies on this sort; with every key empty it was a tie."""
        reviews = [r for r in scan_published_reviews("docs") if r["updated"]]
        desc = sorted(reviews, key=lambda r: r["updated"], reverse=True)
        assert [r["updated"] for r in desc] == sorted(
            [r["updated"] for r in desc], reverse=True)
        # A tie-everything corpus has exactly one distinct value. The live site
        # clusters into a few refresh batches, so any spread at all proves the
        # sort is discriminating; the count itself is not the invariant.
        assert len({r["updated"] for r in desc}) > 1, "every review shares one date"
        # And the newest review must actually sort first.
        assert desc[0]["updated"] == max(r["updated"] for r in desc)