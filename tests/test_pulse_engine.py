"""Tests for the Pulse Engine temporal influence graph."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from abvorn.core.pulse_engine import PulseEngine, get_pulse_engine


def _debate(product="Widget", angle="problem_solution", driver="curiosity",
            audience="Reviewers", violations=None, verdict="Good",
            days_ago=1.0):
    return {
        "product": product,
        "platform": "general",
        "strategy": {
            "angle": angle,
            "emotional_driver": driver,
            "target_audience": audience,
        },
        "puritan_critique": {
            "approved": True,
            "violations": violations or [],
        },
        "final_verdict": {
            "hook": f"{product}: a solid {verdict.lower()} pick",
            "verdict_label": verdict,
            "product_name": product,
        },
        "timestamp": (datetime.now() - timedelta(days=days_ago)).isoformat(),
    }


@pytest.fixture()
def debates_dir(tmp_path):
    return tmp_path / "debates"


def _write_debates(dir_, debates):
    dir_.mkdir(parents=True, exist_ok=True)
    for i, d in enumerate(debates):
        (dir_ / f"debate_{i:02d}.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8"
        )
    return dir_


def test_empty_dir_degrades_gracefully(debates_dir):
    pe = PulseEngine(debates_dir=debates_dir)
    stats = pe.build_from_debates()
    assert stats["built"] is True
    assert stats["nodes"] == 0
    assert pe.get_influential_concepts() == []
    assert pe.get_bridge_concepts() == []
    assert pe.get_temporal_shift() == {"rising": [], "falling": [], "stable": []}
    state = pe.get_state()
    assert state["nodes"] == 0
    assert state["debates_processed"] == 0


def test_missing_dir_never_raises(debates_dir):
    pe = PulseEngine(debates_dir=debates_dir / "nope")
    stats = pe.build_from_debates()
    assert stats["built"] is True
    assert stats["nodes"] == 0


def test_builds_graph_from_debates(debates_dir):
    debates = [
        _debate("Widget", angle="problem_solution", violations=["value does not justify the price"], days_ago=2),
        _debate("Gadget", angle="comparison", violations=["value does not justify the price"], days_ago=3),
    ]
    _write_debates(debates_dir, debates)
    pe = PulseEngine(debates_dir=debates_dir)
    stats = pe.build_from_debates()
    assert stats["built"] is True
    assert stats["debates_processed"] == 2
    assert stats["nodes"] > 0
    assert stats["edges"] > 0


def test_extract_concepts_caps_and_dedupes():
    d = _debate("Widget", violations=["bad value", "bad value", "bad value"])
    concepts = PulseEngine._extract_concepts(d)
    assert concepts.count("bad value") == 1
    assert len(concepts) <= 20
    assert "widget" in "|".join(concepts)


def test_influential_concepts_returned(debates_dir):
    debates = [
        _debate("Widget", angle="problem_solution", days_ago=1),
        _debate("Widget", angle="comparison", days_ago=2),
        _debate("Gadget", angle="comparison", days_ago=3),
    ]
    _write_debates(debates_dir, debates)
    pe = PulseEngine(debates_dir=debates_dir)
    pe.build_from_debates()
    top = pe.get_influential_concepts(top_n=5)
    assert top
    for item in top:
        assert "concept" in item
        assert "influence_score" in item
    scores = [i["influence_score"] for i in top]
    assert scores == sorted(scores, reverse=True)


def test_bridge_concepts_returned(debates_dir):
    debates = [
        _debate("Widget", angle="problem_solution", days_ago=1),
        _debate("Gadget", angle="comparison", days_ago=2),
        _debate("Thing", angle="honest_flaw", days_ago=3),
    ]
    _write_debates(debates_dir, debates)
    pe = PulseEngine(debates_dir=debates_dir)
    pe.build_from_debates()
    bridges = pe.get_bridge_concepts()
    for b in bridges:
        assert "bridge_score" in b
        assert "community" in b


def test_lookback_filters_old_debates(debates_dir):
    debates = [
        _debate("Old", days_ago=40),
        _debate("New", days_ago=1),
    ]
    _write_debates(debates_dir, debates)
    pe = PulseEngine(debates_dir=debates_dir, decay_days=30)
    stats = pe.build_from_debates()
    assert stats["debates_processed"] == 1
    labels = [c["concept"] for c in pe.get_influential_concepts(top_n=20)]
    assert not any("old" in l for l in labels)


def test_singleton():
    a = get_pulse_engine()
    b = get_pulse_engine()
    assert a is b
