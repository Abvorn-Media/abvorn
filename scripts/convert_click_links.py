"""convert_click_links.py — One-time fixup: convert legacy abvorn.com/click/
links in published docs back to the direct (tagged) Amazon affiliate URLs.

The static GitHub Pages host cannot serve the /click/<article>/<idx> redirect
endpoints (they 404). Every legacy click URL is resolved through the
click_targets table (recorded at build time) back to the real product URL.

Usage:
    python scripts/convert_click_links.py [--dry-run] [--path docs/reviews/....html]
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

DOCS = Path("docs")
DB_PATH = Path("data/clicks.db")

CLICK_RE = re.compile(r"https://abvorn\.com/click/([^/\x22'\s?]+)/(\d+)(?:\?[^\x22'\s]*)?")


def load_targets() -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute("SELECT article_id, product_index, product_url FROM click_targets").fetchall()
    conn.close()
    targets = {(a, i): u for a, i, u in rows}
    # Rows missing from click_targets (older build numbering gaps), seeded from
    # the same products seen under other article_ids of the same niche.
    targets.update({
        ("4k-monitors-1", 4): "https://www.amazon.com/dp/B0D3WGM8X8?tag=viraltestco-20",
        ("wireless-headphones-36", 3): "https://www.amazon.com/dp/B0FQFB8FMG?tag=viraltestco-20",
        ("wireless-headphones-36", 4): "https://www.amazon.com/dp/B08WM3LMJF?tag=viraltestco-20",
    })
    return targets


def convert_file(path: Path, targets: dict, dry_run: bool = False):
    text = path.read_text(encoding="utf-8")

    def repl(m):
        article_id, idx = m.group(1), int(m.group(2))
        url = targets.get((article_id, idx))
        if not url:
            return m.group(0)
        return url

    new_text, n = CLICK_RE.subn(repl, text)
    if n == 0:
        return 0, []

    leftovers = [
        m.group(0) for m in CLICK_RE.finditer(new_text)
        if targets.get((m.group(1), int(m.group(2)))) is None
    ]
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return n, leftovers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--path", default=None, help="single file to convert")
    args = ap.parse_args()

    targets = load_targets()
    report = []

    def iter_files():
        if args.path:
            yield Path(args.path)
            return
        for p in sorted(DOCS.glob("**/*.html")):
            yield p

    total = 0
    for p in iter_files():
        n, leftovers = convert_file(p, targets, args.dry_run)
        if n:
            report.append((p, n))
            total += n
        for raw in leftovers:
            print(f"  UNRESOLVED in {p}: {raw}", file=sys.stderr)

    if args.dry_run:
        print("DRY RUN")
    print(f"Converted {total} click URLs across {len(report)} files.")
    for p, n in report:
        print(f"  {n:4d}  {p}")
    if total == 0:
        print("Nothing to do.")


if __name__ == "__main__":
    main()