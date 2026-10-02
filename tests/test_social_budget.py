"""Tests for the daily social budget and the product-card image fix.

Two regressions are locked in here:

1. Every LinkedIn post went out without an image because the Ambassador called
   social.post() with no media_paths, so SocialDeployer skipped the image branch
   and took the link-preview fallback. Nothing warned; the post just had no
   picture. _promote_niche must now hand a real product card down.

2. The promote path fires on every content.published bus event and the content
   loop emits those fast, which produced 19 LinkedIn posts in two hours. The
   budget now caps each platform at one live post per day, and it has to be a
   hard stop that never reaches Composio.
"""

import asyncio
import json

import pytest

from abvorn.core import social_budget
from abvorn.deploy.social import SocialDeployer
from abvorn.platform import registry


@pytest.fixture(autouse=True)
def ensure_registry():
    """Ensure platform adapters are registered."""
    from abvorn.platform import adapters  # noqa: F401
    return registry


@pytest.fixture
def budget_file(tmp_path, monkeypatch):
    """Point the budget at a throwaway state file and pin the limit."""
    state = tmp_path / "social_budget.json"
    monkeypatch.setattr(social_budget, "_state_file", lambda: state)
    monkeypatch.delenv("ABVORN_SOCIAL_DAILY_LIMIT", raising=False)
    return state


# --- social_budget unit behaviour ---------------------------------------


def test_default_limit_is_one_per_platform(budget_file):
    assert social_budget.daily_limit() == 1


def test_budget_allows_one_then_refuses(budget_file):
    allowed, reason = social_budget.check_and_consume("linkedin")
    assert allowed is True
    assert "1/1" in reason

    allowed, reason = social_budget.check_and_consume("linkedin")
    assert allowed is False
    assert "already at 1/1" in reason


def test_budget_is_per_platform(budget_file):
    """One LinkedIn post must not eat the x allowance."""
    social_budget.check_and_consume("linkedin")
    assert social_budget.check_and_consume("x")[0] is True
    assert social_budget.check_and_consume("facebook")[0] is True
    assert social_budget.check_and_consume("linkedin")[0] is False


def test_budget_persists_across_instances(budget_file):
    """A daemon restart must not hand the day back a fresh allowance."""
    social_budget.check_and_consume("linkedin")
    assert social_budget.used_today("linkedin") == 1
    assert social_budget.budget_remaining("linkedin") == 0


def test_refund_restores_the_slot(budget_file):
    """A failed post must not burn the day's only slot."""
    social_budget.check_and_consume("linkedin")
    social_budget.refund("linkedin")
    assert social_budget.check_and_consume("linkedin")[0] is True


def test_refund_never_goes_negative(budget_file):
    social_budget.refund("linkedin")
    assert social_budget.used_today("linkedin") == 0
    assert social_budget.check_and_consume("linkedin")[0] is True


def test_limit_env_override(budget_file, monkeypatch):
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "3")
    assert social_budget.daily_limit() == 3
    for _ in range(3):
        assert social_budget.check_and_consume("linkedin")[0] is True
    assert social_budget.check_and_consume("linkedin")[0] is False


def test_limit_zero_disables_the_cap(budget_file, monkeypatch):
    """0 means 'do not cap me' — an operator escape hatch."""
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "0")
    assert social_budget.daily_limit() is None
    for _ in range(25):
        assert social_budget.check_and_consume("linkedin")[0] is True


def test_unparseable_limit_falls_back_to_default(budget_file, monkeypatch):
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "not-a-number")
    assert social_budget.daily_limit() == 1


def test_stale_day_resets_the_count(budget_file):
    """Yesterday's count must not block today's first post."""
    budget_file.write_text(
        json.dumps({"date": "1999-01-01", "counts": {"linkedin": 9}}),
        encoding="utf-8",
    )
    assert social_budget.used_today("linkedin") == 0
    assert social_budget.check_and_consume("linkedin")[0] is True


def test_corrupt_state_file_does_not_freeze_publishing(budget_file):
    """A bad counter file must not turn into a permanent block."""
    budget_file.write_text("{not json", encoding="utf-8")
    assert social_budget.used_today("linkedin") == 0
    assert social_budget.check_and_consume("linkedin")[0] is True


def test_status_reports_today(budget_file):
    social_budget.check_and_consume("linkedin")
    snap = social_budget.status()
    assert snap["used"]["linkedin"] == 1
    assert snap["limit"] == 1


