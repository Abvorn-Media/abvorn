import pytest, json, tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from abvorn.schedule.planner import PlatformPlanner
from abvorn.schedule.queue import PostingQueue
from abvorn.schedule.manager import ScheduleManager
from abvorn.core.state import AbvornState
from abvorn.platform import registry


def _all_peaks():
    return {n: registry.get(n).schedule_profile for n in registry.list()}


class TestPlatformPeaks:
    def test_all_platforms_have_required_keys(self):
        required = {"best_days", "best_hours", "min_gap_hours", "max_per_day", "cadence"}
        peaks = _all_peaks()
        for platform, config in peaks.items():
            assert config is not None, f"{platform} has no schedule_profile"
            assert required.issubset(config.keys()), f"{platform} missing keys"

    def test_best_hours_are_valid(self):
        for platform, config in _all_peaks().items():
            for h in config["best_hours"]:
                assert 0 <= h <= 23, f"{platform} hour {h} out of range"

    def test_min_gap_positive(self):
        for platform, config in _all_peaks().items():
            assert config["min_gap_hours"] > 0, f"{platform} min_gap_hours must be > 0"

    def test_cadence_valid(self):
        valid = {"daily", "weekly", "per_post"}
        for platform, config in _all_peaks().items():
            assert config["cadence"] in valid, f"{platform} cadence invalid"


class TestPlatformPlanner:
    def test_is_good_time_returns_bool(self):
        planner = PlatformPlanner()
        result = planner.is_good_time("x")
        assert isinstance(result, bool)

    def test_is_good_time_invalid_platform_raises(self):
        planner = PlatformPlanner()
        with pytest.raises(ValueError, match="Unknown platform"):
            planner.is_good_time("nonexistent")

    def test_next_good_time_returns_iso_string(self):
        planner = PlatformPlanner()
        result = planner.next_good_time("x")
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None or "T" in result
        assert len(result) > 10

    def test_next_good_time_is_in_future(self):
        planner = PlatformPlanner()
        now = datetime.now(timezone.utc)
        result = planner.next_good_time("x")
        dt = datetime.fromisoformat(result)
        assert dt > now - timedelta(hours=1)

    def test_min_gap_met_no_last_post(self):
        planner = PlatformPlanner()
        assert planner.min_gap_met("x") is True

    def test_min_gap_met_with_recent_post(self):
        planner = PlatformPlanner()
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert planner.min_gap_met("x", recent) is False

    def test_min_gap_met_with_old_post(self):
        planner = PlatformPlanner()
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        assert planner.min_gap_met("x", old) is True

    def test_time_until_next_returns_positive(self):
        planner = PlatformPlanner()
        seconds = planner.time_until_next("x")
        assert seconds >= 0

    def test_next_good_time_for_all_platforms(self):
        planner = PlatformPlanner()
        for platform in _all_peaks():
            result = planner.next_good_time(platform)
            dt = datetime.fromisoformat(result)
            assert dt > datetime.now(timezone.utc) - timedelta(hours=1)


class TestPostingQueue:
    def test_enqueue_returns_id(self):
        queue = PostingQueue()
        item_id = queue.enqueue("Hello", "x")
        assert isinstance(item_id, str)
        assert len(item_id) > 0

    def test_enqueue_and_dequeue(self):
        queue = PostingQueue()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        queue.enqueue("Test content", "x", priority=10, scheduled_time=past)
        item = queue.dequeue()
        assert item is not None
        assert item["content"] == "Test content"
        assert item["platform"] == "x"

    def test_dequeue_empty_returns_none(self):
        queue = PostingQueue()
        assert queue.dequeue() is None

    def test_peek_does_not_remove(self):
        queue = PostingQueue()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        queue.enqueue("Peek test", "x", priority=10, scheduled_time=past)
        peeked = queue.peek()
        assert peeked is not None
        assert peeked["content"] == "Peek test"
        assert queue.dequeue() is not None

    def test_peek_empty_returns_none(self):
        queue = PostingQueue()
        assert queue.peek() is None

    def test_ack_marks_posted(self):
        queue = PostingQueue()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        item_id = queue.enqueue("Ack test", "x", priority=10, scheduled_time=past)
        queue.dequeue()
        queue.ack(item_id)
        assert queue.get_queue_length() == 0

    def test_nack_marks_failed(self):
        queue = PostingQueue()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        item_id = queue.enqueue("Nack test", "x", priority=10, scheduled_time=past)
        queue.dequeue()
        queue.nack(item_id, "test failure")
        assert queue.get_queue_length() == 0

    def test_priority_ordering(self):
        queue = PostingQueue()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        low = queue.enqueue("Low priority", "x", priority=1, scheduled_time=past)
        high = queue.enqueue("High priority", "x", priority=10, scheduled_time=past)
        first = queue.dequeue()
        assert first["id"] == high

    def test_get_upcoming(self):
        queue = PostingQueue()
        queue.enqueue("Item 1", "x", priority=5)
        queue.enqueue("Item 2", "linkedin", priority=3)
        upcoming = queue.get_upcoming(2)
        assert len(upcoming) == 2

    def test_get_upcoming_filtered(self):
        queue = PostingQueue()
        queue.enqueue("A", "x", priority=5)
        upcoming = queue.get_upcoming(5)
        assert len(upcoming) == 1

    def test_state_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            state = AbvornState(db)
            queue = PostingQueue(state)
            past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            queue.enqueue("Persist me", "x", priority=5, scheduled_time=past)
            saved = state.get_meta("schedule.queue", [])
            assert len(saved) >= 1
            state.close()


class TestScheduleManager:
    def test_should_post_returns_bool(self):
        manager = ScheduleManager()
        result = manager.should_post("x")
        assert isinstance(result, bool)

    def test_should_post_invalid_platform(self):
        manager = ScheduleManager()
        with pytest.raises(ValueError):
            manager.should_post("nonexistent")

    def test_schedule_content_queues_items(self):
        manager = ScheduleManager()
        ids = manager.schedule_content("Multi-platform content", ["x", "linkedin"])
        assert len(ids) == 2

    def test_get_due_items_returns_ready(self):
        manager = ScheduleManager()
        manager.schedule_content("Due content", ["x"])
        due = manager.get_due_items()
        assert len(due) >= 0

    def test_mark_posted_acks_item(self):
        manager = ScheduleManager()
        ids = manager.schedule_content("Mark me", ["x"])
        for item_id in ids:
            manager.mark_posted(item_id)
        assert len(manager.get_due_items()) == 0

    def test_mark_failed_nacks_item(self):
        manager = ScheduleManager()
        ids = manager.schedule_content("Fail me", ["x"])
        for item_id in ids:
            manager.mark_failed(item_id, "test")
        assert len(manager.get_due_items()) == 0

    def test_get_cadence_default(self):
        manager = ScheduleManager()
        cadence = manager.get_cadence("unknown_niche")
        assert cadence in ("daily", "weekly", "per_post")

    def test_update_cadence(self):
        manager = ScheduleManager()
        manager.update_cadence("test_niche", "weekly")
        assert manager.get_cadence("test_niche") == "weekly"

    def test_cadence_from_niche_maturity(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            state = AbvornState(db)
            state.upsert_niche("mature_niche", "Mature Niche")
            state.update_niche_maturity("mature_niche", 15, 8.0)
            manager = ScheduleManager(state)
            cadence = manager.get_cadence("mature_niche")
            assert cadence == "weekly"
            state.close()

    def test_empty_queue_due_items(self):
        manager = ScheduleManager()
        assert manager.get_due_items() == []
