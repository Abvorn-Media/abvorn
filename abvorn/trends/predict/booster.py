"""ScoreBooster — boosts TrendScanner product scores based on velocity signals."""

import logging

logger = logging.getLogger("abvorn.trends.predict.booster")

BOOST_FREQUENCY_2 = 10
BOOST_FREQUENCY_4 = 20
BOOST_SOURCES_2 = 15
BOOST_NOVELTY = 5
BOOST_CAP = 30


class ScoreBooster:
    """Adjusts product scores based on velocity data from snapshot history."""

    def boost(self, products: list[dict], velocity: dict) -> list[dict]:
        """Return products with scores boosted by velocity signals."""
        boosted = []
        for p in products:
            p = dict(p)
            key = p["product_name"].lower().strip()
            v = velocity.get(key, {})
            if not v:
                boosted.append(p)
                continue

            bonus = 0
            freq = v.get("frequency", 0)
            if freq >= 4:
                bonus += BOOST_FREQUENCY_4
            elif freq >= 2:
                bonus += BOOST_FREQUENCY_2

            if v.get("sources", 0) >= 2:
                bonus += BOOST_SOURCES_2

            if v.get("new", False):
                bonus += BOOST_NOVELTY

            p["score"] = p.get("score", 50) + min(bonus, BOOST_CAP)
            p["velocity_bonus"] = min(bonus, BOOST_CAP)
            boosted.append(p)

        return boosted