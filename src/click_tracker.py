"""click_tracker.py — Affiliate click tracking for Abvorn.

Logs clicks on Amazon affiliate links via SQLite, provides
get_clicks(article_id) for economic surplus calculation.
"""
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path("data/clicks.db")


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id TEXT NOT NULL,
            product_url TEXT NOT NULL,
            user_agent TEXT,
            ip_hash TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            article_id TEXT PRIMARY KEY,
            niche TEXT,
            title TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clicks_article ON clicks(article_id)")
    conn.commit()
    conn.close()


def log_click(article_id: str, product_url: str, user_agent: str = "", ip_hash: str = "") -> Dict[str, Any]:
    """Log a single affiliate link click."""
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO clicks (article_id, product_url, user_agent, ip_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (article_id, product_url, user_agent or "", ip_hash or "", datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    logger.info(f"Click logged: {article_id} -> {product_url[:80]}")
    return {"ok": True, "article_id": article_id, "product_url": product_url}


def get_clicks(article_id: str) -> int:
    """Return total click count for an article since tracking began."""
    init_db()
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) as n FROM clicks WHERE article_id = ?", (article_id,)).fetchone()
    conn.close()
    return row["n"] if row else 0


def get_clicks_by_article(limit: int = 100) -> List[Dict[str, Any]]:
    """Return click counts grouped by article_id."""
    init_db()
    conn = _get_conn()
    rows = conn.execute("""
        SELECT article_id, COUNT(*) as clicks, MAX(created_at) as last_click
        FROM clicks
        GROUP BY article_id
        ORDER BY last_click DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def register_article(article_id: str, niche: str = "", title: str = ""):
    """Register an article so we can attribute clicks to it."""
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO articles (article_id, niche, title, created_at) VALUES (?, ?, ?, ?)",
        (article_id, niche, title, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def register_articles_batch(articles: List[Dict[str, Any]]) -> None:
    """Register multiple articles for click tracking."""
    for a in articles:
        register_article(
            a.get("article_id", ""),
            a.get("niche", ""),
            a.get("post_title", a.get("title", "")),
        )


init_db()
