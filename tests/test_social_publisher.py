import pytest

from abvorn.domination.social_publisher import (
    _extract_text,
    _linkedin_params,
    _linkedin_url_share_args,
    SocialPublisher,
)
from abvorn.domination.viral_script_generator import ViralScriptGenerator


def test_extract_text_dict_body():
    assert _extract_text({"body": "Hello"}) == "Hello"
    assert _extract_text(["a", "b"]) == "a\nb"


def test_linkedin_params_non_empty_with_empty_body_and_url():
    """Empty-body scripts (feed.xml has no descriptions) must NOT yield an
    empty commentary when a URL is attached — a bare-link post is a bug."""
    script = {
        "headline": "I spent months researching mice. Here's what matters.",
        "body": "",
        "engagement_question": "What's your experience? Drop it below",
        "url": "https://abvorn.com/reviews/gaming-mice/",
    }
    params = _linkedin_params(script)
    assert params["url"] == script["url"]
    assert params["commentary"].strip()
    assert script["headline"] in params["commentary"]


def test_linkedin_params_neutral_default_when_no_text_keys():
    script = {"url": "https://abvorn.com/reviews/webcams/"}
    params = _linkedin_params(script)
    assert params["commentary"].strip()
    assert params["url"] == script["url"]


def test_linkedin_url_share_args_has_non_empty_commentary():
    params = {
        "author": "urn:li:person:123",
        "commentary": "After comparing real specs and prices, here's what stands out.",
        "url": "https://abvorn.com/reviews/tv/",
        "title": "Best TVs",
        "description": "",
    }
    args = _linkedin_url_share_args(params)
    assert args is not None
    text = args["specificContent"]["com.linkedin.ugc.ShareContent"]["shareCommentary"]["text"]
    assert text.strip()


def test_linkedin_script_has_body_when_summary_empty():
    gen = ViralScriptGenerator()
    post = {
        "title": "Best Gaming Mice 2026",
        "niche": "gaming-mice",
        "summary": "",
        "url": "https://abvorn.com/reviews/gaming-mice/",
        "hooks": {},
    }
    script = gen.generate(post, platforms=["linkedin"])["linkedin"]["script"]
    assert script["url"] == post["url"]
    assert script["body"].strip()


def test_linkedin_script_preserves_summary_body_when_present():
    gen = ViralScriptGenerator()
    post = {
        "title": "Best Webcams 2026",
        "niche": "webcams",
        "summary": "Sharp picture, great low light, plug-and-play on every OS.",
        "url": "https://abvorn.com/reviews/webcams/",
        "hooks": {},
    }
    script = gen.generate(post, platforms=["linkedin"])["linkedin"]["script"]
    assert "Sharp picture" in script["body"]


def test_linkedin_post_text_is_hook_led_and_complete():
    """The LinkedIn post must lead with the hook and carry the question + URL,
    not dump raw summary paragraphs (the "boring post" bug)."""
    gen = ViralScriptGenerator()
    post = {
        "title": "Best Webcams 2026",
        "niche": "webcams",
        "summary": "Sharp picture, great low light, plug-and-play on every OS.",
        "url": "https://abvorn.com/reviews/webcams/",
        "hooks": {},
    }
    script = gen.generate(post, platforms=["linkedin"])["linkedin"]["script"]
    post_text = script["post"]
    assert script["headline"].lstrip(" .\u2022").strip() in post_text
    assert "Sharp picture" in post_text
    assert "experience with webcams" in post_text
    assert "Full guide:" in post_text
    assert post["url"] in post_text
    assert _linkedin_params(script)["commentary"] == post_text


def test_telegram_generates_text_script_with_url():
    gen = ViralScriptGenerator()
    post = {
        "title": "Best Laptops 2026",
        "niche": "laptops",
        "summary": "Fast CPUs, long battery life, solid screens.",
        "url": "https://abvorn.com/reviews/laptops/",
        "hooks": {},
    }
    result = gen.generate(post, platforms=["telegram"])
    assert "telegram" in result
    script = result["telegram"]["script"]
    assert "text" in script
    assert post["url"] in script["text"]
    assert len(script["text"]) <= 2000


def test_telegram_script_strips_stray_leading_dot():
    gen = ViralScriptGenerator()
    script = gen._telegram_script(
        "t", ". How to choose the right mouse in 5 steps.",
        "", "gaming-mice", "https://abvorn.com/reviews/gaming-mice/",
    )
    assert script["text"].startswith("How to choose")


def test_telegram_script_no_duplicate_hook_on_empty_summary():
    """feed.xml has no descriptions, so empty-summary scripts must not repeat
    the hook twice in the post."""
    gen = ViralScriptGenerator()
    post = {
        "title": "Best Laptops 2026",
        "niche": "laptops",
        "summary": "",
        "url": "https://abvorn.com/reviews/laptops/",
        "hooks": {},
    }
    text = gen.generate(post, platforms=["telegram"])["telegram"]["script"]["text"]
    assert text.count("Nobody talks about this") <= 1
    assert text.count(text.strip().splitlines()[0]) == 1


def test_linkedin_post_no_duplicate_hook_on_empty_summary():
    gen = ViralScriptGenerator()
    post = {
        "title": "Best Laptops 2026",
        "niche": "laptops",
        "summary": "",
        "url": "https://abvorn.com/reviews/laptops/",
        "hooks": {},
    }
    post_text = gen.generate(post, platforms=["linkedin"])["linkedin"]["script"]["post"]
    first_line = post_text.strip().splitlines()[0]
    assert post_text.count(first_line) == 1
    assert post_text.count("After comparing real specs") == 1


def test_social_publisher_posts_telegram_without_composio(publisher, monkeypatch):
    """Telegram must post via the Bot API even when Composio is unavailable."""
    monkeypatch.setenv("ABVORN_SOCIAL_PUBLISH", "1")
    monkeypatch.setenv("ABVORN_SOCIAL_PLATFORMS", "telegram")

    class FakeDeployer:
        def post(self, adapted, enable_preview: bool = False):
            return {"status": "posted", "platform": "telegram", "chat_id": "@abvorn"}

    monkeypatch.setattr("abvorn.deploy.social.TelegramDeployer", FakeDeployer)
    result = publisher.publish(
        {"text": "Hot take: most laptops are overpriced.\n\nFull guide: https://abvorn.com/reviews/laptops/"},
        "telegram",
        "laptops",
    )
    assert result["status"] == "posted"


@pytest.fixture
def publisher():
    return SocialPublisher(composio_key="test_key")