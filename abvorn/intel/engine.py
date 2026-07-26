import logging
from typing import Optional
from .patterns import PersuasionPatternDB
from .extractor import PatternExtractor
from .transfers import KnowledgeTransfer
from .report import IntelReport

logger = logging.getLogger("abvorn.intel.engine")

class CrossNicheIntelligence:
    """Main orchestrator — learns from every cycle, applies knowledge across niches."""

    def __init__(self, pattern_db: Optional[PersuasionPatternDB] = None, state=None):
        self.pattern_db = pattern_db or PersuasionPatternDB(state)
        self.extractor = PatternExtractor()
        self.transfer = KnowledgeTransfer(self.pattern_db)
        self.state = state
        self._cycle_count = 0

    def ingest_cycle(self, content: dict, persona: dict, outcome_success: bool = True) -> dict:
        """After a content cycle completes, extract and store patterns."""
        patterns = self.extractor.extract_from_content(content, persona, outcome_success)
        persona_patterns = self.extractor.extract_from_persona(persona)
        all_patterns = patterns + persona_patterns

        stored_count = 0
        for pattern in all_patterns:
            stored = self.pattern_db.store(pattern)
            if stored:
                stored_count += 1

        self._cycle_count += 1

        if self.state:
            try:
                self.state.set_meta("intel_cycle_count", self._cycle_count)
                self.state.set_meta("intel_last_ingest", {
                    "niche": content.get("niche", "unknown"),
                    "patterns_extracted": len(all_patterns),
                    "patterns_stored": stored_count,
                    "total": self.pattern_db.count()
                })
            except Exception as e:
                logger.warning(f"Failed to persist intel state: {e}")

        return {
            "patterns_extracted": len(all_patterns),
            "patterns_stored": stored_count,
            "total_patterns": self.pattern_db.count()
        }

    def prepare_prompt(self, niche: str, persona: dict = None) -> str:
        """Build prompt injection string with cross-niche patterns."""
        return self.transfer.build_cross_niche_prompt(niche, persona)

    def get_intelligence_report(self) -> str:
        """Full intelligence report as formatted string."""
        report = IntelReport()
        return report.generate_full_report(self)

    def get_learning_velocity(self) -> dict:
        """Patterns learned per cycle — shows acceleration."""
        total = self.pattern_db.count()
        if self._cycle_count == 0:
            return {"patterns_per_cycle": 0, "total_cycles": 0, "total_patterns": total}
        return {
            "patterns_per_cycle": round(total / self._cycle_count, 1),
            "total_cycles": self._cycle_count,
            "total_patterns": total
        }