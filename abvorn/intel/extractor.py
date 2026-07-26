import re, logging
from datetime import datetime, timezone
from .patterns import PersuasionPattern, PATTERN_TRIGGER, PATTERN_CTA, PATTERN_STRUCTURE, PATTERN_ANGLE, PATTERN_FORMAT, PATTERN_AVOID

logger = logging.getLogger("abvorn.intel.extractor")

CTA_PATTERNS = [
    r'buy\s+now', r'shop\s+now', r'get\s+yours', r'check\s+(price|it|out)',
    r'click\s+here', r'learn\s+more', r'sign\s+up', r'try\s+it',
    r'see\s+(the|our)', r'start\s+(today|now|here)', r'download\s+(now|free|the)',
]

TRIGGER_PATTERNS = [
    r'stop\s+wasting', r'finally', r'no\s+more', r'never\s+again',
    r'don\'?t\s+settle', r'you\s+deserve', r'imagine', r'what\s+if',
    r'secret', r'surprisingly', r'actually\s+works', r'real\s+people',
    r'trust\s+me', r'i\s+know\s+you', r'you\'?ve\s+been',
]

class PatternExtractor:
    """Analyzes content cycles and detects persuasion patterns."""

    def extract_from_content(self, content: dict, persona: dict = None, outcome: bool = True) -> list:
        """Analyze a completed content cycle and return detected patterns."""
        patterns = []
        article = content.get("article_html", "") or ""
        article_lower = article.lower()
        niche = content.get("niche", "unknown")
        persona_trait = persona.get("decision_trigger", "") if persona else ""

        found_ctas = set()
        for cta in CTA_PATTERNS:
            matches = re.findall(cta, article_lower)
            if matches:
                found_ctas.add(matches[0])
        for cta in found_ctas:
            patterns.append(PersuasionPattern(
                pattern_type=PATTERN_CTA, content=cta,
                source_niche=niche, target_persona_trait=persona_trait,
                success_count=1 if outcome else 0, fail_count=0 if outcome else 1,
                tags=["cta", niche]
            ))

        found_triggers = set()
        for trigger in TRIGGER_PATTERNS:
            matches = re.findall(trigger, article_lower)
            if matches:
                found_triggers.add(matches[0])
        for trigger in found_triggers:
            patterns.append(PersuasionPattern(
                pattern_type=PATTERN_TRIGGER, content=f"Use '{trigger}' trigger",
                source_niche=niche, target_persona_trait=persona_trait,
                success_count=1 if outcome else 0, fail_count=0 if outcome else 1,
                tags=["trigger", niche]
            ))

        angle = content.get("selected_angle", "")
        if angle:
            patterns.append(PersuasionPattern(
                pattern_type=PATTERN_ANGLE, content=angle,
                source_niche=niche, target_persona_trait=persona_trait,
                success_count=1 if outcome else 0, fail_count=0 if outcome else 1,
                tags=["angle", niche]
            ))

        headings = re.findall(r'<h[23][^>]*>(.*?)</h[23]>', article, re.IGNORECASE)
        if headings:
            structure_type = "comparison" if any("vs" in h.lower() for h in headings) else "list" if any(h[0].isdigit() for h in headings) else "narrative"
            patterns.append(PersuasionPattern(
                pattern_type=PATTERN_STRUCTURE, content=f"{structure_type}-based article with {len(headings)} sections",
                source_niche=niche, target_persona_trait=persona_trait,
                success_count=1 if outcome else 0, fail_count=0 if outcome else 1,
                tags=["structure", niche, structure_type]
            ))

        logger.info(f"Extracted {len(patterns)} patterns from content (niche: {niche})")
        return patterns

    def extract_from_persona(self, persona: dict) -> list:
        """Extract patterns from persona psychology — anxieties, desires, triggers."""
        patterns = []
        niche = persona.get("niche", "unknown")

        anxieties = persona.get("anxieties", []) or persona.get("psychology", {}).get("anxieties", [])
        desires = persona.get("desires", []) or persona.get("psychology", {}).get("desires", [])
        decision_trigger = persona.get("decision_trigger", "") or persona.get("psychology", {}).get("decision_trigger", "")

        for anxiety in (anxieties if isinstance(anxieties, list) else [anxieties]):
            if isinstance(anxiety, str):
                patterns.append(PersuasionPattern(
                    pattern_type=PATTERN_TRIGGER,
                    content=f"Address anxiety: {anxiety}",
                    source_niche=niche,
                    target_persona_trait="anxious",
                    tags=["anxiety", niche]
                ))

        for desire in (desires if isinstance(desires, list) else [desires]):
            if isinstance(desire, str):
                patterns.append(PersuasionPattern(
                    pattern_type=PATTERN_TRIGGER,
                    content=f"Appeal to desire: {desire}",
                    source_niche=niche,
                    target_persona_trait="aspiring",
                    tags=["desire", niche]
                ))

        if decision_trigger:
            patterns.append(PersuasionPattern(
                pattern_type=PATTERN_ANGLE,
                content=f"Decision trigger: {decision_trigger}",
                source_niche=niche,
                target_persona_trait=decision_trigger,
                tags=["decision", niche, decision_trigger]
            ))

        logger.info(f"Extracted {len(patterns)} patterns from persona (niche: {niche})")
        return patterns

    def extract_niche_similarity(self, niche_a: str, niche_b: str, pattern_db=None) -> float:
        """Compute similarity between two niches based on pattern overlap."""
        if not pattern_db:
            return 0.0
        patterns_a = pattern_db.search(niche=niche_a)
        patterns_b = pattern_db.search(niche=niche_b)
        if not patterns_a or not patterns_b:
            return 0.0
        contents_a = {p["content"] for p in patterns_a}
        contents_b = {p["content"] for p in patterns_b}
        if not contents_a or not contents_b:
            return 0.0
        intersection = contents_a & contents_b
        union = contents_a | contents_b
        return round(len(intersection) / len(union), 2) if union else 0.0