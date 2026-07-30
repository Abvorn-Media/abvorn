"""instance_spawner.py — Abvorn Instance Spawning System.

Spawns multiple system instances with different configurations
to find the optimal setup through parallel experimentation.
"""
import os
import sys
import json
import time
import concurrent.futures
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger("abvorn.instance_spawner")


@dataclass
class InstanceConfig:
    instance_id: str
    name: str
    provider_preferences: List[str] = field(default_factory=lambda: ["kilo"])
    workflow_name: str = "standard"
    max_workers: int = 1
    temperature: float = 0.7
    max_tokens: int = 2000
    quality_checks: bool = False
    use_knowledge_core: bool = False
    use_feedback_loop: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstanceResult:
    instance_id: str
    success: bool
    niches_processed: int = 0
    articles_generated: int = 0
    total_duration: float = 0.0
    cost: float = 0.0
    engagement_score: float = 0.0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class InstanceSpawner:
    def __init__(self, base_config: Dict[str, Any]):
        self.base_config = base_config
        self.instances: Dict[str, InstanceConfig] = {}
        self.results: Dict[str, InstanceResult] = {}
        self.workspace = Path("instances")
        self.workspace.mkdir(exist_ok=True)

    def create_instance(self, name: str, config_overrides: Dict[str, Any]) -> str:
        instance_id = f"inst_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.instances) + 1}"
        merged = {**self.base_config, **config_overrides}
        merged["name"] = name
        merged["instance_id"] = instance_id

        try:
            instance = InstanceConfig(**merged)
        except TypeError:
            instance = InstanceConfig(
                instance_id=instance_id,
                name=name,
                provider_preferences=merged.get("provider_preferences", ["kilo"]),
                workflow_name=merged.get("workflow_name", "standard"),
                max_workers=merged.get("max_workers", 1),
                temperature=merged.get("temperature", 0.7),
                max_tokens=merged.get("max_tokens", 2000),
                quality_checks=merged.get("quality_checks", False),
                use_knowledge_core=merged.get("use_knowledge_core", False),
                use_feedback_loop=merged.get("use_feedback_loop", True),
                metadata=merged.get("metadata", {}),
            )
        self.instances[instance_id] = instance
        config_path = self.workspace / f"{instance_id}_config.json"
        config_path.write_text(json.dumps(asdict(instance), indent=2), encoding="utf-8")
        logger.info(f"Instance created: {instance_id} ({name})")
        return instance_id

    def spawn_all(self, niches: List[Dict]) -> Dict[str, InstanceResult]:
        if not self.instances:
            logger.warning("No instances to spawn")
            return {}
        logger.info(f"Spawning {len(self.instances)} instances")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.instances)) as executor:
            futures = {
                executor.submit(self._run_instance, instance_id, instance, niches): instance_id
                for instance_id, instance in self.instances.items()
            }
            for future in concurrent.futures.as_completed(futures):
                iid = futures[future]
                try:
                    result = future.result(timeout=1800)
                    self.results[iid] = result
                    logger.info(
                        f"Instance {iid}: {result.articles_generated} articles, "
                        f"{result.total_duration:.1f}s, engagement={result.engagement_score:.2f}"
                    )
                except Exception as e:
                    logger.error(f"Instance {iid} failed: {e}")
                    self.results[iid] = InstanceResult(
                        instance_id=iid, success=False, errors=[str(e)]
                    )
        return self.results

    def _run_instance(
        self, instance_id: str, config: InstanceConfig, niches: List[Dict]
    ) -> InstanceResult:
        start = time.time()
        try:
            from run_cycle import (
                get_secrets, load_state, pick_niche, save_state,
                write_files, research_products, generate_outline, write_draft,
            )
            from src.ai_sql import create_ai_sql, QueryPlan
            from src.change_management import create_change_manager, ChangeType, ChangeStatus
            from src.infrastructure import infra_reporter
            from src.energy_accounting import energy_accounting

            ai_sql = create_ai_sql()
            change_mgr = create_change_manager()
            change_id = change_mgr.create_change(
                name=f"{instance_id}_cycle",
                change_type=ChangeType.PIPELINE,
                description=f"Instance {instance_id} run",
            )
            articles_count = 0
            total_cost = 0.0
            for niche in niches:
                niche_slug = niche.get("slug", "unknown")
                products = research_products(niche_slug)
                if not products:
                    continue
                outline = generate_outline(niche_slug, products)
                if not outline:
                    continue
                draft = write_draft(niche_slug, products, outline)
                if not draft:
                    continue
                state = load_state()
                articles = {niche_slug: [draft]}
                write_files(
                    niche_slug, articles, state,
                    pexels_key=get_secrets().get("PEXELS_KEY", ""),
                    amazon_tag=get_secrets().get("AMAZON_TAG", "viraltestco-20"),
                )
                niche["posts"] = niche.get("posts", 0) + 1
                save_state(state)
                articles_count += 1
            change_mgr.promote_change(change_id, ChangeStatus.PRODUCTION)
            duration = time.time() - start
            return InstanceResult(
                instance_id=instance_id,
                success=True,
                niches_processed=len(niches),
                articles_generated=articles_count,
                total_duration=duration,
                cost=total_cost,
                engagement_score=min(articles_count / max(len(niches), 1), 1.0),
            )
        except Exception as e:
            duration = time.time() - start
            return InstanceResult(
                instance_id=instance_id, success=False,
                total_duration=duration, errors=[str(e)],
            )

    def get_best_instance(self) -> Optional[str]:
        if not self.results:
            return None
        successful = {k: v for k, v in self.results.items() if v.success}
        if not successful:
            return None
        return max(successful, key=lambda x: successful[x].engagement_score)

    def generate_report(self) -> Dict[str, Any]:
        return {
            "total_instances": len(self.instances),
            "completed": sum(1 for r in self.results.values() if r.success),
            "best_instance": self.get_best_instance(),
            "results": {
                iid: {
                    "success": r.success,
                    "articles": r.articles_generated,
                    "duration": r.total_duration,
                    "engagement": r.engagement_score,
                    "cost": r.cost,
                    "errors": r.errors,
                }
                for iid, r in self.results.items()
            },
        }