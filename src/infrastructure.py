#!/usr/bin/env python3
"""
infrastructure.py — Infrastructure layer for compute optimization and economic surplus tracking.

Tracks API costs per article/provider, latency, and measures economic surplus vs. cost.
Implements Nadella's Infrastructure Layer (compute optimization, cost monitoring).
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger("infrastructure")


class InfrastructureReporter:
    def __init__(self):
        self.cost_by_article: Dict[str, Dict[str, Any]] = {}
        self.cost_by_provider: Dict[str, float] = defaultdict(float)
        self.cost_by_niche: Dict[str, float] = defaultdict(float)
        self.latency_by_provider: Dict[str, float] = defaultdict(float)
        self.total_cost = 0.0
        self.total_articles = 0
        self.total_tokens = 0
        self.total_revenue = 0.0
        self.total_latency_ms = 0.0

    def report_article_cost(
        self,
        article_id: str,
        provider_name: str,
        cost: float,
        latency_ms: float,
        tokens: int,
        niche: str = "",
    ):
        self.cost_by_article[article_id] = {
            "provider": provider_name,
            "cost": cost,
            "latency_ms": latency_ms,
            "tokens": tokens,
            "niche": niche,
            "timestamp": datetime.now().isoformat(),
        }
        self.cost_by_provider[provider_name] += cost
        self.latency_by_provider[provider_name] = (
            self.latency_by_provider.get(provider_name, 0.0) + latency_ms
        )
        self.cost_by_niche[niche] += cost
        self.total_cost += cost
        self.total_articles += 1
        self.total_tokens += tokens
        self.total_latency_ms += latency_ms
        logger.info(
            f"Article {article_id}: {provider_name} | "
            f"cost=${cost:.4f} | {tokens}tok | {latency_ms:.0f}ms"
        )

    def report_article_revenue(self, article_id: str, revenue: float):
        if article_id in self.cost_by_article:
            self.cost_by_article[article_id]["revenue"] = revenue
        self.total_revenue += revenue

    def get_summary(self) -> Dict[str, Any]:
        avg_cost = self.total_cost / max(self.total_articles, 1)
        avg_latency = self.total_latency_ms / max(self.total_articles, 1)
        avg_tokens = self.total_tokens / max(self.total_articles, 1)
        profit = self.total_revenue - self.total_cost

        return {
            "total_articles": self.total_articles,
            "total_cost": round(self.total_cost, 4),
            "total_revenue": round(self.total_revenue, 2),
            "total_tokens": self.total_tokens,
            "profit": round(profit, 2),
            "average_cost_per_article": round(avg_cost, 4),
            "average_latency_ms": round(avg_latency, 0),
            "average_tokens_per_article": round(avg_tokens, 0),
            "roi": round(self.total_revenue / max(self.total_cost, 0.001), 2),
            "cost_by_provider": dict(self.cost_by_provider),
            "cost_by_niche": dict(self.cost_by_niche),
            "latency_by_provider": {
                k: round(v, 0)
                for k, v in self.latency_by_provider.items()
            },
        }

    def get_provider_report(self) -> Dict[str, Dict[str, Any]]:
        providers: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"cost": 0.0, "articles": 0, "tokens": 0, "latency_ms": 0.0}
        )
        for article_id, data in self.cost_by_article.items():
            p = data["provider"]
            providers[p]["cost"] += data["cost"]
            providers[p]["articles"] += 1
            providers[p]["tokens"] += data.get("tokens", 0)
            providers[p]["latency_ms"] += data.get("latency_ms", 0.0)
        return dict(providers)


infra_reporter = InfrastructureReporter()
