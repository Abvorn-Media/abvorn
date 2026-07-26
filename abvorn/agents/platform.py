"""PlatformAgent — per-platform content agent template."""

import logging
from .base import AgentBase
from ..platform.registry import PlatformRegistry
from ..platform.voice import format_voice_rules_for_prompt

logger = logging.getLogger("abvorn.agents.platform")


class PlatformAgent(AgentBase):
    """Template for per-platform content agents."""

    def __init__(self, bus, state, router, platform_name: str, voice_profile: dict = None,
                 registry: PlatformRegistry = None, brain=None, will=None):
        super().__init__(f"PlatformAgent_{platform_name}", bus, state, brain, will=will)
        self.platform_name = platform_name
        self.router = router
        self.voice_profile = voice_profile or {}
        self.registry = registry
        self._last_content_id = 0

    async def perceive(self) -> dict:
        events = self.bus.get_recent_events("content.drafted", limit=5)
        platform_events = [e for e in events
                           if e["id"] > self._last_content_id
                           and self.platform_name in e["message"].get("platforms", [self.platform_name])]
        return {"platform_events": platform_events}

    async def decide(self, perception: dict) -> str:
        if perception.get("platform_events"):
            ev = max(perception["platform_events"], key=lambda e: e["id"])
            self._last_content_id = ev["id"]
            niche = ev['message'].get('niche', 'general')
            if not self.soul_check("adapt_content", {"niche": niche, "platform": self.platform_name}):
                logger.info(f"[{self.name}] Soul blocked adaptation for {niche}")
                return "wait"
            return f"adapt:{niche}"
        return "wait"

    async def act(self, decision: str):
        if decision.startswith("adapt:"):
            niche = decision.split(":", 1)[1]
            logger.info(f"[{self.name}] Adapting content for {self.platform_name} ({niche})")
            voice_prompt = format_voice_rules_for_prompt(self.platform_name)
            return {
                "platform": self.platform_name,
                "niche": niche,
                "voice_profile": self.voice_profile,
                "voice_rules": voice_prompt,
            }
        return {"action": "none"}

    async def reflect(self, outcome):
        if outcome and "platform" in outcome:
            logger.info(f"[{self.name}] Completed adaptation for {outcome.get('platform')} / {outcome.get('niche')}")
        if self.drive:
            succeeded = bool(outcome and "platform" in outcome)
            self.drive.log_outcome("adapt", succeeded=succeeded)