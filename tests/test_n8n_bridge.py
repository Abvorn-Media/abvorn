"""Tests for the n8n integration bridge and webhook endpoints."""

import json

import pytest

from abvorn.core.n8n_bridge import (
    N8NBridge,
    get_n8n_bridge,
    REFLECTION_WEBHOOK_PATH,
    PUBLISH_WEBHOOK_PATH,
    GSC_ANALYSIS_WEBHOOK_PATH,
    EVOLUTION_WEBHOOK_PATH,
)


@pytest.fixture(autouse=True)
def _reset_singletons():
    import abvorn.core.n8n_bridge as n8n

    n8n._n8n = None
    yield
    n8n._n8n = None


def test_bridge_defaults_use_real_ports():
    bridge = N8NBridge()
    assert bridge.port == 5678
    # The webhook target is the mobile server on 8080 (not 8000)
    assert bridge.webhook_base == "http://localhost:8080"
    assert bridge.base_url == "http://localhost:5678"


def test_abvorn_webhook_url_paths():
    bridge = N8NBridge()
    assert bridge.abvorn_webhook_url("gsc_fetch") == "http://localhost:8080/webhook/abvorn/gsc_fetch"
    assert bridge.abvorn_webhook_url("journal_update") == "http://localhost:8080/webhook/abvorn/journal_update"


def test_workflow_paths_are_constant():
    assert REFLECTION_WEBHOOK_PATH == "abvorn-reflection"
    assert PUBLISH_WEBHOOK_PATH == "abvorn-publish"
    assert GSC_ANALYSIS_WEBHOOK_PATH == "abvorn-gsc-analysis"
    assert EVOLUTION_WEBHOOK_PATH == "abvorn-evolution"


def test_trigger_workflow_never_raises(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        raise ConnectionError("n8n not running")

    monkeypatch.setattr("abvorn.core.n8n_bridge.requests.post", fake_post)
    bridge = N8NBridge()
    result = bridge.trigger_workflow(REFLECTION_WEBHOOK_PATH, {"content_id": "a"})
    assert result["success"] is False
    assert "error" in result


def test_trigger_workflow_success(monkeypatch):
    import requests

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    def fake_post(url, json=None, headers=None, timeout=None):
        assert url == "http://localhost:5678/webhook/abvorn-reflection"
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    bridge = N8NBridge()
    result = bridge.generate_reflection_workflow("article_1", "web")
    assert result["success"] is True
    assert result["data"] == {"ok": True}


def test_gsc_workflow_sends_days(monkeypatch):
    import requests

    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(json)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    bridge = N8NBridge()
    bridge.gsc_analysis_workflow(days=30)
    assert captured["days"] == 30
    assert "timestamp" in captured


def test_health_reports_unreachable():
    bridge = N8NBridge(host="localhost", port=1)
    health = bridge.health()
    assert health["healthy"] is False
    assert health["status"] == "error"


def test_health_connected(monkeypatch):
    import contextlib

    monkeypatch.setattr(
        "abvorn.core.n8n_bridge.socket.create_connection",
        lambda *a, **k: contextlib.nullcontext(),
    )
    bridge = N8NBridge(host="n8n.example.com", port=5678)
    health = bridge.health()
    assert health["healthy"] is True
    assert health["status"] == "connected"
    assert health["n8n_url"] == "http://n8n.example.com:5678"


def test_get_n8n_bridge_singleton():
    a = get_n8n_bridge()
    b = get_n8n_bridge()
    assert a is b


def test_evolution_workflow_payload(monkeypatch):
    import requests

    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(json)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    bridge = N8NBridge()
    bridge.evolution_workflow(generation=3)
    assert captured["generation"] == 3


def test_workflow_json_files_are_valid_and_reference_real_endpoints():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    workflows_dir = repo / "n8n" / "workflows"
    assert workflows_dir.exists(), "n8n/workflows/ dir must exist"

    for json_path in sorted(workflows_dir.glob("*.json")):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "name" in data
        assert "nodes" in data
        # Every HTTP call goes through $env.ABVORN_URL, never a hardcoded bad port
        text = json_path.read_text(encoding="utf-8")
        assert "$env.ABVORN_URL" in text
        assert "localhost:8000" not in text


def test_evolution_check_webhook_returns_should_evolve():
    """The evolution workflow reads {{ $json.should_evolve }} — the webhook must return it."""
    import mobile_server
    from fastapi.testclient import TestClient

    client = TestClient(mobile_server.app)
    response = client.post("/webhook/abvorn/evolution_check", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "should_evolve" in body
    assert isinstance(body["should_evolve"], bool)


def test_unknown_webhook_action_returns_error():
    import mobile_server
    from fastapi.testclient import TestClient

    client = TestClient(mobile_server.app)
    response = client.post("/webhook/abvorn/nope", json={})
    assert response.status_code == 200
    assert response.json()["success"] is False


def test_content_recent_endpoint_exists():
    import mobile_server
    from fastapi.testclient import TestClient

    client = TestClient(mobile_server.app)
    response = client.get("/api/content/recent", params={"limit": 3})
    assert response.status_code == 200
    assert "items" in response.json()
