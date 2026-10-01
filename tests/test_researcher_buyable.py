"""Regression tests: research_niche must produce BUYABLE products.

Every product research_niche returns has to survive
``_products_are_placeholder()``, or the deploy boundary refuses the page and
the niche never publishes. The tv niche sat refused with "1 product(s) and
none carry an ASIN" while Tavily was happily returning plausible TVs — because
the Tavily and LLM-knowledge prompts never ask for an ASIN or a photo.
"""

import json

import pytest

import abvorn.agents.researcher as researcher
from abvorn.agents.orchestrator import _products_are_placeholder
from abvorn.agents.researcher import research_niche
from abvorn.core.amazon_catalog import AmazonCatalogClient, _cache_key, _clean_name

# Exactly what Tavily extract_products / the AI-knowledge fallback produce.
UNBUYABLE = json.dumps([
    {
        "name": "Sony Bravia XR X90L 65-inch OLED",
        "price": "$1299.99",
        "description": "The best 65-inch OLED we tested.",
        "features": ["120Hz", "HDMI 2.1"],
        "category": "best_overall",
        "source_url": "https://www.rtings.com/tv/reviews/sony/x90l",
    },
    {
        "name": "Roku 55-Inch Select Series Smart TV",
        "price": "$349.99",
        "description": "Best value.",
        "features": ["4K"],
        "category": "best_value",
        "source_url": "https://www.rtings.com/tv/reviews/roku/select-55",
    },
])

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


class FakeRouter:
    def __init__(self, payload=UNBUYABLE):
        self.payload = payload

    def ask(self, prompt, **kw):
        return self.payload


class FakeTavily:
    def __init__(self, available=True):
        self.available = available

    def extract_products(self, niche, router=None):
        return json.loads(UNBUYABLE)


class FakeAmazon:
    def __init__(self, products):
        self.products = products

    def search_products(self, niche, **kw):
        return self.products


@pytest.fixture
def no_ddgs(monkeypatch):
    """DDGS must not hit the network in these tests."""
    monkeypatch.setattr(researcher, "DDGS", None)


# --- the regression itself -------------------------------------------------

def test_tavily_products_alone_are_refused_at_deploy(monkeypatch, no_ddgs):
    """Documents the failure mode: Tavily output is never publishable."""
    monkeypatch.setattr(researcher, "_get_amazon", lambda: FakeAmazon([]))
    monkeypatch.setattr(researcher, "_get_tavily", lambda: FakeTavily())

    products = research_niche("tv", FakeRouter())

    assert products, "expected Tavily to return something"
    assert _products_are_placeholder(products) is True


def test_research_prefers_amazon_over_tavily(monkeypatch, no_ddgs):
    """Amazon goes first, so a niche with real products publishes.

    This is the fix: previously the Tavily answer won and the page was refused.
    """
    monkeypatch.setattr(researcher, "_get_amazon", lambda: FakeAmazon(BUYABLE))

    def _tavily_must_not_run():
        raise AssertionError("Tavily was consulted before Amazon")

    monkeypatch.setattr(researcher, "_get_tavily", _tavily_must_not_run)

    products = research_niche("tv", FakeRouter())

    assert [p["asin"] for p in products] == ["B0C1TV55IN", "B0CSAMU800"]
    assert _products_are_placeholder(products) is False


def test_amazon_survives_a_dead_tavily_and_router(monkeypatch, no_ddgs):
    """Amazon products publish even when every LLM provider is down."""
    monkeypatch.setattr(researcher, "_get_amazon", lambda: FakeAmazon(BUYABLE))
    monkeypatch.setattr(researcher, "_get_tavily", lambda: FakeTavily(available=False))

    class DeadRouter:
        def ask(self, prompt, **kw):
            raise RuntimeError("all providers unavailable")

    products = research_niche("tv", DeadRouter())

    assert len(products) == 2
    assert _products_are_placeholder(products) is False


def test_amazon_failure_falls_through_to_llm(monkeypatch, no_ddgs):
    """A broken Amazon client must not take research down with it."""
    class ExplodingAmazon:
        def search_products(self, niche, **kw):
            raise RuntimeError("amazon 500")

    monkeypatch.setattr(researcher, "_get_amazon", ExplodingAmazon)
    monkeypatch.setattr(researcher, "_get_tavily", lambda: FakeTavily())

    products = research_niche("tv", FakeRouter())

    assert products, "should still fall back to Tavily"


# --- the Amazon client itself ---------------------------------------------

