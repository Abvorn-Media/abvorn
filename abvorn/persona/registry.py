"""Persona registry — stores, retrieves, and manages persona lifecycle."""

import json, logging, sqlite3, threading
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger("abvorn.persona.registry")


class PersonaRegistry:
    """SQLite-backed persona registry with lifecycle management."""

    def __init__(self, db_path):
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
            c.execute("""
                CREATE TABLE IF NOT EXISTS personas (
                    persona_id TEXT PRIMARY KEY,
                    niche TEXT NOT NULL,
                    name TEXT NOT NULL,
                    psychology_json TEXT NOT NULL,
                    age_range TEXT,
                    status TEXT DEFAULT 'active',
                    post_count INT DEFAULT 0,
                    conversion_count INT DEFAULT 0,
                    total_revenue REAL DEFAULT 0.0,
                    avg_quality REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    last_used TEXT,
                    retired_at TEXT
                )
            """)

    def register_persona(self, persona_id: str, niche: str, persona_data: dict):
        name = persona_data.get("name", persona_id)
        psychology = persona_data.get("psychology", {})
        age_range = persona_data.get("age_range", "")
        with self._cursor() as c:
            c.execute("""INSERT OR REPLACE INTO personas
                (persona_id, niche, name, psychology_json, age_range, created_at, last_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (persona_id, niche, name, json.dumps(psychology), age_range,
                 datetime.now().isoformat(), datetime.now().isoformat()))

    def get_persona(self, persona_id: str) -> dict:
        with self._cursor() as c:
            c.execute("SELECT * FROM personas WHERE persona_id=?", (persona_id,))
            row = c.fetchone()
            if not row:
                return None
            d = dict(row)
            d["psychology"] = json.loads(d.pop("psychology_json"))
            return d

    def get_active_personas(self, niche: str = None) -> list[dict]:
        with self._cursor() as c:
            if niche:
                c.execute("SELECT * FROM personas WHERE status='active' AND niche=?", (niche,))
            else:
                c.execute("SELECT * FROM personas WHERE status='active'")
            results = []
            for row in c.fetchall():
                d = dict(row)
                d["psychology"] = json.loads(d.pop("psychology_json"))
                results.append(d)
            return results

    def update_performance(self, persona_id: str, converted: bool = False,
                           quality_score: float = 0.0, revenue: float = 0.0):
        with self._cursor() as c:
            c.execute("""UPDATE personas SET
                post_count = post_count + 1,
                last_used = ?,
                conversion_count = CASE WHEN ? THEN conversion_count + 1 ELSE conversion_count END,
                total_revenue = total_revenue + ?,
                avg_quality = CASE WHEN post_count > 0
                    THEN (avg_quality * post_count + ?) / (post_count + 1)
                    ELSE ? END
                WHERE persona_id=?""",
                (datetime.now().isoformat(), converted, revenue,
                 quality_score, quality_score, persona_id))
            self._check_retirement(persona_id)

    def _check_retirement(self, persona_id: str):
        with self._cursor() as c:
            c.execute("SELECT post_count, conversion_count FROM personas WHERE persona_id=?", (persona_id,))
            row = c.fetchone()
            if row and row["post_count"] >= 5:
                conversion_rate = row["conversion_count"] / row["post_count"]
                if conversion_rate < 0.01:
                    c.execute("UPDATE personas SET status='retired', retired_at=? WHERE persona_id=?",
                              (datetime.now().isoformat(), persona_id))
                    logger.info(f"Persona {persona_id} retired (conversion rate: {conversion_rate:.1%})")

    def select_best_persona(self, niche: str) -> dict:
        """Pick the best active persona for a niche."""
        personas = self.get_active_personas(niche)
        if not personas:
            return None
        personas.sort(key=lambda p: p.get("conversion_count", 0) / max(p.get("post_count", 1), 1), reverse=True)
        return personas[0]