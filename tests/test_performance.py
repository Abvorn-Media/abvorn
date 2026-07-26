import pytest
from datetime import datetime, timezone, timedelta
from abvorn.schedule.performance import PostPerformanceTracker
from abvorn.schedule.optimizer import ScheduleOptimizer
from abvorn.platform import registry
from abvorn.platform import adapters  # noqa: F401


class TestPostPerformanceTracker:
    def test_record_post(self):
        tracker = PostPerformanceTracker()
        record = tracker.record_post("x", "headphones")
        assert record["platform"] == "x"
        assert record["hour_utc"] >= 0
        assert record["day_of_week"] in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

    def test_update_engagement(self):
        tracker = PostPerformanceTracker()
        r = tracker.record_post("x", "headphones")
        assert tracker.update_engagement("x", r["posted_at"], 0.85) is True
        assert tracker.update_engagement("nonexistent", "never", 0.5) is False

    def test_get_records_filtered(self):
        tracker = PostPerformanceTracker()
        tracker.record_post("x", "headphones")
        tracker.record_post("linkedin", "headphones")
        assert len(tracker.get_records(platform="x")) == 1
        assert len(tracker.get_records()) == 2

    def test_analyze_hour_insufficient_data(self):
        tracker = PostPerformanceTracker()
        tracker.set_min_records(100)
        result = tracker.analyze_by_hour("x")
        assert result["status"] == "insufficient_data"

    def test_analyze_hour_with_data(self):
        tracker = PostPerformanceTracker()
        tracker.set_min_records(2)
        r1 = tracker.record_post("x", "headphones")
        tracker.update_engagement("x", r1["posted_at"], 0.85)
        r2 = tracker.record_post("x", "headphones")
        tracker.update_engagement("x", r2["posted_at"], 0.9)
        result = tracker.analyze_by_hour("x")
        assert result["status"] == "analyzed"

    def test_analyze_day_with_data(self):
        tracker = PostPerformanceTracker()
        tracker.set_min_records(2)
        r1 = tracker.record_post("x", "headphones")
        tracker.update_engagement("x", r1["posted_at"], 0.75)
        r2 = tracker.record_post("x", "headphones")
        tracker.update_engagement("x", r2["posted_at"], 0.8)
        result = tracker.analyze_by_day("x")
        assert result["status"] == "analyzed"

    def test_get_optimization_suggestions(self):
        tracker = PostPerformanceTracker()
        tracker.set_min_records(2)
        tracker.record_post("x", "headphones")
        r = tracker.record_post("x", "headphones")
        tracker.update_engagement("x", r["posted_at"], 0.75)
        suggestions = tracker.get_optimization_suggestions("x")
        assert suggestions["platform"] == "x"

    def test_record_count(self):
        tracker = PostPerformanceTracker()
        assert tracker.record_count() == 0
        tracker.record_post("x", "headphones")
        assert tracker.record_count() == 1


class TestScheduleOptimizer:
    def test_optimize_insufficient_data(self):
        tracker = PostPerformanceTracker()
        optimizer = ScheduleOptimizer(tracker)
        result = optimizer.optimize_platform("x")
        assert result["status"] == "insufficient_data"

    def test_optimize_with_data(self):
        tracker = PostPerformanceTracker()
        tracker.set_min_records(3)
        optimizer = ScheduleOptimizer(tracker)
        for _ in range(5):
            r = tracker.record_post("x", "headphones")
            tracker.update_engagement("x", r["posted_at"], 0.8)
        result = optimizer.optimize_platform("x")
        assert result["platform"] == "x"

    def test_optimize_all(self):
        tracker = PostPerformanceTracker()
        optimizer = ScheduleOptimizer(tracker)
        results = optimizer.optimize_all()
        assert len(results) > 0

    def test_optimization_report(self):
        tracker = PostPerformanceTracker()
        optimizer = ScheduleOptimizer(tracker)
        report = optimizer.get_optimization_report()
        assert "total_records" in report
        assert "platforms_total" in report

    def test_auto_apply_disabled_by_default(self):
        tracker = PostPerformanceTracker()
        optimizer = ScheduleOptimizer(tracker)
        assert optimizer._auto_apply is False

    def test_enable_disable_auto_apply(self):
        tracker = PostPerformanceTracker()
        optimizer = ScheduleOptimizer(tracker)
        optimizer.enable_auto_apply()
        assert optimizer._auto_apply is True
        optimizer.disable_auto_apply()
        assert optimizer._auto_apply is False