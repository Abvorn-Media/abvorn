"""ClickTracker — records widget clicks and impressions in state DB."""

import json
import logging
from datetime import datetime

logger = logging.getLogger("abvorn.persuasion.tracker")
STORAGE_KEY = "persuasion:events"


class ClickTracker:
    """Tracks persuasion widget clicks and impressions."""

    def __init__(self, state):
        self._state = state

    def record_click(self, niche: str, stage: str, product_index: int):
        self._append_event({
            "type": "click",
            "niche": niche,
            "stage": stage,
            "product_index": product_index,
            "timestamp": datetime.now().isoformat(),
        })

    def record_impression(self, niche: str, stage: str):
        self._append_event({
            "type": "impression",
            "niche": niche,
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
        })

    def get_stats(self, niche: str = None) -> dict:
        raw = self._state.get_meta(STORAGE_KEY, "[]")
        events = json.loads(raw) if isinstance(raw, str) else raw
        if niche:
            events = [e for e in events if e.get("niche") == niche]
        clicks = [e for e in events if e.get("type") == "click"]
        impressions = [e for e in events if e.get("type") == "impression"]
        return {
            "total_clicks": len(clicks),
            "total_impressions": len(impressions),
            "click_rate": len(clicks) / len(impressions) if impressions else 0.0,
        }

    def _append_event(self, event: dict):
        raw = self._state.get_meta(STORAGE_KEY, "[]")
        events = json.loads(raw) if isinstance(raw, str) else raw
        events.append(event)
        self._state.set_meta(STORAGE_KEY, json.dumps(events, default=str))
