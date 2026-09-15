"""TrendScanner — uses real web providers for trending tech product discovery."""

import json
import logging
import re
import time
from pathlib import Path

from .recon.providers import DuckDuckGoSource, AmazonSource, RedditSource, GoogleTrendsSource
from .predict.snapshotter import SignalSnapshotter
from .predict.velocity import VelocityTracker
from .predict.booster import ScoreBooster

logger = logging.getLogger("abvorn.trends.scanner")

# Proven baseline scan scope. `data_driven_subcategories()` widens this to the
# rest of the site's taxonomy (plus Search Console demand) so discovery hunts
# where the site actually publishes instead of a fixed handful of niches.
DEFAULT_SUBCATEGORIES = ["tv", "robot vacuum", "laptop", "monitor", "smart home"]


def _repo_data_dir() -> Path:
    """Repo-root data/ dir (the daemon and feed both write discovery data there)."""
    return Path(__file__).resolve().parents[2] / "data"


_REVIEWS_SEG = re.compile(r"/reviews/([a-z0-9-]+)", re.I)


def _last_path_segment(url: str) -> str:
    path = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)
    return path[-1].strip().lower() if path else ""


def _gsc_category_phrases(data_dir=None) -> list:
    """Site categories with Search Console demand, from gsc_top_performing.json.

    Only segments that resolve to a real site category slug count — anything
    else (article slugs, the repo root) is ignored so we never mint junk scope.
    """
    d = Path(data_dir) if data_dir else (_repo_data_dir() or Path("data"))
    try:
        payload = json.loads((d / "gsc_top_performing.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    items = payload.get("items", []) if isinstance(payload, dict) else []

    from ..discovery.scanner import SITE_CATEGORY_MAP
    valid = set(SITE_CATEGORY_MAP.values())
    segs = []
    for it in items:
        url = (it or {}).get("url") or ""
        for m in _REVIEWS_SEG.finditer(url):
            seg = m.group(1).strip().lower()
            if seg in valid and seg not in segs:
                segs.append(seg)
        seg = _last_path_segment(url)
        if seg in valid and seg not in segs:
            segs.append(seg)

    # Turn a site slug back into the canonical discovery phrase for that category.
    phrase_by_slug = {}
    for key, slug in SITE_CATEGORY_MAP.items():
        phrase_by_slug.setdefault(slug, key)
    return [phrase_by_slug[seg] for seg in segs]


def _covered_slugs(phrases, site_map) -> set:
    """Site category slugs already covered by a given phrase set."""
    covered = set()
    for key, slug in site_map.items():
        if key in phrases:
            covered.add(slug)
    return covered


def data_driven_subcategories(cap_extra=None, data_dir=None) -> list:
    """Compose the trending scan scope from Google signals + the full taxonomy.

    Rules:
    * DEFAULT_SUBCATEGORIES is always the baseline.
    * Categories with Search Console demand come next (one phrase each).
    * Then the rest of the site's discovery taxonomy, one representative phrase
      per category, in SITE_CATEGORY_MAP order.
    * `cap_extra` (int) truncates the extras; None keeps them all.
    """
    from ..discovery.scanner import SITE_CATEGORY_MAP

    seen, result = set(), []
    for phrase in DEFAULT_SUBCATEGORIES:
        key = phrase.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(key)

    extras = []
    covered = _covered_slugs(seen, SITE_CATEGORY_MAP)
    for phrase in _gsc_category_phrases(data_dir):
        key = phrase.strip().lower()
        if key and key not in seen:
            seen.add(key)
            extras.append(key)
    for phrase, slug in SITE_CATEGORY_MAP.items():
        key = phrase.strip().lower()
        if not key or key in seen or slug in covered:
            continue
        covered.add(slug)  # one phrase per category keeps the pool bounded
        seen.add(key)
        extras.append(key)

    if cap_extra is not None:
        extras = extras[:max(0, cap_extra)]
    return result + extras


def _default_subcategories() -> list:
    try:
        return data_driven_subcategories() or DEFAULT_SUBCATEGORIES
    except Exception as e:
        logger.debug(f"Falling back to baseline subcategories: {e}")
        return DEFAULT_SUBCATEGORIES


class TrendScanner:
    """Scans multiple sources for trending tech products using real web providers."""

    def __init__(self, min_score: int = 40, cache_seconds: int = 86400,
                 subcategories: list = None, providers: list = None,
                 state=None):
        self.min_score = min_score
        self.cache_seconds = cache_seconds
        self.subcategories = subcategories if subcategories else _default_subcategories()
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