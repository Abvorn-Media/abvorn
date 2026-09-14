"""Tests for the product-aware social pipeline:
- product_assets: JSON-LD parsing, slug resolution, name cleaning
- instagram_cards: 1080x1350 composition (no black bars)
- viral_script_generator: product-aware carousel copy
- cinematic_filter: cover-crop resize (no letterboxing)
"""

import json
import re
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


def test_slug_from_url_reviews_dated_file():
    # Real RSS feed links: /reviews/<niche>/<article>-<date>.html
    assert (
        pa.slug_from_url(
            "https://abvorn.com/reviews/smart-home/"
            "best-smart-home-devices-2026-echo-show-15-echo-show-5-"
            "sujeet-night-light-compared-2026-08-26.html"
        )
        == "smart-home"
    )
    assert (
        pa.slug_from_url(
            "https://abvorn.com/reviews/4k-monitors/"
            "best-4k-monitors-2026-dell-s2725qs-s2725qc-"
            "lg-27up650k-w-compared-2026-08-07.html"
        )
        == "4k-monitors"
    )


def test_review_page_candidates_matches_dated_flat_file(tmp_path, monkeypatch):
    # The site publishes dated flat files inside reviews/<niche>/ rather than
    # only an index.html — the candidate list must surface them so the
    # domination cycle can resolve real product photos from the article the
    # RSS feed points at.
    dated_dir = tmp_path / "reviews" / "webcams"
    dated_dir.mkdir(parents=True)
    dated = dated_dir / "top-3-webcams-2026-crisp-video-smooth-streaming-2026-09-08.html"
    dated.write_text(SAMPLE_HTML, encoding="utf-8")
    monkeypatch.setattr(pa, "_review_roots", lambda: [tmp_path])

    cands = pa.review_page_candidates(dated.name)
    assert dated in cands
    html = pa.load_review_html(dated.name)
    assert "application/ld+json" in html


def test_load_products_from_dated_flat_file(tmp_path, monkeypatch):
    # End-to-end: the exact slug the feed URL yields must resolve real products.
    dated_dir = tmp_path / "reviews" / "webcams"
    dated_dir.mkdir(parents=True)
    dated = dated_dir / "top-3-webcams-2026-crisp-video-smooth-streaming-2026-09-08.html"
    dated.write_text(SAMPLE_HTML, encoding="utf-8")
    monkeypatch.setattr(pa, "_review_roots", lambda: [tmp_path])
    monkeypatch.setattr(pa, "CACHE_FILES", [tmp_path / "cache.json"])

    slug = pa.slug_from_url(
        "https://abvorn.com/reviews/webcams/"
        "top-3-webcams-2026-crisp-video-smooth-streaming-2026-09-08.html"
    )
    assert slug == "webcams"
    products = pa.load_products_for_niche(dated.name)
    assert len(products) >= 1
    assert products[0]["name"].startswith("Logitech")
    assert "_SL1500_" in products[0]["image"]


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


def test_persona_aware_carousel_uses_buyer_pain_and_hope():
    gen = vsg.ViralScriptGenerator()
    post = {"title": "Best Gaming Mice", "niche": "gaming-mice", "summary": "",
            "url": "https://abvorn.com/gaming-mice/", "hooks": {}}
    products = [{"name": "Logitech G305", "price": "$29.99", "role": "Overall Winner"}]
    persona = {
        "name": "Competitive Calvin",
        "psychology": {
            "anxieties": ["missed flick shots", "sensor jitter"],
            "hopes": ["sub-50g wireless", "flawless tracking"],
        },
    }
    out = gen.generate(post, platforms=["instagram"], products=products, persona=persona)
    insta = out["instagram"]
    assert insta["persona"] == "Competitive Calvin"
    slides = insta["script"]
    joined = "\n".join(slides)
    # persona pain/hope phrases surface in the copy
    assert "missed flick shots" in insta["hook"] or "sub-50g wireless" in insta["hook"]
    assert "missed flick shots" in joined or "flawless tracking" in joined
    # still product first + honest
    assert "Logitech G305" in joined
    for banned in ("we tested", "hands-on", "in our lab"):
        assert banned.lower() not in joined.lower()


def test_persona_hook_matches_niche_slug_via_normalization():
    from abvorn.persona.engine import PersonaEngine
    personas = PersonaEngine().discover_personas("4k-monitors")
    # slug-normalized lookup hits the display-name template bank
    assert personas and personas[0]["name"] == "Creative Director Chloe"


