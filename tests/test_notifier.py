import pytest
from abvorn.deploy.notifier import TelegramNotifier


@pytest.fixture
def no_creds(monkeypatch):
    """Simulate a deployment with no Telegram credentials configured, so the
    notifier can never read real secrets from disk during tests."""
    monkeypatch.setattr("abvorn.deploy.notifier.load_secrets", lambda: {})
    return {}


def test_notifier_init_from_secrets():
    """Should init even without real credentials."""
    notifier = TelegramNotifier()
    assert notifier is not None


def test_notifier_send_no_creds(no_creds):
    """Should skip sending when no credentials."""
    notifier = TelegramNotifier(token="", chat_id="")
    result = notifier.send("test")
    assert result is False


def test_report_cycle_formats(no_creds):
    """Should format a cycle report without errors."""
    notifier = TelegramNotifier(token="", chat_id="")
    result = notifier.report_cycle("wireless headphones", "success", "Best Headphones")
    assert result is False  # no creds, but no crash


def test_report_error_formats(no_creds):
    """Should format an error report without errors."""
    notifier = TelegramNotifier(token="", chat_id="")
    result = notifier.report_error("niche", "Something broke", 2)
    assert result is False  # no creds, but no crash


def test_report_health_formats(no_creds):
    """Should format a health report without errors."""
    notifier = TelegramNotifier(token="", chat_id="")
    stats = {"total_cycles": 10, "success_rate": 0.8, "avg_duration_s": 120, "pending_opportunities": 3}
    result = notifier.report_health(stats)
    assert result is False  # no creds, but no crash


class _FakeResp:
    def __init__(self, code, ok=False):
        self.status_code = code
        self._ok = ok

    def json(self):
        if self.status_code == 429:
            return {"parameters": {"retry_after": 1}}
        return {"ok": self._ok}

    @property
    def text(self):
        return ""


def test_notifier_send_retries_once_on_429(monkeypatch):
    """429+retry_after must be honored with one retry, not silently dropped."""
    monkeypatch.setattr("abvorn.deploy.notifier.time.sleep", lambda s: None)
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        return _FakeResp(429 if calls["n"] == 1 else 200, ok=True)

    monkeypatch.setattr("abvorn.deploy.notifier.requests.post", fake_post)
    notifier = TelegramNotifier(token="t", chat_id="c")
    assert notifier.send("hello") is True
    assert calls["n"] == 2