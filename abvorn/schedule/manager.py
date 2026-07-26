import logging

from .planner import PlatformPlanner
from .queue import PostingQueue

logger = logging.getLogger("abvorn.schedule.manager")


class ScheduleManager:
    """Coordinates platform timing and content queuing."""

    def __init__(self, state=None):
        self._planner = PlatformPlanner()
        self._queue = PostingQueue(state)
        self._state = state
        self._niche_cadences: dict[str, str] = {}

        if state and hasattr(state, "get_meta"):
            saved = state.get_meta("schedule.niche_cadences", {})
            self._niche_cadences = saved if isinstance(saved, dict) else {}

    def should_post(self, platform: str) -> bool:
        if not self._planner.is_good_time(platform):
            return False
        return self._planner.min_gap_met(platform)

    def schedule_content(self, content: str, platforms: list[str]) -> list[str]:
        ids = []
        for platform in platforms:
            item_id = self._queue.enqueue(content, platform)
            ids.append(item_id)
        logger.info(f"Scheduled content on {len(platforms)} platforms")
        return ids

    def get_due_items(self) -> list[dict]:
        items = []
        while True:
            item = self._queue.dequeue()
            if item is None:
                break
            items.append(item)
        return items

    def mark_posted(self, item_id: str):
        self._queue.ack(item_id)

    def mark_failed(self, item_id: str, reason: str = ""):
        self._queue.nack(item_id, reason)

    def get_cadence(self, niche: str) -> str:
        if niche in self._niche_cadences:
            return self._niche_cadences[niche]
        if not self._state or not hasattr(self._state, "get_niche"):
            return "daily"
        niche_data = self._state.get_niche(niche)
        if not niche_data:
            return "daily"
        maturity = niche_data.get("maturity", "seed")
        cadence_map = {
            "seed": "daily",
            "sprout": "daily",
            "growing": "daily",
            "thriving": "weekly",
            "evergreen": "weekly",
        }
        return cadence_map.get(maturity, "daily")

    def update_cadence(self, niche: str, new_cadence: str):
        self._niche_cadences[niche] = new_cadence
        if self._state and hasattr(self._state, "set_meta"):
            self._state.set_meta("schedule.niche_cadences", self._niche_cadences)
        logger.info(f"Updated cadence for {niche} -> {new_cadence}")