def test_humanize_niche_labels_and_brand_case():
    assert vsg._humanize_niche("smart-home") == "Smart home devices"
    assert vsg._humanize_niche("smart_home") == "Smart home devices"
    assert vsg._humanize_niche("Smart-Home") == "Smart home devices"
    assert vsg._humanize_niche("4k-monitors") == "4K monitors"
    assert vsg._humanize_niche("gaming-mice") == "Gaming mice"


def test_humanize_niche_single_word_slugs_are_plural():
    """'We compared 4 Monitor' shipped live because single-word content-intel
    slugs ('tv', 'monitor', 'laptop', ...) humanized to bare singulars. Every
    one must now render as a plural, countable noun."""
    assert vsg._humanize_niche("tv") == "TVs"
    assert vsg._humanize_niche("monitor") == "Monitors"
    assert vsg._humanize_niche("laptop") == "Laptops"
    assert vsg._humanize_niche("webcam") == "Webcams"
    assert vsg._humanize_niche("headphone") == "Headphones"
    assert vsg._humanize_niche("robot-vacuum") == "Robot vacuums"
    assert vsg._humanize_niche("gaming-mouse") == "Gaming mice"
    assert vsg._humanize_niche("wireless-chargers") == "Wireless chargers"
    assert vsg._humanize_niche("mechanical-keyboard") == "Mechanical keyboards"
    # the TypeError family: plural nouns ending in 's' must not double up
    assert vsg._humanize_niche("wireless-mice") == "Wireless mice"


def test_generate_hooks_count_context_uses_plural():
    """'I compared 10 tv' would have shipped via the legacy HOOK_TEMPLATES
    (raw slug into a count template) even after _humanize_niche was fixed.
    Count contexts get the plural label, singular-noun templates do not."""
    gen = vsg.ViralScriptGenerator()
    hooks = gen._generate_hooks("Best TVs", "tv", "$500", "5", "Sony", "curiosity")
    joined = " | ".join(hooks)
    assert "I compared 10 TVs" in joined
    assert not re.search(r"\bcompared 10 tv\b", joined, re.IGNORECASE)
    # singular-noun templates stay singular ("The TV you're using is wrong")
    assert "The TV you're using is probably wrong for you." in joined
    assert "The TVs you\u2019re" not in joined


def test_niche_for_template_edges():
    assert vsg._niche_for_template("I compared 10 {niche} so you don't have to.", "monitor") == "Monitors"
    assert vsg._niche_for_template("The {niche} you're using is wrong.", "monitor") == "Monitor"
    assert vsg._niche_for_template("{num_steps} things to check before buying {niche}.", "smart-home") == "Smart home devices"
    assert vsg._singular_niche_label("Gaming mice") == "Gaming mouse"
    assert vsg._singular_niche_label("Smart home devices") == "Smart home device"


def test_persona_hook_keeps_brand_case_and_niche_noun():
    """The exact regression that posted broken copy: persona pain 'Matter
    certification delays' + niche 'smart-home' must render as readable copy
    (brand cased, countable noun after the count)."""
    gen = vsg.ViralScriptGenerator()
    post = {"title": "Best Smart Home Devices", "niche": "smart-home", "summary": "",
            "url": "https://abvorn.com/smart-home/", "hooks": {}}
    products = [
        {"name": "Product A", "price": "$49.99", "role": "Overall Winner"},
        {"name": "Product B", "price": "$39.99", "role": "Runner-Up"},
        {"name": "Product C", "price": "$59.99", "role": "Best Value"},
        {"name": "Product D", "price": "$79.99", "role": "Premium Pick"},
    ]
    persona = {
        "name": "Aware Alex",
        "psychology": {
            "anxieties": ["Matter certification delays", "hub compatibility hell"],
            "hopes": ["true local control no cloud"],
        },
    }
    out = gen.generate(post, platforms=["instagram"], products=products, persona=persona)
    hook = out["instagram"]["hook"]
    joined = "\n".join(out["instagram"]["script"])
    assert "Matter certification delays" in hook
    assert "matter certification delays" not in hook
    assert "Smart home devices" in hook
    assert "compared 4 Smart home devices" in joined
    # grammatical: the count sentence now has its noun
    assert "compared 4 Smart home devices so you" in joined
    # still honest: no physical-testing claims
    for banned in ("we tested", "hands-on", "in our lab"):
        assert banned.lower() not in joined.lower()


def test_no_persona_keeps_generic_copy():
    gen = vsg.ViralScriptGenerator()
    post = {"title": "Best Gaming Mice", "niche": "gaming-mice", "summary": "",
            "url": "https://abvorn.com/gaming-mice/", "hooks": {}}
    out = gen.generate(post, platforms=["instagram"]).get("instagram", {})
    assert out.get("persona", "") == ""
    assert out.get("hook", "")  # generic template hook used


