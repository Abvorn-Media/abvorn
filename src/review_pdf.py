"""Render a review page as a clean, printable PDF.

Takes a fully-rendered review page (as produced by run_cycle.build_article_page),
finds the article body, strips the web chrome (nav, CTA, reactions, share), and
reflows the review through WeasyPrint into a branded A4 PDF that also carries:

- the Abvorn logo in the header of the first page (embedded as a data URI),
- the product images from the review body (re-enable the existing <img> tags),
- the Abvorn Verdict breakdown bars,
- the "Performance Breakdown" radar chart (the web version is a Chart.js
  <canvas>; here it is re-rendered as a static inline SVG image from the same
  JSON data embedded in the page),
- the Regret Probability widget (client-side JS on the web; re-computed here in
  Python from the embedded rps data using the default preference profile).

WeasyPrint and its system libraries (libpango, etc.) are only required at
render time; every environment is expected to degrade gracefully to "no PDF".
"""
from __future__ import annotations

import base64
import json
import logging
import math
from html import escape as html_escape
from pathlib import Path

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

_PKG_DIR = Path(__file__).resolve().parent
_BASE_DIR = _PKG_DIR.parent


def review_pdf_available() -> bool:
    """True when this environment can actually render PDFs (bs4 + weasyprint)."""
    return _BS4_OK and _WEASYPRINT_OK


# ── Regret Probability engine (Python port of the page JS, default profile) ──
_PREFS = {
    "sound_quality": "Sound Quality",
    "battery_life": "Battery Life",
    "comfort": "Comfort & Fit",
    "features": "Features & Tech",
    "value": "Value for Money",
    "performance": "Performance",
    "build_quality": "Build Quality",
    "ease_of_use": "Ease of Use",
    "design": "Design",
    "reliability": "Reliability",
    "accuracy": "Accuracy",
    "compatibility": "Compatibility",
}
_DEFAULT_PREFS = {"sound_quality": 5, "battery_life": 5, "comfort": 5, "features": 5, "value": 5}
_SEV_COLORS = {"low": "#3a8a5c", "moderate": "#d4a03e", "high": "#d4633e", "very_high": "#c0392b"}
_SEV_LABELS = {
    "low": "Low Regret Risk",
    "moderate": "Moderate Regret Risk",
    "high": "High Regret Risk",
    "very_high": "Very High Regret Risk",
}
_SEV_TIPS = {
    "low": "This product aligns well with your preferences.",
    "moderate": "Some of your priorities don't match this product.",
    "high": "This product may not be right for you.",
    "very_high": "Based on your preferences, this is likely the wrong choice.",
}


def _title_key(key):
    return " ".join(word.capitalize() for word in key.split("_"))


def _calc_regret(prefs, scores):
    """Port of the page's calcRegret(); returns regret/kicker/reasons dicts."""
    total_w = 0.0
    weighted_sum = 0.0
    reasons = []
    good = []
    poor = []
    for key, importance_raw in prefs.items():
        importance = min(10, max(0, importance_raw))
        label = _PREFS.get(key)
        if not label or label not in scores:
            continue
        prod_val = float(scores[label])
        diff = abs(importance - prod_val) / 10
        align = 1 - diff
        weighted_sum += align * importance
        total_w += importance
        if diff > 0.3:
            message = (
                f"You prioritize {_title_key(key)} ({importance:.0f}/10), "
                f"but this product scores {prod_val:.1f}/10."
            )
            reasons.append({"message": message, "severity": "mismatch" if diff > 0.6 else "notice"})
        if abs(importance - prod_val) <= 2 and importance >= 5:
            good.append({"label": _title_key(key), "val": f"{importance}/{prod_val:.1f}"})
        if abs(importance - prod_val) > 2 and importance >= 5:
            poor.append({"label": _title_key(key), "val": f"{importance}/{prod_val:.1f}"})
    align_score = weighted_sum / total_w if total_w else 0.0
    regret = min(1, max(0, 1 - align_score))
    if regret < 0.3:
        severity = "low"
    elif regret < 0.6:
        severity = "moderate"
    elif regret < 0.8:
        severity = "high"
    else:
        severity = "very_high"
    return {
        "regret_prob": round(regret * 1000) / 10,
        "align_score": round(align_score * 100) / 100,
        "reasons": reasons[:4],
        "good_matches": good[:3],
        "poor_matches": poor[:3],
        "severity": severity,
    }


def _rank_alternatives(primary_name, products):
    ranked = []
    for p in products:
        if p.get("name") == primary_name:
            continue
        pr = _calc_regret(_DEFAULT_PREFS, p.get("scores") or {})
        ranked.append({"name": p.get("name", ""), "prob": pr["regret_prob"], "price": p.get("price", "")})
    ranked.sort(key=lambda a: a["prob"])
    return ranked[:3]


