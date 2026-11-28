"""Regression: product-card copy must be visible, not hidden in an attribute."""
from bs4 import BeautifulSoup

from src.warm_editorial import warm_product_card_html


def _card(description):
    product = {
        "name": "Test Webcam",
        "price": "$19.99",
        "description": description,
        "image": "https://m.media-amazon.com/images/I/test.jpg",
        "url": "https://www.amazon.com/dp/B000000001",
    }
    html = warm_product_card_html(
        product,
        affiliate_url="https://example.com/buy",
        base="https://abvorn.com",
    )
    return BeautifulSoup(html, "html.parser").select_one("div.warm-product-card")


def test_product_card_shows_description_as_visible_summary():
    """Commit f1d98bd0e moved the blurb to data-description and deleted the
    paragraph, so every rebuilt review page shipped cards with no visible copy.
    """
    card = _card("Sharp 1080p video with a privacy cover.")
    summary = card.select_one("p.warm-product-card__summary")
    assert summary is not None, "description is hidden in data-description only"
    assert summary.get_text(strip=True) == "Sharp 1080p video with a privacy cover."


def test_product_card_without_description_renders_no_empty_paragraph():
    card = _card("")
    assert card.select_one("p.warm-product-card__summary") is None
