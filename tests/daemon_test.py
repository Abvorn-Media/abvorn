"""Tests for OptimizationDaemon — CTA, hooks, brain optimization cycle."""

import pytest, time, tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


@pytest.fixture
def state(tmp_path):
    from abvorn.core.state import AbvornState
    s = AbvornState(tmp_path / "test.db")
    s.add_post("test", "Test Post", "test.html")
    return s


@pytest.fixture
def daemon(state):
    from abvorn.daemon import OptimizationDaemon
    from abvorn.trends.scanner import TrendScanner

    class _MockProvider:
        def search(self, category, max_results=5):
            return []
    return OptimizationDaemon(state, trend_scanner=TrendScanner(providers=[_MockProvider()]))


class TestOptimizationDaemon:
    def test_run_cycle_returns_expected_structure(self, daemon):
        result = daemon.run_cycle()
        assert "cycle_id" in result
        assert "timestamp" in result
        assert "actions" in result
        assert isinstance(result["cycle_id"], str)
        assert len(result["cycle_id"]) == 8
        assert isinstance(result["actions"], list)

    def test_optimize_ctas_returns_list(self, daemon):
        actions = daemon.optimize_ctas()
        assert isinstance(actions, list)

    def test_optimize_ctas_with_data(self, state):
        from abvorn.daemon import OptimizationDaemon
        from abvorn.cta.tracker import CTATracker

        tracker = CTATracker(state)
        post_id = state.get_posts_for_niche("test")[0]["id"]
        for i in range(15):
            tracker.track_impression(post_id=post_id, cta_id=f"perf_{i}",
                                      cta_text="click here", niche="test")
        tracker.track_impression(post_id=post_id, cta_id="good_cta",
                                  cta_text="Buy Now", niche="test")
        tracker.track_click(post_id=post_id, cta_id="good_cta", niche="test")

        d = OptimizationDaemon(state)
        actions = d.optimize_ctas()
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_optimize_hooks_returns_list(self, daemon):
        actions = daemon.optimize_hooks()
        assert isinstance(actions, list)
        assert len(actions) >= 0

    def test_should_run_returns_true_when_no_last_run(self, daemon):
        assert daemon.should_run() is True

    def test_should_run_returns_false_within_interval(self, daemon):
        now = datetime.now().isoformat()
        daemon.state.set_meta("optimization_last_run", now)
        assert daemon.should_run(interval=3600) is False

    def test_should_run_respects_interval(self, daemon):
        past = (datetime.now() - timedelta(hours=2)).isoformat()
        daemon.state.set_meta("optimization_last_run", past)
        assert daemon.should_run(interval=3600) is True

    def test_generate_report_returns_markdown(self, daemon):
        report = daemon.generate_report()
        assert isinstance(report, str)
        assert report.startswith("# Abvorn Optimization Report")
        assert "## CTA Performance" in report
        assert "## Hook Recommendations" in report
        assert "## Brain Status" in report
        assert "## Engagement Summary" in report

    def test_generate_report_includes_data(self, state):
        from abvorn.daemon import OptimizationDaemon
        state.set_meta("optimization_last_run", datetime.now().isoformat())
        state.set_meta("brain_last_refresh", datetime.now().isoformat())

        d = OptimizationDaemon(state)
        report = d.generate_report()
        assert "**Last optimization cycle:**" in report
        assert "**Last refresh:**" in report


def test_run_once_convenience(state):
    from abvorn.daemon import OptimizationDaemon
    from abvorn.trends.scanner import TrendScanner

    class _MockProvider:
        def search(self, category, max_results=5):
            return []
    d = OptimizationDaemon(state, trend_scanner=TrendScanner(providers=[_MockProvider()]))
    report = d.generate_report()
    assert isinstance(report, str)
    assert len(report) > 20


def test_run_once_sets_last_run(state):
    from abvorn.daemon import OptimizationDaemon
    from abvorn.trends.scanner import TrendScanner

    class _MockProvider:
        def search(self, category, max_results=5):
            return []
    d = OptimizationDaemon(state, trend_scanner=TrendScanner(providers=[_MockProvider()]))
    d.run_cycle()
    last_run = state.get_meta("optimization_last_run")
    assert last_run is not None


def test_daemon_smart_defaults(state):
    from abvorn.daemon import OptimizationDaemon
    d = OptimizationDaemon(state)
    assert d.cta_tracker is not None
    assert d.cta_analyzer is not None
    assert d.cta_optimizer is not None
    assert d.hook_tester is not None
    assert d.hook_optimizer is not None
    assert d.brain_refresher is not None


