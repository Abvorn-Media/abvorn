"""Regression tests for prose-safety in generated article copy.

Three real defects these lock down:
  1. the URL slug leaked into user-facing titles ("Best robot-vacuums 2026"),
  2. count nouns stayed plural ("the best robot vacuums", "a good tv"),
  3. the FAQ quoted the hardcoded "$50" price floor for niches absent from
     PRICE_FLOORS -- an OLED TV guide telling readers to expect $50.
"""
import pytest

from src.article_design import (
    PRICE_FLOORS,
    build_faq,
    catalog_price_floor,
    niche_display,
    price_floor_for,
    singularize,
)


@pytest.mark.parametrize("raw,expected", [
    ("robot-vacuums", "Robot Vacuums"),
    ("tv", "TV"),
    ("tv", "TV"),
    ("4k-monitors", "4K Monitors"),
    ("gaming-mice", "Gaming Mice"),
    ("Robot Vacuums", "Robot Vacuums"),
    ("wireless-headphones", "Wireless Headphones"),
    ("", ""),
])
def test_niche_display_never_returns_a_slug(raw, expected):
    out = niche_display(raw)
    assert out == expected
    assert "-" not in out or raw == ""


@pytest.mark.parametrize("raw,expected", [
    ("robot vacuums", "robot vacuum"),
    ("gaming mice", "gaming mouse"),
    ("tv", "tv"),
    ("laptops", "laptop"),
    ("fitness trackers", "fitness tracker"),
    ("4k monitors", "4k monitor"),
    ("robot vacuum", "robot vacuum"),
    ("", ""),
])
def test_singularize(raw, expected):
    assert singularize(raw) == expected


def test_price_floor_default_is_not_hardcoded_for_new_niches():
    # robot-vacuums/tv were missing from PRICE_FLOORS, so they silently
    # inherited the "$50" default. The default itself is fine; build_faq is
    # responsible for not using it when the catalogue knows better.
    assert price_floor_for("robot-vacuums") == "50"
    assert "robot-vacuums" not in PRICE_FLOORS
    assert "tv" not in PRICE_FLOORS


def test_catalog_price_floor_uses_cheapest_real_price():
    products = [
        {"name": "A", "price": "$199.99"},
        {"name": "B", "price": "$99.99"},
        {"name": "C", "price": "$249.00"},
    ]
    assert catalog_price_floor(products, "50") == "99.99"


def test_catalog_price_floor_formats_whole_numbers():
    assert catalog_price_floor([{"price": "$300"}], "50") == "300"
    assert catalog_price_floor([{"price": 130}], "50") == "130"


def test_catalog_price_floor_falls_back_when_prices_missing():
    assert catalog_price_floor([{"name": "A"}], "50") == "50"
    assert catalog_price_floor([], "300") == "300"
    assert catalog_price_floor(None, "300") == "300"


def test_build_faq_never_advertises_a_price_the_catalogue_does_not_have():
    products = [
        {"name": "iRobot Roomba 115X Combo", "price": "$199.99"},
        {"name": "Shark AI Ultra", "price": "$249.99"},
    ]
    faq_html, questions = build_faq(
        "robot-vacuums", "Robot Vacuums", products, "Roomba", "50",
    )
    spend_q, spend_a = next(
        (q, a) for q, a in questions if "spend" in q.lower()
    )
    assert "$50" not in spend_a, "FAQ quoted the default floor, not the catalogue"
    assert "$99" in spend_a or "$199" in spend_a
    # plural is right for the generic question, singular for the count noun
    assert spend_q.endswith("robot vacuums?")
    assert "a genuinely good robot vacuum for" in spend_a
    assert "a genuinely good robot vacuums" not in spend_a
    assert "$50" not in faq_html


def test_build_faq_singularizes_the_best_question():
    products = [{"name": "LG C5 OLED", "price": "$1299.99"}]
    _, questions = build_faq("tv", "TV", products, "LG C5", "50")
    best_q, _ = next((q, a) for q, a in questions if "What is the best" in q)
    assert best_q == "What is the best TV?"
    assert "TVs" not in best_q


def test_build_faq_tv_price_comes_from_catalogue_not_default():
    products = [
        {"name": "LG C5 65 OLED", "price": "$1299.99"},
        {"name": "Sony Bravia XR", "price": "$1699.99"},
    ]
    _, questions = build_faq("tv", "TV", products, "LG C5", "50")
    spend_a = next(a for q, a in questions if "spend" in q.lower())
    assert "$50" not in spend_a
    assert "$1299.99" in spend_a
