import logging
import uuid
from datetime import datetime, timezone, timedelta

from .planner import PlatformPlanner

logger = logging.getLogger("abvorn.schedule.queue")

PRIORITY_LOW = 1
PRIORITY_DEFAULT = 5
PRIORITY_HIGH = 10


class PostingQueue:
    """Posting queue with optional AbvornState persistence."""

    def __init__(self, state=None):
        self._planner = PlatformPlanner()
        self._state = state
        self._items: list[dict] = []

    def enqueue(self, content: str, platform: str, priority: int = PRIORITY_DEFAULT, scheduled_time: str | None = None) -> str:
        item_id = str(uuid.uuid4())
        scheduled = scheduled_time or self._planner.next_good_time(platform)
        item = {
            "id": item_id,
            "content": content,
            "platform": platform,
            "priority": priority,
            "scheduled_time": scheduled,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "queued",
        }
        self._items.append(item)
        self._persist()
        logger.info(f"Enqueued {item_id} for {platform} at {scheduled}")
        return item_id

    def dequeue(self) -> dict | None:
        now = datetime.now(timezone.utc)
        ready = [
            it for it in self._items
            if it["status"] == "queued"
            and datetime.fromisoformat(it["scheduled_time"]) <= now
        ]
        if not ready:
            return None
        ready.sort(key=lambda x: (-x["priority"], x["scheduled_time"]))
        item = ready[0]
        item["status"] = "dequeued"
        self._persist()
        return item

    def peek(self) -> dict | None:
        now = datetime.now(timezone.utc)
        ready = [
            it for it in self._items
            if it["status"] == "queued"
            and datetime.fromisoformat(it["scheduled_time"]) <= now
        ]
        if not ready:
            return None
        ready.sort(key=lambda x: (-x["priority"], x["scheduled_time"]))
        return dict(ready[0])

    def ack(self, item_id: str):
        for it in self._items:
            if it["id"] == item_id:
                it["status"] = "posted"
                it["posted_at"] = datetime.now(timezone.utc).isoformat()
                self._persist()
                logger.info(f"Ack {item_id} — posted")
                return

    def nack(self, item_id: str, reason: str = ""):
        for it in self._items:
            if it["id"] == item_id:
                it["status"] = "failed"
                it["failure_reason"] = reason
                self._persist()
                logger.warning(f"Nack {item_id} — {reason}")
                return

    def get_queue_length(self) -> int:
        return sum(1 for it in self._items if it["status"] == "queued")

    def get_upcoming(self, count: int = 5) -> list[dict]:
        queued = [it for it in self._items if it["status"] == "queued"]
        queued.sort(key=lambda x: (x["scheduled_time"], -x["priority"]))
        return queued[:count]

    def _persist(self):
        if self._state and hasattr(self._state, "set_meta"):
            self._state.set_meta("schedule.queue", self._items)
