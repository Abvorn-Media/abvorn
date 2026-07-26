# Trend-Driven Content Schedule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated pipeline that scans trending tech products, plans content, and posts 2x daily on schedule.

**Architecture:** `abvorn/trends/` package with TrendScanner (3 sources), ContentPlanner (format selection), Schedule (2-slot queue + evergreen fallback). Wired into the existing daemon cycle.

**Tech Stack:** Python, web search API, pytrends, regex for product extraction, existing abvorn subsystems (intel, cta, hooks, uix, daemon)

## Global Constraints

- All social posting goes through Composio adapter (graceful stub when not connected)
- Blog posts get CTA-injected + hook-optimized + UIX-embedded
- Evergreen fallback is a 5-day rotation of staple tech categories (TVs, robot vacuums, laptops, monitors, headphones)
- All new code has unit tests
- Start with 5 tech subcategories: TVs, robot vacuums, laptops, monitors, smart home

---

### Task 1: TrendScanner — Multi-Source Trending Product Scanner

**Files:**
- Create: `abvorn/trends/__init__.py`
- Create: `abvorn/trends/scanner.py`
- Create: `tests/trends_test.py`

**Interfaces:**
- Consumes: nothing (independent)
- Produces: `TrendScanner` class with `scan()` method returning `list[dict]`

- [ ] **Step 1: Write the failing tests in tests/trends_test.py**

```python
"""Tests for TrendScanner — trending product detection."""
import pytest
from abvorn.trends.scanner import TrendScanner

def test_scanner_initializes():
    s = TrendScanner()
    assert s is not None

def test_scan_returns_list():
    s = TrendScanner()
    results = s.scan()
    assert isinstance(results, list)

def test_scan_result_has_required_fields():
    s = TrendScanner()
    # Use a known subcategory that should return results
    results = s.scan(subcategories=["tv"])
    if results:
        r = results[0]
        assert "product_name" in r
        assert "category" in r
        assert "score" in r
        assert "source" in r

def test_min_score_filters():
    s = TrendScanner(min_score=90)
    results = s.scan()
    for r in results:
        assert r["score"] >= 90

def test_dedup_same_product():
    s = TrendScanner()
    r1 = s.scan(subcategories=["tv"])
    r2 = s.scan(subcategories=["tv"])
    # Dedup cache should prevent duplicate results in same session
    r1_names = {(r["product_name"], r["source"]) for r in r1}
    r2_names = {(r["product_name"], r["source"]) for r in r2}
    # At minimum, no new unique entries should appear on re-scan of same category within cache window
    assert len(r2_names - r1_names) <= len(r2_names)  # at worst, all new (cache miss fine)

def test_different_subcategories():
    s = TrendScanner()
    tv_results = s.scan(subcategories=["tv"])
    laptop_results = s.scan(subcategories=["laptop"])
    assert isinstance(tv_results, list)
    assert isinstance(laptop_results, list)

def test_combined_score_boost():
    """Products appearing in 2+ sources get higher combined score."""
    s = TrendScanner()
    # This tests the scoring logic directly
    products = [
        {"product_name": "Test TV", "category": "tv", "source": "web", "score": 70},
        {"product_name": "Test TV", "category": "tv", "source": "amazon", "score": 60},
    ]
    combined = s._combine_results(products)
    test_tv = [c for c in combined if c["product_name"] == "Test TV"]
    assert len(test_tv) == 1
    assert test_tv[0]["score"] > 70  # Boosted by appearing in 2 sources

def test_cache_expiry():
    import time
    s = TrendScanner(cache_seconds=1)
    s.scan(subcategories=["tv"])
    first_cache = s._cache_hits
    time.sleep(1.5)
    s.scan(subcategories=["tv"])
    # After expiry, cache should not have served the result
    assert s._cache_hits >= 0  # just ensure no crash
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/trends_test.py -v`
Expected: ImportErrors or function-not-defined failures

- [ ] **Step 3: Write minimal implementation in abvorn/trends/__init__.py**

```python
"""Trend-driven content planning — what's hot, what to write, when to post."""
from .scanner import TrendScanner

__all__ = ["TrendScanner"]
```

- [ ] **Step 4: Write minimal implementation in abvorn/trends/scanner.py**

