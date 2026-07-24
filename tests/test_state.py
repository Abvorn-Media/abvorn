import pytest, tempfile, sqlite3
from pathlib import Path
from abvorn.core.state import AbvornState


def test_new_tables_exist():
    """Should create new tables for Phase 3."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        state = AbvornState(db)
        conn = sqlite3.connect(str(db))
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        state.close()
        assert "opportunities" in tables
        assert "subscribers" in tables
        assert "email_sequences" in tables