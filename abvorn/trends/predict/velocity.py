"""VelocityTracker — computes product velocity from snapshot history."""

import json, logging

logger = logging.getLogger("abvorn.trends.predict.velocity")

LOOKBACK = 5
SIGNAL_PREFIX = "trend_signal:"
SOURCES = ("duckduckgo", "amazon", "reddit", "googletrends")


class VelocityTracker:
    """Analyzes snapshot history to compute frequency and novelty per product."""

    def get_velocity(self, niche: str, state) -> dict:
        """Return dict of product_name -> {frequency, sources, new}."""
        velocity = {}

        for source in SOURCES:
            key = f"{SIGNAL_PREFIX}{niche}:{source}"
            try:
                raw = state.get_meta(key, "[]")
                history = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                continue

            recent = history[-LOOKBACK:]
            for snap in recent:
                for name in snap.get("products", []):
                    key_name = name.lower().strip()
                    if key_name not in velocity:
                        velocity[key_name] = {"frequency": 0, "sources": set()}
                    velocity[key_name]["frequency"] += 1
                    velocity[key_name]["sources"].add(source)

        for name, v in velocity.items():
            v["sources"] = len(v["sources"])
            v["frequency"] = min(v["frequency"], LOOKBACK)
            v["new"] = v["frequency"] == 1

        return velocity