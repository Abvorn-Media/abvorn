"""Render a review page as a clean, printable PDF.

Takes a fully-rendered review page (as produced by run_cycle.build_article_page),
finds the article body, strips the web chrome (nav, CTA, reactions, share,
charts, remote images), and reflows the review through WeasyPrint into a
branded A4 PDF.

WeasyPrint and its system libraries (libpango, etc.) are only required at
render time; every environment is expected to degrade gracefully to "no PDF".
"""
from __future__ import annotations

import logging
from html import escape as html_escape

_log = logging.getLogger("review_pdf")

try:
    from bs4 import BeautifulSoup
    _BS4_OK = True
except Exception:  # pragma: no cover - import guard
    BeautifulSoup = None
    _BS4_OK = False

try:
    from weasyprint import HTML  # noqa: F401  (imported lazily below as well)
    _WEASYPRINT_OK = True
except Exception:
    _WEASYPRINT_OK = False


def review_pdf_available() -> bool:
    """True when this environment can actually render PDFs (bs4 + weasyprint)."""
    return _BS4_OK and _WEASYPRINT_OK


_PRINT_CSS = """
@page {
    size: A4;
    margin: 14mm 13mm 16mm 13mm;
    @bottom-left { content: "abvorn.com"; color: #999; font-size: 7pt; }
    @bottom-right { content: "Page " counter(page) " of " counter(pages); color: #999; font-size: 7pt; }
}
html, body {
    font-family: 'DejaVu Sans', 'Liberation Sans', 'Helvetica', 'Arial', sans-serif;
    font-size: 9.5pt; line-height: 1.55; color: #161618; margin: 0; padding: 0;
}
.pdf-cover { border-top: 4pt solid #c98a2c; padding-top: 10pt; margin-bottom: 12pt; }
.pdf-cover .pdf-kicker {
    font-size: 8pt; letter-spacing: .09em; text-transform: uppercase;
    color: #c98a2c; font-weight: 700;
}
.pdf-cover h1 {
    font-family: 'DejaVu Serif', 'Liberation Serif', Georgia, serif;
    font-size: 19pt; line-height: 1.25; margin: 6pt 0 5pt; color: #0f0f12;
}
.pdf-cover .pdf-sub { color: #777; font-size: 8pt; }
.pdf-rule { border-bottom: .5pt solid #ddd; margin-bottom: 10pt; }

.article-intro { font-size: 11pt; color: #2a2a2f; font-weight: 500; }

h2 {
    font-family: 'DejaVu Serif', 'Liberation Serif', Georgia, serif;
    font-size: 13.5pt; color: #0f0f12; margin: 13pt 0 5pt;
    border-bottom: .5pt solid #e8e8e8; padding-bottom: 3pt;
    page-break-after: avoid;
}
h3 { font-size: 10.5pt; margin: 9pt 0 4pt; color: #1a1a1e; page-break-after: avoid; }
p { margin: 0 0 6pt; }
ul, ol { margin: 0 0 6pt; padding-left: 14pt; }
li { margin: 0 0 2pt; }
a { color: #1a5f8f; text-decoration: none; }
strong { font-weight: 700; }
blockquote { border-left: 2.5pt solid #c98a2c; margin: 7pt 0; padding: 2pt 0 2pt 10pt; color: #444; font-style: italic; }
figure { margin: 6pt 0; page-break-inside: avoid; }
img { display: none !important; }

.disclosure {
    font-size: 7.5pt; color: #6b6b70; border: .5pt dashed #ccc; border-radius: 3pt;
    padding: 5pt 7pt; margin: 0 0 9pt;
}

.verdict-box {
    border: .6pt solid #c98a2c; border-left: 3pt solid #c98a2c; border-radius: 5pt;
    padding: 8pt 10pt; margin: 9pt 0; background: #fbf7ef; page-break-inside: avoid;
}
.verdict-box .verdict-title { font-size: 12pt; font-weight: 700; color: #0f0f12; margin: 0 0 3pt; }
.verdict-box .verdict-price { color: #b0721a; font-weight: 700; font-size: 10pt; margin: 2pt 0 5pt; }
.verdict-box .verdict-for, .verdict-box .verdict-not-for { font-size: 9pt; margin: 2pt 0; }
.verdict-box .buy-btn, .verdict-box .btn, .btn, .buy-btn {
    display: inline-block; border: .6pt solid #c98a2c; background: #fff;
    color: #7a4e0a; font-weight: 700; font-size: 8pt; padding: 3pt 9pt;
    border-radius: 3pt; margin: 4pt 5pt 4pt 0;
}

table { width: 100%; border-collapse: collapse; font-size: 8.3pt; margin: 6pt 0 9pt; }
th, td { border: .45pt solid #dcdce0; padding: 4pt 6pt; vertical-align: top; text-align: left; }
th { background: #f3f3f5; font-weight: 700; }
.table-wrap { display: block; margin: 8pt 0; overflow: visible; }

.warm-product-card {
    border: .6pt solid #e2e2e6; border-radius: 5pt; padding: 8pt 10pt;
    margin: 6pt 0 9pt; page-break-inside: avoid;
}
.warm-product-card__media { display: none !important; }
.warm-product-card__name { font-size: 10.8pt; margin: 0 0 2pt; color: #0f0f12; }
.warm-product-card__price { color: #b0721a; font-weight: 700; font-size: 9.5pt; margin: 0 0 3pt; }
.warm-product-card__summary { font-size: 8.8pt; color: #333; margin: 3pt 0 4pt; }

.faq-section { margin-top: 12pt; }
.faq-item { margin: 5pt 0; page-break-inside: avoid; }
.faq-q { font-weight: 700; color: #0f0f12; margin: 7pt 0 2pt; }
.faq-answer, .faq-a { margin: 0 0 4pt 8pt; }
summary { display: none; }
details { display: block; }

.product-shot { display: block; margin: 7pt 0; page-break-inside: avoid; }
.product-shot__badge {
    display: block; font-size: 7.5pt; font-weight: 700; letter-spacing: .06em;
    color: #c98a2c; text-transform: uppercase; margin-bottom: 2pt;
}
.product-shot figcaption { font-size: 8pt; color: #555; margin-top: 2pt; }

.cta-banner, .reactions-bar, .share-row, .share-buttons, .related-cats,
.further-reading, canvas, [class*="chart"], svg, form, script, style { display: none !important; }
"""

