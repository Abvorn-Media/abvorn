import pytest
from abvorn.domination.social_publisher import SocialPublisher


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
