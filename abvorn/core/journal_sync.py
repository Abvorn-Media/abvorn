"""journal_sync.py — Keep the Evolution Journal live from real runtime signals.

The public journal page and its live poll are only as fresh as the repo-tracked
data/evolution_journal.json. In practice that file stagnates because the only
writer is RelentlessCore.append_entry inside CI cycles, which byte-dedupes
identical narratives. Meanwhile the runtime keeps producing genuinely new
signals — GSC insights (data/ab_journal_entries.jsonl), relentless drive
actions (data/relentless_state.json history), and daily reflections
(data/reflections/reflections.jsonl) — that never reach the page.

This module harvests those sources and appends them to the tracked journal.
The journal target honors ABVORN_JOURNAL_PATH (as evolution_journal does), so
the same code runs in tests against a temp path and on the server against the
repo-tracked copy.
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_MAX_PER_SOURCE = 4


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read newline-delimited JSON, ignoring unparseable lines. Never raises."""
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception as e:
        logger.warning("journal_sync: unreadable jsonl %s: %s", path, e)
    return rows


def _read_json(path: Path) -> Dict[str, Any]:
    """Read a JSON object; never raises. Returns {} on any failure."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("journal_sync: unreadable json %s: %s", path, e)
    return {}


def _current_generation(data_dir: Path, fallback: int = 1) -> int:
    """Read the current generation from genesis lineage, defaulting to 1."""
    lineage = _read_json(data_dir / "genesis" / "lineage.json")
    try:
        return int(lineage.get("generations", [{}])[0].get("to_version") or fallback)
    except Exception:
        return fallback


def _memory_graph(data_dir: Path) -> Dict[str, Any]:
    """Return {graph_nodes, graph_edges} from the neural memory state."""
    memory = _read_json(data_dir / "neural_memory_state.json")
    try:
        nodes = int(memory.get("entities") or 0)
    except (TypeError, ValueError):
        nodes = 0
    try:
        edges = int(memory.get("relationships") or 0)
    except (TypeError, ValueError):
        edges = 0
    return {"graph_nodes": nodes, "graph_edges": edges}


def harvest_entries(data_dir: Path, since: str = "") -> List[Dict[str, Any]]:
    """Collect candidate journal entries from runtime signals newer than ``since``.

    Sources (newest-first overall, capped per source): GSC insights,
    relentless drive actions, daily reflections. Timestamps come from the
    source rows so last_update advances only when genuinely new data exists.
    """
    data_dir = Path(data_dir)
    gen = _current_generation(data_dir)
    graph = _memory_graph(data_dir)
    merged: List[Dict[str, Any]] = []

    for row in _read_jsonl(data_dir / "ab_journal_entries.jsonl"):
        ts = str(row.get("timestamp") or "")
        if not ts or ts <= since:
            continue
        insights = row.get("insights") or []
        narrative = "; ".join(str(i) for i in insights[:3])
        if not narrative:
            narrative = "Search Console ingested performance data."
        merged.append({
            "timestamp": ts,
            "generation": gen,
            "action": "insight",
            "narrative": f"Search Console insight — {narrative}",
            **graph,
        })

    state = _read_json(data_dir / "relentless_state.json")
    for row in state.get("history") or []:
        ts = str(row.get("timestamp") or "")
        if not ts or ts <= since:
            continue
        action = str(row.get("action") or "drive")
        result = str(row.get("result") or "").strip()
        narrative = f"Drive action '{action}'" + (f": {result}" if result else "")
        merged.append({
            "timestamp": ts,
            "generation": gen,
            "drive_score": state.get("drive_score"),
            "action": action,
            "narrative": narrative,
            **graph,
        })

    for row in _read_jsonl(data_dir / "reflections" / "reflections.jsonl"):
        ts = str(row.get("created_at") or row.get("timestamp") or "")
        if not ts or ts <= since:
            continue
        learned = row.get("key_learnings") or []
        narrative = (
            f"Reflection — {str(learned[0])}"
            if learned
            else "Reflection — reviewed a completed content cycle"
        )
        merged.append({
            "timestamp": ts,
            "generation": int(row.get("generation") or gen),
            "action": "reflection",
            "narrative": narrative,
            **graph,
        })

    merged.sort(key=lambda e: str(e.get("timestamp") or ""), reverse=True)

    per_action: Dict[str, int] = defaultdict(int)
    capped: List[Dict[str, Any]] = []
    for e in merged:
        action = e.get("action") or "unknown"
        if per_action[action] >= _MAX_PER_SOURCE:
            continue
        per_action[action] += 1
        capped.append(e)
    return capped


def sync_journal_from_sources(data_dir: Path) -> int:
    """Append fresh runtime signals to the tracked journal. Returns count added.

    The journal target comes from ABVORN_JOURNAL_PATH (falling back to
    data/evolution_journal.json relative to CWD). Idempotent: rows already
    represented (timestamp <= the newest entry, or a byte-identical narrative)
    are skipped. last_update is normalized to the newest entry after writing so
    a future harvest never re-appends an older batch row. Never raises.
    """
    from abvorn.core import evolution_journal as ej

    current = ej.read_journal()
    entries = current.get("entries") or []
    newest = max((str(e.get("timestamp") or "") for e in entries), default="")
    added = 0
    for entry in harvest_entries(Path(data_dir), since=newest):
        try:
            if ej.append_entry(entry):
                added += 1
        except Exception as e:
            logger.warning("journal_sync: append failed: %s", e)

    if added:
        try:
            fresh_entries = ej.read_journal().get("entries") or []
            fresh_newest = max((str(e.get("timestamp") or "") for e in fresh_entries), default="")
            if fresh_newest and fresh_newest != ej.read_journal().get("last_update"):
                payload = {"entries": fresh_entries, "last_update": fresh_newest}
                path = ej.journal_path()
                tmp = path.with_suffix(path.suffix + ".tmp")
                tmp.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                os.replace(tmp, path)
        except Exception as e:
            logger.warning("journal_sync: last_update normalize failed: %s", e)
    return added