"""Tests for TelegramNotifier commands."""
from unittest.mock import MagicMock
from abvorn.deploy.notifier import TelegramNotifier
from abvorn.sites.model import Site


def test_telegram_sites_command():
    n = TelegramNotifier(token="t", chat_id="c")
    n._site_registry = MagicMock()
    n._site_registry.list.return_value = [
        Site(site_id="s1", slug="tech", name="Tech", tagline="", logo_text="T", logo_icon="T",
             primary_color="#000", secondary_color="#fff", voice_rules={},
             niches=["tv", "laptop"], status="active")
    ]
    resp = n.process_command("/sites")
    assert "Tech" in resp


def test_telegram_site_command_found():
    n = TelegramNotifier(token="t", chat_id="c")
    n._site_registry = MagicMock()
    n._site_registry.list.return_value = [
        Site(site_id="s1", slug="tech", name="Tech", tagline="Gadgets", logo_text="T", logo_icon="T",
             primary_color="#000", secondary_color="#fff", voice_rules={},
             niches=["tv"], status="active")
    ]
    resp = n.process_command("/site tech")
    assert "Tech" in resp
    assert "Gadgets" in resp


def test_telegram_site_command_not_found():
    n = TelegramNotifier(token="t", chat_id="c")
    n._site_registry = MagicMock()
    n._site_registry.list.return_value = []
    resp = n.process_command("/site unknown")
    assert "not found" in resp


def test_telegram_traffic_with_site_arg():
    n = TelegramNotifier(token="t", chat_id="c")
    n._analytics_engine = MagicMock()
    n._analytics_engine.generate_insight_report.return_value = "Traffic report"
    resp = n.process_command("/traffic tech-gadgets")
    assert "Traffic" in resp
