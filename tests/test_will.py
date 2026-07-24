import pytest, json
from abvorn.will import Will


def test_default_mission():
    """Should have a sensible default mission."""
    w = Will()
    assert len(w.mission) > 10
    assert "help" in w.mission.lower()


def test_mission_check_blocks_bad():
    """Should block actions that violate mission."""
    w = Will()
    assert w.mission_check("how to trick amazon algorithm") is False
    assert w.mission_check("best wireless headphones under $100") is True


def test_generate_goals_returns_list():
    """Should generate at least 2 goals."""
    w = Will()
    goals = w.generate_goals()
    assert len(goals) >= 2
    assert all("type" in g for g in goals)
    assert all("priority" in g for g in goals)


def test_curiosity_pick_mixes_exploit_and_explore():
    """Should return items with high-scorers first, but include low-scorers."""
    w = Will()
    w.curiosity_score = 0.5
    items = [
        {"name": "A", "score": 0.9},
        {"name": "B", "score": 0.8},
        {"name": "C", "score": 0.3},
        {"name": "D", "score": 0.2},
    ]
    picked = w.curiosity_pick(items)
    assert len(picked) == 4
    assert picked[0]["name"] == "A"  # highest score first


def test_reflection_adjusts_curiosity():
    """Should increase curiosity on good revenue, decrease on bad."""
    w = Will()
    w.curiosity_score = 0.3

    w.reflect(cycles_completed=10, revenue=500.0, engagement=0.1)
    assert w.curiosity_score > 0.3  # increased

    w.curiosity_score = 0.3
    w.reflect(cycles_completed=10, revenue=5.0, engagement=0.01)
    assert w.curiosity_score < 0.3  # decreased