def _render_rps(primary, products):
    """Static version of the web page's renderRPS() widget HTML."""
    reg = _calc_regret(_DEFAULT_PREFS, primary.get("scores") or {})
    sev = reg["severity"]
    color = _SEV_COLORS[sev]
    parts = ['<div id="abvorn-rps-widget"><div class="rps-container">']
    parts.append('<div class="rps-badge">Abvorn Regret Probability Score</div>')
    parts.append(f'<div class="rps-header" style="border-left-color:{color}">')
    parts.append(
        '<div class="rps-score">'
        f'<span class="rps-number" style="color:{color}">{reg["regret_prob"]:g}%</span>'
        f'<span class="rps-sev" style="color:{color}">{html_escape(_SEV_LABELS[sev])}</span>'
        "</div>"
    )
    parts.append(f'<div class="rps-product-name">For: {html_escape(primary.get("name", ""))}</div>')
    parts.append("</div>")
    if reg["reasons"]:
        parts.append('<div class="rps-reasons"><div class="rps-section-title">Why?</div>')
        for reason in reg["reasons"]:
            parts.append(f'<div class="rps-reason rps-{reason["severity"]}">{html_escape(reason["message"])}</div>')
        parts.append("</div>")
    parts.append(f'<div class="rps-tip">{html_escape(_SEV_TIPS[sev])}</div>')
    alts = _rank_alternatives(primary.get("name"), products)
    if alts:
        parts.append('<div class="rps-alt-title">Better alternatives based on your preferences:</div>')
        for alt in alts:
            alt_color = _SEV_COLORS["low" if alt["prob"] < 30 else "moderate" if alt["prob"] < 60 else "high"]
            parts.append(
                '<div class="rps-alt-item">'
                f'<span class="rps-alt-name">{html_escape(alt["name"])}</span>'
                f'<span class="rps-alt-prob" style="color:{alt_color}">Regret Risk: {alt["prob"]:g}%</span>'
                f'<span class="rps-alt-price">{html_escape(alt["price"])}</span>'
                "</div>"
            )
    parts.append(
        '<div class="rps-footer">Rated from Abvorn\'s default preference profile '
        "(5/10 weight on each factor). Personalise yours at abvorn.com.</div>"
    )
    parts.append("</div></div>")
    return "".join(parts)


# ── Performance Breakdown radar chart (static SVG, mirrors the Chart.js one) ──
def _radar_svg(breakdown):
    labels = list(breakdown)
    try:
        values = [float(breakdown[label]) for label in labels]
    except (TypeError, ValueError):
        return None
    if len(values) < 3:
        return None
    cx, cy, radius = 230, 205, 135
    n = len(values)
    points = []
    for i, value in enumerate(values):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        rr = radius * min(10, max(0, value)) / 10.0
        points.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))

    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 460 420" font-family="DejaVu Sans, sans-serif">']
    for score in (2, 4, 6, 8, 10):
        rr = radius * score / 10.0
        s.append(f'<circle cx="{cx}" cy="{cy}" r="{rr:.1f}" fill="none" stroke="#e9e7e2"/>')
        s.append(
            f'<text x="{cx - rr - 4:.1f}" y="{cy + 3:.1f}" text-anchor="end" '
            f'font-size="9" fill="#b3afa9">{score}</text>'
        )
    for i, label in enumerate(labels):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        x2 = cx + radius * math.cos(ang)
        y2 = cy + radius * math.sin(ang)
        s.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#efede9"/>')
        lx = cx + (radius + 18) * math.cos(ang)
        ly = cy + (radius + 18) * math.sin(ang)
        cos_a, sin_a = math.cos(ang), math.sin(ang)
        anchor = "middle"
        dx = dy = 0
        if cos_a > 0.25:
            anchor, dx = "start", 6
        elif cos_a < -0.25:
            anchor, dx = "end", -6
        if sin_a > 0.3:
            dy = 12
        elif sin_a < -0.3:
            dy = -4
        text = label.replace("&", "&amp;").replace("<", "&lt;")
        s.append(
            f'<text x="{lx + dx:.1f}" y="{ly + dy:.1f}" text-anchor="{anchor}" '
            f'font-size="11" font-weight="600" fill="#1a1a1e">{text}</text>'
        )
    polygon = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    s.append(f'<polygon points="{polygon}" fill="#c98a2c" fill-opacity="0.22" stroke="#c98a2c" stroke-width="2"/>')
    for (x, y), value in zip(points, values):
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#b06f16"/>')
        s.append(f'<text x="{x + 7:.1f}" y="{y - 5:.1f}" font-size="9" font-weight="700" fill="#7a4e0a">{value:.1f}</text>')
    s.append("</svg>")
    return "".join(s)


