"""meta_evolution.py — Abvorn Meta-Evolution Engine.

The system evolves itself by spawning child instances,
evaluating their performance, and selecting the best.
"""
import random
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging

from src.instance_spawner import InstanceSpawner, InstanceConfig, InstanceResult

logger = logging.getLogger("abvorn.meta_evolution")

ALL_PROVIDERS = ["kilo", "groq", "deepseek", "openai", "glm", "local"]
ALL_WORKFLOWS = ["standard", "accelerated", "quality", "experimental"]


@dataclass
class Generation:
    number: int
    instance_results: Dict[str, InstanceResult]
    best_instance_id: Optional[str] = None
    average_engagement: float = 0.0
    best_engagement: float = 0.0


class MetaEvolutionEngine:
    def __init__(self, base_config: Dict[str, Any]):
        self.base_config = base_config
        self.generations: List[Generation] = []
        self.current_best_config = base_config.copy()
        self.population_size = 4
        self.mutation_rate = 0.3
        self.spawner: Optional[InstanceSpawner] = None

    def _mutate_providers(self, current: List[str]) -> List[str]:
        mutated = list(current)
        all_providers = [p for p in ALL_PROVIDERS if p not in mutated]
        if random.random() < 0.4 and mutated:
            mutated.pop(random.randrange(len(mutated)))
        if random.random() < 0.4 and all_providers:
            mutated.append(random.choice(all_providers))
        return mutated if mutated else ["kilo"]

    def _mutate_workflow(self) -> str:
        return random.choice(ALL_WORKFLOWS)

    def _mutate_temperature(self, current: float) -> float:
        return max(0.1, min(1.0, current + random.uniform(-0.3, 0.3)))

    def _mutate_max_tokens(self, current: int) -> int:
        return max(500, min(4000, current + random.randint(-500, 500)))

    def _create_variations(self, count: int) -> List[Dict[str, Any]]:
        variations = []
        base = self.current_best_config

        for _ in range(count):
            variation = base.copy()

            if random.random() < self.mutation_rate:
                variation["provider_preferences"] = self._mutate_providers(
                    variation.get("provider_preferences", ["kilo"])
                )

            if random.random() < self.mutation_rate:
                variation["workflow_name"] = self._mutate_workflow()

            if random.random() < self.mutation_rate:
                variation["temperature"] = self._mutate_temperature(
                    variation.get("temperature", 0.7)
                )

            if random.random() < self.mutation_rate:
                variation["max_tokens"] = self._mutate_max_tokens(
                    variation.get("max_tokens", 2000)
                )

            variations.append(variation)

        return variations

    def _extract_best_config(self, best_result: InstanceResult) -> Dict[str, Any]:
        meta = best_result.metadata or {}
        config = self.current_best_config.copy()
        config.update({
            k: v for k, v in meta.items()
            if k in InstanceConfig.__dataclass_fields__
        })
        return config

    def evolve(self, niches: List[Dict]) -> Dict[str, Any]:
        generation_number = len(self.generations) + 1
        logger.info(f"Generation {generation_number}: evolving {len(niches)} niches")

        if self.spawner is None:
            self.spawner = InstanceSpawner(self.base_config)

        variations = self._create_variations(self.population_size)

        for i, variation in enumerate(variations):
            name = f"Gen{generation_number}_V{i + 1}"
            self.spawner.create_instance(name, variation)

        results = self.spawner.spawn_all(niches)

        best_id = self.spawner.get_best_instance()
        best_result = results.get(best_id) if best_id else None

        average_engagement = (
            sum(r.engagement_score for r in results.values() if r.success)
            / max(sum(1 for r in results.values() if r.success), 1)
        )
        best_engagement = best_result.engagement_score if best_result and best_result.success else 0.0

        generation = Generation(
            number=generation_number,
            instance_results=results,
            best_instance_id=best_id,
            average_engagement=average_engagement,
            best_engagement=best_engagement,
        )
        self.generations.append(generation)

        if best_result and best_result.success:
            self.current_best_config = self._extract_best_config(best_result)

        logger.info(
            f"Generation {generation_number} complete — "
            f"best: {best_id} (engagement: {best_engagement:.2f}), "
            f"avg: {average_engagement:.2f}"
        )

        return {
            "generation": generation_number,
            "best_id": best_id,
            "best_engagement": best_engagement,
            "average_engagement": average_engagement,
            "population_size": len(results),
        }

    def run_evolution(self, niches: List[Dict], generations: int = 3) -> Dict[str, Any]:
        for gen in range(generations):
            self.evolve(niches)

        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        return {
            "total_generations": len(self.generations),
            "best_engagement": max(
                (g.best_engagement for g in self.generations), default=0.0
            ),
            "current_best_config": self.current_best_config,
            "generations": [
                {
                    "number": g.number,
                    "best_id": g.best_instance_id,
                    "average_engagement": g.average_engagement,
                    "best_engagement": g.best_engagement,
                }
                for g in self.generations
            ],
            "report": self.spawner.generate_report() if self.spawner else {},
        }