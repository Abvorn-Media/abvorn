"""Shared pytest fixtures.

The social budget persists its counters to disk so a daemon restart cannot hand
the day back a fresh allowance. Without isolation the suite would read and spend
the developer's real daily allowance, and any test that posts would block every
later test with `budget_exceeded`. Point it at a per-test tmp file instead.
"""

import pytest


@pytest.fixture(autouse=True)
def isolate_social_budget(tmp_path, monkeypatch):
    """Keep the live daily social budget out of the test run."""
    from abvorn.core import social_budget

    monkeypatch.setenv(
        "ABVORN_SOCIAL_BUDGET_FILE", str(tmp_path / "social_budget.json")
    )
    # A test may opt into a different limit via the env ladder.
    monkeypatch.delenv("ABVORN_SOCIAL_DAILY_LIMIT", raising=False)
    return social_budget