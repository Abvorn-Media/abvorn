"""Tests for CrossLinker — contextual sister-site links."""
from unittest.mock import MagicMock
from abvorn.deploy.crosslinker import CrossLinker
from abvorn.sites.model import Site


def test_crosslinker_no_sister_sites():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"site_id":"s1","slug":"tech","name":"Tech","tagline":"",'
        '"logo_text":"T","logo_icon":"T","primary_color":"#000",'
        '"secondary_color":"#fff","voice_rules":{},"niches":["tv","laptop"],'
        '"domain":"","status":"active","created_at":""}]'
    )
    cl = CrossLinker(state)
    result = cl.inject_links("<p>Some content</p>", "tv")
    assert result == "<p>Some content</p>"

def test_crosslinker_adds_link_when_sister_exists():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"site_id":"s1","slug":"tech","name":"Tech","tagline":"",'
        '"logo_text":"T","logo_icon":"T","primary_color":"#000",'
        '"secondary_color":"#fff","voice_rules":{},"niches":["tv"],'
        '"domain":"","status":"active","created_at":""},'
        '{"site_id":"s2","slug":"home","name":"Home","tagline":"",'
        '"logo_text":"H","logo_icon":"H","primary_color":"#000",'
        '"secondary_color":"#fff","voice_rules":{},"niches":["vacuum"],'
        '"domain":"","status":"active","created_at":""}]'
    )
    cl = CrossLinker(state)
    result = cl.inject_links("<p>Great for your home.</p>", "tv")
    assert len(result) > len("<p>Great for your home.</p>")

def test_crosslinker_graceful_failure():
    state = MagicMock()
    state.get_meta.side_effect = Exception("DB error")
    cl = CrossLinker(state)
    result = cl.inject_links("<p>Content</p>", "tv")
    assert result == "<p>Content</p>"
