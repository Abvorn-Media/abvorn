"""ContextParser — extracts persuasion context from content + persona."""

import re
from dataclasses import dataclass, field
from .stage import BuyingStage, detect_stage


@dataclass
class PersuasionContext:
    niche: str
    persona_name: str
    buying_stage: BuyingStage
    keywords: list[str] = field(default_factory=list)
    product_intents: list[str] = field(default_factory=list)


class ContextParser:
    """Analyzes article content to produce PersuasionContext."""

    def parse(self, content: dict, persona: dict | None = None) -> PersuasionContext:
        niche = content.get("niche", "") or ""
        persona_name = (persona or {}).get("name", "") or ""
        buying_stage = detect_stage(content)

        text = f"{content.get('title', '')} {content.get('article_html', '')}".lower()
        keywords = self._extract_keywords(text)
        product_intents = self._extract_intents(text)

        return PersuasionContext(
            niche=niche,
            persona_name=persona_name,
            buying_stage=buying_stage,
            keywords=keywords,
            product_intents=product_intents,
        )

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> list[str]:
        words = re.findall(r'\b[a-z]{4,}\b', text)
        stopwords = {"this", "that", "with", "from", "have", "been", "were", "they", "their", "what", "which", "where", "when", "about", "above", "after", "again", "than", "them", "then", "there", "these", "thing", "very", "just", "also", "more", "some", "into", "over", "such", "only", "other", "each", "could", "would", "should"}
        words = [w for w in words if w not in stopwords]
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: -x[1])
        return [w for w, _ in sorted_words[:max_keywords]]

    def _extract_intents(self, text: str) -> list[str]:
        patterns = [
            r'(?:best|top|cheap|affordable|buy|review)\s+([a-z\s]{3,30}?)',
            r'([a-z\s]{3,30}?)\s+(?:review|comparison|vs\.?)',
        ]
        intents = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                cleaned = m.strip()[:40]
                if cleaned and cleaned not in intents:
                    intents.append(cleaned)
        return intents[:3]
