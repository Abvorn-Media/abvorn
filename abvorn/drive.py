"""Per-agent drive — grit, persistence, and alternative path finding."""

import logging, random
from datetime import datetime

logger = logging.getLogger("abvorn.drive")


class Drive:
    """An agent's spine — determines how it persists through failure."""

    def __init__(self, agent_name: str, mission: str = ""):
        self.agent_name = agent_name
        self.mission = mission
        self.grit = 0
        self._history = []

    def should_retry(self, attempt: int, error: str = "") -> bool:
        """Returns True if the agent should try again with a different approach."""
        max_attempts = max(3, 5 - self.grit)
        if attempt >= max_attempts:
            return False
        logger.info(f"{self.agent_name}: attempt {attempt+1}/{max_attempts} — {error or 'retrying'}")
        return True

    def alternative_path(self, blocked_action: str) -> str:
        """Find a different way to achieve the same goal."""
        alternatives = {
            "x_post": ["linkedin_post", "medium_post"],
            "linkedin_post": ["x_post", "medium_post"],
            "blog_post": ["medium_post", "linkedin_article"],
            "email_send": ["blog_post", "social_post"],
        }
        options = alternatives.get(blocked_action, ["retry_different_approach"])
        choice = random.choice(options)
        logger.info(f"{self.agent_name}: {blocked_action} blocked → trying {choice}")
        return choice

    def log_outcome(self, action: str, succeeded: bool, note: str = ""):
        """Record what happened and update grit."""
        self._history.append({
            "action": action, "succeeded": succeeded,
            "note": note, "timestamp": datetime.now().isoformat(),
        })
        if not succeeded:
            self.grit += 1
            logger.info(f"{self.agent_name}: grit increased to {self.grit}")
        else:
            self.grit = max(0, self.grit - 1)

    def get_history(self, limit: int = 10) -> list:
        return self._history[-limit:]