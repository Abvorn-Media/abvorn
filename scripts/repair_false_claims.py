"""Remove fabricated testing/sales claims from generated pages.

Abvorn does not run lab tests and has no internal sales numbers, yet early LLM
drafts shipped claims like "Based on our testing", "We tested the X side by
side", "How We Tested These Products", and "Sales: 4K+ units sold in the past
month". This script rewrites them to honest equivalents site-wide so the live
tree carries no unverifiable first-person testing or sales claims.

The copyguard FABRICATED_TESTING_CLAIM rule (abvorn/core/copyguard.py) blocks
these phrases from being *written*; this script removes the ones already
published.

Usage:
    python scripts/repair_false_claims.py            # scan, print remaining count
    python scripts/repair_false_claims.py --fix      # rewrite in place
    python scripts/repair_false_claims.py --path X   # single file/dir
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from abvorn.core.copyguard import (
    _PAGE_BLOCKING_RULES,
    _FABRICATED_CLAIM_RES,
    check_text,
    enabled,
    html_to_text,
)

# Curated rewrites. Order matters: longer phrases first so "we've tested and
# researched" is not half-matched by "we tested".
REWRITES = [
    # Headings: "How We Tested These Products" -> comparison/research framing.
    (re.compile(r'<(h2)([^>]*id=")how-we-tested-', re.I),
     r"<\1\2how-we-compared-"),
    (re.compile(r'([#]how-we-tested-)', re.I), r"\1"),
    (re.compile(r"how-we-tested-(these-(?:wireless-)?[a-z-]+)", re.I),
     r"how-we-compared-\1"),
    (re.compile(r"How We Tested These ([^<]{1,60}?)", re.I),
     r"How We Compared These \1"),
    (re.compile(r"How We Tested", re.I), "How We Compared"),
    # Body claims.
    (re.compile(r"Based on our testing", re.I), "Based on our research"),
    (re.compile(r"We'?ve? tested and researched", re.I), "We've researched and compared"),
    (re.compile(r"We'?ve? tested and analyzed", re.I), "We've researched and analyzed"),
    (re.compile(r"We tested real-world performance", re.I), "We compared real-world value"),
    (re.compile(r"We tested and researched", re.I), "We compared and researched"),
    (re.compile(r"We tested too", re.I), "We compared too"),
    (re.compile(r"We tested", re.I), "We compared"),
    (re.compile(r"we'?ve? tested", re.I), "we've compared"),
    (re.compile(r"we tested", re.I), "we compared"),
    # Sales figures (scraper-to-LLM transcription of "bought in past month").
    (re.compile(
        r"\s*<li>\s*<strong>Sales(?: Volume)?:</strong>[^<]*?(?:"
        r"units? sold in the past month|units?/[a-z]+|bought in(?: the)? past month)"
        r"[^<]*?</li>", re.I),
     ""),
    (re.compile(
        r"\s*<li>\s*\d[\d.,]*[kK]?\+?\s+(?:units?|bought)"
        r"(?:\s+sold)?\s+in\s+(?:the\s+)?(?:past\s+month|month)[^<]*?</li>",
        re.I),
     ""),
    (re.compile(
        r"<strong>Sales(?: Volume)?:</strong>\s*\d[\d.,]*[kK]?\+?\s+"
        r"(?:units?|bought)(?:\s+sold)?\s+(?:in\s+(?:the\s+)?past\s+month|monthly)",
        re.I),
     "strong ongoing sales"),
    (re.compile(
        r"\d[\d.,]*[kK]?\+?\s+units?\s+(?:sold|bought)"
        r"\s+in\s+(?:the\s+)?past\s+month", re.I),
     "strong ongoing sales"),
    (re.compile(
        r"\d[\d.,]*[kK]?\+?\s+units?\s+(?:sold|bought)\s+monthly", re.I),
     "strong ongoing sales"),
    (re.compile(
        r"(?:in|over|about)\s+\d[\d.,]*[kK]?\+?\s+units?\s+sold\s+last\s+month",
        re.I),
     "strong recent sales"),
    (re.compile(
        r"\d[\d.,]*[kK]?\+?\s+units?\s+\w+\s+recently", re.I),
     "recent strong sales"),
    (re.compile(
        r"<td>\s*\d[\d.,]*[kK]?\+?\s+units?\s+(?:sold\s+)?bought[^<]*?</td>", re.I),
     "<td>—</td>"),
    (re.compile(
        r"<td>\s*\d[\d.,]*[kK]?\+?\s+(?:units?|bought)\s+"
        r"(?:in\s+)?(?:the\s+)?(?:past\s+month|monthly)[^<]*?</td>", re.I),
     "<td>—</td>"),
    (re.compile(
        r"\d[\d.,]*[kK]?\+?\s+units?\s+(?:sold|bought)\s+last\s+month", re.I),
     "strong recent sales"),
    (re.compile(
        r"over\s+an?\s+(?:[\w.,-]+)\s+units?\s+(?:sold|bought)\s+"
        r"in\s+(?:the\s+)?past\s+month", re.I),
     "strong ongoing sales"),
    (re.compile(
        r"(?:<strong>\s*)?\d[\d.,]*[kK]?\+?(?:\s*</strong>)?\s*units?\s+"
        r"(?:sold|bought)\s+recently", re.I),
     "recent strong sales"),
    # Markup-split figure with an explicit "in the past month" tail:
    # "<strong>50K+</strong> units sold in the past month". The <strong> tags
    # are REQUIRED here (unlike the "recently" rule above, which cannot
    # collide with the verb rule). Optional tags would make this a plain-text
    # duplicate of the generic rule below and it would pre-empt the verb rule,
    # turning "ships over 5,000 units in the past month" into
    # "ships over strong ongoing sales".
    (re.compile(
        r"<strong>\s*\d[\d.,]*(?:[\s\u00a0\u202f]\d{3})*[kK]?\+?\s*</strong>\s*units?\s+"
        r"(?:sold\s+)?(?:in\s+(?:the\s+)?past\s+month|monthly)", re.I),
     "strong ongoing sales"),
    # Drop a leading perfect-continuous auxiliary so the verb rule below can
    # supply its own "has": "has been moving over 3 000 units" must not become
    # "has been has strong ongoing sales".
    (re.compile(
        r"\b(?:has|have|had)\s+been\s+(?=(?:mov|sell|ship|shift))", re.I),
     ""),
    # "<verb> over/around N units in the past month" -> drop the verb+figure
    # and keep a clean predicate ("moved over 3 000 units in the past month"
    # -> "has strong ongoing sales"). This MUST stay ahead of the generic
    # "N units in the past month" rule below: that one would otherwise consume
    # only the numeric tail and leave "moved over strong ongoing sales".
    (re.compile(
        r"\b(?:mov(?:e|ed|ing)|sell(?:s|ing|sold)|ship(?:s|ped|ping)|"
        r"selling|shipped|shift(?:s|ed|ing))\s+(?:over|around|about|roughly)?\s*"
        r"[0-9.,]+(?:[\s\u00a0\u202f]\d{3})*k?\s*\+?\s*"
        r"(?:units?|bought)\s+(?:sold\s+)?(?:in\s+(?:the\s+)?past\s+month|monthly)",
        re.I),
     "has strong ongoing sales"),
    (re.compile(
        r"\d[\d.,]*(?:[\s\u00a0\u202f]\d{3})*k?\+?\s+units?\s+in\s+(?:the\s+)?past\s+month", re.I),
     "strong ongoing sales"),
    (re.compile(
        r"\b[0-9.,]+k?\s*\+?\s*(?:units?|bought)\s+(?:sold\s+in\s+(?:the\s+)?past\s+month|in\s+(?:the\s+)?past\s+month)\b", re.I),
     "strong ongoing sales"),
]

# Patterns used to detect anything still present after repair. Reuse the
# copyguard FABRICATED_TESTING_CLAIM patterns so this scan agrees exactly with
# the rule that hard-blocks these phrases from being *written*; the narrower
# list below only adds the heading/anchor forms copyguard does not model.
DETECT = list(_FABRICATED_CLAIM_RES) + [
    re.compile(r"based on our testing", re.I),
    re.compile(r"we'?ve?\s+tested|we\s+tested", re.I),
    re.compile(r"units?\s+sold|units?/month|bought in(?: the)? past month", re.I),
    re.compile(r"sales:\s*[0-9.,]+k?\+?", re.I),
    re.compile(r"how we tested", re.I),
]


def rewrite_page(text: str) -> str:
    out = text
    for pat, repl in REWRITES:
        out = pat.sub(repl, out)
    return out


def count_remaining(text: str) -> int:
    return sum(len(p.findall(text)) for p in DETECT)


def scan_file(path: Path, fix: bool) -> tuple:
    """Return (found, remaining, fixed) for one file after an optional rewrite."""
    text = path.read_text(encoding="utf-8")
    found = count_remaining(text)
    if found == 0:
        return 0, 0, 0
    if not fix:
        return found, found, 0
    rewritten = rewrite_page(text)
    remaining = count_remaining(rewritten)
    changed = rewritten != text
    if changed:
        path.write_text(rewritten, encoding="utf-8")
    return found, remaining, 1 if changed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="rewrite claims in place")
    parser.add_argument("--path", default=None, help="path to scan (default: docs/)")
    args = parser.parse_args()

    root = Path(args.path) if args.path else Path(__file__).resolve().parents[1] / "docs"
    targets = sorted(root.rglob("*.html")) if root.is_dir() else [root]

    total_found = total_remaining = total_fixed = 0
    issues = []
    for p in targets:
        found, remaining, fixed = scan_file(p, args.fix)
        total_found += found
        total_remaining += remaining
        total_fixed += fixed
        rel = p.relative_to(root) if root.is_dir() else p
        if found and not args.fix:
            issues.append(str(rel))
        elif fixed:
            print(f"  rewrote: {rel}")

    if total_fixed:
        print(f"Rewrote {total_fixed} file(s); {total_remaining} claim(s) remaining.")
        return 0 if total_remaining == 0 else 1

    if issues:
        print(f"\nFabricated claims in {len(issues)} file(s) ({total_found} occurrences):")
        for path in issues[:25]:
            print(f"  {path}")
        print("\nRun with --fix to rewrite, or fix the generation source.")
        return 1

    print(f"OK: {len(targets)} file(s) checked, no fabricated claims.")
    return 0


if __name__ == "__main__":
    sys.exit(main())