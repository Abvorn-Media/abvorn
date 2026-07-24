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