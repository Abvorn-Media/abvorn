#!/usr/bin/env python3
"""
paradox_engine.py — The Abvorn Paradox Engine

Identifies the unexpected contradictions and counterintuitive
insights within product data that make the most compelling content.
"""

import logging
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ParadoxEngine:
    def __init__(self, knowledge_core=None):
        self.knowledge_core = knowledge_core
        self.paradox_cache = {}

        self.paradox_patterns = [
            {
                "name": "price_quality_inversion",
                "description": "Lower-priced products outperform higher-priced ones in key metrics",
                "trigger": lambda p: p.get("price", 0) < 100
                and p.get("verdict", {}).get("overall", 0) >= 8.0,
            },
            {
                "name": "feature_overload",
                "description": "Products with more features score lower due to complexity",
                "trigger": lambda p: len(p.get("features", [])) > 10
                and p.get("verdict", {}).get("overall", 0) < 7.0,
            },
            {
                "name": "review_count_myth",
                "description": "High review counts don't correlate with high scores",
                "trigger": lambda p: p.get("review_count", 0) > 5000
                and p.get("verdict", {}).get("overall", 0) < 6.0,
            },
            {
                "name": "best_category_worst_overall",
                "description": "Product excels in one category but fails overall",
                "trigger": lambda p: any(
                    v >= 9.0 for v in p.get("verdict", {}).get("breakdown", {}).values()
                )
                and p.get("verdict", {}).get("overall", 0) < 6.0,
            },
            {
                "name": "budget_hidden_champion",
                "description": "A budget product beats premium options in user satisfaction",
                "trigger": lambda p: p.get("price", 0) < 50
                and p.get("verdict", {}).get("overall", 0) >= 7.5,
            },
            {
                "name": "new_versus_proven",
                "description": "Newer products with fewer reviews outperform established ones",
                "trigger": lambda p: p.get("review_count", 0) < 500
                and p.get("verdict", {}).get("overall", 0) >= 8.5,
            },
        ]

    def generate_paradox_content(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        paradoxes = self._detect_paradoxes(product_data)
        if not paradoxes:
            return self._generate_standard_content(product_data)

        primary_paradox = paradoxes[0]
        hook = self._generate_paradox_hook(primary_paradox, product_data)
        body = self._generate_paradox_body(primary_paradox, product_data, paradoxes)
        conclusion = self._generate_paradox_conclusion(primary_paradox, product_data)

        return {
            "hook": hook,
            "body": body,
            "conclusion": conclusion,
            "paradoxes_detected": len(paradoxes),
            "primary_paradox": primary_paradox["name"],
            "all_paradoxes": [p["name"] for p in paradoxes],
        }

    def _detect_paradoxes(self, product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        detected = []
        for pattern in self.paradox_patterns:
            try:
                if pattern["trigger"](product_data):
                    detected.append({
                        "name": pattern["name"],
                        "description": pattern["description"],
                        "product": product_data.get("product_name", "Unknown"),
                    })
            except Exception:
                pass
        return detected

    def _generate_paradox_hook(self, paradox: Dict[str, Any], product_data: Dict[str, Any]) -> str:
        name = product_data.get("product_name", "This product")
        pattern = paradox["name"]

        hooks = {
            "price_quality_inversion": f"Why {name} beats products 3x its price",
            "feature_overload": f"More features doesn't mean better — the {name} proof",
            "review_count_myth": f"With 5000+ reviews, {name} still surprises us",
            "best_category_worst_overall": f"{name} dominates one category but fails overall — here's why",
            "budget_hidden_champion": f"The {name} under ${product_data.get('price', 0)} outperforms everything",
            "new_versus_proven": f"New and unproven, but {name} already beats the classics",
        }
        return hooks.get(pattern, f"The surprising truth about {name}")

    def _generate_paradox_body(
        self,
        paradox: Dict[str, Any],
        product_data: Dict[str, Any],
        all_paradoxes: List[Dict[str, Any]],
    ) -> str:
        name = product_data.get("product_name", "This product")
        overall = product_data.get("verdict", {}).get("overall", 0)
        breakdown = product_data.get("verdict", {}).get("breakdown", {})

        body_parts = [f"Here's the paradox with {name}:"]
        body_parts.append(f"Overall score: {overall}/10, but the story is more complex.")

        if breakdown:
            best_cat = max(breakdown, key=breakdown.get)
            worst_cat = min(breakdown, key=breakdown.get)
            body_parts.append(
                f"It scores {breakdown[best_cat]:.1f} in {best_cat} "
                f"but only {breakdown[worst_cat]:.1f} in {worst_cat}."
            )

        body_parts.append(f"Paradox detected: {paradox['description']}")

        if len(all_paradoxes) > 1:
            body_parts.append(
                f"Additional patterns: {', '.join(p['name'] for p in all_paradoxes[1:])}"
            )

        return " ".join(body_parts)

    def _generate_paradox_conclusion(
        self, paradox: Dict[str, Any], product_data: Dict[str, Any]
    ) -> str:
        name = product_data.get("product_name", "this product")
        return (
            f"The takeaway: {name} proves that conventional metrics don't tell the whole story. "
            f"Look beyond the score to understand what this product truly delivers."
        )

    def _generate_standard_content(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        name = product_data.get("product_name", "This product")
        overall = product_data.get("verdict", {}).get("overall", 0)
        return {
            "hook": f"The honest breakdown of {name}",
            "body": f"{name} scores {overall}/10. Here's what we found.",
            "conclusion": f"Our verdict on {name}: solid performance with room to grow.",
            "paradoxes_detected": 0,
            "primary_paradox": None,
            "all_paradoxes": [],
        }


def create_paradox_engine(knowledge_core=None) -> ParadoxEngine:
    return ParadoxEngine(knowledge_core=knowledge_core)


if __name__ == "__main__":
    engine = create_paradox_engine()

    product_data = {
        "product_name": "Budget Headphones X",
        "price": 39.99,
        "verdict": {"overall": 8.2, "breakdown": {"sound": 9.1, "comfort": 6.0}},
        "features": ["Bluetooth 5.0", "ANC", "30h battery", "USB-C", "App support"],
        "review_count": 12000,
    }

    result = engine.generate_paradox_content(product_data)
    print(f"Hook: {result['hook']}")
    print(f"Body: {result['body'][:100]}...")
    print(f"Conclusion: {result['conclusion']}")
    print(f"Paradoxes detected: {result['paradoxes_detected']}")