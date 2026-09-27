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


def test_product_card_image_reads_products_not_top_level(tmp_path):
    """The card photo lives on products[i]["image"]; there is no top-level key.

    A content payload as produced by abvorn/content/pipeline.py::run has no
    "image" key, so callers using content.get("image") persisted an empty
    posts.image and every such card fell back to the generic niche artwork
    instead of the product photo.
    """
    from src.deployment import product_card_image

    content = {
        "post_title": "2026 Ultimate TV Buying Guide",
        "products": [
            {"name": "Sony Bravia 9", "image": "https://m.media-amazon.com/images/I/61abc._AC_SL500_.jpg"},
            {"name": "LG C4", "image": "https://m.media-amazon.com/images/I/61def._AC_SL500_.jpg"},
        ],
    }
    # The trap this guards: the naive read yields nothing.
    assert content.get("image") is None

    image = product_card_image(content)
    assert image.startswith("https://m.media-amazon.com/images/I/61abc")
    assert "_AC_SL500_" not in image  # upgraded to a larger rendition

    # A payload with no product photo must stay empty rather than invent one.
    assert product_card_image({"post_title": "No products"}) == ""
    assert product_card_image({"products": [{"name": "x"}]}) == ""


def test_add_post_persists_product_card_image(tmp_path):
    """End-to-end: the resolved product photo must survive into posts.image."""
    from src.deployment import product_card_image

    db = tmp_path / "card.db"
    state = AbvornState(db)
    state.upsert_niche("tv", "TV", "Electronics")
    content = {
        "post_title": "2026 Ultimate TV Buying Guide",
        "products": [{"name": "Sony Bravia 9",
                      "image": "https://m.media-amazon.com/images/I/61abc._AC_SL500_.jpg"}],
    }
    state.add_post("tv", content["post_title"], "tv-guide.html",
                   image=product_card_image(content))
    post = state.get_posts_for_niche("tv")[0]
    assert post["image"].startswith("https://m.media-amazon.com/images/I/61abc")
    state.close()


def test_no_production_add_post_reads_top_level_image():
    """Every production add_post() must resolve its image via product_card_image.

    A content payload has no top-level "image" key, so a call site reading
    content.get("image") silently persists an empty posts.image and the card
    falls back to generic niche artwork. This walks the real call sites so the
    bug cannot come back at a new or edited call site.
    """
    import ast
    from pathlib import Path

    pkg = Path(__file__).resolve().parent.parent / "abvorn"
    offenders = []
    checked = 0
    for path in sorted(pkg.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute) and fn.attr == "add_post"):
                continue
            img_kw = next((k.value for k in node.keywords if k.arg == "image"), None)
            if img_kw is None:
                offenders.append("%s:%d add_post without image=" % (path.name, node.lineno))
                continue
            checked += 1
            resolves = (
                isinstance(img_kw, ast.Call)
                and isinstance(img_kw.func, ast.Name)
                and img_kw.func.id == "product_card_image"
            )
            if not resolves:
                offenders.append("%s:%d image= is not product_card_image(...)"
                                 % (path.name, node.lineno))
    assert checked, "expected to find production add_post call sites"
    assert not offenders, "add_post image regression:\n" + "\n".join(offenders)