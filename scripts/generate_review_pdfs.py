#!/usr/bin/env python3
"""Generate review PDFs for every dated review page on disk.

Read-only over the existing HTML: for each docs/reviews/*/<article>.html it
renders a clean print PDF next to it. index.html is skipped — it mirrors the
newest dated article, whose PDF is generated from that article's own page.

Used as a one-off backfill (and anytime a PDF is missing):
    python scripts/generate_review_pdfs.py            # only missing PDFs
    python scripts/generate_review_pdfs.py --force    # regenerate everything
Exit code 0 = all good; 1 = WeasyPrint unavailable (CI/box must install system
libs) or renderer-side hard failure.
"""
from __future__ import annotations

import argparse
import re
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.review_pdf import build_review_page_pdf, review_pdf_available  # noqa: E402

DOCS = ROOT / "docs" / "reviews"
TITLE_RE = re.compile(r"<title>(.*?)(?:\s*\|\s*Abvorn)?</title>", re.S | re.I)


def _niche_name(slug):
    return slug.replace("-", " ").title()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate PDFs even where one already exists on disk.",
    )
    args = parser.parse_args()
    if not review_pdf_available():
        print("ERROR: WeasyPrint/beautifulsoup4 not available (install libpango etc.)")
        return 1
    pages = sorted(DOCS.glob("*/*.html"))
    built = skipped = 0
    for page in pages:
        if page.name == "index.html":
            continue
        pdf = page.with_suffix(".pdf")
        if pdf.exists() and pdf.stat().st_size > 0 and not args.force:
            skipped += 1
            continue
        try:
            page_html = page.read_text(encoding="utf-8")
            m = TITLE_RE.search(page_html)
            title = re.sub(r"\s+", " ", unescape(m.group(1))).strip() if m else page.stem
            data = build_review_page_pdf(
                page_html,
                title=title,
                niche_name=_niche_name(page.parent.name),
                base="https://abvorn.com",
            )
            if not data:
                print(f"  SKIP (render failed): {pdf.relative_to(ROOT)}")
                continue
            pdf.write_bytes(data)
            print(f"  Built: {pdf.relative_to(ROOT)} ({len(data) // 1024} KiB)")
            built += 1
        except Exception as exc:
            print(f"  ERROR {pdf.relative_to(ROOT)}: {exc}")
    print(f"Done. Built {built} PDFs, skipped {skipped} existing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())