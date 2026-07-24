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