class _FakeLearner:
    def __init__(self, hooks):
        self._hooks = hooks

    def best_hooks(self, niche, platform, limit=3):
        return self._hooks


def test_learner_prepends_winning_hooks_to_variants():
    gen = vsg.ViralScriptGenerator()
    post = {"title": "Best Gaming Mice", "niche": "gaming-mice", "summary": "",
            "url": "https://abvorn.com/gaming-mice/", "hooks": {}}
    winner = {"hook_text": "This mouse wins rounds before it leaves the box", "score": 4.2}
    loser = {"hook_text": "A boring hook that tested poorly", "score": 0}
    learner = _FakeLearner([winner, loser])
    out = gen.generate(post, platforms=["x"], learner=learner)["x"]
    variants = out["hook_variants"]
    assert winner["hook_text"] in variants
    assert loser["hook_text"] not in variants  # score <= 0 filtered out


def test_learner_absent_generates_normally():
    gen = vsg.ViralScriptGenerator()
    post = {"title": "Best Gaming Mice", "niche": "gaming-mice", "summary": "",
            "url": "https://abvorn.com/gaming-mice/", "hooks": {}}
    out = gen.generate(post, platforms=["x"])
    assert out["x"]["hook_variants"]


def test_learned_hook_outranks_persona_hook_when_measured():
    """Measured engagement beats hypothesized persona psychology: the hook
    the learner ranks from real GA4 feedback wins even when a persona is
    present and would otherwise dominate the variant list."""
    gen = vsg.ViralScriptGenerator()
    post = {"title": "Best Gaming Mice", "niche": "gaming-mice", "summary": "",
            "url": "https://abvorn.com/gaming-mice/", "hooks": {}}
    winner = {"hook_text": "This mouse wins rounds before it leaves the box", "score": 4.2}
    learner = _FakeLearner([winner])
    persona = {
        "name": "Competitive Calvin",
        "psychology": {"anxieties": ["dead zones"], "hopes": ["raked wins"]},
    }
    out = gen.generate(post, platforms=["x"], learner=learner, persona=persona)["x"]
    assert out["hook"] == winner["hook_text"]
    assert out["hook_variants"][0] == winner["hook_text"]


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


def test_cta_card_title_fits_and_no_overflow(tmp_path, monkeypatch):
    """The finale card must wrap/shrink long guide titles so nothing bleeds
    off the 1080x1350 canvas (regression for the one-line centered title)."""
    from abvorn.domination import instagram_cards as igc
    from PIL import Image
    src = tmp_path / "src.jpg"
    Image.new("RGB", (1500, 1500), (30, 60, 200)).save(src)
    monkeypatch.setattr(igc, "_download_image", lambda p: str(src))

    products = [{
        "name": "Samsung Odyssey OLED G9 49-inch Ultra-Wide Gaming Monitor",
        "price": "$1,299.99", "role": "Overall Winner", "score": 8.2, "index": 0,
    }]
    paths = igc.compose_carousel(
        products, "4k-monitors",
        "The Best 4K Monitors for Work, Gaming and Everything In Between",
        "https://abvorn.com/", cache_dir=tmp_path)
    cta = next(p for p in paths if p.endswith("cta.jpg"))
    im = Image.open(cta).convert("RGB")
    assert im.size == (1080, 1350)
    px = im.load()

    def is_ink(pq, x, y):
        r, g, b = pq[x, y]
        return r < 60 and g < 60 and b < 60

    # 40px side guards + the bottom 10 rows must stay pure ink.
    for y in range(60, 1340, 4):
        for x in (0, 20, 1040, 1060):
            assert is_ink(px, x, y), f"overflow pixel at {x, y}: {px[x, y]}"
    for x in range(0, 1080, 16):
        for y in range(1340, 1350):
            assert is_ink(px, x, y), f"bottom overflow pixel at {x, y}: {px[x, y]}"

    # The winner's verdict badge must be present as the deep-gold accent.
    gold = sum(
        1
        for x in range(0, 1080, 3)
        for y in range(0, 1350, 3)
        if (lambda c: c[0] > 140 and 60 < c[1] < 190 and c[2] < 130)(px[x, y])
    )
    assert gold > 500


def test_cta_card_winner_data_is_rendered(tmp_path):
    from abvorn.domination import instagram_cards as igc
    from PIL import Image
    a = igc.compose_cta_card(
        "mice", "Best Gaming Mice", "https://abvorn.com/mice/", tmp_path / "with.jpg",
        winner={"name": "Logitech G305", "score": 9}, cache_dir=tmp_path)
    b = igc.compose_cta_card(
        "mice", "Best Gaming Mice", "https://abvorn.com/mice/", tmp_path / "without.jpg",
        winner=None, cache_dir=tmp_path)
    assert a and b
    assert Image.open(a).size == (1080, 1350)
    assert Image.open(a).tobytes() != Image.open(b).tobytes()