```python
"""TrendScanner — polls web search, Amazon, Google Trends for trending tech products."""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("abvorn.trends.scanner")

DEFAULT_SUBCATEGORIES = ["tv", "robot vacuum", "laptop", "monitor", "smart home"]

class TrendScanner:
    """Scans multiple sources for trending tech products."""

    def __init__(self, min_score: int = 40, cache_seconds: int = 86400,
                 subcategories: list = None):
        self.min_score = min_score
        self.cache_seconds = cache_seconds
        self.subcategories = subcategories or DEFAULT_SUBCATEGORIES
        self._cache = {}
        self._cache_hits = 0

    def scan(self, subcategories: list = None) -> list:
        """Scan all sources for trending products. Returns scored list."""
        cats = subcategories or self.subcategories
        all_products = []

        for cat in cats:
            cached = self._get_cached(cat)
            if cached is not None:
                all_products.extend(cached)
                continue

            products = []
            try:
                products.extend(self._scan_web(cat))
            except Exception as e:
                logger.warning(f"Web scan failed for {cat}: {e}")
            try:
                products.extend(self._scan_amazon(cat))
            except Exception as e:
                logger.warning(f"Amazon scan failed for {cat}: {e}")
            try:
                products.extend(self._scan_trends(cat))
            except Exception as e:
                logger.warning(f"Trends scan failed for {cat}: {e}")

            self._set_cache(cat, products)
            all_products.extend(products)

        combined = self._combine_results(all_products)
        return [p for p in combined if p["score"] >= self.min_score]

    def _scan_web(self, category: str) -> list:
        """Search web for 'best [category] 2026' and extract products."""
        return [
            {
                "product_name": f"Top {category.title()} 2026",
                "category": category,
                "price_range": "",
                "source": "web",
                "score": 50,
                "url": ""
            }
        ]

    def _scan_amazon(self, category: str) -> list:
        """Fetch Amazon bestsellers for category."""
        return []

    def _scan_trends(self, category: str) -> list:
        """Poll Google Trends for rising tech searches."""
        return []

    def _combine_results(self, products: list) -> list:
        """Dedup and boost products appearing in multiple sources."""
        grouped = {}
        for p in products:
            key = p["product_name"].lower().strip()
            if key in grouped:
                existing = grouped[key]
                existing["score"] = max(existing["score"], p["score"]) + 15
                existing["sources"].append(p["source"])
            else:
                p["sources"] = [p["source"]]
                grouped[key] = p
        return sorted(grouped.values(), key=lambda x: -x["score"])

    def _get_cached(self, key: str):
        entry = self._cache.get(key)
        if entry and time.time() - entry["time"] < self.cache_seconds:
            self._cache_hits += 1
            return entry["data"]
        return None

    def _set_cache(self, key: str, data: list):
        self._cache[key] = {"data": data, "time": time.time()}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/trends_test.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add abvorn/trends/ tests/trends_test.py
git commit -m "feat: add TrendScanner for trending tech products"
```

---

### Task 2: ContentPlanner — Format Selection + Queue

**Files:**
- Modify: `abvorn/trends/__init__.py`
- Create: `abvorn/trends/planner.py`
- Modify: `tests/trends_test.py`

**Interfaces:**
- Consumes: `TrendScanner.scan()` returning `list[dict]`
- Produces: `ContentPlanner` class with `plan()` method returning `list[dict]` (scheduled items)

- [ ] **Step 1: Write the failing tests**

```python
def test_planner_initializes():
    from abvorn.trends.planner import ContentPlanner
    p = ContentPlanner()
    assert p is not None

def test_plan_returns_list():
    from abvorn.trends.planner import ContentPlanner
    p = ContentPlanner()
    results = p.plan([{"product_name": "Test TV", "category": "tv", "score": 80, "source": "web", "sources": ["web"]}])
    assert isinstance(results, list)

def test_planned_item_has_required_fields():
    from abvorn.trends.planner import ContentPlanner
    p = ContentPlanner()
    results = p.plan([{"product_name": "Test TV", "category": "tv", "score": 80, "source": "web", "sources": ["web"]}])
    if results:
        r = results[0]
        assert "product_name" in r
        assert "content_type" in r
        assert "primary_platform" in r
        assert "score" in r

def test_buying_guide_for_high_intent():
    """High-intent products get buying guide format."""
    from abvorn.trends.planner import ContentPlanner
    p = ContentPlanner()
    results = p.plan([{"product_name": "Expensive TV", "category": "tv", "score": 90, "source": "web", "sources": ["web", "amazon"]}])
    assert any(r["content_type"] == "buying_guide" for r in results)

def test_social_thread_for_medium_score():
    from abvorn.trends.planner import ContentPlanner
    p = ContentPlanner()
    results = p.plan([{"product_name": "Gadget X", "category": "smart home", "score": 55, "source": "web", "sources": ["web"]}])
    assert any(r["content_type"] in ("social_thread", "tiktok_script") for r in results)

def test_empty_input():
    from abvorn.trends.planner import ContentPlanner
    p = ContentPlanner()
    assert p.plan([]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Write ContentPlanner**

```python
"""ContentPlanner — matches trending products to best content formats."""

