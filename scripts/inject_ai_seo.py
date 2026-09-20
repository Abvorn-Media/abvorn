#!/usr/bin/env python3
"""Post-build AI-SEO injector for docs/*.html.

Adds machine-readable structured data and freshness to already-built pages
*without* regenerating content, so the rich hand-tuned hubs are never rebuilt
by an ad-hoc tool (see AGENTS.md). Idempotent: re-running changes nothing.

Injected
--------
* Article JSON-LD on og:type=article pages: headline, description,
  datePublished/dateModified (from the visible Published/Updated dates),
  author + publisher (Organization "Abvorn"), image, mainEntityOfPage,
  articleSection, isAccessibleForFree.
* WebPage JSON-LD on the remaining pages (they shipped with zero JSON-LD).
* Organization + WebSite JSON-LD on the homepage.
* <time datetime="..."> around the visible Published/Updated dates.
* <main> landmark on pages whose id="main" element is an <article>.
* Comparison pages: canonical / og:url / breadcrumb point at the real
  /comparisons/<slug>.html instead of the non-existent /comparisons/<slug>/.

Usage
-----
    python scripts/inject_ai_seo.py [--dry-run] [--check] [--root docs]

--check exits 1 if any page would change (for CI); --dry-run prints the files
that would change without writing.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime
from html import unescape

SITE = "https://abvorn.com"
LOGO = f"{SITE}/assets/logo.png"
ORG = {
    "@type": "Organization",
    "name": "Abvorn",
    "url": f"{SITE}/",
    "logo": {"@type": "ImageObject", "url": LOGO},
}
SKIP = {"console.html", "google73aec0d1f1cc59ad.html"}

_DATE = r"([A-Z][a-z]{2} \d{1,2}, \d{4})"


def rel_url(rel: str) -> str:
    if rel == "index.html":
        return f"{SITE}/"
    if rel.endswith("/index.html"):
        return f"{SITE}/{rel[: -len('index.html')]}"
    return f"{SITE}/{rel}"


def iso_date(text: str) -> str:
    return datetime.strptime(text, "%b %d, %Y").date().isoformat()


def meta(html: str, key: str) -> str:
    for attr in ("property", "name"):
        m = re.search(
            rf'<meta[^>]*{attr}="{re.escape(key)}"[^>]*content="([^"]*)"', html
        )
        if m:
            return unescape(m.group(1))
    return ""


def h1_text(html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()


def ld_block(obj: dict, marker: str, nl: str = "\n") -> str:
    payload = json.dumps(obj, ensure_ascii=True, separators=(",", ":"))
    return (
        f'<!-- ai-seo:{marker} -->{nl}'
        f'<script type="application/ld+json">{payload}</script>{nl}'
    )


def article_obj(rel: str, html: str) -> dict:
    url = rel_url(rel)
    obj: dict = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": h1_text(html) or meta(html, "og:title"),
        "description": meta(html, "description") or meta(html, "og:description"),
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "url": url,
        "author": ORG,
        "publisher": ORG,
        "isAccessibleForFree": True,
    }
    image = meta(html, "og:image")
    if image:
        obj["image"] = image
    parts = rel.split("/")
    if parts[0] == "reviews" and len(parts) > 1:
        obj["articleSection"] = parts[1].replace("-", " ").title()
    pub = re.search(r"Published " + _DATE, html)
    upd = re.search(r"Updated " + _DATE, html)
    if pub:
        obj["datePublished"] = iso_date(pub.group(1))
    if upd:
        obj["dateModified"] = iso_date(upd.group(1))
    elif pub:
        obj["dateModified"] = obj["datePublished"]
    return obj


def webpage_obj(rel: str, html: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": meta(html, "og:title") or h1_text(html),
        "description": meta(html, "description"),
        "url": rel_url(rel),
        "isPartOf": {"@type": "WebSite", "name": "Abvorn", "url": f"{SITE}/"},
    }


def wrap_time(html: str, label: str) -> str:
    pattern = rf'(<span class="date">){label} ({_DATE[1:-1]})(</span>)'

    def repl(m: re.Match) -> str:
        return (
            f"{m.group(1)}{label} "
            f'<time datetime="{iso_date(m.group(2))}">{m.group(2)}</time>'
            f"{m.group(3)}"
        )

    return re.sub(pattern, repl, html)


def add_main(html: str) -> str:
    if "<main" in html:
        return html
    m = re.search(r'<article([^>]*?)\sid="main"([^>]*)>', html)
    if not m:
        return html
    html = html.replace(
        m.group(0), f'<main id="main"><article{m.group(1)}{m.group(2)}>', 1
    )
    return html.replace("</article>", "</article></main>", 1)


def fix_comparison_canonical(rel: str, html: str) -> str:
    if not (rel.startswith("comparisons/") and rel.endswith(".html")):
        return html
    slug = rel[len("comparisons/"):-len(".html")]
    html = html.replace(
        f"{SITE}/comparisons/{slug}/", f"{SITE}/comparisons/{slug}.html"
    )
    html = html.replace(
        f'"/comparisons/{slug}/"', f'"/comparisons/{slug}.html"'
    )
    return html


def process(rel: str, html: str) -> str:
    # Build schema from the raw page first: wrap_time() rewrites the visible
    # dates, which would hide them from the date parser.
    block = ""
    if "ai-seo:schema" not in html:
        nl = "\r\n" if "\r\n" in html else "\n"
        is_article = (
            re.search(r'<meta[^>]*property="og:type"[^>]*content="article"', html)
            is not None
        )
        if is_article:
            block = ld_block(article_obj(rel, html), "schema", nl)
        else:
            block = ld_block(webpage_obj(rel, html), "schema", nl)
            if rel == "index.html":
                block += ld_block(
                    ORG | {"@context": "https://schema.org"}, "org", nl
                )
                block += ld_block(
                    {"@context": "https://schema.org", "@type": "WebSite",
                     "name": "Abvorn", "url": f"{SITE}/"},
                    "website",
                    nl,
                )

    html = wrap_time(html, "Published")
    html = wrap_time(html, "Updated")
    html = fix_comparison_canonical(rel, html)
    html = add_main(html)
    if block:
        html = html.replace("</head>", block + "</head>", 1)
    return html


def inject_tree(root, dry_run: bool = False, check: bool = False) -> tuple[int, int]:
    """Apply :func:`process` to every HTML file under *root*.

    Returns ``(changed, added)`` where ``added`` counts pages that received a
    new JSON-LD block. With ``dry_run`` or ``check`` nothing is written.
    """
    root = pathlib.Path(root)
    changed = added = 0
    for f in sorted(root.rglob("*.html")):
        rel = f.relative_to(root).as_posix()
        if rel in SKIP:
            continue
        before = f.read_bytes().decode("utf-8")
        after = process(rel, before)
        if after == before:
            continue
        changed += 1
        if "ai-seo:schema" not in before and "ai-seo:schema" in after:
            added += 1
        if dry_run or check:
            print(f"  {'needs' if check else 'would change'}: {rel}")
        else:
            f.write_bytes(after.encode("utf-8"))
    return changed, added


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="docs")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    changed, added = inject_tree(args.root, dry_run=args.dry_run, check=args.check)
    verb = "would change" if (args.dry_run or args.check) else "updated"
    print(f"{changed} page(s) {verb}; {added} got new JSON-LD")
    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
