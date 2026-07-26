"""TrendScanner — uses real web providers for trending tech product discovery."""

import logging
import time
from .recon.providers import DuckDuckGoSource, AmazonSource, RedditSource, GoogleTrendsSource
from .predict.snapshotter import SignalSnapshotter
from .predict.velocity import VelocityTracker
from .predict.booster import ScoreBooster

logger = logging.getLogger("abvorn.trends.scanner")

DEFAULT_SUBCATEGORIES = ["tv", "robot vacuum", "laptop", "monitor", "smart home"]


class TrendScanner:
    """Scans multiple sources for trending tech products using real web providers."""

    def __init__(self, min_score: int = 40, cache_seconds: int = 86400,
                 subcategories: list = None, providers: list = None,
                 state=None):
        self.min_score = min_score
        self.cache_seconds = cache_seconds
        self.subcategories = subcategories or DEFAULT_SUBCATEGORIES
        self._cache = {}
        self._cache_hits = 0
        self._state = state
        self._recon_providers = providers or [
            DuckDuckGoSource(),
            AmazonSource(),
            RedditSource(),
            GoogleTrendsSource(),
        ]
        self._signal_snapshotter = SignalSnapshotter()
        self._velocity_tracker = VelocityTracker()
        self._score_booster = ScoreBooster()

    def scan(self, subcategories: list = None) -> list:
        """Scan all sources for trending products. Returns scored list."""
        cats = subcategories or self.subcategories
        all_products = []

        for cat in cats:
            cached = self._get_cached(cat)
            if cached is not None:
                all_products.extend(cached)
                continue

            products = []
            for provider in self._recon_providers:
                try:
                    products.extend(provider.search(cat))
                except Exception as e:
                    logger.debug(f"{provider.__class__.__name__} failed for {cat}: {e}")

            self._set_cache(cat, products)

            try:
                self._signal_snapshotter.store(cat, products, self._state)
            except Exception:
                pass

            all_products.extend(products)

        if self._state:
            try:
                velocity = {}
                for cat in cats:
                    v = self._velocity_tracker.get_velocity(cat, self._state)
                    velocity.update(v)
                all_products = self._score_booster.boost(all_products, velocity)
            except Exception as e:
                logger.debug(f"Velocity boost failed: {e}")

        combined = self._combine_results(all_products)
        return [p for p in combined if p["score"] >= self.min_score]

    def _combine_results(self, products: list) -> list:
        """Dedup and boost products appearing in multiple sources."""
        grouped = {}
        for p in products:
            key = p["product_name"].lower().strip()
            if key in grouped:
                existing = grouped[key]
                existing["score"] = max(existing["score"], p["score"]) + 15
                if "sources" not in existing:
                    existing["sources"] = [existing.get("source", "unknown")]
                existing["sources"].append(p.get("source", "unknown"))
            else:
                p["sources"] = [p.get("source", "unknown")]
                grouped[key] = p
        return sorted(grouped.values(), key=lambda x: -x["score"])

    def _get_cached(self, key: str):
        entry = self._cache.get(key)
        if entry and time.time() - entry["time"] < self.cache_seconds:
            self._cache_hits += 1
            return entry["data"]
        return None

    def _set_cache(self, key: str, data: list):
        self._cache[key] = {"data": data, "time": time.time()}

    def clear_cache(self):
        self._cache = {}