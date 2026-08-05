"""Tests for the Oliver Henry Title Engine."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from abvorn.core.title_engine import (
    TEMPLATES,
    TitleEngine,
    get_title_engine,
)


def _carousel(product="Sony WH-1000XM6", overall=8.7, label="Excellent",
              breakdown=None, price="$350", category=""):
    return {
        "product_name": product,
        "verdict": {
            "overall": overall,
            "label": label,
            "breakdown": breakdown or {"Sound": 9.2, "Comfort": 8.8, "Battery": 7.5},
        },
        "price": price,
        "category": category,
    }


@pytest.fixture()
def engine(tmp_path):
    return TitleEngine(history_path=str(tmp_path / "title_perf.json"))


def test_all_templates_are_fillable(engine):
    """Every template must produce a non-empty title with the product in it."""
    carousel = _carousel()
    variants = engine.generate_titles(carousel, platform="tiktok", count=len(TEMPLATES) + 1)
    assert len(variants) == len(TEMPLATES)
    for v in variants:
        assert v["title"]
        has_product_slot = "[product]" in TEMPLATES[v["template"]]["template"]
        if has_product_slot:
            assert "Sony WH-1000XM6" in v["title"]


def test_variants_are_sorted_by_impact(engine):
    variants = engine.generate_titles(_carousel(), platform="tiktok", count=5)
    impacts = [v["estimated_impact"] for v in variants]
    assert impacts == sorted(impacts, reverse=True)


def test_count_limit_respected(engine):
    variants = engine.generate_titles(_carousel(), platform="linkedin", count=3)
    assert len(variants) == 3


def test_deterministic_output(engine):
    a = engine.generate_titles(_carousel(), platform="tiktok")
    b = engine.generate_titles(_carousel(), platform="tiktok")
    assert [v["title"] for v in a] == [v["title"] for v in b]


def test_platform_adaptation_truncates(engine):
    variants = engine.generate_titles(_carousel(), platform="tiktok")
    for v in variants:
        assert len(v["title"]) <= 63


def test_record_performance_bumps_learned_weight(engine, tmp_path):
    carousel = _carousel()
    before = engine.generate_titles(carousel, platform="tiktok")
    winner = before[0]["template"]
    engine.record_performance(platform="tiktok", template=winner, won=True)
    after = engine.generate_titles(carousel, platform="tiktok")
    # the learned boost persists and the winner stays on top
    assert engine._learned[winner]["tiktok"] > 0
    assert after[0]["template"] == winner


def test_persistence_across_instances(tmp_path):
    path = str(tmp_path / "title_perf.json")
    e1 = TitleEngine(history_path=path)
    e1.record_performance(platform="x", template="brutal_truth", won=True)
    e2 = TitleEngine(history_path=path)
    assert e2._learned["brutal_truth"]["x"] > 0


def test_unknown_template_ignored(engine):
    engine.record_performance(platform="tiktok", template="not_a_template", won=True)
    assert "not_a_template" not in engine._learned


def test_empty_carousel_never_raises(engine):
    variants = engine.generate_titles({}, platform="tiktok")
    assert isinstance(variants, list)


def test_verdict_drives_criticism(engine):
    low = engine._build_context(_carousel(overall=5.5))["criticism"]
    high = engine._build_context(_carousel(overall=9.2))["criticism"]
    assert "waste" in low
    assert high != low


def test_best_criterion_becomes_reveal(engine):
    ctx = engine._build_context(_carousel(breakdown={"Sound": 9.2, "Battery": 7.0}))
    assert ctx["reveal"] == "Sound"


def test_price_injection(engine):
    ctx = engine._build_context(_carousel(price="$600"))
    assert "$600" in ctx["price"]


def test_singleton_returns_same_instance():
    assert get_title_engine() is get_title_engine()
