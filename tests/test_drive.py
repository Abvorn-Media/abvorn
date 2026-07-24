import pytest
from abvorn.drive import Drive


def test_drive_default_grit():
    """Should start with grit 0."""
    d = Drive("TestAgent", "test mission")
    assert d.grit == 0


def test_should_retry_returns_true_for_first_attempts():
    """Should say yes to early retries."""
    d = Drive("TestAgent")
    assert d.should_retry(0) is True
    assert d.should_retry(1) is True
    assert d.should_retry(2) is True


def test_should_retry_returns_false_after_max():
    """Should say no after too many attempts."""
    d = Drive("TestAgent")
    assert d.should_retry(10) is False


def test_alternative_path_different_from_blocked():
    """Should return a different path."""
    d = Drive("TestAgent")
    alt = d.alternative_path("x_post")
    assert alt != "x_post"
    assert "post" in alt  # some kind of post


def test_log_outcome_increases_grit_on_failure():
    """Grit should increase on failure."""
    d = Drive("TestAgent")
    d.log_outcome("x_post", succeeded=False)
    assert d.grit == 1
    d.log_outcome("linkedin_post", succeeded=False)
    assert d.grit == 2


def test_log_outcome_decreases_grit_on_success():
    """Grit should decrease on success."""
    d = Drive("TestAgent")
    d.grit = 3
    d.log_outcome("x_post", succeeded=True)
    assert d.grit == 2


def test_get_history():
    """Should return recent history."""
    d = Drive("TestAgent")
    d.log_outcome("a", True)
    d.log_outcome("b", False)
    hist = d.get_history()
    assert len(hist) == 2
    assert hist[0]["action"] == "a"
    assert hist[0]["succeeded"] is True