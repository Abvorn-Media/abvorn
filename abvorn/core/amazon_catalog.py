"""Amazon catalog client — real, buyable products for a niche.

Tavily and the LLM knowledge fallback cannot produce a buyable product: both
prompt for ``{name, price, description, features, category, source_url}`` and
neither asks for an ASIN or a product photo. Every product they return is
therefore rejected by ``_products_are_placeholder()`` at the deploy boundary,
which is why ``research_niche()`` could never unblock a fresh tv page.

This client hits the Open Web Ninja realtime Amazon endpoint, the one source in
the repo that returns ``asin`` + ``image`` + ``url`` per product. Results are
cached on disk so a provider outage degrades to the last good product list
instead of a skipped page.

Signup/key: OPENWEB_NINJA_KEY (see abvorn/core/secrets.py).
"""

import hashlib
import html
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("abvorn.amazon")

API_URL = "https://api.openwebninja.com/realtime-amazon-data/search"

CACHE_DIRS = [
    Path("data/openweb_cache"),
    Path("/opt/abvorn-core/data/openweb_cache"),
]


def _cache_dir() -> Path:
    for d in CACHE_DIRS:
        try:
            if d.parent.exists():
                return d
        except OSError:
            continue
    return CACHE_DIRS[0]


def _cache_key(query: str) -> str:
    return hashlib.md5(f"amazon:best {query}".encode()).hexdigest()


def _clean_name(raw: str) -> str:
    """Amazon titles arrive HTML-escaped and comma-stuffed.

    ``INSIGNIA 50&quot; Class F50 Series, LED 4K UHD`` becomes
    ``INSIGNIA 50" Class F50 Series LED 4K UHD``. Without this the escaped
    entities ship straight into product names on a live page.
    """
    text = str(raw or "").split(",")[0].strip()
    return html.unescape(text)


class AmazonCatalogClient:
    """Real Amazon products with ASIN, price, rating and photo."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("OPENWEB_NINJA_KEY", "")

    @property
    def available(self) -> bool:
        return bool(self.api_key) and "YOUR_" not in self.api_key

    def _load_cache(self) -> dict:
        f = _cache_dir() / "cache.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_cache(self, cache: dict):
        d = _cache_dir()
        try:
            d.mkdir(parents=True, exist_ok=True)
            (d / "cache.json").write_text(
                json.dumps(cache, indent=2), encoding="utf-8"
            )
        except OSError as e:
            logger.warning(f"Amazon catalog cache write failed: {e}")

    @staticmethod
    def _normalize(raw: dict) -> dict:
        return {
            "name": _clean_name(raw.get("product_title", "")),
            "price": str(raw.get("product_price", "") or ""),
            "original_price": str(raw.get("product_original_price", "") or ""),
            "rating": str(raw.get("product_star_rating", "") or ""),
            "ratings_count": raw.get("product_num_ratings", 0),
            "image": str(raw.get("product_photo", "") or ""),
            "url": str(raw.get("product_url", "") or ""),
            "asin": str(raw.get("asin", "") or "").strip(),
            "description": _clean_name(raw.get("product_title", "")),
            "features": [],
            "is_best_seller": bool(raw.get("is_best_seller", False)),
            "is_amazon_choice": bool(raw.get("is_amazon_choice", False)),
            "sales_volume": raw.get("sales_volume", ""),
        }

    def search_products(self, niche: str, max_products: int = 5,
                        use_cache: bool = True) -> list:
        """Return real products for ``niche``, or [] when nothing is available.

        Cache first, then the live API. A cached list is only returned when it
        still carries an ASIN and a photo, so a pre-fix cache full of unusable
        shapes cannot resurrect a refused page.
        """
        query = niche.replace("-", " ")
        key = _cache_key(query)

        if use_cache:
            cached = self._load_cache().get(key)
            if cached:
                buyable = [
                    p for p in cached
                    if str(p.get("asin") or "").strip() and str(p.get("image") or "").strip()
                ]
                if buyable:
                    logger.info(
                        f"Amazon catalog cache hit for '{niche}': {len(buyable)} products"
                    )
                    return buyable[:max_products]
                logger.warning(
                    f"Amazon catalog cache entry for '{niche}' has no ASIN/photo; "
                    "refetching instead of returning unusable products"
                )

        if not self.available:
            logger.warning("Amazon catalog: no OPENWEB_NINJA_KEY configured")
            return []

        try:
            import requests as rq
            resp = rq.get(
                API_URL,
                params={"query": query, "page": 1},
                headers={"X-API-Key": self.api_key},
                timeout=15,
            )
        except Exception as e:
            logger.warning(f"Amazon catalog request failed for '{niche}': {e}")
            return []

        if resp.status_code != 200:
            logger.warning(f"Amazon catalog returned {resp.status_code} for '{niche}'")
            return []

        try:
            raws = resp.json().get("data", {}).get("products", []) or []
        except (ValueError, AttributeError) as e:
            logger.warning(f"Amazon catalog response unparseable for '{niche}': {e}")
            return []

        products = [self._normalize(p) for p in raws[:max_products]]
        # The deploy boundary refuses any payload with no ASIN anywhere, so do
        # not let an ASIN-less response become a product list at all.
        products = [p for p in products if p["asin"]]
        if not products:
            logger.warning(f"Amazon catalog returned no ASIN-bearing products for '{niche}'")
            return []

        if use_cache:
            cache = self._load_cache()
            cache[key] = products
            self._save_cache(cache)

        logger.info(
            f"Amazon catalog found {len(products)} products for '{niche}': "
            f"{[p['name'] for p in products]}"
        )
        return products