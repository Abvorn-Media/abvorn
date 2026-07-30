#!/usr/bin/env python3
"""
energy_accounting.py — Energy and resource consumption tracking per article and provider.

Implements Nadella's Social Permission Principle: AI must earn societal consent
to consume energy resources by demonstrating measurable economic surplus.
Tracks carbon footprint alongside cost and performance metrics.
"""

import logging
from collections import defaultdict
from typing import Dict, Any

logger = logging.getLogger("energy_accounting")

# Approximate carbon intensity per provider (g CO2 per 1000 tokens)
# Based on typical data center PUE and grid carbon intensity per compute region.
CARBON_INTENSITY = {
    "kilogateway": 0.012,
    "deepseek": 0.015,
    "kimi": 0.018,
    "openai": 0.020,
    "anthropic": 0.018,
    "gemini": 0.014,
    "groq": 0.010,
    "glm": 0.020,
    "local": 0.0,
    "huggingface": 0.015,
}

# Approximate energy per 1000 tokens in kWh (very rough estimate)
ENERGY_PER_1K_TOKENS_KWH = 0.000001

# Average cost per 1000 tokens per provider (for free tier models, cost = 0)
COST_PER_1K_TOKENS = {
    "kilogateway": 0.0,
    "deepseek": 0.002,
    "kimi": 0.003,
    "openai": 0.015,
    "anthropic": 0.018,
    "gemini": 0.001,
    "groq": 0.002,
    "glm": 0.003,
    "local": 0.0,
    "huggingface": 0.001,
}


class EnergyAccounting:
    def __init__(self):
        self.provider_consumption: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"tokens": 0, "energy_kwh": 0.0, "co2_g": 0.0, "cost_usd": 0.0}
        )
        self.total_tokens = 0
        self.total_energy_kwh = 0.0
        self.total_co2_g = 0.0
        self.total_cost_usd = 0.0

    def record_usage(
        self, provider_name: str, tokens: int, latency_ms: float = 0.0
    ):
        carbon = CARBON_INTENSITY.get(provider_name, 0.015)
        energy = tokens * (ENERGY_PER_1K_TOKENS_KWH / 1000.0)
        co2 = tokens * (carbon / 1000.0)
        cost = tokens * (COST_PER_1K_TOKENS.get(provider_name, 0.002) / 1000.0)

        entry = self.provider_consumption[provider_name]
        entry["tokens"] += tokens
        entry["energy_kwh"] += energy
        entry["co2_g"] += co2
        entry["cost_usd"] += cost

        self.total_tokens += tokens
        self.total_energy_kwh += energy
        self.total_co2_g += co2
        self.total_cost_usd += cost

    def get_report(self) -> Dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "total_energy_kwh": round(self.total_energy_kwh, 6),
            "total_co2_g": round(self.total_co2_g, 4),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "carbon_intensity_g_per_1k_tokens": round(
                (self.total_co2_g / max(self.total_tokens, 1)) * 1000, 4
            ),
            "by_provider": {
                name: {
                    "tokens": data["tokens"],
                    "energy_kwh": round(data["energy_kwh"], 6),
                    "co2_g": round(data["co2_g"], 4),
                    "cost_usd": round(data["cost_usd"], 6),
                }
                for name, data in self.provider_consumption.items()
            },
        }

    def get_social_permission_score(self, economic_surplus: float) -> Dict[str, Any]:
        if self.total_cost_usd <= 0:
            return {"score": 1.0, "reason": "zero cost, full permission"}
        return_usd = economic_surplus
        ratio = return_usd / self.total_cost_usd if self.total_cost_usd > 0 else 0
        score = min(ratio / 10, 1.0)
        return {
            "score": round(score, 4),
            "return_per_dollar_usd": round(return_usd / max(self.total_cost_usd, 0.001), 2),
            "co2_g": round(self.total_co2_g, 4),
            "energy_kwh": round(self.total_energy_kwh, 6),
        }


energy_accounting = EnergyAccounting()
