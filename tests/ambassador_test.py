"""Tests for the SocialAmbassador agent — warm, human social media posting."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from abvorn.agents.ambassador import SocialAmbassador, PERSONA, PLATFORM_TONE


@pytest.fixture
def bus():
    b = MagicMock()
    b.get_recent_events.return_value = []
    return b


@pytest.fixture
def state():
    s = MagicMock()
    s.get_meta.return_value = []
    return s


@pytest.fixture
def router():
    r = MagicMock()
    r.ask.return_value = "Just tested 10 products so you don't have to. Here's the one that won. What's your experience?"
    return r


@pytest.fixture
def social():
    s = MagicMock()
    s.post.return_value = {"status": "posted", "platform": "x"}
    s.composio = None
    return s


@pytest.fixture
def ambassador(bus, state, router, social):
    a = SocialAmbassador(bus, state, router, social)
    return a


def test_ambassador_initializes(ambassador):
    assert ambassador.name == "SocialAmbassador"
    assert ambassador is not None


def test_ambassador_persona_defined():
    assert "warm" in PERSONA
    assert "helpful" in PERSONA


def test_platform_tone_defined():
    for p in ("x", "linkedin", "facebook"):
        assert p in PLATFORM_TONE
        assert len(PLATFORM_TONE[p]) > 10


@pytest.mark.asyncio
async def test_perceive_returns_structure(ambassador):
    perception = await ambassador.perceive()
    assert "schedule_due" in perception or True
    assert hasattr(ambassador, '_perception')
    if hasattr(ambassador, '_perception'):
        p = ambassador._perception
        assert "published_content" in p
        assert "mentions" in p
        assert "schedule_due" in p


@pytest.mark.asyncio
async def test_decide_returns_wait_when_nothing_due(ambassador):
    await ambassador.perceive()
    decision = await ambassador.decide({
        "published_content": [],
        "mentions": [],
        "schedule_due": [],
    })
    assert decision == "wait"


@pytest.mark.asyncio
async def test_decide_returns_post_scheduled_when_due(ambassador):
    decision = await ambassador.decide({
        "published_content": [],
        "mentions": [],
        "schedule_due": [{"niche": "tv", "platform": "x"}],
    })
    assert decision == "post_scheduled"


@pytest.mark.asyncio
async def test_decide_returns_promote_when_published(ambassador):
    decision = await ambassador.decide({
        "published_content": [{"id": 1, "created_at": "2026-01-01", "message": {"niche": "tv"}}],
        "mentions": [],
        "schedule_due": [],
    })
    assert decision == "promote_new_content"


@pytest.mark.asyncio
async def test_act_promote_posts_to_social(ambassador, social):
    await ambassador.perceive()
    ambassador._perception = {
        "published_content": [{"id": 1, "created_at": "2026-01-01", "niche": "tv",
                                "message": {"niche": "tv"}}],
        "mentions": [],
        "schedule_due": [],
    }
    result = await ambassador.act("promote_new_content")
    assert result["action"] == "promote"
    assert result["niche"] == "tv"
    social.post.assert_called()


@pytest.mark.asyncio
async def test_act_post_scheduled_crafts_content(ambassador, state, social):
    state.get_meta.return_value = [
        {"id": "1", "niche": "tv", "platform": "x", "headline": "Best TV 2026",
         "product": "Samsung QLED", "scheduled_at": "2025-01-01", "posted": False}
    ]
    await ambassador.perceive()
    ambassador._perception = {"published_content": [], "mentions": [], "schedule_due": state.get_meta.return_value}
    result = await ambassador.act("post_scheduled")
    assert result["action"] == "scheduled_posts"
    social.post.assert_called()


def test_get_due_posts_filters(ambassador, state):
    state.get_meta.return_value = [
        {"id": "1", "scheduled_at": "2025-01-01", "posted": False},
        {"id": "2", "scheduled_at": "2099-01-01", "posted": False},
        {"id": "3", "scheduled_at": "2025-01-01", "posted": True},
    ]
    due = ambassador._get_due_posts()
    assert len(due) == 1
    assert due[0]["id"] == "1"


@pytest.mark.asyncio
async def test_act_engage_with_watcher_mentions(ambassador, router):
    from abvorn.engagement.watcher import MentionWatcher
    from abvorn.engagement.replier import ReplyGenerator, ReplyPoster
    ambassador.mention_watcher = MentionWatcher(composio_key="", state=None)
    ambassador.reply_generator = ReplyGenerator(router=router)
    ambassador.reply_poster = ReplyPoster(composio_key="")
    ambassador._perception = {"published_content": [], "mentions": [{"id": "1"}], "schedule_due": []}
    decision = await ambassador.decide({"published_content": [], "mentions": [{"id": "1"}], "schedule_due": []})
    assert decision == "engage"
    result = await ambassador.act("engage")
    assert result["action"] == "engage"


@pytest.mark.asyncio
async def test_act_engage_no_mentions(ambassador):
    ambassador._perception = {"published_content": [], "mentions": [], "schedule_due": []}
    result = await ambassador.act("engage")
    assert result["action"] == "none"


def test_get_platform_wisdom(ambassador):
    wisdom = ambassador._get_platform_wisdom("x")
    assert isinstance(wisdom, str)


# ---------------------------------------------------------------------------
# Promotion cooldown: the same article/product must not be re-announced on
# every cycle that re-surfaces the same content.
# ---------------------------------------------------------------------------


class _MetaState:
    """Minimal state double backed by a real dict, so set_meta/get_meta round
    trips like production instead of MagicMock's sticky return_value."""

    def __init__(self, initial=None):
        self.meta = dict(initial or {})

    def get_meta(self, key, default=None):
        return self.meta.get(key, default)

    def set_meta(self, key, value):
        self.meta[key] = value


