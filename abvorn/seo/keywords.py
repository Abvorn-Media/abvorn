import logging
import hashlib

logger = logging.getLogger("abvorn.seo.keywords")

_NICHE_KEYWORDS = {
    "wireless headphones": {
        "primary": "best wireless headphones",
        "secondary": ["wireless earbuds", "noise cancelling headphones", "bluetooth headphones", "over ear headphones"],
        "long_tail": [
            "best wireless headphones for commuting",
            "wireless headphones with long battery life",
            "noise cancelling headphones under 200",
            "best bluetooth headphones for running",
            "affordable wireless earbuds for work",
            "over ear headphones for small heads",
            "wireless headphones for tv watching",
            "best budget noise cancelling headphones 2026",
            "wireless earbuds for phone calls",
            "sports headphones that stay in ear",
        ],
    },
    "gaming mouse": {
        "primary": "best gaming mouse",
        "secondary": ["wireless gaming mouse", "ergonomic gaming mouse", "budget gaming mouse", "mmo mouse"],
        "long_tail": [
            "best wireless gaming mouse for fps",
            "lightweight gaming mouse for claw grip",
            "best budget gaming mouse under 50",
            "ergonomic mouse for large hands gaming",
            "wireless gaming mouse no lag",
            "best mmo mouse for world of warcraft",
            "gaming mouse for small hands",
            "best mouse for valorant 2026",
            "vertical gaming mouse for carpal tunnel",
            "cheap gaming mouse with side buttons",
        ],
    },
}

_INTENTS = ["informational", "commercial", "transactional", "navigational"]


def _seed_from_string(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)


def _pseudo_volume(keyword: str, base: int = 1200) -> int:
    h = _seed_from_string(keyword)
    return base + (h % 4800)


def _pseudo_difficulty(keyword: str) -> float:
    h = _seed_from_string(keyword)
    return round(0.15 + (h % 85) / 100, 2)


def _pseudo_intent(keyword: str) -> str:
    h = _seed_from_string(keyword)
    return _INTENTS[h % len(_INTENTS)]


class KeywordResearch:
    def research_keywords(self, niche: str, persona: str = "") -> list[dict]:
        keyword_map = _NICHE_KEYWORDS.get(niche.lower(), {})
        if not keyword_map:
            return self._generate_fallback(niche, persona)

        results = []
        primary = keyword_map["primary"]
        results.append({
            "keyword": primary,
            "volume": _pseudo_volume(primary, 2000),
            "difficulty": _pseudo_difficulty(primary),
            "intent": "commercial",
            "long_tail": self.extract_long_tail(primary),
        })

        for kw in keyword_map["secondary"]:
            results.append({
                "keyword": kw,
                "volume": _pseudo_volume(kw, 800),
                "difficulty": _pseudo_difficulty(kw),
                "intent": _pseudo_intent(kw),
                "long_tail": self.extract_long_tail(kw),
            })

        for kw in keyword_map["long_tail"]:
            results.append({
                "keyword": kw,
                "volume": _pseudo_volume(kw, 100),
                "difficulty": _pseudo_difficulty(kw),
                "intent": "informational",
                "long_tail": [],
            })

        return results

    def _generate_fallback(self, niche: str, persona: str) -> list[dict]:
        results = []
        parts = niche.strip().lower().split()

        base_keyword = niche.lower()
        results.append({
            "keyword": f"best {base_keyword}",
            "volume": _pseudo_volume(base_keyword, 1000),
            "difficulty": _pseudo_difficulty(base_keyword),
            "intent": "commercial",
            "long_tail": self.extract_long_tail(base_keyword),
        })

        for i in range(min(4, len(parts) + 2)):
            kw = " ".join(parts[:i+1]) if parts else niche
            if kw == base_keyword:
                continue
            results.append({
                "keyword": f"{kw} review" if i % 2 == 0 else f"best {kw}",
                "volume": _pseudo_volume(kw, 500),
                "difficulty": _pseudo_difficulty(kw),
                "intent": _INTENTS[i % len(_INTENTS)],
                "long_tail": self.extract_long_tail(kw),
            })

        for i in range(6):
            kw = f"{base_keyword} {'buying guide' if i % 2 == 0 else 'for beginners'}"
            results.append({
                "keyword": kw,
                "volume": _pseudo_volume(kw, 80),
                "difficulty": _pseudo_difficulty(kw),
                "intent": "informational",
                "long_tail": [],
            })

        return results

    def extract_long_tail(self, keyword: str) -> list[str]:
        templates = [
            f"best {keyword} for",
            f"{keyword} vs",
            f"how to choose {keyword}",
            f"is {keyword} worth it",
            f"what to look for in {keyword}",
        ]
        completions = [
            "beginners", "professionals", "budget", "premium",
            "small spaces", "daily use", "travel", "home office",
        ]
        results = []
        for t in templates:
            for c in completions[:2]:
                results.append(f"{t} {c}")
        return results[:6]
