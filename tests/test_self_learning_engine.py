import shutil
import tempfile
from pathlib import Path

import pytest

from abvorn.domination.self_learning_engine import SelfLearningEngine


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
