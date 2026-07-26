"""Specificity booster — detects vague claims and suggests concrete replacements."""

import re, logging

logger = logging.getLogger("abvorn.humanize.specificity")

_VAGUE_PATTERNS = {
    "very_adj": (re.compile(r'\bvery\s+(good|great|bad|poor|nice|helpful|useful|popular|easy|hard|fast|slow|large|small|expensive|cheap)\b', re.IGNORECASE),
                 "Replace 'very {adj}' with a specific measurement or fact"),
    "extremely_adj": (re.compile(r'\bextremely\s+(good|great|bad|poor|nice|helpful|useful|popular|easy|hard|fast|slow|large|small|expensive|cheap)\b', re.IGNORECASE),
                      "Replace 'extremely {adj}' with a specific measurement"),
    "vague_quantity": (re.compile(r'\ba\s+(lot|little|bit|bunch|ton|heap|load)\s+of\b', re.IGNORECASE),
                       "Use a specific number or quantity"),
    "vague_people": (re.compile(r'\b(many|most|some|a\s+lot\s+of)\s+(people|users|customers|reviewers|shoppers)\b', re.IGNORECASE),
                     "Be specific or cite a source"),
    "vague_price_positive": (re.compile(r'\b(affordable|budget.friendly|reasonably\s+priced|great\s+value)\b', re.IGNORECASE),
                              "Add a specific price reference"),
    "vague_quality": (re.compile(r'\b(high.quality|top.quality|premium\s+quality|superior\s+quality)\b', re.IGNORECASE),
                      "Specify what makes it high quality"),
    "vague_rating": (re.compile(r'\b(top.rated|best.selling|best.known|popular|well.known)\b', re.IGNORECASE),
                     "Cite the source or metric"),
    "vague_market": (re.compile(r'\b(industry.leading|market.leading|state.of.the.art|cutting.edge)\b', re.IGNORECASE),
                     "Be specific about what sets it apart"),
    "vague_performance": (re.compile(r'\b(great\s+performance|excellent\s+performance|outstanding\s+performance)\b', re.IGNORECASE),
                          "Add a benchmark or specific result"),
    "vague_design": (re.compile(r'\b(sleek|stylish|modern|elegant|beautiful)\s+(design|look|aesthetic)\b', re.IGNORECASE),
                     "Describe what makes the design good"),
}


class SpecificityBooster:
    """Detects vague claims and suggests specific replacements."""

    def scan_for_vagueness(self, text: str) -> list[dict]:
        """Scan text for vague claims. Returns list of {match, pattern_key, position, suggestion}."""
        results = []
        for key, (regex, suggestion) in _VAGUE_PATTERNS.items():
            for match in regex.finditer(text):
                results.append({
                    "match": match.group(),
                    "pattern_key": key,
                    "position": match.start(),
                    "suggestion": suggestion,
                })
        return sorted(results, key=lambda x: x["position"])

    def scan_for_vagueness_html(self, html: str) -> list[dict]:
        """Scan HTML content for vague claims."""
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'&[a-z]+;', ' ', text)
        return self.scan_for_vagueness(text)

    def count_vague_claims(self, text: str) -> int:
        return len(self.scan_for_vagueness(text))

    def get_specificity_score(self, text: str) -> float:
        """Score 0.0-1.0 where 1.0 = maximally specific (no vague claims)."""
        count = self.count_vague_claims(text)
        word_count = len(text.split())
        if word_count < 10:
            return 1.0
        density = count / max(1, word_count / 100)
        score = max(0.0, 1.0 - (density * 0.2))
        return round(score, 2)