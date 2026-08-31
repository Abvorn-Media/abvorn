"""Tests for the repo-tracked Evolution Journal (abvorn.core.evolution_journal).

Guards the CI-safe journal source that keeps Ab's journal page live when the
content-cycle workflow runs without access to the developer's local Obsidian
vault: append/read round-trips, duplicate suppression, and the mojibake guard
on what gets committed.
"""

import json

import pytest

from abvorn.core import evolution_journal as ej
from src.deployment import find_mojibake


@pytest.fixture()
def journal(tmp_path, monkeypatch):
    """Point the journal at a throwaway path for each test."""
    monkeypatch.setenv("ABVORN_JOURNAL_PATH", str(tmp_path / "journal.json"))
    return tmp_path


def _entry(**over):
    base = {
        "timestamp": "2026-08-31T10:00:00.000000",
        "generation": 2,
        "drive_score": 0.123,
        "action": "expand_content",
        "narrative": "Drive score 0.123 — action 'expand_content': Expanded content",
        "graph_nodes": 2640,
        "graph_edges": 4000,
    }
    base.update(over)
    return base


def test_append_and_read_roundtrip(journal):
    assert ej.append_entry(_entry()) is True
    entries = ej.load_entries()
    assert len(entries) == 1
    assert entries[0]["generation"] == 2
    assert entries[0]["narrative"].startswith("Drive score 0.123")


def test_newest_first(journal):
    ej.append_entry(_entry(timestamp="2026-08-01T00:00:00", action="a",
                           narrative="narrative a"))
    ej.append_entry(_entry(timestamp="2026-08-02T00:00:00", action="b",
                           narrative="narrative b"))
    ej.append_entry(_entry(timestamp="2026-08-03T00:00:00", action="c",
                           narrative="narrative c"))
    entries = ej.load_entries()
    assert [e["action"] for e in entries] == ["c", "b", "a"]


def test_identical_duplicate_narrative_is_skipped(journal):
    ej.append_entry(_entry(timestamp="2026-08-01T00:00:00"))
    # Same narrative again -> suppressed, count unchanged.
    assert ej.append_entry(_entry(timestamp="2026-08-02T00:00:00")) is False
    assert len(ej.load_entries()) == 1


def test_empty_narrative_is_rejected(journal):
    assert ej.append_entry(_entry(narrative="   ")) is False
    assert len(ej.load_entries()) == 0


def test_summarize_derives_stats_and_generation(journal):
    ej.append_entry(_entry(generation=1, graph_nodes=100, graph_edges=200,
                           narrative="gen1"))
    ej.append_entry(_entry(generation=3, graph_nodes=2640, graph_edges=4000,
                           narrative="gen3"))
    s = ej.summarize()
    assert s["current_generation"] == 3
    assert s["total_entries"] == 2
    assert s["graph_nodes"] == 2640
    assert s["graph_edges"] == 4000
    assert s["last_update"]


def test_missing_file_yields_zero_summary(journal):
    s = ej.summarize()
    assert s["total_entries"] == 0
    assert s["current_generation"] == 1


def test_committed_journal_is_mojibake_clean(tmp_path, monkeypatch):
    """The tracked journal must never carry the cp1252 double-encoding."""
    monkeypatch.setenv("ABVORN_JOURNAL_PATH", str(tmp_path / "journal.json"))
    ej.append_entry(_entry())
    raw = (tmp_path / "journal.json").read_text(encoding="utf-8")
    assert find_mojibake(raw) == []
    # sanity: intended em-dash survives as a real em-dash
    assert "—" in raw
