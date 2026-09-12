"""Pinterest live-pin flow + per-platform persona body copy."""

import json
from pathlib import Path

import pytest
from PIL import Image

from abvorn.domination.social_publisher import SocialPublisher
from abvorn.domination.viral_script_generator import ViralScriptGenerator
from abvorn.persona.engine import PERSONA_TEMPLATES

PERSONA = PERSONA_TEMPLATES["gaming mice"][0]  # Competitive Calvin (anxieties/hopes set)

POST = {
    "title": "Best Gaming Mice 2026",
    "niche": "gaming-mice",
    "summary": "Sub-50g wireless, flawless tracking, honest prices.",
    "url": "https://abvorn.com/reviews/gaming-mice/",
    "hooks": {},
}


@pytest.fixture
def publisher():
    return SocialPublisher(composio_key="test_key")


def _gen_script(platform):
    return ViralScriptGenerator().generate(POST, platforms=[platform])[platform]["script"]


# ----------------------------------------------------------------------------
# Per-platform persona body copy (LinkedIn / Telegram / X)
# ----------------------------------------------------------------------------


def test_persona_body_requires_persona():
    gen = ViralScriptGenerator()
    assert gen._persona_body("gaming-mice", None, 3, platform="linkedin") is None


def test_persona_body_leads_with_pain_for_text_platforms():
    gen = ViralScriptGenerator()
    body = gen._persona_body("gaming-mice", PERSONA, 3, platform="linkedin")
    assert body
    assert "mis" in body or "shots" in body  # persona pain surfacing
    assert "sub-50g" in body  # persona hope surfacing
    assert "tested" not in body.lower()  # no false testing claim
    assert "tired of" in body.lower() or "buyers want" in body.lower()


def test_persona_body_x_is_tight():
    gen = ViralScriptGenerator()
    line = gen._persona_body("gaming-mice", PERSONA, 3, platform="x")
    assert line
    assert len(line) <= 280


def test_linkedin_body_gets_persona_lead():
    gen = ViralScriptGenerator()
    result = gen.generate(POST, platforms=["linkedin"], persona=PERSONA)["linkedin"]
    assert result["persona"] == PERSONA["name"]
    body = result["script"]["body"]
    assert "tired of" in body.lower()  # persona lead in body, not just hook
    assert "Sub-50g wireless" in body  # editorial body still present


def test_linkedin_body_generic_without_persona():
    script = _gen_script("linkedin")
    assert "tired of" not in script["body"].lower()


def test_telegram_body_gets_persona_lead():
    gen = ViralScriptGenerator()
    result = gen.generate(POST, platforms=["telegram"], persona=PERSONA)["telegram"]
    assert result["persona"] == PERSONA["name"]
    assert "tired of" in result["script"]["text"].lower()
    assert "honest prices" in result["script"]["text"].lower()


def test_telegram_body_generic_without_persona():
    script = _gen_script("telegram")
    assert "tired of" not in script["text"].lower()


def test_thread_gets_persona_line():
    gen = ViralScriptGenerator()
    thread = gen.generate(POST, platforms=["x"], persona=PERSONA)["x"]["script"]
    assert thread[0]  # hook first
    persona_line = thread[1] if len(thread) > 1 else ""
    assert "tired of" in persona_line.lower()
    assert len(persona_line) <= 280


def test_thread_generic_without_persona():
    thread = _gen_script("x")
    assert all("tired of" not in t.lower() for t in thread)


# ----------------------------------------------------------------------------
# Pinterest: pin script carries url + live flow is wired
# ----------------------------------------------------------------------------


def test_pin_script_carries_url():
    script = _gen_script("pinterest")
    assert script["url"] == POST["url"]
    assert script["title"]


def test_pinterest_flow_is_wired_live(publisher):
    client = publisher._client
    assert client is not None
    # the platform mapping must target the real tools, not export-only
    from abvorn.domination.social_publisher import PLATFORM_ACTIONS
    action = PLATFORM_ACTIONS["pinterest"]
    assert action.get("flow") == "pin"
    assert action.get("slug") == "PINTEREST_CREATE_PIN"
    assert not action.get("export_only")


def test_honest_pin_description(publisher):
    desc = publisher._honest_pinterest_description(
        {"description": "We tested 20+ mice to find the best."}, "gaming-mice"
    )
    assert "tested" not in desc.lower()
    assert "#gamingmice" in desc


def test_pinterest_export_when_no_media(publisher, monkeypatch, tmp_path):
    monkeypatch.setattr("abvorn.domination.social_publisher.EXPORT_DIR", tmp_path / "exports")
    result = publisher._publish_pinterest_pin(POST, "pinterest", "gaming-mice", [])
    assert result["status"] == "exported"


