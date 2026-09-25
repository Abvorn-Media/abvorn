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


def test_opportunities_carry_category():
    """Opportunities store their resolved site category."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        state = AbvornState(db)
        state.add_opportunity("insignia-50-fire-tv", 0.9, category="tv")
        opp = state.get_opportunities(limit=1)[0]
        assert opp["category"] == "tv"
        state.close()


def test_opportunities_migration_adds_category_column():
    """Pre-existing state.db files must gain the category column."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "old.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""
            CREATE TABLE opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                niche TEXT NOT NULL,
                score REAL NOT NULL,
                search_volume INT DEFAULT 0,
                buying_intent REAL DEFAULT 0.0,
                competition REAL DEFAULT 0.0,
                commission REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                last_post_at TEXT
            )
        """)
        conn.execute("INSERT INTO opportunities (niche, score, created_at) VALUES ('old-niche', 0.5, '2026-01-01T00:00:00')")
        conn.commit()
        conn.close()

        state = AbvornState(db)
        opp = state.get_opportunities()[0]
        assert opp["niche"] == "old-niche"
        assert opp["category"] == ""
        state.close()


def test_posts_migration_adds_image_column():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "old.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                niche_slug TEXT NOT NULL,
                title TEXT NOT NULL,
                filename TEXT,
                product_name TEXT,
                angle TEXT,
                quality_score REAL,
                persona_id TEXT,
                deployment_status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

        state = AbvornState(db)
        columns_conn = sqlite3.connect(str(db))
        columns = {
            row[1]
            for row in columns_conn.execute(
                "PRAGMA table_info(posts)"
            ).fetchall()
        }
        columns_conn.close()
        assert "image" in columns
        state.close()