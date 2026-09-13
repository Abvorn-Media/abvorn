"""LinkedIn image-post path tests.

The publisher posts LinkedIn with composed product cards attach as real
images (media category IMAGE) — the bare link-preview card is a last-resort
fallback, and export is only reached when neither works.
"""
import pytest
from PIL import Image

from abvorn.domination.social_publisher import _linkedin_params, SocialPublisher
from abvorn.deploy.composio_client import ComposioClient

POST = {
    "title": "Best 4K Monitors 2026",
    "post": "After comparing specs, prices, and owner feedback, here's what stands out.",
    "body": "Actual body copy.",
    "url": "https://abvorn.com/reviews/4k-monitors/",
}


@pytest.fixture
def publisher():
    return SocialPublisher(composio_key="test_key")


@pytest.fixture(autouse=True)
def _gate_on_for_routing(monkeypatch):
    """The routing tests exercise publish() past the gate + scoping.

    Gate default marker exists but data/social_platforms.txt scopes live
    posting to x/pinterest/medium, so force both on for the LinkedIn path.
    """
    monkeypatch.setenv("ABVORN_SOCIAL_PUBLISH", "1")
    monkeypatch.setenv("ABVORN_SOCIAL_PLATFORMS", "linkedin,x")


def _make_images(tmp_path, n=2):
    paths = []
    for i in range(n):
        p = tmp_path / f"share_{i}.jpg"
        Image.new("RGB", (1200, 627), (i * 20, 20, 20)).save(p)
        paths.append(str(p))
    return paths


# ----------------------------------------------------------------------------
# ComposioClient.linkedin_publish_image_post
# ----------------------------------------------------------------------------


def test_linkedin_image_post_builds_uploadables(monkeypatch, tmp_path):
    from abvorn.deploy.composio_client import ComposioClient
    from abvorn.deploy.social import COMPOSIO_TOOLS
    paths = _make_images(tmp_path)

    c = ComposioClient(api_key="k")
    monkeypatch.setattr(c, "resolve_connection", lambda t: ("u", "ca_linkedin", "v"))
    monkeypatch.setattr(c, "linkedin_author_urn", lambda: "urn:li:person:abc")

    captured = {}
    dd = {}

    class _FakeFileUploadable:
        def __init__(self, **kw):
            dd["path"] = kw.get("file")
            self._dump = {
                "name": kw.get("file", "").split("/")[-1],
                "mimetype": "image/jpeg",
                "s3key": "fake-key",
            }

        def model_dump(self):
            return self._dump

        @classmethod
        def from_path(cls, **kw):
            return cls(**kw)

    import composio.core.models._files as _files
    monkeypatch.setattr(_files, "FileUploadable", _FakeFileUploadable)

    def fake_execute(toolkit, slug, arguments):
        captured["toolkit"] = toolkit
        captured["slug"] = slug
        captured["arguments"] = arguments
        return {"id": "post-1"}

    monkeypatch.setattr(c, "execute", fake_execute)

    out = c.linkedin_publish_image_post(
        "Comparing specs, prices, and owner feedback.",
        paths,
        author_urn="urn:li:person:abc",
    )
    assert out == {"id": "post-1"}
    assert captured["toolkit"] == "linkedin"
    assert captured["slug"] == COMPOSIO_TOOLS["linkedin"]["slug"]
    args = captured["arguments"]
    assert args["author"] == "urn:li:person:abc"
    assert args["commentary"].startswith("Comparing specs")
    assert len(args["images"]) == 2
    assert args["images"][0]["mimetype"] == "image/jpeg"
    assert args["images"][0]["s3key"]


