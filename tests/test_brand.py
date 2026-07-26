"""Tests for the brand soul — every content check against Abvorn's identity."""

from abvorn.brand import (
    check_text, check_soul, format_voice_rules,
    DISCLOSURE_BANNER, TRUST_SIGNAL, AFFILIATE_FOOTER,
    MISSION, VISION, MOTTO, get_disclosure_html,
)


def test_banned_phrase_detected():
    violations = check_text("This is a game-changer for productivity")
    assert any("game-changer" in v for v in violations)


def test_banned_filler_detected():
    violations = check_text("It is very good and really useful")
    assert any("very" in v for v in violations)
    assert any("really" in v for v in violations)


def test_banned_pattern_detected():
    violations = check_text("From Acme, the makers of WidgetPro")
    assert len(violations) > 0


def test_clean_text_passes():
    violations = check_text("This headphone weighs 8.2 oz and costs $49.")
    assert len(violations) == 0


def test_soul_check_text_field():
    result = check_soul("write_post", {"text": "game-changer headphones"})
    assert not result["pass"]
    assert len(result["violations"]) > 0


def test_soul_check_title_field():
    result = check_soul("write_post", {"title": "Best very good headphones"})
    assert not result["pass"]


def test_soul_check_clean_passes():
    result = check_soul("write_post", {
        "title": "Best Wireless Headphones for Commuters",
        "text": "We tested 12 models. The Sony WH-1000XM5 weighs 254g and costs $349.",
    })
    assert result["pass"]


def test_voice_rules_formatted():
    rules = format_voice_rules()
    assert "contractions" in rules
    assert "No adverbs" in rules
    assert "Numbers everywhere" in rules


def test_disclosure_templates():
    assert "earn a commission" in DISCLOSURE_BANNER
    assert "trust Abvorn" in TRUST_SIGNAL
    assert "Amazon Associate" in AFFILIATE_FOOTER


def test_disclosure_html():
    html = get_disclosure_html()
    assert "trust Abvorn" in html
    assert "Amazon Associate" in html
    assert "disclosure" in html


def test_identity_constants():
    assert "buy with confidence" in MISSION
    assert "product recommendation" in VISION
    assert MOTTO == "Buy with confidence."