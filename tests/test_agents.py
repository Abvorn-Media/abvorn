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
