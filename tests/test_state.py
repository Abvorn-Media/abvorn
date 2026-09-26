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


def test_posts_image_and_created_at_are_not_swapped(tmp_path):
    """image must never receive the created_at timestamp.

    posts.image is appended by a migration, so it lands *after* created_at in
    the real column order. A hand-maintained key list that put image first
    swapped the two and every consumer rendered a bare timestamp as an <img
    src>. Keys are now derived from the query, so the order cannot drift.
    """
    db = tmp_path / "fresh.db"
    state = AbvornState(db)
    state.upsert_niche("tv", "TV", "Electronics")
    state.add_post("tv", "A Review", "a.html", image="https://m.media-amazon.com/i/1.jpg")
    post = state.get_posts_for_niche("tv")[0]
    assert post["image"] == "https://m.media-amazon.com/i/1.jpg"
    assert post["created_at"][:4] == "2026"
    state.close()


def test_posts_image_empty_on_migrated_db(tmp_path):
    """The migrated column order must not leak created_at into image."""
    db = tmp_path / "old.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE niches (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Other',
            maturity TEXT DEFAULT 'seed',
            total_posts INT DEFAULT 0,
            avg_quality REAL DEFAULT 0.0,
            ga4_views INT DEFAULT 0,
            ga4_users INT DEFAULT 0,
            ga4_score REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            last_post_at TEXT
        )
    """)
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
    conn.execute(
        "INSERT INTO posts (niche_slug, title, created_at) VALUES (?,?,?)",
        ("tv", "Legacy Review", "2026-02-03T04:05:06"),
    )
    conn.commit()
    conn.close()

    state = AbvornState(db)
    post = state.get_posts_for_niche("tv")[0]
    assert post["image"] == ""
    assert post["created_at"] == "2026-02-03T04:05:06"
    state.close()