def test_pinterest_posts_when_media_and_client_ok(publisher, monkeypatch, tmp_path):
    img = tmp_path / "pin.jpg"
    Image.new("RGB", (1000, 1500), (5, 5, 5)).save(img)

    calls = {}

    class FakeClient:
        def pinterest_board_id(self):
            return "9999"
        def pinterest_publish_pin(self, **kw):
            calls.update(kw)
            return {"id": "123"}

    monkeypatch.setattr(publisher, "_client", FakeClient())
    result = publisher._publish_pinterest_pin(POST, "pinterest", "gaming-mice", [str(img)])
    assert result["status"] == "posted"
    assert calls["board_id"] == "9999"
    assert calls["title"]
    assert calls["description"]
    assert calls["link"] == POST["url"]


def test_pinterest_export_when_client_fails(publisher, monkeypatch, tmp_path):
    img = tmp_path / "pin.jpg"
    Image.new("RGB", (1000, 1500), (5, 5, 5)).save(img)

    class BoomClient:
        def pinterest_board_id(self):
            raise RuntimeError("composio down")
        def pinterest_publish_pin(self, **kw):
            raise AssertionError("must not be called")

    monkeypatch.setattr(publisher, "_client", BoomClient())
    monkeypatch.setattr("abvorn.domination.social_publisher.EXPORT_DIR", tmp_path / "exports")
    result = publisher._publish_pinterest_pin(POST, "pinterest", "gaming-mice", [str(img)])
    assert result["status"] == "exported"


# ----------------------------------------------------------------------------
# ComposioClient pin source building
# ----------------------------------------------------------------------------


def _fake_client(monkeypatch, execute_result=None, board_id="555"):
    from abvorn.deploy import composio_client as cc
    c = cc.ComposioClient(api_key="k")
    c._pinterest_board_id = board_id
    captured = {}

    def fake_execute(toolkit, slug, arguments):
        captured["toolkit"] = toolkit
        captured["slug"] = slug
        captured["arguments"] = arguments
        if not execute_result:
            raise AssertionError("unexpected execute")
        return execute_result

    monkeypatch.setattr(c, "execute", fake_execute)
    return c, captured


def test_composio_pin_single_image_uses_base64_source(monkeypatch, tmp_path):
    from abvorn.deploy.composio_client import PINTEREST_CREATE_PIN_TOOL, PINTEREST_TOOLKIT
    img = tmp_path / "one.jpg"
    Image.new("RGB", (1000, 1500), (10, 10, 10)).save(img)

    c, captured = _fake_client(monkeypatch, execute_result={"id": "p1"})
    c.pinterest_publish_pin("555", [str(img)], title="T", description="D", link="L")
    args = captured["arguments"]
    assert captured["slug"] == PINTEREST_CREATE_PIN_TOOL
    assert captured["toolkit"] == PINTEREST_TOOLKIT
    assert args["board_id"] == "555"
    assert args["media_source"]["source_type"] == "image_base64"
    assert args["media_source"]["content_type"] == "image/jpeg"
    assert args["media_source"]["data"]


def test_composio_pin_carousel_when_multi_image(monkeypatch, tmp_path):
    paths = []
    for i in range(3):
        p = tmp_path / f"p{i}.jpg"
        Image.new("RGB", (1000, 1500), (i, i, i)).save(p)
        paths.append(str(p))

    c, captured = _fake_client(monkeypatch, execute_result={"id": "c1"})
    c.pinterest_publish_pin("555", paths, title="C")
    source = captured["arguments"]["media_source"]
    assert source["source_type"] == "multiple_image_base64"
    assert 2 <= len(source["items"]) <= 5


def test_composio_pin_no_readable_media_raises(monkeypatch, tmp_path):
    from abvorn.deploy.composio_client import ComposioClient
    c = ComposioClient(api_key="k")
    monkeypatch.setattr(c, "execute", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")))
    with pytest.raises(RuntimeError):
        c.pinterest_publish_pin("555", [str(tmp_path / "missing.jpg")])


def test_composio_board_id_env_override(monkeypatch):
    from abvorn.deploy.composio_client import ComposioClient
    monkeypatch.setenv("PINTEREST_BOARD_ID", "env-board")
    c = ComposioClient(api_key="k")
    assert c.pinterest_board_id() == "env-board"


def test_composio_board_autocreate(monkeypatch, tmp_path):
    from abvorn.deploy.composio_client import ComposioClient, PINTEREST_CREATE_BOARD_TOOL
    monkeypatch.delenv("PINTEREST_BOARD_ID", raising=False)
    monkeypatch.setattr(
        "abvorn.deploy.composio_client.Path.home",
        lambda: tmp_path / "home",
    )
    c = ComposioClient(api_key="k")

    calls = {}
    def fake_execute(toolkit, slug, arguments):
        calls["slug"] = slug
        calls["args"] = arguments
        return {"id": "new-board"}

    monkeypatch.setattr(c, "execute", fake_execute)
    monkeypatch.setattr(c, "resolve_connection", lambda *a: ("u", "c", "v"))
    assert c.pinterest_board_id() == "new-board"
    assert calls["slug"] == PINTEREST_CREATE_BOARD_TOOL
    assert calls["args"]["name"] == "Abvorn Finds"
    # persisted for the next process
    assert (tmp_path / "home" / ".abvorn" / "pinterest_board_id.txt").read_text(encoding="utf-8") == "new-board"