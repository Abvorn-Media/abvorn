from bs4 import BeautifulSoup

from src.review_pdf import _refine, _render_rps


def test_render_rps_tolerates_missing_price():
    primary = {"name": "A", "scores": {"performance": 8, "value": 7, "quality": 6}, "price": None}
    alt = {"name": "B", "scores": {"performance": 9, "value": 8, "quality": 9}, "price": None}
    html = _render_rps(primary, [primary, alt])
    assert "rps-container" in html
    assert "<span class=\"rps-alt-price\"></span>" in html


def test_render_rps_escapes_prices():
    primary = {"name": "<A>", "scores": {"performance": 8, "value": 7, "quality": 6}, "price": None}
    alt = {"name": "B", "scores": {"performance": 9, "value": 8, "quality": 9}, "price": "$199.99"}
    html = _render_rps(primary, [primary, alt])
    assert "$199.99" in html
    assert "<A>" not in html


def test_refine_does_not_duplicate_a_visible_product_summary():
    """Print used to re-add the blurb that web cards stopped rendering; once
    the paragraph is restored it must not be emitted twice in the PDF.
    """
    desc = "Sharp 1080p video with a privacy cover."
    html = (
        '<html><body><article><div class="warm-product-card" '
        f'data-description="{desc}">'
        '<div class="warm-product-card__price">$19.99</div>'
        f'<p class="warm-product-card__summary">{desc}</p>'
        '</div></article></body></html>'
    )
    soup = BeautifulSoup(html, "html.parser")
    art = _refine(soup, soup.select_one("article"))
    assert len(art.select(".warm-product-card__summary")) == 1