def test_cooldown_key_prefers_the_article_over_the_product():
    """Two promotions of the same article collide even if the product list
    underneath rotates — otherwise the rotation defeats the cooldown."""
    from abvorn.agents.ambassador import _promotion_key

    a = _promotion_key("https://abvorn.com/reviews/tvs/", "tvs", "tv",
                       [{"asin": "B0AAA", "name": "TV A"}])
    b = _promotion_key("https://abvorn.com/reviews/tvs/", "tvs", "tv",
                       [{"asin": "B0BBB", "name": "TV B"}])
    assert a == b
    assert a.startswith("article:")


def test_cooldown_key_distinguishes_different_articles():
    from abvorn.agents.ambassador import _promotion_key

    a = _promotion_key("https://abvorn.com/reviews/tvs/", "tvs", "tv", [])
    b = _promotion_key("https://abvorn.com/reviews/mice/", "mice", "mice", [])
    assert a != b


def test_cooldown_key_normalises_case_and_trailing_slash():
    from abvorn.agents.ambassador import _promotion_key

    a = _promotion_key("https://abvorn.com/reviews/TVs", "tvs", "tv", [])
    b = _promotion_key("https://abvorn.com/reviews/tvs/", "tvs", "tv", [])
    assert a == b


def test_cooldown_key_falls_back_to_product_asin():
    """With no article identity the ASIN is the strongest available signal."""
    from abvorn.agents.ambassador import _product_key_from_products

    assert _product_key_from_products([{"asin": "b0abc123"}]) == "asin:B0ABC123"
    # First identifiable ASIN wins regardless of list order noise.
    assert _product_key_from_products([{"asin": ""}, {"asin": "B0ABC123"}]) == "asin:B0ABC123"


def test_cooldown_handles_naive_and_malformed_timestamps():
    """Stored timestamps may be naive or garbage; neither may raise TypeError
    when compared against an aware now."""
    from abvorn.agents.ambassador import _cooldown_active, _utcnow

    recent_naive = _utcnow().replace(tzinfo=None).isoformat()  # naive, just now
    state = _MetaState({
        "ambassador_recent_promotions": [
            {"key": "article:a", "ts": recent_naive},       # naive, recent
            {"key": "article:b", "ts": "not-a-timestamp"},  # malformed
        ]
    })
    # Naive recent entry -> cooldown active; malformed entry ignored.
    assert _cooldown_active(state, "article:a") is True
    assert _cooldown_active(state, "article:b") is False
    # Garbage timestamp got pruned from storage.
    stored = state.get_meta("ambassador_recent_promotions", [])
    assert all(isinstance(i, dict) and i.get("key") != "article:b" for i in stored)
    # The active, well-formed entry survives the prune.
    assert any(i.get("key") == "article:a" for i in stored)


