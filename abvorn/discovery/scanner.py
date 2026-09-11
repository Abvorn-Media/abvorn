"""Opportunity discovery — finds untapped affiliate niches."""

import logging, re

logger = logging.getLogger("abvorn.discovery")


def score_opportunity(search_demand: int, buying_intent: float,
                      commission: float, competition: float) -> float:
    """Score an opportunity 0-1. Higher is better."""
    demand_norm = min(search_demand / 10000, 1.0)
    intent_norm = min(buying_intent, 1.0)
    commission_norm = min(commission / 100, 1.0)
    competition_norm = 1.0 - min(competition, 1.0)
    score = demand_norm * 0.3 + intent_norm * 0.3 + commission_norm * 0.2 + competition_norm * 0.2
    return round(score, 2)


class OpportunityScanner:
    """Scans for untapped affiliate opportunities."""

    def __init__(self, state):
        self.state = state

    def discover_from_keywords(self, keywords: list[str],
                                base_demand: int = 1000,
                                base_intent: float = 0.5,
                                base_commission: float = 20.0) -> list[dict]:
        """Discover opportunities from a keyword list. Uses simulated data for Phase 3a."""
        results = []
        for kw in keywords:
            niche = kw.strip().lower()
            existing = self.state.get_opportunities("pending")
            if any(e["niche"] == niche for e in existing):
                continue
            score = score_opportunity(base_demand, base_intent, base_commission, 0.4)
            self.state.add_opportunity(niche, score, base_demand, base_intent, 0.4, base_commission)
            results.append({"niche": niche, "score": score})
            logger.info(f"Discovered opportunity: {niche} (score: {score})")
        return results

    def discover_from_trends(self, trends: list[dict],
                             max_opportunities: int = 3) -> list[dict]:
        """Turn real trending data into deploy opportunities (page + social posts).

        A trend becomes an opportunity only when it is a research-worthy guide
        (buying_guide/comparison) and the niche does not already have a pending
        opportunity or any posts on the site.
        """
        from ..trends.planner import ContentPlanner

        if not trends:
            return []
        planned = ContentPlanner().plan(trends, max_items=max_opportunities * 2)

        existing = self.state.get_opportunities("pending")
        existing_niches = set(n["slug"] for n in self.state.get_all_niches())

        results = []
        for item in planned:
            if item["content_type"] not in ("buying_guide", "comparison"):
                continue
            niche = self._slugify(item["product_name"]) or item["category"]
            if any(e["niche"] == niche for e in existing) or niche in existing_niches:
                continue
            if len(results) >= max_opportunities:
                break
            score = self._trend_score(item["score"])
            self.state.add_opportunity(niche, score, search_volume=0,
                                       buying_intent=0.5, competition=0.4,
                                       commission=20.0)
            results.append({
                "niche": niche,
                "product_name": item["product_name"],
                "category": item["category"],
                "score": round(item["score"], 1),
                "sources": item.get("sources", []),
            })
            logger.info(f"Trend discovery: {niche} (trend score {item['score']})")
        return results

    def _slugify(self, name: str) -> str:
        slug = name.strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
        return slug[:60]

    def _trend_score(self, trend_score: int) -> float:
        """Map a trend score (0-100) onto the opportunity 0-1 scale."""
        score = min(max(trend_score / 100, 0.0), 1.0)
        return round(max(score, 0.5), 2)