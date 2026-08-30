"""One-off: swap the mailto 'Email this review' rail card for the new
email-me-the-PDF form on every existing review page, and inject the guide JS.

Idempotent: already-patched pages only get their `const payload` PDF url
repaired (the canonical on review pages is a directory URL, so the PDF name
must come from the page filename, matching rebuild_reviews.py). Mirrors the
generator output in src/warm_editorial.py + run_cycle.py so the next
content-cycle regen produces identical HTML.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.warm_editorial import WARM_EMAIL_GUIDE_JS

DOCS = Path(__file__).resolve().parents[1] / "docs"

NEW_CARD = """        <div class="rail-card">
            <p class="rail-card__title">Email this review</p>
            <p>Send yourself the full guide as a PDF &mdash; every score, price, and verdict &mdash; straight to your inbox.</p>
            <form id="email-guide-form" onsubmit="submitEmailGuide(event)">
                <input type="text" name="_gotcha" style="display:none" tabindex="-1" autocomplete="off" aria-hidden="true">
                <label for="email-guide-email" class="sr-only">Email address</label>
                <input type="email" id="email-guide-email" class="input" placeholder="you@example.com" required>
                <button type="submit" class="btn btn--ink">Email Me the PDF</button>
                <p class="subscribe-msg" id="email-guide-msg" aria-live="polite"></p>
            </form>
        </div>"""

OLD_CARD_RE = re.compile(
    r'<div class="rail-card">\s*<p class="rail-card__title">Email this review</p>.*?</div>',
    re.S,
)
PAYLOAD_RE = re.compile(r"const payload = \{.*?\};", re.S)
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]+)">')
TITLE_RE = re.compile(r"<title>(.*?)\s*\| Abvorn</title>", re.S)
NICHE_NAME_RE = re.compile(r"lead_magnet:\s*'([^']+?) updates'")
BODY_RE = re.compile(r"</body>", re.I)


def pdf_stem_for(page: Path) -> str:
    if page.name == "index.html":
        dated = [p for p in page.parent.glob("*.html") if p.name != "index.html"]
        if not dated:
            return page.stem
        best = None
        best_date = ""
        for p in dated:
            h = p.read_text(encoding="utf-8")
            m = TITLE_RE.search(h)
            # published date tag on the page heading: "Published Mar 05, 2026"
            dm = re.search(r"Published\s+([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})", h)
            d = dm.group(1) if dm else ""
            if d > best_date:
                best_date, best = d, p.stem
        return best or page.parent.name
    return page.stem


def main() -> int:
    pages = sorted(DOCS.rglob("*.html"))
    changed = skipped = errors = 0
    for page in pages:
        try:
            html = page.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ERR read {page}: {e}")
            errors += 1
            continue

        already = "email-guide-form" in html and "submitEmailGuide" in html

        m = TITLE_RE.search(html)
        title = m.group(1).strip() if m else page.stem
        niche_slug = page.parent.name
        m = NICHE_NAME_RE.search(html)
        niche_name = m.group(1).strip() if m else niche_slug
        m = CANON_RE.search(html)
        canonical = m.group(1) if m else ""
        pdf_url = f"https://abvorn.com/reviews/{niche_slug}/{pdf_stem_for(page)}.pdf"

        if not already:
            if OLD_CARD_RE.search(html) is None:
                print(f"  SKIP (no mailto card): {page.relative_to(DOCS)}")
                skipped += 1
                continue
            html = OLD_CARD_RE.sub(NEW_CARD, html, count=1)

        payload = json.dumps({
            "action": "pdf_guide",
            "slug": niche_slug,
            "title": title,
            "niche": niche_slug,
            "niche_name": niche_name,
            "source": "review_rail",
            "pdf_url": pdf_url,
            "guide_url": canonical or "",
        }, ensure_ascii=True)

        guide_js = WARM_EMAIL_GUIDE_JS.replace("__GUIDE_PAYLOAD__", payload)

        if already:
            if PAYLOAD_RE.search(html) is None:
                print(f"  ERR payload missing: {page.relative_to(DOCS)}")
                errors += 1
                continue
            html = PAYLOAD_RE.sub(lambda _m: "const payload = " + payload + ";", html, count=1)
        else:
            html = re.sub(BODY_RE, lambda _m: f"{guide_js}\n</body>", html, count=1)

        page.write_text(html, encoding="utf-8")
        changed += 1
        print(f"  {'repaired' if already else 'patched'}: {page.relative_to(DOCS)}")

    print(f"\nchanged={changed} skipped={skipped} errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())