def test_linkedin_image_post_raises_on_unreadable_file(monkeypatch, tmp_path):
    """A missing file must surface as an exception (caller falls back)."""
    from pathlib import Path

    from abvorn.deploy.composio_client import ComposioClient
    good = tmp_path / "good.jpg"
    Image.new("RGB", (1200, 627), (20, 20, 20)).save(good)
    paths = [str(good), str(tmp_path / "missing.jpg")]

    c = ComposioClient(api_key="k")
    monkeypatch.setattr(c, "resolve_connection", lambda t: ("u", "ca", "v"))
    monkeypatch.setattr(c, "linkedin_author_urn", lambda: "urn:li:person:abc")

    seen = []

    class _FakeFileUploadable:
        def __init__(self, **kw):
            seen.append(Path(kw.get("file")))

        def model_dump(self):
            return {"name": "x.jpg", "mimetype": "image/jpeg", "s3key": "k"}

        @classmethod
        def from_path(cls, **kw):
            path = Path(kw["file"])
            if not path.is_file():
                raise FileNotFoundError(path)
            return cls(**kw)

    import composio.core.models._files as _files
    monkeypatch.setattr(_files, "FileUploadable", _FakeFileUploadable)

    with pytest.raises(FileNotFoundError):
        c.linkedin_publish_image_post("c", paths, author_urn="urn:li:person:abc")
    assert len(seen) == 1  # only the readable file was turned into an uploadable


# ----------------------------------------------------------------------------
# SocialPublisher LinkedIn image routing
# ----------------------------------------------------------------------------


def test_linkedin_publish_prefers_image_post_when_media(publisher, monkeypatch, tmp_path):
    paths = _make_images(tmp_path)

    def fake_image_post(commentary, image_paths, author_urn=""):
        return {"id": "img-post"}

    monkeypatch.setattr(publisher._client, "linkedin_publish_image_post", fake_image_post)
    monkeypatch.setattr(publisher._client, "linkedin_author_urn", lambda: "urn:li:person:abc")
    result = publisher.publish(POST, "linkedin", "4k-monitors", media_paths=paths)
    assert result["status"] == "posted"
    assert result["tool"] == "LINKEDIN_CREATE_LINKED_IN_POST"


def test_linkedin_publish_falls_back_to_url_share_when_image_fails(publisher, monkeypatch, tmp_path):
    paths = _make_images(tmp_path)

    def boom_image_post(commentary, image_paths, author_urn=""):
        raise RuntimeError("image upload downstream failed")

    monkeypatch.setattr(publisher._client, "linkedin_publish_image_post", boom_image_post)
    monkeypatch.setattr(publisher._client, "linkedin_author_urn", lambda: "urn:li:person:abc")

    URLCALL = {}
    def fake_execute(toolkit, slug, arguments):
        if slug == "LINKEDIN_CREATE_ARTICLE_OR_URL_SHARE":
            URLCALL["hit"] = True
            return {"id": "url-share-1"}
        raise AssertionError(f"unexpected {slug}")

    monkeypatch.setattr(publisher._client, "execute", fake_execute)
    result = publisher.publish(POST, "linkedin", "4k-monitors", media_paths=paths)
    assert result["status"] == "posted"
    assert result["tool"] == "LINKEDIN_CREATE_ARTICLE_OR_URL_SHARE"
    assert URLCALL.get("hit")


def test_linkedin_publish_no_media_uses_url_share_directly(publisher, monkeypatch):
    def fake_execute(toolkit, slug, arguments):
        assert slug == "LINKEDIN_CREATE_ARTICLE_OR_URL_SHARE"
        return {"id": "u2"}

    monkeypatch.setattr(publisher._client, "linkedin_author_urn", lambda: "urn:li:person:abc")
    monkeypatch.setattr(publisher._client, "execute", fake_execute)
    result = publisher.publish(POST, "linkedin", "4k-monitors", media_paths=[])
    assert result["status"] == "posted"


def test_linkedin_publish_exports_when_composio_fails(publisher, monkeypatch, tmp_path):
    paths = _make_images(tmp_path)

    monkeypatch.setattr(publisher._client, "linkedin_author_urn", lambda: "urn:li:person:abc")

    def boom_image_post(*a, **k):
        raise RuntimeError("image upload downstream failed")
    monkeypatch.setattr(publisher._client, "linkedin_publish_image_post", boom_image_post)

    def boom_execute(*a, **k):
        raise RuntimeError("composio down")
    monkeypatch.setattr(publisher._client, "execute", boom_execute)

    result = publisher.publish(POST, "linkedin", "4k-monitors", media_paths=paths)
    assert result["status"] == "exported"


def test_linkedin_params_carry_real_url_and_copy():
    params = _linkedin_params(POST)
    assert params["commentary"] == POST["post"]
    assert params.get("url") == POST["url"]
    assert params.get("title") == POST["title"]