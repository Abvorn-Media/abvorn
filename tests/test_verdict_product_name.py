"""Regression tests for abvorn.core.verdict.clean_product_name display cleanup."""
from abvorn.core.verdict import clean_product_name


def test_clean_product_name_balances_truncated_paren():
    """Scraper truncation drops the trailing ')' from model parentheticals.

    The unbalanced string is repeated across the verdict card, FAQ, comparison
    table, JSON-LD and affiliate links, so it is closed once at the source.
    """
    out = clean_product_name(
        "LG 65-Inch OLED evo AI 4K C5 Series Smart TV (OLED65C5PUA")
    assert out == "LG 65-Inch OLED evo AI 4K C5 Series Smart TV (OLED65C5PUA)"
    assert out.count("(") == out.count(")")


def test_clean_product_name_closes_multiple_unbalanced_parens():
    assert clean_product_name("Widget (B (C").count("(") == \
        clean_product_name("Widget (B (C").count(")")


def test_clean_product_name_leaves_balanced_names_alone():
    for name in ("Sony WH-1000XM5 (Black)", "Roborock Q7 Max (2023)",
                 "Dreame X50 Omni", "No parens here"):
        assert clean_product_name(name) == name


def test_clean_product_name_normalises_encoded_quotes():
    assert clean_product_name('1.1&quot;&quot; inch') == '1.1" inch'


def test_clean_product_name_handles_empty():
    assert clean_product_name("") == ""
    assert clean_product_name(None) is None
