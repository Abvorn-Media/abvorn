"""UserInteractionCollector — tracks per-product user engagement signals."""

import logging, json, os
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("abvorn.analytics.collector")


class UserInteractionCollector:
    """Collects user interactions (page views, affiliate clicks, conversions) per product.

    Stores raw events in a local JSON store for batch processing by the FeedbackLearner.
    """

    def __init__(self, store_dir: str = None, ga4_client=None):
        self.ga4_client = ga4_client
        self.store_dir = Path(store_dir or "data/interactions")
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._unsent = []

    def track_page_view(self, page_url: str, product_id: str = None, niche_slug: str = None):
        """Record a page view event."""
        event = {
            "type": "page_view",
            "page_url": page_url,
            "product_id": product_id,
            "niche_slug": niche_slug,
            "timestamp": datetime.now().isoformat(),
        }
        self._store(event)

    def track_affiliate_click(self, product_id: str, niche_slug: str = None, user_id: str = None):
        """Record an affiliate link click."""
        event = {
            "type": "affiliate_click",
            "product_id": product_id,
            "niche_slug": niche_slug,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
        }
        self._store(event)

    def track_conversion(self, product_id: str, niche_slug: str = None, revenue: float = None, user_id: str = None):
        """Record a confirmed purchase conversion."""
        event = {
            "type": "conversion",
            "product_id": product_id,
            "niche_slug": niche_slug,
            "revenue": revenue,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
        }
        self._store(event)

    def _store(self, event: dict):
        """Write event to daily JSONL file for batch processing."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = self.store_dir / f"{date_str}.jsonl"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
        self._unsent.append(event)

    def get_recent_interactions(self, days: int = 7) -> list[dict]:
        """Load interaction events from the last N days."""
        events = []
        for i in range(days):
            date_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            filepath = self.store_dir / f"{date_str}.jsonl"
            if filepath.exists():
                with open(filepath, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            events.append(json.loads(line))
        return events

    def get_interactions_by_product(self, days: int = 7) -> dict:
        """Group recent interactions by product_id, returning aggregates."""
        events = self.get_recent_interactions(days=days)
        by_product = {}
        for ev in events:
            pid = ev.get("product_id")
            if not pid:
                continue
            if pid not in by_product:
                by_product[pid] = {"page_views": 0, "affiliate_clicks": 0, "conversions": 0, "revenue": 0.0}
            t = ev["type"]
            if t == "page_view":
                by_product[pid]["page_views"] += 1
            elif t == "affiliate_click":
                by_product[pid]["affiliate_clicks"] += 1
            elif t == "conversion":
                by_product[pid]["conversions"] += 1
                by_product[pid]["revenue"] += ev.get("revenue", 0.0)
        return by_product
