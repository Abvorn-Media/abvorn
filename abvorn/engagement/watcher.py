"""MentionWatcher — polls Composio for social mentions with rate-limit-safe polling."""

import logging
import os
import time
from datetime import datetime

logger = logging.getLogger("abvorn.engagement.watcher")

SPAM_PATTERNS = ["lol", "nice", "cool", "follow me", "check out", "http://", "https://"]

from ..deploy.composio_client import ComposioClient

# X has no dedicated "mentions" tool on the v3 surface; mentions are polled
# through recent-search filtered to reply-style @mentions of the brand handle.
MENTION_FETCH_SLUG = "TWITTER_RECENT_SEARCH"


class MentionWatcher:
    """Polls Composio for mentions every 15 min. Deduplicates and filters spam."""

    def __init__(self, composio_key: str = "", state=None, handle: str = ""):
        self.composio_key = composio_key
        self.state = state
        self.handle = handle or os.environ.get("ABVORN_X_HANDLE", "Abvorn")
        self.poll_interval = 900
        self._last_poll = 0.0
        self._replied_ids = set()
        self._raw_mentions = []
        self._client = ComposioClient(api_key=composio_key)

    def poll(self) -> list[dict]:
        """Poll for new mentions. Returns only substantive, unseen mentions."""
        now = time.time()
        if now - self._last_poll < self.poll_interval:
            return []
        self._last_poll = now
        if self._client.available:
            self._fetch_mentions()
        return self._filter_new()

    def _fetch_mentions(self):
        query = f"@{self.handle} -is:retweet"
        try:
            data = self._client.execute(
                "twitter", MENTION_FETCH_SLUG,
                {"query": query, "max_results": 20},
            )
        except Exception as e:
            logger.debug(f"Mention fetch failed: {e}")
            return
        tweets = (
            data.get("tweets")
            or data.get("data")
            or (data if isinstance(data, list) else [])
        )
        self._raw_mentions = self._normalize(tweets)

    @staticmethod
    def _normalize(tweets) -> list[dict]:
        mentions = []
        for t in tweets or []:
            if not isinstance(t, dict):
                continue
            author = t.get("author") or t.get("user") or t.get("author_id") or {}
            username = author.get("username") if isinstance(author, dict) else str(author)
            mentions.append({
                "id": str(t.get("id", "")),
                "author": username or "unknown",
                "text": t.get("text", ""),
                "tweet_id": str(t.get("id", "")),
                "created_at": t.get("created_at", datetime.now().isoformat()),
                "platform": "x",
            })
        return mentions

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