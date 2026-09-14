import pytest, asyncio
from abvorn.agents.base import AgentBase
from abvorn.core.bus import AgentBus

def test_agent_lifecycle():
    """Agent should go through perceive -> decide -> act -> reflect cycle."""
    bus = AgentBus(":memory:")
    class TestAgent(AgentBase):
        def __init__(self):
            super().__init__("test_agent", bus)
            self.cycle_count = 0
        async def perceive(self):
            return {"events": self.bus.get_recent_events("test.topic")}
        async def decide(self, perception):
            return "act_on_test" if perception["events"] else "wait"
        async def act(self, decision):
            if decision == "act_on_test":
                self.acted = True
        async def reflect(self, outcome):
            pass

    agent = TestAgent()
    bus.publish("test.topic", {"msg": "hello"})
    asyncio.run(agent.run_once())
    assert agent.cycle_count == 1
    assert agent.acted is True


def test_supervisor_does_not_flag_unstarted_agents_as_dead():
    """Agents that have not sent a heartbeat yet must not be considered dead."""
    from abvorn.agents.supervisor import SupervisorAgent

    supervise = SupervisorAgent(AgentBus(":memory:"))
    class FreshAgent(AgentBase):
        async def perceive(self):
            return {}
        async def decide(self, perception):
            return "wait"
        async def act(self, decision):
            pass
        async def reflect(self, outcome):
            pass

    fresh = FreshAgent("fresh", AgentBus(":memory:"))
    supervise.registry["fresh"] = {
        "class": "FreshAgent", "status": "running",
        "instance": fresh, "spawned_at": "x",
    }
    assert supervise.detect_dead_agents() == []


def test_supervisor_respawns_dead_agent_from_factory():
    """A dead agent must be rebuilt from its stored factory and restarted —
    regression for the audit finding that respawn only marked the intent
    (respawn_pending + None instance) without ever rebuilding."""
    import asyncio
    from abvorn.agents.supervisor import SupervisorAgent, HEARTBEAT_TIMEOUT

    supervise = SupervisorAgent(AgentBus(":memory:"))
    created = []

    class TrackedAgent(AgentBase):
        def __init__(self, tag="x"):
            super().__init__("TrackedAgent", AgentBus(":memory:"))
            self.tag = tag
            self.spawned = len(created)
            created.append(self)
        async def perceive(self):
            return {}
        async def decide(self, perception):
            return "wait"
        async def act(self, decision):
            pass
        async def reflect(self, outcome):
            pass

    first = supervise.spawn_agent("tracked", TrackedAgent, "v1")
    assert first is not None
    assert len(created) == 1

    # Simulate heartbeat death: stamp a heartbeat far older than the timeout.
    import time
    first._last_heartbeat = time.time() - (HEARTBEAT_TIMEOUT + 5)
    assert supervise.detect_dead_agents() == ["tracked"]

    async def run():
        decided = await supervise.decide({"dead_agents": ["tracked"],
                                          "pending_commands": [],
                                          "registry_size": 2})
        assert decided == "respawn:tracked"
        outcome = await supervise.act(decided)
        await supervise.reflect(outcome)

    asyncio.run(run())

    assert len(created) == 2, "respawn must build a new instance"
    assert created[1].tag == "v1"
    entry = supervise.registry["tracked"]
    assert entry["status"] == "running"
    assert entry["instance"] is created[1]
    assert entry["class"] == "TrackedAgent"


def test_supervisor_respawn_failure_reports_failed():
    """No factory in the registry → respawn reports failure, not silence."""
    import asyncio
    from abvorn.agents.supervisor import SupervisorAgent

    supervise = SupervisorAgent(AgentBus(":memory:"))
    supervise.registry["ghost"] = {
        "class": "GhostAgent", "status": "dead",
        "instance": None, "spawned_at": "x",
    }

    outcome = asyncio.run(supervise.act("respawn:ghost"))
    assert outcome == {"respawning": [], "failed": ["ghost"]}


def test_content_agent_decide_reads_wrapped_bus_message():
    """ContentAgent.decide must read the 'message' envelope returned by
    get_recent_events. Regression: bare `last['niche']` raised KeyError on
    every event-bearing poll after the bus event-driven layer (d220d8b1)
    wrapped payloads in a 'message' key."""
    import asyncio
    from abvorn.agents.orchestrator import ContentAgent

    bus = AgentBus(":memory:")
    agent = ContentAgent(bus, state=None, router=None, pipeline=None)
    bus.publish("content.researched", {"niche": "webcams", "products": [{"title": "x"}], "count": 1})

    async def run():
        perception = await agent.perceive()
        return await agent.decide(perception)

    assert asyncio.run(run()) == "generate:webcams"


def test_content_agent_decide_waits_when_niche_missing():
    """A research envelope without 'niche' must be skipped, not crash."""
    import asyncio
    from abvorn.agents.orchestrator import ContentAgent

    bus = AgentBus(":memory:")
    agent = ContentAgent(bus, state=None, router=None, pipeline=None)
    bus.publish("content.researched", {"products": []})

    async def run():
        perception = await agent.perceive()
        return await agent.decide(perception)

    assert asyncio.run(run()) == "wait"
