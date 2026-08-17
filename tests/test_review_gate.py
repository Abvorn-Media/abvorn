"""Tests for the content review gate and capability-aware routing."""
import os
import pytest
from unittest.mock import MagicMock
from pathlib import Path


# ---------------------------------------------------------------------------
# Review gate (abvorn/core/review_gate.py)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_review_env(monkeypatch):
    monkeypatch.delenv("ABVORN_CONTENT_REVIEW", raising=False)
    marker = Path("data/content_review.enabled")
    if marker.exists():
        marker.unlink()
    yield
    queue = Path("data/review_queue")
    if queue.exists():
        for p in sorted(queue.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
        queue.rmdir() if queue.exists() else None
    if marker.exists():
        marker.unlink()


def test_review_gate_off_by_default():
    from abvorn.core.review_gate import is_content_review_enabled
    assert is_content_review_enabled() is False


def test_review_gate_env_var_enables():
    os.environ["ABVORN_CONTENT_REVIEW"] = "1"
    from abvorn.core.review_gate import is_content_review_enabled
    assert is_content_review_enabled() is True


def test_review_gate_marker_file_enables(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    marker = Path("data/content_review.enabled")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    from abvorn.core.review_gate import is_content_review_enabled
    assert is_content_review_enabled() is True


def test_review_gate_state_meta_enables():
    from abvorn.core.review_gate import is_content_review_enabled
    state = MagicMock()
    state.get_meta.return_value = True
    assert is_content_review_enabled(state) is True


def test_write_gated_publishes_when_off(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from abvorn.core.review_gate import write_gated
    target = Path("docs/index.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    actual = write_gated(target, "<p>hello</p>")
    assert actual == target
    assert target.read_text(encoding="utf-8") == "<p>hello</p>"
    assert not Path("data/review_queue/index.html").exists()


def test_write_gated_stages_when_on(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.environ["ABVORN_CONTENT_REVIEW"] = "1"
    from abvorn.core.review_gate import write_gated, list_staged
    target = Path("docs/reviews/niche/index.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    actual = write_gated(target, "<p>pending</p>")
    assert actual != target
    assert not target.exists()
    staged = Path("data/review_queue/reviews/niche/index.html")
    assert staged.exists()
    assert staged.read_text(encoding="utf-8") == "<p>pending</p>"
    assert list_staged() == [str(Path("reviews") / "niche" / "index.html")]


def test_approve_staged_promotes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.environ["ABVORN_CONTENT_REVIEW"] = "1"
    from abvorn.core.review_gate import write_gated, approve_staged
    target = Path("docs/reviews/niche/index.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    write_gated(target, "<p>approved</p>")
    promoted = approve_staged()
    assert len(promoted) == 1
    assert target.read_text(encoding="utf-8") == "<p>approved</p>"
    assert not Path("data/review_queue").exists() or not list(Path("data/review_queue").rglob("*.html"))


def test_reject_staged_removes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.environ["ABVORN_CONTENT_REVIEW"] = "1"
    from abvorn.core.review_gate import write_gated, reject_staged
    target = Path("docs/reviews/niche/index.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    write_gated(target, "<p>rejected</p>")
    removed = reject_staged()
    assert len(removed) == 1
    assert not target.exists()


def test_review_status_report():
    os.environ["ABVORN_CONTENT_REVIEW"] = "1"
    from abvorn.core.review_gate import review_status
    status = review_status()
    assert status["gate_on"] is True
    assert "staged_count" in status


def test_write_checked_respects_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.deployment import write_checked
    target = Path("docs/check.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    write_checked(target, "<p>direct</p>", "check")
    assert target.exists()
    os.environ["ABVORN_CONTENT_REVIEW"] = "1"
    target2 = Path("docs/check2.html")
    write_checked(target2, "<p>gated</p>", "check2")
    assert not target2.exists()
    assert Path("data/review_queue/check2.html").exists()


# ---------------------------------------------------------------------------
# Capability-aware routing (src/ai_sql.py)
# ---------------------------------------------------------------------------

def test_task_capability_map():
    from src.ai_sql import TASK_CAPABILITY
    assert TASK_CAPABILITY["draft"] == "strong"
    assert TASK_CAPABILITY["social"] == "fast"
    assert TASK_CAPABILITY["research"] == "fast"
    assert TASK_CAPABILITY["fact_check"] == "strong"


def test_query_plan_carries_task():
    from src.ai_sql import QueryPlan
    q = QueryPlan("s", "u", {"temperature": 0.7}, task="draft")
    assert q.task == "draft"
    q2 = QueryPlan("s", "u", {"temperature": 0.7})
    assert q2.task is None


def test_order_by_capability_strong_first():
    from src.ai_sql import AISQL, KiloGatewayProvider, NvidiaProvider
    ai = AISQL.__new__(AISQL)
    ai.provider_scores = {}
    kilogw = KiloGatewayProvider()
    kilogw.capability = "fast"
    nvidia = NvidiaProvider()
    nvidia.capability = "strong"
    chain = ai._order_by_capability([kilogw, nvidia], "strong")
    assert chain[0] is nvidia
    assert chain[1] is kilogw


def test_providers_carry_capability_after_create():
    from src.ai_sql import create_ai_sql
    ai = create_ai_sql()
    for name, cap in ai.capabilities.items():
        assert ai.providers[name].capability == cap, name


def test_abvorn_tier_for_task():
    from abvorn.core.models import TIER_FOR_TASK
    assert TIER_FOR_TASK["draft"] == "strong"
    assert TIER_FOR_TASK["social"] == "fast"
