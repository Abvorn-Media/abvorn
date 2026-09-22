"""Tests for the pre-publish mojibake guard."""
import pytest

from src.deployment import (
    find_mojibake,
    check_encoding,
    repair_mojibake,
    verify_page,
)


def test_clean_utf8_passes():
    html = "<p>Serious performance at a serious price — worth it if you use it daily.</p>"
    assert find_mojibake(html) == []
    assert check_encoding(html) is True


def test_clean_curly_quotes_pass():
    html = "<p>“Best overall” — John’s pick</p>"
    assert find_mojibake(html) == []


def test_clean_box_drawing_passes():
    html = "/* ══════ Footer category columns ══════ */"
    assert find_mojibake(html) == []


def test_emoji_passes():
    html = "<p>Icon \U0001f50c works fine</p>"
    assert find_mojibake(html) == []


def test_cp1252_double_encoded_emdash_caught():
    # UTF-8 bytes of "—" decoded as cp1252, re-encoded as UTF-8
    text = "price \u2014 worth".encode("utf-8")
    corrupted = text.decode("cp1252").encode("utf-8").decode("utf-8")
    hits = find_mojibake(corrupted)
    assert hits


def test_latin1_fallback_variant_caught():
    # The mixed codec variant seen in the wild: U+2550 separator through
    # cp1252-with-latin1-fallback -> bytes c3 a2 e2 80 a2 c2 90
    corrupted = "/* \u00e2\u2022\u0090\u00e2\u2022\u0090 */"
    assert find_mojibake(corrupted)


def test_rdquo_latin1_fallback_caught():
    corrupted = "thicky \u00e2\u20ac\u009d sound"
    assert find_mojibake(corrupted)


def test_check_encoding_raises_on_mojibake():
    corrupted = "price \u00e2\u20ac\u009d worth"
    with pytest.raises(ValueError, match="Mojibake detected"):
        check_encoding(corrupted, label="test page")


def test_check_encoding_passes_clean():
    assert check_encoding("No corruption here — just fine text.", label="test") is True


def test_repair_mojibake_restores_clean_text():
    original = "price \u2014 worth, John\u2019s pick"
    corrupted = original.encode("utf-8").decode("cp1252").encode("utf-8").decode("utf-8")
    assert corrupted != original
    repaired = repair_mojibake(corrupted)
    assert repaired == original
    assert find_mojibake(repaired) == []


def test_repair_mojibake_leaves_clean_text_alone():
    clean = "<p>Serious performance at a serious price — worth it daily.</p>"
    assert repair_mojibake(clean) == clean


def test_repair_mojibake_fixes_box_drawing_separator():
    corrupted = "/* \u00e2\u2022\u0090\u00e2\u2022\u0090 */"
    repaired = repair_mojibake(corrupted)
    assert "\u2550" in repaired
    assert find_mojibake(repaired) == []


def test_repair_mojibake_fixes_rdquo_fallback():
    corrupted = "thicky \u00e2\u20ac\u009d sound"
    repaired = repair_mojibake(corrupted)
    assert "\u201d" in repaired
    assert find_mojibake(repaired) == []


def test_verify_page_blocks_mojibake():
    html = (
        '<div id="abvorn-rps-data"></div>'
        '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
        '<div class="av-bar-row"></div>'
        "which mouse should I buy? \u00e2\u20ac\u009d</p>"
    )
    with pytest.raises(ValueError, match="Mojibake"):
        verify_page(html)


def test_verify_page_passes_when_clean():
    html = (
        '<div id="abvorn-rps-data"></div>'
        '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
        '<div class="av-bar-row"></div>'
        "which mouse should I buy? \u201d</p>"
    )
    assert verify_page(html) is True


def test_sanitizer_purges_placeholder_asin():
    from src.article_design import sanitize_article_html
    html = (
        '<p>The <a href="https://www.amazon.com/dp/B0BXYZ123" '
        'rel="nofollow sponsored">LG G3 OLED</a> features:</p>'
    )
    clean = sanitize_article_html(html)
    assert "amazon.com/dp" not in clean
    assert "LG G3 OLED" in clean


def test_sanitizer_keeps_real_asin():
    from src.article_design import sanitize_article_html
    html = '<p><a href="https://www.amazon.com/dp/B0H69PVMKC" rel="sponsored">JBL</a></p>'
    assert sanitize_article_html(html) == html


def test_sanitizer_strips_empty_tag_clause():
    from src.article_design import sanitize_article_html
    html = '<a href="https://www.amazon.com/s?k=wireless+headphones&amp;tag=">Shop</a>'
    clean = sanitize_article_html(html)
    assert "/s?k=wireless+headphones&amp;tag=" not in clean
    assert "/s?k=wireless+headphones\"" in clean


def test_enforce_amazon_tag_blankets_in_body_ctas():
    from src.article_design import enforce_amazon_tag
    html = '<a class="btn" href="https://www.amazon.com/s?k=wireless+headphones">Shop all</a>'
    tagged = enforce_amazon_tag(html, "viraltestco-20")
    assert "tag=viraltestco-20" in tagged
    assert "&amp;tag=viraltestco-20" in tagged


def test_enforce_amazon_tag_leaves_already_tagged():
    from src.article_design import enforce_amazon_tag
    html = '<a href="https://www.amazon.com/dp/B0H69PVMKC?tag=x">ok</a>'
    assert enforce_amazon_tag(html, "viraltestco-20") == html
