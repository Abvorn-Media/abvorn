"""specialized_agents.py — Abvorn Specialized Agents.

Dedicated agents for different niche categories with optimized
configurations and prompts.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("abvorn.specialized_agents")


@dataclass
class AgentProfile:
    name: str
    categories: List[str]
    system_prompt: str
    provider_preferences: List[str]
    temperature: float
    max_tokens: int
    tone: str
    expertise: List[str]


class SpecializedAgentFactory:
    def __init__(self):
        self.agent_templates: Dict[str, AgentProfile] = {}
        self._register_default_agents()

    def _register_default_agents(self):
        self.agent_templates["tech_reviewer"] = AgentProfile(
            name="Tech Reviewer",
            categories=["tech", "gadgets", "audio", "computing", "gaming"],
            system_prompt="You are a tech product reviewer with deep expertise in consumer electronics.",
            provider_preferences=["kilo", "groq", "deepseek"],
            temperature=0.7,
            max_tokens=2500,
            tone="technical but accessible",
            expertise=["audio quality", "performance benchmarks", "build quality"],
        )

        self.agent_templates["home_lifestyle"] = AgentProfile(
            name="Home & Lifestyle Expert",
            categories=["home", "furniture", "kitchen", "lifestyle", "outdoor"],
            system_prompt="You are a home and lifestyle product reviewer with a focus on practical usability.",
            provider_preferences=["kilo", "groq"],
            temperature=0.8,
            max_tokens=2000,
            tone="warm and practical",
            expertise=["usability", "durability", "value for money"],
        )

        self.agent_templates["fitness_health"] = AgentProfile(
            name="Fitness & Health Specialist",
            categories=["fitness", "health", "wellness", "nutrition"],
            system_prompt="You are a fitness and health product reviewer with expertise in sports science.",
            provider_preferences=["kilo", "deepseek"],
            temperature=0.6,
            max_tokens=2200,
            tone="motivational and analytical",
            expertise=["performance", "safety", "scientific accuracy"],
        )

        self.agent_templates["finance_business"] = AgentProfile(
            name="Finance & Business Analyst",
            categories=["finance", "business", "investing", "entrepreneurship"],
            system_prompt="You are a finance and business product reviewer with expertise in ROI analysis.",
            provider_preferences=["deepseek", "groq"],
            temperature=0.5,
            max_tokens=3000,
            tone="professional and analytical",
            expertise=["ROI", "cost-benefit", "business efficiency"],
        )

    def get_agent_for_niche(self, niche: str) -> AgentProfile:
        niche_lower = niche.lower()
        for agent in self.agent_templates.values():
            for category in agent.categories:
                if category in niche_lower:
                    return agent
        return self.agent_templates.get("tech_reviewer") or list(self.agent_templates.values())[0]

    def get_prompt_for_agent(
        self, agent: AgentProfile, niche: str, product_data: Dict[str, Any]
    ) -> str:
        return (
            f"{agent.system_prompt}\n\n"
            f"Tone: {agent.tone}.\n\n"
            f"Expertise areas: {', '.join(agent.expertise)}.\n\n"
            f"Niche: {niche}\n"
            f"Product: {product_data.get('name', 'unknown')}\n"
            f"Price: {product_data.get('price', 'unknown')}\n\n"
            f"Provide a detailed, honest review with specific recommendations."
        )

    def list_agents(self) -> Dict[str, str]:
        return {name: profile.name for name, profile in self.agent_templates.items()}