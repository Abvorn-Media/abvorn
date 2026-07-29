#!/usr/bin/env python3
"""
economic_surplus.py — Economic Surplus Measurement

Measures economic surplus at SaaS, community, and country levels.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SaaSMetrics:
    def __init__(self):
        self.revenue_data = []
        self.user_value_data = []
        self.cost_savings_data = []

    def calculate_revenue(self) -> float:
        return sum(d.get("amount", 0) for d in self.revenue_data)

    def calculate_user_value(self) -> float:
        if not self.user_value_data:
            return 0.0
        return sum(d.get("value", 0) for d in self.user_value_data) / len(self.user_value_data)

    def calculate_cost_savings(self) -> float:
        if not self.cost_savings_data:
            return 0.0
        return sum(d.get("savings", 0) for d in self.cost_savings_data)

    def get_report(self) -> Dict[str, Any]:
        return {
            "revenue": self.calculate_revenue(),
            "user_value_per_user": self.calculate_user_value(),
            "cost_savings": self.calculate_cost_savings(),
            "data_points": len(self.revenue_data),
        }


class CommunityMetrics:
    def __init__(self):
        self.time_saved_data = []
        self.decision_improvement_data = []
        self.community_growth_data = []

    def calculate_time_saved(self) -> float:
        if not self.time_saved_data:
            return 0.0
        return sum(d.get("hours", 0) for d in self.time_saved_data)

    def calculate_decision_improvement(self) -> float:
        if not self.decision_improvement_data:
            return 0.0
        return sum(d.get("improvement", 0) for d in self.decision_improvement_data) / max(len(self.decision_improvement_data), 1)

    def calculate_community_growth(self) -> float:
        if not self.community_growth_data:
            return 0.0
        latest = self.community_growth_data[-1].get("growth", 0)
        return latest

    def get_report(self) -> Dict[str, Any]:
        return {
            "total_time_saved_hours": self.calculate_time_saved(),
            "avg_decision_improvement": self.calculate_decision_improvement(),
            "community_growth_rate": self.calculate_community_growth(),
            "data_points": len(self.time_saved_data),
        }


class CountryMetrics:
    def __init__(self):
        self.productivity_gain_data = []
        self.innovation_index_data = []
        self.economic_impact_data = []

    def calculate_productivity_gain(self) -> float:
        if not self.productivity_gain_data:
            return 0.0
        return sum(d.get("gain", 0) for d in self.productivity_gain_data) / max(len(self.productivity_gain_data), 1)

    def calculate_innovation_index(self) -> float:
        if not self.innovation_index_data:
            return 0.0
        return sum(d.get("index", 0) for d in self.innovation_index_data) / max(len(self.innovation_index_data), 1)

    def calculate_economic_impact(self) -> float:
        if not self.economic_impact_data:
            return 0.0
        return sum(d.get("impact", 0) for d in self.economic_impact_data)

    def get_report(self) -> Dict[str, Any]:
        return {
            "avg_productivity_gain": self.calculate_productivity_gain(),
            "avg_innovation_index": self.calculate_innovation_index(),
            "total_economic_impact": self.calculate_economic_impact(),
            "data_points": len(self.productivity_gain_data),
        }


class EconomicSurplusTracker:
    def __init__(self, data_dir: str = "data/surplus"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.saas = SaaSMetrics()
        self.community = CommunityMetrics()
        self.country = CountryMetrics()
        self.social_permission_score = 0.0

    def measure(self) -> Dict[str, Any]:
        return {
            "saas": self.saas.get_report(),
            "community": self.community.get_report(),
            "country": self.country.get_report(),
            "social_permission_score": self._calculate_social_permission(),
            "measured_at": datetime.now().isoformat(),
        }

    def _calculate_social_permission(self) -> float:
        saas = self.saas.get_report()
        community = self.community.get_report()
        country = self.country.get_report()
        score = 0.0
        score += min(saas.get("revenue", 0) / 10000, 0.3)
        score += min(community.get("total_time_saved_hours", 0) / 1000, 0.3)
        score += min(country.get("avg_productivity_gain", 0) * 10, 0.4)
        return min(score, 1.0)

    def save_report(self) -> str:
        report = self.measure()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        path = self.data_dir / f"surplus_report_{timestamp}.json"
        path.write_text(
            json.dumps(report, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Surplus report saved: {path}")
        return str(path)


def create_economic_surplus_tracker() -> EconomicSurplusTracker:
    return EconomicSurplusTracker()


if __name__ == "__main__":
    tracker = create_economic_surplus_tracker()
    report = tracker.measure()
    print(json.dumps(report, indent=2, default=str))