_DOC_TPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{TITLE}</title>
<style>{CSS}</style>
</head>
<body>
{COVER}
<article class="pdf-body">{BODY}</article>
</body>
</html>"""

_CHROME_SELECTORS = (
    ".cta-banner",
    ".reactions-bar",
    ".share-row",
    ".share-buttons",
    ".related-cats",
    ".further-reading",
    ".price-chart",
    ".chart-wrapper",
    "[class*='chart']",
)


def _parse_title(page_html, fallback=""):
    try:
        soup = BeautifulSoup(page_html, "html.parser")
        t = soup.find("title")
        if t and t.get_text(strip=True):
            return t.get_text(strip=True).replace(" | Abvorn", "").strip()
    except Exception:
        pass
    return fallback


def _refine(soup, art):
    """Mutate the parsed article body into a print-friendly document."""
    for sel in _CHROME_SELECTORS:
        for el in art.select(sel):
            el.decompose()
    for tag in art.select("script, style, canvas, svg, form, img, iframe, video, audio, noscript"):
        tag.decompose()
    # <details>/<summary> (FAQ) render empty in WeasyPrint -> flatten to blocks.
    for d in art.select("details.faq-item"):
        d.name = "div"
        d.attrs.clear()
        for s in d.select("summary"):
            s.name = "div"
            s["class"] = "faq-q"
        for a in d.select(".faq-answer"):
            a["class"] = (a.get("class") or []) + ["faq-a"]
    # Product cards hide their blurb in data-description; surface it for print.
    for card in art.select(".warm-product-card[data-description]"):
        desc = (card.get("data-description") or "").strip()
        if not desc:
            continue
        p = soup.new_tag("p")
        p["class"] = "warm-product-card__summary"
        p.string = desc
        price = card.find(class_="warm-product-card__price")
        if price:
            price.insert_after(p)
        else:
            card.insert(2, p)
    return art


def build_review_page_pdf(page_html, *, title="", niche_name="", base="https://abvorn.com"):
    """Extract the article body from a rendered review page and render PDF bytes.

    Returns ``bytes`` on success and ``None`` when WeasyPrint is unavailable or
    the render fails — callers must skip PDF generation gracefully.
    """
    if not review_pdf_available():
        _log.debug("WeasyPrint/beautifulsoup not available on this platform")
        return None
    try:
        from weasyprint import HTML
    except Exception as exc:  # pragma: no cover - environment guard
        _log.warning("WeasyPrint import failed: %s", exc)
        return None
    try:
        soup = BeautifulSoup(page_html, "html.parser")
        art = soup.find("article", class_="article-body")
        if art is None:
            _log.warning("No article-body found; skipping PDF")
            return None
        art = _refine(soup, art)
        title = title.strip() or _parse_title(page_html, niche_name)
        cover = ""
        if title:
            cover = (
                '<div class="pdf-cover">'
                f'<div class="pdf-kicker">Abvorn &middot; {html_escape(niche_name or "Review")}</div>'
                f"<h1>{html_escape(title)}</h1>"
                f'<div class="pdf-sub">Independent testing and reviews &middot; {html_escape(base.rstrip("/"))}</div>'
                "</div>"
                '<div class="pdf-rule"></div>'
            )
        doc = (
            _DOC_TPL.replace("{TITLE}", html_escape(title))
            .replace("{CSS}", _PRINT_CSS)
            .replace("{COVER}", cover)
            .replace("{BODY}", str(art))
        )
        return HTML(string=doc, base_url=base).write_pdf()
    except Exception as exc:
        _log.warning("PDF render failed for %s: %s", title or page_html[:40], exc)
        return None