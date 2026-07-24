import pytest
from abvorn.deploy.analytics import compute_ga4_score

def test_compute_score():
    """Score should weight users more than views, duration as bonus."""
    score = compute_ga4_score(views=100, users=20, avg_duration=30.0)
    assert score > 100  # 100 + 40 + 3 = 143
    assert score < 200