"""Regression test: no review card may render twice on a listing page.

Bug: build_homepage() and _hub_sections() each emit a "Latest reviews" strip
built from the newest reviews and then re-render every category/group in full,
including those same newest reviews. The homepage shipped the tv/laptops trio
in both "Latest reviews" and "Computing & Monitors" (21 cards, 18 unique), and
the /reviews/ + /categories/ hubs each repeated 4 more.

Identity is the per-page rel path, not the niche slug: every docs/reviews/tv/
article shares the slug "tv", so slug-based dedup would drop real cards.
"""
import re
from collections import Counter

from src.deployment import build_homepage, _hub_sections, _review_key


def _state():
    return {
        "niches": [
            {"name": "TV", "slug": "tv", "posts": 1},
            {"name": "Laptops", "slug": "laptops", "posts": 1},
        ]
    }


def _reviews():
    """6 tv articles + 6 laptops articles, all distinct per-page paths."""
    out = []
    for slug in ("tv", "laptops"):
        for i in range(6):
            out.append({
                "slug": slug,
                "name": slug.title(),
                "title": f"{slug.title()} Review {i}",
                "updated": f"2026-09-0{i + 1}",
                "rel": f"/reviews/{slug}/2026090{i + 1}-review-{i}.html",
                "snippet": "s",
            })
    return out


CARD_HREF = re.compile(r'<h2><a href="([^"]+)"')


def _hrefs(html):
    return CARD_HREF.findall(html)


def test_review_key_separates_articles_sharing_a_slug():
    """The whole dedup depends on this: slug is NOT unique per card."""
    a = {"slug": "tv", "rel": "/reviews/tv/roku-55.html"}
    b = {"slug": "tv", "rel": "/reviews/tv/echo-show-5.html"}
    assert _review_key(a) != _review_key(b)
    # Falls back to slug when a caller omits rel (e.g. a single-card category).
    assert _review_key({"slug": "tv"}) == "tv"


def test_homepage_has_no_duplicate_review_cards():
    html = build_homepage(_state(), reviews=_reviews())
    hrefs = _hrefs(html)
    assert hrefs, "expected the homepage to render review cards"
    dupes = {h: c for h, c in Counter(hrefs).items() if c > 1}
    assert not dupes, f"homepage rendered the same review twice: {dupes}"


def test_homepage_keeps_featured_plus_next_reviews():
    """Dedup must not drop coverage: the featured strip takes the newest 3 and
    the category section fills in with the next 3, so no review is lost."""
    reviews = _reviews()
    html = build_homepage(_state(), reviews=reviews)
    hrefs = _hrefs(html)
    # "tv" and "laptops" both map to one category, so: 3 featured + 3 next.
    assert len(hrefs) == 6, f"expected 6 unique cards, got {len(hrefs)}"
    # The 3 newest are the featured strip; the rest come from the section.
    newest = [r["rel"] for r in sorted(reviews, key=lambda r: r["updated"],
                                       reverse=True)[:3]]
    rest = [r["rel"] for r in sorted(reviews, key=lambda r: r["updated"],
                                     reverse=True)[3:6]]
    base = "https://abvorn.com"
    for rel in newest + rest:
        assert f'{base}{rel}' in hrefs, f"{rel} disappeared from the homepage"


def test_hub_sections_have_no_duplicate_review_cards():
    html = _hub_sections(
        _reviews(), "", "#a7c3e8",
        group_key=lambda r: r["slug"],
        group_label=lambda k: k.title(),
        group_id=lambda k: k,
    )
    hrefs = _hrefs(html)
    assert hrefs, "expected the hub to render review cards"
    dupes = {h: c for h, c in Counter(hrefs).items() if c > 1}
    assert not dupes, f"hub rendered the same review twice: {dupes}"
