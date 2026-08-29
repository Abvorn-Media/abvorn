"""Tests for src/click_tracker D5 hardening: used_fallback migration, bot filter, WAL."""
import sqlite3

import pytest

import src.click_tracker as ct


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "DB_PATH", tmp_path / "clicks.db")
    ct.init_db()
    yield
    for suffix in ("", "-wal", "-shm"):
        p = tmp_path / f"clicks.db{suffix}"
        if p.exists():
            p.unlink()


def test_init_db_adds_used_fallback_column_to_existing_table(tmp_path, monkeypatch):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE clicks (id INTEGER PRIMARY KEY AUTOINCREMENT, article_id TEXT NOT NULL, product_url TEXT NOT NULL, user_agent TEXT, ip_hash TEXT, created_at TEXT NOT NULL)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(ct, "DB_PATH", db)
    ct.init_db()
    conn = sqlite3.connect(str(db))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(clicks)").fetchall()]
    conn.close()
    assert "used_fallback" in cols


def test_used_fallback_column_persisted(tmp_path, monkeypatch):
    db = tmp_path / "clicks.db"
    monkeypatch.setattr(ct, "DB_PATH", db)
    ct.init_db()
    ct.log_click("art-1", "https://amazon.com/dp/X", used_fallback=True)
    conn = sqlite3.connect(str(db))
    row = conn.execute("SELECT used_fallback FROM clicks").fetchone()
    conn.close()
    assert row[0] == 1


def test_log_click_missing_index_filled(tmp_path, monkeypatch):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE clicks (id INTEGER PRIMARY KEY AUTOINCREMENT, article_id TEXT NOT NULL, product_url TEXT NOT NULL, user_agent TEXT, ip_hash TEXT, used_fallback INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(ct, "DB_PATH", db)
    ct.init_db()
    ct.log_click("art-2", "https://amazon.com/dp/Y")
    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(*) FROM clicks").fetchone()[0]
    conn.close()
    assert n == 1


def test_connections_use_wal(tmp_path, monkeypatch):
    db = tmp_path / "clicks.db"
    monkeypatch.setattr(ct, "DB_PATH", db)
    ct.init_db()
    conn = ct._get_conn()
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    conn.close()
    assert mode.upper() == "WAL"
    assert busy == 10000


@pytest.mark.parametrize("ua,expected_bot", [
    ("Mozilla/5.0 (Windows NT 10.0) Chrome/120", False),
    ("Googlebot/2.1 (+http://www.google.com/bot.html)", True),
    ("facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)", True),
    ("python-requests/2.31.0", True),
    ("Mozilla/5.0 Pingdom.com_bot_version_1.4", True),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X) Safari/605", False),
])
def test_bot_detection(ua, expected_bot):
    assert ct._is_bot(ua) is expected_bot


def test_bot_clicks_not_recorded(tmp_path, monkeypatch):
    db = tmp_path / "clicks.db"
    monkeypatch.setattr(ct, "DB_PATH", db)
    ct.init_db()
    result = ct.log_click("art-3", "https://amazon.com/dp/Z", user_agent="curl/8.0")
    assert result["ok"] is False and result["filtered"] == "bot"
    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(*) FROM clicks").fetchone()[0]
    conn.close()
    assert n == 0