import asyncio, logging, time
from abc import ABC, abstractmethod

logger = logging.getLogger("abvorn.agents")

class AgentBase(ABC):
    """Base class for all agents with async lifecycle and Abvorn soul."""

    def __init__(self, name: str, bus, state=None, brain=None, will=None, drive=None):
        self.name = name
        self.bus = bus
        self.state = state
        self.brain = brain
        self.will = will
        self.drive = drive
        self.cycle_count = 0
        self._running = False
        self._last_heartbeat = 0.0

    def soul_check(self, action: str, context: dict = None) -> bool:
        """Check action against the Abvorn mission and entitlements. Logs violations."""
        # Mission check (Will)
        if self.will:
            ok = self.will.mission_check(action, context or {})
            if not ok:
                logger.warning(f"[{self.name}] Soul blocked: {action}")
                return ok

        # Entitlements check (permission gate)
        try:
            from abvorn.core.entitlements import get_entitlements
            gate = get_entitlements().check(action, agent=self.name, context=context)
            if not gate["allowed"]:
                logger.warning(
                    f"[{self.name}] Entitlements blocked: {action} — {gate['reason']}"
                )
                return False
        except Exception:
            pass  # entitlements module unavailable — fall through

        return True

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
        """Execute one perceive -> soul_check -> decide -> act -> reflect cycle."""
        self.cycle_count += 1
        attempt = 0
        while True:
            try:
                perception = await self.perceive()
                decision = await self.decide(perception)
                outcome = None
                if decision and decision != "wait":
                    if not self.soul_check(decision, perception):
                        logger.info(f"[{self.name}] Skipped {decision} — soul violation")
                        await self.reflect({"skipped": True, "decision": decision, "reason": "soul_violation"})
                        return {"decision": decision, "outcome": None, "soul_blocked": True}
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
                if self.drive and self.drive.should_retry(attempt, str(e)):
                    self.drive.log_outcome(f"cycle_{self.cycle_count}", succeeded=False, note=str(e)[:100])
                    attempt += 1
                    await asyncio.sleep(1 * attempt)
                    continue
                if self.drive:
                    self.drive.log_outcome(f"cycle_{self.cycle_count}", succeeded=False, note=str(e)[:100])
                return {"error": str(e)}

    async def run_forever(self, poll_interval: float = 5.0):
        """Run the agent lifecycle indefinitely."""
        self._running = True
        while self._running:
            await self.run_once()
            await asyncio.sleep(poll_interval)

    def stop(self):
        self._running = False
