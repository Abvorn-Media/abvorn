"""evolution_journal.py — Repo-tracked Evolution Journal.

A CI-safe journal source for Ab's "Evolution Journal" page. The Relentless
Core writes one entry per drive cycle here in addition to (or instead of) the
local Obsidian vault journal. Because this file lives in the repo and is
committed by the content-cycle workflow, GitHub Pages builds and the live
/​api/evolution/public poller always see fresh entries even though CI has no
access to the developer's local vault.

Schema (on-disk, docs/data-independent):
    {
      "entries": [
        {
          "timestamp": ISO-8601,
          "generation": int,
          "drive_score": float,
          "action": str,
          "narrative": str,
          "graph_nodes": int|None,
          "graph_edges": int|None
        }
      ],
      "last_update": ISO-8601
    }

All functions are defensive: they never raise, so a corrupt or missing file
degrades to an empty journal instead of breaking a content cycle.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PATH = Path("data") / "evolution_journal.json"
# maxima per generation/action to keep the file from growing unbounded
MAX_ENTRIES = 500


def journal_path() -> Path:
    """Resolve the repo-tracked journal path (env override for tests)."""
    p = os.getenv("ABVORN_JOURNAL_PATH")
    return Path(p) if p else DEFAULT_PATH


def read_journal() -> Dict[str, Any]:
    """Load the tracked journal. Returns {entries: [...], last_update: ...}."""
    p = journal_path()
    try:
        if not p.exists():
            return {"entries": [], "last_update": None}
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"entries": [], "last_update": None}
        entries = data.get("entries")
        if not isinstance(entries, list):
            entries = []
        return {
            "entries": [e for e in entries if isinstance(e, dict)],
            "last_update": data.get("last_update"),
        }
    except Exception:
        return {"entries": [], "last_update": None}


def load_entries(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return journal entries, newest first."""
    entries = read_journal()["entries"]
    sorted_entries = sorted(
        entries,
        key=lambda e: str(e.get("timestamp", "")),
        reverse=True,
    )
    if limit:
        return sorted_entries[:limit]
    return sorted_entries


def append_entry(entry: Dict[str, Any]) -> bool:
    """Append one entry and rewrite the tracked journal atomically.

    Appends every call (each drive cycle leaves a trace) but skips an entry
    whose narrative is byte-identical to the most recent one, to avoid literal
    duplicates from an unchanged cycle. Keeps only the newest MAX_ENTRIES.

    Returns False (no entry written) when the entry is empty or a duplicate of
    the latest, True on success. Never raises.
    """
    if not entry:
        return False
    try:
        data = read_journal()
        entries = data["entries"]

        stamp = entry.get("timestamp") or datetime.now().isoformat()
        narrative = str(entry.get("narrative") or "").strip()
        if not narrative:
            return False
        if entries and entries[-1].get("narrative") == narrative:
            return False

        candidate = {
            "timestamp": stamp,
            "generation": int(entry.get("generation") or 1),
            "drive_score": round(float(entry.get("drive_score") or 0.0), 4),
            "action": str(entry.get("action") or "unknown"),
            "narrative": narrative,
            "graph_nodes": entry.get("graph_nodes"),
            "graph_edges": entry.get("graph_edges"),
        }
        entries.append(candidate)

        entries = entries[-MAX_ENTRIES:]
        payload = {"entries": entries, "last_update": stamp}

        p = journal_path()
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, p)
        return True
    except Exception:
        return False


def summarize() -> Dict[str, Any]:
    """Derive {current_generation, total_entries, graph_nodes, graph_edges,
    last_update} from the tracked journal, preferring recorded graph stats and
    falling back to the most recent entry's values."""
    entries = load_entries()
    gen = 1
    nodes = edges = 0
    last_update = None
    for e in entries:
        gen = max(gen, int(e.get("generation") or 1))
        if e.get("graph_nodes"):
            nodes = int(e["graph_nodes"])
        if e.get("graph_edges"):
            edges = int(e["graph_edges"])
        if not last_update and e.get("timestamp"):
            last_update = e["timestamp"]
    if not last_update:
        last_update = read_journal()["last_update"]
    return {
        "current_generation": gen,
        "total_entries": len(entries),
        "graph_nodes": nodes,
        "graph_edges": edges,
        "last_update": last_update,
    }
