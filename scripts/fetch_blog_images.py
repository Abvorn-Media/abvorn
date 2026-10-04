#!/usr/bin/env python3
"""fetch_blog_images.py - source Pexels photographs for a Dispatch post.

Every Dispatch post needs a hero and at least one inline photograph, each
committed under docs/assets/blog/<slug>/ and credited to its photographer in
the post record (Abvorn's brand claim is that every picture is fact-checked).

Can be used as a library (fetch_blog_images) or from the CLI:

  python scripts/fetch_blog_images.py --slug quiet-focus-block \
      --query "morning light desk window" --query "cluttered desk home office"

Key resolution order: --key, PEXELS_KEY env, boardroom secrets.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

PEXELS_BASE = "https://api.pexels.com/v1"
REPO = Path(__file__).resolve().parents[1]
BLOG_ASSET_DIR = REPO / "docs" / "assets" / "blog"

MIN_W, MIN_H = 1200, 700
HERO_W, INLINE_W = 1600, 1200


def get_pexels_key(explicit: str = "") -> str:
    if explicit:
        return explicit
    for env in ("PEXELS_KEY", "PEXELS_API_KEY"):
        val = os.environ.get(env) or ""
        if val and "your" not in val.lower() and "YOUR_" not in val:
            return val
    try:
        secrets_path = Path.home() / ".abvorn" / "boardroom" / "secrets.json"
        if secrets_path.exists():
            data = json.loads(secrets_path.read_text(encoding="utf-8-sig"))
            val = str(data.get("PEXELS_KEY", ""))
            if val and "your" not in val.lower():
                return val
    except Exception:
        pass
    return ""


def search_photos(query: str, key: str, per_page: int = 12) -> list:
    resp = requests.get(
        f"{PEXELS_BASE}/search",
        headers={"Authorization": key},
        params={"query": query, "per_page": per_page, "orientation": "landscape"},
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json().get("photos", [])


def pick_photo(photos: list, window: tuple, used_ids: set, rank: int = 0):
    lo, hi = window
    candidates = []
    for p in photos:
        if p.get("id") in used_ids:
            continue
        w, h = p.get("width", 0), p.get("height", 0)
        if w < MIN_W or h < MIN_H:
            continue
        ratio = w / h if h else 0
        if lo <= ratio <= hi:
            candidates.append(p)
    candidates.sort(key=lambda p: p["width"] * p["height"], reverse=True)
    return candidates[rank] if len(candidates) > rank else (candidates[0] if candidates else None)


def download_and_compress(url: str, dest: Path, target_w: int) -> bool:
    try:
        resp = requests.get(url, headers={"User-Agent": "AbvornDispatch/1.0"}, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    except Exception as e:
        print(f"FAIL download {dest.name}: {e}", file=sys.stderr)
        return False
    try:
        from PIL import Image

        im = Image.open(dest)
        if im.mode != "RGB":
            im = im.convert("RGB")
        if im.width > target_w:
            im = im.resize((target_w, int(im.height * target_w / im.width)), Image.LANCZOS)
        im.save(dest, "JPEG", quality=82, optimize=True, progressive=True)
    except Exception as e:
        print(f"warn: Pillow recompress skipped for {dest.name} ({e})", file=sys.stderr)
    return True


def _record(photo: dict, rel_file: str, query: str, caption: str = "") -> dict:
    return {
        "file": rel_file.replace("\\", "/"),
        "query": query,
        "alt": (photo.get("alt") or query).strip(),
        "caption": caption,
        "photo_id": photo.get("id"),
        "photographer": photo.get("photographer", ""),
        "photographer_url": photo.get("photographer_url", ""),
        "pexels_url": photo.get("url", ""),
        "width": photo.get("width"),
        "height": photo.get("height"),
        "source": "Pexels",
        "fetched": datetime.now().isoformat(timespec="seconds"),
    }


def fetch_blog_images(slug: str, queries: list, key: str, count: int = 3,
                      refresh: bool = False) -> tuple:
    """Return (hero_record, [inline_records]). Missing photographs are skipped."""
    if not key or not queries:
        return None, []
    out_dir = BLOG_ASSET_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    hero = None
    images = []
    used_ids: set = set()

    specs = [("hero", HERO_W, (1.30, 1.95))] + [
        (f"{i:02d}", INLINE_W, (1.15, 1.85)) for i in range(1, count)
    ]

    for (name, target_w, window), query in zip(specs, queries):
        dest = out_dir / f"{name}.jpg"
        rel = f"assets/blog/{slug}/{name}.jpg"
        if dest.exists() and not refresh:
            # Rebuild the record from the sidecar manifest if we have one.
            meta = _load_manifest(out_dir).get(name)
            if meta:
                rec = meta
            else:
                rec = {"file": rel, "query": query, "alt": query, "source": "Pexels"}
            rec["file"] = rel
        else:
            try:
                photos = search_photos(query, key)
            except Exception as e:
                print(f"FAIL search {query!r}: {e}", file=sys.stderr)
                continue
            photo = pick_photo(photos, window, used_ids)
            if not photo:
                print(f"FAIL no candidate for {query!r}", file=sys.stderr)
                continue
            dl = f"{photo['src']['original']}?auto=compress&cs=tinysrgb&w={target_w}"
            if not download_and_compress(dl, dest, target_w):
                continue
            used_ids.add(photo.get("id"))
            caption = (photo.get("alt") or query).strip()
            rec = _record(photo, rel, query, caption=caption if name != "hero" else "")
            _save_manifest(out_dir, name, rec)

        if name == "hero":
            hero = rec
        else:
            images.append(rec)

    return hero, images


def _load_manifest(out_dir: Path) -> dict:
    path = out_dir / "credits.json"
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_manifest(out_dir: Path, name: str, rec: dict) -> None:
    path = out_dir / "credits.json"
    data = _load_manifest(out_dir)
    data[name] = rec
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--query", action="append", default=[],
                    help="repeatable; first is the hero, rest are inline")
    ap.add_argument("--key", default="")
    ap.add_argument("--count", type=int, default=3, help="total photos incl. hero")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    key = get_pexels_key(args.key)
    if not key:
        print("No Pexels key found (--key, PEXELS_KEY, or boardroom secrets).", file=sys.stderr)
        return 1
    if not args.query:
        print("Provide at least one --query.", file=sys.stderr)
        return 1

    hero, images = fetch_blog_images(args.slug, args.query, key, count=args.count, refresh=args.refresh)
    print(json.dumps({"hero": hero, "images": images}, ensure_ascii=False, indent=2))
    return 0 if hero else 1


if __name__ == "__main__":
    sys.exit(main())
