"""Persona discovery — derives buyer personas from niches using brain frameworks."""

import logging, random

logger = logging.getLogger("abvorn.persona")

AWARENESS_LEVELS = ["unaware", "problem_aware", "solution_aware", "product_aware", "most_aware"]
LF8_DESIRES = ["survival", "food_enjoyment", "freedom_from_pain", "companionship",
               "comfortable_living", "superiority", "care_for_loved_ones", "social_approval"]
CIALDINI_PRINCIPLES = ["reciprocity", "scarcity", "authority", "liking",
                        "consistency", "social_proof", "unity"]
HOFFELD_REASONS = ["gain", "avoid", "feel", "conform", "identity", "reduce_uncertainty"]

PERSONA_TEMPLATES = {
    "wireless headphones": [
        {"name": "Marcus the Commuter", "age_range": "25-40",
         "psychology": {"awareness_level": "solution_aware", "primary_lf8_desire": "freedom_from_pain",
                        "anxieties": ["battery dying mid-commute", "missing my stop", "tangled wires"],
                        "hopes": ["peaceful commute", "hear every detail"]}},
        {"name": "Gamer Gary", "age_range": "18-35",
         "psychology": {"awareness_level": "product_aware", "primary_lf8_desire": "superiority",
                        "anxieties": ["lag ruining my game", "mic cutting out"],
                        "hopes": ["hear footsteps first", "win more matches"]}},
        {"name": "Audiophile Amy", "age_range": "30-55",
         "psychology": {"awareness_level": "most_aware", "primary_lf8_desire": "comfortable_living",
                        "anxieties": ["compressed audio", "cheap build quality"],
                        "hopes": ["reference-quality sound", "luxury feel"]}},
    ]
}


class PersonaEngine:
    """Discovers buyer personas for niches using brain psychology frameworks."""

    def discover_personas(self, niche: str) -> list[dict]:
        """Derive 2-5 candidate personas for a niche."""
        niche_lower = niche.lower()
        templates = PERSONA_TEMPLATES.get(niche_lower, [])
        if not templates:
            templates = self._generate_personas(niche)
        for p in templates:
            if "cialdini_principles" not in p.get("psychology", {}):
                p.setdefault("psychology", {})["cialdini_principles"] = random.sample(CIALDINI_PRINCIPLES, 3)
            if "hoffeld_buying_reason" not in p.get("psychology", {}):
                p["psychology"]["hoffeld_buying_reason"] = random.choice(HOFFELD_REASONS)
        logger.info(f"Discovered {len(templates)} personas for '{niche}'")
        return templates

    def _generate_personas(self, niche: str) -> list[dict]:
        """Fallback: generate generic personas for any niche."""
        return [
            {"name": "The First-Time Buyer", "age_range": "20-40",
             "psychology": {"awareness_level": "problem_aware", "primary_lf8_desire": "freedom_from_pain",
                            "anxieties": ["wasting money", "choosing wrong product"],
                            "hopes": ["get it right first time"]}},
            {"name": "The Enthusiast", "age_range": "25-50",
             "psychology": {"awareness_level": "product_aware", "primary_lf8_desire": "superiority",
                            "anxieties": ["missing features", "outdated tech"],
                            "hopes": ["best-in-class experience"]}},
        ]