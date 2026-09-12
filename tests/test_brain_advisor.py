"""Tests for BrainAdvisor — industry-knowledge decision support layer."""

import json
from pathlib import Path

from abvorn.domination.brain_advisor import (
    BrainAdvisor,
    snapshot_guidance,
    run_brain_advisory,
)
from abvorn.deploy.digest import advisory_block_text


class _FakeBrain:
    """Minimal stand-in for abvorn.core.brain.Brain.query()."""

    def __init__(self, results=None, error=False):
        self._results = results or []
        self._error = error
        self.queries = []

    def query(self, question, limit=5):
        self.queries.append(question)
        if self._error:
            raise RuntimeError("brain broken")
        return self._results[:limit]


def test_guidance_returns_empty_without_brain():
    advisor = BrainAdvisor(brain=None)
    advisor._get_brain = lambda: None
    assert advisor.guidance("Any question?") == []


def test_guidance_surfaces_insights():
    brain = _FakeBrain(results=[
        {"source": "Book", "insight": "Invest early in niches with repeat purchases.", "relevance": 0.9},
        {"source": "Book", "insight": "Avoid price-only positioning.", "relevance": 0.8},
    ])
    advisor = BrainAdvisor(brain=brain)
    out = advisor.guidance("Best practice for niche growth?", limit=3)
    assert len(out) == 2
    assert out[0]["insight"].startswith("Invest early")


def test_guidance_survives_brain_error():
    advisor = BrainAdvisor(brain=_FakeBrain(error=True))
    assert advisor.guidance("Should we double down?") == []
    # retries are suppressed per question (cache)
    assert advisor.guidance("Should we double down?") == []


def test_guidance_caches_per_question():
    brain = _FakeBrain(results=[{"source": "Book", "insight": "X", "relevance": 1.0}])
    advisor = BrainAdvisor(brain=brain)
    q = "Growth playbook for coffee-makers?"
    first = advisor.guidance(q)
    second = advisor.guidance(q)
    assert first and second == []
    assert len(brain.queries) == 1


def test_growth_guidance_falls_through_questions():
    brain = _FakeBrain(results=[{"source": "Book", "insight": "Y", "relevance": 0.7}])
    advisor = BrainAdvisor(brain=brain)
    out = advisor.growth_guidance("gaming mice")
    assert out and out[0]["insight"] == "Y"
    assert "gaming mice" in brain.queries[0]


def test_snapshot_only_flags_measured_decisions():
    brain = _FakeBrain(results=[{"source": "Book", "insight": "Grow when demand holds.", "relevance": 0.9}])
    advisor = BrainAdvisor(brain=brain)
    analytics = {
        "laptops": {"views": 150, "users": 40},
        "mice": {"views": 4, "users": 1},
        "coffee": {"views": 0, "users": 0},
    }
    snap = snapshot_guidance(advisor, analytics)
    assert set(snap.keys()) == {"laptops", "mice"}
    assert snap["laptops"]["decision"] == "double_down"
    assert snap["mice"]["decision"] == "pivot"
    # coffee had nothing measurable — no guidance burned on it
    assert "coffee" not in snap


def test_run_brain_advisory_persists_to_state(tmp_path):
    brain = _FakeBrain(results=[{"source": "Book", "insight": "Double down on clear winners.", "relevance": 0.8}])
    advisor = BrainAdvisor(brain=brain)
    state = _MetaState(tmp_path / "state.json")
    analytics = {"laptops": {"views": 120, "users": 30}}
    out = run_brain_advisory(advisor, analytics, state)
    assert out["laptops"]["decision"] == "double_down"
    stored = json.loads(state.meta["brain_advisory"])
    assert stored["laptops"]["decision"] == "double_down"


def test_run_brain_advisory_is_non_fatal_on_brain_failure(tmp_path):
    advisor = BrainAdvisor(brain=_FakeBrain(error=True))
    state = _MetaState(tmp_path / "state.json")
    out = run_brain_advisory(advisor, {"laptops": {"views": 120}}, state)
    assert out == {}
    assert "brain_advisory" not in state.meta


def test_advisory_block_empty_without_data():
    assert advisory_block_text({}) == ""


def test_advisory_block_lists_decision_and_insight():
    advisory = {
        "laptops": {
            "decision": "double_down",
            "score": 210.0,
            "insights": [{"source": "Book", "insight": "Invest early with repeat purchases."}],
        },
        "mice": {"decision": "pivot", "score": 6.0, "insights": []},
    }
    block = advisory_block_text(advisory)
    assert "Brain guidance" in block
    assert "laptops: 📈 double down (score 210.0)" in block
    assert "Invest early with repeat purchases" in block
    assert "mice: 🪂 pivot (score 6.0)" in block


def test_advisory_block_generic_without_insight():
    block = advisory_block_text({"mice": {"decision": "pivot", "score": 6.0, "insights": []}})
    assert "mice: 🪂 pivot (score 6.0)" in block
    assert "—" not in block


class _MetaState:
    """Tiny stand-in for AbvornState (set_meta/get_meta)."""

    def __init__(self, path):
        self.meta = {}

    def set_meta(self, key, value):
        self.meta[key] = value

    def get_meta(self, key, default=None):
        return self.meta.get(key, default)