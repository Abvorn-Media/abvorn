import pytest
from abvorn.exploder.email import generate_lead_magnet, generate_sequence


def test_lead_magnet_generation():
    """Should generate a lead magnet from content."""
    content = {
        "post_title": "Best Wireless Headphones",
        "niche": "wireless headphones",
        "tags": ["wireless", "headphones"]
    }
    magnet = generate_lead_magnet(content)
    assert "title" in magnet
    assert "description" in magnet
    assert "content" in magnet
    assert len(magnet["title"]) > 0


def test_email_sequence():
    """Should generate a 5-7 email sequence."""
    persona = {"name": "Marcus the Commuter", "psychology": {"anxieties": ["battery dying"]}}
    content = {"post_title": "Best Wireless Headphones for Commuters", "niche": "wireless headphones"}
    sequence = generate_sequence(content, persona)
    assert len(sequence) >= 5
    assert "day" in sequence[0]
    assert "subject" in sequence[0]
    assert "body" in sequence[0]
    assert sequence[0]["day"] == 1
    assert sequence[-1]["day"] >= 30