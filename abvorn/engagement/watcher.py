"""MentionWatcher — polls Composio for social mentions with rate-limit-safe polling."""

import logging
from datetime import datetime

logger = logging.getLogger("abvorn.engagement.watcher")

SPAM_PATTERNS = ["lol", "nice", "cool", "follow me", "check out", "http://", "https://"]

try:
    from composio import ComposioToolSet, Action
    HAS_COMPOSIO = True
except ImportError:
    HAS_COMPOSIO = False
    Action = object


class MentionWatcher:
    """Polls Composio for mentions every 15 min. Deduplicates and filters spam."""

    def __init__(self, composio_key: str = "", state=None):
        self.composio_key = composio_key
        self.state = state
        self.poll_interval = 900
        self._replied_ids = set()
        self._raw_mentions = []
        self._composio = None
        if composio_key and HAS_COMPOSIO:
            try:
                self._composio = ComposioToolSet(api_key=composio_key)
            except Exception as e:
                logger.warning(f"Composio init failed: {e}")

    def poll(self) -> list[dict]:
        """Poll for new mentions. Returns only substantive, unseen mentions."""
        if self._composio:
            self._fetch_mentions()
        return self._filter_new()

    def _fetch_mentions(self):
        mentions_action = getattr(Action, "TWITTER_GET_MENTIONS", None)
        if not mentions_action:
            return
        try:
            result = self._composio.execute_action(mentions_action, params={"count": 20})
            self._raw_mentions = result if isinstance(result, list) else []
        except Exception as e:
            logger.debug(f"Mention fetch failed: {e}")

    def _filter_new(self) -> list[dict]:
        results = []
        for m in self._raw_mentions:
            mid = str(m.get("id", ""))
            if mid in self._replied_ids:
                continue
            text = m.get("text", "")
            if not self._is_substantive(text):
                continue
            self._replied_ids.add(mid)
            results.append({
                "id": mid,
                "author": m.get("author", m.get("user", {}).get("username", "unknown")),
                "text": text,
                "tweet_id": mid,
                "created_at": m.get("created_at", datetime.now().isoformat()),
            })
        return results

    def _is_substantive(self, text: str) -> bool:
        if len(text) < 20:
            return False
        lower = text.lower()
        for pat in SPAM_PATTERNS:
            if pat in lower:
                return False
        return True
