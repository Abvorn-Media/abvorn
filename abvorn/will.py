"""The soul of Abvorn — mission, curiosity, goals, and strategic reflection."""

import logging, random
from datetime import datetime

logger = logging.getLogger("abvorn.will")


class Will:
    """The volitional center. Holds mission, generates goals, adjusts strategy."""

    def __init__(self, state=None, mission=None, bus=None):
        self.mission = mission or (
            "Help people buy with confidence through "
            "honest, researched recommendations"
        )
        self.state = state
        self.bus = bus
        self.curiosity_score = 0.3
        self._cycle_count = 0
        self._last_reflection = None
        self._goals = []

    def set_bus(self, bus):
        self.bus = bus

    def generate_goals(self) -> list[dict]:
        """Generate goals based on mission, state, and curiosity."""
        goals = [
            {"type": "produce_content", "reason": "mission", "priority": 10},
        ]
        if self.curiosity_score > 0.2:
            goals.append({
                "type": "explore_opportunity",
                "reason": "curiosity",
                "priority": int(self.curiosity_score * 10),
            })
        goals.append({
            "type": "optimize_underperformers",
            "reason": "growth",
            "priority": 7,
        })
        self._goals = goals
        if self.bus:
            self.bus.publish("will.goals", {"goals": goals, "curiosity": self.curiosity_score})
        return goals

    def curiosity_pick(self, items: list[dict], score_key: str = "score") -> list[dict]:
        """Mix exploitation (top scorers) with exploration (novel picks)."""
        if not items:
            return []
        sorted_items = sorted(items, key=lambda x: x.get(score_key, 0), reverse=True)
        split = max(1, int(len(sorted_items) * (1 - self.curiosity_score)))
        exploit = sorted_items[:split]
        explore = sorted_items[split:]
        random.shuffle(explore)
        return exploit + explore

    def reflect(self, cycles_completed: int = 1, revenue: float = 0.0,
                engagement: float = 0.0) -> dict:
        """Reflect on performance and adjust strategy."""
        self._cycle_count += cycles_completed
        insights = []

        if revenue > 100 and engagement > 0.05:
            self.curiosity_score = min(1.0, self.curiosity_score + 0.05)
            insights.append("Revenue healthy — increasing exploration")
        elif revenue < 10 and cycles_completed > 5:
            self.curiosity_score = max(0.1, self.curiosity_score - 0.05)
            insights.append("Revenue low — focusing on proven niches")

        self._last_reflection = datetime.now().isoformat()
        reflection = {
            "cycle_count": self._cycle_count,
            "curiosity_score": round(self.curiosity_score, 2),
            "insights": insights,
            "timestamp": self._last_reflection,
        }
        if self.bus:
            self.bus.publish("will.reflection", reflection)
        logger.info(f"Reflection: {insights[-1] if insights else 'steady as she goes'}")
        return reflection

    def mission_check(self, action: str, context: dict = None) -> bool:
        """Check if an action aligns with the mission."""
        action_lower = action.lower()
        positive_signals = ["help", "recommend", "guide", "review",
                           "compare", "best", "honest"]
        if any(s in action_lower for s in positive_signals):
            return True
        negative_signals = ["trick", "scam", "deceive", "clickbait", "fake"]
        if any(s in action_lower for s in negative_signals):
            logger.warning(f"Mission violation blocked: {action}")
            return False
        return True