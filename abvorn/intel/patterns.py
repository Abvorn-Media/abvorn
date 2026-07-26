import json, threading, logging, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List

logger = logging.getLogger("abvorn.intel.patterns")

PATTERN_TRIGGER = "trigger"
PATTERN_CTA = "cta"
PATTERN_STRUCTURE = "structure"
PATTERN_ANGLE = "angle"
PATTERN_FORMAT = "format"
PATTERN_AVOID = "avoid"

@dataclass
class PersuasionPattern:
    pattern_type: str
    content: str
    source_niche: str
    target_persona_trait: str = ""
    success_count: int = 0
    fail_count: int = 0
    tags: list = field(default_factory=list)
    pattern_id: str = ""
    created_at: str = ""
    last_used_at: str = ""

    def __post_init__(self):
        if not self.pattern_id:
            self.pattern_id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def confidence(self) -> float:
        total = self.success_count + self.fail_count
        if total == 0:
            return 0.0
        return round(self.success_count / total, 2)

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "content": self.content,
            "source_niche": self.source_niche,
            "target_persona_trait": self.target_persona_trait,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "confidence": self.confidence,
            "tags": self.tags,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at
        }

class PersuasionPatternDB:
    """Thread-safe in-memory pattern database with optional SQLite persistence."""

    def __init__(self, state=None):
        self._patterns: dict[str, PersuasionPattern] = {}
        self._lock = threading.Lock()
        self.state = state

    def store(self, pattern: PersuasionPattern) -> PersuasionPattern:
        with self._lock:
            existing = self._find_by_content(pattern.content, pattern.source_niche, pattern.pattern_type)
            if existing:
                existing.success_count += pattern.success_count
                existing.fail_count += pattern.fail_count
                existing.last_used_at = datetime.now(timezone.utc).isoformat()
                if pattern.tags:
                    existing.tags = list(set(existing.tags + pattern.tags))
                result = existing
            else:
                self._patterns[pattern.pattern_id] = pattern
                result = pattern
            if self.state:
                try:
                    r = result
                    self.state.upsert_intel_pattern(
                        r.pattern_id, r.pattern_type, r.content, r.source_niche,
                        r.target_persona_trait, r.success_count, r.fail_count,
                        r.confidence, r.tags
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist pattern: {e}")
            return result

    def _find_by_content(self, content: str, source_niche: str, pattern_type: str) -> Optional[PersuasionPattern]:
        for p in self._patterns.values():
            if p.content == content and p.source_niche == source_niche and p.pattern_type == pattern_type:
                return p
        return None

    def record_outcome(self, pattern_id: str, succeeded: bool):
        with self._lock:
            pattern = self._patterns.get(pattern_id)
            if not pattern:
                logger.warning(f"Pattern {pattern_id} not found")
                return
            if succeeded:
                pattern.success_count += 1
            else:
                pattern.fail_count += 1
            pattern.last_used_at = datetime.now(timezone.utc).isoformat()
            if self.state:
                try:
                    self.state.record_intel_pattern_outcome(pattern_id, succeeded)
                except Exception as e:
                    logger.warning(f"Failed to persist outcome: {e}")

    def search(self, niche: str = None, persona_trait: str = None,
               pattern_type: str = None, min_confidence: float = 0.5) -> list:
        with self._lock:
            results = list(self._patterns.values())

            if self.state:
                try:
                    state_patterns = self.state.search_intel_patterns(pattern_type, niche, min_confidence)
                    for sp in state_patterns:
                        pid = sp["id"]
                        if pid not in self._patterns:
                            self._patterns[pid] = PersuasionPattern(
                                pattern_id=pid, pattern_type=sp["pattern_type"],
                                content=sp["content"], source_niche=sp["source_niche"],
                                target_persona_trait=sp.get("target_persona_trait", ""),
                                success_count=sp["success_count"], fail_count=sp["fail_count"],
                                tags=json.loads(sp.get("tags_json", "[]")),
                                created_at=sp["created_at"]
                            )
                except Exception as e:
                    logger.warning(f"Failed to load from state: {e}")

        filtered = []
        for p in results:
            if p.confidence < min_confidence:
                continue
            if niche and p.source_niche != niche:
                continue
            if persona_trait and p.target_persona_trait != persona_trait:
                continue
            if pattern_type and p.pattern_type != pattern_type:
                continue
            filtered.append(p.to_dict())
        return filtered

    def get_high_confidence(self, min_confidence: float = 0.7) -> list:
        return [p.to_dict() for p in self._patterns.values() if p.confidence >= min_confidence]

    def get_transferable(self, source_niche: str, target_niche: str, limit: int = 5) -> list:
        with self._lock:
            candidates = [p for p in self._patterns.values()
                         if p.source_niche == source_niche and p.source_niche != target_niche]
            candidates.sort(key=lambda p: p.confidence, reverse=True)
            return [c.to_dict() for c in candidates[:limit]]

    def count(self) -> int:
        if self.state:
            try:
                return max(len(self._patterns), self.state.get_intel_pattern_count())
            except Exception:
                pass
        return len(self._patterns)

    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._patterns)
            if total == 0:
                return {"total": 0, "by_type": {}, "avg_confidence": 0, "top_niches": []}
            by_type = {}
            niches = {}
            conf_sum = 0
            for p in self._patterns.values():
                by_type[p.pattern_type] = by_type.get(p.pattern_type, 0) + 1
                niches[p.source_niche] = niches.get(p.source_niche, 0) + 1
                conf_sum += p.confidence
            top_niches = sorted(niches.items(), key=lambda x: -x[1])[:5]
            return {
                "total": total,
                "by_type": by_type,
                "avg_confidence": round(conf_sum / total, 2),
                "top_niches": [{"niche": n, "count": c} for n, c in top_niches]
            }