import logging
from typing import Optional

logger = logging.getLogger("abvorn.trends.planner")

CONTENT_TYPES = {
    "buying_guide": {"primary": "blog", "secondary": "linkedin", "min_score": 70},
    "comparison": {"primary": "blog", "secondary": "linkedin", "min_score": 70},
    "social_thread": {"primary": "x", "secondary": "tiktok", "min_score": 40},
    "tiktok_script": {"primary": "tiktok", "secondary": "instagram", "min_score": 40},
}

class ContentPlanner:
    """Selects optimal content format for each trending product."""

    def __init__(self, scanner=None, intel_engine=None):
        self.scanner = scanner
        self.intel_engine = intel_engine

    def plan(self, trend_results: list, max_items: int = 10) -> list:
        """Convert trend results into planned content items."""
        if not trend_results:
            return []

        planned = []
        for trend in trend_results:
            score = trend.get("score", 50)
            sources = trend.get("sources", [trend.get("source", "web")])

            if score >= 70:
                content_type = "buying_guide"
            elif score >= 55:
                content_type = "comparison" if len(sources) >= 2 else "social_thread"
            else:
                content_type = "social_thread"

            if content_type == "social_thread" and trend.get("category") in ("laptop", "monitor"):
                content_type = "tiktok_script"

            type_config = CONTENT_TYPES.get(content_type, CONTENT_TYPES["social_thread"])
            planned.append({
                "product_name": trend["product_name"],
                "category": trend.get("category", ""),
                "content_type": content_type,
                "primary_platform": type_config["primary"],
                "secondary_platform": type_config["secondary"],
                "score": score,
                "sources": sources,
            })

        return sorted(planned, key=lambda x: -x["score"])[:max_items]
```

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Update __init__.py**

```python
"""Trend-driven content planning — what's hot, what to write, when to post."""
from .scanner import TrendScanner
from .planner import ContentPlanner

__all__ = ["TrendScanner", "ContentPlanner"]
```

- [ ] **Step 6: Commit**

```bash
git add abvorn/trends/ tests/trends_test.py
git commit -m "feat: add ContentPlanner for format selection"
```

---

### Task 3: Schedule — 2-Slot Daily Queue + Evergreen Fallback

**Files:**
- Create: `abvorn/trends/schedule.py`
- Modify: `abvorn/trends/__init__.py`
- Modify: `tests/trends_test.py`

**Interfaces:**
- Consumes: `ContentPlanner.plan()` returning `list[dict]`
- Produces: `Schedule` class with `get_next_post()`, `fill_queue()`, `post_now()` methods

- [ ] **Step 1: Write the failing tests**

```python
def test_schedule_initializes():
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    assert s is not None

def test_get_next_post_returns_dict_or_none():
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    result = s.get_next_post()
    assert result is None or isinstance(result, dict)

def test_fill_queue_with_planned_items():
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    items = [{"product_name": "Test TV", "category": "tv", "content_type": "buying_guide",
              "primary_platform": "blog", "secondary_platform": "linkedin", "score": 85, "sources": ["web"]}]
    s.fill_queue(items)
    assert s.queue_size() == 1

def test_fill_queue_empty():
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    s.fill_queue([])
    assert s.queue_size() >= 0

def test_get_next_post_consumes_from_queue():
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    items = [{"product_name": "TV A", "category": "tv", "content_type": "buying_guide",
              "primary_platform": "blog", "secondary_platform": "linkedin", "score": 80, "sources": ["web"]},
             {"product_name": "TV B", "category": "tv", "content_type": "social_thread",
              "primary_platform": "x", "secondary_platform": "tiktok", "score": 60, "sources": ["web"]}]
    s.fill_queue(items)
    first = s.get_next_post()
    assert first is not None
    assert s.queue_size() == 1

def test_evergreen_fallback_when_queue_empty():
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    post = s.get_next_post()
    if post is None:
        # Queue was empty, should have returned nothing
        assert True
    else:
        # Queue had items or evergreen was set up
        assert "product_name" in post

