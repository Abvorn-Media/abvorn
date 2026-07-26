"""Schedule — 2-slot daily content queue with evergreen fallback."""

import logging
from datetime import datetime

logger = logging.getLogger("abvorn.trends.schedule")

EVERGREEN_QUEUE = [
    {"product_name": "Best TVs of 2026", "category": "tv", "content_type": "buying_guide",
     "primary_platform": "blog", "secondary_platform": "linkedin", "score": 50, "sources": ["evergreen"]},
    {"product_name": "Best Robot Vacuums of 2026", "category": "robot vacuum", "content_type": "buying_guide",
     "primary_platform": "blog", "secondary_platform": "linkedin", "score": 50, "sources": ["evergreen"]},
    {"product_name": "Best Laptops of 2026", "category": "laptop", "content_type": "buying_guide",
     "primary_platform": "blog", "secondary_platform": "linkedin", "score": 50, "sources": ["evergreen"]},
    {"product_name": "Best Monitors of 2026", "category": "monitor", "content_type": "buying_guide",
     "primary_platform": "blog", "secondary_platform": "linkedin", "score": 50, "sources": ["evergreen"]},
    {"product_name": "Best Headphones of 2026", "category": "headphones", "content_type": "buying_guide",
     "primary_platform": "blog", "secondary_platform": "linkedin", "score": 50, "sources": ["evergreen"]},
]

LIGHT_EVERGREEN = [
    {"product_name": "Tech Deal of the Day", "category": "tech", "content_type": "social_thread",
     "primary_platform": "x", "secondary_platform": "tiktok", "score": 40, "sources": ["evergreen"]},
    {"product_name": "Gadget of the Week", "category": "tech", "content_type": "tiktok_script",
     "primary_platform": "tiktok", "secondary_platform": "instagram", "score": 40, "sources": ["evergreen"]},
    {"product_name": "Tech Question Thread", "category": "tech", "content_type": "social_thread",
     "primary_platform": "x", "secondary_platform": "tiktok", "score": 35, "sources": ["evergreen"]},
]


class Schedule:
    """Manages the daily 2-slot posting queue with trend + evergreen mix."""

    def __init__(self, state=None):
        self.state = state
        self._queue = []
        self._posts = []
        self._evergreen_index = 0
        self._light_evergreen_index = 0
        self._am_post = None
        self._pm_post = None

    def fill_queue(self, items: list):
        if items:
            self._queue.extend(items)

    def assign_slots(self):
        """Sort queue into AM (deep) and PM (light) slots. Falls back to evergreen."""
        deep = [i for i in self._queue if i.get("content_type") in ("buying_guide", "comparison")]
        light = [i for i in self._queue if i.get("content_type") in ("social_thread", "tiktok_script")]

        self._am_post = deep[0] if deep else self._next_evergreen_deep()
        self._pm_post = light[0] if light else self._next_evergreen_light()

        # Remove assigned items from queue
        if self._am_post and self._am_post in self._queue:
            self._queue.remove(self._am_post)
        if self._pm_post and self._pm_post in self._queue:
            self._queue.remove(self._pm_post)

    def get_am_post(self) -> dict:
        return self._am_post

    def get_pm_post(self) -> dict:
        return self._pm_post

    def get_next_post(self) -> dict:
        """Pop and return next item from queue."""
        if self._queue:
            return self._queue.pop(0)
        return None

    def queue_size(self) -> int:
        return len(self._queue)

    def record_post(self, item: dict, status: str = "posted"):
        self._posts.append({**item, "status": status, "posted_at": datetime.now().isoformat()})

    def post_count(self) -> int:
        return len(self._posts)

    def _next_evergreen_deep(self) -> dict:
        p = EVERGREEN_QUEUE[self._evergreen_index % len(EVERGREEN_QUEUE)]
        self._evergreen_index += 1
        return dict(p)

    def _next_evergreen_light(self) -> dict:
        p = LIGHT_EVERGREEN[self._light_evergreen_index % len(LIGHT_EVERGREEN)]
        self._light_evergreen_index += 1
        return dict(p)