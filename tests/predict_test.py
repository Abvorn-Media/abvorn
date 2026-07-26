"""Tests for predictive trend detection — signal snapshots, velocity, scoring."""
import pytest, json
from unittest.mock import MagicMock
from abvorn.trends.predict.snapshotter import SignalSnapshotter


def test_snapshotter_stores_and_retrieves():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    snapshotter = SignalSnapshotter()
    results = [
        {"product_name": "Samsung S95H", "source": "duckduckgo", "score": 80},
        {"product_name": "LG C5", "source": "duckduckgo", "score": 75},
    ]
    snapshotter.store("tv", results, state)
    assert state.set_meta.called
    stored_key = state.set_meta.call_args[0][0]
    assert "trend_signal:" in stored_key


def test_snapshotter_purges_old():
    state = MagicMock()
    old_snapshots = [{"ts": "2026-01-01T00:00", "products": ["Old Product"], "count": 1}] * 60
    state.get_meta.return_value = json.dumps(old_snapshots)
    snapshotter = SignalSnapshotter()
    snapshotter.store("tv", [{"product_name": "New", "source": "duckduckgo", "score": 80}], state)
    stored = json.loads(state.set_meta.call_args[0][1])
    assert len(stored) <= 50


from abvorn.trends.predict.velocity import VelocityTracker
from abvorn.trends.predict.booster import ScoreBooster


def test_velocity_tracker_computes_frequency():
    state = MagicMock()
    history = [
        {"ts": "2026-07-25T08:00", "products": ["Samsung S95H", "LG C5"], "count": 2},
        {"ts": "2026-07-25T10:00", "products": ["Samsung S95H", "LG C5", "TCL QM8L"], "count": 3},
        {"ts": "2026-07-25T12:00", "products": ["Samsung S95H", "LG C5"], "count": 2},
    ]

    def get_meta_side_effect(key, default="[]"):
        if "trend_signal:tv:duckduckgo" in str(key):
            return json.dumps(history)
        return "[]"
    state.get_meta.side_effect = get_meta_side_effect

    vt = VelocityTracker()
    velocity = vt.get_velocity("tv", state)
    assert velocity["samsung s95h"]["frequency"] == 3
    assert velocity["tcl qm8l"]["frequency"] == 1
    assert velocity["tcl qm8l"]["new"] is True


def test_booster_boosts_frequent_products():
    booster = ScoreBooster()
    velocity = {
        "samsung s95h": {"frequency": 3, "sources": 2, "new": False},
        "lg c5": {"frequency": 1, "sources": 1, "new": True},
    }
    products = [
        {"product_name": "Samsung S95H", "category": "tv", "source": "duckduckgo", "score": 70},
        {"product_name": "LG C5", "category": "tv", "source": "duckduckgo", "score": 60},
    ]
    boosted = booster.boost(products, velocity)
    samsung = [p for p in boosted if p["product_name"] == "Samsung S95H"][0]
    lg = [p for p in boosted if p["product_name"] == "LG C5"][0]
    assert samsung["score"] > 70
    assert lg["score"] == 60 + 5


def test_booster_does_not_boost_unknown():
    booster = ScoreBooster()
    velocity = {}
    products = [{"product_name": "Unknown Product", "category": "tv", "source": "duckduckgo", "score": 50}]
    boosted = booster.boost(products, velocity)
    assert boosted[0]["score"] == 50


def test_trend_scanner_wired_with_state():
    from abvorn.trends.scanner import TrendScanner
    state = MagicMock()
    state.get_meta.return_value = "[]"
    scanner = TrendScanner(state=state, providers=[])
    results = scanner.scan(["tv"])
    assert isinstance(results, list)
    assert scanner._state is state