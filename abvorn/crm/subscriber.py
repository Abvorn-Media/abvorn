"""Email CRM — subscriber management and sequence tracking."""

import logging, sqlite3, threading
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger("abvorn.crm")


class SubscriberDB:
    """SQLite-backed subscriber database with email sequence tracking."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    @contextmanager
    def _cursor(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.row_factory = sqlite3.Row
        yield self._local.conn.cursor()
        self._local.conn.commit()

    def _init_db(self):
        with self._cursor() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    email TEXT PRIMARY KEY,
                    persona_id TEXT,
                    niche TEXT,
                    subscribed_at TEXT NOT NULL,
                    last_open_at TEXT,
                    last_click_at TEXT,
                    sequence_step INT DEFAULT 0,
                    total_conversions INT DEFAULT 0,
                    total_revenue REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'active'
                );
                CREATE TABLE IF NOT EXISTS email_sequences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    niche TEXT NOT NULL,
                    persona_id TEXT,
                    day INT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    lead_magnet TEXT,
                    sent_count INT DEFAULT 0,
                    open_count INT DEFAULT 0,
                    click_count INT DEFAULT 0,
                    created_at TEXT NOT NULL
                );
            """)

    def add_subscriber(self, email: str, persona_id: str, niche: str):
        with self._cursor() as c:
            c.execute("""INSERT OR IGNORE INTO subscribers
                (email, persona_id, niche, subscribed_at)
                VALUES (?, ?, ?, ?)""",
                (email, persona_id, niche, datetime.now().isoformat()))
            logger.info(f"Subscriber added: {email} ({persona_id})")

    def get_subscribers(self, niche: str = None) -> list[dict]:
        with self._cursor() as c:
            if niche:
                c.execute("SELECT * FROM subscribers WHERE niche=? AND status='active'", (niche,))
            else:
                c.execute("SELECT * FROM subscribers WHERE status='active'")
            return [dict(row) for row in c.fetchall()]

    def track_open(self, email: str):
        with self._cursor() as c:
            c.execute("UPDATE subscribers SET last_open_at=? WHERE email=?",
                      (datetime.now().isoformat(), email))

    def track_click(self, email: str):
        with self._cursor() as c:
            c.execute("UPDATE subscribers SET last_click_at=? WHERE email=?",
                      (datetime.now().isoformat(), email))

    def save_sequence(self, niche: str, persona_id: str, emails: list[dict]):
        with self._cursor() as c:
            for email_data in emails:
                c.execute("""INSERT INTO email_sequences
                    (niche, persona_id, day, subject, body, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (niche, persona_id, email_data["day"],
                     email_data["subject"], email_data["body"],
                     datetime.now().isoformat()))

    def get_sequence(self, niche: str, persona_id: str = None) -> list[dict]:
        with self._cursor() as c:
            if persona_id:
                c.execute("""SELECT * FROM email_sequences
                    WHERE niche=? AND persona_id=? ORDER BY day""",
                    (niche, persona_id))
            else:
                c.execute("""SELECT * FROM email_sequences
                    WHERE niche=? ORDER BY day""", (niche,))
            return [dict(row) for row in c.fetchall()]

    def close(self):
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None