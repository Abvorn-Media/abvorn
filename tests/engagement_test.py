"""Tests for MentionWatcher — polls Composio for mentions with dedup."""
import pytest
from unittest.mock import MagicMock, patch
from abvorn.engagement.watcher import MentionWatcher


def test_watcher_initializes():
    mw = MentionWatcher(composio_key="test", state=None)
    assert mw is not None
    assert mw.poll_interval == 900


def test_poll_returns_list():
    mw = MentionWatcher(composio_key="test", state=None)
    result = mw.poll()
    assert isinstance(result, list)


def test_poll_deduplicates():
    mw = MentionWatcher(composio_key="test", state=None)
    mw._replied_ids.add("dup_1")
    mw._raw_mentions = [{"id": "dup_1", "text": "This is an old mention we already replied to"}, {"id": "new_1", "text": "This is a brand new mention we should include"}]
    result = mw.poll()
    assert len(result) == 1
    assert result[0]["id"] == "new_1"


def test_filter_substantive_only():
    mw = MentionWatcher(composio_key="test", state=None)
    mw._raw_mentions = [
        {"id": "1", "text": "@abvorn nice!", "author": "user1"},
        {"id": "2", "text": "Does this work with Samsung TVs? I've been looking for something like this.", "author": "user2"},
        {"id": "3", "text": "lol", "author": "user3"},
    ]
    result = mw.poll()
    assert len(result) == 1
    assert result[0]["id"] == "2"


def test_no_key_returns_empty():
    mw = MentionWatcher(composio_key="", state=None)
    assert mw.poll() == []


def test_poll_respects_interval():
    """poll() must not hit the API again within poll_interval."""
    import time
    mw = MentionWatcher(composio_key="test", state=None)
    mw._last_poll = 0.0
    mw.poll()  # first poll performs a fetch (or skips if client unavailable)
    fetched = mw._last_poll
    assert fetched > 0
    mw.poll()  # immediately again — must not fetch
    assert mw._last_poll == fetched


def test_wait_decision_does_not_log_failure_to_drive():
    """Agents that decide to wait should not inflate grit via reflect(None)."""
    import asyncio
    from abvorn.agents.base import AgentBase
    from abvorn.core.bus import AgentBus
    from abvorn.drive import Drive

    bus = AgentBus(":memory:")

    class IdleAgent(AgentBase):
        async def perceive(self):
            return {}
        async def decide(self, perception):
            return "wait"
        async def act(self, decision):
            raise AssertionError("act must not run on wait")
        async def reflect(self, outcome):
            self.reflected = outcome
            self.drive.log_outcome("cycle", succeeded=bool(outcome))

    drive = Drive("IdleAgent", "test")
    agent = IdleAgent("idle", bus, drive=drive)
    agent.cycle_count = 0
    asyncio.run(agent.run_once())
    assert drive.grit == 0
    assert not hasattr(agent, "reflected")


def test_heartbeat_updated_each_cycle():
    """_last_heartbeat must advance so supervisor does not flag live agents dead."""
    import asyncio, time
    from abvorn.agents.base import AgentBase
    from abvorn.core.bus import AgentBus

    bus = AgentBus(":memory:")

    class HBAgent(AgentBase):
        async def perceive(self):
            return {}
        async def decide(self, perception):
            return "wait"
        async def act(self, decision):
            pass
        async def reflect(self, outcome):
            pass

    agent = HBAgent("hb", bus)
    agent.cycle_count = 0
    before = agent._last_heartbeat
    asyncio.run(agent.run_once())
    assert agent._last_heartbeat > before


from abvorn.engagement.replier import ReplyGenerator, ReplyPoster


def test_reply_generator_initializes():
    rg = ReplyGenerator(router=None)
    assert rg is not None


def test_reply_generator_craft_returns_string():
    rg = ReplyGenerator(router=None)
    reply = rg.craft({"text": "Does this work with Samsung TVs?", "author": "user"}, {})
    assert isinstance(reply, str)
    assert len(reply) > 10


def test_reply_generator_with_llm():
    router = MagicMock()
    router.ask.return_value = "Great question! Yes, it works with Samsung TVs from 2022 onwards."
    rg = ReplyGenerator(router=router)
    reply = rg.craft({"text": "Does this work with Samsung TVs?", "author": "user"},
                     {"niche": "tv", "post_title": "Best TV 2026"})
    assert "Samsung" in reply
    router.ask.assert_called_once()


def test_reply_poster_initializes():
    rp = ReplyPoster(composio_key="test")
    assert rp is not None


def test_reply_poster_no_key():
    rp = ReplyPoster(composio_key="")
    result = rp.post({"tweet_id": "123"}, "Great question!")
    assert result["status"] == "skipped"


def test_reply_poster_returns_structure():
    rp = ReplyPoster(composio_key="fake_key")
    result = rp.post({"tweet_id": "123"}, "Thanks for asking!")
    assert "status" in result
