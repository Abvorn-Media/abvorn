"""Tests for ClickTracker."""
from unittest.mock import MagicMock
from abvorn.persuasion.tracker import ClickTracker


def test_record_click_stores():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    tracker = ClickTracker(state)
    tracker.record_click("tv", "consideration", 0)
    assert state.set_meta.called


def test_record_impression_stores():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    tracker = ClickTracker(state)
    tracker.record_impression("tv", "awareness")
    assert state.set_meta.called


def test_get_stats_empty():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    tracker = ClickTracker(state)
    stats = tracker.get_stats()
    assert "total_clicks" in stats
    assert stats["total_clicks"] == 0
