"""check_copy.py — scan copy with the pre-publish LanguageTool gate.

Runs the same copyguard used at the social/email/page publish boundaries, so
you can spot-check any text, file, or directory before committing:

    python scripts/check_copy.py "This is an test"
    python scripts/check_copy.py --file some/copy.txt
    python scripts/check_copy.py --dir docs/reviews/laptops
    python scripts/check_copy.py --mode block --file script.json

Exit codes:
    0 = clean (report mode passes regardless of findings)
    1 = blocking issue found (--mode block) or any issue (--strict, report mode)
    2 = LanguageTool server unreachable (--ensure-server could not start it)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from abvorn.core.copyguard import gate_copy, html_to_text

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_SERVER_UNAVAILABLE = 2

SCAN_EXTENSIONS = {".html", ".txt", ".md", ".json"}


def _load(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".html":
        return html_to_text(raw)
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_copy.py",
        description="Scan copy with the self-hosted LanguageTool gate "
                    "(the same checks the social/email/page publish boundaries run).",
    )
    parser.add_argument("text", nargs="?", help="inline text to check")
    parser.add_argument("--file", type=Path, help="check a single text/html/json file")
    parser.add_argument("--dir", type=Path, help="recursively scan a directory")
    parser.add_argument("--mode", choices=["report", "block"], default="report",
                        help="report = log findings but never fail (default); "
                             "block = exit 1 on blocking-severity issues")
    parser.add_argument("--strict", action="store_true",
                        help="with --mode report, exit 1 on ANY flagged issue")
    parser.add_argument("--ensure-server", action="store_true",
                        help="start the LanguageTool server if it is not running")
    args = parser.parse_args(argv)

    sources: list[tuple[str, str]] = []
    if args.dir:
        for p in sorted(args.dir.rglob("*")):
            if p.suffix.lower() in SCAN_EXTENSIONS and p.is_file():
                sources.append((str(p), _load(p)))
    elif args.file:
        sources.append((str(args.file), _load(Path(args.file))))
    elif args.text is not None:
        sources.append(("inline", args.text))
    else:
        parser.error("provide text, --file, or --dir")

    if args.ensure_server:
        from abvorn.core.copyguard import ensure_server
        if not ensure_server():
            print("ERROR: LanguageTool server not reachable and could not be started",
                  file=sys.stderr)
            return EXIT_SERVER_UNAVAILABLE

    any_blocked = False
    any_issues = False
    for label, text in sources:
        if not text.strip():
            print(f"{label}: (empty, skipped)")
            continue
        res = gate_copy(text, label, mode=args.mode)
        count = len(res.issues)
        if count:
            any_issues = True
            print(f"{label}: {count} issue(s) — review the warnings above")
        else:
            print(f"{label}: ok")
        if args.mode == "block" and not res.ok:
            any_blocked = True

    if args.mode == "block" and any_blocked:
        return EXIT_FINDINGS
    if args.mode == "report" and args.strict and any_issues:
        return EXIT_FINDINGS
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())