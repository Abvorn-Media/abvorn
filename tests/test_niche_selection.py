"""Tests for GA4-aware niche selection (pick_niche)."""
import pytest

from run_cycle import pick_niche


def _state(niches, last=None):
    return {"niches": niches, "last_processed": last}


def _niches(*pairs):
    return [{"slug": slug, "name": slug, "posts": posts} for slug, posts in pairs]


# ── Legacy behavior (no GA4 scores) ─────────────────────────────────────

def test_fewest_posts_wins_without_ga4():
    state = _state(_niches(("a", 3), ("b", 1), ("c", 5)))
    assert pick_niche(state)["slug"] == "b"


def test_round_robin_tie_break_after_last_without_ga4():
    state = _state(_niches(("a", 1), ("b", 1), ("c", 1)), last="a")
    assert pick_niche(state)["slug"] == "b"


def test_round_robin_wraps_around_without_ga4():
    state = _state(_niches(("a", 1), ("b", 1), ("c", 1)), last="c")
    assert pick_niche(state)["slug"] == "a"


# ── GA4-aware: proven performer at the floor ────────────────────────────

def test_ga4_proven_wins_over_other_floor_candidates():
    state = _state(_niches(("a", 1), ("b", 1), ("c", 1)))
    scores = {"a": 0.0, "b": 42.0, "c": 0.0}
    assert pick_niche(state, ga4_scores=scores)["slug"] == "b"


def test_ga4_highest_score_wins_at_floor():
    state = _state(_niches(("a", 1), ("b", 1), ("c", 1)))
    scores = {"a": 5.0, "b": 42.0, "c": 91.0}
    assert pick_niche(state, ga4_scores=scores)["slug"] == "c"


def test_floor_still_dominated_by_fewest_posts():
    # A proven niche above the floor with weak engagement must not jump the queue.
    state = _state(_niches(("a", 1), ("b", 3)))
    scores = {"a": 0.0, "b": 15.0}  # b proven but 2 posts above floor
    assert pick_niche(state, ga4_scores=scores)["slug"] == "a"


def test_no_ga4_for_floor_falls_back_to_round_robin():
    state = _state(_niches(("a", 1), ("b", 1), ("c", 1)), last="a")
    scores = {"x": 99.0}  # unrelated slug
    assert pick_niche(state, ga4_scores=scores)["slug"] == "b"


# ── GA4-aware: promotion one post above the floor (strong proof) ─────────

def test_strong_ga4_promotes_one_post_above_floor():
    state = _state(_niches(("a", 1), ("b", 2), ("c", 2)))
    scores = {"a": 0.0, "b": 25.0, "c": 0.0}
    assert pick_niche(state, ga4_scores=scores)["slug"] == "b"


def test_weak_ga4_does_not_promote_above_floor():
    state = _state(_niches(("a", 1), ("b", 2)))
    scores = {"a": 0.0, "b": 15.0}  # below the 20 threshold
    assert pick_niche(state, ga4_scores=scores)["slug"] == "a"


def test_promotion_respects_round_robin_among_strong():
    state = _state(_niches(("a", 1), ("b", 2), ("c", 2)), last="b")
    scores = {"a": 0.0, "b": 25.0, "c": 30.0}
    # c has the highest score; guaranteed pick regardless of last.
    assert pick_niche(state, ga4_scores=scores)["slug"] == "c"


# ── Edge cases ──────────────────────────────────────────────────────────

def test_empty_state_falls_back_to_first():
    state = _state(_niches(("a", 0)))
    assert pick_niche(state)["slug"] == "a"


def test_none_ga4_scores_is_same_as_missing():
    state = _state(_niches(("a", 1), ("b", 1)))
    assert pick_niche(state, ga4_scores=None)["slug"] == "a"