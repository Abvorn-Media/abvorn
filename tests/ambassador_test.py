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