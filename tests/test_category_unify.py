"""Category taxonomy unification.

state.db's niches table is the registry of which categories EXIST; the rich
feed builder derives its group map from it, so categories created by the
daemon's opportunity pipeline (e.g. 'tv') survive feed rebuilds instead of
being silently dropped from the live tree.
"""
import os
import sqlite3
from pathlib import Path

import pytest

from src.deployment import (
    STATIC_CATEGORY_MAP,
    STATIC_CATEGORY_NAMES,
    _effective_category_map,
)

_NICHES = [
    {"slug": "tv", "name": "TV", "category": "Other"},
    {"slug": "robot-vacuums", "name": "Robot Vacuums", "category": "Other"},
    {"slug": "noise-cancelling-headphones", "name": "Noise Cancelling Headphones", "category": "Audio"},
    {"slug": "ultra-wild-card", "name": "Ultra Wild Card", "category": "None"},
]


def test_static_groups_unchanged_when_state_empty():
    effects, names = _effective_category_map([])
    assert effects == STATIC_CATEGORY_MAP
    assert names == STATIC_CATEGORY_NAMES


def test_daemon_category_folds_into_curated_group():
    effects, _ = _effective_category_map(_NICHES)
    assert "tv" in effects["Computing & Monitors"]
    assert "robot-vacuums" in effects["Home & Lifestyle"]
    assert "noise-cancelling-headphones" in effects["Audio"]


def test_unknown_category_gets_own_group():
    effects, names = _effective_category_map(_NICHES)
    assert effects["Ultra Wild Card"] == ["ultra-wild-card"]
    assert names["ultra-wild-card"] == "Ultra Wild Card"
    assert names["tv"] == "TV"


def test_merge_never_duplicates_slugs():
    effects, _ = _effective_category_map(_NICHES + [
        {"slug": "tv", "name": "TV", "category": "Other"},
    ])
    for slugs in effects.values():
        assert len(slugs) == len(set(slugs))


def test_live_merged_map_covers_state_db():
    """On machines with a state.db, every registered niche must appear in the
    effective feed taxonomy — the invariant this fix installs."""
    db = Path(os.environ.get("ABVORN_STATE_DB") or Path.home() / ".abvorn" / "state.db")
    if not db.exists():
        pytest.skip("no state.db on this machine")
    conn = sqlite3.connect(str(db))
    try:
        slugs = {r[0] for r in conn.execute("SELECT slug FROM niches").fetchall()}
    finally:
        conn.close()

    from src.deployment import CATEGORY_MAP
    merged = {s for slugs_ in CATEGORY_MAP.values() for s in slugs_}
    missing = slugs - merged
    assert not missing, f"state.db niches missing from feed taxonomy: {missing}"