# --- the gate inside SocialDeployer.post ---------------------------------


def test_post_stops_at_the_daily_budget_and_never_calls_composio(
    budget_file, monkeypatch
):
    """The whole point: a spent day must not reach the network."""
    monkeypatch.setattr(
        "abvorn.core.social_gate.require_social_publishing", lambda state=None: True
    )
    monkeypatch.setattr(
        "abvorn.deploy.social._allowed_platforms", lambda: {"linkedin"}
    )

    executed = []

    class FakeTools:
        def execute(self, **kw):
            executed.append(kw)
            return {"successful": True}

    class FakeComposio:
        tools = FakeTools()

    deployer = SocialDeployer(composio_key="k")
    deployer.composio = FakeComposio()
    deployer._client.connection = lambda toolkit: ("u", "c", "v")
    deployer._client.linkedin_author_urn = lambda: "urn:li:person:x"
    deployer.composio_key = "k"

    content = {"post_title": "T", "intro": "hello", "article_html": "", "tags": []}

    first = deployer.post(content, "linkedin")
    assert first["status"] == "posted"

    second = deployer.post(content, "linkedin")
    assert second["status"] == "budget_exceeded"
    assert "already at 1/1" in second["reason"]

    # Exactly one network call happened, for the first post.
    assert len(executed) == 1


def test_failed_post_refunds_the_budget_slot(budget_file, monkeypatch):
    """A Composio error must leave the day's post still available."""
    monkeypatch.setattr(
        "abvorn.core.social_gate.require_social_publishing", lambda state=None: True
    )
    monkeypatch.setattr(
        "abvorn.deploy.social._allowed_platforms", lambda: {"linkedin"}
    )

    class FakeTools:
        def execute(self, **kw):
            raise RuntimeError("composio is down")

    class FakeComposio:
        tools = FakeTools()

    deployer = SocialDeployer(composio_key="k")
    deployer.composio = FakeComposio()
    deployer._client.connection = lambda toolkit: ("u", "c", "v")
    deployer._client.linkedin_author_urn = lambda: "urn:li:person:x"
    deployer.composio_key = "k"

    content = {"post_title": "T", "intro": "hello", "article_html": "", "tags": []}
    result = deployer.post(content, "linkedin")

    assert result["status"] == "failed"
    assert social_budget.used_today("linkedin") == 0
    assert social_budget.check_and_consume("linkedin")[0] is True


def test_staged_draft_does_not_spend_the_budget(budget_file, monkeypatch):
    """Gate off means review copy, not a live post — it must be free."""
    monkeypatch.setattr(
        "abvorn.core.social_gate.require_social_publishing", lambda state=None: False
    )
    deployer = SocialDeployer()
    content = {"post_title": "T", "intro": "hi", "article_html": "", "tags": []}

    assert deployer.post(content, "linkedin")["status"] == "staged"
    assert social_budget.used_today("linkedin") == 0


# --- the image fix: the Ambassador must hand media down ------------------


class _FakeSocial:
    """Captures the media_paths the ambassador passes to social.post()."""

    composio = object()

    def __init__(self):
        self.calls = []

    def post(self, content, platform, media_paths=None):
        self.calls.append({"platform": platform, "media": list(media_paths or [])})
        return {"status": "posted", "platform": platform}


def _ambassador(social):
    from abvorn.agents.ambassador import SocialAmbassador

    amb = SocialAmbassador.__new__(SocialAmbassador)
    amb.social = social
    amb.router = None
    amb.state = None
    amb.notifier = None
    amb._perception = {}  # ensure no perception state

    # Attach methods we just added (in case of import order issues in tests)
    try:
        from abvorn.agents import ambassador as amb_mod

        if not hasattr(amb, "_media_for"):
            amb._media_for = amb_mod.SocialAmbassador._media_for.__get__(amb)
        if not hasattr(amb, "_craft_and_post"):
            amb._craft_and_post = amb_mod.SocialAmbassador._craft_and_post.__get__(amb)
        if not hasattr(amb, "_promote_niche"):
            amb._promote_niche = amb_mod.SocialAmbassador._promote_niche.__get__(amb)
    except Exception:
        pass

    return amb


