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
    # Categories = number of niches (3), stable either way.
    assert stats["categories"] == 3


def test_stats_do_not_show_zero_when_state_reports_zero():
    # The exact bug: state says 0 posts but reviews exist. Stats must not be 0.
    html = build_homepage(_state(posts=0), reviews=_reviews(5))
    stats = _stats(html)
    assert stats["guides"] == 5
    assert stats["guides"] != 0
