"""Self-driving scheduler — prioritizes opportunities and orchestrates cycles."""

import logging
from pathlib import Path

logger = logging.getLogger("abvorn.orchestrator")


class Scheduler:
    """Manages the autonomous content cycle queue."""

    def __init__(self, state_db: str = None):
        from ..core.state import AbvornState
        self.state_path = Path(state_db) if state_db else Path.home() / ".abvorn" / "state.db"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = AbvornState(self.state_path)

    def get_next_opportunity(self) -> dict:
        """Get the highest-priority pending opportunity."""
        opportunities = self.state.get_opportunities("pending", limit=1)
        return opportunities[0] if opportunities else None

    def mark_complete(self, opp_id: int):
        """Mark an opportunity as complete."""
        self.state.update_opportunity_status(opp_id, "completed")

    def queue_deploy(self, niche: str):
        """Queue a deploy for a specific niche (triggered by Telegram command)."""
        self.state.add_opportunity(niche, score=1.0)
        logger.info(f"[Scheduler] Queued manual deploy for '{niche}' via Telegram")