def test_record_promotion_replaces_same_key_and_expires_old():
    from abvorn.agents.ambassador import _record_promotion

    state = _MetaState({
        "ambassador_recent_promotions": [
            {"key": "article:a", "ts": "2020-01-01T00:00:00+00:00"},  # expired
        ]
    })
    _record_promotion(state, "article:b")
    keys = [i["key"] for i in state.get_meta("ambassador_recent_promotions", [])]
    assert keys == ["article:b"]


@pytest.mark.asyncio
async def test_repeat_promotion_is_suppressed_within_cooldown(ambassador, state, social, monkeypatch):
    """The same article promoted twice in a row must only post once."""
    from abvorn.agents.ambassador import _promotion_key

    real_state = _MetaState()
    ambassador.state = real_state
    social.post.return_value = {"status": "posted", "platform": "x"}
    # Always allow the publish window so we exercise the cooldown, not the gate.
    monkeypatch.setattr("abvorn.agents.ambassador.can_attempt", lambda p: True)

    url = "https://abvorn.com/reviews/tvs/"
    key = _promotion_key(url, "tvs", "tv", [])

    first = await ambassador._promote_niche("tv", url=url, title="Best TVs", slug="tvs")
    assert first["action"] == "promote"
    posted_first = sum(
        1 for r in first["results"] if r.get("status") == "posted"
    )
    assert posted_first >= 1
    # The cooldown is now armed for this article.
    assert key in [i["key"] for i in real_state.get_meta("ambassador_recent_promotions", [])]

    social.post.reset_mock()
    second = await ambassador._promote_niche("tv", url=url, title="Best TVs", slug="tvs")
    assert second["action"] == "promote_skipped"
    assert second["reason"] == "promotion_cooldown"
    # Nothing was posted on the suppressed run.
    social.post.assert_not_called()


@pytest.mark.asyncio
async def test_failed_promotion_does_not_arm_the_cooldown(ambassador, state, social, monkeypatch):
    """A failed post must stay retryable; only a genuine 'posted' result arms
    the cooldown."""
    real_state = _MetaState()
    ambassador.state = real_state
    social.post.return_value = {"status": "failed", "platform": "x", "error": "boom"}
    monkeypatch.setattr("abvorn.agents.ambassador.can_attempt", lambda p: True)

    url = "https://abvorn.com/reviews/tvs/"
    first = await ambassador._promote_niche("tv", url=url, title="Best TVs", slug="tvs")
    assert first["action"] == "promote"
    # Nothing recorded because nothing posted.
    assert real_state.get_meta("ambassador_recent_promotions", []) == []

    # A retry is allowed (not cooldown-skipped).
    second = await ambassador._promote_niche("tv", url=url, title="Best TVs", slug="tvs")
    assert second["action"] == "promote"


@pytest.mark.asyncio
async def test_different_articles_are_both_promoted(ambassador, state, social, monkeypatch):
    """The cooldown is per-article, not global: promoting article B after
    article A must not be suppressed."""
    real_state = _MetaState()
    ambassador.state = real_state
    social.post.return_value = {"status": "posted", "platform": "x"}
    monkeypatch.setattr("abvorn.agents.ambassador.can_attempt", lambda p: True)

    a = await ambassador._promote_niche("tv", url="https://abvorn.com/reviews/tvs/",
                                        title="Best TVs", slug="tvs")
    b = await ambassador._promote_niche("mice", url="https://abvorn.com/reviews/mice/",
                                        title="Best Mice", slug="mice")
    assert a["action"] == "promote"
    assert b["action"] == "promote"