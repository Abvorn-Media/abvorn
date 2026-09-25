import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from abvorn.domination.self_learning_engine import (
    SelfLearningEngine,
    normalize_source_url,
)


@pytest.fixture
def learn_db(tmp_path):
    yield str(tmp_path / "learn.db")
    for p in sorted(tmp_path.glob("*"), reverse=True):
        try:
            p.unlink()
        except OSError:
            pass


def test_posted_urls_empty_on_fresh_db(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    assert sle.posted_urls() == set()


def test_post_urls_roundtrip_via_record(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    sle.record_post_performance(
        url="https://abvorn.com/reviews/laptops/",
        niche="laptops",
        platform="x",
    )
    assert sle.posted_urls() == {"https://abvorn.com/reviews/laptops/"}
    # duplicate insert must not duplicate the returned set
    sle.record_post_performance(
        url="https://abvorn.com/reviews/laptops/",
        niche="laptops",
        platform="x",
    )
    assert sle.posted_urls() == {"https://abvorn.com/reviews/laptops/"}


def test_same_niche_distinct_articles_are_distinct_posts(learn_db):
    """Two articles sharing one niche hub must record as two posts."""
    sle = SelfLearningEngine(db_path=learn_db)
    sle.record_post_performance(
        url="https://abvorn.com/reviews/laptops/",
        niche="laptops",
        platform="x",
        source_url="https://abvorn.com/reviews/laptops/best-a.html",
    )
    sle.record_post_performance(
        url="https://abvorn.com/reviews/laptops/",
        niche="laptops",
        platform="x",
        source_url="https://abvorn.com/reviews/laptops/best-b.html",
    )
    assert sle.posted_urls() == {
        "https://abvorn.com/reviews/laptops/best-a.html",
        "https://abvorn.com/reviews/laptops/best-b.html",
    }


def test_same_article_across_platforms_records_once_per_platform(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    for platform in ("x", "telegram", "linkedin"):
        sle.record_post_performance(
            url="https://abvorn.com/reviews/laptops/",
            niche="laptops",
            platform=platform,
            source_url="https://abvorn.com/reviews/laptops/best-a.html",
        )
    import sqlite3
    with sqlite3.connect(learn_db) as conn:
        rows = conn.execute(
            "SELECT platform FROM content_performance ORDER BY platform"
        ).fetchall()
    assert [r[0] for r in rows] == ["linkedin", "telegram", "x"]


def test_niche_post_times_reports_recency_order(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    assert sle.niche_post_times() == {}
    sle.record_post_performance(
        url="https://abvorn.com/reviews/laptops/",
        niche="laptops",
        platform="x",
        source_url="https://abvorn.com/reviews/laptops/best-a.html",
    )
    sle.record_post_performance(
        url="https://abvorn.com/reviews/mice/",
        niche="mice",
        platform="x",
        source_url="https://abvorn.com/reviews/mice/best-a.html",
    )
    recency = sle.niche_post_times()
    assert set(recency) == {"laptops", "mice"}
    # mice was recorded last, so it is the more recent niche
    assert recency["mice"] > recency["laptops"]


def test_legacy_post_url_unique_schema_migrates(learn_db):
    """A pre-source_url DB must migrate in place, keeping its rows.

    The old schema had post_url UNIQUE, which is what collapsed a niche's
    articles into one row. Migration must preserve history and drop that
    constraint so a niche can hold many articles.
    """
    import sqlite3
    with sqlite3.connect(learn_db) as conn:
        conn.execute("""
            CREATE TABLE content_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_url TEXT NOT NULL UNIQUE,
                niche TEXT NOT NULL,
                platform TEXT NOT NULL,
                hook_used TEXT,
                sentiment TEXT,
                virality_score REAL DEFAULT 0.0,
                total_engagement INTEGER DEFAULT 0,
                posted_at TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute(
            "INSERT INTO content_performance (post_url, niche, platform, posted_at) "
            "VALUES ('https://abvorn.com/reviews/laptops/', 'laptops', 'x', '2026-09-01 00:00:00')"
        )
        conn.commit()

    sle = SelfLearningEngine(db_path=learn_db)

    # legacy row survives, backfilled with its own post_url as source_url
    assert sle.posted_urls() == {"https://abvorn.com/reviews/laptops/"}
    with sqlite3.connect(learn_db) as c:
        assert c.execute("SELECT count(*) FROM content_performance").fetchone()[0] == 1
        assert c.execute("SELECT post_url FROM content_performance").fetchone()[0] == (
            "https://abvorn.com/reviews/laptops/"
        )
    # no rotation history exists for pre-migration rows, so the niche counts as
    # never-posted and rotation would give it priority. That is safe: its articles
    # are still deduped, so it cannot re-post one.
    assert sle.niche_post_times() == {}

    # the same hub can now hold a second article
    sle.record_post_performance(
        url="https://abvorn.com/reviews/laptops/",
        niche="laptops",
        platform="x",
        source_url="https://abvorn.com/reviews/laptops/best-b.html",
    )
    assert len(sle.posted_urls()) == 2

    # migration is idempotent
    SelfLearningEngine(db_path=learn_db)
    assert len(SelfLearningEngine(db_path=learn_db).posted_urls()) == 2


def test_best_hooks_empty_before_ga4_feedback(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    sle.record_hook_test("Buy now", "laptops", "x")
    assert sle.best_hooks("laptops", "x") == []
    # posting insights column absent until real engagement feeds in
    assert sle.best_posting_times("laptops", "x") == []


def test_feed_ga4_engagement_updates_hook_and_posting(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    sle.record_hook_test("We compared 6 laptops", "laptops", "x")
    sle.record_post_performance(
        url="https://abvorn.com/reviews/laptops/",
        niche="laptops",
        platform="x",
        hook="We compared 6 laptops",
    )
    fed = sle.feed_ga4_engagement(
        {"laptops": {"views": 120, "users": 30}},
        {"laptops": {"clicks": 4}},
        site_url="https://abvorn.com/reviews",
    )
    assert fed == 1
    best = sle.best_hooks("laptops", "x")
    assert best and best[0]["impressions"] >= 120
    assert best[0]["clicks"] == 4
    assert best[0]["score"] > 0
    import sqlite3
    with sqlite3.connect(learn_db) as conn:
        row = conn.execute(
            "SELECT sample_size, avg_engagement FROM posting_insights "
            "WHERE niche='laptops' AND platform='x'"
        ).fetchone()
    assert row is not None
    assert row[0] == 1
    assert row[1] == 120 + 30 * 2 + 4 * 10  # views + 2*users + 10*clicks


def test_dated_republication_dedupes_to_one_post(learn_db):
    """The feed republishes one article under new dated filenames.

    Exact-URL dedupe would treat ...-2026-08-24.html and ...-2026-08-31.html as
    two articles and post the same content back-to-back.
    """
    sle = SelfLearningEngine(db_path=learn_db)
    base = "https://abvorn.com/reviews/4k-monitors/best-4k-monitors-compared"
    sle.record_post_performance(
        url="https://abvorn.com/reviews/4k-monitors/",
        niche="4k-monitors",
        platform="x",
        source_url=f"{base}-2026-08-24.html",
    )
    posted = sle.posted_urls()
    assert posted == {f"{base}.html"}

    # the later dated copy of the same content is already considered posted
    sle.record_post_performance(
        url="https://abvorn.com/reviews/4k-monitors/",
        niche="4k-monitors",
        platform="x",
        source_url=f"{base}-2026-08-31.html",
    )
    with sqlite3.connect(learn_db) as c:
        assert c.execute("SELECT count(*) FROM content_performance").fetchone()[0] == 1
    assert sle.posted_urls() == {f"{base}.html"}


def test_repeat_record_keeps_one_dedupe_row_but_advances_rotation(learn_db):
    """Dedupe and rotation recency are separate ledgers.

    content_performance must keep exactly one row per (article, platform) so a
    repeat cannot re-post. niche_post_order must still append, otherwise rotation
    reads the same recency forever and pins itself to one niche.
    """
    sle = SelfLearningEngine(db_path=learn_db)
    for _ in range(3):
        sle.record_post_performance(
            url="https://abvorn.com/reviews/laptops/",
            niche="laptops",
            platform="x",
            source_url="https://abvorn.com/reviews/laptops/best.html",
        )
    with sqlite3.connect(learn_db) as c:
        assert c.execute("SELECT count(*) FROM content_performance").fetchone()[0] == 1
        assert c.execute("SELECT id FROM content_performance").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM niche_post_order").fetchone()[0] == 3
    # recency advanced to the third post
    assert sle.niche_post_times() == {"laptops": 3}


def test_normalize_source_url_only_strips_trailing_date():
    assert normalize_source_url(
        "https://abvorn.com/reviews/x/best-2026-guide-2026-08-24.html"
    ) == "https://abvorn.com/reviews/x/best-2026-guide.html"
    # a year inside the slug is not a date suffix
    assert normalize_source_url(
        "https://abvorn.com/reviews/x/2026-roundup.html"
    ) == "https://abvorn.com/reviews/x/2026-roundup.html"
    # date mid-slug is untouched
    assert normalize_source_url(
        "https://abvorn.com/reviews/x/2026-08-24-roundup-final.html"
    ) == "https://abvorn.com/reviews/x/2026-08-24-roundup-final.html"
    assert normalize_source_url("") == ""
    # hub URLs have no date and pass through unchanged
    assert normalize_source_url(
        "https://abvorn.com/reviews/laptops/"
    ) == "https://abvorn.com/reviews/laptops/"


def test_feed_ga4_skips_unknown_slug(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    sle.record_post_performance(
        url="https://abvorn.com/reviews/mice/",
        niche="mice",
        platform="x",
        hook="hook A",
    )
    fed = sle.feed_ga4_engagement(
        {"keyboards": {"views": 5}}, {}, site_url="https://abvorn.com/reviews"
    )
    assert fed == 0


def test_feed_ga4_matches_latest_hook_variant(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    sle.record_hook_test("Old hook", "laptops", "x")
    sle.record_hook_test("New hook", "laptops", "x")
    sle.record_post_performance(
        url="https://abvorn.com/reviews/laptops/",
        niche="laptops",
        platform="x",
        hook="New hook",
    )
    sle.feed_ga4_engagement(
        {"laptops": {"views": 50, "users": 10}}, {}, site_url="https://abvorn.com/reviews"
    )
    best = sle.best_hooks("laptops", "x")
    assert len(best) == 1 and best[0]["hook_text"] == "New hook"


def test_record_posting_time_at_buckets_by_datetime(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    from datetime import datetime
    when = datetime(2026, 9, 10, 14, 30)
    sle.record_posting_time_at("laptops", "x", 5.0, when)
    sle.record_posting_time_at("laptops", "x", 15.0, when)
    times = sle.best_posting_times("laptops", "x")
    assert len(times) == 1
    assert times[0]["day_of_week"] == "Thursday"
    assert times[0]["hour"] == 14
    assert times[0]["sample_size"] == 2
    assert times[0]["avg_engagement"] == 10.0


def test_alignment_delay_zero_on_empty_db(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    assert sle.next_alignment_delay() == 0


def test_alignment_delay_returns_wait_until_best_hour(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    from datetime import datetime
    # Thursday 14:00 was the learned best hour (multiple samples)
    when = datetime(2026, 9, 10, 14, 0)
    for _ in range(3):
        sle.record_posting_time_at("laptops", "x", 10.0, when)
    # Now it's Thursday 10:00 → 4h away
    now = datetime(2026, 9, 10, 10, 0)
    assert sle.next_alignment_delay(now=now, max_lookahead_hours=6) == 4 * 3600


def test_alignment_delay_zero_if_best_hour_passed(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    from datetime import datetime
    when = datetime(2026, 9, 10, 14, 0)
    for _ in range(3):
        sle.record_posting_time_at("laptops", "x", 10.0, when)
    now = datetime(2026, 9, 10, 15, 0)  # past the best hour
    assert sle.next_alignment_delay(now=now, max_lookahead_hours=6) == 0


def test_alignment_delay_bounded_by_lookahead(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    from datetime import datetime
    when = datetime(2026, 9, 10, 14, 0)
    for _ in range(3):
        sle.record_posting_time_at("laptops", "x", 10.0, when)
    now = datetime(2026, 9, 10, 6, 0)  # 8h away > 6h lookahead
    assert sle.next_alignment_delay(now=now, max_lookahead_hours=6) == 0


def test_alignment_delay_ignores_weak_data(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    from datetime import datetime
    when = datetime(2026, 9, 10, 14, 0)
    sle.record_posting_time_at("laptops", "x", 10.0, when)  # 1 sample only
    now = datetime(2026, 9, 10, 10, 0)
    assert sle.next_alignment_delay(now=now, min_samples=3) == 0


def test_alignment_delay_this_weekday_only(learn_db):
    sle = SelfLearningEngine(db_path=learn_db)
    from datetime import datetime
    friday = datetime(2026, 9, 11, 14, 0)  # different weekday
    for _ in range(3):
        sle.record_posting_time_at("laptops", "x", 10.0, friday)
    thursday_now = datetime(2026, 9, 10, 10, 0)
    assert sle.next_alignment_delay(now=thursday_now, max_lookahead_hours=6) == 0
