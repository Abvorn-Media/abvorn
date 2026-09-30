"""Regression test: homepage stats must derive from actually-published reviews.

Bug: build_homepage summed state["niches"][]["posts"] (the gitignored
cycle_state.json field), which reports 0 on a fresh checkout — so the homepage
showed "0 Guides published / 0 Products compared" even though review pages
existed on disk. The stats now count the actually-published reviews instead.
"""
import re

from src.deployment import build_homepage


def _state(posts=0):
    slugs = ["4k-monitors", "laptops", "webcams"]
    return {
        "niches": [
            {"name": slug.replace("-", " ").title(), "slug": slug, "posts": posts}
            for slug in slugs
        ]
    }


def _reviews(n, slug="laptops"):
    return [
        {
            "slug": slug,
            "name": slug.replace("-", " ").title(),
            "title": f"Review {i}",
            "updated": "2026-09-01",
            "rel": f"/reviews/{slug}/20260901-review-{i}.html",
            "snippet": "s",
        }
        for i in range(n)
    ]


def _stats(html):
    # The four stat cells appear in order: guides, categories, products, cycle.
    # data-target holds the count; the cycle stat has no data-target.
    targets = re.findall(r'data-target="(\d+)"', html)
    # First three are guides / categories / products (in template order).
    return {
        "guides": int(targets[0]) if len(targets) > 0 else None,
        "categories": int(targets[1]) if len(targets) > 1 else None,
        "products": int(targets[2]) if len(targets) > 2 else None,
    }


def test_stats_count_published_reviews_not_state_posts():
    # Fresh-checkout condition: every niche in state reports posts=0.
    html = build_homepage(_state(posts=0), reviews=_reviews(7))
    stats = _stats(html)
    assert stats["guides"] is not None, "guides stat not found"
    assert stats["products"] is not None, "products stat not found"
    # Guides = number of actually-published review pages (7), not state's 0.
    assert stats["guides"] == 7
    # Products est = guides * 3.
    assert stats["products"] == 21
    # Categories = categories that actually have a published review. All 7
    # reviews here are 'laptops', which lives in exactly one CATEGORY_MAP
    # category ("Computing & Monitors"), so the stat must be 1 -- not the
    # 3 niches in state.
    assert stats["categories"] == 1


def test_stats_do_not_show_zero_when_state_reports_zero():
    # The exact bug: state says 0 posts but reviews exist. Stats must not be 0.
    html = build_homepage(_state(posts=0), reviews=_reviews(5))
    stats = _stats(html)
    assert stats["guides"] == 5
    assert stats["guides"] != 0


def test_categories_stat_ignores_niches_with_no_published_review():
    """The 'Categories covered' stat must count the CATEGORY_MAP categories
    that actually have a published review.

    Bug: the stat used len(niches) from state, so a daemon whose state only
    listed 3 niches (laptops, robot-vacuums, tv) reported "3 Categories
    covered" while the page covers 6 categories. A niche with no published
    review covers nothing and must not be counted.
    """
    # 3 niches in state, but only 2 of them have any published review.
    state = {
        "niches": [
            {"name": "Laptops", "slug": "laptops", "posts": 9},
            {"name": "Tv", "slug": "tv", "posts": 5},
            {"name": "Webcams", "slug": "webcams", "posts": 4},
        ]
    }
    reviews = _reviews(3, slug="laptops") + _reviews(2, slug="tv")

    html = build_homepage(state, reviews=reviews)
    stats = _stats(html)

    # laptops + tv both live in "Computing & Monitors" -> exactly 1 covered.
    assert stats["categories"] == 1
    # Not the raw niche count.
    assert stats["categories"] != len(state["niches"])


def test_categories_stat_counts_covered_categories_across_niches():
    """Reviews spread over three different CATEGORY_MAP categories must report
    3, even though state lists only 2 niches."""
    state = {
        "niches": [
            {"name": "Laptops", "slug": "laptops", "posts": 9},
            {"name": "Tv", "slug": "tv", "posts": 5},
        ]
    }
    reviews = (
        _reviews(1, slug="laptops")           # Computing & Monitors
        + _reviews(1, slug="wireless-earbuds")  # Audio
        + _reviews(1, slug="webcams")          # Webcams & Accessories
    )

    html = build_homepage(state, reviews=reviews)
    stats = _stats(html)

    assert stats["categories"] == 3
    assert stats["categories"] != len(state["niches"])
