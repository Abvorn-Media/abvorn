"""Tests for the product-aware social pipeline:
- product_assets: JSON-LD parsing, slug resolution, name cleaning
- instagram_cards: 1080x1350 composition (no black bars)
- viral_script_generator: product-aware carousel copy
- cinematic_filter: cover-crop resize (no letterboxing)
"""

import json
from pathlib import Path

from abvorn.domination import (
    viral_script_generator as vsg,
    product_assets as pa,
)

SAMPLE_HTML = """<!DOCTYPE html>
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
 {"@type":"BreadcrumbList","itemListElement":[]},
 {"@type":"FAQPage","mainEntity":[]},
 {"@type":"Product","name":"Logitech G305 Lightspeed Wireless Gaming Mouse",
  "image":"https://m.media-amazon.com/images/I/51sg9BLSMTL._AC_SL1500_.jpg",
  "offers":{"@type":"Offer","priceCurrency":"USD","price":"29.99",
            "url":"https://www.amazon.com/dp/B07CMS5Q6P?tag=x-20"}}
]}
</script>
</head><body></body></html>
"""


def test_slug_from_url_plain():
    assert pa.slug_from_url("https://abvorn.com/wireless-headphones/") == "wireless-headphones"
    assert pa.slug_from_url("https://abvorn.com") == ""
    assert pa.slug_from_url("") == ""


def test_slug_from_url_reviews_nested():
    assert pa.slug_from_url("https://abvorn.com/reviews/gaming-mice/") == "gaming-mice"


def test_json_ld_product_parse():
    products = pa._parse_json_ld_products(SAMPLE_HTML)
    assert len(products) == 1
    p = products[0]
    assert p["name"] == "Logitech G305 Lightspeed Wireless Gaming Mouse"
    assert p["price"] == "29.99"
    assert "_SL1500_" in p["image"]
    assert "tag=x-20" in p["url"]


def test_json_ld_ignores_other_schema_types():
    html = SAMPLE_HTML.replace('"@type":"Product"', '"@type":"Article"')
    assert pa._parse_json_ld_products(html) == []


def test_clean_product_name_truncates_branding():
    long_name = ("HyperX Cloud Stinger 2 Core Wireless Gaming Headset for "
                 "PC with 20+ Hour Battery Life and 40mm Drivers")
    cleaned = pa.clean_product_name(long_name)
    assert len(cleaned) <= 52
    assert cleaned.endswith("…")


def test_upgrade_image_to_hires():
    src = "https://m.media-amazon.com/images/I/51sg9BLSMTL._AC_UY654_QL65_.jpg"
    assert pa._upgrade_image(src).endswith("_AC_SL1500_.jpg")


def test_format_price():
    assert pa._format_price("29.99") == "$29.99"
    assert pa._format_price("$19.99") == "$19.99"
    assert pa._format_price("") == "Check price"


def test_product_aware_carousel_slides():
    gen = vsg.ViralScriptGenerator()
    post = {"title": "Best Gaming Mice", "niche": "gaming-mice", "summary": "",
            "url": "https://abvorn.com/gaming-mice/", "hooks": {}}
    products = [
        {"name": "Logitech G305", "price": "$29.99", "role": "Overall Winner"},
        {"name": "Razer Viper Mini", "price": "$39.99", "role": "Runner-Up"},
    ]
    out = gen.generate(post, platforms=["instagram"], products=products)
    slides = out["instagram"]["script"]
    assert isinstance(slides, list)
    joined = "\n".join(slides)
    assert "Logitech G305" in joined
    assert "$29.99" in joined
    assert "Overall Winner" in joined
    # humanized niche, not the raw slug
    assert "gaming-mice" not in joined
    assert "Gaming mice" in joined
    # honest: no physical-testing claims on the carousel
    for banned in ("we tested", "hands-on", "in our lab"):
        assert banned.lower() not in joined.lower()


def test_ig_card_is_1080x1350_with_no_padding(tmp_path, monkeypatch):
    from abvorn.domination import instagram_cards as igc

    # Build a realistic wide (landscape) product photo → card must still be 4:5.
    from PIL import Image
    wide = tmp_path / "src.jpg"
    Image.new("RGB", (1600, 1000), (200, 120, 120)).save(wide)

    def fake_download(product):
        return str(wide)

    monkeypatch.setattr(igc, "_download_image", fake_download)
    product = {
        "name": "Logitech G305",
        "price": "$29.99",
        "role": "Overall Winner",
        "index": 0,
    }
    out = igc.compose_product_card(product, "Overall Winner", tmp_path / "card.jpg")
    assert out
    img = Image.open(out)
    assert img.size == (1080, 1350)


def test_full_carousel_compose(tmp_path, monkeypatch):
    from abvorn.domination import instagram_cards as igc
    from PIL import Image
    square = tmp_path / "src2.jpg"
    Image.new("RGB", (1500, 1500), (30, 60, 200)).save(square)
    monkeypatch.setattr(igc, "_download_image", lambda p: str(square))

    products = [
        {"name": "Logitech G305", "price": "$29.99", "role": "Overall Winner", "index": 0},
        {"name": "Razer Viper Mini", "price": "$39.99", "role": "Runner-Up", "index": 1},
    ]
    paths = igc.compose_carousel(products, "gaming-mice", "Best Gaming Mice",
                                 "https://abvorn.com/gaming-mice/", cache_dir=tmp_path)
    assert len(paths) == 3  # 2 product cards + CTA
    for p in paths:
        assert Image.open(p).size == (1080, 1350)


def test_cinematic_resize_cover_crops_wide_image(tmp_path):
    from abvorn.domination.cinematic_filter import CinematicFilter
    from PIL import Image
    wide = tmp_path / "wide.jpg"
    Image.new("RGB", (2000, 700), (90, 90, 90)).save(wide)
    out = tmp_path / "ig.jpg"
    done = CinematicFilter().resize_for_platform(str(wide), "instagram", str(out))
    assert done
    img = Image.open(done)
    assert img.size == (1080, 1350)


def test_cinematic_resize_keeps_existing_4x5_untouched(tmp_path):
    from abvorn.domination.cinematic_filter import CinematicFilter
    from PIL import Image
    exact = tmp_path / "card.jpg"
    Image.new("RGB", (1080, 1350), (10, 10, 10)).save(exact)
    out = tmp_path / "out.jpg"
    done = CinematicFilter().resize_for_platform(str(exact), "instagram", str(out))
    assert done
    assert Image.open(done).size == (1080, 1350)


def test_load_products_from_html(tmp_path, monkeypatch):
    page = tmp_path / "index.html"
    page.write_text(SAMPLE_HTML, encoding="utf-8")
    monkeypatch.setattr(pa, "review_page_candidates", lambda slug: [page])
    monkeypatch.setattr(pa, "CACHE_FILES", [tmp_path / "cache.json"])
    products = pa.load_products_for_niche("gaming-mice")
    assert len(products) >= 1
    p = products[0]
    assert p["name"].startswith("Logitech")
    assert p["price"] == "$29.99"
    assert p["role"] == "Overall Winner"
    assert p["image"].endswith("_AC_SL1500_.jpg")