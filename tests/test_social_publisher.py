import pytest

from abvorn.domination.social_publisher import (
    _extract_text,
    _linkedin_params,
    _linkedin_url_share_args,
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