#!/usr/bin/env python3
"""
social_permission.py — Actionable Social Permission Framework

Measures AI's earned social consent to consume resources and acts on scores.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CommunitySurplusReport:
    level: str
    social_permission_score: float
    surplus_type: str
    value: float
    recommendation: str
    action_required: bool
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class SocialPermissionThresholds:
    community_min: float = 0.7
    country_min: float = 0.6
    global_min: float = 0.8
    critical_min: float = 0.3

    def get_level(self, score: float) -> str:
        if score >= self.global_min:
            return "global"
        elif score >= self.country_min:
            return "country"
        elif score >= self.community_min:
            return "community"
        elif score >= self.critical_min:
            return "caution"
        else:
            return "critical"


@dataclass
class SocialAction:
    action_type: str
    description: str
    priority: int
    estimated_impact: float
    auto_execute: bool = False


THRESHOLDS = SocialPermissionThresholds()

ACTIONS = {
    "global": [
        SocialAction(
            action_type="expand",
            description="Expand AI resource consumption — surplus is strong",
            priority=1,
            estimated_impact=0.1,
            auto_execute=False,
        ),
        SocialAction(
            action_type="invest",
            description="Invest surplus back into community and infrastructure",
            priority=2,
            estimated_impact=0.15,
            auto_execute=False,
        ),
    ],
    "country": [
        SocialAction(
            action_type="maintain",
            description="Maintain current usage levels — surplus is adequate",
            priority=1,
            estimated_impact=0.0,
            auto_execute=True,
        ),
        SocialAction(
            action_type="optimize",
            description="Optimize resource usage to improve surplus score",
            priority=2,
            estimated_impact=0.05,
            auto_execute=False,
        ),
    ],
    "community": [
        SocialAction(
            action_type="reduce",
            description="Reduce AI resource consumption to improve community surplus",
            priority=1,
            estimated_impact=-0.05,
            auto_execute=False,
        ),
        SocialAction(
            action_type="invest_community",
            description="Invest in community infrastructure to raise surplus",
            priority=2,
            estimated_impact=0.1,
            auto_execute=False,
        ),
        SocialAction(
            action_type="solicit_feedback",
            description="Solicit user feedback to understand community concerns",
            priority=3,
            estimated_impact=0.0,
            auto_execute=False,
        ),
    ],
    "caution": [
        SocialAction(
            action_type="halt_expansion",
            description="Halt all AI resource expansion immediately",
            priority=1,
            estimated_impact=-0.1,
            auto_execute=True,
        ),
        SocialAction(
            action_type="emergency_audit",
            description="Run emergency social permission audit",
            priority=2,
            estimated_impact=0.0,
            auto_execute=False,
        ),
    ],
    "critical": [
        SocialAction(
            action_type="stop_all",
            description="Stop all AI resource consumption — critical social permission deficit",
            priority=1,
            estimated_impact=-0.2,
            auto_execute=True,
        ),
        SocialAction(
            action_type="public_accountability",
            description="Publish transparency report on AI resource usage",
            priority=2,
            estimated_impact=0.0,
            auto_execute=False,
        ),
        SocialAction(
            action_type="community_restoration",
            description="Launch community restoration initiative",
            priority=3,
            estimated_impact=0.15,
            auto_execute=False,
        ),
    ],
}


class SocialPermissionFramework:
    def __init__(self, data_dir: str = "data/social_permission", nervous_system=None, energy_accounting=None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.nervous_system = nervous_system
        self.energy_accounting = energy_accounting
        self.history: List[Dict[str, Any]] = []
        self.action_log: List[Dict[str, Any]] = []

    def _apply_carbon_adjustment(self, score: float, metrics: Dict[str, Any] = None) -> float:
        if not self.energy_accounting:
            return score
        try:
            report = self.energy_accounting.get_report()
            total_co2 = report.get("total_co2_g", 0)
            carbon_factor = max(0.0, 1.0 - (total_co2 / 100.0))
            economic = (metrics or {}).get("economic_surplus", score * 0.4)
            engagement = (metrics or {}).get("user_engagement", score * 0.3)
            trust = (metrics or {}).get("trust_score", score * 0.3)
            return (economic * 0.4 + engagement * 0.3 + trust * 0.3) * carbon_factor
        except Exception:
            return score

    def act(
        self, score: float, surplus_data: Dict[str, Any] = None, metrics: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Act on social permission score — execute appropriate actions.

        Args:
            score: Social permission score (0.0 - 1.0)
            surplus_data: Optional surplus metrics for context
            metrics: Optional metrics dict (economic_surplus, user_engagement, trust_score)

        Returns:
            Dict with actions taken, level, and recommendations
        """
        score = self._apply_carbon_adjustment(score, metrics)
        level = THRESHOLDS.get_level(score)
        actions = ACTIONS.get(level, [])
        executed_actions: List[Dict[str, Any]] = []

        for action in actions:
            action_entry = {
                "action_type": action.action_type,
                "description": action.description,
                "priority": action.priority,
                "estimated_impact": action.estimated_impact,
                "auto_execute": action.auto_execute,
                "executed": action.auto_execute,
                "executed_at": datetime.now().isoformat() if action.auto_execute else None,
            }

            if action.auto_execute:
                self._execute_action(action, score, level)
                executed_actions.append(action_entry)
                self.action_log.append(action_entry)
            else:
                executed_actions.append(action_entry)
                self.action_log.append(action_entry)

        report = {
            "social_permission_score": score,
            "level": level,
            "thresholds": {
                "community_min": THRESHOLDS.community_min,
                "country_min": THRESHOLDS.country_min,
                "global_min": THRESHOLDS.global_min,
                "critical_min": THRESHOLDS.critical_min,
            },
            "actions": executed_actions,
            "surplus_data": surplus_data or {},
            "metrics": metrics or {},
            "recommendations": self._generate_recommendations(level, score),
            "timestamp": datetime.now().isoformat(),
        }

        self.history.append(report)
        self._save_report(report)

        return report

    def _execute_action(
        self, action: SocialAction, score: float, level: str
    ) -> None:
        """Execute an auto-execute action by routing to the Nervous System."""
        logger.info(
            f"AUTO-EXECUTING action '{action.action_type}' for level '{level}' (score={score:.2f})"
        )
        if not self.nervous_system:
            logger.warning("No NervousSystem available, action not executed")
            return

        action_map = {
            "reduce": self.nervous_system.pause_low_performing_niches,
            "halt_expansion": self.nervous_system.pause_expansion,
            "stop_all": self.nervous_system.pause_expansion,
            "scale": self.nervous_system.scale_infrastructure,
            "expand": self.nervous_system.expand_niches,
            "invest": self.nervous_system.add_features,
            "maintain": self.nervous_system.increase_frequency,
            "optimize": self.nervous_system.refine_content,
            "refine": self.nervous_system.optimize_providers,
        }

        if action.action_type in action_map:
            try:
                action_map[action.action_type]()
                logger.info(f"Action '{action.action_type}' executed via NervousSystem")
            except Exception as e:
                logger.error(f"Action {action.action_type} failed: {e}")
        else:
            logger.warning(f"Unknown action type '{action.action_type}' for NervousSystem mapping")

    def _generate_recommendations(
        self, level: str, score: float
    ) -> List[str]:
        recommendations = []

        if level == "global":
            recommendations.append("Surplus is strong. Consider expanding AI-driven services.")
            recommendations.append("Invest in community infrastructure to maintain high scores.")
            recommendations.append("Publish transparency report to reinforce social trust.")
        elif level == "country":
            recommendations.append("Surplus is adequate. Optimize usage to reach global level.")
            recommendations.append("Monitor community feedback for early warning signs.")
        elif level == "community":
            recommendations.append(
                "Community surplus is declining. Reduce non-essential AI resource consumption."
            )
            recommendations.append("Engage community stakeholders in resource usage decisions.")
            recommendations.append("Invest in local infrastructure to improve community surplus.")
        elif level == "caution":
            recommendations.append("Social permission is at risk. Halt all expansion immediately.")
            recommendations.append("Conduct audit of all AI resource consumption.")
            recommendations.append("Develop restitution plan for affected communities.")
        else:
            recommendations.append("CRITICAL: Social permission deficit detected.")
            recommendations.append("Stop all AI resource consumption immediately.")
            recommendations.append("Publish full transparency report of all AI usage.")
            recommendations.append("Launch community restoration program with measurable targets.")

        return recommendations

    def _save_report(self, report: Dict[str, Any]) -> None:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        path = self.data_dir / f"social_permission_report_{timestamp}.json"
        path.write_text(
            json.dumps(report, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Social permission report saved: {path}")

    def get_history(self) -> List[Dict[str, Any]]:
        return self.history

    def get_current_level(self) -> str:
        if not self.history:
            return "unknown"
        return self.history[-1].get("level", "unknown")

    def get_avg_score(self) -> float:
        if not self.history:
            return 0.0
        scores = [r.get("social_permission_score", 0.0) for r in self.history]
        return sum(scores) / len(scores)

    def generate_community_report(self) -> Dict[str, Any]:
        """Generate a comprehensive community-level surplus report."""
        avg_score = self.get_avg_score()
        current_level = self.get_current_level()
        recommendations = self._generate_recommendations(current_level, avg_score)

        return {
            "social_permission_score": avg_score,
            "current_level": current_level,
            "thresholds": {
                "community_min": THRESHOLDS.community_min,
                "country_min": THRESHOLDS.country_min,
                "global_min": THRESHOLDS.global_min,
                "critical_min": THRESHOLDS.critical_min,
            },
            "total_actions_logged": len(self.action_log),
            "auto_executed_actions": sum(
                1 for a in self.action_log if a.get("auto_execute", False)
            ),
            "recommendations": recommendations,
            "history_count": len(self.history),
            "timestamp": datetime.now().isoformat(),
        }


def create_social_permission_framework(**kwargs) -> SocialPermissionFramework:
    return SocialPermissionFramework(**kwargs)