"""Regression tests for niche detection in the domination content pipeline."

A bare '4k' keyword in the tv bucket (-tv-/-video) hijacked every
4K-monitor article before the -monitor- bucket was ever checked. That sent
monitor products out to live social with TV persona copy ("We compared 4 Tv").
The tv bucket must only match TV-adjacent phrases, never a bare -4k-.
"""
from abvorn.domination.content_intelligence import ContentIntelligence


def _detect(title, tags=()):
    return ContentIntelligence()._detect_niche(title, title, list(tags))


def test_4k_monitor_article_is_not_tv():
    title = "Best 4K Monitors 2026: Dell vs LG Compared"
    assert _detect(title) == "monitor"


def test_4k_monitor_buying_guide_is_not_tv():
    title = "The Ultimate 4K Monitor Buying Guide: Compare Top Picks"
    assert _detect(title) == "monitor"


def test_generic_monitor_plural_heading_is_monitor():
    title = "Best 4k-Monitors 2026: Dell S2725QS, S2725QC & LG 27UP650K-W Compared"
    assert _detect(title) == "monitor"


def test_4k_tv_still_recognized_as_tv():
    assert _detect("Best 4K TVs 2026: Top Picks") == "tv"
    assert _detect("Best 4K Smart TV for 2026") == "tv"


def test_tv_with_bare_word_matches_tv():
    assert _detect("Best TV deals 2026") == "tv"