def test_fmt_score_edges():
    from abvorn.domination.instagram_cards import _fmt_score
    assert _fmt_score(8) == "8"
    assert _fmt_score(8.0) == "8"
    assert _fmt_score(8.2) == "8.2"
    assert _fmt_score("7.5") == "7.5"
    assert _fmt_score(None) is None
    assert _fmt_score("n/a") is None


def test_platform_media_landscape_sizes_for_share_platforms(tmp_path, monkeypatch):
    """LinkedIn/X/Facebook must get horizontal product-photo share cards at their
    canonical share dimensions, not the 4:5 Instagram canvas."""
    from abvorn.domination import instagram_cards as igc
    from PIL import Image
    src = tmp_path / "src.jpg"
    Image.new("RGB", (1200, 1200), (30, 60, 200)).save(src)
    monkeypatch.setattr(igc, "_download_image", lambda p: str(src))
    products = [
        {"name": "Logitech G305", "price": "$29.99", "role": "Overall Winner", "index": 0},
    ]
    for platform, dims in [("linkedin", (1200, 627)), ("x", (1200, 675)), ("facebook", (1200, 630))]:
        paths = igc.compose_platform_media(
            products, "gaming-mice", "Best Gaming Mice",
            "https://abvorn.com/gaming-mice/", platform, cache_dir=tmp_path / platform,
        )
        assert paths, f"{platform} produced no media"
        assert Image.open(paths[0]).size == dims, f"{platform}: {Image.open(paths[0]).size}"


def test_platform_media_linkedin_is_single_winner_card(tmp_path, monkeypatch):
    """LinkedIn must carry exactly ONE share card — the Overall Winner — while
    Instagram keeps the full carousel deck (product slides + Abvorn CTA)."""
    from abvorn.domination import instagram_cards as igc
    from PIL import Image
    src = tmp_path / "src.jpg"
    Image.new("RGB", (1200, 1200), (30, 60, 200)).save(src)
    monkeypatch.setattr(igc, "_download_image", lambda p: str(src))
    products = [
        {"name": "Logitech G305", "price": "$29.99", "role": "Overall Winner", "index": 0},
        {"name": "Razer Viper Mini", "price": "$39.99", "role": "Runner-Up", "index": 1},
        {"name": "Pulsar X2", "price": "$49.99", "role": "Also Great", "index": 2},
    ]
    li = igc.compose_platform_media(
        products, "gaming-mice", "Best Gaming Mice",
        "https://abvorn.com/gaming-mice/", "linkedin",
        cache_dir=tmp_path / "linkedin",
    )
    assert len(li) == 1, f"linkedin must get exactly one winner card, got {len(li)}"
    assert Image.open(li[0]).size == (1200, 627)
    # Winner (index 0) is the only card composed — the deck is its share card.
    assert str(li[0]).endswith("share_0.jpg")

    ig = igc.compose_platform_media(
        products, "gaming-mice", "Best Gaming Mice",
        "https://abvorn.com/gaming-mice/", "instagram",
        cache_dir=tmp_path / "instagram",
    )
    assert len(ig) == len(products) + 1  # product slides + CTA stay intact
    assert Image.open(ig[-1]).size == (1080, 1350)


def test_platform_media_pinterest_is_2x3(tmp_path, monkeypatch):
    """Pinterest pins must be 1000x1500 (2:3), the platform's recommended ratio."""
    from abvorn.domination import instagram_cards as igc
    from PIL import Image
    src = tmp_path / "src.jpg"
    Image.new("RGB", (1200, 1200), (30, 60, 200)).save(src)
    monkeypatch.setattr(igc, "_download_image", lambda p: str(src))
    products = [
        {"name": "Logitech G305", "price": "$29.99", "role": "Overall Winner", "index": 0},
        {"name": "Razer Viper Mini", "price": "$39.99", "role": "Runner-Up", "index": 1},
    ]
    paths = igc.compose_platform_media(
        products, "gaming-mice", "Best Gaming Mice",
        "https://abvorn.com/gaming-mice/", "pinterest", cache_dir=tmp_path / "pinterest",
    )
    assert len(paths) == 2
    for p in paths:
        assert Image.open(p).size == (1000, 1500), f"got {Image.open(p).size}"


