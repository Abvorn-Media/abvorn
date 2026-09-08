"""Tests for the category-hero photo staging: real Pexels JPGs replacing the
SVG placeholders, the credits.json manifest, and the on-page credit line."""
import json
from pathlib import Path

from run_cycle import build_category_page, hero_credit

HERO_DIR = Path("docs/assets/hero")
NICHES = {
    "4k-monitors",
    "fitness-trackers",
    "gaming-mice",
    "laptops",
    "mechanical-keyboards",
    "smart-home",
    "streaming-devices",
    "webcams",
    "wireless-earbuds",
    "wireless-headphones",
}


def _credits():
    with open(HERO_DIR / "credits.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_hero_credit_present_for_staged_slug():
    info = hero_credit("laptops", "https://abvorn-media.github.io/abvorn")
    assert info is not None
    assert info["src"].endswith("assets/hero/laptops.jpg")
    assert info["photographer"]
    assert info["url"].startswith("https://www.pexels.com/")
    assert info["alt"]


def test_hero_credit_none_without_jpg():
    assert hero_credit("nope-not-a-niche", "https://x") is None


def test_every_jpg_has_a_credit_entry():
    credits = _credits()
    jpgs = {p.stem for p in HERO_DIR.glob("*.jpg")}
    assert jpgs, "no hero JPGs committed"
    missing = jpgs - set(credits)
    assert not missing, f"JPGs without credits.json entry: {sorted(missing)}"


def test_credit_entries_cover_all_niches():
    credits = _credits()
    assert set(credits) == NICHES, (
        f"credits.json must cover exactly the staged niches; extra: "
        f"{sorted(set(credits) - NICHES)}, missing: {sorted(NICHES - set(credits))}"
    )


def test_credit_entry_shape():
    for slug, entry in _credits().items():
        for key in ("query", "alt", "photo_id", "photographer", "photographer_url",
                    "pexels_url", "width", "height", "source"):
            assert key in entry, f"{slug}: missing key {key}"
        assert entry["source"] == "Pexels"
        assert entry["width"] > 0 and entry["height"] > 0


def test_built_page_renders_photo_stage_for_every_niche():
    # Every staged niche must render a photo stage with a credit line, never
    # a hidden SVG fallback stage.
    for slug in NICHES:
        html = build_category_page(slug, slug.replace("-", " ").title(), [], NICHES)
        assert "cat-hero__stage--photo" in html, slug
        assert "cat-hero__credit" in html, slug
        assert 'aria-hidden="true"' not in (
            html.split("cat-hero__stage")[1].split("</div>")[0]
        ), slug