import pytest
from abvorn.exploder.adapters import (
    adapt_for_x, adapt_for_linkedin, adapt_for_tiktok,
    adapt_for_instagram, adapt_for_pinterest, adapt_for_medium
)

ANCHOR = {
    "post_title": "Best Wireless Headphones for Commuters in 2026",
    "intro": "<p>Your commute should be your sanctuary.</p>",
    "article_html": "<p>After testing 20+ pairs, here are our top picks.</p><h2>1. Sony WH-1000XM6</h2><p>Best noise cancellation.</p><h2>2. Bose QC Ultra</h2><p>Best comfort.</p>",
    "meta_description": "Tired of tangled wires? We tested 20+ headphones. Here are the best.",
    "tags": ["wireless", "headphones", "commuter"],
    "niche": "wireless headphones",
}


def test_x_thread():
    result = adapt_for_x(ANCHOR)
    assert len(result) >= 3
    assert all(isinstance(t, str) for t in result)


def test_linkedin_article():
    result = adapt_for_linkedin(ANCHOR)
    assert "title" in result
    assert "body" in result
    assert len(result["body"]) > 100


def test_tiktok_script():
    result = adapt_for_tiktok(ANCHOR)
    assert "hook" in result
    assert "body" in result
    assert "cta" in result


def test_instagram_carousel():
    result = adapt_for_instagram(ANCHOR)
    assert len(result) >= 3
    assert all(isinstance(s, str) for s in result)


def test_pinterest_pin():
    result = adapt_for_pinterest(ANCHOR)
    assert "title" in result
    assert "description" in result


def test_medium_article():
    result = adapt_for_medium(ANCHOR)
    assert len(result) > 100