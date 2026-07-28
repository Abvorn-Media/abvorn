"""Pexels Asset Fetcher — pulls images and videos from Pexels API
for use in social posts, carousels, and video backgrounds."""

import logging, os, json, hashlib
from pathlib import Path
from datetime import datetime

import requests

logger = logging.getLogger("abvorn.domination.pexels")

PEXELS_BASE = "https://api.pexels.com/v1"
PEXELS_VIDEO_BASE = "https://api.pexels.com/videos"
ASSET_DIR = Path.home() / ".abvorn" / "assets"


class PexelsAssetFetcher:
    """Fetches and caches Pexels images/videos for social content.

    Checks APIBudget before every live API call. When budget is exhausted,
    serves cached results or falls back to placeholders.
    """

    def __init__(self, api_key: str = "", budget=None):
        self.api_key = api_key or os.environ.get("PEXELS_KEY", "")
        self._budget = budget
        self._cache_file = ASSET_DIR / "pexels_cache.json"
        ASSET_DIR.mkdir(parents=True, exist_ok=True)
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        if self._cache_file.exists():
            try:
                return json.loads(self._cache_file.read_text())
            except (json.JSONDecodeError, Exception):
                pass
        return {}

    def _save_cache(self):
        self._cache_file.write_text(json.dumps(self._cache, indent=2))

    def search_images(self, query: str, per_page: int = 5,
                      orientation: str = "") -> list[dict]:
        cache_key = f"img:{query}:{per_page}:{orientation}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if isinstance(cached, list):
                logger.debug(f"Pexels cache hit: {query}")
                return cached

        if not self.api_key:
            logger.warning("No Pexels API key configured")
            return self._fallback_images(query)

        # ── Budget check ──────────────────────────────────────────
        if self._budget and not self._budget.can_call("pexels"):
            logger.warning(f"Pexels budget exhausted — serving cached/fallback for '{query}'")
            same_query = self._cache.get(cache_key)
            if isinstance(same_query, list) and same_query:
                logger.info(f"Pexels: reusing cached result for same query '{query}'")
                return same_query
            return self._fallback_images(query)
        # ────────────────────────────────────────────────────────────

        try:
            params = {"query": query, "per_page": min(per_page, 80)}
            if orientation:
                params["orientation"] = orientation
            resp = requests.get(
                f"{PEXELS_BASE}/search",
                headers={"Authorization": self.api_key},
                params=params,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                photos = [
                    {
                        "id": p["id"],
                        "url": p["url"],
                        "src": p["src"]["original"],
                        "src_medium": p["src"]["medium"],
                        "src_small": p["src"]["small"],
                        "photographer": p["photographer"],
                        "photographer_url": p["photographer_url"],
                        "alt": p.get("alt", query),
                        "width": p["width"],
                        "height": p["height"],
                    }
                    for p in data.get("photos", [])
                ]
                self._cache[cache_key] = photos
                self._save_cache()
                if self._budget:
                    self._budget.record_call("pexels")
                logger.info(f"Pexels: fetched {len(photos)} images for '{query}'")
                return photos
            else:
                logger.warning(f"Pexels API error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Pexels search failed: {e}")

        return self._fallback_images(query)

    def search_videos(self, query: str, per_page: int = 3) -> list[dict]:
        cache_key = f"vid:{query}:{per_page}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if isinstance(cached, list):
                logger.debug(f"Pexels video cache hit: {query}")
                return cached

        if not self.api_key:
            logger.warning("No Pexels API key configured")
            return []

        if self._budget and not self._budget.can_call("pexels"):
            logger.warning(f"Pexels budget exhausted — serving cached video fallback for '{query}'")
            for key, cached in self._cache.items():
                if key.startswith("vid:") and isinstance(cached, list) and cached:
                    logger.info(f"Pexels: reusing cached video '{key}' as budget fallback")
                    return cached
            return []

        try:
            resp = requests.get(
                f"{PEXELS_VIDEO_BASE}/search",
                headers={"Authorization": self.api_key},
                params={"query": query, "per_page": min(per_page, 80)},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                videos = []
                for v in data.get("videos", []):
                    video_files = sorted(
                        v.get("video_files", []),
                        key=lambda x: x.get("width", 0) * x.get("height", 0),
                        reverse=True,
                    )
                    videos.append({
                        "id": v["id"],
                        "url": v["url"],
                        "video_files": video_files[:3],
                        "duration": v.get("duration", 0),
                        "width": v.get("width", 0),
                        "height": v.get("height", 0),
                        "user": v.get("user", {}).get("name", ""),
                    })
                self._cache[cache_key] = videos
                self._save_cache()
                if self._budget:
                    self._budget.record_call("pexels")
                logger.info(f"Pexels: fetched {len(videos)} videos for '{query}'")
                return videos
            else:
                logger.warning(f"Pexels video API error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Pexels video search failed: {e}")

        return []

    def download_image(self, url: str, niche: str = "",
                       filename: str = "") -> str | None:
        dest_dir = ASSET_DIR / niche if niche else ASSET_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / (filename or hashlib.md5(url.encode()).hexdigest()[:16] + ".jpg")

        if dest.exists():
            return str(dest)

        try:
            resp = requests.get(url, timeout=30, headers={
                "User-Agent": "AbvornDomination/1.0"
            })
            if resp.status_code == 200:
                dest.write_bytes(resp.content)
                logger.info(f"Downloaded Pexels asset to {dest}")
                return str(dest)
            else:
                logger.warning(f"Download failed {resp.status_code}: {url[:80]}")
        except Exception as e:
            logger.warning(f"Download error: {e}")

        return None

    def asset_for_niche(self, niche: str, count: int = 3) -> list[dict]:
        query_map = {
            "tv": "modern living room tv",
            "laptop": "person using laptop",
            "smart-home": "smart home technology",
            "monitor": "computer monitor desk",
            "robot-vacuum": "robot vacuum cleaning",
            "webcams": "video conference camera",
            "headphones": "person wearing headphones",
            "gaming-mouse": "gaming setup mouse",
            "wireless-chargers": "phone wireless charging",
            "mechanical-keyboard": "mechanical keyboard desk",
        }
        query = query_map.get(niche, niche)
        return self.search_images(query, per_page=count)

    def _fallback_images(self, query: str) -> list[dict]:
        """Generate placeholder asset references when API is unavailable."""
        return [
            {
                "id": f"fallback_{hashlib.md5(query.encode()).hexdigest()[:8]}",
                "url": f"https://via.placeholder.com/800x600/1a1a1a/cccccc?text={query.replace(' ', '+')}",
                "src": "",
                "src_medium": "",
                "src_small": "",
                "photographer": "Abvorn",
                "alt": query,
                "width": 800,
                "height": 600,
            }
        ]