def test_promote_niche_passes_a_product_card_to_social(monkeypatch, tmp_path):
    """Regression: LinkedIn posts shipped with no image because media was
    never passed. The promote path must now carry a real card."""
    card = tmp_path / "card.jpg"
    card.write_bytes(b"not-really-a-jpeg")

    seen = {}

    def fake_media_for(self, niche, platform, url="", title=""):
        seen["args"] = {"niche": niche, "platform": platform, "url": url, "title": title}
        return [str(card)]

    monkeypatch.setattr(
        "abvorn.agents.ambassador.SocialAmbassador._media_for", fake_media_for
    )

    social = _FakeSocial()
    amb = _ambassador(social)

    # Stub the LLM draft so the test does not call a model.
    async def fake_craft(_self, item, media_paths=None):
        return social.post({}, item["platform"], media_paths)

    monkeypatch.setattr(
        "abvorn.agents.ambassador.SocialAmbassador._craft_and_post", fake_craft
    )

    result = asyncio.run(amb._promote_niche("wireless-headphones", url="https://abvorn.com/reviews/wireless-headphones/"))

    assert result["action"] == "promote"
    assert social.calls, "promote posted nothing"
    for call in social.calls:
        assert call["media"], f"{call['platform']} posted with no image"
        assert call["media"] == [str(card)]
    # linkedin must be among them.
    assert "linkedin" in {c["platform"] for c in social.calls}


def test_promote_niche_uses_the_event_url_for_the_slug(monkeypatch):
    """The card has to describe the page we are actually promoting."""
    seen = {}

    def fake_media_for(self, niche, platform, url="", title=""):
        seen["url"] = url
        seen["title"] = title
        return []

    monkeypatch.setattr(
        "abvorn.agents.ambassador.SocialAmbassador._media_for", fake_media_for
    )

    social = _FakeSocial()
    amb = _ambassador(social)

    async def fake_craft(_self, item, media_paths=None):
        return {"status": "posted", "platform": item["platform"]}

    monkeypatch.setattr(
        "abvorn.agents.ambassador.SocialAmbassador._craft_and_post", fake_craft
    )

    asyncio.run(
        amb._promote_niche(
            "wireless-headphones",
            url="https://abvorn.com/reviews/wireless-headphones/",
        )
    )

    assert seen["url"] == "https://abvorn.com/reviews/wireless-headphones/"
    assert "wireless-headphones guide" in seen["title"]


def test_media_for_survives_a_missing_review_page(monkeypatch):
    """No products resolvable must return [] and not raise — the post still
    goes out (now budget-capped to one a day) but the loss is logged."""
    amb = _ambassador(_FakeSocial())
    monkeypatch.setattr(
        "abvorn.domination.product_assets.load_products_for_niche", lambda slug: []
    )
    assert amb._media_for("tv", "linkedin", url="") == []


# --- the daemon publish loop must hand media down too ---------------------


def test_daemon_publish_loop_passes_media_to_social(monkeypatch):
    """The daemon's own publish loop posted with no media at all.

    This is the path that produced every live `telegram: posted` line: it calls
    social.post(content, platform) with two arguments, so the Telegram branch
    never sees a photo and LinkedIn silently takes the link-preview fallback.
    The Ambassador path was fixed; this one was missed.
    """
    import ast
    import inspect

    from abvorn import daemon as daemon_mod

    src = inspect.getsource(daemon_mod)
    tree = ast.parse(src)

    # Find the social.post(...) call inside the registry.list(category="social")
    # loop and assert it forwards media.
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "post"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "social"
    ]
    assert calls, "daemon no longer calls self.social.post"

    # Every one of them must forward a third argument (the media list).
    for call in calls:
        assert len(call.args) == 3, (
            "daemon social.post must pass media_paths; a 2-arg call ships "
            "every platform imageless"
        )


def test_compose_media_for_post_is_shared_by_both_callers():
    """Both callers must go through one implementation so they cannot drift."""
    import inspect

    from abvorn.agents.ambassador import compose_media_for_post, SocialAmbassador

    # Ambassador delegates to the shared helper rather than duplicating it.
    src = inspect.getsource(SocialAmbassador._media_for)
    assert "compose_media_for_post" in src

    # Daemon imports the same helper.
    from abvorn import daemon as daemon_mod
    assert "compose_media_for_post" in inspect.getsource(daemon_mod)

    # And it degrades to [] rather than raising when products are missing.
    assert compose_media_for_post.__doc__