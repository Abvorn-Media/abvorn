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


def test_url_folder_slug_wins_over_keyword_detection():
    """A dated /reviews/gaming-mice/ file must not be labeled 'webcams' just
    because the title mentions a Logitech brand ("Best Gaming Mice 2026:
    Logitech vs Razer Compared" hit the webcams bucket's 'logitech' keyword and
    shipped 'We compared 4 Webcams' copy linked to a mice page). The URL folder
    is the ground-truth niche id."""
    ci = ContentIntelligence()
    url = "https://abvorn.com/reviews/gaming-mice/best-gaming-mice-2026-logitech-vs-razer-compared-2026-08-17.html"
    title = "Best Gaming Mice 2026: Logitech vs Razer Compared"
    assert ci._niche_for_entry(url, title, title, []) == "gaming-mice"


def test_earbuds_url_is_not_headphones():
    ci = ContentIntelligence()
    url = "https://abvorn.com/reviews/wireless-earbuds/best-wireless-earbuds-2026-haoyuyan-vs-apple-airpods-pro-3-compared-2026-09-01.html"
    title = "Best Wireless Earbuds 2026: HAOYUYAN vs Apple AirPods Pro 3 Compared"
    assert ci._niche_for_entry(url, title, title, []) == "wireless-earbuds"


def test_keyword_fallback_no_longer_calls_logitech_webcams():
    """Without a URL the keyword path is the only signal; a gaming-mouse article
    must land on gaming-mouse even though it mentions the Logitech brand."""
    assert _detect("Best Gaming Mice 2026: Logitech vs Razer Compared") == "gaming-mouse"


def test_review_root_url_falls_back_to_keywords():
    ci = ContentIntelligence()
    title = "Best 4K Monitors 2026: Dell vs LG Compared"
    assert ci._niche_for_entry("https://abvorn.com/reviews/", title, title, []) == "monitor"


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