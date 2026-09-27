"""Backfill posts.image for published reviews that stored an empty image.

Why this exists
---------------
`AbvornDaemon` used to persist `image=content.get("image")`, but a content
payload carries the product photo at `products[0]["image"]` and has no
top-level "image" key. Every row therefore stored an empty string, and every
card built from a state row fell back to the generic niche artwork
(`/assets/<niche>.svg`) instead of the real product photo. `add_post` now
persists the photo correctly (see `src.deployment.product_card_image`), so this
script only has to repair rows written before that fix.

What it does
------------
For each `posts` row with an empty image, resolve the published review page
(local `docs/` first, then the live URL), extract the same real product photo
the page itself renders, and store it. The extraction deliberately reuses the
review-page regexes in `src.deployment`, which only match genuine product
photography (`hero-pick` / `product-shot`), so a page with no product photo
yields nothing and the row is left untouched rather than filled with fallback
artwork.

This script never deletes or rewrites titles/filenames, and it is idempotent:
re-running it only touches rows that are still empty.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.deployment import (  # noqa: E402
    _HERO_PICK_IMG_RE,
    _NICHE_HERO_IMG_RE,
    upgrade_product_image,
)

SITE = "https://abvorn.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def extract_product_image(html: str) -> str:
    """Return the real product photo a review page renders, else "".

    Both patterns require a real product-photo container, so pages that only
    carry the niche fallback artwork return "" and are left alone.
    """
    if not html:
        return ""
    m = _HERO_PICK_IMG_RE.search(html) or _NICHE_HERO_IMG_RE.search(html)
    if not m:
        return ""
    url = (m.group(1) or "").strip()
    if not url.startswith(("http://", "https://")):
        # A local /assets/... path means we matched chrome, not a product shot.
        return ""
    return upgrade_product_image(url)


def _fetch(url: str, timeout: int = 45) -> str:
    return (urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
            .read().decode("utf-8", "replace"))


def candidate_relpaths(slug: str, filename: str, allow_hub: bool = True) -> list:
    """Published paths for a post, most specific first.

    ``allow_hub`` gates the category-hub fallback used for rows that carry no
    article filename. It is off by default: a hub exposes ONE best-pick product
    photo, so every empty-filename row in a niche inherits that same image. On
    this repo's state.db that collapsed 78 rows onto a single webcam photo, so
    the fallback is opt-in rather than silently wrong.
    """
    slug = (slug or "").strip("/")
    name = (filename or "").strip().lstrip("/")
    if name and name != "index.html":
        return ["reviews/%s/%s" % (slug, name)]
    if allow_hub:
        return ["reviews/%s/index.html" % slug]
    return []


def resolve_image(slug: str, filename: str, docs_dir: Path, offline: bool = False,
                  allow_hub: bool = True) -> tuple:
    """Find the product photo for a post. Returns (image, source)."""
    for rel in candidate_relpaths(slug, filename, allow_hub=allow_hub):
        local = docs_dir / rel
        if local.is_file():
            try:
                img = extract_product_image(local.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                img = ""
            if img:
                return img, "local:%s" % rel
        if offline:
            continue
        url = "%s/%s" % (SITE, rel)
        for attempt in range(2):
            try:
                img = extract_product_image(_fetch(url))
                if img:
                    return img, "live:%s" % rel
                break
            except (urllib.error.URLError, OSError, ValueError):
                if attempt == 0:
                    time.sleep(2)
    return "", ""


def backfill(db_path: Path, docs_dir: Path, dry_run: bool = False,
             limit: int = 0, offline: bool = False, delay: float = 0.4,
             allow_hub: bool = False) -> dict:
    stats = {"rows": 0, "filled": 0, "already": 0, "unresolved": 0, "skipped": 0}
    con = sqlite3.connect(str(db_path), timeout=30)
    try:
        con.execute("PRAGMA busy_timeout=30000")
        cur = con.cursor()
        cur.execute("SELECT id, niche_slug, title, filename, image FROM posts")
        rows = cur.fetchall()
        updates = []
        for pid, slug, title, filename, image in rows:
            stats["rows"] += 1
            if (image or "").strip():
                stats["already"] += 1
                continue
            if not slug or not title:
                stats["skipped"] += 1
                continue
            if TIMESTAMP_RE.match((image or "").strip()):
                # Legacy rows that stored created_at in the image column.
                stats["skipped"] += 1
                continue
            if limit and stats["filled"] + stats["unresolved"] >= limit:
                break
            img, source = resolve_image(slug, filename or "", docs_dir, offline=offline,
                                        allow_hub=allow_hub)
            if not img:
                stats["unresolved"] += 1
                print("  UNRESOLVED %-14s %-52s" % (slug[:14], (title or "")[:52]))
                continue
            stats["filled"] += 1
            print("  + %-14s %-52s" % (slug[:14], (title or "")[:52]))
            print("      img  = %s" % img[:92])
            print("      from = %s" % source[:92])
            updates.append((img, pid))
            if not offline and delay:
                time.sleep(delay)
        if updates and not dry_run:
            con.executemany("UPDATE posts SET image=? WHERE id=?", updates)
            con.commit()
    finally:
        con.close()
    return stats


def main(argv=None) -> int:
    # Post titles contain non-ASCII (en/em dashes, U+2011 non-breaking hyphens).
    # On Windows a cp1252 stdout raises UnicodeEncodeError on the first one and
    # kills the run part-way through the report, so force UTF-8 before printing.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state-db", type=Path,
                    default=Path.home() / ".abvorn" / "state.db",
                    help="state.db to repair (VPS: /opt/abvorn-core/.abvorn/state.db)")
    ap.add_argument("--docs-dir", type=Path, default=Path("docs"))
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    ap.add_argument("--offline", action="store_true", help="use docs/ only, no live fetches")
    ap.add_argument("--limit", type=int, default=0, help="stop after N attempted rows")
    ap.add_argument("--delay", type=float, default=0.4, help="seconds between live fetches")
    ap.add_argument("--allow-hub-fallback", action="store_true",
                    help="also fill rows that have no article filename, using the "
                         "category hub. A hub exposes one best-pick photo, so this "
                         "stamps the same image on every such row in a niche")
    args = ap.parse_args(argv)

    if not args.state_db.is_file():
        print("state db not found: %s" % args.state_db)
        return 1

    print("state db : %s" % args.state_db)
    print("docs dir : %s" % args.docs_dir)
    print("mode     : %s%s%s" % ("DRY RUN" if args.dry_run else "WRITE",
                                 ", offline" if args.offline else "",
                                 ", hub-fallback" if args.allow_hub_fallback else ""))
    print("-" * 78)
    stats = backfill(args.state_db, args.docs_dir, dry_run=args.dry_run,
                     limit=args.limit, offline=args.offline, delay=args.delay,
                     allow_hub=args.allow_hub_fallback)
    print("-" * 78)
    print("rows=%(rows)d filled=%(filled)d already_set=%(already)d "
          "unresolved=%(unresolved)d skipped=%(skipped)d" % stats)
    if stats["filled"] and not args.dry_run:
        print("committed %d image(s); re-run is a no-op" % stats["filled"])
    elif args.dry_run and stats["filled"]:
        print("dry run: nothing written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
