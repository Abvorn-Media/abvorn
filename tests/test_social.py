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
    """Should skip posting when no Composio key."""
    deployer = SocialDeployer()
    content = {"post_title": "Test", "intro": "", "article_html": "", "tags": []}
    result = deployer.post(content, "x")
    assert result["status"] == "skipped"


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