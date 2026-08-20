"""Tests for the MoneyPrinterTurbo video rendering bridge."""

import pytest

from abvorn.core.video_render import (
    VideoRenderer,
    get_video_renderer,
    build_video_payload,
    platform_aspect,
    DEFAULT_MPT_URL,
    VIDEO_RENDER_WEBHOOK_PATH,
)


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch):
    import abvorn.core.video_render as vr

    vr._renderer = None
    monkeypatch.delenv("ABVORN_MPT_URL", raising=False)
    monkeypatch.delenv("ABVORN_MPT_VOICE", raising=False)
    yield
    vr._renderer = None


def test_default_url_and_webhook_path():
    assert DEFAULT_MPT_URL == "http://localhost:8080"
    assert VIDEO_RENDER_WEBHOOK_PATH == "abvorn-video-render"


def test_platform_aspect_mapping():
    assert platform_aspect("tiktok") == "9:16"
    assert platform_aspect("youtube") == "16:9"
    assert platform_aspect("instagram") == "1:1"
    assert platform_aspect("unknown") == "9:16"


def test_build_payload_from_colosseum_carousel():
    source = {
        "product_name": "Sony WH-1000XM5",
        "slides": {
            "hook": "Nobody talks about this",
            "problem": "Most ANC headphones fail in the gym",
            "verdict": "The XM5 wins",
            "breakdown": "Battery lasts 30 hours",
            "comparison": "Better than the XM4",
            "call": "Get the Sony",
        },
    }
    payload = build_video_payload(source, platform="tiktok")
    assert payload["video_subject"] == "Sony WH-1000XM5"
    assert "Nobody talks about this" in payload["video_script"]
    assert "Get the Sony" in payload["video_script"]
    assert payload["video_aspect"] == "9:16"
    assert payload["video_count"] == 1


def test_build_payload_from_domination_script():
    source = {
        "title": "Sony WH-1000XM5 Review",
        "script": {
            "hook": "The XM5 is the best ANC",
            "body": "Battery lasts 30 hours",
            "cta": "Link in bio",
        },
    }
    payload = build_video_payload(source, platform="youtube")
    assert payload["video_subject"] == "Sony WH-1000XM5 Review"
    assert "The XM5 is the best ANC" in payload["video_script"]
    assert "Link in bio" in payload["video_script"]
    assert payload["video_aspect"] == "16:9"


def test_build_payload_terms_from_string():
    payload = build_video_payload(
        {"video_subject": "Sony XM5", "video_terms": "headphones, noise cancelling, sony"},
    )
    assert payload["video_terms"] == ["headphones", "noise cancelling", "sony"]


def test_build_payload_uses_explicit_materials():
    source = {
        "video_subject": "Sony XM5",
        "video_materials": [
            {"url": "https://images.pexels.com/videos/123.mp4"},
            {"url": "https://images.pexels.com/videos/456.mp4"},
        ],
    }
    payload = build_video_payload(source)
    assert len(payload["video_materials"]) == 2
    assert payload["video_materials"][0]["provider"] == "pexels"


def test_submit_posts_to_videos_endpoint(monkeypatch):
    import requests

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"status": 200, "data": {"task_id": "abc-123"}}

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    renderer = VideoRenderer(base_url="http://mpt.example.com:8080")
    result = renderer.submit({"video_subject": "Test"})
    assert result["success"] is True
    assert result["task_id"] == "abc-123"
    assert captured["url"] == "http://mpt.example.com:8080/api/v1/videos"
    assert captured["json"]["video_subject"] == "Test"


def test_submit_never_raises(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        raise ConnectionError("mpt not running")

    monkeypatch.setattr("abvorn.core.video_render.requests.post", fake_post)
    renderer = VideoRenderer(base_url="http://localhost:1")
    result = renderer.submit({"video_subject": "Test"})
    assert result["success"] is False
    assert "error" in result


def test_status_returns_public_urls(monkeypatch):
    import requests

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": 200,
                "data": {
                    "task_id": "abc-123",
                    "state": 1,
                    "progress": 100,
                    "videos": ["/tasks/abc-123/final-1.mp4"],
                },
            }

    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse())
    renderer = VideoRenderer(base_url="http://mpt.example.com:8080")
    result = renderer.status("abc-123")
    assert result["success"] is True
    assert result["state"] == 1
    assert result["task"]["videos"] == [
        "http://mpt.example.com:8080/tasks/abc-123/final-1.mp4"
    ]


def test_wait_completes(monkeypatch):
    import requests

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": 200,
                "data": {
                    "task_id": "abc-123",
                    "state": 1,
                    "progress": 100,
                    "videos": ["final-1.mp4"],
                },
            }

    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse())
    renderer = VideoRenderer(base_url="http://mpt.example.com:8080", timeout=30)
    result = renderer.wait("abc-123", poll_interval=0)
    assert result["success"] is True
    assert result["completed"] is True


def test_wait_failed(monkeypatch):
    import requests

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": 200,
                "data": {"task_id": "abc-123", "state": -1, "error": "TTS timed out"},
            }

    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse())
    renderer = VideoRenderer(base_url="http://mpt.example.com:8080", timeout=30)
    result = renderer.wait("abc-123", poll_interval=0)
    assert result["success"] is False
    assert "TTS timed out" in result["error"]


def test_render_never_raises_when_unreachable(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        raise ConnectionError("mpt not running")

    monkeypatch.setattr("abvorn.core.video_render.requests.post", fake_post)
    renderer = VideoRenderer(base_url="http://localhost:1")
    result = renderer.render({"video_subject": "Test"})
    assert result["success"] is False


def test_health_reports_unreachable():
    renderer = VideoRenderer(base_url="http://localhost:1")
    health = renderer.health()
    assert health["healthy"] is False
    assert health["status"] == "error"


def test_get_video_renderer_singleton(monkeypatch):
    a = get_video_renderer()
    b = get_video_renderer()
    assert a is b