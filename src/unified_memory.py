#!/usr/bin/env python3
"""
unified_memory.py — The Unified Memory Layer

Consolidates ChromaDB, JSON state, in-memory knowledge, and cloud storage
into a single memory abstraction with automatic tiering.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemoryTier(Enum):
    EPHEMERAL = "ephemeral"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    PERSISTENT = "persistent"


@dataclass
class MemoryEntry:
    key: str
    value: Any
    tier: MemoryTier
    created_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 3600


class EphemeralMemory:
    def __init__(self):
        self._store: Dict[str, Any] = {}

    def store(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        self._store[key] = value

    def retrieve(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def list_keys(self) -> List[str]:
        return list(self._store.keys())

    def clear(self) -> None:
        self._store.clear()


class ShortTermMemory:
    def __init__(self, state_path: str = "data/state.json"):
        self.state_path = Path(state_path)
        self._store: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if self.state_path.exists():
            try:
                self._store = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._store = {}

    def _save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self._store, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def store(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self._store[key] = {"value": value, "expires": (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()}
        self._save()

    def retrieve(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry and "expires" in entry:
            try:
                expires = datetime.fromisoformat(entry["expires"])
                if datetime.now() > expires:
                    del self._store[key]
                    self._save()
                    return None
            except (ValueError, TypeError):
                pass
        return entry.get("value") if isinstance(entry, dict) else entry

    def list_keys(self) -> List[str]:
        return list(self._store.keys())

    def clear(self) -> None:
        self._store.clear()
        self._save()


class LongTermMemory:
    def __init__(self, db_path: str = "data/chroma"):
        self.db_path = Path(db_path)
        self._store: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if self.db_path.exists():
            try:
                for f in self.db_path.glob("*.json"):
                    key = f.stem
                    self._store[key] = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._store = {}

    def _save(self, key: str, value: Any):
        self.db_path.mkdir(parents=True, exist_ok=True)
        (self.db_path / f"{key}.json").write_text(
            json.dumps(value, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def store(self, key: str, value: Any, ttl_seconds: int = 86400) -> None:
        self._store[key] = value
        self._save(key, value)

    def retrieve(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, Any]]:
        results = []
        for key, value in self._store.items():
            if query.lower() in str(value).lower() or query.lower() in key.lower():
                results.append((key, value))
        return results[:top_k]

    def list_keys(self) -> List[str]:
        return list(self._store.keys())

    def clear(self) -> None:
        self._store.clear()
        for f in self.db_path.glob("*.json"):
            f.unlink()


class PersistentMemory:
    def __init__(self, storage_path: str = "data/persistent"):
        self.storage_path = Path(storage_path)

    def store(self, key: str, value: Any, ttl_seconds: int = 0) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        (self.storage_path / f"{key}.json").write_text(
            json.dumps(value, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def retrieve(self, key: str) -> Optional[Any]:
        path = self.storage_path / f"{key}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def list_keys(self) -> List[str]:
        if self.storage_path.exists():
            return [f.stem for f in self.storage_path.glob("*.json")]
        return []

    def clear(self) -> None:
        if self.storage_path.exists():
            for f in self.storage_path.glob("*.json"):
                f.unlink()


class UnifiedMemory:
    """
    Single unified memory abstraction with automatic tiering.
    """

    def __init__(self):
        self.layers = {
            MemoryTier.EPHEMERAL: EphemeralMemory(),
            MemoryTier.SHORT_TERM: ShortTermMemory(),
            MemoryTier.LONG_TERM: LongTermMemory(),
            MemoryTier.PERSISTENT: PersistentMemory(),
        }
        self.entries: Dict[str, MemoryEntry] = {}
        self.compression_threshold = 1000

    def store(self, key: str, value: Any, tier: MemoryTier = MemoryTier.SHORT_TERM, ttl_seconds: int = 3600) -> None:
        entry = MemoryEntry(key=key, value=value, tier=tier, ttl_seconds=ttl_seconds)
        self.entries[key] = entry
        self.layers[tier].store(key, value, ttl_seconds)
        logger.info(f"Memory stored: {key} @ {tier.value}")

    def retrieve(self, key: str) -> Optional[Any]:
        entry = self.entries.get(key)
        if entry:
            entry.access_count += 1
            entry.last_accessed = datetime.now()
        value = self.layers[entry.tier if entry else MemoryTier.SHORT_TERM].retrieve(key)
        if value and entry and entry.tier == MemoryTier.EPHEMERAL:
            self._promote(key, value)
        return value

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, Any]]:
        all_results = []
        for tier, layer in self.layers.items():
            if hasattr(layer, "search"):
                all_results.extend(layer.search(query, top_k=top_k // len(self.layers)))
        all_results.sort(key=lambda x: str(x[1]).count(query), reverse=True)
        return all_results[:top_k]

    def _promote(self, key: str, value: Any) -> None:
        entry = self.entries.get(key)
        if entry and entry.access_count >= 3:
            entry.tier = MemoryTier.SHORT_TERM
            self.layers[MemoryTier.SHORT_TERM].store(key, value, entry.ttl_seconds)
            logger.info(f"Memory promoted: {key} -> short_term")

    def compress(self) -> None:
        if len(self.entries) > self.compression_threshold:
            oldest = sorted(
                self.entries.values(),
                key=lambda e: e.last_accessed,
            )[: len(self.entries) // 2]
            for entry in oldest:
                if entry.tier == MemoryTier.SHORT_TERM:
                    entry.tier = MemoryTier.LONG_TERM
            logger.info(f"Memory compressed: {len(oldest)} entries moved to long_term")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_entries": len(self.entries),
            "tiers": {tier.value: len([e for e in self.entries.values() if e.tier == tier]) for tier in MemoryTier},
            "total_accesses": sum(e.access_count for e in self.entries.values()),
        }


def create_unified_memory() -> UnifiedMemory:
    return UnifiedMemory()


if __name__ == "__main__":
    mem = create_unified_memory()
    mem.store("test_key", {"score": 9.5, "product": "Sony WH-1000XM6"}, tier=MemoryTier.EPHEMERAL)
    result = mem.retrieve("test_key")
    print(f"Retrieved: {result}")
    print(f"Stats: {mem.get_stats()}")
    print(f"Search: {mem.search('sony')}")