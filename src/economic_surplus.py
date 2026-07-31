#!/usr/bin/env python3
"""
economic_surplus.py — Economic Surplus Measurement with Real Data Collection

Measures economic surplus at SaaS, community, and country levels with
actual data collection from available sources and computed proxies.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SaaSMetrics:
    def __init__(self):
        self.revenue_data = []
        self.user_value_data = []
        self.cost_savings_data = []

    def add_revenue(self, amount: float, source: str = "unknown") -> None:
        self.revenue_data.append({
            "amount": amount,
            "source": source,
            "timestamp": datetime.now().isoformat(),
        })

    def add_user_value(self, value: float, user_id: str = "anonymous") -> None:
        self.user_value_data.append({
            "value": value,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
        })

    def add_cost_savings(self, savings: float, category: str = "general") -> None:
        self.cost_savings_data.append({
            "savings": savings,
            "category": category,
            "timestamp": datetime.now().isoformat(),
        })

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
            "revenue_count": len(self.revenue_data),
            "user_value_count": len(self.user_value_data),
            "cost_savings_count": len(self.cost_savings_data),
            "data_points": len(self.revenue_data),
        }

    def collect_from_env(self) -> Dict[str, Any]:
        revenue = float(os.environ.get("ABVORN_REVENUE", "0"))
        users = int(os.environ.get("ABVORN_USERS", "0"))
        user_value = float(os.environ.get("ABVORN_USER_VALUE", "0"))
        cost_savings = float(os.environ.get("ABVORN_COST_SAVINGS", "0"))

        if revenue > 0:
            self.add_revenue(revenue, "environment")
        if user_value > 0:
            self.add_user_value(user_value, "environment")
        if cost_savings > 0:
            self.add_cost_savings(cost_savings, "environment")

        return {
            "revenue": revenue,
            "users": users,
            "user_value": user_value,
            "cost_savings": cost_savings,
            "collected_at": datetime.now().isoformat(),
        }


class CommunityMetrics:
    def __init__(self):
        self.time_saved_data = []
        self.decision_improvement_data = []
        self.community_growth_data = []
        self.satisfaction_data = []

    def add_time_saved(self, hours: float, user_id: str = "anonymous") -> None:
        self.time_saved_data.append({
            "hours": hours,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
        })

    def add_decision_improvement(self, improvement: float, metric: str = "accuracy") -> None:
        self.decision_improvement_data.append({
            "improvement": improvement,
            "metric": metric,
            "timestamp": datetime.now().isoformat(),
        })

    def add_community_growth(self, growth: float, source: str = "organic") -> None:
        self.community_growth_data.append({
            "growth": growth,
            "source": source,
            "timestamp": datetime.now().isoformat(),
        })

    def add_satisfaction(self, score: float, user_id: str = "anonymous") -> None:
        self.satisfaction_data.append({
            "score": score,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
        })

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

    def calculate_satisfaction(self) -> float:
        if not self.satisfaction_data:
            return 0.0
        return sum(d.get("score", 0) for d in self.satisfaction_data) / len(self.satisfaction_data)

    def get_report(self) -> Dict[str, Any]:
        return {
            "total_time_saved_hours": self.calculate_time_saved(),
            "avg_decision_improvement": self.calculate_decision_improvement(),
            "community_growth_rate": self.calculate_community_growth(),
            "avg_satisfaction": self.calculate_satisfaction(),
            "time_saved_count": len(self.time_saved_data),
            "data_points": len(self.time_saved_data),
        }

    def collect_from_env(self) -> Dict[str, Any]:
        hours = float(os.environ.get("ABVORN_COMMUNITY_HOURS_SAVED", "0"))
        satisfaction = float(os.environ.get("ABVORN_COMMUNITY_SATISFACTION", "0"))
        growth = float(os.environ.get("ABVORN_COMMUNITY_GROWTH", "0"))

        if hours > 0:
            self.add_time_saved(hours, "environment")
        if satisfaction > 0:
            self.add_satisfaction(satisfaction, "environment")
        if growth > 0:
            self.add_community_growth(growth, "environment")

        return {
            "time_saved_hours": hours,
            "satisfaction": satisfaction,
            "growth_rate": growth,
            "collected_at": datetime.now().isoformat(),
        }


class CountryMetrics:
    def __init__(self):
        self.productivity_gain_data = []
        self.innovation_index_data = []
        self.economic_impact_data = []

    def add_productivity_gain(self, gain: float, sector: str = "general") -> None:
        self.productivity_gain_data.append({
            "gain": gain,
            "sector": sector,
            "timestamp": datetime.now().isoformat(),
        })

    def add_innovation_index(self, score: float, category: str = "ai_adoption") -> None:
        self.innovation_index_data.append({
            "index": score,
            "category": category,
            "timestamp": datetime.now().isoformat(),
        })

    def add_economic_impact(self, impact: float, metric: str = "gdp_contribution") -> None:
        self.economic_impact_data.append({
            "impact": impact,
            "metric": metric,
            "timestamp": datetime.now().isoformat(),
        })

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
            "productivity_gain_count": len(self.productivity_gain_data),
            "data_points": len(self.productivity_gain_data),
        }

    def collect_from_env(self) -> Dict[str, Any]:
        productivity = float(os.environ.get("ABVORN_PRODUCTIVITY_GAIN", "0"))
        innovation = float(os.environ.get("ABVORN_INNOVATION_INDEX", "0"))
        impact = float(os.environ.get("ABVORN_ECONOMIC_IMPACT", "0"))

        if productivity > 0:
            self.add_productivity_gain(productivity, "environment")
        if innovation > 0:
            self.add_innovation_index(innovation, "environment")
        if impact > 0:
            self.add_economic_impact(impact, "environment")

        return {
            "productivity_gain": productivity,
            "innovation_index": innovation,
            "economic_impact": impact,
            "collected_at": datetime.now().isoformat(),
        }


class EconomicSurplusTracker:
    def __init__(self, data_dir: str = "data/surplus"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.saas = SaaSMetrics()
        self.community = CommunityMetrics()
        self.country = CountryMetrics()
        self.social_permission_score = 0.0
        self.measurement_history: List[Dict[str, Any]] = []
        self.article_records: List[Dict[str, Any]] = []
        self.load_records()
        self._data_sources_initialized = False
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        config_path = Path("config.yaml")
        if not config_path.exists():
            return {}
        try:
            if yaml is None:
                return {}
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data.get("economic", {})
        except Exception:
            return {}

    def _initialize_data_sources(self) -> None:
        if self._data_sources_initialized:
            return
        self.saas.collect_from_env()
        self.community.collect_from_env()
        self.country.collect_from_env()
        self._data_sources_initialized = True

    def measure(self) -> Dict[str, Any]:
        self._initialize_data_sources()
        self.saas.collect_from_env()
        self.community.collect_from_env()
        self.country.collect_from_env()

        result = {
            "saas": self.saas.get_report(),
            "community": self.community.get_report(),
            "country": self.country.get_report(),
            "social_permission_score": self._calculate_social_permission(),
            "measured_at": datetime.now().isoformat(),
        }
        self.measurement_history.append(result)
        return result

    def measure_and_report(self) -> Dict[str, Any]:
        result = self.measure()
        report_path = self.save_report(result)
        result["report_path"] = report_path
        return result

    def calculate_estimated_revenue(self, clicks: int) -> float:
        config = self.config.get("estimated", {})
        conv_rate = config.get("estimated_conversion_rate", 0.07)
        comm_rate = config.get("estimated_commission_rate", 0.06)
        avg_order = config.get("average_order_value", 50)
        sales = clicks * conv_rate
        return float(sales * avg_order * comm_rate)

    def record_article(self, article_id: str, niche: str, revenue: float, costs: float = 0.0) -> Dict[str, Any]:
        record = {
            "article_id": article_id,
            "niche": niche,
            "revenue": revenue,
            "costs": costs,
            "profit": revenue - costs,
            "recorded_at": datetime.now().isoformat(),
        }
        self.article_records.append(record)
        self.saas.add_revenue(revenue, source=f"article:{article_id}")
        if costs:
            self.saas.add_cost_savings(costs, category=f"article:{article_id}")
        self.save_records()
        return record

    def save_records(self):
        """Save all article records to disk."""
        filepath = self.data_dir / "economic_records.json"
        data = [dict(r) for r in self.article_records]
        filepath.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Saved {len(self.article_records)} economic records")

    def load_records(self):
        """Load article records from disk."""
        filepath = self.data_dir / "economic_records.json"
        if filepath.exists():
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                self.article_records = [dict(r) for r in data]
                logger.info(f"Loaded {len(self.article_records)} economic records")
            except Exception as e:
                logger.warning(f"Failed to load economic records: {e}")

    def _calculate_social_permission(self) -> float:
        saas = self.saas.get_report()
        community = self.community.get_report()
        country = self.country.get_report()
        score = 0.0
        score += min(saas.get("revenue", 0) / 10000, 0.3)
        score += min(community.get("total_time_saved_hours", 0) / 1000, 0.3)
        score += min(country.get("avg_productivity_gain", 0) * 10, 0.4)
        return min(score, 1.0)

    def save_report(self, report: Dict[str, Any] = None) -> str:
        if report is None:
            report = self.measure()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        path = self.data_dir / f"surplus_report_{timestamp}.json"
        path.write_text(
            json.dumps(report, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Surplus report saved: {path}")
        return str(path)

    def get_all_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.measurement_history[-limit:] if self.measurement_history else []

    def get_trend(self, metric: str) -> List[float]:
        values = []
        for report in self.measurement_history:
            if metric == "social_permission_score":
                values.append(report.get("social_permission_score", 0.0))
            elif metric == "revenue":
                values.append(report.get("saas", {}).get("revenue", 0.0))
            elif metric == "time_saved":
                values.append(report.get("community", {}).get("total_time_saved_hours", 0.0))
            elif metric == "productivity_gain":
                values.append(report.get("country", {}).get("avg_productivity_gain", 0.0))
        return values


def create_economic_surplus_tracker() -> EconomicSurplusTracker:
    return EconomicSurplusTracker()


if __name__ == "__main__":
    tracker = create_economic_surplus_tracker()
    report = tracker.measure()
    print(json.dumps(report, indent=2, default=str))