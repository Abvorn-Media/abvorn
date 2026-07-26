import logging
from typing import Optional
from .patterns import PersuasionPatternDB

logger = logging.getLogger("abvorn.intel.transfers")

class KnowledgeTransfer:
    """Cross-niche knowledge relay — finds and applies patterns from related niches."""

    def __init__(self, pattern_db: Optional[PersuasionPatternDB] = None):
        self.pattern_db = pattern_db

    def find_related_niches(self, source_niche: str, all_niches: list, limit: int = 3) -> list:
        if not self.pattern_db or not all_niches:
            return []
        scored = []
        for niche in all_niches:
            if niche == source_niche:
                continue
            source_patterns = self.pattern_db.search(niche=source_niche)
            target_patterns = self.pattern_db.search(niche=niche)
            if not source_patterns or not target_patterns:
                continue
            source_traits = {p.get("target_persona_trait", "") for p in source_patterns}
            target_traits = {p.get("target_persona_trait", "") for p in target_patterns}
            if not source_traits or not target_traits:
                continue
            overlap = len(source_traits & target_traits) / max(len(source_traits | target_traits), 1)
            scored.append((niche, overlap))

        scored.sort(key=lambda x: -x[1])
        return [{"niche": n, "similarity": round(s, 2)} for n, s in scored[:limit]]

    def transfer_patterns(self, source_niche: str, target_niche: str, limit: int = 3) -> list:
        if not self.pattern_db:
            return []
        return self.pattern_db.get_transferable(source_niche, target_niche, limit)

    def build_cross_niche_prompt(self, niche: str, persona: dict = None) -> str:
        if not self.pattern_db:
            return ""

        persona_trait = ""
        if persona:
            persona_trait = persona.get("decision_trigger", "") or persona.get("psychology", {}).get("decision_trigger", "")

        niche_patterns = self.pattern_db.search(niche=niche, min_confidence=0.6)
        transferable = self.pattern_db.search(persona_trait=persona_trait, min_confidence=0.7) if persona_trait else []

        if not niche_patterns and not transferable:
            return ""

        parts = ["[CROSS-NICHE INTELLIGENCE]"]

        working = [p for p in niche_patterns if p.get("success_count", 0) > p.get("fail_count", 0)][:5]
        if working:
            parts.append("\nPatterns that work in this niche:")
            for p in working:
                parts.append(f"  - {p['content']} (confidence: {p.get('confidence', 0)})")

        if transferable:
            parts.append("\nTransferable patterns from similar niches:")
            for p in transferable:
                parts.append(f"  - {p['content']} (from: {p.get('source_niche', 'unknown')}, confidence: {p.get('confidence', 0)})")

        avoids = [p for p in niche_patterns if p.get("fail_count", 0) > p.get("success_count", 0)][:3]
        if avoids:
            parts.append("\nWhat to avoid:")
            for p in avoids:
                parts.append(f"  - {p['content']} (failed {p.get('fail_count', 0)} times)")

        return "\n".join(parts)

    def compute_pattern_overlap(self, niche_a: str, niche_b: str) -> float:
        if not self.pattern_db:
            return 0.0
        patterns_a = self.pattern_db.search(niche=niche_a, min_confidence=0.0)
        patterns_b = self.pattern_db.search(niche=niche_b, min_confidence=0.0)
        if not patterns_a or not patterns_b:
            return 0.0
        contents_a = {p["content"] for p in patterns_a}
        contents_b = {p["content"] for p in patterns_b}
        intersection = contents_a & contents_b
        union = contents_a | contents_b
        return round(len(intersection) / len(union), 2) if union else 0.0