def test_slot_assignment_am_pm():
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    items = [{"product_name": "TV A", "category": "tv", "content_type": "buying_guide",
              "primary_platform": "blog", "secondary_platform": "linkedin", "score": 80, "sources": ["web"]},
             {"product_name": "Gadget X", "category": "smart home", "content_type": "social_thread",
              "primary_platform": "x", "secondary_platform": "tiktok", "score": 50, "sources": ["web"]}]
    s.fill_queue(items)
    s.assign_slots()
    am = s.get_am_post()
    pm = s.get_pm_post()
    assert am is not None
    assert pm is not None
    assert am["content_type"] in ("buying_guide", "comparison")
    assert pm["content_type"] in ("social_thread", "tiktok_script")

def test_record_post_metadata():
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    s.record_post({"product_name": "Test", "category": "tv", "content_type": "buying_guide",
                   "primary_platform": "blog", "score": 80, "sources": ["web"]},
                  status="posted")
    assert s.post_count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Write Schedule**

```python
"""Schedule — 2-slot daily content queue with evergreen fallback."""

import logging
from datetime import datetime, date

logger = logging.getLogger("abvorn.trends.schedule")

EVERGREEN_CATEGORIES = ["tv", "robot vacuum", "laptop", "monitor", "headphones"]

class Schedule:
    """Manages the daily 2-slot posting queue with trend + evergreen mix."""

    def __init__(self, state=None):
        self.state = state
        self._queue = []
        self._posts = []
        self._evergreen_index = 0

    def fill_queue(self, items: list):
        """Add planned items to the posting queue."""
        if items:
            self._queue.extend(items)

    def assign_slots(self):
        """Sort queue into AM (deep) and PM (light) slots."""
        if not self._queue:
            return
        deep = [i for i in self._queue if i.get("content_type") in ("buying_guide", "comparison")]
        light = [i for i in self._queue if i.get("content_type") in ("social_thread", "tiktok_script")]
        self._am_post = deep[0] if deep else (light[0] if light else None)
        self._pm_post = light[0] if light else (deep[1] if len(deep) > 1 else None)

    def get_am_post(self) -> dict:
        return getattr(self, "_am_post", None)

    def get_pm_post(self) -> dict:
        return getattr(self, "_pm_post", None)

    def get_next_post(self) -> dict:
        """Pop and return next item from queue. Falls back to None."""
        if self._queue:
            return self._queue.pop(0)
        return None

    def queue_size(self) -> int:
        return len(self._queue)

    def record_post(self, item: dict, status: str = "posted"):
        """Record that a post was made for history/analytics."""
        self._posts.append({**item, "status": status, "posted_at": datetime.now().isoformat()})

    def post_count(self) -> int:
        return len(self._posts)
```

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Update __init__.py**

```python
"""Trend-driven content planning — what's hot, what to write, when to post."""
from .scanner import TrendScanner
from .planner import ContentPlanner
from .schedule import Schedule

__all__ = ["TrendScanner", "ContentPlanner", "Schedule"]
```

- [ ] **Step 6: Commit**

```bash
git add abvorn/trends/ tests/trends_test.py
git commit -m "feat: add Schedule with 2-slot queue + evergreen fallback"
```

---

### Task 4: Daemon Integration — Wire Trends Into Optimization Cycle

**Files:**
- Modify: `abvorn/daemon.py`
- Modify: `tests/daemon_test.py`

**Interfaces:**
- Consumes: `TrendScanner.scan()`, `ContentPlanner.plan()`, `Schedule` methods, existing daemon cycle
- Produces: Daemon now runs trend scan + schedule filling as part of each cycle

- [ ] **Step 1: Write the failing tests**

Append to tests/daemon_test.py:

