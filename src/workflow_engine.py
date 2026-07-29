#!/usr/bin/env python3
"""
workflow_engine.py — Adaptive Workflow Engine with A/B Testing

Routes each content cycle through the best-performing workflow variant,
using multi-armed bandit selection to continuously optimize.
"""

import json
import logging
import random
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowType(Enum):
    STANDARD = "standard"
    ACCELERATED = "accelerated"
    QUALITY = "quality"
    EXPERIMENTAL = "experimental"


@dataclass
class WorkflowResult:
    workflow_type: str
    score: float
    engagement_prediction: float
    quality_score: float
    processing_time_ms: float
    content: Dict[str, Any]
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class WorkflowConfig:
    name: str
    description: str
    temperature: float
    max_tokens: int
    style: str
    quality_gate: bool
    use_paradox: bool
    use_quantum: bool
    use_fact_check: bool


WORKFLOW_CONFIGS = {
    WorkflowType.STANDARD: WorkflowConfig(
        name="standard",
        description="Balanced pipeline with quality gate",
        temperature=0.7,
        max_tokens=2000,
        style="balanced",
        quality_gate=True,
        use_paradox=False,
        use_quantum=True,
        use_fact_check=True,
    ),
    WorkflowType.ACCELERATED: WorkflowConfig(
        name="accelerated",
        description="Fast pipeline optimized for speed",
        temperature=0.8,
        max_tokens=1000,
        style="concise",
        quality_gate=False,
        use_paradox=False,
        use_quantum=True,
        use_fact_check=False,
    ),
    WorkflowType.QUALITY: WorkflowConfig(
        name="quality",
        description="Deep pipeline optimized for quality",
        temperature=0.5,
        max_tokens=3000,
        style="detailed",
        quality_gate=True,
        use_paradox=True,
        use_quantum=True,
        use_fact_check=True,
    ),
    WorkflowType.EXPERIMENTAL: WorkflowConfig(
        name="experimental",
        description="Exploratory pipeline with novel techniques",
        temperature=1.0,
        max_tokens=4000,
        style="creative",
        quality_gate=False,
        use_paradox=True,
        use_quantum=True,
        use_fact_check=False,
    ),
}


