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