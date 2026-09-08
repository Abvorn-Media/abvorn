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
}

MIN_W = 1200
MIN_H = 700
DL_W = 1440


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
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--only", nargs="*", help="niche slugs to process")
    ap.add_argument("--pick", type=int, default=0, help="force the Nth ranked candidate (0=best)")
    ap.add_argument("--refresh", action="store_true", help="re-fetch even if the JPG exists")
    ap.add_argument("--dry-run", action="store_true", help="print picks without downloading")
    ap.add_argument("--top", type=int, default=0, help="print this many ranked candidates per slug (no downloads)")
    args = ap.parse_args()

    if not args.key:
        print("No Pexels key: pass --key or set PEXELS_KEY/PEXELS_API_KEY.", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    credits_path = args.out / CREDITS_FILE
    credits = {}
    if credits_path.exists():
        try:
            credits = json.loads(credits_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            credits = {}

    slugs = args.only or list(HEROES)
    headers = {"Authorization": args.key}
    changed = []

    for slug in slugs:
        if slug not in HEROES:
            print(f"skip: {slug} (not in HEROES map)")
            continue
        query, window, _default_pick = HEROES[slug]
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
        print(f"OK:   {slug:22s} {size_kb}KB <= docs/assets/hero/{slug}.jpg  ({alt[:60]})")
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