from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image
from abvorn.deploy.composio_client import parse_insight_metrics
from abvorn.domination.social_publisher import SocialPublisher, _parse_ig_timestamp
from abvorn.domination.cinematic_filter import CinematicFilter


@pytest.fixture
def publisher():
    return SocialPublisher(composio_key="test_key")


def test_honest_caption_ok(publisher):
    cap = publisher._honest_instagram_caption(["📌 Best 4K Monitors\n\nSwipe →"], "4k-monitors")
    assert "Best 4K Monitors" in cap
    assert "testing" not in cap.lower()
    assert "bought" not in cap.lower()


def test_honest_caption_neutralizes_false_claim(publisher):
    cap = publisher._honest_instagram_caption(
        ["📌 We tested 20+ monitors side by side"], "4k-monitors"
    )
    assert "tested" not in cap.lower()
    assert "Comparing specs, prices" in cap or "comparing specs" in cap.lower()


def test_honest_caption_empty_uses_neutral(publisher):
    cap = publisher._honest_instagram_caption("", "4k-monitors")
    assert cap.startswith("After comparing specs")


def test_carousel_requires_two_images(publisher):
    """<2 media paths must fall back to export, never hit a live publish."""
    result = publisher._publish_instagram_carousel(["slide"], "instagram", "4k-monitors", ["only-one.jpg"])
    assert result["status"] == "exported"


def test_carousel_export_on_client_failure(publisher, monkeypatch):
    """Client failure with >=2 images must still fall back to export."""
    def _boom(caption, images):
        raise RuntimeError("composio down")
    monkeypatch.setattr(publisher._client, "instagram_publish_carousel", _boom)
    result = publisher._publish_instagram_carousel(
        ["📌 foo"], "instagram", "4k-monitors", ["a.jpg", "b.jpg"]
    )
    assert result["status"] == "exported"


def test_instagram_resize_is_45_portrait(tmp_path):
    """IG feed resize must produce 1080x1350 (4:5), not square."""
    src = tmp_path / "landscape.png"
    img = Image.new("RGB", (1920, 800), (40, 40, 40))
    img.save(src)
    out = tmp_path / "ig_out.jpg"
    result = CinematicFilter().resize_for_platform(str(src), "instagram", str(out))
    assert result is not None
    size = Image.open(result).size
    assert size == (1080, 1350), f"expected 1080x1350, got {size}"


def test_resize_verify_rejects_failed_write(tmp_path, monkeypatch):
    """If the output is missing/wrong size, resize must return None (no bad frame)."""
    src = tmp_path / "src.png"
    Image.new("RGB", (800, 800), (10, 10, 10)).save(src)

    # capture the real save before patching, so the "bad" write still works
    probe = Image.new("RGB", (1, 1))
    real_save = probe.save  # bound method, unaffected by class patch

    def _bad_save(self, output, **params):
        real_save(Image.new("RGB", (1, 1)), output, format="JPEG")

    monkeypatch.setattr(Image.Image, "save", _bad_save)
    out = tmp_path / "ig_bad.jpg"
    result = CinematicFilter().resize_for_platform(str(src), "instagram", str(out))
    assert result is None


def test_resize_instagram_drops_missing_files(publisher, tmp_path):
    """_resize_for_instagram must never return an unresized original."""
    real = tmp_path / "real.jpg"
    Image.new("RGB", (800, 600), (30, 30, 30)).save(real)
    resized = publisher._resize_for_instagram([str(tmp_path / "missing.jpg"), str(real)])
    assert resized  # at least the real one resized
    got = Image.open(resized[0]).size
    assert got == (1080, 1350), f"expected 4:5 portrait, got {got}"


def test_resize_instagram_never_returns_original_path(publisher, tmp_path):
    """The original file must never appear in the output list."""
    real = tmp_path / "keep-original.jpg"
    Image.new("RGB", (800, 600), (30, 30, 30)).save(real)
    resized = publisher._resize_for_instagram([str(real)])
    assert resized
    assert all(str(p) != str(real) for p in resized)


