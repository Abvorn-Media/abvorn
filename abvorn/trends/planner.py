"""ContentPlanner — matches trending products to best content formats."""

import logging

logger = logging.getLogger("abvorn.trends.planner")

CONTENT_TYPES = {
    "buying_guide": {"primary": "blog", "secondary": "linkedin", "min_score": 70},
    "comparison": {"primary": "blog", "secondary": "linkedin", "min_score": 70},
    "social_thread": {"primary": "x", "secondary": "tiktok", "min_score": 40},
    "tiktok_script": {"primary": "tiktok", "secondary": "instagram", "min_score": 40},
}


class ContentPlanner:
    """Selects optimal content format for each trending product."""

    def __init__(self, scanner=None, intel_engine=None):
        self.scanner = scanner
        self.intel_engine = intel_engine

    def plan(self, trend_results: list, max_items: int = 10) -> list:
        if not trend_results:
            return []

        planned = []
        for trend in trend_results:
            score = trend.get("score", 50)
            sources = trend.get("sources", [trend.get("source", "web")])

            if score >= 70:
                content_type = "buying_guide"
            elif score >= 55:
                content_type = "comparison" if len(sources) >= 2 else "social_thread"
            else:
                content_type = "social_thread"

            if content_type == "social_thread" and trend.get("category") in ("laptop", "monitor"):
                content_type = "tiktok_script"

            type_config = CONTENT_TYPES.get(content_type, CONTENT_TYPES["social_thread"])
            planned.append({
                "product_name": trend["product_name"],
                "category": trend.get("category", ""),
                "content_type": content_type,
                "primary_platform": type_config["primary"],
                "secondary_platform": type_config["secondary"],
                "score": score,
                "sources": sources,
            })

        return sorted(planned, key=lambda x: -x["score"])[:max_items]