"""Tests for GA4 traffic analytics and analytics engine."""
import pytest
from unittest.mock import MagicMock, patch
from abvorn.analytics.ga4 import GA4Client
from abvorn.analytics.engine import AnalyticsEngine


def test_ga4_client_initializes():
    client = GA4Client(property_id="123456789")
    assert client is not None


def test_ga4_client_no_credentials():
    client = GA4Client()
    result = client.query()
    assert result["status"] == "unconfigured"


def test_ga4_client_query_returns_structure():
    client = GA4Client(property_id="123456789")
    client._client = MagicMock()
    with patch.object(client, '_run_report', return_value={
        "status": "ok",
        "total_page_views": 350,
        "total_sessions": 300,
        "total_users": 45,
        "pages": [
            {"path": "/best-tv-2026", "views": 150, "sessions": 120, "users": 45},
            {"path": "/best-laptop-2026", "views": 200, "sessions": 180, "users": 60},
        ],
        "period_days": 7,
    }):
        result = client.query(days=7)
        assert "pages" in result
        assert result["total_page_views"] == 350
        assert len(result["pages"]) == 2


def test_ga4_client_cache():
    client = GA4Client(property_id="123456789")
    client._client = MagicMock()
    client._cache = {"ga4_7": {"data": {"total_page_views": 100}, "time": 9999999999}}
    result = client.query(days=7)
    assert result["total_page_views"] == 100


def test_analytics_engine_initializes():
    engine = AnalyticsEngine()
    assert engine is not None


def test_analytics_engine_collect():
    engine = AnalyticsEngine(ga4_client=GA4Client())
    report = engine.collect()
    assert isinstance(report, dict)
    assert "collected_at" in report


def test_analytics_engine_insight_report():
    engine = AnalyticsEngine()
    engine.data = {"total_page_views": 1000, "top_pages": [{"path": "/test", "views": 500}]}
    report = engine.generate_insight_report()
    assert isinstance(report, str)
    assert len(report) > 20


def test_analytics_engine_site_filter():
    from unittest.mock import MagicMock
    from abvorn.analytics.engine import AnalyticsEngine
    state = MagicMock()
    engine = AnalyticsEngine(ga4_client=MagicMock(), state=state)
    report = engine.generate_insight_report(site_id="tech-gadgets")
    assert isinstance(report, str)