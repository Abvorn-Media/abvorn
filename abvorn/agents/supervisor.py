"""SupervisorAgent — spawns, monitors, and rescues agents across platforms."""

import asyncio, logging, time
from datetime import datetime
from .base import AgentBase

logger = logging.getLogger("abvorn.agents.supervisor")

HEARTBEAT_TIMEOUT = 60.0


class SupervisorAgent(AgentBase):
    """Spans agents, monitors health, respawns on failure, processes Telegram commands."""

    def __init__(self, bus, state=None, brain=None, will=None, drive=None):
        super().__init__("SupervisorAgent", bus, state, brain, will, drive)
        self.registry: dict[str, dict] = {}
        self._spawned_tasks: dict[str, asyncio.Task] = {}
        self._register_self()
        self._pending_commands: list[dict] = []

    def _register_self(self):
        self.registry[self.name] = {
            "class": self.__class__.__name__,
            "status": "running",
            "instance": self,
            "spawned_at": datetime.now().isoformat(),
        }

    def spawn_agent(self, name: str, agent_class, *args, **kwargs):
        if name in self.registry:
            logger.warning(f"[Supervisor] Agent '{name}' already registered — skipping spawn")
            return False
        try:
            instance = agent_class(*args, **kwargs)
            self.registry[name] = {
                "class": agent_class.__name__,
                "status": "running",
                "instance": instance,
                "spawned_at": datetime.now().isoformat(),
                # Factory for a true respawn: rebuild + restart on heartbeat death.
                "factory": (agent_class, args, kwargs),
            }
            self.bus.publish("agent.spawned", {"agent": name, "class": agent_class.__name__})
            logger.info(f"[Supervisor] Spawned agent: {name} ({agent_class.__name__})")
            return instance
        except Exception as e:
            logger.error(f"[Supervisor] Failed to spawn '{name}': {e}")
            return False

    def kill_agent(self, name: str):
        if name not in self.registry:
            logger.warning(f"[Supervisor] Agent '{name}' not found — cannot kill")
            return False
        if name == self.name:
            logger.warning("[Supervisor] Cannot kill self")
            return False
        agent = self.registry[name]["instance"]
        try:
            agent.stop()
        except Exception:
            pass
        task = self._spawned_tasks.pop(name, None)
        if task:
            task.cancel()
        self.registry[name]["status"] = "killed"
        self.bus.publish("agent.killed", {"agent": name})
        logger.info(f"[Supervisor] Killed agent: {name}")
        return True

    def _kill_stale_task(self, name: str):
        task = self._spawned_tasks.pop(name, None)
        if task:
            task.cancel()

    def stop(self):
        self._running = False
        for task in self._spawned_tasks.values():
            task.cancel()
        self._spawned_tasks.clear()
        super().stop()

    def _spawn_from_factory(self, name: str, info: dict):
        """Rebuild a dead agent from its stored factory and restart it as a
        task tracked by the supervisor. Returns the new instance."""
        factory = info.get("factory")
        if not factory:
            logger.error(f"[Supervisor] No factory for '{name}' — cannot respawn")
            return None
        agent_class, args, kwargs = factory
        try:
            instance = agent_class(*args, **kwargs)
        except Exception as e:
            logger.error(f"[Supervisor] Respawn of '{name}' failed to build: {e}")
            return None
        self._kill_stale_task(name)
        self.registry[name].update({
            "class": agent_class.__name__,
            "status": "running",
            "instance": instance,
            "spawned_at": datetime.now().isoformat(),
        })
        task = asyncio.create_task(instance.run_forever())
        self._spawned_tasks[name] = task
        self.bus.publish("agent.spawned", {"agent": name, "class": agent_class.__name__, "respawned": True})
        logger.info(f"[Supervisor] Respawned dead agent: {name}")
        return instance

    def detect_dead_agents(self) -> list[str]:
        dead = []
        now = time.time()
        for name, info in self.registry.items():
            if name == self.name:
                continue
            inst = info.get("instance")
            if inst and hasattr(inst, "_last_heartbeat") and inst._last_heartbeat:
                age = now - inst._last_heartbeat
                if age > HEARTBEAT_TIMEOUT:
                    dead.append(name)
        return dead

    def get_agent_status(self) -> list[dict]:
        results = []
        now = time.time()
        for name, info in self.registry.items():
            inst = info.get("instance")
            heartbeat_age = None
            if inst and hasattr(inst, "_last_heartbeat") and inst._last_heartbeat:
                heartbeat_age = round(now - inst._last_heartbeat, 1)
            results.append({
                "name": name,
                "class": info["class"],
                "status": info["status"],
                "spawned_at": info["spawned_at"],
                "heartbeat_age_s": heartbeat_age,
                "cycle_count": getattr(inst, "cycle_count", 0) if inst else 0,
            })
        return results

    async def perceive(self) -> dict:
        dead = self.detect_dead_agents()
        events = self.bus.get_recent_events("telegram.command", limit=5)
        pending = []
        for ev in events:
            pending.append(ev["message"])
        return {
            "dead_agents": dead,
            "pending_commands": pending,
            "registry_size": len(self.registry),
        }

    async def decide(self, perception: dict) -> str:
        if perception.get("dead_agents"):
            return f"respawn:{','.join(perception['dead_agents'])}"
        if perception.get("pending_commands"):
            return "process_commands"
        return "wait"

    async def act(self, decision: str):
        if decision.startswith("respawn:"):
            names = decision.split(":", 1)[1].split(",")
            respawned = []
            failed = []
            for name in names:
                info = self.registry.get(name)
                if not info:
                    failed.append(name)
                    continue
                new_instance = self._spawn_from_factory(name, info)
                if new_instance is not None:
                    respawned.append(name)
                else:
                    failed.append(name)
            return {"respawning": respawned, "failed": failed}
        if decision == "process_commands":
            commands = self._pending_commands[:]
            self._pending_commands.clear()
            results = []
            for cmd in commands:
                results.append({"command": cmd.get("text", "")})
            return {"processed": results}
        return {"action": "none"}

    async def reflect(self, outcome):
        if outcome and outcome.get("respawning"):
            for name in outcome["respawning"]:
                logger.info(f"[Supervisor] Agent '{name}' respawned successfully")
        if outcome and outcome.get("failed"):
            for name in outcome["failed"]:
                logger.warning(f"[Supervisor] Agent '{name}' could not be respawned")
        if outcome and outcome.get("processed"):
            for c in outcome["processed"]:
                logger.info(f"[Supervisor] Processed command: {c['command']}")