def test_client_returns_products_with_asin_and_image(monkeypatch):
    client = AmazonCatalogClient("k" * 40)
    assert client.available is True

    raw = {
        "data": {"products": [{
            "product_title": 'INSIGNIA 50&quot; Class F50 Series, LED 4K UHD',
            "product_price": "$279.99",
            "product_star_rating": "4.4",
            "product_num_ratings": 1200,
            "product_photo": "https://m.media-amazon.com/i/insignia.jpg",
            "product_url": "https://www.amazon.com/dp/B0F19KLHG3",
            "asin": "B0F19KLHG3",
            "is_best_seller": True,
        }]}
    }

    class FakeResp:
        status_code = 200

        def json(self):
            return raw

    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResp())
    monkeypatch.setattr(client, "_load_cache", lambda: {})
    monkeypatch.setattr(client, "_save_cache", lambda c: None)

    products = client.search_products("tv")

    assert len(products) == 1
    p = products[0]
    assert p["asin"] == "B0F19KLHG3"
    assert p["image"].startswith("https://m.media-amazon.com/")
    assert p["url"].endswith("B0F19KLHG3")
    assert p["rating"] == "4.4"
    assert p["is_best_seller"] is True
    # The comma tail is dropped (run_cycle.research_products has always done
    # this) and HTML entities are decoded, so neither reaches a published name.
    assert p["name"] == 'INSIGNIA 50" Class F50 Series'
    assert "&quot;" not in p["name"]
    assert _products_are_placeholder(products) is False


def test_client_drops_asin_less_results(monkeypatch):
    """An ASIN-less API response must not become a product list.

    That exact shape is what produced the "none carry an ASIN" refusal.
    """
    client = AmazonCatalogClient("k" * 40)

    class FakeResp:
        status_code = 200

        def json(self):
            return {"data": {"products": [{
                "product_title": "Generic Smart TV",
                "product_price": "$199",
                "product_photo": "https://m.media-amazon.com/i/x.jpg",
                "asin": "",
            }]}}

    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResp())
    monkeypatch.setattr(client, "_load_cache", lambda: {})
    monkeypatch.setattr(client, "_save_cache", lambda c: None)

    assert client.search_products("tv") == []


def test_client_ignores_an_unusable_cache_entry(monkeypatch):
    """A cache entry with no ASIN/photo is refetched, not returned.

    Returning it would reproduce the refusal the cache was meant to avoid.
    """
    client = AmazonCatalogClient("k" * 40)
    stale = [{"name": "Top tv Pick", "price": "Check Price",
              "image": "", "url": "?tag=x-20", "asin": ""}]

    monkeypatch.setattr(client, "_load_cache", lambda: {_cache_key("tv"): stale})

    class FakeResp:
        status_code = 200

        def json(self):
            return {"data": {"products": [{
                "product_title": "Roku Streaming Stick HD",
                "product_price": "$29.99",
                "product_photo": "https://m.media-amazon.com/i/roku.jpg",
                "product_url": "https://www.amazon.com/dp/B0CSTICKHD",
                "asin": "B0CSTICKHD",
            }]}}

    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResp())
    monkeypatch.setattr(client, "_save_cache", lambda c: None)

    products = client.search_products("tv")

    assert [p["asin"] for p in products] == ["B0CSTICKHD"]


def test_client_serves_a_usable_cache_entry_without_network(monkeypatch):
    client = AmazonCatalogClient("k" * 40)
    monkeypatch.setattr(client, "_load_cache", lambda: {_cache_key("tv"): BUYABLE})

    def _no_network(*a, **k):
        raise AssertionError("hit the network despite a usable cache")

    monkeypatch.setattr("requests.get", _no_network)

    products = client.search_products("tv")
    assert [p["asin"] for p in products] == ["B0C1TV55IN", "B0CSAMU800"]


def test_client_fails_closed_without_a_key():
    assert AmazonCatalogClient("").available is False
    assert AmazonCatalogClient("YOUR_KEY_HERE").available is False
    assert AmazonCatalogClient("").search_products("tv", use_cache=False) == []


@pytest.mark.parametrize("raw,expected", [
    ('INSIGNIA 50&quot; Class F50 Series, LED 4K UHD', 'INSIGNIA 50" Class F50 Series'),
    ("Roku &amp; Co 40&quot; HD, with voice", 'Roku & Co 40" HD'),
    ("", ""),
    (None, ""),
])
def test_clean_name(raw, expected):
    assert _clean_name(raw) == expected