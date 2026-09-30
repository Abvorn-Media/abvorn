"""A page with no products is not a product review.

`scan_published_reviews()` enumerates every docs/reviews/<niche>/*.html file and
feeds the result to the homepage cards, the category listings, sitemap.xml,
feed.xml, llms.txt and llms-full.txt. It had no invariant that the page it
accepted actually contained a product, so a productless page that the content
pipeline left behind was indexed everywhere as if it were a real review.

Two failure modes, one missing gate:

  * off-topic article filed under a niche -- an LLM wrote "First-Time Hotel
    Booking Guide" and "Solar Panels for Beginners" into reviews/laptops/ and
    reviews/robot-vacuums/;
  * a directory named after a product title -- the LLM returned a product name
    where a niche slug was expected, so
    reviews/roku-40-inch-select-series-smart-tv-2026-1080p-full-hd-tv-ro/
    was created.

Both were live, self-canonical and not noindex. The quality scorer had rated
all of them quality_score 10.0 (the maximum), so the quality gate did not
catch them either.
"""

import json

import pytest

from src.deployment import scan_published_reviews


ASIN = "B0BXGFFSL1"
GOOD = f"""<!doctype html><html><head><title>t</title></head><body>
<h1>Best Webcams 2026</h1>
<p>Updated: 2026-09-30</p>
<a href="https://www.amazon.com/dp/{ASIN}?tag=x-20">Check Price on Amazon</a>
<a href="/compare.html?asin={ASIN}">Compare</a>
<p>Great webcam for streaming.</p>
</body></html>"""

# Productless, off-topic. Carries an EMPTY product set and the FAQ schema's
# `itemprop="mainEntity"` (which is a question list, NOT a product) so a naive
# "does it mention a product-ish attribute" check would wrongly accept it.
PRODUCTLESS = f"""<!doctype html><html><head><title>t</title>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[]}}
</script>
<script id="abvorn-rps-data" type="application/json">{json.dumps({"products": []})}</script>
</head><body>
<h1>First-Time Hotel Booking Guide: No Mistakes, Full Savings</h1>
<p>Updated: 2026-09-30</p>
<div class="verdict" itemprop="mainEntity"></div>
<p>Book your hotel with confidence and save money on every trip.</p>
</body></html>"""


def _write(root, niche, name, html):
    d = root / "reviews" / niche
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(html, encoding="utf-8")
    return d / name


def test_productless_page_is_not_a_published_review(tmp_path):
    _write(tmp_path, "laptops", "hotel-booking.html", PRODUCTLESS)
    assert scan_published_reviews(str(tmp_path)) == []


def test_product_page_is_still_a_published_review(tmp_path):
    _write(tmp_path, "webcams", "best-webcams.html", GOOD)
    got = scan_published_reviews(str(tmp_path))
    assert [r["rel"] for r in got] == ["/reviews/webcams/best-webcams.html"]


def test_productless_page_excluded_while_siblings_survive(tmp_path):
    """The exact production shape: a real niche that also holds one junk file."""
    _write(tmp_path, "laptops", "best-laptops.html", GOOD)
    _write(tmp_path, "laptops", "solar-panels.html", PRODUCTLESS)

    got = scan_published_reviews(str(tmp_path))
    rels = [r["rel"] for r in got]
    assert rels == ["/reviews/laptops/best-laptops.html"], rels


def test_niche_dir_named_after_a_product_is_excluded(tmp_path):
    """The LLM returned a product name where a niche slug was expected."""
    _write(tmp_path, "roku-40-inch-select-series-smart-tv-2026-1080p", "index.html", PRODUCTLESS)
    assert scan_published_reviews(str(tmp_path)) == []


def test_rps_products_alone_count_as_products(tmp_path):
    """Some real pages carry the product set only in the RPS JSON block --
    reviews/wireless-earbuds/index.html has 1 product and 0 amazon /dp/ links.
    Filtering on /dp/ alone would delete a legitimate page."""
    only_rps = f"""<!doctype html><html><head><title>t</title>
<script id="abvorn-rps-data" type="application/json">
{json.dumps({"products": [{"name": "AirPods Pro 3", "price": "$249.00"}]})}
</script></head><body>
<h1>Best Wireless Earbuds 2026</h1>
<p>Updated: 2026-09-30</p>
<p>Excellent sound and great noise cancelling.</p>
</body></html>"""
    _write(tmp_path, "wireless-earbuds", "index.html", only_rps)
    got = scan_published_reviews(str(tmp_path))
    assert [r["rel"] for r in got] == ["/reviews/wireless-earbuds/"]


def test_niche_with_only_a_productless_index_is_excluded(tmp_path):
    _write(tmp_path, "ghost-niche", "index.html", PRODUCTLESS)
    assert scan_published_reviews(str(tmp_path)) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
