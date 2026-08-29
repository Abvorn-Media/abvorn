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


BOT_UA_FRAGMENTS = (
    "bot", "crawl", "spider", "slurp", "archive.org", "wget", "curl",
    "python-requests", "go-http-client", "headlesschrome", "petalbot",
    "bingpreview", "facebookexternalhit", "googlebot", "yandex", "baiduspider",
    "duckduckbot", "site24x7", "uptimerobot", "pingdom", "newrelic",
)


def _is_bot(user_agent: str) -> bool:
    """True for obvious crawler/bot user agents we should not count."""
    ua = (user_agent or "").lower()
    return any(f in ua for f in BOT_UA_FRAGMENTS)


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
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
            used_fallback INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(clicks)").fetchall()]
    if "used_fallback" not in cols:
        conn.execute("ALTER TABLE clicks ADD COLUMN used_fallback INTEGER NOT NULL DEFAULT 0")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            article_id TEXT PRIMARY KEY,
            niche TEXT,
            title TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clicks_article ON clicks(article_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS click_targets (
            article_id TEXT NOT NULL,
            product_index INTEGER NOT NULL,
            product_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (article_id, product_index)
        )
    """)
    conn.commit()
    conn.close()


def record_product_url(article_id: str, product_index: int, product_url: str) -> None:
    """Persist the real affiliate URL for /click/<article_id>/<index> resolution.

    Called at build time while rewriting affiliate links, so the redirect
    server can resolve a click link back to the actual Amazon URL.
    """
    if not article_id or not product_url:
        return
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO click_targets (article_id, product_index, product_url, created_at) "
        "VALUES (?, ?, ?, ?)",
        (article_id, product_index, product_url or "", datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def resolve_product_url(article_id: str, product_index: int, fallback: str = "") -> str:
    """Look up the real affiliate URL for a click link. Returns fallback if unknown."""
    init_db()
    conn = _get_conn()
    row = conn.execute(
        "SELECT product_url FROM click_targets WHERE article_id = ? AND product_index = ?",
        (article_id, product_index),
    ).fetchone()
    conn.close()
    return row["product_url"] if row and row["product_url"] else fallback


def log_click(article_id: str, product_url: str, user_agent: str = "", ip_hash: str = "",
              used_fallback: bool = False) -> Dict[str, Any]:
    """Log a single affiliate link click. Bot clicks are filtered out."""
    if _is_bot(user_agent):
        logger.info(f"Click ignored (bot UA): {article_id}")
        return {"ok": False, "filtered": "bot", "article_id": article_id}
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO clicks (article_id, product_url, user_agent, ip_hash, used_fallback, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (article_id, product_url, user_agent or "", ip_hash or "",
         int(bool(used_fallback)), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    logger.info(f"Click logged: {article_id} -> {product_url[:80]}")
    return {"ok": True, "article_id": article_id, "product_url": product_url,
            "used_fallback": bool(used_fallback)}


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
