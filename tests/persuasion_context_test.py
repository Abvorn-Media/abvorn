"""Tests for ContextParser."""
from abvorn.persuasion.context import ContextParser, PersuasionContext
from abvorn.persuasion.stage import BuyingStage


def test_parse_returns_context_with_keywords():
    parser = ContextParser()
    content = {"title": "Best Noise Cancelling Headphones", "article_html": "<p>Top 10 noise cancelling headphones reviewed...</p>", "niche": "headphones"}
    persona = {"name": "Alex", "traits": ["tech-savvy", "audio-lover"]}
    ctx = parser.parse(content, persona)
    assert isinstance(ctx, PersuasionContext)
    assert ctx.niche == "headphones"
    assert ctx.persona_name == "Alex"
    assert ctx.buying_stage == BuyingStage.CONSIDERATION
    assert len(ctx.keywords) > 0


def test_parse_without_persona():
    parser = ContextParser()
    content = {"title": "Buy Cheap Monitors", "article_html": "<p>Where to find monitor deals...</p>", "niche": "monitor"}
    ctx = parser.parse(content, None)
    assert ctx.persona_name == ""
    assert ctx.buying_stage == BuyingStage.DECISION
