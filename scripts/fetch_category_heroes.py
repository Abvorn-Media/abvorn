#!/usr/bin/env python3
"""fetch_category_heroes.py - Source real Pexels photos for category page heroes.

Searches Pexels for an object-first, dark-friendly photo per niche, downloads a
compressed JPG to docs/assets/hero/<slug>.jpg, and records photographer credit
in docs/assets/hero/credits.json (rendered as a visible credit line because
Abvorn's honesty is the brand claim).

Usage:
  python scripts/fetch_category_heroes.py --dry-run          # preview picks, no writes
  python scripts/fetch_category_heroes.py                    # fetch any missing heroes
  python scripts/fetch_category_heroes.py --refresh          # re-fetch everything
  python scripts/fetch_category_heroes.py --only laptops     # one niche
  python scripts/fetch_category_heroes.py --pick 2 --only laptops   # force 3rd result
  python scripts/fetch_category_heroes.py --set scene --dry-run --top 6  # lifestyle set

Two sets, two art directions:
  --set stage  (default) docs/assets/hero/        object on a dark stage, category pages
  --set scene                 docs/assets/hero-scene/ product in a real room, About page

Needs a Pexels key: env PEXELS_KEY / PEXELS_API_KEY or --key.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

PEXELS_BASE = "https://api.pexels.com/v1"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "hero"
SCENE_OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "hero-scene"
CREDITS_FILE = "credits.json"

# slug -> (pexels query, aspect window, default rank pick). Runs from the repo
# root. Art direction: object-first product photography, no people, no
# distinctive brand, no bright backdrops — a "specimen on a dark stage"
# consistent with the dark showroom hero. Default picks were chosen from
# reviewed candidate lists on 2026-09-08; --pick overrides per run.
HEROES = {
    "4k-monitors": ("computer monitor black background", (1.15, 1.9), 3),
    "fitness-trackers": ("smart watch product black background", (1.0, 1.7), 3),
    "gaming-mice": ("gaming mouse dark", (1.15, 2.0), 0),
    "laptops": ("laptop keyboard closeup dark", (1.0, 1.8), 1),
    "mechanical-keyboards": ("mechanical keyboard black keycaps dark", (1.2, 2.1), 2),
    "smart-home": ("smart speaker product photography", (1.1, 1.9), 5),
    "streaming-devices": ("smart tv remote product", (1.1, 1.9), 5),
    "webcams": ("computer camera closeup", (1.0, 1.9), 5),
    "wireless-earbuds": ("earbuds dark", (1.0, 1.8), 2),
    "wireless-headphones": ("headphones product black background", (1.1, 2.0), 4),
    "audio": ("wireless headphones product black background", (1.1, 2.0), 1),
    "fitness-and-health": ("smartwatch fitness black background", (1.0, 1.7), 0),
    "home-and-lifestyle": ("smart speaker home dark", (1.1, 1.9), 0),
    "computing-and-monitors": ("ultrawide monitor black background", (1.15, 1.9), 0),
    "gaming": ("gaming rgb keyboard mouse dark", (1.1, 2.0), 0),
    "webcams-and-accessories": ("webcam product black background", (1.0, 1.9), 0),
}

MIN_W = 1200
MIN_H = 700
DL_W = 1440

# Lifestyle set for the About page hero. This is deliberately the OPPOSITE of
# HEROES above: no dark stage, no specimen. The About hero has to sell "we
# review what you actually live with", so each shot puts the product in a real
# room with a person using it -- a TV in a living room, a laptop on a desk,
# headphones on a head. Queries name the scene, not the product, because
# Pexels' "headphones product black background" returns a flat lay.
#
# Written to docs/assets/hero-scene/ with its own credits.json so the reviewed
# dark-stage category heroes keep their art direction untouched.
#
# Windows are centred on the About hero's 4:3 aspect-ratio box; object-fit:
# cover trims the rest, so anything in 1.2-1.7 crops without a hard letterbox.
SCENES = {
    # Default picks were reviewed against the candidate lists on 2026-10-01 and
    # the reasons recorded, because --pick is global and cannot express these
    # per-slug choices:
    #   webcams  -> rank 2, not 0. Rank 0/1 are generic "virtual meeting" shots
    #               and rank 1 is credited to "LinkedIn Sales Navigator", a
    #               spam-bait photographer name. Rank 2 is RDNE Stock and puts
    #               the laptop on an actual wooden desk, which is the scene.
    #   earbuds  -> rank 2, not 0/1. Rank 0 is a flat lay on a table, not a
    #               product in use. Rank 1 washed out badly (mean luminance 190,
    #               edge energy 3.3 -- effectively a bright white room). Rank 2
    #               is a person with earbuds actually in her ears, correctly
    #               exposed. Rank 3 has more surface detail but the alt says
    #               "wireless headphones", i.e. the wrong product, and this
    #               site's whole claim is that every pick is fact-checked.
    "streaming-devices": ("modern living room television sofa", (1.2, 1.7), 0),
    "wireless-headphones": ("woman wearing headphones listening music", (1.2, 1.7), 0),
    "webcams": ("laptop video call home office desk", (1.2, 1.7), 2),
    "wireless-earbuds": ("person using wireless earbuds smartphone", (1.2, 1.7), 2),
    "smart-home": ("cozy living room interior lamp evening", (1.2, 1.7), 0),
}


def pick_photos(photos, window, pick=0):
    """Rank candidates: in-aspect, big enough, largest area first."""
    lo, hi = window
    in_window = []
    for p in photos:
        w, h = p.get("width", 0), p.get("height", 0)
        if w < MIN_W or h < MIN_H:
            continue
        ratio = w / h if h else 0
        if not (lo <= ratio <= hi):
            continue
        in_window.append(p)
    in_window.sort(key=lambda p: p["width"] * p["height"], reverse=True)
    return in_window[pick] if len(in_window) > pick else None


def download_photo(url, dest, timeout=60):
    resp = requests.get(url, headers={"User-Agent": "AbvornHeroSource/1.0"}, timeout=timeout)
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=os.environ.get("PEXELS_KEY") or os.environ.get("PEXELS_API_KEY"))
    ap.add_argument("--set", dest="which_set", choices=("stage", "scene"), default="stage",
                    help="stage = object on a dark stage (category pages); "
                         "scene = product in a real room (About page)")
    ap.add_argument("--out", type=Path, default=None,
                    help="override the output dir (defaults per --set)")
    ap.add_argument("--only", nargs="*", help="niche slugs to process")
    ap.add_argument("--pick", type=int, default=0, help="force the Nth ranked candidate (0=best)")
    ap.add_argument("--refresh", action="store_true", help="re-fetch even if the JPG exists")
    ap.add_argument("--dry-run", action="store_true", help="print picks without downloading")
    ap.add_argument("--top", type=int, default=0, help="print this many ranked candidates per slug (no downloads)")
    args = ap.parse_args()

    if not args.key:
        print("No Pexels key: pass --key or set PEXELS_KEY/PEXELS_API_KEY.", file=sys.stderr)
        return 1

    sets = {"stage": HEROES, "scene": SCENES}
    heroes = sets[args.which_set]
    if args.out is None:
        args.out = (SCENE_OUT if args.which_set == "scene" else DEFAULT_OUT)

    args.out.mkdir(parents=True, exist_ok=True)
    credits_path = args.out / CREDITS_FILE
    credits = {}
    if credits_path.exists():
        try:
            credits = json.loads(credits_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            credits = {}

    slugs = args.only or list(heroes)
    headers = {"Authorization": args.key}
    changed = []

    for slug in slugs:
        if slug not in heroes:
            print(f"skip: {slug} (not in the '{args.which_set}' map)")
            continue
        query, window, _default_pick = heroes[slug]
        pick = args.pick if args.pick else _default_pick
        dest = args.out / f"{slug}.jpg"
        if dest.exists() and not args.refresh:
            print(f"have: {slug}")
            continue

        try:
            resp = requests.get(
                f"{PEXELS_BASE}/search",
                headers=headers,
                params={"query": query, "per_page": 12, "orientation": "landscape"},
                timeout=20,
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
        except Exception as e:
            print(f"FAIL: {slug} search error: {e}")
            continue

        photo = pick_photos(photos, window, pick)
        if not photo:
            print(f"FAIL: {slug} no candidate in aspect window for '{query}'")
            continue

        if args.top:
            top = []
            lo, hi = window
            for p in photos:
                w, h = p.get("width", 0), p.get("height", 0)
                if w < MIN_W or h < MIN_H:
                    continue
                ratio = w / h if h else 0
                if not (lo <= ratio <= hi):
                    continue
                top.append(p)
            top.sort(key=lambda p: p["width"] * p["height"], reverse=True)
            for i, p in enumerate(top[: args.top]):
                alt = (p.get("alt") or "").strip().replace("\n", " ")
                print(
                    f"rank {i:2d} {slug:22s} {p['width']}x{p['height']}  "
                    f"{alt[:80]!r}  by {p.get('photographer','')}"
                )
            continue

        src = photo["src"]
        dl_url = f"{src['original']}?auto=compress&cs=tinysrgb&w={DL_W}"
        alt = (photo.get("alt") or query).strip()
        info = {
            "query": query,
            "alt": alt,
            "photo_id": photo["id"],
            "photographer": photo.get("photographer", ""),
            "photographer_url": photo.get("photographer_url", ""),
            "pexels_url": photo.get("url", ""),
            "width": photo.get("width"),
            "height": photo.get("height"),
            "source": "Pexels",
            "fetched": datetime.now().isoformat(timespec="seconds"),
        }
        if args.dry_run:
            print(f"pick: {slug:22s} {info['width']}x{info['height']}  {alt[:70]!r}  by {info['photographer']}")
            continue

        try:
            download_photo(dl_url, dest)
        except Exception as e:
            print(f"FAIL: {slug} download error: {e}")
            continue

        try:
            from PIL import Image

            im = Image.open(dest)
            if im.mode != "RGB":
                im = im.convert("RGB")
            if im.width > DL_W:
                im = im.resize((DL_W, int(im.height * DL_W / im.width)), Image.LANCZOS)
            im.save(dest, "JPEG", quality=82, optimize=True, progressive=True)
        except Exception as e:
            print(f"warn: {slug} Pillow recompress skipped ({e})")

        credits[slug] = info
        size_kb = dest.stat().st_size // 1024
        print(f"OK:   {slug:22s} {size_kb}KB <= {dest}  ({alt[:60]})")
        changed.append(slug)

    if changed and not args.dry_run:
        credits_path.write_text(
            json.dumps(credits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"credits written: {credits_path} ({len(credits)} entries)")

    if args.dry_run:
        print("\n(dry run — nothing written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())