"""ProductMatcher — matches products to persuasion context."""

import json
import logging
from dataclasses import dataclass, field
from ..sites.model import BrandConfig

logger = logging.getLogger("abvorn.persuasion.matcher")
MAX_PRODUCTS = 3
PRODUCTS_KEY = "persuasion:products"


@dataclass
class ProductRecommendation:
    name: str
    tagline: str
    price_range: str
    affiliate_url: str
    reason_to_buy: str = ""
    image_url: str = ""


class ProductMatcher:
    """Matches products from catalog to context. Falls back to empty list."""

    def __init__(self, state):
        self._state = state

    def match(self, context) -> list[ProductRecommendation]:
        products = self._load_products(context.niche)
        products = self._rank_by_stage(products, context.buying_stage)
        return products[:MAX_PRODUCTS]

    def _load_products(self, niche: str) -> list[ProductRecommendation]:
        raw = self._state.get_meta(f"{PRODUCTS_KEY}:{niche}", "[]")
        data = json.loads(raw) if isinstance(raw, str) else raw
        result = []
        for item in data:
            result.append(ProductRecommendation(
                name=item.get("name", ""),
                tagline=item.get("tagline", ""),
                price_range=item.get("price_range", ""),
                affiliate_url=item.get("affiliate_url", ""),
                reason_to_buy=item.get("reason_to_buy", ""),
                image_url=item.get("image_url", ""),
            ))
        return result

    def _rank_by_stage(self, products: list, stage) -> list:
        if stage.value == "decision":
            return sorted(products, key=lambda p: self._price_value(p), reverse=True)
        elif stage.value == "awareness":
            return sorted(products, key=lambda p: self._price_value(p))
        return products

    def _price_value(self, p: ProductRecommendation) -> float:
        import re
        nums = re.findall(r'\d+', p.price_range)
        return int(nums[0]) if nums else 0
