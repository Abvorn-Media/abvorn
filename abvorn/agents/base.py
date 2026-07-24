import asyncio, logging, time
from abc import ABC, abstractmethod

logger = logging.getLogger("abvorn.agents")

class AgentBase(ABC):
    """Base class for all agents with async lifecycle."""

    def __init__(self, name: str, bus, state=None, brain=None):
        self.name = name
        self.bus = bus
        self.state = state
        self.brain = brain
        self.cycle_count = 0
        self._running = False
        self._last_heartbeat = 0.0

    @abstractmethod
    async def perceive(self) -> dict:
        """Sense the environment: check bus events, state, analytics."""

    @abstractmethod
    async def decide(self, perception: dict) -> str:
        """Decide what action to take based on perception."""

    @abstractmethod
    async def act(self, decision: str):
        """Execute the decided action."""

    @abstractmethod
    async def reflect(self, outcome):
        """Learn from what happened."""

    async def run_once(self) -> dict:
        """Execute one perceive -> decide -> act -> reflect cycle."""
        self.cycle_count += 1
        try:
            perception = await self.perceive()
            decision = await self.decide(perception)
            outcome = None
            if decision and decision != "wait":
                act_start = time.time()
                outcome = await self.act(decision)
                act_time = time.time() - act_start
                logger.info(f"[{self.name}] Cycle {self.cycle_count}: {decision} ({act_time:.1f}s)")
            await self.reflect(outcome)
            self.bus.publish("system.heartbeat", {"agent": self.name, "cycle": self.cycle_count})
            return {"decision": decision, "outcome": outcome}
        except Exception as e:
            logger.error(f"[{self.name}] Cycle {self.cycle_count} failed: {e}")
            self.bus.publish("system.error", {"agent": self.name, "error": str(e)})
            return {"error": str(e)}

    async def run_forever(self, poll_interval: float = 5.0):
        """Run the agent lifecycle indefinitely."""
        self._running = True
        while self._running:
            await self.run_once()
            await asyncio.sleep(poll_interval)

    def stop(self):
        self._running = False
