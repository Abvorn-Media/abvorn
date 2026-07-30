"""evolution_runner.py — Abvorn Full Evolution Runner.

Orchestrates the complete evolution cycle:
1. Specialized agent selection
2. Instance spawning
3. Meta-evolution
4. Reporting
"""

import json
import logging
from typing import Dict, Any, List

from src.instance_spawner import InstanceSpawner, InstanceConfig
from src.meta_evolution import MetaEvolutionEngine
from src.specialized_agents import SpecializedAgentFactory

logger = logging.getLogger("abvorn.evolution_runner")

logging.basicConfig(level=logging.INFO)


def run_evolution_cycle(niches: List[Dict]) -> Dict[str, Any]:
    logger.info("Starting full evolution cycle")

    agent_factory = SpecializedAgentFactory()
    niche_agents = {}
    for niche in niches:
        agent = agent_factory.get_agent_for_niche(niche["slug"])
        niche_agents[niche["slug"]] = agent.name
        logger.info(f"{niche['slug']} -> {agent.name}")

    base_config = {
        "provider_preferences": ["kilo", "groq", "deepseek"],
        "workflow_name": "parallel",
        "max_workers": 4,
        "temperature": 0.7,
        "max_tokens": 2000,
        "quality_checks": True,
        "use_knowledge_core": True,
        "use_feedback_loop": True,
    }

    evolution_engine = MetaEvolutionEngine(base_config)

    for gen in range(3):
        result = evolution_engine.evolve(niches)
        logger.info(f"Generation {gen + 1} complete: {result['best_engagement']:.2f}")

    report = evolution_engine.generate_report()

    return {
        "niche_agents": niche_agents,
        "final_report": report,
        "best_config": evolution_engine.current_best_config,
    }


if __name__ == "__main__":
    test_niches = [
        {"slug": "wireless-headphones"},
        {"slug": "fitness-trackers"},
        {"slug": "gaming-mice"},
        {"slug": "mechanical-keyboards"},
    ]

    result = run_evolution_cycle(test_niches)
    print(json.dumps(result, indent=2))