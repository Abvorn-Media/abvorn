"""Regression tests: run_cycle research must survive an Open Web Ninja outage.

The content cycle sat broken for weeks because ``research_products`` returned
``None`` when Open Web Ninja rate-limited (429) and ``main`` then did
``sys.exit(1)``. Two things are pinned here:

* ``research_products`` falls back to the shared provider chain and keeps only
  *buyable* products (ASIN/photo), so a rate-limited scrape degrades to a real
  page instead of a fabricated placeholder one.
* a cycle with no buyable products is *skipped* (exit 0), not failed.
"""

import pytest

import run_cycle
from run_cycle import _research_fallback, research_products

BUYABLE = [
    {
        "name": 'Roku 55" Select Series Smart TV',
        "price": "$349.99",
        "image": "https://m.media-amazon.com/i/roku.jpg",
        "url": "https://www.amazon.com/dp/B0C1TV55IN?tag=x-20",
        "asin": "B0C1TV55IN",
    },
    {
        "name": "Samsung 65-Inch Crystal UHD U8000H",
        "price": "$899.99",
        "image": "https://m.media-amazon.com/i/samsung.jpg",
        "url": "https://www.amazon.com/dp/B0CSAMU800?tag=x-20",
        "asin": "B0CSAMU800",
    },
]

# The shape Tavily / the LLM fallback produce: no ASIN, no photo.
PLACEHOLDER = [
    {
        "name": "Sony Bravia XR X90L 65-inch OLED",
        "price": "$1299.99",
        "description": "The best 65-inch OLED we tested.",
        "features": ["120Hz"],
    },
]


class FakeResp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _patch_own(monkeypatch, response):
    monkeypatch.setattr(run_cycle, "_own_load_cache", lambda: {})
    monkeypatch.setattr(run_cycle, "_own_save_cache", lambda c: None)
    monkeypatch.setattr(run_cycle, "get_secrets", lambda: {"OPENWEB_NINJA_KEY": "k" * 20})
    monkeypatch.setattr(run_cycle, "http_requests", type("R", (), {"get": staticmethod(lambda *a, **k: response)}))


# --- research_products fallback wiring -------------------------------------

def test_429_falls_back_to_buyable_products(monkeypatch):
    """A 429 must not end the cycle: the fallback provider's products are used."""
    _patch_own(monkeypatch, FakeResp(429))
    monkeypatch.setattr(run_cycle, "_research_fallback", lambda niche: BUYABLE)

    products = research_products("tv")

    assert [p["asin"] for p in products] == ["B0C1TV55IN", "B0CSAMU800"]


def test_empty_own_payload_falls_back(monkeypatch):
    """HTTP 200 with an empty product list is still an outage."""
    _patch_own(monkeypatch, FakeResp(200, {"data": {"products": []}}))
    monkeypatch.setattr(run_cycle, "_research_fallback", lambda niche: BUYABLE)

    assert research_products("tv") == BUYABLE


def test_no_fallback_products_returns_empty(monkeypatch):
    """Every provider empty -> [] (skip), never None-with-a-crash contract."""
    _patch_own(monkeypatch, FakeResp(429))
    monkeypatch.setattr(run_cycle, "_research_fallback", lambda niche: [])

    assert research_products("tv") == []


def test_missing_key_falls_back(monkeypatch):
    monkeypatch.setattr(run_cycle, "_own_load_cache", lambda: {})
    monkeypatch.setattr(run_cycle, "_own_save_cache", lambda c: None)
    monkeypatch.setattr(run_cycle, "get_secrets", lambda: {})
    monkeypatch.setattr(run_cycle, "_research_fallback", lambda niche: BUYABLE)

    assert research_products("tv") == BUYABLE


def test_fallback_result_is_cached(monkeypatch):
    """A fallback hit is cached so the next cycle does not re-hit the providers."""
    saved = {}
    monkeypatch.setattr(run_cycle, "_own_load_cache", lambda: {})
    monkeypatch.setattr(run_cycle, "_own_save_cache", lambda c: saved.update(c))
    monkeypatch.setattr(run_cycle, "get_secrets", lambda: {"OPENWEB_NINJA_KEY": "k" * 20})
    monkeypatch.setattr(run_cycle, "http_requests",
                        type("R", (), {"get": staticmethod(lambda *a, **k: FakeResp(429))}))
    monkeypatch.setattr(run_cycle, "_research_fallback", lambda niche: BUYABLE)

    research_products("tv")

    key = run_cycle._own_cache_key("best tv", "amazon")
    assert saved.get(key) == BUYABLE


# --- the buyable filter in _research_fallback -------------------------------

def test_fallback_keeps_only_buyable(monkeypatch):
    monkeypatch.setattr("abvorn.agents.researcher.research_niche",
                        lambda niche, router=None: BUYABLE + PLACEHOLDER)

    result = _research_fallback("tv")

    assert [p["asin"] for p in result] == ["B0C1TV55IN", "B0CSAMU800"]


def test_fallback_discards_all_placeholder(monkeypatch):
    monkeypatch.setattr("abvorn.agents.researcher.research_niche",
                        lambda niche, router=None: PLACEHOLDER)

    assert _research_fallback("tv") == []


def test_fallback_survives_provider_exception(monkeypatch):
    def _boom(niche, router=None):
        raise RuntimeError("all providers down")

    monkeypatch.setattr("abvorn.agents.researcher.research_niche", _boom)

    assert _research_fallback("tv") == []


# --- main() skips instead of exiting non-zero -------------------------------

class _FakeChangeMgr:
    def create_change(self, **kw):
        return "cid"


class _FakeEngine:
    workflows = {}


class _FakeDAG:
    def __init__(self):
        self.priority_weights = {}


def test_main_skips_when_no_products(monkeypatch):
    """No buyable products returns a skip dict and never sys.exit(1)s."""
    monkeypatch.delenv("LIBRARY_PATH", raising=False)
    monkeypatch.setattr(run_cycle, "get_secrets", lambda: {})
    monkeypatch.setattr(run_cycle, "create_ai_sql", lambda: object())
    monkeypatch.setattr("src.content_generation.set_ai_sql", lambda x: None)
    monkeypatch.setattr(run_cycle, "create_workflow_engine", lambda: _FakeEngine())
    monkeypatch.setattr(run_cycle, "create_feedback_loop", lambda x: None)
    monkeypatch.setattr(run_cycle, "create_change_manager", lambda: _FakeChangeMgr())
    monkeypatch.setattr(run_cycle, "DAGScheduler", _FakeDAG)
    monkeypatch.setattr(run_cycle, "load_state",
                        lambda: {"niches": [{"slug": "tv", "name": "TV", "posts": 0}]})
    monkeypatch.setattr(run_cycle, "pick_niche", lambda state, ga4_scores=None: {"slug": "tv", "name": "TV", "posts": 0})
    monkeypatch.setattr(run_cycle, "research_products", lambda niche: [])

    result = run_cycle.main(forced_niche="tv")

    assert result == {"status": "skipped", "niche": "tv", "reason": "no_products"}
