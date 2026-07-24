"""Abvorn daemon — runs all agents continuously."""

import asyncio, logging, signal, sys, json
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("abvorn.daemon")

from .core.state import AbvornState
from .core.models import ModelRouter
from .core.secrets import load_secrets
from .core.bus import AgentBus
from .content.pipeline import ContentPipeline
from .agents.orchestrator import ResearchAgent, ContentAgent, DeployAgent
from .brain.orchestrator import refresh_brain, get_brain_retriever
from .deploy.github import GitHubDeployer

STATE_DB = Path.home() / ".abvorn" / "state.db"
BUS_DB = Path.home() / ".abvorn" / "bus.db"

class AbvornDaemon:
    """The daemon that keeps Abvorn alive 24/7."""

    def __init__(self, state_db: str = None):
        self.running = False
        self.state_path = Path(state_db) if state_db else STATE_DB
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = AbvornState(self.state_path)
        self.bus = AgentBus(str(BUS_DB))
        self.secrets = load_secrets()
        self.router = ModelRouter(self.secrets)
        self.agents = []
        self._tasks = []
        self._init_phase3()

    def _init_phase3(self):
        """Initialize Phase 3 subsystems."""
        from .discovery.scanner import OpportunityScanner
        from .persona.engine import PersonaEngine
        from .persona.registry import PersonaRegistry
        from .factory.pipeline import PersuasionPipeline
        from .deploy.social import SocialDeployer
        from .deploy.notifier import TelegramNotifier
        from .orchestrator.scheduler import Scheduler
        from .orchestrator.health import HealthMonitor

        self.scanner = OpportunityScanner(self.state)
        self.persona_engine = PersonaEngine()
        self.persona_registry = PersonaRegistry(str(self.state_path.parent / "personas.db"))
        self.factory = PersuasionPipeline()
        self.social = SocialDeployer(self.secrets.get("COMPOSIO_KEY", ""))
        self.notifier = TelegramNotifier()
        self.scheduler = Scheduler(state_db=str(self.state_path))
        self.health = HealthMonitor(state_db=str(self.state_path))

    def is_paused(self) -> bool:
        """Check if the kill switch is engaged."""
        return self.state.get_meta("kill_switch", False)

    async def run_full_cycle(self) -> dict:
        """Run one complete opportunity → content → deploy cycle."""
        if self.is_paused():
            return {"status": "paused"}

        opp = self.scheduler.get_next_opportunity()
        if not opp:
            logger.info("No pending opportunities — running discovery")
            self.scanner.discover_from_keywords(["wireless headphones", "gaming mouse"])
            opp = self.scheduler.get_next_opportunity()
            if not opp:
                return {"status": "nothing_to_do"}

        niche = opp["niche"]
        logger.info(f"Starting cycle for: {niche}")

        personas = self.persona_engine.discover_personas(niche)
        if not personas:
            self.scheduler.mark_failed(opp["id"])
            self.notifier.report_cycle(niche, "failed", "No personas found")
            return {"status": "no_personas"}

        persona = personas[0]
        persona_id = f"{niche}_{persona['name'].lower().replace(' ', '_')}"
        self.persona_registry.register_persona(persona_id, niche, persona)

        content = self.factory.run(niche, persona, self.router)
        if not content:
            self.scheduler.mark_failed(opp["id"])
            self.notifier.report_error(niche, "Content factory returned None")
            return {"status": "content_failed"}

        from .exploder.adapters import (
            adapt_for_x, adapt_for_linkedin, adapt_for_tiktok,
            adapt_for_instagram, adapt_for_pinterest, adapt_for_medium,
        )
        from .exploder.email import generate_lead_magnet, generate_sequence

        magnet = generate_lead_magnet(content)
        sequence = generate_sequence(content, persona)

        threaded = adapt_for_x(content)
        linkedin = adapt_for_linkedin(content)
        self.social.post_to_x(threaded)
        self.social.post_to_linkedin(linkedin)
        self.social.post_to_medium(content)

        self.scheduler.mark_complete(opp["id"])
        self.health.log_cycle(niche, success=True, duration_s=120)
        self.persona_registry.update_performance(persona_id, converted=False, quality_score=7.0)
        self.notifier.report_cycle(niche, "success", content.get("post_title", ""))

        self.bus.publish("content.drafted", {"niche": niche, "title": content.get("post_title", "")})
        return {"status": "success", "niche": niche, "persona": persona_id}

    async def start(self):
        """Start all agents and the brain."""
        self.running = True
        logger.info("Abvorn daemon starting...")

        brain = None
        try:
            result = refresh_brain()
            if result.get("status") == "ok":
                brain = get_brain_retriever()
                logger.info(f"Brain loaded: {result.get('indexed', 0)} documents")
        except Exception as e:
            logger.warning(f"Brain init failed (non-fatal): {e}")

        pipeline = ContentPipeline(self.state)
        if brain:
            pipeline.brain = brain

        deployer = GitHubDeployer(
            token=self.secrets.get("GITHUB_TOKEN", ""),
            repo=self.secrets.get("GITHUB_REPO", ""),
        )

        self.agents = [
            ResearchAgent(self.bus, self.state, self.router, brain),
            ContentAgent(self.bus, self.state, self.router, pipeline, brain),
            DeployAgent(self.bus, self.state, deployer),
        ]

        for agent in self.agents:
            logger.info(f"  Starting agent: {agent.name}")

        for agent in self.agents:
            task = asyncio.create_task(agent.run_forever())
            self._tasks.append(task)

        bus_task = asyncio.create_task(self._bus_loop())
        self._tasks.append(bus_task)

        logger.info(f"Daemon running with {len(self.agents)} agents")

    async def _bus_loop(self):
        while self.running:
            events = self.bus.get_recent_events()
            await asyncio.sleep(10)

    async def stop(self):
        """Graceful shutdown of all agents."""
        logger.info("Daemon stopping...")
        self.running = False
        for agent in self.agents:
            agent.stop()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Daemon stopped")