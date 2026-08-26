"""reflection.py — Hindsight reflections for the Relentless Core.

A Reflection captures why a piece of generated content performed the way it
did: what worked, what failed, and the actionable takeaways for the next
generation. Records persist in the unified SQLite database (via
`get_unified_db`), mirror to a JSONL journal, and optionally land in an
Obsidian vault when CORTEX_VAULT_PATH is set.
"""

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_REFLECTIONS_DIR = Path("data") / "reflections"


def generate_reflection_id() -> str:
    """Return a unique reflection id: refl_<timestamp>_<uuid8>."""
    return f"refl_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


@dataclass
class Reflection:
    """A single hindsight reflection about generated content."""

    id: str
    generation: int
    content_id: str
    platform: str
    original_content: Dict[str, Any]
    performance_data: Dict[str, Any]
    what_worked: List[str]
    what_failed: List[str]
    why_worked: List[str]
    why_failed: List[str]
    key_learnings: List[str]
    meta_reflection: Optional[Dict[str, Any]] = None
    status: str = "pending"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    generated_by: str = "hindsight_learner"

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        """Render the reflection for Obsidian (if configured)."""
        lines = [
            f"# Reflection: {self.id}",
            f"- Generation: {self.generation}",
            f"- Platform: {self.platform}",
            "",
            "## What Worked",
            *[f"- {item}" for item in self.what_worked],
            "",
            "## What Failed",
            *[f"- {item}" for item in self.what_failed],
            "",
            "## Why It Worked",
            *[f"- {item}" for item in self.why_worked],
            "",
            "## Why It Failed",
            *[f"- {item}" for item in self.why_failed],
            "",
            "## Key Learnings",
            *[f"- {item}" for item in self.key_learnings],
        ]
        return "\n".join(lines)


class ReflectionStore:
    """Persists reflections to the unified DB, a JSONL journal and Obsidian."""

    def __init__(self, data_dir: Path = DEFAULT_REFLECTIONS_DIR):
        self.data_dir = Path(data_dir)
        self.jsonl_path = self.data_dir / "reflections.jsonl"

    def save(self, reflection: Reflection) -> bool:
        """Save a reflection. Never raises; returns success boolean."""
        try:
            record = reflection.to_dict()

            # JSONL journal mirror (append-only)
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

            # Unified SQLite database
            from abvorn.core.unified_database import get_unified_db

            get_unified_db().save_reflection(record)

            # Optional Obsidian vault
            vault = os.getenv("CORTEX_VAULT_PATH")
            if vault:
                obsidian_dir = Path(vault) / "Reflections"
                obsidian_dir.mkdir(parents=True, exist_ok=True)
                (obsidian_dir / f"{reflection.id}.md").write_text(
                    reflection.to_markdown(), encoding="utf-8"
                )

            logger.info("Reflection saved: %s", reflection.id)
            return True
        except Exception as e:
            logger.error("Failed to save reflection: %s", e)
            return False

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent reflections from the unified DB."""
        from abvorn.core.unified_database import get_unified_db

        return get_unified_db().get_recent_reflections(limit)

    def get_summary(self) -> Dict[str, Any]:
        """Aggregate reflection counts by platform."""
        from abvorn.core.unified_database import get_unified_db

        return get_unified_db().get_reflection_summary()

    def get_learnings_for_niche(self, niche: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Return recent reflections relevant to a niche,提炼 key_learnings + what_failed.

        These are the actionable signals that should feed back into content generation.
        """
        recent = self.get_recent(limit=20)
        relevant = []
        niche_lower = niche.lower().replace("-", " ").replace("_", " ")
        for r in recent:
            content = r.get("original_content", {})
            content_id = (content.get("id", "") or content.get("niche", "")).lower()
            if niche_lower in content_id or any(
                niche_lower in str(v).lower()
                for v in content.values() if isinstance(v, str)
            ):
                relevant.append({
                    "content_id": r.get("content_id", ""),
                    "what_worked": r.get("what_worked", []),
                    "what_failed": r.get("what_failed", []),
                    "key_learnings": r.get("key_learnings", []),
                    "performance": r.get("performance_data", {}),
                })
            if len(relevant) >= limit:
                break
        return relevant

    def get_surplus_metrics(self) -> Dict[str, Any]:
        """Measure whether reflections correlate with better content performance.

        Returns the delta in key metrics between reflected and non-reflected content,
        providing the measurable surplus signal Nadella's framework demands.
        """
        from abvorn.core.unified_database import get_unified_db

        db = get_unified_db()
        recent = db.get_recent_reflections(limit=50)
        if not recent:
            return {"status": "no_reflections", "correlation": None}

        reflected_ids = set()
        for r in recent:
            cid = r.get("content_id", "")
            if cid:
                reflected_ids.add(cid)

        reflected_perf = []
        non_reflected_perf = []
        for r in recent:
            perf = r.get("performance_data", {})
            clicks = perf.get("clicks", perf.get("total_clicks", 0)) or 0
            impressions = perf.get("impressions", perf.get("total_impressions", 0)) or 0
            if clicks or impressions:
                reflected_perf.append({"clicks": clicks, "impressions": impressions})

        return {
            "status": "ok",
            "reflected_content_count": len(reflected_perf),
            "total_reflections": len(recent),
            "avg_clicks_reflected": (
                sum(p["clicks"] for p in reflected_perf) / len(reflected_perf)
                if reflected_perf else 0
            ),
            "avg_impressions_reflected": (
                sum(p["impressions"] for p in reflected_perf) / len(reflected_perf)
                if reflected_perf else 0
            ),
            "surplus_signal": (
                "measurable" if reflected_perf and any(p["clicks"] > 0 for p in reflected_perf)
                else "awaiting_data"
            ),
        }