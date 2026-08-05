"""Pre-publish content check: scan generated pages for mojibake before shipping.

Usage:
    python scripts/check_publish_content.py            # scan docs/, exit 1 if issues
    python scripts/check_publish_content.py --fix      # auto-repair fixable mojibake
    python scripts/check_publish_content.py --path X   # scan a specific path

Catches the double-encoded UTF-8 corruption (decoded as cp1252 then re-encoded
as UTF-8) that previously shipped to the live site. Run before committing docs/.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.deployment import find_mojibake, repair_mojibake


def repair_bytes(data: bytes) -> bytes:
    return repair_mojibake(data.decode("utf-8")).encode("utf-8")


def scan_path(path: Path, fix: bool) -> tuple:
    """Return (remaining_hits, was_fixed) for one file."""
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        if not fix:
            return 1, 0
        # Non-UTF-8 bytes: try the latin-1 fallback decode the corruption used,
        # then re-encode cleanly.
        text = data.decode("latin-1")
        cleaned = text.encode("utf-8")
        path.write_bytes(cleaned)
        return 0, 1
    hits = find_mojibake(text)
    if not hits:
        return 0, 0
    if not fix:
        return len(hits), 0
    repaired = repair_bytes(data)
    path.write_bytes(repaired)
    remaining = len(find_mojibake(repaired.decode("utf-8")))
    return remaining, 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="auto-repair fixable mojibake")
    parser.add_argument("--path", default=None, help="path to scan (default: docs/)")
    args = parser.parse_args()

    root = Path(args.path) if args.path else Path(__file__).resolve().parents[1] / "docs"
    targets = sorted(root.rglob("*.html")) if root.is_dir() else [root]

    total_remaining = total_fixed = 0
    issues = []
    for p in targets:
        remaining, fixed = scan_path(p, args.fix)
        total_remaining += remaining
        total_fixed += fixed
        rel = p.relative_to(root) if root.is_dir() else p
        if remaining and not args.fix:
            issues.append(str(rel))
        elif fixed:
            print(f"  repaired: {rel}")

    if total_fixed:
        print(f"Repaired {total_fixed} file(s).")
        return 0 if total_remaining == 0 else 1

    if issues:
        print(f"\nMojibake found in {len(issues)} file(s):")
        for path in issues[:20]:
            print(f"  {path}")
        print("\nRun with --fix to auto-repair, or fix the generation source.")
        return 1

    print(f"OK: {len(targets)} file(s) checked, no mojibake detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