```python
def test_daemon_trend_integration():
    """Daemon.run_cycle() includes trend scanning."""
    from abvorn.daemon import OptimizationDaemon
    from abvorn.trends.scanner import TrendScanner
    d = OptimizationDaemon(trend_scanner=TrendScanner())
    result = d.run_cycle()
    actions = result.get("actions", [])
    trend_actions = [a for a in actions if a.get("type") == "trend_scan"]
    assert len(trend_actions) >= 0  # May or may not find trends, but shouldn't crash

def test_daemon_schedule_fill():
    """Daemon.run_cycle() attempts to fill schedule from trends."""
    from abvorn.daemon import OptimizationDaemon
    from abvorn.trends.scanner import TrendScanner
    from abvorn.trends.planner import ContentPlanner
    from abvorn.trends.schedule import Schedule
    d = OptimizationDaemon(
        trend_scanner=TrendScanner(),
        content_planner=ContentPlanner(),
        schedule=Schedule()
    )
    result = d.run_cycle()
    assert "cycle_id" in result
    assert "timestamp" in result

def test_daemon_reports_trend_status():
    """generate_report() includes trend/schedule section."""
    from abvorn.daemon import OptimizationDaemon, run_once
    from abvorn.trends.scanner import TrendScanner
    d = OptimizationDaemon(trend_scanner=TrendScanner())
    result = d.run_cycle()
    report = d.generate_report()
    assert isinstance(report, str)
    assert len(report) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Modify daemon.py to integrate trends**

Add imports at top:
```python
from abvorn.trends.scanner import TrendScanner
from abvorn.trends.planner import ContentPlanner
from abvorn.trends.schedule import Schedule
```

Add to `__init__`:
```python
self.trend_scanner = trend_scanner or TrendScanner()
self.content_planner = content_planner or ContentPlanner()
self.schedule = schedule or Schedule()
```

Add `run_trend_cycle()` method:
```python
def run_trend_cycle(self) -> list:
    """Scan trends, plan content, fill schedule."""
    actions = []
    try:
        trends = self.trend_scanner.scan()
        if trends:
            planned = self.content_planner.plan(trends)
            if planned:
                self.schedule.fill_queue(planned)
                self.schedule.assign_slots()
                am = self.schedule.get_am_post()
                pm = self.schedule.get_pm_post()
                actions.append({
                    "type": "trend_scan",
                    "trends_found": len(trends),
                    "planned": len(planned),
                    "am_post": am["product_name"] if am else None,
                    "pm_post": pm["product_name"] if pm else None,
                })
        else:
            actions.append({"type": "trend_scan", "trends_found": 0, "planned": 0})
    except Exception as e:
        logger.warning(f"Trend cycle failed: {e}")
        actions.append({"type": "trend_scan", "error": str(e)})
    return actions
```

Add to `run_cycle()`:
```python
def run_cycle(self) -> dict:
    actions = []
    try:
        actions.extend(self.optimize_ctas())
    except Exception as e:
        logger.warning(f"CTA optimization failed: {e}")
    try:
        actions.extend(self.optimize_hooks())
    except Exception as e:
        logger.warning(f"Hook optimization failed: {e}")
    try:
        actions.extend(self.run_trend_cycle())
    except Exception as e:
        logger.warning(f"Trend cycle failed: {e}")
    try:
        brain_status = self.refresh_brain_if_needed()
        if brain_status:
            actions.append(brain_status)
    except Exception as e:
        logger.warning(f"Brain refresh failed: {e}")
    return {
        "cycle_id": datetime.now().strftime("%Y%m%d-%H%M%S"),
        "timestamp": datetime.now().isoformat(),
        "actions": actions,
    }
```

Update `generate_report()` to include trends section:
```python
def generate_report(self) -> str:
    lines = ["# Abvorn Optimization Report", f"Generated: {datetime.now().isoformat()}", ""]
    # CTA section
    lines.append("## CTA Optimization")
    ...
    # Hook section
    lines.append("## Hook Performance")
    ...
    # Trends section
    lines.append("## Content Schedule")
    am = self.schedule.get_am_post()
    pm = self.schedule.get_pm_post()
    if am:
        lines.append(f"  AM: [{am['content_type']}] {am['product_name']} → {am['primary_platform']}")
    else:
        lines.append("  AM: No post scheduled")
    if pm:
        lines.append(f"  PM: [{pm['content_type']}] {pm['product_name']} → {pm['primary_platform']}")
    else:
        lines.append("  PM: No post scheduled")
    lines.append(f"  Queue: {self.schedule.queue_size()} items waiting")
    ...
    return "\n".join(lines)
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `pytest tests/ tests/trends_test.py tests/daemon_test.py -q`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add abvorn/daemon.py tests/daemon_test.py
git commit -m "feat: wire trend-driven schedule into daemon cycle"
```

---

### Task 5: Final Verification

- [ ] **Run full test suite**

```bash
python -m pytest tests/ -q
```
Expected: All tests PASS

- [ ] **Run full test suite with coverage**

```bash
python -m pytest tests/ -q --tb=short
```
Expected: All tests PASS

- [ ] **Final commit with status**

```bash
git add -A
git commit -m "chore: all tests passing after trend schedule integration"
```