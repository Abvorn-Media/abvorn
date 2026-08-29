"""Backfill click_targets from existing Abvorn docs.

Scans docs/reviews/**/*.html. For every affiliate click button
(/click/<article_id>/<index>) it finds the product's Amazon URL from the
matching "compare" link url=/asin= in the same card, and upserts it into the
click_targets table so /click/ redirects go to the real product rather than
the generic search fallback.
"""
import re
import sqlite3
import glob
import os
import sys
import urllib.parse

DOCS_ROOT = sys.argv[1] if len(sys.argv) > 1 else "/var/www/abvorn/docs"
DB_PATH = sys.argv[2] if len(sys.argv) > 2 else "/opt/abvorn-core/data/clicks.db"
AFFILIATE_TAG = "viraltestco-20"

CLICK_RE = re.compile(r'href="https?://(?:[^"/]+)?/click/([^"/]+)/(\d+)"')
COMPARE_RE = re.compile(r'compare\.html\?[^"\']*')
URL_PARAM_RE = re.compile(r'[?&]url=([^&"\']+)')
ASIN_PARAM_RE = re.compile(r'[?&]asin=([^&"\']+)')
NAME_RE = re.compile(r'(?:warm-product-card|hero-pick)__name">\s*([^<]+?)\s*</')


def find_nearby_url(html, prev_pos, pos, next_pos):
    """Look within the same product card for the compare url, asin, or name.

    Card boundaries are the previous and next /click/ button, so compare links
    from another card are never picked up. The old fixed 3000-char window both
    grabbed the next card's link and missed far links in the same card.
    """
    after = html[pos:next_pos]
    for m in COMPARE_RE.finditer(after):
        seg = m.group(0)
        um = URL_PARAM_RE.search(seg)
        if um:
            raw = urllib.parse.unquote(um.group(1))
            if "amazon" in raw:
                return raw
        am = ASIN_PARAM_RE.search(seg)
        if am:
            return "https://www.amazon.com/dp/" + am.group(1)
        break

    # fall back to compare link before the button (rare ordering)
    before = html[prev_pos:pos]
    for m in reversed(list(COMPARE_RE.finditer(before))):
        seg = m.group(0)
        um = URL_PARAM_RE.search(seg)
        if um:
            raw = urllib.parse.unquote(um.group(1))
            if "amazon" in raw:
                return raw
        am = ASIN_PARAM_RE.search(seg)
        if am:
            return "https://www.amazon.com/dp/" + am.group(1)
        break

    # last resort: product name -> amazon search
    seg = html[prev_pos:next_pos]
    nm = NAME_RE.findall(seg)
    if nm:
        name = nm[-1].strip()
        if name:
            return "https://www.amazon.com/s?k={}&tag={}".format(
                urllib.parse.quote_plus(name), AFFILIATE_TAG
            )
    return ""


def ensure_url(url):
    if not url:
        return ""
    if "tag=" not in url:
        sep = "&" if "?" in url else "?"
        url = url + sep + "tag=" + AFFILIATE_TAG
    return url


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS click_targets (
        article_id TEXT NOT NULL,
        product_index INTEGER NOT NULL,
        product_url TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (article_id, product_index)
    )""")
    files = sorted(glob.glob(os.path.join(DOCS_ROOT, "reviews", "**", "*.html"), recursive=True))
    total = 0
    per_file = 0
    for f in files:
        html = open(f, encoding="utf-8", errors="replace").read()
        rows = []
        matches = list(CLICK_RE.finditer(html))
        bounds = [m.start() for m in matches]
        for i, m in enumerate(matches):
            article_id, idx = m.group(1), int(m.group(2))
            prev_pos = bounds[i - 1] if i > 0 else 0
            next_pos = bounds[i + 1] if i + 1 < len(bounds) else len(html)
            url = find_nearby_url(html, prev_pos, m.start(), next_pos)
            url = ensure_url(url)
            if url:
                rows.append((article_id, idx, url))
        for article_id, idx, url in rows:
            cur.execute(
                "INSERT OR REPLACE INTO click_targets (article_id, product_index, product_url, created_at) "
                "VALUES (?,?,?,?)",
                (article_id, idx, url, __import__("datetime").datetime.now().isoformat()),
            )
            total += 1
        if rows:
            per_file += 1
    conn.commit()
    n = cur.execute("SELECT COUNT(*) FROM click_targets").fetchone()[0]
    conn.close()
    print("scanned %d files; %d files had targets; %d total click_targets rows;" % (len(files), per_file, n))


if __name__ == "__main__":
    main()