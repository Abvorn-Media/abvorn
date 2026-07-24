"""Opportunity discovery — finds untapped affiliate niches."""

import logging
from datetime import datetime

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