def _radar_data_uri(breakdown):
    svg = _radar_svg(breakdown)
    if not svg:
        return None
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return "data:image/svg+xml;base64," + encoded


def _logo_data_uri():
    """Embed docs/logo.svg inline so the PDF is self-contained (white mark, so it
    sits on the dark header band in the cover)."""
    candidate = _BASE_DIR / "docs" / "logo.svg"
    if candidate.exists():
        try:
            svg = candidate.read_text(encoding="utf-8")
            encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
            return "data:image/svg+xml;base64," + encoded
        except Exception:
            pass
    return "https://abvorn.com/logo.svg"


# ── JSON blobs embedded in the page (verdict + RPS) ─────────────────────────
def _parse_json_script(soup, script_id):
    el = soup.find(id=script_id)
    if el is None or not el.string:
        return None
    text = el.string
    for old, new in (
        ("&quot;", '"'),
        ("&#39;", "'"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&amp;", "&"),
    ):
        text = text.replace(old, new)
    try:
        return json.loads(text)
    except Exception:
        return None


def _verdict_breakdown(soup):
    data = _parse_json_script(soup, "abvorn-verdict-data")
    if isinstance(data, dict) and isinstance(data.get("breakdown"), dict) and data["breakdown"]:
        return dict(data["breakdown"])
    rps = _parse_json_script(soup, "abvorn-rps-data")
    if isinstance(rps, dict):
        products = rps.get("products") or []
        if products and isinstance(products[0].get("scores"), dict) and products[0]["scores"]:
            return dict(products[0]["scores"])
    return None


# ── Print stylesheet ─────────────────────────────────────────────────────────
_PRINT_CSS = r"""
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
.pdf-header {
    display: flex; align-items: center; background: #0f0f12; border-radius: 6pt;
    padding: 8pt 11pt; margin-bottom: 12pt;
}
.pdf-logo { display: block; height: 20pt; width: auto; }
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

/* Product imagery from the review body */
img { max-width: 100%; }
.warm-product-card__media { display: block; margin: 5pt 0 6pt; }
.warm-product-card__media img { display: block; max-height: 105pt; width: auto; margin: 0; }
.product-figure {
    display: block; border: .6pt solid #e2e2e6; border-radius: 4pt;
    padding: 6pt; margin: 6pt 0; page-break-inside: avoid; background: #fcfcfc;
}
.product-figure img { display: block; max-height: 105pt; width: auto; margin: 0 auto; }

.disclosure {
    font-size: 7.5pt; color: #6b6b70; border: .5pt dashed #ccc; border-radius: 3pt;
    padding: 5pt 7pt; margin: 0 0 9pt;
}

/* -- Abvorn Verdict block (bars already server-rendered) -- */
.abvorn-verdict {
    border: .6pt solid #e8e8e8; border-left: 3pt solid #c98a2c; border-radius: 6pt;
    padding: 10pt 12pt; margin: 10pt 0; background: #fdfdfb; page-break-inside: avoid;
}
.av-badge {
    display: inline-block; background: #0a0a0a; color: #fff; font-size: 7pt;
    font-weight: 800; text-transform: uppercase; letter-spacing: .06em;
    padding: 3pt 9pt; border-radius: 100px; margin-bottom: 8pt;
}
.av-score-row { display: flex; align-items: center; gap: 12pt; margin: 8pt 0; }
.av-score { display: flex; align-items: baseline; }
.av-number { font-size: 26pt; font-weight: 800; color: #0f0f12; line-height: 1; }
.av-outof { font-size: 11pt; color: #6b6b70; font-weight: 600; }
.av-label-row { display: flex; flex-direction: column; }
.av-product { font-size: 11pt; font-weight: 700; color: #0f0f12; margin: 0; }
.av-label { font-size: 9.5pt; font-weight: 700; color: #c98a2c; }
.av-breakdown { margin: 8pt 0; }
.av-bar-row { display: flex; align-items: center; gap: 8pt; margin: 3pt 0; }
.av-bar-label { flex: 0 0 125pt; text-align: right; font-size: 8pt; font-weight: 600; color: #6b6b70; }
.av-bar-track { flex: 1; height: 7pt; background: #f2f1ee; border-radius: 100px; }
.av-bar-fill { height: 100%; border-radius: 100px; }
.av-bar-score { flex: 0 0 20pt; text-align: right; font-size: 8pt; font-weight: 700; color: #0a0a0a; }
.av-summary { font-size: 9pt; color: #555; line-height: 1.5; margin: 6pt 0 7pt; }
.av-cta .btn {
    display: inline-block; border: .6pt solid #c98a2c; border-radius: 3pt;
    padding: 3pt 9pt; margin: 2pt 4pt 2pt 0; font-size: 8pt; font-weight: 700;
    background: #fff; color: #7a4e0a; text-decoration: none;
}
.av-cta .btn--accent { background: #c98a2c; color: #0f0f12; }

/* -- Performance Breakdown chart section (static radar) -- */
.chart-section {
    border: .6pt solid #e2e2e6; border-radius: 6pt; padding: 9pt 11pt;
    margin: 10pt 0; background: #fff; page-break-inside: avoid;
}
.chart-section .rail-card__title { font-size: 10.5pt; margin: 0 0 4pt; }
.chart-wrapper { height: auto; max-width: none !important; width: 100%; }
img.pdf-radar { display: block; width: 100%; max-width: 410px; height: auto; margin: 4pt auto; }
.chart-note { text-align: center; font-size: 7.5pt; color: #8b8783; margin: 4pt 0 0; }

/* -- Regret Probability widget -- */
.rps-container {
    border: .6pt solid #e2e2e6; border-radius: 6pt; padding: 10pt 12pt;
    margin: 10pt 0; background: #fcfcfb; page-break-inside: avoid;
}
.rps-badge {
    font-size: 7pt; font-weight: 800; text-transform: uppercase; letter-spacing: .07em;
    color: #0a0a0a; margin-bottom: 6pt;
}
.rps-header { border-left: 3pt solid; padding-left: 8pt; margin: 4pt 0 6pt; }
.rps-score { display: flex; align-items: baseline; gap: 7pt; }
.rps-number { font-size: 17pt; font-weight: 800; }
.rps-sev { font-weight: 600; font-size: 8.5pt; }
.rps-product-name { font-size: 8.5pt; color: #6b6b70; margin-top: 2pt; }
.rps-section-title { font-weight: 700; font-size: 8.5pt; margin: 5pt 0 2pt; }
.rps-reason { font-size: 8pt; margin: 2pt 0; padding-left: 8pt; }
.rps-reason.rps-mismatch { color: #a94a3a; }
.rps-reason.rps-notice { color: #a07a2a; }
.rps-tip { font-size: 8pt; color: #6b6b70; font-style: italic; margin: 5pt 0; }
.rps-alt-title { font-weight: 700; font-size: 8.5pt; margin: 6pt 0 3pt; color: #1a1a1e; }
.rps-alt-item { display: block; border-top: .5pt solid #eee; padding: 3pt 0; font-size: 8pt; }
.rps-alt-name { font-weight: 600; color: #1a1a1e; }
.rps-alt-prob { float: right; font-weight: 600; font-size: 7.5pt; }
.rps-alt-price { color: #7a7a80; margin-left: 6pt; }
.rps-footer { font-size: 7pt; color: #9a9690; margin-top: 7pt; }

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
.further-reading, canvas, svg, form, script, style { display: none !important; }
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


def _embed_chart_block(soup, art):
    """Replace the Chart.js canvas in the Performance Breakdown section with a
    static radar image; drop the section when no score data is available."""
    kept = []
    for section in art.select(".chart-section"):
        breakdown = _verdict_breakdown(soup)
        uri = _radar_data_uri(breakdown) if breakdown else None
        wrapper = section.select_one(".chart-wrapper")
        if uri and wrapper:
            img = soup.new_tag("img")
            img["class"] = "pdf-radar"
            img["src"] = uri
            img["alt"] = "Performance breakdown radar chart"
            wrapper.clear()
            wrapper.append(img)
            kept.append(section)
        else:
            section.decompose()
    return kept


def _inject_rps_widget(soup, art):
    """Re-create the client-side Regret Probability widget as static HTML."""
    rps = _parse_json_script(soup, "abvorn-rps-data")
    if not isinstance(rps, dict):
        return
    products = rps.get("products") or []
    if not products or not isinstance(products[0], dict):
        return
    widget_html = _render_rps(products[0], products)
    verdict = art.find(class_="abvorn-verdict")
    target = verdict if verdict is not None else None
    if target is not None:
        fragment = BeautifulSoup(widget_html, "html.parser")
        for node in list(fragment.contents):
            target.insert_after(node.extract())


def _refine(soup, art):
    """Mutate the parsed article body into a print-friendly document."""
    _embed_chart_block(soup, art)
    _inject_rps_widget(soup, art)

    for sel in _CHROME_SELECTORS:
        for el in art.select(sel):
            el.decompose()
    # Remove residual chart wrappers (mini price charts, empty canvases), but
    # never the Performance Breakdown section we just populated.
    for el in list(art.select("[class*='chart']")):
        if "chart-section" in (el.get("class") or []):
            continue
        parent = el.find_parent(class_="chart-section")
        if parent is not None:
            continue
        el.decompose()
    for tag in art.select("script, style, canvas, svg, form, iframe, video, audio, noscript"):
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
                f'<div class="pdf-header"><img class="pdf-logo" src="{_logo_data_uri()}" alt="Abvorn"></div>'
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