import pytest
from abvorn.agents.researcher import research_niche

def test_research_returns_products():
    """RESEARCH stage should return a list of dicts with required keys."""
    class FakeRouter:
        def ask(self, prompt, **kw):
            return '[{"name": "Test Product", "price": "$49.99", "rating": "4.5/5", "features": ["Feature A"], "summary": "Great product"}]'
    products = research_niche("test_niche", FakeRouter())
    assert isinstance(products, list)
    assert len(products) > 0
    p = products[0]
    assert "name" in p
    assert "price" in p
    assert "features" in p


def test_research_returns_empty_when_every_lookup_fails():
    """A dead search provider and a dead LLM used to yield a fabricated
    "Top <niche> Pick" that was then published as a real product (invented
    7.0 scores, a ?tag=... search link, no ASIN). Failing closed lets the
    existing no-products guards skip the page instead."""
    class DeadRouter:
        def ask(self, prompt, **kw):
            raise RuntimeError("all providers unavailable")

    assert research_niche("tv", DeadRouter()) == []


def test_research_never_invents_a_placeholder_product():
    """Whatever the providers return, no product may be a 'Top <niche> Pick'
    stub or lack an identifier we can link to."""
    class EmptyRouter:
        def ask(self, prompt, **kw):
            return "[]"

    assert research_niche("tv", EmptyRouter()) == []
    # No router at all: the AI knowledge fallback cannot run, so the result is
    # empty rather than a stub.
    assert research_niche("tv", None) == []
