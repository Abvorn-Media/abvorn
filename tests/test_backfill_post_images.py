"""Tests for the posts.image backfill (scripts/backfill_post_images.py).

Guards the property that matters most: a page with no real product photo must
never yield an image, or the backfill would replace one wrong value (a
timestamp, or nothing) with another wrong value (generic niche artwork) and
the bug would look "fixed" while cards still showed no product photo.
"""
import importlib.util
import pathlib
import sqlite3
import sys

_SCRIPT = (pathlib.Path(__file__).resolve().parent.parent
           / "scripts" / "backfill_post_images.py")
_spec = importlib.util.spec_from_file_location("backfill_post_images", _SCRIPT)
bf = importlib.util.module_from_spec(_spec)
sys.modules["backfill_post_images"] = bf
_spec.loader.exec_module(bf)

AMZON = "https://m.media-amazon.com/images/I/61abc._AC_SL500_.jpg"

REVIEW_PAGE = """<!DOCTYPE html><html><body>
<aside class="hero-pick"><div class="hero-pick__media"><img src="%s" alt="Sony"></div></aside>
<figure class="product-shot"><img class="product-shot__img" src="%s"></figure>
</body></html>""" % (AMZON, AMZON)

# A category/hub page whose only images are the generic niche fallback: exactly
# the markup a state-posted card renders when posts.image is empty.
FALLBACK_ONLY_PAGE = """<!DOCTYPE html><html><body>
<a href="/reviews/tv/"><img src="/assets/tv.svg" alt="2026 Ultimate TV Buying Guide"></a>
</body></html>"""


def _db(tmp_path, rows):
    path = tmp_path / "state.db"
    con = sqlite3.connect(str(path))
    con.execute("""CREATE TABLE posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        niche_slug TEXT, title TEXT, filename TEXT,
        image TEXT, created_at TEXT)""")
    con.executemany(
        "INSERT INTO posts (niche_slug, title, filename, image, created_at) "
        "VALUES (?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return path


def test_extract_product_image_upgrades_real_product_shot():
    got = bf.extract_product_image(REVIEW_PAGE)
    assert got.startswith("https://m.media-amazon.com/images/I/61abc")
    assert "_AC_SL500_" not in got, "should be upgraded to a larger rendition"


def test_extract_product_image_refuses_fallback_artwork():
    """The core guard: no product photo means no image, never the niche SVG."""
    assert bf.extract_product_image(FALLBACK_ONLY_PAGE) == ""
    assert bf.extract_product_image("") == ""
    assert bf.extract_product_image("<html><body>nothing</body></html>") == ""


def test_candidate_relpaths_prefers_specific_page():
    assert bf.candidate_relpaths("tv", "a-guide.html") == ["reviews/tv/a-guide.html"]
    assert bf.candidate_relpaths("tv", "index.html") == ["reviews/tv/index.html"]
    assert bf.candidate_relpaths("tv", "") == ["reviews/tv/index.html"]


def test_backfill_fills_empty_rows_only_and_is_idempotent(tmp_path):
    docs = tmp_path / "docs"
    (docs / "reviews" / "tv").mkdir(parents=True)
    (docs / "reviews" / "tv" / "guide.html").write_text(REVIEW_PAGE, encoding="utf-8")

    db = _db(tmp_path, [
        ("tv", "Real guide", "guide.html", "", "2026-02-03T04:05:06"),
        ("tv", "Already set", "guide.html", AMZON, "2026-02-03T04:05:06"),
        ("tv", "No page", "missing.html", "", "2026-02-03T04:05:06"),
    ])

    stats = bf.backfill(db, docs, dry_run=False, offline=True)
    assert stats["filled"] == 1
    assert stats["already"] == 1
    assert stats["unresolved"] == 1

    con = sqlite3.connect(str(db))
    images = dict(con.execute("SELECT title, image FROM posts").fetchall())
    con.close()
    assert images["Real guide"].startswith("https://m.media-amazon.com/images/I/61abc")
    assert images["Already set"] == AMZON, "must not overwrite a good image"
    assert images["No page"] == "", "unresolvable row must stay empty"

    # Second run changes nothing.
    again = bf.backfill(db, docs, dry_run=False, offline=True)
    assert again["filled"] == 0
    assert again["already"] == 2


def test_backfill_dry_run_writes_nothing(tmp_path):
    docs = tmp_path / "docs"
    (docs / "reviews" / "tv").mkdir(parents=True)
    (docs / "reviews" / "tv" / "guide.html").write_text(REVIEW_PAGE, encoding="utf-8")
    db = _db(tmp_path, [("tv", "Real guide", "guide.html", "", "2026-01-01T00:00:00")])

    bf.backfill(db, docs, dry_run=True, offline=True)
    con = sqlite3.connect(str(db))
    assert con.execute("SELECT image FROM posts").fetchone()[0] == ""
    con.close()
