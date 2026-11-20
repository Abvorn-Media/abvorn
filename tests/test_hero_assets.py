"""Regression: the TV category hero must be real photography, not a test stub.

The flat blue rectangle on the homepage was docs/assets/hero/tv.jpg, backed by
a credits.json entry with photo_id 12345 / photographer "Test" / a
/photo/test/ URL - a fixture committed in the 2026-10-03 TV batch and never
replaced. Guard both the credit metadata and the pixels.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tv_hero_credit_is_a_real_pexels_photo():
    credits = json.loads(
        (ROOT / "docs/assets/hero/credits.json").read_text(encoding="utf-8")
    )
    tv = credits["tv"]

    assert tv.get("photo_id") != 12345
    assert tv.get("photographer") not in ("", "Test")
    assert "/photo/test/" not in tv.get("pexels_url", "")
    assert tv.get("pexels_url", "").startswith("https://www.pexels.com/photo/")


def test_tv_hero_is_photography_not_a_flat_rectangle():
    from PIL import Image

    with Image.open(ROOT / "docs/assets/hero/tv.jpg") as img:
        assert img.width >= 1200
        small = img.convert("RGB").resize((80, 45))
        pixels = (small.get_flattened_data() if hasattr(small, "get_flattened_data")
                  else small.getdata())
        distinct = len(set(pixels))

    assert distinct > 300, f"tv hero has only {distinct} distinct colours"
