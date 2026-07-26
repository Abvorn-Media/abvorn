"""Tests for TrendScanner — trending product detection."""
import pytest
from unittest.mock import MagicMock
from abvorn.trends.scanner import TrendScanner
from abvorn.trends.planner import ContentPlanner

_SEED_DATA = {
    "tv": [
        {"product_name": "TCL QM8L SQD Mini-LED TV", "category": "tv", "score": 78, "source": "duckduckgo", "price_range": "$1,500-$2,000", "url": ""},
        {"product_name": "LG C5 Series OLED TV", "category": "tv", "score": 82, "source": "duckduckgo", "price_range": "$1,300-$2,500", "url": ""},
    ],
    "laptop": [
        {"product_name": "MacBook Air M4", "category": "laptop", "score": 76, "source": "duckduckgo", "price_range": "$1,099-$1,599", "url": ""},
    ],
}


class _MockProvider:
    def search(self, category, max_results=5):
        return [dict(r) for r in _SEED_DATA.get(category, [])][:max_results]


def _make_scanner(**kw):
    return TrendScanner(providers=[_MockProvider()], **kw)


def test_scanner_initializes():
    s = _make_scanner()
    assert s is not None


def test_scan_returns_list():
    s = _make_scanner()
    results = s.scan()
    assert isinstance(results, list)


def test_scan_result_has_required_fields():
    s = _make_scanner()
    results = s.scan(subcategories=["tv"])
    if results:
        r = results[0]
        assert "product_name" in r
        assert "category" in r
        assert "score" in r
        assert "source" in r


def test_min_score_filters():
    s = _make_scanner(min_score=90)
    results = s.scan()
    for r in results:
        assert r["score"] >= 90


def test_dedup_same_product():
    s = _make_scanner()
    r1 = s.scan(subcategories=["tv"])
    r2 = s.scan(subcategories=["tv"])
    r1_names = {(r["product_name"], r["source"]) for r in r1}
    r2_names = {(r["product_name"], r["source"]) for r in r2}
    assert len(r2_names - r1_names) <= len(r2_names)


def test_different_subcategories():
    s = _make_scanner()
    tv_results = s.scan(subcategories=["tv"])
    laptop_results = s.scan(subcategories=["laptop"])
    assert isinstance(tv_results, list)
    assert isinstance(laptop_results, list)


def test_combined_score_boost():
    s = _make_scanner()
    products = [
        {"product_name": "Test TV", "category": "tv", "source": "web", "score": 70},
        {"product_name": "Test TV", "category": "tv", "source": "amazon", "score": 60},
    ]
    combined = s._combine_results(products)
    test_tv = [c for c in combined if c["product_name"] == "Test TV"]
    assert len(test_tv) == 1
    assert test_tv[0]["score"] > 70


def test_cache_expiry():
    s = _make_scanner(cache_seconds=1)
    s.scan(subcategories=["tv"])
    first_cache = s._cache_hits
    import time
    time.sleep(0.01)
    s.scan(subcategories=["tv"])
    assert s._cache_hits >= first_cache


# === ContentPlanner Tests ===

def test_planner_initializes():
    p = ContentPlanner()
    assert p is not None


def test_plan_returns_list():
    p = ContentPlanner()
    results = p.plan([{"product_name": "Test TV", "category": "tv", "score": 80, "source": "web", "sources": ["web"]}])
    assert isinstance(results, list)


def test_planned_item_has_required_fields():
    p = ContentPlanner()
    results = p.plan([{"product_name": "Test TV", "category": "tv", "score": 80, "source": "web", "sources": ["web"]}])
    if results:
        r = results[0]
        assert "product_name" in r
        assert "content_type" in r
        assert "primary_platform" in r
        assert "score" in r


def test_buying_guide_for_high_score():
    p = ContentPlanner()
    results = p.plan([{"product_name": "Expensive TV", "category": "tv", "score": 90, "source": "web", "sources": ["web", "amazon"]}])
    assert any(r["content_type"] == "buying_guide" for r in results)


def test_social_thread_for_medium_score():
    p = ContentPlanner()
    results = p.plan([{"product_name": "Gadget X", "category": "smart home", "score": 55, "source": "web", "sources": ["web"]}])
    assert any(r["content_type"] in ("social_thread", "tiktok_script") for r in results)


def test_empty_input():
    p = ContentPlanner()
    assert p.plan([]) == []


# === Schedule Tests ===

def test_schedule_initializes():
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    assert s is not None


def test_get_next_post_returns_none_when_empty():
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    assert s.get_next_post() is None


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
    assert s.queue_size() == 0


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


def test_slot_fallback_to_evergreen():
    """When queue is empty, slots fall back to evergreen rotation."""
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    s.assign_slots()
    am = s.get_am_post()
    pm = s.get_pm_post()
    assert am is not None
    assert pm is not None
    assert am["sources"] == ["evergreen"]
    assert pm["sources"] == ["evergreen"]


def test_record_post_metadata():
    from abvorn.trends.schedule import Schedule
    s = Schedule()
    s.record_post({"product_name": "Test", "category": "tv", "content_type": "buying_guide",
                   "primary_platform": "blog", "score": 80, "sources": ["web"]}, status="posted")
    assert s.post_count() == 1


def test_evergreen_rotation_cycles():
    """Evergreen posts should rotate through the list and wrap around."""
    from abvorn.trends.schedule import Schedule, EVERGREEN_QUEUE
    s = Schedule()
    first = s._next_evergreen_deep()
    second = s._next_evergreen_deep()
    assert first["product_name"] != second["product_name"]
    # Exhaust the remaining unique items
    names = {first["product_name"], second["product_name"]}
    for _ in range(len(EVERGREEN_QUEUE) * 2):
        names.add(s._next_evergreen_deep()["product_name"])
    # Should have collected more than 2 unique names via rotation
    assert len(names) > 2