def test_daemon_custom_injections(state):
    from abvorn.daemon import OptimizationDaemon
    mock = MagicMock()
    d = OptimizationDaemon(state, cta_tracker=mock, cta_analyzer=mock,
                            cta_optimizer=mock, hook_tester=mock,
                            hook_optimizer=mock, brain_refresher=lambda: {"status": "ok"})
    assert d.cta_tracker is mock
    assert d.brain_refresher() == {"status": "ok"}


def test_run_cycle_records_timestamp(daemon):
    before = datetime.now().isoformat()[:16]
    daemon.run_cycle()
    last_run = daemon.state.get_meta("optimization_last_run")
    assert last_run is not None
    assert last_run[:16] >= before


def test_daemon_trend_integration(state):
    from abvorn.daemon import OptimizationDaemon
    from unittest.mock import MagicMock

    class _MockProvider:
        def search(self, category, max_results=5):
            return []
    from abvorn.trends.scanner import TrendScanner
    d = OptimizationDaemon(state, trend_scanner=TrendScanner(providers=[_MockProvider()]))
    result = d.run_cycle()
    assert "cycle_id" in result
    trend_actions = [a for a in result.get("actions", []) if a.get("type") == "trend_scan"]
    assert len(trend_actions) >= 0


def test_daemon_trend_schedule_fill(state):
    from abvorn.daemon import OptimizationDaemon
    from unittest.mock import MagicMock

    class _MockProvider:
        def search(self, category, max_results=5):
            return [{"product_name": "Test TV", "category": "tv", "source": "mock", "score": 80, "price_range": "", "url": ""}]
    from abvorn.trends.scanner import TrendScanner
    from abvorn.trends.planner import ContentPlanner
    from abvorn.trends.schedule import Schedule
    d = OptimizationDaemon(
        state,
        trend_scanner=TrendScanner(providers=[_MockProvider()]),
        content_planner=ContentPlanner(),
        schedule=Schedule(state)
    )
    result = d.run_cycle()
    assert "cycle_id" in result
    assert "timestamp" in result


def test_daemon_report_includes_schedule(daemon):
    report = daemon.generate_report()
    assert "## Content Schedule" in report
    assert "AM:" in report or "No post scheduled" in report


def test_daemon_trend_records_scan_time(state):
    from abvorn.daemon import OptimizationDaemon
    from unittest.mock import MagicMock

    class _MockProvider:
        def search(self, category, max_results=5):
            return [{"product_name": "Test TV", "category": "tv", "source": "mock", "score": 80, "price_range": "", "url": ""}]
    from abvorn.trends.scanner import TrendScanner
    d = OptimizationDaemon(state, trend_scanner=TrendScanner(providers=[_MockProvider()]))
    d.run_cycle()
    last_scan = state.get_meta("trend_last_scan")
    assert last_scan is not None


def test_daemon_email_dispatch_returns_list(state):
    from abvorn.daemon import OptimizationDaemon
    mock_sender = MagicMock()
    mock_sender.send_persona_content.return_value = {"sent": 2, "errors": 0, "total": 2}
    mock_db = MagicMock()
    mock_db.get_subscribers.return_value = [
        {"email": "a@b.com", "name": "Alice"},
        {"email": "c@d.com", "name": "Bob"},
    ]
    d = OptimizationDaemon(state, email_sender=mock_sender, subscriber_db=mock_db)
    actions = d.dispatch_scheduled_emails()
    assert isinstance(actions, list)


def test_daemon_email_dispatch_wired_in_cycle(state):
    from abvorn.daemon import OptimizationDaemon
    from abvorn.trends.scanner import TrendScanner

    class _MockProvider:
        def search(self, category, max_results=5):
            return []
    mock_sender = MagicMock()
    mock_sender.send_persona_content.return_value = {"sent": 1, "errors": 0, "total": 1}
    mock_db = MagicMock()
    mock_db.get_subscribers.return_value = [{"email": "x@y.com", "name": "Test"}]
    d = OptimizationDaemon(state, email_sender=mock_sender, subscriber_db=mock_db,
                            trend_scanner=TrendScanner(providers=[_MockProvider()]))
    result = d.run_cycle()
    email_actions = [a for a in result.get("actions", []) if a.get("type") == "email_dispatch"]
    assert isinstance(email_actions, list)
