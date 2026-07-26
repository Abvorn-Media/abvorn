"""Tests for ProductMatcher."""
from unittest.mock import MagicMock
from abvorn.persuasion.matcher import ProductMatcher, ProductRecommendation
from abvorn.persuasion.context import PersuasionContext
from abvorn.persuasion.stage import BuyingStage


def test_match_returns_products_from_catalog():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"name":"Sony WH-1000XM5","tagline":"Best noise cancelling",'
        '"price_range":"$299-$349","affiliate_url":"https://amzn.to/sony",'
        '"reason_to_buy":"Industry-leading ANC"}]'
    )
    matcher = ProductMatcher(state)
    ctx = PersuasionContext(niche="headphones", persona_name="Alex",
                            buying_stage=BuyingStage.CONSIDERATION,
                            keywords=["noise", "cancelling"], product_intents=["headphones"])
    results = matcher.match(ctx)
    assert len(results) > 0
    assert results[0].name == "Sony WH-1000XM5"


def test_match_handles_empty_catalog():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    matcher = ProductMatcher(state)
    ctx = PersuasionContext(niche="unknown", persona_name="", buying_stage=BuyingStage.AWARENESS)
    results = matcher.match(ctx)
    assert len(results) == 0


def test_match_up_to_three():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"name":"A","tagline":"a","price_range":"$10","affiliate_url":"https://a.com","reason_to_buy":"good"},'
        '{"name":"B","tagline":"b","price_range":"$20","affiliate_url":"https://b.com","reason_to_buy":"better"},'
        '{"name":"C","tagline":"c","price_range":"$30","affiliate_url":"https://c.com","reason_to_buy":"best"},'
        '{"name":"D","tagline":"d","price_range":"$40","affiliate_url":"https://d.com","reason_to_buy":"extra"}]'
    )
    matcher = ProductMatcher(state)
    ctx = PersuasionContext(niche="tv", persona_name="", buying_stage=BuyingStage.CONSIDERATION)
    results = matcher.match(ctx)
    assert len(results) <= 3
