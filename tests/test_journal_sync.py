"""Tests for the journal sync harvester (abvorn.core.journal_sync).

Guards the pipeline that keeps Ab's journal page live: harvesting real runtime
signals (GSC insights, relentless drive history, daily reflections) into the
repo-tracked Evolution Journal, idempotently (timestamp-based since + the
append_entry narrative dedupe), plus the JSON-narrative skip that keeps
n8n-reflection machine records off the journal page.
"""

import json

import pytest

from abvorn.core import journal_sync
from src.deployment import _journal_entry_narrative


@pytest.fixture()
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "ab_journal_entries.jsonl").write_text(
        json.dumps({
            "timestamp": "2026-09-08T14:47:02.000000",
            "source": "Google Search Console",
            "insights": ["Top page: wireless-earbuds", "CTR 2.1%"],
        }) + "\n",
        encoding="utf-8",
    )
    (d / "reflections").mkdir()
    (d / "reflections" / "reflections.jsonl").write_text(
        json.dumps({
            "created_at": "2026-09-08T05:00:05.000000",
            "generation": 2,
            "key_learnings": ["Anchor headings proved out"],
        }) + "\n",
        encoding="utf-8",
    )
    (d / "relentless_state.json").write_text(json.dumps({
        "drive_score": 0.42,
        "history": [{
            "timestamp": "2026-09-07T18:00:00.000000",
            "action": "generate_content",
            "result": "wrote wireless-earbuds guide",
        }],
    }), encoding="utf-8")
    (d / "genesis").mkdir()
    (d / "genesis" / "lineage.json").write_text(json.dumps({
        "generations": [{"to_version": 2}],
    }), encoding="utf-8")
    (d / "neural_memory_state.json").write_text(json.dumps({
        "entities": 3010,
        "relationships": 4521,
    }), encoding="utf-8")
    return d


def test_harvest_collects_all_sources_newest_first(data_dir):
    entries = journal_sync.harvest_entries(data_dir)
    assert len(entries) == 3
    stamps = [e["timestamp"] for e in entries]
    assert stamps == sorted(stamps, reverse=True)
    assert entries[0]["action"] == "insight"
    assert entries[1]["action"] == "reflection"
    assert entries[2]["action"] == "generate_content"


def test_harvest_respects_since_filter(data_dir):
    entries = journal_sync.harvest_entries(data_dir, since="2026-09-08T00:00:00.000000")
    assert [e["action"] for e in entries] == ["insight", "reflection"]


def test_harvest_attaches_generation_and_graph(data_dir):
    entries = journal_sync.harvest_entries(data_dir, since="")
    e = entries[0]
    assert e["generation"] == 2
    assert e["graph_nodes"] == 3010
    assert e["graph_edges"] == 4521


def test_sync_appends_and_advances_last_update(data_dir, monkeypatch, tmp_path):
    journal = tmp_path / "evolution_journal.json"
    monkeypatch.setenv("ABVORN_JOURNAL_PATH", str(journal))
    journal.write_text(json.dumps({
        "entries": [{
            "timestamp": "2026-09-06T00:00:00.000000",
            "generation": 2,
            "drive_score": 0.0,
            "action": "expand_content",
            "narrative": "old entry",
        }],
        "last_update": "2026-09-06T00:00:00.000000",
    }), encoding="utf-8")

    added = journal_sync.sync_journal_from_sources(data_dir)
    assert added == 3

    payload = json.loads(journal.read_text(encoding="utf-8"))
    assert payload["last_update"] == "2026-09-08T14:47:02.000000"
    assert len(payload["entries"]) == 4


def test_sync_is_idempotent(data_dir, monkeypatch, tmp_path):
    journal = tmp_path / "evolution_journal.json"
    monkeypatch.setenv("ABVORN_JOURNAL_PATH", str(journal))

    assert journal_sync.sync_journal_from_sources(data_dir) == 3
    assert journal_sync.sync_journal_from_sources(data_dir) == 0
    payload = json.loads(journal.read_text(encoding="utf-8"))
    assert len(payload["entries"]) == 3


def test_caps_per_source(data_dir):
    (data_dir / "ab_journal_entries.jsonl").write_text(
        "".join(
            json.dumps({
                "timestamp": f"2026-09-0{i}T12:00:00.000000",
                "source": "Google Search Console",
                "insights": [f"insight {i}"],
            }) + "\n"
            for i in range(1, 9)
        ),
        encoding="utf-8",
    )
    entries = journal_sync.harvest_entries(data_dir, since="")
    insight_count = sum(1 for e in entries if e["action"] == "insight")
    assert insight_count <= journal_sync._MAX_PER_SOURCE


@pytest.mark.parametrize("body", [
    '{"timestamp":"2026-09-08T05:00:00","data":{"reflection_id":"r1"}}',
    '[\n  {"a": 1},\n  {"b": 2}\n]',
])
def test_journal_narrative_skips_json_bodies(body):
    assert _journal_entry_narrative(body) == ""


def test_journal_narrative_keeps_prose():
    assert _journal_entry_narrative("# Day 3\nWrote the wireless-earbuds guide.") == \
        "Wrote the wireless-earbuds guide."