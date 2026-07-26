import logging
import hashlib

logger = logging.getLogger("abvorn.seo.trends")

_TREND_TEMPLATES = [
    {"topic": "{keyword} buying guide {year}", "growth": "rising", "base_momentum": 0.75},
    {"topic": "best {keyword} for {use_case}", "growth": "rising", "base_momentum": 0.85},
    {"topic": "{keyword} vs {competitor}", "growth": "peaking", "base_momentum": 0.65},
    {"topic": "{keyword} deals {month}", "growth": "peaking", "base_momentum": 0.55},
    {"topic": "budget {keyword} options", "growth": "declining", "base_momentum": 0.35},
    {"topic": "premium {keyword} recommendations", "growth": "rising", "base_momentum": 0.70},
]

_USE_CASES = [
    "everyday use", "professional work", "travel", "home office",
    "gaming", "fitness", "outdoor adventures", "remote work",
]

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_COMPETITORS = [
    "alternatives", "top brands compared", "Sony vs Bose",
    "Apple vs Samsung", "budget vs premium",
]

_RELATED_QUERIES = [
    "how to choose {keyword}",
    "are {keyword} worth it",
    "{keyword} reviews 2026",
    "where to buy {keyword}",
    "{keyword} for beginners",
]


def _hash_seed(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)


class TrendDiscovery:
    def discover_trends(self, base_keywords: list[str]) -> list[dict]:
        results = []
        from datetime import datetime
        year = datetime.now().year
        month = _MONTHS[datetime.now().month - 1]

        for kw in base_keywords:
            for template in _TREND_TEMPLATES:
                use_case = _USE_CASES[_hash_seed(kw + template["topic"]) % len(_USE_CASES)]
                competitor = _COMPETITORS[_hash_seed(kw) % len(_COMPETITORS)]

                topic = template["topic"].format(
                    keyword=kw,
                    year=year,
                    month=month,
                    use_case=use_case,
                    competitor=competitor,
                ).lower()

                h = _hash_seed(topic)
                momentum = round(min(template["base_momentum"] + (h % 20) / 100, 1.0), 2)

                related = [
                    q.format(keyword=kw)
                    for q in _RELATED_QUERIES
                ]

                results.append({
                    "topic": topic,
                    "growth_rate": template["growth"],
                    "momentum_score": momentum,
                    "related_queries": related,
                })

        return results[:len(base_keywords) * 3]

    def calculate_opportunity_score(self, trend: dict) -> float:
        momentum = trend.get("momentum_score", 0.0)
        growth = trend.get("growth_rate", "declining")

        growth_bonus = {"rising": 0.3, "peaking": 0.15, "declining": 0.0}.get(growth, 0.0)
        score = (momentum * 0.7 + growth_bonus) * 100
        return round(min(score, 100.0), 1)