def test_platform_media_telegram_reuses_vertical_deck(tmp_path, monkeypatch):
    """Telegram consumes the same vertical product deck as IG (1080x1350 album)."""
    from abvorn.domination import instagram_cards as igc
    from PIL import Image
    src = tmp_path / "src.jpg"
    Image.new("RGB", (1200, 1200), (30, 60, 200)).save(src)
    monkeypatch.setattr(igc, "_download_image", lambda p: str(src))
    products = [
        {"name": "Logitech G305", "price": "$29.99", "role": "Overall Winner", "index": 0},
        {"name": "Razer Viper Mini", "price": "$39.99", "role": "Runner-Up", "index": 1},
    ]
    paths = igc.compose_platform_media(
        products, "gaming-mice", "Best Gaming Mice",
        "https://abvorn.com/gaming-mice/", "telegram", cache_dir=tmp_path / "telegram",
    )
    assert paths
    for p in paths:
        assert Image.open(p).size == (1080, 1350)


def test_platform_media_empty_without_products(tmp_path, monkeypatch):
    from abvorn.domination import instagram_cards as igc
    assert igc.compose_platform_media([], "gaming-mice", "t", "u", "linkedin",
                                      cache_dir=tmp_path) == []


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


# ─── Half-sentence "compared 4 General" regression guard ────────────────────


def test_detect_niche_classifies_fitness_trackers():
    """The exact bug that shipped 'We compared 4 General': the fitness-tracker
    article resolved to the 'general' fallback niche because the keyword map
    had no wearable keywords. It must classify as its own niche."""
    from abvorn.domination.content_intelligence import ContentIntelligence
    ci = ContentIntelligence(rss_path="")
    assert (
        ci._detect_niche(
            "Best Fitness Trackers 2026: Top 3 Picks Compared for Heart Rate "
            "and Sleep Health Tracking",
            "fitness tracker smartwatch heart rate",
            [],
        )
        == "fitness-tracker"
    )
    assert (
        ci._detect_niche("Fitbit Charge 6 Review", "fitbit charge 6 fitness band", [])
        == "fitness-tracker"
    )


def test_fitness_tracker_copy_never_reads_general():
    """A fitness-tracker post with real products must render 'Fitness trackers'
    everywhere the old niche fallback rendered 'General'."""
    gen = vsg.ViralScriptGenerator()
    post = {"title": "Best Fitness Trackers 2026", "niche": "fitness-tracker",
            "summary": "", "url": "https://abvorn.com/reviews/fitness-trackers/",
            "hooks": {}}
    products = [
        {"name": "Product A", "price": "$79.99", "role": "Overall Winner"},
        {"name": "Product B", "price": "$49.99", "role": "Runner-Up"},
        {"name": "Product C", "price": "$129.99", "role": "Premium Pick"},
        {"name": "Product D", "price": "$39.99", "role": "Best Value"},
    ]
    out = gen.generate(post, platforms=["instagram", "telegram", "linkedin", "pinterest", "x"],
                       products=products)
    for platform in ("telegram", "linkedin"):
        script = out[platform]["script"]
        joined = "\n".join(script) if isinstance(script, list) else str(script)
        assert "General" not in joined
        assert "Fitness trackers" in joined or "fitness-tracker" in joined
    assert "Fitness trackers" in out["telegram"]["script"]["text"]
    assert "Fitness trackers" in out["instagram"]["hook"]
    assert "4 General" not in out["instagram"]["hook"]
    assert "compared 4 General" not in out["pinterest"]["script"]["description"]


def test_humanize_niche_has_countable_noun():
    assert vsg._humanize_niche("fitness-tracker") == "Fitness trackers"
    assert vsg._humanize_niche("general") == "products"


def test_fit_text_cuts_at_sentence_boundary():
    from abvorn.platform.adapters import fit_text
    text = "First sentence. Second sentence goes here. Third sentence."
    out = fit_text(text, 30)
    assert out.endswith("\u2026")
    assert out.startswith("First sentence.")
    assert "Second " not in out  # the second sentence must not hang half-cut
    assert len(out) <= 30
    # a long sentence with no boundary falls back to a word boundary, never a
    # mid-word hard cut
    assert fit_text("nospace" * 40, 30) == ("nospace" * 4 + "nospace")[:29] + "\u2026"


def test_fit_text_leaves_short_text_untouched():
    from abvorn.platform.adapters import fit_text
    assert fit_text("Short copy that fits.", 50) == "Short copy that fits."
    assert fit_text("", 50) == ""
    # already-ending punctuation: no ellipsis added when the sentence fits
    out = fit_text("Complete sentence.", 20)
    assert out == "Complete sentence." and not out.endswith("\u2026")