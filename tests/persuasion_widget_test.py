"""Tests for PersuasionWidget."""
from abvorn.persuasion.widget import PersuasionWidget
from abvorn.persuasion.context import PersuasionContext
from abvorn.persuasion.matcher import ProductRecommendation
from abvorn.persuasion.stage import BuyingStage


def test_widget_renders_html():
    widget = PersuasionWidget()
    ctx = PersuasionContext(niche="headphones", persona_name="", buying_stage=BuyingStage.CONSIDERATION)
    recs = [
        ProductRecommendation(name="Sony WH-1000XM5", tagline="Best ANC", price_range="$349",
                              affiliate_url="https://amzn.to/sony", reason_to_buy="Quietest on market")
    ]
    html = widget.render(ctx, recs)
    assert "Sony" in html
    assert "$349" in html
    assert "amzn.to" in html
    assert "persuasion" in html.lower()


def test_widget_empty_recommendations():
    widget = PersuasionWidget()
    ctx = PersuasionContext(niche="tv", persona_name="", buying_stage=BuyingStage.AWARENESS)
    html = widget.render(ctx, [])
    assert html == ""


def test_widget_includes_json_data():
    widget = PersuasionWidget()
    ctx = PersuasionContext(niche="tv", persona_name="Alex", buying_stage=BuyingStage.DECISION)
    recs = [ProductRecommendation(name="LG C3", tagline="OLED", price_range="$1500",
                                  affiliate_url="https://amzn.to/lg", reason_to_buy="Best OLED")]
    html = widget.render(ctx, recs)
    assert "__ABVORN_PERSUASION" in html
    assert "LG C3" in html
