import pytest
import abvorn.agents.researcher as researcher
from abvorn.agents.researcher import research_niche


@pytest.fixture
def no_live_sources(monkeypatch):
    """Take every non-LLM research source offline.

    research_niche() tries Amazon first, then Tavily, then DDGS. Without this
    fixture the "all lookups fail" tests actually hit the live Amazon catalog,
    get five real TVs back and never exercise the fail-closed path they pin.
    """
    class EmptyAmazon:
        def search_products(self, niche):
            return []

    class OfflineTavily:
        available = False

    class OfflineDDGS:
        def __enter__(self):
            raise RuntimeError("search offline")
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(researcher, "_get_amazon", lambda: EmptyAmazon())
    monkeypatch.setattr(researcher, "_get_tavily", lambda: OfflineTavily())
    monkeypatch.setattr(researcher, "DDGS", OfflineDDGS)


def test_research_returns_products(no_live_sources):
    """RESEARCH stage should return a list of dicts with required keys.

    The fake product carries an image because research now fails closed on
    unpictured output - the same LLM shape that used to render as a blue
    category-fallback card on the homepage.
    """
    class FakeRouter:
        def ask(self, prompt, **kw):
            return (
                '[{"name": "Test Product", "price": "$49.99", "rating": "4.5/5", '
                '"features": ["Feature A"], "summary": "Great product", '
                '"image": "https://m.media-amazon.com/images/I/71abc._AC_SL1500_.jpg"}]'
            )
    products = research_niche("test_niche", FakeRouter())
    assert isinstance(products, list)
    assert len(products) > 0
    p = products[0]
    assert "name" in p
    assert "price" in p
    assert "features" in p


def test_research_returns_empty_when_every_lookup_fails(no_live_sources):
    """A dead search provider and a dead LLM used to yield a fabricated
    "Top <niche> Pick" that was then published as a real product (invented
    7.0 scores, a ?tag=... search link, no ASIN). Failing closed lets the
    existing no-products guards skip the page instead."""
    class DeadRouter:
        def ask(self, prompt, **kw):
            raise RuntimeError("all providers unavailable")

    assert research_niche("tv", DeadRouter()) == []


def test_research_never_invents_a_placeholder_product(no_live_sources):
    """Whatever the providers return, no product may be a 'Top <niche> Pick'
    stub or lack an identifier we can link to."""
    class EmptyRouter:
        def ask(self, prompt, **kw):
            return "[]"

    assert research_niche("tv", EmptyRouter()) == []
    # No router at all: the AI knowledge fallback cannot run, so the result is
    # empty rather than a stub.
    assert research_niche("tv", None) == []