class PerformanceTracker:
    def __init__(self, data_dir: str = "data/workflows"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history: List[WorkflowResult] = []
        self._load_history()

    def _load_history(self):
        history_file = self.data_dir / "workflow_history.json"
        if history_file.exists():
            try:
                data = json.loads(history_file.read_text(encoding="utf-8"))
                self.history = [WorkflowResult(**r) for r in data]
            except (json.JSONDecodeError, TypeError):
                self.history = []

    def track(self, result: WorkflowResult):
        self.history.append(result)
        self._save()

    def _save(self):
        history_file = self.data_dir / "workflow_history.json"
        data = [
            {
                "workflow_type": r.workflow_type,
                "score": r.score,
                "engagement_prediction": r.engagement_prediction,
                "quality_score": r.quality_score,
                "processing_time_ms": r.processing_time_ms,
                "content": r.content,
                "timestamp": r.timestamp,
            }
            for r in self.history
        ]
        history_file.write_text(
            json.dumps(data, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_stats(self, workflow_type: str = None) -> Dict[str, Any]:
        if workflow_type:
            records = [r for r in self.history if r.workflow_type == workflow_type]
        else:
            records = self.history

        if not records:
            return {"count": 0, "avg_score": 0.0, "best_score": 0.0}

        scores = [r.score for r in records]
        engagement = [r.engagement_prediction for r in records]
        quality = [r.quality_score for r in records]

        return {
            "count": len(records),
            "avg_score": sum(scores) / len(scores),
            "best_score": max(scores),
            "avg_engagement": sum(engagement) / len(engagement),
            "avg_quality": sum(quality) / len(quality),
            "total_runs": len(self.history),
        }


def _multi_arm_bandit_select(
    workflows: Dict[str, WorkflowConfig],
    tracker: PerformanceTracker,
    blog_data: Dict[str, Any],
) -> str:
    """Select workflow using epsilon-greedy multi-armed bandit."""
    epsilon = 0.15

    if random.random() < epsilon:
        return random.choice(list(workflows.keys()))

    stats = {
        wt: tracker.get_stats(wt)
        for wt in workflows.keys()
    }

    best_wf = max(stats, key=lambda k: stats[k].get("avg_score", 0.0))
    return best_wf


def _select_initial_workflow(blog_data: Dict[str, Any]) -> str:
    """Select initial workflow based on content characteristics."""
    content_length = len(str(blog_data)) if blog_data else 0

    if content_length > 5000:
        return WorkflowType.QUALITY.value
    elif content_length < 1000:
        return WorkflowType.ACCELERATED.value
    else:
        return WorkflowType.STANDARD.value


class WorkflowEngine:
    def __init__(self):
        self.workflows = {wt.value: cfg for wt, cfg in WORKFLOW_CONFIGS.items()}
        self.tracker = PerformanceTracker()
        self.current_workflow = WorkflowType.STANDARD.value
        self.results_history: List[WorkflowResult] = []

    def run_cycle(
        self, blog_data: Dict[str, Any], content_generator
    ) -> Dict[str, Any]:
        """Run the best workflow for this content."""
        selected_name = _multi_arm_bandit_select(
            self.workflows, self.tracker, blog_data
        )
        config = self.workflows[selected_name]
        self.current_workflow = selected_name

        logger.info(f"Workflow engine selected: {selected_name} ({config.description})")

        start_time = datetime.now()
        result = content_generator(blog_data, config)
        elapsed = (datetime.now() - start_time).total_seconds() * 1000

        score = self._score_result(result, config)
        engagement = result.get("predicted_engagement", 0.0)
        quality = result.get("quality_score", 0.0)

        wf_result = WorkflowResult(
            workflow_type=selected_name,
            score=score,
            engagement_prediction=engagement,
            quality_score=quality,
            processing_time_ms=elapsed,
            content=result,
        )
        self.tracker.track(wf_result)
        self.results_history.append(wf_result)

        if score < 0.6:
            alternative = _multi_arm_bandit_select(
                {k: v for k, v in self.workflows.items() if k != selected_name},
                self.tracker,
                blog_data,
            )
            if alternative and alternative != selected_name:
                logger.info(
                    f"Low score ({score:.2f}), retrying with {alternative} workflow"
                )
                alt_config = self.workflows[alternative]
                alt_result = content_generator(blog_data, alt_config)
                alt_score = self._score_result(alt_result, alt_config)
                alt_engagement = alt_result.get("predicted_engagement", 0.0)
                alt_quality = alt_result.get("quality_score", 0.0)

                alt_wf_result = WorkflowResult(
                    workflow_type=alternative,
                    score=alt_score,
                    engagement_prediction=alt_engagement,
                    quality_score=alt_quality,
                    processing_time_ms=elapsed,
                    content=alt_result,
                )
                self.tracker.track(alt_wf_result)
                self.results_history.append(alt_wf_result)

                if alt_score > score:
                    return {
                        **alt_result,
                        "workflow_used": alternative,
                        "workflow_retry": True,
                        "original_workflow": selected_name,
                    }

        return {
            **result,
            "workflow_used": selected_name,
            "workflow_retry": False,
            "workflow_score": score,
        }

    def _score_result(self, result: Dict[str, Any], config: WorkflowConfig) -> float:
        score = 0.0

        engagement = result.get("predicted_engagement", 0.0)
        score += engagement * 0.4

        quality = result.get("quality_score", 0.0)
        score += quality * 0.3

        word_count = result.get("word_count", 0)
        if config.style == "detailed" and word_count >= 500:
            score += 0.15
        elif config.style == "balanced" and 200 <= word_count < 800:
            score += 0.15
        elif config.style == "concise" and word_count < 300:
            score += 0.15

        if config.quality_gate and result.get("quality_gate_passed", True):
            score += 0.1
        elif not config.quality_gate:
            score += 0.05

        hooks = result.get("hooks", [])
        if hooks:
            score += 0.05

        return min(score, 1.0)

    def get_stats(self) -> Dict[str, Any]:
        all_stats = {}
        for wf_name in self.workflows:
            all_stats[wf_name] = self.tracker.get_stats(wf_name)
        all_stats["total_runs"] = len(self.results_history)
        all_stats["current_workflow"] = self.current_workflow
        all_stats["all_time_best"] = max(
            (r for r in self.results_history),
            key=lambda r: r.score,
            default=None,
        )
        return all_stats

    def get_workflow_recommendation(self, blog_data: Dict[str, Any]) -> str:
        """Recommend the best workflow for new content without running it."""
        return _multi_arm_bandit_select(
            self.workflows, self.tracker, blog_data
        )


def create_workflow_engine() -> WorkflowEngine:
    return WorkflowEngine()