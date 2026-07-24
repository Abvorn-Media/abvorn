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
