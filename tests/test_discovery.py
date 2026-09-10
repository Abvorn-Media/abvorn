import pytest
from abvorn.discovery.scanner import OpportunityScanner, score_opportunity


def test_score_opportunity():
    """Should compute a score between 0 and 1."""
    score = score_opportunity(search_demand=5000, buying_intent=0.7,
                              commission=50.0, competition=0.3)
    assert 0 <= score <= 1
    assert score > 0.5


def test_low_opportunity_scores_low():
    """Low demand + high competition should score near 0."""
    score = score_opportunity(search_demand=100, buying_intent=0.2,
                              commission=5.0, competition=0.9)
    assert score < 0.3


def test_scanner_creates_opportunities():
    """Scanner should discover and store opportunities."""
    from abvorn.core.state import AbvornState
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        state = AbvornState(db_path)
        scanner = OpportunityScanner(state)
        results = scanner.discover_from_keywords(["wireless headphones", "gaming mouse"])
        assert len(results) <= 2
        niches = state.get_opportunities()
        assert len(niches) > 0
        state.close()


TREND_SAMPLE = [
    {"product_name": "4K Gaming Monitor Under $300", "category": "monitor",
     "score": 88, "sources": ["reddit", "amazon"]},
    {"product_name": "Mechanical Keyboard Guide 2026", "category": "keyboard",
     "score": 72, "sources": ["reddit"]},
    {"product_name": "Cheap Gaming Mouse", "category": "mouse",
     "score": 50, "sources": ["web"]},
]


def test_discover_from_trends_creates_buying_guides():
    """High-score trends should become deployable opportunities (page + social)."""
    from abvorn.core.state import AbvornState
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        state = AbvornState(db_path)
        scanner = OpportunityScanner(state)
        results = scanner.discover_from_trends(TREND_SAMPLE)

        # Only score>=70 trends map to buying_guide; the 50-score mouse is skipped
        assert len(results) == 2
        niches = {r["niche"] for r in results}
        assert "4k-gaming-monitor-under-300" in niches
        assert "mechanical-keyboard-guide-2026" in niches
        prods = {r["product_name"] for r in results}
        assert "4K Gaming Monitor Under $300" in prods
        assert "Mechanical Keyboard Guide 2026" in prods
        assert "Cheap Gaming Mouse" not in prods

        stored = state.get_opportunities()
        assert len(stored) == 2
        assert all(o["status"] == "pending" for o in stored)
        state.close()


def test_discover_from_trends_skips_existing_niches():
    """Trends whose slug already has a pending opportunity must be skipped."""
    from abvorn.core.state import AbvornState
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        state = AbvornState(db_path)
        scanner = OpportunityScanner(state)
        state.add_opportunity("4k-gaming-monitor-under-300", 0.5)
        results = scanner.discover_from_trends(TREND_SAMPLE)
        prods = {r["product_name"] for r in results}
        assert "4K Gaming Monitor Under $300" not in prods
        assert "Mechanical Keyboard Guide 2026" in prods
        state.close()


def test_discover_from_trends_empty():
    """No trends -> no opportunities, no error."""
    from abvorn.core.state import AbvornState
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        state = AbvornState(db_path)
        scanner = OpportunityScanner(state)
        assert scanner.discover_from_trends([]) == []
        assert state.get_opportunities() == []
        state.close()