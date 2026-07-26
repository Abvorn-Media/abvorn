# Predictive Trend Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect rising products before they peak by tracking signal velocity across recon providers, and boost TrendScanner scores for accelerating products.

**Architecture:** Lightweight score-boosting layer inside TrendScanner. SignalSnapshotter stores which products appeared per niche per source per scan in state DB. VelocityTracker computes frequency/novelty from snapshot history. ScoreBooster adjusts `_combine_results()` scores by up to +30 for products showing acceleration.

**Tech Stack:** Python, AbvornState (SQLite-backed key-value), existing TrendScanner, recon providers

## Global Constraints

- All signal data stored in state DB under `trend_signal:{niche}:{source}` keys
- Keep max 50 snapshots per key, purge oldest on each write
- Score boost capped at +30 per product
- All operations synchronous — no new async schedules
- Snapshotter/booster wrapped in try/except — failures never block content production
- All tests use mocked state, no real API calls

---

### Task 1: SignalSnapshotter

**Files:**
- Create: `abvorn/trends/predict/__init__.py`
- Create: `abvorn/trends/predict/snapshotter.py`
- Create: `tests/predict_test.py` (first 2 tests)

**Interfaces:**
- Consumes: `AbvornState` (get_meta/set_meta), `list[dict]` of provider results with `product_name`
- Produces: `SignalSnapshotter.store(niche, results, state) -> None` — persists snapshot to state DB

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/predict_test.py -v --tb=short`
Expected: FAIL with ImportError or module not found

- [ ] **Step 3: Write SignalSnapshotter**

Create `abvorn/trends/predict/__init__.py` (empty file).

Create `abvorn/trends/predict/snapshotter.py`:

```python
"""SignalSnapshotter — stores per-scan signal data for velocity tracking."""

import json, logging
from datetime import datetime

logger = logging.getLogger("abvorn.trends.predict.snapshotter")

MAX_SNAPSHOTS = 50


