"""Tests for ErrorReporter and DaemonGuard."""
from unittest.mock import MagicMock
from abvorn.monitor.error_reporter import ErrorReporter, DaemonGuard


def test_record_stores_error():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    reporter = ErrorReporter(state)
    result = reporter.record("test", ValueError("oops"), {"niche": "tv"})
    assert result["recorded"] is True
    assert state.set_meta.called


def test_get_recent_returns_errors():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"subsystem":"test","error_type":"ValueError","message":"oops",'
        '"traceback":"","context":{},"key":"test:ValueError","timestamp":"2026-07-26T00:00:00"}]'
    )
    reporter = ErrorReporter(state)
    recent = reporter.get_recent(limit=10)
    assert len(recent) == 1
    assert recent[0]["error_type"] == "ValueError"


def test_get_summary():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"subsystem":"a","error_type":"Err1","message":"","traceback":"",'
        '"context":{},"key":"a:Err1","timestamp":"2026-07-26T00:00:00"},'
        '{"subsystem":"a","error_type":"Err1","message":"","traceback":"",'
        '"context":{},"key":"a:Err1","timestamp":"2026-07-26T01:00:00"},'
        '{"subsystem":"b","error_type":"Err2","message":"","traceback":"",'
        '"context":{},"key":"b:Err2","timestamp":"2026-07-26T02:00:00"}]'
    )
    reporter = ErrorReporter(state)
    summary = reporter.get_summary()
    assert summary["total"] == 3
    assert summary["unique_types"] == 2


def test_guard_catches_and_re_raises():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    reporter = ErrorReporter(state)
    guard = DaemonGuard(reporter)
    try:
        guard.guard("test", lambda: 1 / 0)
        assert False, "Should have raised"
    except ZeroDivisionError:
        pass
    assert state.set_meta.called


def test_safe_returns_default():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    reporter = ErrorReporter(state)
    guard = DaemonGuard(reporter)
    result = guard.safe("test", lambda: 1 / 0, default="fallback")
    assert result == "fallback"
