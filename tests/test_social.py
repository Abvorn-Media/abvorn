import pytest
from abvorn.deploy.social import SocialDeployer
from abvorn.platform import registry


@pytest.fixture(autouse=True)
def ensure_registry():
    """Ensure platform adapters are registered."""
    from abvorn.platform import adapters  # noqa: F401
    return registry


def test_social_deployer_init():
    """Should initialize without real credentials."""
    deployer = SocialDeployer(composio_key="test_key")
    assert deployer is not None


def test_post_x_without_key():
    """Should NOT post — publish gate is off by default, so drafts are staged."""
    deployer = SocialDeployer()
    content = {"post_title": "Test", "intro": "", "article_html": "", "tags": []}
    result = deployer.post(content, "x")
    assert result["status"] == "staged"


def test_post_unknown_platform():
    """Should return error for unknown platform."""
    deployer = SocialDeployer()
    result = deployer.post({}, "nonexistent")
    assert result["status"] == "error"


def test_post_to_all():
    """Should post to all registered social platforms."""
    deployer = SocialDeployer()
    content = {"post_title": "Test", "intro": "<p>Test</p>", "article_html": "<p>Body</p>", "tags": ["test"]}
    results = deployer.post_to_all(content)
    assert len(results) > 0


def test_list_platforms():
    """Registry should list all platforms."""
    from abvorn.platform import adapters  # noqa: F401
    platforms = registry.list()
    assert "x" in platforms
    assert "linkedin" in platforms
    assert "facebook" in platforms
    assert "youtube" in platforms


def test_facebook_stub():
    """Facebook should adapt without error."""
    from abvorn.platform.adapters import facebook_adapter
    result = facebook_adapter({"post_title": "Test", "meta_description": "Desc"})
    assert "message" in result or "link" in result


def test_youtube_stub():
    """YouTube should adapt without error."""
    from abvorn.platform.adapters import youtube_adapter
    content = {"post_title": "Test", "intro": "Intro", "article_html": "<h2>Section 1</h2><h2>Section 2</h2>", "meta_description": "Desc"}
    result = youtube_adapter(content)
    assert "script" in result
    assert "description" in result


def test_sanitize_encoding_repairs_mojibake_in_string():
    deployer = SocialDeployer()
    corrupted = "price \u00e2\u20ac\u009d worth"  # "price ” worth" double-encoded
    cleaned = deployer._sanitize_encoding(corrupted, "x")
    assert "\u201d" in cleaned
    assert "\u00e2" not in cleaned


def test_sanitize_encoding_repairs_list_and_dict():
    deployer = SocialDeployer()
    corrupted_str = "John\u2019s \u00e2\u20ac\u009d pick"
    list_in = [corrupted_str, "fine"]
    dict_in = {"text": corrupted_str, "title": "ok"}
    out_list = deployer._sanitize_encoding(list_in, "x")
    out_dict = deployer._sanitize_encoding(dict_in, "linkedin")
    assert "\u201d" in out_list[0]
    assert out_list[1] == "fine"
    assert "\u201d" in out_dict["text"]
    assert out_dict["title"] == "ok"


def test_post_stages_clean_content_through_guard():
    deployer = SocialDeployer()
    content = {"post_title": "Best mice — 2026", "intro": "<p>Real em dash — fine.</p>", "article_html": "<p>Body</p>", "tags": ["mice"]}
    result = deployer.post(content, "x")
    assert result["status"] == "staged"
    assert "—" in str(result["data"])


def test_post_raises_on_unrepairable_mojibake():
    """Content that still carries mojibake after repair must be blocked."""
    deployer = SocialDeployer()
    # U+FFFD replacement char cannot be repaired — must be blocked.
    content = {"post_title": "Test", "intro": "<p>Broken \ufffd text</p>", "article_html": "<p>Body</p>", "tags": []}
    with pytest.raises(ValueError, match="Mojibake"):
        deployer.post(content, "x")