"""Tests for Tavily API-key rotation (primary -> backup fallback)."""

from unittest.mock import MagicMock, patch

from abvorn.core.tavily import TavilyClient


def _resp(status, payload=None, text=""):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload if payload is not None else {}
    m.text = text
    return m


def test_tavily_keys_include_backup_from_env(monkeypatch):
    """Primary + backup are both kept; placeholders and dups are dropped."""
    monkeypatch.setenv("TAVILY_KEY", "tvly-primary")
    monkeypatch.setenv("TAVILY_KEY_BACKUP", "tvly-backup")
    tc = TavilyClient()
    assert tc.available is True
    assert tc._keys == ["tvly-primary", "tvly-backup"]

    explicit = TavilyClient("tvly-primary", "YOUR_BACKUP_HERE")
    assert explicit._keys == ["tvly-primary"]


def test_tavily_backup_only_is_available(monkeypatch):
    """A backup on its own still enables search (primary absent)."""
    monkeypatch.delenv("TAVILY_KEY", raising=False)
    monkeypatch.setenv("TAVILY_KEY_BACKUP", "tvly-only-backup")
    tc = TavilyClient("")
    assert tc.available is True
    assert tc.api_key == "tvly-only-backup"


@patch("abvorn.core.tavily.time.sleep")
@patch("requests.post")
def test_tavily_rotates_to_backup_on_quota(mock_post, mock_sleep):
    """A quota-exhausted primary (HTTP 432) falls through to the backup."""
    ok = {"answer": "backup answer", "results": [{"title": "t"}], "response_time": 0.1}
    mock_post.side_effect = [_resp(432, text="plan limit exceeded"), _resp(200, ok)]
    tc = TavilyClient("tvly-primary", "tvly-backup")
    assert tc.search("query") == ok
    assert tc.api_key == "tvly-backup"
    assert mock_post.call_count == 2


@patch("abvorn.core.tavily.time.sleep")
@patch("requests.post")
def test_tavily_rotates_on_auth_failure(mock_post, mock_sleep):
    """A revoked/invalid primary key (HTTP 401) falls through to the backup."""
    ok = {"answer": "ok", "results": [], "response_time": 0.1}
    mock_post.side_effect = [_resp(401, text="invalid api key"), _resp(200, ok)]
    tc = TavilyClient("tvly-primary", "tvly-backup")
    assert tc.search("query") == ok
    assert tc.api_key == "tvly-backup"


@patch("abvorn.core.tavily.time.sleep")
@patch("requests.post")
def test_tavily_no_rotation_when_primary_works(mock_post, mock_sleep):
    """A healthy primary is used once and never rotates."""
    ok = {"answer": "primary answer", "results": [], "response_time": 0.2}
    mock_post.return_value = _resp(200, ok)
    tc = TavilyClient("tvly-primary", "tvly-backup")
    assert tc.search("query") == ok
    assert tc.api_key == "tvly-primary"
    assert mock_post.call_count == 1


@patch("abvorn.core.tavily.time.sleep")
@patch("requests.post")
def test_tavily_all_keys_rejected(mock_post, mock_sleep):
    """When every key is rejected the call degrades to an empty result."""
    mock_post.side_effect = [_resp(429, text="rate limited"), _resp(401, text="bad key")]
    tc = TavilyClient("tvly-primary", "tvly-backup")
    out = tc.search("query")
    assert out == {"answer": "", "results": [], "response_time": 0}
    assert mock_post.call_count == 2


@patch("abvorn.core.tavily.time.sleep")
@patch("requests.post")
def test_tavily_server_error_does_not_rotate(mock_post, mock_sleep):
    """A 5xx is a server fault - don't burn the backup key on it."""
    mock_post.return_value = _resp(503, text="upstream unavailable")
    tc = TavilyClient("tvly-primary", "tvly-backup")
    out = tc.search("query")
    assert out == {"answer": "", "results": [], "response_time": 0}
    assert mock_post.call_count == 1
    assert tc.api_key == "tvly-primary"
