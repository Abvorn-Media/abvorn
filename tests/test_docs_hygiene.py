"""Regression guard for published-docs hygiene (live-site P0 fixes).

- console.html (internal dashboard) must stay gitignored + untracked, so a
  whole-tree `git add docs/` can never ship it.
- No published page may define window.loadAnalytics twice: the second IIFE
  fires a duplicate GA4 pageview for consented visitors.
- No published page may contain a fabricated first-hand testing / invented
  sales claim (the FABRICATED_TESTING_CLAIM copyguard rule is a hard block on
  pages, so a regression here would also fail the next rebuild).
"""
import subprocess
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"


def _docs_pages():
    return sorted(DOCS.glob("**/*.html"))


def test_console_html_is_gitignored_and_untracked():
    # NOTE: deliberately no exists() assertion. docs/console.html is an
    # ignored, untracked developer file, so it is absent on a clean CI
    # checkout -- asserting it exists would fail everywhere but this machine.
    # What must hold is the *ignore* rule, which git resolves for paths that
    # are not on disk.
    ignored = subprocess.run(
        ["git", "check-ignore", "docs/console.html"], cwd=DOCS.parent,
        capture_output=True, text=True,
    )
    assert ignored.returncode == 0, "docs/console.html must stay gitignored"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "docs/console.html"],
        cwd=DOCS.parent, capture_output=True, text=True,
    )
    assert tracked.returncode != 0, "docs/console.html must never be tracked"


def test_no_duplicate_ga_loader():
    for page in _docs_pages():
        n = page.read_text(encoding="utf-8", errors="replace").count(
            "window.loadAnalytics=function()"
        )
        assert n <= 1, f"{page} defines loadAnalytics {n}x (double GA4 fire)"


def test_no_fabricated_testing_or_sales_claims():
    from abvorn.core.copyguard import _fabricated_claim_issues
    offenders = {}
    for page in _docs_pages():
        html = page.read_text(encoding="utf-8", errors="replace")
        issues = _fabricated_claim_issues(html)
        if issues:
            offenders[page.name] = len(issues)
    assert not offenders, f"fabricated claims in published pages: {offenders}"


def test_false_claim_repair_yields_clean_prose():
    """Redaction must leave readable sentences, not word salad.

    The rewrite rules are order-sensitive: a generic "N units in the past
    month" pattern placed ahead of the verb-aware one consumes only the
    numeric tail and leaves "moved over strong ongoing sales". Each case
    below is a real phrasing seen in the tree; the assertions cover both the
    complete removal of the claim and the absence of the doubled-preposition
    / doubled-auxiliary grammar artifacts.
    """
    import re

    from scripts.repair_false_claims import DETECT, REWRITES

    cases = [
        "It has been moving over 3 000 units in the past month.",
        "The seller moved over 10K+ units in the past month.",
        "Gear shifts over 8 500 units in the past month, so it is a safe bet.",
        "It ships over 5,000 units in the past month.",
        "<p><strong>50K+</strong> units sold in the past month</p>",
        "Sales: 20K+ bought in past month",
    ]
    # "over/around <qualifier>" and "<aux> has <qualifier>" are both
    # impossible results of a well-formed rewrite.
    artifacts = re.compile(
        r"\b(?:over|around|about|roughly)\s+(?:strong|recent|ongoing)\b"
        r"|\b(?:has|have|is|are|been)\s+(?:has|have|been)\b",
        re.I,
    )
    for src in cases:
        out = src
        for rx, repl in REWRITES:
            out = rx.sub(repl, out)
        residue = [p.pattern for p in DETECT if p.search(out)]
        assert not residue, f"{src!r} still matches {residue} after repair"
        assert not artifacts.search(out), (
            f"{src!r} repaired to ungrammatical {out!r}"
        )


def test_extended_rewrite_covers_scraped_sales_and_testing_phrases():
    """The live corpus carries figure/test phrasings beyond the curated list.

    These are the shapes that survived a plain REWRITES pass on the 623 legacy
    pages; rewrite_page() must clear them without touching honest disclaimers.
    """
    from abvorn.core.copyguard import _fabricated_claim_issues
    from scripts.repair_false_claims import rewrite_page

    cases = [
        "<li><strong>Sales:</strong> 6K+ units sold</li>",
        "<li>Sales: 6,000+ units sold in the last month</li>",
        "<li><strong>Sales:</strong> 10\u202fK+ bought past month</li>",
        "<li>Monthly sales: 10,000+ units</li>",
        "<p>Over 10,000 units sold in the last month prove its popularity.</p>",
        "<p>300k+ units sold.</p>",
        "<p><strong>Independent lab testing</strong> confirms sensor accuracy.</p>",
        "<p>We have tested, analyzed, and compared the top-rated options.</p>",
        "<p>Each product went through a standardized test bench.</p>",
    ]
    for src in cases:
        out = rewrite_page(src)
        assert not _fabricated_claim_issues(out), f"{src!r} still flagged: {out!r}"

    # A negated disclosure is honest copy and must survive verbatim.
    disclaimer = "<p>No hands-on lab testing was performed.</p>"
    assert rewrite_page(disclaimer) == disclaimer


# def test_repair_leaves_negated_disclaimers_alone():
