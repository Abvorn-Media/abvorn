import pytest
from abvorn.deploy.notifier import TelegramNotifier


def test_notifier_init_from_secrets():
    """Should init even without real credentials."""
    notifier = TelegramNotifier()
    assert notifier is not None


def test_notifier_send_no_creds():
    """Should skip sending when no credentials."""
    notifier = TelegramNotifier(token="", chat_id="")
    result = notifier.send("test")
    assert result is False


def test_report_cycle_formats():
    """Should format a cycle report without errors."""
    notifier = TelegramNotifier(token="", chat_id="")
    result = notifier.report_cycle("wireless headphones", "success", "Best Headphones")
    assert result is False  # no creds, but no crash


def test_report_error_formats():
    """Should format an error report without errors."""
    notifier = TelegramNotifier(token="", chat_id="")
    result = notifier.report_error("niche", "Something broke", 2)
    assert result is False  # no creds, but no crash


def test_report_health_formats():
    """Should format a health report without errors."""
    notifier = TelegramNotifier(token="", chat_id="")
    stats = {"total_cycles": 10, "success_rate": 0.8, "avg_duration_s": 120, "pending_opportunities": 3}
    result = notifier.report_health(stats)
    assert result is False  # no creds, but no crash