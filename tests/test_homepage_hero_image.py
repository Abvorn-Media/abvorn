"""Regression test: a hero slide must not fall back to the static category
asset when the niche has a real product photo available.

Bug: build_homepage() picked one review per niche with
``{r["slug"]: r for r in review_list}``, which keeps the LAST entry. The
freshly-written article of the current cycle is appended last by
_overlay_review(), and that overlay has ``image == ""`` whenever the article
shipped with no products (image is only filled inside ``if products:``). So a
product-less article hijacked its whole niche slide and the hero rendered the
generic stock asset -- e.g. assets/hero/laptops.jpg, a keyboard close-up -- next
to product-shot slides, instead of the laptop product photo already in that
niche.

Fix: when choosing the per-niche review, skip entries that carry no image, so a
product-less overlay can never displace a review that has a real photo. The
static asset is still used when the niche genuinely has no product image.
"""
import re

from src.deployment import build_homepage

SLUGS = ["tv", "laptops"]


def _state():
    return {
        "niches": [
            {"name": "Tv", "slug": "tv", "posts": 1},
            {"name": "Laptops", "slug": "laptops", "posts": 2},
        ]
    }


def _review(slug, image, name="Product", updated="2026-09-01"):
    return {
        "slug": slug,
        "name": slug.title(),
        "title": f"{slug.title()} review",
        "updated": updated,
        "rel": f"/reviews/{slug}/a-review.html",
        "snippet": "s",
        "image": image,
        "score": 8.4,
        "breakdown": {},
        "label": "Excellent",
        "product_name": name,
    }


def _hero_slides(html):
    """(alt, src) per hero slide, in render order."""
    return re.findall(
        r'<div class="hero-slide[^"]*"><img src="([^"]+)" alt="([^"]+)"', html)


def test_productless_overlay_does_not_hijack_the_hero_slide():
    reviews = [
        _review("tv", "https://m.media-amazon.com/tv.jpg", "Sony TV"),
        _review("laptops", "https://m.media-amazon.com/laptop.jpg",
                "Lenovo ThinkPad"),
        # This is the article written this cycle. No products -> no image,
        # exactly what _overlay_review() produces for a product-less article.
        _review("laptops", "", "Best Laptops 2026", updated="2026-09-30"),
    ]

    html = build_homepage(_state(), "", reviews=reviews, base="")
    srcs = {alt: src for src, alt in _hero_slides(html)}

    assert srcs["Tv"] == "https://m.media-amazon.com/tv.jpg"
    # Must show the laptop product photo, not the static category asset.
    assert srcs["Laptops"] == "https://m.media-amazon.com/laptop.jpg"
    assert "/assets/hero/laptops.jpg" not in html


def test_static_asset_still_used_when_niche_has_no_product_image():
    """The fallback is only a fallback: with no product photo anywhere in the
    niche, the static category asset is still correct."""
    reviews = [
        _review("tv", "https://m.media-amazon.com/tv.jpg", "Sony TV"),
        _review("laptops", "", "Best Laptops 2026"),
    ]

    html = build_homepage(_state(), "", reviews=reviews, base="")
    srcs = {alt: src for src, alt in _hero_slides(html)}

    assert srcs["Tv"] == "https://m.media-amazon.com/tv.jpg"
    assert srcs["Laptops"].endswith("/assets/hero/laptops.jpg")


def test_hero_slide_keeps_verdict_from_the_review_it_photographs():
    """The scorecard must belong to the same review as the photo, not to a
    product-less overlay that has no verdict data."""
    reviews = [
        _review("tv", "https://m.media-amazon.com/tv.jpg", "Sony TV"),
        _review("laptops", "https://m.media-amazon.com/laptop.jpg",
                "Lenovo ThinkPad", updated="2026-09-01"),
        _review("laptops", "", "Best Laptops 2026", updated="2026-09-30"),
    ]

    html = build_homepage(_state(), "", reviews=reviews, base="")

    slide = re.search(r'<div class="hero-slide[^"]*">.*?</div>', html, re.S)
    assert slide, "expected a hero slide"
    text = slide.group(0)
    assert "assets/hero/laptops.jpg" not in text
