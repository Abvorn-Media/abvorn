"""Tests for the Hindsight Reflection module (abvorn/core/reflection.py)."""

import json

import pytest

import abvorn.core.unified_database as udb
from abvorn.core.learner import HindsightLearner
from abvorn.core.reflection import Reflection, ReflectionStore, generate_reflection_id


@pytest.fixture(autouse=True)
def _reset_unified_db():
    """get_unified_db() caches a singleton; reset it so each test is isolated."""
    udb._instance = None
    yield
    udb._instance = None


def _make_reflection(**overrides):
    base = dict(
        id=generate_reflection_id(),
        generation=2,
        content_id="article_1",
        platform="web",
        original_content={"action": "expand_content", "niche": "laptops"},
        performance_data={"clicks": 120, "win_metrics": {"total_runs": 3}},
        what_worked=["Hook phrasing", "Verdict table"],
        what_failed=["CTA placement"],
        why_worked=["Clear contrast vs alternatives"],
        why_failed=["Buried below the fold"],
        key_learnings=["Move CTA above decision matrix"],
    )
    base.update(overrides)
    return Reflection(**base)


def test_generate_reflection_id_unique():
    a = generate_reflection_id()
    b = generate_reflection_id()
    assert a != b
    assert a.startswith("refl_")


def test_reflection_to_dict_roundtrip():
    ref = _make_reflection()
    d = ref.to_dict()
    assert d["status"] == "pending"
    assert d["generated_by"] == "hindsight_learner"
    assert d["created_at"] == d["updated_at"]
    assert "what_worked" in d


def test_reflection_to_markdown():
    md = _make_reflection().to_markdown()
    assert "# Reflection:" in md
    assert "## What Worked" in md
    assert "- Hook phrasing" in md
    assert "## Key Learnings" in md


def test_store_save_and_recent(tmp_path, monkeypatch):
    monkeypatch.setenv("ABVORN_DB_PATH", str(tmp_path / "test.db"))
    store = ReflectionStore(data_dir=tmp_path / "reflections")
    ref = _make_reflection()
    assert store.save(ref) is True

    recent = store.get_recent(10)
    assert len(recent) == 1
    row = recent[0]
    assert row["id"] == ref.id
    assert row["platform"] == "web"
    # JSON-encoded columns come back decoded
    assert row["original_content"]["action"] == "expand_content"
    assert row["what_worked"] == ["Hook phrasing", "Verdict table"]

    # JSONL mirror was written
    lines = (tmp_path / "reflections" / "reflections.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == ref.id


def test_store_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("ABVORN_DB_PATH", str(tmp_path / "test.db"))
    store = ReflectionStore(data_dir=tmp_path / "reflections")
    store.save(_make_reflection(platform="web"))
    store.save(_make_reflection(platform="tiktok"))
    store.save(_make_reflection(platform="web"))

    summary = store.get_summary()
    assert summary["total"] == 3
    assert summary["platforms"] == {"web": 2, "tiktok": 1}


def test_store_idempotent_by_id(tmp_path, monkeypatch):
    monkeypatch.setenv("ABVORN_DB_PATH", str(tmp_path / "test.db"))
    store = ReflectionStore(data_dir=tmp_path / "reflections")
    ref = _make_reflection()
    store.save(ref)
    store.save(ref)
    assert len(store.get_recent(10)) == 1


def test_hindsight_learner_generates_reflection(tmp_path, monkeypatch):
    monkeypatch.setenv("ABVORN_DB_PATH", str(tmp_path / "test.db"))
    store = ReflectionStore(data_dir=tmp_path / "reflections")

    def fake_model_ask(prompt, json_mode=False):
        return {
            "what_worked": ["A", "B"],
            "what_failed": ["C"],
            "why_worked": ["Reason X"],
            "why_failed": ["Reason Y"],
            "key_learnings": ["Do Z next"],
        }

    learner = HindsightLearner(model_ask=fake_model_ask, store=store)
    content = {"id": "article_9", "generation": 4, "platform": "web"}
    performance = {"clicks": 90}
    ref = learner.generate_reflection(content, performance)

    assert ref is not None
    assert ref.id.startswith("refl_")
    assert ref.status == "complete"
    assert ref.what_worked == ["A", "B"]
    assert ref.key_learnings == ["Do Z next"]
    assert learner.reflection_count == 1
    assert len(store.get_recent(10)) == 1


def test_hindsight_learner_fallback_on_bad_response(tmp_path, monkeypatch):
    monkeypatch.setenv("ABVORN_DB_PATH", str(tmp_path / "test.db"))
    store = ReflectionStore(data_dir=tmp_path / "reflections")

    def broken_model_ask(prompt, json_mode=False):
        return "not json at all"

    learner = HindsightLearner(model_ask=broken_model_ask, store=store)
    ref = learner.generate_reflection({"id": "x", "generation": 1, "platform": "web"}, {})
    assert ref is not None
    # Heuristic fallback keeps the loop alive
    assert ref.what_worked == ["Content generated successfully"]


def test_hindsight_learner_never_raises_on_model_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("ABVORN_DB_PATH", str(tmp_path / "test.db"))
    store = ReflectionStore(data_dir=tmp_path / "reflections")

    def crashing_model_ask(prompt, json_mode=False):
        raise RuntimeError("provider down")

    learner = HindsightLearner(model_ask=crashing_model_ask, store=store)
    ref = learner.generate_reflection({"id": "x", "generation": 1, "platform": "web"}, {})
    assert ref is None  # swallowed, does not crash the cycle