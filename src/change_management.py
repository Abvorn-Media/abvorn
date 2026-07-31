import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("change_management")


class ChangeStatus(Enum):
    DRAFT = "draft"
    STAGING = "staging"
    CANARY = "canary"
    PRODUCTION = "production"
    ROLLED_BACK = "rolled_back"
    DEPRECATED = "deprecated"


class ChangeType(Enum):
    FEATURE = "feature"
    WORKFLOW = "workflow"
    PROMPT = "prompt"
    PROVIDER = "provider"
    PIPELINE = "pipeline"


@dataclass
class Change:
    id: str
    name: str
    type: ChangeType
    description: str
    status: ChangeStatus
    created_at: datetime
    updated_at: datetime
    deployed_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    rollback_strategy: Optional[str] = None
    success_rate: float = 0.0
    observations: int = 0


@dataclass
class WorkflowVersion:
    id: str
    name: str
    version: str
    pipeline_config: Dict[str, Any]
    status: ChangeStatus
    created_at: datetime
    deployed_at: Optional[datetime] = None


class ChangeManager:
    def __init__(self):
        self.changes: Dict[str, Change] = {}
        self.workflow_versions: Dict[str, List[WorkflowVersion]] = defaultdict(list)
        self.feature_flags: Dict[str, bool] = {}
        self.onboarding_templates: Dict[str, Dict] = {}
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self._ab_results: List[Dict[str, Any]] = []

    def create_change(self, name: str, change_type: ChangeType, description: str) -> Change:
        change_id = f"change_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(name.encode()).hexdigest()[:8]}"
        change = Change(
            id=change_id,
            name=name,
            type=change_type,
            description=description,
            status=ChangeStatus.DRAFT,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self.changes[change_id] = change
        logger.info(f"Change created: {change_id}")
        return change_id

    def promote_change(self, change_id: str, target_status: ChangeStatus) -> bool:
        if change_id not in self.changes:
            logger.error(f"Change {change_id} not found")
            return False
        change = self.changes[change_id]
        valid_paths = {
            ChangeStatus.DRAFT: [ChangeStatus.STAGING],
            ChangeStatus.STAGING: [ChangeStatus.CANARY, ChangeStatus.ROLLED_BACK],
            ChangeStatus.CANARY: [ChangeStatus.PRODUCTION, ChangeStatus.ROLLED_BACK],
            ChangeStatus.PRODUCTION: [ChangeStatus.ROLLED_BACK, ChangeStatus.DEPRECATED],
        }
        if target_status not in valid_paths.get(change.status, []):
            logger.error(f"Invalid promotion: {change.status} -> {target_status}")
            return False
        change.status = target_status
        change.updated_at = datetime.now()
        if target_status == ChangeStatus.PRODUCTION:
            change.deployed_at = datetime.now()
        logger.info(f"Change {change_id} promoted to {target_status}")
        return True

    def rollback_change(self, change_id: str, reason: str) -> bool:
        if change_id not in self.changes:
            logger.error(f"Change {change_id} not found")
            return False
        change = self.changes[change_id]
        change.status = ChangeStatus.ROLLED_BACK
        change.rolled_back_at = datetime.now()
        change.metadata["rollback_reason"] = reason
        logger.info(f"Change {change_id} rolled back: {reason}")
        return True

    def set_feature_flag(self, flag_name: str, enabled: bool) -> None:
        self.feature_flags[flag_name] = enabled
        logger.info(f"Feature flag {flag_name} set to {enabled}")

    def is_feature_enabled(self, flag_name: str) -> bool:
        return self.feature_flags.get(flag_name, False)

    def register_workflow_version(self, workflow_name: str, config: Dict[str, Any], version: str = None) -> WorkflowVersion:
        if version is None:
            version = f"v{len(self.workflow_versions[workflow_name]) + 1}.0"
        workflow = WorkflowVersion(
            id=f"{workflow_name}_{version}",
            name=workflow_name,
            version=version,
            pipeline_config=config,
            status=ChangeStatus.STAGING,
            created_at=datetime.now(),
        )
        self.workflow_versions[workflow_name].append(workflow)
        logger.info(f"Workflow version registered: {workflow.id}")
        return workflow

    def deploy_workflow_version(self, workflow_name: str, version: str) -> bool:
        for wf in self.workflow_versions.get(workflow_name, []):
            if wf.version == version:
                wf.status = ChangeStatus.PRODUCTION
                wf.deployed_at = datetime.now()
                logger.info(f"Workflow {workflow_name} version {version} deployed")
                return True
        logger.error(f"Workflow version {version} not found")
        return False

    def run_ab_test(self, test_name: str, variant_a: Callable, variant_b: Callable,
                    sample_size: int = 100, metric: str = "success") -> Dict[str, Any]:
        results = {
            "test_name": test_name,
            "metric": metric,
            "variant_a": {"successes": 0, "failures": 0, "scores": []},
            "variant_b": {"successes": 0, "failures": 0, "scores": []},
            "winner": None,
            "confidence": 0.0,
            "p_value": None,
            "significant": False,
            "statistical_test": None,
        }
        for i in range(sample_size):
            if i < sample_size // 2:
                try:
                    result = variant_a()
                    results["variant_a"]["successes"] += 1
                    if isinstance(result, dict) and metric in result:
                        results["variant_a"]["scores"].append(result[metric])
                except Exception:
                    results["variant_a"]["failures"] += 1
            else:
                try:
                    result = variant_b()
                    results["variant_b"]["successes"] += 1
                    if isinstance(result, dict) and metric in result:
                        results["variant_b"]["scores"].append(result[metric])
                except Exception:
                    results["variant_b"]["failures"] += 1

        a_total = results["variant_a"]["successes"] + results["variant_a"]["failures"]
        b_total = results["variant_b"]["successes"] + results["variant_b"]["failures"]
        a_rate = results["variant_a"]["successes"] / max(a_total, 1)
        b_rate = results["variant_b"]["successes"] / max(b_total, 1)

        results["winner"] = "A" if a_rate > b_rate else "B" if b_rate > a_rate else "TIE"
        results["confidence"] = abs(a_rate - b_rate) / max(a_rate + b_rate, 0.001)

        # Statistical significance testing
        try:
            if results["variant_a"]["scores"] and results["variant_b"]["scores"]:
                n_a = len(results["variant_a"]["scores"])
                n_b = len(results["variant_b"]["scores"])
                mean_a = sum(results["variant_a"]["scores"]) / n_a
                mean_b = sum(results["variant_b"]["scores"]) / n_b
                var_a = sum((x - mean_a) ** 2 for x in results["variant_a"]["scores"]) / max(n_a - 1, 1)
                var_b = sum((x - mean_b) ** 2 for x in results["variant_b"]["scores"]) / max(n_b - 1, 1)
                pooled_se = ((var_a / n_a) + (var_b / n_b)) ** 0.5
                if pooled_se > 0:
                    t_stat = (mean_a - mean_b) / pooled_se
                    df = n_a + n_b - 2
                    p_value = self._t_test_p_value(t_stat, df)
                    results["p_value"] = p_value
                    results["statistical_test"] = {"t_stat": t_stat, "df": df, "p_value": p_value}
                    results["significant"] = p_value < 0.05
        except Exception:
            results["statistical_test"] = {"test": "approx_ci", "p_value": None}

        self._ab_results.append(results)
        return results

    def _t_test_p_value(self, t_stat: float, df: int) -> float:
        """Approximate p-value for t-statistic using normal distribution (large sample)."""
        import math
        abs_t = abs(t_stat)
        if abs_t > 5:
            return 0.0
        # Normal approximation for t-distribution (acceptable for df > 30)
        # Two-tailed p-value
        z = abs_t
        p = 2 * (1 - self._norm_cdf(z))
        return min(max(p, 0.0), 1.0)

    def _norm_cdf(self, x: float) -> float:
        """Standard normal CDF approximation."""
        import math
        a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
        p = 0.3275911
        sign = 1 if x >= 0 else -1
        x = abs(x) / math.sqrt(2)
        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
        return 0.5 * (1.0 + sign * y)

    def create_onboarding_template(self, name: str, steps: List[Dict[str, Any]]) -> None:
        self.onboarding_templates[name] = {
            "steps": steps,
            "created_at": datetime.now().isoformat(),
        }

    def get_onboarding_workflow(self, template_name: str) -> Optional[List[Dict[str, Any]]]:
        if template_name in self.onboarding_templates:
            return self.onboarding_templates[template_name]["steps"]
        return None

    def generate_report(self) -> Dict[str, Any]:
        return {
            "total_changes": len(self.changes),
            "changes_by_status": {
                status.value: len([c for c in self.changes.values() if c.status == status])
                for status in ChangeStatus
            },
            "feature_flags": self.feature_flags,
            "workflow_versions": {
                name: [wf.version for wf in versions]
                for name, versions in self.workflow_versions.items()
            },
            "onboarding_templates": list(self.onboarding_templates.keys()),
        }


def create_change_manager() -> ChangeManager:
    return ChangeManager()