def test_parse_insight_metrics_unwraps_composio_envelope():
    payload = {"data": [{"name": "likes", "values": [{"value": 3}]},
                        {"name": "reach", "values": [{"value": 40}]}]}
    assert parse_insight_metrics(payload) == {"likes": 3, "reach": 40}


def test_parse_insight_metrics_unwraps_double_nesting():
    """The Graph API wraps in data too, so the envelope nests twice."""
    payload = {"data": {"data": [{"name": "shares", "values": [{"value": 2}]}]}}
    assert parse_insight_metrics(payload) == {"shares": 2}


def test_parse_insight_metrics_rejects_error_payload():
    """A 400 must never be mistaken for a set of zero metrics."""
    assert parse_insight_metrics(
        {"message": "metric is required", "status_code": 400}) == {}
    assert parse_insight_metrics(None) == {}
    assert parse_insight_metrics([]) == {}
    assert parse_insight_metrics({"data": {"message": "bad", "status_code": 400}}) == {}


def test_parse_insight_metrics_omits_absent_metric():
    """Instagram drops metrics it has no data for; absent stays absent."""
    payload = {"data": [{"name": "likes", "values": [{"value": 0}]}]}
    parsed = parse_insight_metrics(payload)
    assert parsed == {"likes": 0}
    assert "reach" not in parsed


def test_parse_insight_metrics_ignores_malformed_values():
    payload = {"data": [{"values": [{"value": 1}]},
                        {"name": "likes", "values": []},
                        {"name": "comments", "values": [{"value": "many"}]},
                        {"name": "saved", "values": [{"value": None}]},
                        {"name": "shares", "values": [{"value": 7}]}]}
    assert parse_insight_metrics(payload) == {"shares": 7}


def test_parse_ig_timestamp_handles_colonless_offset():
    when = _parse_ig_timestamp("2026-09-26T11:52:01+0000")
    assert when is not None
    assert when.utcoffset() == timedelta(0)
    assert (when.hour, when.minute, when.second) == (11, 52, 1)


def test_parse_ig_timestamp_rejects_unknown_or_absent_zone():
    assert _parse_ig_timestamp("") is None
    assert _parse_ig_timestamp("not-a-date") is None
    assert _parse_ig_timestamp("2026-09-26T11:52:01") is None


class _StubInsightClient:
    available = True

    def __init__(self, media, insights=None):
        self._media = media
        self._insights = insights or {}

    def instagram_media_list(self, limit=50):
        return list(self._media)

    def instagram_post_insights(self, media_id):
        return self._insights.get(media_id, {})


class _StubOfflineClient:
    available = False

    def instagram_media_list(self, limit=50):  # pragma: no cover - guard
        raise AssertionError("media list must not be called when unavailable")


def test_collect_insights_returns_recent_media_with_metrics(publisher, monkeypatch):
    now = datetime.now(timezone.utc)
    media = [
        {"id": "fresh",
         "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S+0000")},
        {"id": "stale",
         "timestamp": (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S+0000")},
        {"id": "broken", "timestamp": "not-a-date"},
        {"timestamp": now.strftime("%Y-%m-%dT%H:%M:%S+0000")},
    ]
    monkeypatch.setattr(publisher, "_client",
                        _StubInsightClient(media, {"fresh": {"likes": 2}}))

    items = publisher.collect_instagram_insights(days=30)

    assert [i["media_id"] for i in items] == ["fresh"]
    assert items[0]["metrics"] == {"likes": 2}
    assert isinstance(items[0]["when"], datetime)


def test_collect_insights_is_empty_without_a_live_client(publisher, monkeypatch):
    monkeypatch.setattr(publisher, "_client", _StubOfflineClient())
    assert publisher.collect_instagram_insights() == []


def test_collect_insights_never_raises(publisher, monkeypatch):
    class _Boom:
        available = True

        def instagram_media_list(self, limit=50):
            raise RuntimeError("composio down")

    monkeypatch.setattr(publisher, "_client", _Boom())
    assert publisher.collect_instagram_insights() == []
