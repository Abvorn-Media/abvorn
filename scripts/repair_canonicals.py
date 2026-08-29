"""repair_canonicals.py — deterministic canonical/og sweep over the docs tree.

Fixes the audit D1/D8 findings in already-built pages:

  * Any `https://Abvorn-Media.github.io` reference (canonical, og:url,
    breadcrumb JSON-LD, share links, images) → `https://abvorn.com`, so no
    committed page points at the dead GitHub Pages host.
  * Relative canonical/og:url (`href="/reviews/4k-monitors/"`) and relative
    og:image/twitter:image (`content="/assets/logo.png"`) → absolute
    `https://abvorn.com/...`, so social previews and search crawlers get a
    fully-qualified URL.

Modes:
  default        apply fixes in place
  --verify       report remaining problem references; exit 0 if clean
  --path <file>  operate on a single file instead of the whole tree

CRLF is preserved: files are read/written with newline="" so Windows line
endings on dated articles are untouched. UTF-8 is declared on every open.
"""
import argparse
import os
import re
import sys
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"
GOOD_HOST = "https://abvorn.com"
BAD_HOST = "https://Abvorn-Media.github.io"

# Only these attributes should be absolutized; nav/search hrefs stay relative.
# Consume the leading "/" and re-emit it as host + "/" so the value becomes
# "https://abvorn.com/<path>" rather than "/https://abvorn.com<path>".
ABSOLUTIZE_PATTERNS = (
    (re.compile(r'(rel="canonical" href=")/'), r"\1" + GOOD_HOST + "/"),
    (re.compile(r'(property="og:url" content=")/'), r"\1" + GOOD_HOST + "/"),
    (re.compile(r'(property="og:image" content=")/'), r"\1" + GOOD_HOST + "/"),
    (re.compile(r'(name="twitter:image" content=")/'), r"\1" + GOOD_HOST + "/"),
)


def _iter_html_files(root: Path):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".html"):
                yield Path(dirpath) / name


def repair_text(text: str) -> tuple:
    """Return (repaired_text, changes). Case-insensitive for the stale host."""
    changes = 0
    host_rx = re.compile(re.escape(BAD_HOST), re.IGNORECASE)
    new_text, n = host_rx.subn(GOOD_HOST, text)
    changes += n
    for rx, repl in ABSOLUTIZE_PATTERNS:
        new_text, n = rx.subn(repl, new_text)
        changes += n
    return new_text, changes


def scan_problems(text: str) -> list:
    """Return a list of problem references still present in text."""
    problems = []
    if re.search(re.escape(BAD_HOST), text, re.IGNORECASE):
        problems.append(BAD_HOST)
    for rx, _repl in ABSOLUTIZE_PATTERNS:
        if rx.search(text):
            problems.append(rx.pattern[:48])
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true",
                        help="report remaining problem references without editing")
    parser.add_argument("--path", type=str, default="",
                        help="single file to inspect instead of the whole docs tree")
    args = parser.parse_args()

    if args.path:
        files = [Path(args.path)]
    else:
        files = sorted(_iter_html_files(DOCS_ROOT))

    total_changes = 0
    dirty = 0
    for f in files:
        if not f.exists():
            print(f"MISSING: {f}")
            sys.exit(2)
        text = f.read_text(encoding="utf-8", newline="")
        problems = scan_problems(text)
        if not problems:
            continue
        if args.verify:
            print(f"  {f.relative_to(DOCS_ROOT.parent)}: {', '.join(problems)}")
            dirty += 1
            continue
        new_text, n = repair_text(text)
        if n:
            f.write_text(new_text, encoding="utf-8", newline="")
            total_changes += n
            print(f"  fixed {n:>3} ref(s): {f.relative_to(DOCS_ROOT.parent)}")

    if args.verify:
        print(f"checked {len(files)} files; {dirty} still reference stale/relative URLs" if dirty else
              f"checked {len(files)} files; all canonical/og references are absolute on {GOOD_HOST}")
        sys.exit(1 if dirty else 0)
    print(f"done: {total_changes} reference(s) repaired across {len(files)} html file(s)")
    sys.exit(0)


if __name__ == "__main__":
    main()