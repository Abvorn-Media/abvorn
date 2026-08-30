from src.review_pdf import _render_rps


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