class SignalSnapshotter:
    """Records which products appeared per niche per source per scan."""

    def store(self, niche: str, results: list[dict], state) -> None:
        """Persist a snapshot of products found for this niche."""
        grouped = {}
        for r in results:
            source = r.get("source", "unknown")
            if source not in grouped:
                grouped[source] = set()
            grouped[source].add(r["product_name"])

        for source, products in grouped.items():
            key = f"trend_signal:{niche}:{source}"
            try:
                raw = state.get_meta(key, "[]")
                history = json.loads(raw)
                history.append({
                    "ts": datetime.now().isoformat(),
                    "products": sorted(products),
                    "count": len(products),
                })
                if len(history) > MAX_SNAPSHOTS:
                    history = history[-MAX_SNAPSHOTS:]
                state.set_meta(key, json.dumps(history))
            except Exception as e:
                logger.debug(f"Snapshot store failed for {key}: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/predict_test.py::test_snapshotter_stores_and_retrieves tests/predict_test.py::test_snapshotter_purges_old -v --tb=short`
Expected: PASS (2/2)

- [ ] **Step 5: Commit**

```bash
git add abvorn/trends/predict/ tests/predict_test.py
git commit -m "feat: SignalSnapshotter — stores per-scan product signals in state DB"
```

---

### Task 2: VelocityTracker + ScoreBooster

**Files:**
- Create: `abvorn/trends/predict/velocity.py`
- Create: `abvorn/trends/predict/booster.py`
- Modify: `tests/predict_test.py` (append 3 tests)

**Interfaces:**
- Consumes: `state` with `trend_signal:{niche}:{source}` keys, `list[dict]` of products from scanner
- Produces: `VelocityTracker.get_velocity(niche, state) -> dict[name -> {"frequency": int, "sources": int, "new": bool}]`
- Produces: `ScoreBooster.boost(products, velocity_data) -> list[dict]` with adjusted scores

- [ ] **Step 1: Write the failing tests**

Append to `tests/predict_test.py`:

```python
from abvorn.trends.predict.velocity import VelocityTracker
from abvorn.trends.predict.booster import ScoreBooster


def test_velocity_tracker_computes_frequency():
    state = MagicMock()
    history = json.dumps([
        {"ts": "2026-07-25T08:00", "products": ["Samsung S95H", "LG C5"], "count": 2},
        {"ts": "2026-07-25T10:00", "products": ["Samsung S95H", "LG C5", "TCL QM8L"], "count": 3},
        {"ts": "2026-07-25T12:00", "products": ["Samsung S95H", "LG C5"], "count": 2},
    ])
    state.get_meta.return_value = history
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
    assert lg["score"] == 60 + 5  # novelty only


def test_booster_does_not_boost_unknown():
    booster = ScoreBooster()
    velocity = {}
    products = [{"product_name": "Unknown Product", "category": "tv", "source": "duckduckgo", "score": 50}]
    boosted = booster.boost(products, velocity)
    assert boosted[0]["score"] == 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/predict_test.py -v --tb=short`
Expected: 2 old pass, 3 new FAIL (ImportError)

- [ ] **Step 3: Write VelocityTracker**

Create `abvorn/trends/predict/velocity.py`:

```python
"""VelocityTracker — computes product velocity from snapshot history."""

import json, logging

logger = logging.getLogger("abvorn.trends.predict.velocity")

LOOKBACK = 5
SIGNAL_PREFIX = "trend_signal:"


class VelocityTracker:
    """Analyzes snapshot history to compute frequency and novelty per product."""

    def get_velocity(self, niche: str, state) -> dict:
        """Return dict of product_name -> {frequency, sources, new}."""
        velocity = {}

        for source in ("duckduckgo", "amazon", "reddit", "googletrends"):
            key = f"{SIGNAL_PREFIX}{niche}:{source}"
            try:
                raw = state.get_meta(key, "[]")
                history = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                continue

            recent = history[-LOOKBACK:]
            for snap in recent:
                for name in snap.get("products", []):
                    key_name = name.lower().strip()
                    if key_name not in velocity:
                        velocity[key_name] = {"frequency": 0, "sources": set(), "first_ts": snap["ts"]}
                    velocity[key_name]["frequency"] += 1
                    velocity[key_name]["sources"].add(source)

        latest_ts = None
        for v in velocity.values():
            for source in v.get("sources", set()):
                key = f"{SIGNAL_PREFIX}{niche}:{source}"
                try:
                    raw = state.get_meta(key, "[]")
                    history = json.loads(raw) if isinstance(raw, str) else raw
                    if history:
                        ts = history[-1]["ts"]
                        if latest_ts is None or ts > latest_ts:
                            latest_ts = ts
                except Exception:
                    continue

        for name, v in velocity.items():
            v["sources"] = len(v["sources"])
            v["frequency"] = min(v["frequency"], LOOKBACK)
            v["new"] = latest_ts is not None and v.get("first_ts", "") == latest_ts and v["frequency"] == 1
            v.pop("first_ts", None)

        return velocity
```

- [ ] **Step 4: Write ScoreBooster**

Create `abvorn/trends/predict/booster.py`:

```python
"""ScoreBooster — boosts TrendScanner product scores based on velocity signals."""

import logging

logger = logging.getLogger("abvorn.trends.predict.booster")

BOOST_FREQUENCY_2 = 10
BOOST_FREQUENCY_4 = 20
BOOST_SOURCES_2 = 15
BOOST_NOVELTY = 5
BOOST_CAP = 30


class ScoreBooster:
    """Adjusts product scores based on velocity data from snapshot history."""

    def boost(self, products: list[dict], velocity: dict) -> list[dict]:
        """Return products with scores boosted by velocity signals."""
        boosted = []
        for p in products:
            p = dict(p)
            key = p["product_name"].lower().strip()
            v = velocity.get(key, {})
            if not v:
                boosted.append(p)
                continue

            bonus = 0
            freq = v.get("frequency", 0)
            if freq >= 4:
                bonus += BOOST_FREQUENCY_4
            elif freq >= 2:
                bonus += BOOST_FREQUENCY_2

            if v.get("sources", 0) >= 2:
                bonus += BOOST_SOURCES_2

            if v.get("new", False):
                bonus += BOOST_NOVELTY

            p["score"] = p.get("score", 50) + min(bonus, BOOST_CAP)
            p["velocity_bonus"] = min(bonus, BOOST_CAP)
            boosted.append(p)

        return boosted
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/predict_test.py -v --tb=short`
Expected: 5/5 PASS

- [ ] **Step 6: Commit**

```bash
git add abvorn/trends/predict/velocity.py abvorn/trends/predict/booster.py tests/predict_test.py
git commit -m "feat: VelocityTracker + ScoreBooster — frequency/novelty analysis and score boosting"
```

---

### Task 3: Wire into TrendScanner + Telegram + Daemon

**Files:**
- Modify: `abvorn/trends/scanner.py` (add state param, import and wire snapshotter + booster)
- Modify: `abvorn/deploy/notifier.py` (add `/predict [niche]` command)
- Modify: `abvorn/daemon.py` (wire scanner into notifier for trend-cycle daemons)
- Modify: `tests/predict_test.py` (append 1 integration test)

- [ ] **Step 1: Write the failing integration test**

```python
def test_scanner_wires_snapshotter_and_booster():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    called = {"snapshot": False}

    class _TrackingSnapshotter:
        def store(self, niche, results, s):
            called["snapshot"] = True

    from abvorn.trends.scanner import TrendScanner
    scanner = TrendScanner(providers=[], state=state)
    scanner._signal_snapshotter = _TrackingSnapshotter()
    results = scanner.scan(["tv"])
    assert called["snapshot"]
    assert isinstance(results, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/predict_test.py::test_scanner_wires_snapshotter_and_booster -v --tb=short`
Expected: FAIL (TypeError: unexpected keyword argument 'state')

- [ ] **Step 3: Wire into TrendScanner**

In `abvorn/trends/scanner.py`, add after line 5:
```python
from .predict.snapshotter import SignalSnapshotter
from .predict.velocity import VelocityTracker
from .predict.booster import ScoreBooster
```

Change `__init__` to accept `state=None` and initialize infrastructure:
```python
    def __init__(self, min_score: int = 40, cache_seconds: int = 86400,
                 subcategories: list = None, providers: list = None,
                 state=None):
        self.min_score = min_score
        self.cache_seconds = cache_seconds
        self.subcategories = subcategories or DEFAULT_SUBCATEGORIES
        self._cache = {}
        self._cache_hits = 0
        self._state = state
        self._recon_providers = providers or [
            DuckDuckGoSource(), AmazonSource(), RedditSource(), GoogleTrendsSource(),
        ]
        self._signal_snapshotter = SignalSnapshotter()
        self._velocity_tracker = VelocityTracker()
        self._score_booster = ScoreBooster()
```

In `scan()`, after `self._set_cache(cat, products)`:
```python
            try:
                self._signal_snapshotter.store(cat, products, self._state)
            except Exception:
                pass
```

In `scan()`, before `combined = self._combine_results(all_products)`:
```python
        if self._state:
            try:
                velocity = {}
                for cat in cats:
                    v = self._velocity_tracker.get_velocity(cat, self._state)
                    velocity.update(v)
                all_products = self._score_booster.boost(all_products, velocity)
            except Exception as e:
                logger.debug(f"Velocity boost failed: {e}")
```

- [ ] **Step 4: Add /predict command to notifier.py**

In `abvorn/deploy/notifier.py`, add to COMMANDS:
```python
        "/predict [niche]": "Show top rising products for a niche",
```

Add handler in `process_command()`, after the /help block:
```python
        if base_cmd == "/predict":
            lines = ["📈 <b>Predictive Trends</b>"]
            target_niche = arg.strip().lower() if arg else ""
            scanner = getattr(self, '_trend_scanner', None)
            if scanner and getattr(scanner, '_state', None):
                try:
                    from abvorn.trends.predict.velocity import VelocityTracker
                    vt = VelocityTracker()
                    niches = [target_niche] if target_niche else ["tv", "laptop", "robot vacuum", "monitor", "smart home"]
                    for niche in niches:
                        velocity = vt.get_velocity(niche, scanner._state)
                        rising = sorted(velocity.items(), key=lambda x: -x[1]["frequency"])[:3]
                        if rising:
                            lines.append(f"\n<b>{niche.title()}:</b>")
                            for name, v in rising:
                                icon = "🔥" if v["frequency"] >= 3 else "↑" if v["frequency"] >= 2 else "●"
                                lines.append(f"  {icon} {name.title()} (freq: {v['frequency']}, sources: {v['sources']})")
                    if len(lines) == 1:
                        lines.append("• No velocity data yet — run a trend cycle first")
                except Exception as e:
                    lines.append(f"• Error: {e}")
            else:
                lines.append("• Trend scanner not available")
            return "\n".join(lines)
```

- [ ] **Step 5: Wire TrendScanner into notifier in daemon.py**

In `abvorn/daemon.py`, in `OptimizationDaemon.__init__`, add after `self.trend_scanner = ...`:
```python
        if hasattr(self, 'notifier') and self.notifier:
            self.notifier._trend_scanner = self.trend_scanner
```

And pass `state` to TrendScanner creation in `OptimizationDaemon.__init__`:
Change `self.trend_scanner = TrendScanner()` to:
```python
        self.trend_scanner = TrendScanner(state=state)
```

- [ ] **Step 6: Run integration test**

Run: `pytest tests/predict_test.py::test_scanner_wires_snapshotter_and_booster -v --tb=short`
Expected: PASS

- [ ] **Step 7: Run all predict tests**

Run: `pytest tests/predict_test.py -v --tb=short`
Expected: 6/6 PASS

- [ ] **Step 8: Run full test suite**

Run: `pytest tests/ --ignore=tests/recon_test.py -q --tb=short`
Expected: All existing tests still pass

- [ ] **Step 9: Commit**

```bash
git add abvorn/trends/scanner.py abvorn/deploy/notifier.py abvorn/daemon.py tests/predict_test.py
git commit -m "feat: wire predictive trend detection into TrendScanner + Telegram /predict + daemon"
```

---

### Task 4: Update Roadmap

**Files:**
- Modify: `abvorn/brain/roadmap.md`

- [ ] **Step 1: Move Predictive Trend Detection to Tier 1 — Active Build**

In `abvorn/brain/roadmap.md`, update the Tier 2 entry for "Predictive Trend Detection":
- Move it from Tier 2 to Tier 1
- Update status to "Building (`abvorn/trends/predict/`)"
- Add: Tests: 6

- [ ] **Step 2: Commit**

```bash
git add abvorn/brain/roadmap.md
git commit -m "docs: move predictive trend detection to Tier 1 — active build"
```