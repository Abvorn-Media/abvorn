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


def test_hook_platform_count_contexts_use_plural_labels():
    """'I compared 5 tv' / '5 things to check before buying tv' shipped via
    content_intelligence._hook_for_platform because it interpolated the raw
    slug. Count contexts must now use the plural label; one-noun contexts the
    singular noun."""
    import re
    from abvorn.domination.content_intelligence import ContentIntelligence
    ci = ContentIntelligence(rss_path="")
    price = re.search(r"\$\d+", "$500")
    num = re.search(r"\d+", "5")
    x_hooks = ci._hook_for_platform("Best TVs compared", "tv", "x", price, num)
    x_joined = " | ".join(x_hooks)
    assert "I compared 5 TVs" in x_joined
    assert not re.search(r"\b5 tv\b", x_joined, re.IGNORECASE)
    tg_hooks = ci._hook_for_platform("Best TVs compared", "tv", "telegram", price, num)
    tg_joined = " | ".join(tg_hooks)
    assert "check before buying TVs" in tg_joined
    assert "another TV," in tg_joined  # one-noun context stays singular
    assert not re.search(r"\b5 tv\b", tg_joined, re.IGNORECASE)