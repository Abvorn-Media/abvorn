import pytest
from abvorn.deploy.social import SocialDeployer, TelegramDeployer
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


def test_telegram_deployer_retries_once_on_429(monkeypatch):
    """Bot API 429+retry_after must be honored with one retry, not dropped."""
    monkeypatch.setattr("abvorn.deploy.social.time.sleep", lambda s: None)
    calls = {"n": 0}

    class FakeResp:
        def __init__(self, code, ok=False):
            self.status_code = code
            self._ok = ok

        def json(self):
            if self.status_code == 429:
                return {"parameters": {"retry_after": 1}}
            return {"ok": self._ok}

    def fake_post(*a, **k):
        calls["n"] += 1
        return FakeResp(429 if calls["n"] == 1 else 200, ok=True)

    monkeypatch.setattr("abvorn.deploy.social.requests.post", fake_post)
    d = TelegramDeployer(token="t", chat_id="c", channel="")
    result = d.post({"text": "hello"})
    assert result["status"] == "posted"
    assert calls["n"] == 2


def test_post_x_without_key(monkeypatch):
    """Should NOT post — with the publish gate OFF, drafts are staged."""
    monkeypatch.setattr("abvorn.core.social_gate.require_social_publishing", lambda state=None: False)
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


def test_resolve_url_priority(monkeypatch):
    monkeypatch.delenv("SITE_URL", raising=False)
    from abvorn.platform.adapters import resolve_url
    assert resolve_url({"url": "https://x.test/a", "slug": "b"}) == "https://x.test/a"
    assert resolve_url({"link": "https://x.test/a", "url": ""}) == "https://x.test/a"
    assert resolve_url({"slug": "b"}) == "https://abvorn.com/b"
    assert resolve_url({"niche": "4k-monitors"}) == "https://abvorn.com/reviews/4k-monitors/"
    assert resolve_url({}) == ""


def test_linkedin_adapter_includes_real_url_no_placeholder(monkeypatch):
    monkeypatch.delenv("SITE_URL", raising=False)
    from abvorn.platform.adapters import linkedin_adapter
    content = {
        "post_title": "Best 4K Monitors 2026",
        "niche": "4k-monitors",
        "intro": "<p>We tested 20+ monitors side by side for hours.</p>",
        "article_html": "<h2>Brightness: the numbers</h2><h2>Color Accuracy</h2><h2>Ergonomics</h2>",
        "meta_description": "The honest verdict on the best 4K monitors, tested side by side.",
    }
    out = linkedin_adapter(content)
    assert "https://abvorn.com/reviews/4k-monitors/" in out["post"]
    assert "[link]" not in out["post"]
    assert out["url"] == "https://abvorn.com/reviews/4k-monitors/"
    assert "lab-tested" not in out["post"]
    assert "✅" in out["post"]


def test_x_adapter_last_tweet_has_real_url(monkeypatch):
    monkeypatch.delenv("SITE_URL", raising=False)
    from abvorn.platform.adapters import x_adapter
    content = {
        "post_title": "Best 4K Monitors 2026",
        "niche": "4k-monitors",
        "intro": "<p>We tested 20+ monitors side by side.</p>",
        "article_html": "<h2>Brightness</h2><h2>Color Accuracy</h2>",
    }
    thread = x_adapter(content)
    assert "https://abvorn.com/reviews/4k-monitors/" in thread[-1]
    assert "[link]" not in "\n".join(thread)


def test_facebook_adapter_uses_real_url(monkeypatch):
    monkeypatch.delenv("SITE_URL", raising=False)
    from abvorn.platform.adapters import facebook_adapter
    out = facebook_adapter({"post_title": "Test", "niche": "4k-monitors", "meta_description": "Desc"})
    assert out["link"] == "https://abvorn.com/reviews/4k-monitors/"


def test_post_copy_avoids_false_testing_claims(monkeypatch):
    """Live adapter copy must never claim we physically buy/test products.

    We do research-based comparison (specs, prices, owner feedback) — not
    hands-on lab testing — so no generated post may claim otherwise.
    """
    monkeypatch.delenv("SITE_URL", raising=False)
    from abvorn.platform.adapters import (
        x_adapter, linkedin_adapter, tiktok_adapter, facebook_adapter,
    )
    content = {
        "post_title": "Best 4K Monitors 2026",
        "niche": "4k-monitors",
        "intro": "<p>We physically tested 20+ monitors side by side in our lab.</p>",
        "article_html": "<h2>Brightness</h2><h2>Color Accuracy</h2><h2>Ergonomics</h2>",
        "meta_description": "We bought and tested every 4K monitor to find the best one.",
    }
    forbidden = ["we tested", "we test", "we buy", "we bought", "lab-test", "hands-on"]
    outputs = [
        "\n".join(x_adapter(content)),
        linkedin_adapter(content).get("post", ""),
        tiktok_adapter(content).get("body", ""),
        facebook_adapter(content).get("message", ""),
    ]
    for out in outputs:
        lower = out.lower()
        for phrase in forbidden:
            assert phrase not in lower, f"false claim '{phrase}' leaked into post: {out}"


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


def test_post_stages_clean_content_through_guard(monkeypatch):
    monkeypatch.setattr("abvorn.core.social_gate.require_social_publishing", lambda state=None: False)
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


def test_gate_on_but_platform_not_allowed_stays_staged(monkeypatch):
    """Gate ON + platform scoping env must leave disallowed platforms staged."""
    monkeypatch.setenv("ABVORN_SOCIAL_PUBLISH", "1")
    monkeypatch.setenv("ABVORN_SOCIAL_PLATFORMS", "x,medium")
    deployer = SocialDeployer(composio_key="test_key")
    content = {"post_title": "Test", "intro": "<p>Test</p>", "article_html": "<p>Body</p>", "tags": []}
    result = deployer.post(content, "linkedin")
    assert result["status"] == "staged"
    assert result["platform"] == "linkedin"


def test_gate_on_allowed_platform_proceeds_past_scoping(monkeypatch):
    """Gate ON + allowed platform must NOT be blocked by scoping."""
    monkeypatch.setenv("ABVORN_SOCIAL_PUBLISH", "1")
    monkeypatch.setenv("ABVORN_SOCIAL_PLATFORMS", "x,medium")
    deployer = SocialDeployer()  # no composio key
    content = {"post_title": "Test", "intro": "<p>Test</p>", "article_html": "<p>Body</p>", "tags": []}
    result = deployer.post(content, "x")
    # Passed the scoping gate; with no key it must be "skipped", not a live post.
    assert result["status"] == "skipped"
    assert result["reason"] == "no_composio_key"