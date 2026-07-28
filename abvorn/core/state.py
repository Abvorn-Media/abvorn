import sqlite3, json, threading, logging
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger("abvorn.state")

class AbvornState:
    """Thread-safe SQLite-backed state. WAL mode for concurrent access."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    @contextmanager
    def _cursor(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=5000")
        yield self._local.conn.cursor()
        self._local.conn.commit()

    def _init_db(self):
        with self._cursor() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS niches (
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
                );
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    niche_slug TEXT NOT NULL REFERENCES niches(slug),
                    title TEXT NOT NULL,
                    filename TEXT,
                    product_name TEXT,
                    angle TEXT,
                    quality_score REAL,
                    persona_id TEXT,
                    deployment_status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    niche_slug TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    priority INT DEFAULT 10,
                    payload TEXT,
                    created_at TEXT NOT NULL,
                    locked_until TEXT
                );
                CREATE TABLE IF NOT EXISTS persona_registry (
                    persona_id TEXT PRIMARY KEY,
                    niche TEXT NOT NULL,
                    persona_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used TEXT,
                    post_count INT DEFAULT 0,
                    avg_quality REAL DEFAULT 0.0,
                    impressions INT DEFAULT 0,
                    clicks INT DEFAULT 0,
                    conversions INT DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS model_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    time_ms REAL,
                    tokens INT,
                    created_at TEXT NOT NULL
                );
            """)

    def close(self):
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def get_meta(self, key: str, default=None):
        with self._cursor() as c:
            c.execute("SELECT value FROM meta WHERE key=?", (key,))
            row = c.fetchone()
            return json.loads(row[0]) if row else default

    def set_meta(self, key: str, value):
        with self._cursor() as c:
            c.execute("REPLACE INTO meta VALUES (?, ?)", (key, json.dumps(value)))

    def upsert_niche(self, slug: str, name: str, category: str = "Other"):
        with self._cursor() as c:
            c.execute("""
                INSERT INTO niches (slug, name, category, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET name=excluded.name, category=excluded.category
            """, (slug, name, category, datetime.now().isoformat()))

    def get_niche(self, slug: str) -> dict:
        with self._cursor() as c:
            c.execute("SELECT * FROM niches WHERE slug=?", (slug,))
            row = c.fetchone()
            if not row:
                return None
            keys = ["slug","name","category","maturity","total_posts","avg_quality",
                    "ga4_views","ga4_users","ga4_score","created_at","last_post_at"]
            return dict(zip(keys, row))

    def get_all_niches(self) -> list:
        with self._cursor() as c:
            c.execute("SELECT * FROM niches ORDER BY ga4_score DESC")
            keys = ["slug","name","category","maturity","total_posts","avg_quality",
                    "ga4_views","ga4_users","ga4_score","created_at","last_post_at"]
            return [dict(zip(keys, row)) for row in c.fetchall()]

    def update_niche_analytics(self, slug: str, views: int, users: int, score: float):
        with self._cursor() as c:
            c.execute("""
                UPDATE niches SET ga4_views=?, ga4_users=?, ga4_score=?
                WHERE slug=?
            """, (views, users, round(score, 1), slug))

    def update_niche_maturity(self, slug: str, total_posts: int, avg_quality: float):
        maturity = "seed"
        if total_posts >= 10 and avg_quality >= 7.5: maturity = "evergreen"
        elif total_posts >= 7: maturity = "thriving"
        elif total_posts >= 4: maturity = "growing"
        elif total_posts >= 2: maturity = "sprout"
        with self._cursor() as c:
            c.execute("""
                UPDATE niches SET total_posts=?, avg_quality=?, maturity=?, last_post_at=?
                WHERE slug=?
            """, (total_posts, round(avg_quality, 1), maturity, datetime.now().isoformat(), slug))

    def add_post(self, niche_slug: str, title: str, filename: str,
                 product_name: str = "", angle: str = "", quality_score: float = 0.0,
                 persona_id: str = ""):
        with self._cursor() as c:
            c.execute("""
                INSERT INTO posts (niche_slug, title, filename, product_name, angle,
                                    quality_score, persona_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (niche_slug, title, filename, product_name, angle,
                  quality_score, persona_id, datetime.now().isoformat()))

    def get_posts_for_niche(self, niche_slug: str) -> list:
        with self._cursor() as c:
            c.execute("SELECT * FROM posts WHERE niche_slug=? ORDER BY created_at DESC", (niche_slug,))
            keys = ["id","niche_slug","title","filename","product_name","angle",
                    "quality_score","persona_id","deployment_status","created_at"]
            return [dict(zip(keys, row)) for row in c.fetchall()]

    def enqueue(self, niche_slug: str, stage: str, priority: int = 10, payload: dict = None):
        with self._cursor() as c:
            c.execute("""
                INSERT INTO queue (niche_slug, stage, priority, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (niche_slug, stage, priority, json.dumps(payload or {}), datetime.now().isoformat()))

    def dequeue(self) -> dict:
        with self._cursor() as c:
            c.execute("""
                SELECT * FROM queue
                WHERE locked_until IS NULL OR locked_until < datetime('now')
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            """)
            row = c.fetchone()
            if not row:
                return None
            task = {
                "id": row[0], "niche_slug": row[1], "stage": row[2],
                "priority": row[3], "payload": json.loads(row[4]) if row[4] else {},
                "created_at": row[5]
            }
            c.execute("UPDATE queue SET locked_until=datetime('now','+5 minutes') WHERE id=?", (task["id"],))
            return task

    def complete_queue_item(self, task_id: int):
        with self._cursor() as c:
            c.execute("DELETE FROM queue WHERE id=?", (task_id,))

    def fail_queue_item(self, task_id: int):
        with self._cursor() as c:
            c.execute("DELETE FROM queue WHERE id=?", (task_id,))

    def upsert_persona(self, persona_id: str, niche: str, persona: dict):
        with self._cursor() as c:
            c.execute("""
                INSERT INTO persona_registry (persona_id, niche, persona_json, created_at, last_used)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(persona_id) DO UPDATE SET
                    last_used=excluded.last_used,
                    persona_json=excluded.persona_json
            """, (persona_id, niche, json.dumps(persona), datetime.now().isoformat(), datetime.now().isoformat()))

    def update_persona_performance(self, persona_id: str, quality_score: float = 0,
                                    views: int = 0, clicks: int = 0, conversions: int = 0):
        with self._cursor() as c:
            c.execute("""
                UPDATE persona_registry SET
                    post_count = post_count + 1,
                    impressions = impressions + ?,
                    clicks = clicks + ?,
                    conversions = conversions + ?,
                    avg_quality = CASE WHEN post_count > 0
                        THEN (avg_quality * post_count + ?) / (post_count + 1)
                        ELSE ? END,
                    last_used = ?
                WHERE persona_id=?
            """, (views, clicks, conversions, quality_score, quality_score, datetime.now().isoformat(), persona_id))

    def get_personas_for_niche(self, niche: str) -> list:
        with self._cursor() as c:
            c.execute("SELECT * FROM persona_registry WHERE niche=?", (niche,))
            keys = ["persona_id","niche","persona_json","created_at","last_used",
                    "post_count","avg_quality","impressions","clicks","conversions"]
            return [dict(zip(keys, row)) for row in c.fetchall()]

    def log_model_metric(self, provider: str, time_ms: float, tokens: int):
        with self._cursor() as c:
            c.execute("INSERT INTO model_metrics (provider, time_ms, tokens, created_at) VALUES (?, ?, ?, ?)",
                      (provider, time_ms, tokens, datetime.now().isoformat()))

    def get_model_stats(self) -> list:
        with self._cursor() as c:
            c.execute("""
                SELECT provider, COUNT(*) as calls, AVG(time_ms) as avg_time,
                       SUM(tokens) as total_tokens
                FROM model_metrics
                WHERE created_at > datetime('now', '-7 days')
                GROUP BY provider
            """)
            keys = ["provider", "calls", "avg_time_ms", "total_tokens"]
            return [dict(zip(keys, row)) for row in c.fetchall()]

    def get_opportunities(self, status: str = "pending", limit: int = 10) -> list:
        with self._cursor() as c:
            c.execute("""
                SELECT * FROM queue WHERE stage=? ORDER BY priority DESC, created_at ASC LIMIT ?
            """, (status, limit))
            keys = ["id", "niche_slug", "stage", "priority", "payload", "created_at"]
            rows = []
            for row in c.fetchall():
                item = dict(zip(keys, row))
                if isinstance(item.get("payload"), str):
                    item["payload"] = json.loads(item["payload"])
                rows.append(item)
            return rows

    def add_opportunity(self, niche: str, score: float = 0.0, payload: dict = None):
        self.enqueue(niche, "pending", priority=max(1, int(score * 10)), payload=payload or {})

    def update_opportunity_status(self, opp_id: int, status: str):
        with self._cursor() as c:
            c.execute("UPDATE queue SET stage=? WHERE id=?", (status, opp_id))

    def get_cta_stats(self) -> list:
        with self._cursor() as c:
            c.execute("""
                SELECT json_extract(payload, '$.cta_id') as cta_id,
                       json_extract(payload, '$.niche') as niche,
                       json_extract(payload, '$.cta_text') as cta_text,
                       json_extract(payload, '$.cta_type') as cta_type,
                       json_extract(payload, '$.impressions') as impressions,
                       json_extract(payload, '$.clicks') as clicks,
                       json_extract(payload, '$.conversions') as conversions
                FROM queue
                WHERE stage='cta_tracked'
            """)
            rows = []
            for row in c.fetchall():
                impressions = int(row[4] or 0)
                clicks = int(row[5] or 0)
                rows.append({
                    "cta_id": row[0],
                    "niche": row[1],
                    "cta_text": row[2],
                    "cta_type": row[3],
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": int(row[6] or 0),
                    "click_rate": clicks / impressions if impressions > 0 else 0,
                })
            return rows

    def get_cta_summary(self) -> dict:
        stats = self.get_cta_stats()
        total_impressions = sum(s["impressions"] for s in stats)
        total_clicks = sum(s["clicks"] for s in stats)
        total_conversions = sum(s["conversions"] for s in stats)
        return {
            "total_ctas": len(stats),
            "overall_click_rate": total_clicks / total_impressions if total_impressions > 0 else 0,
            "total_conversions": total_conversions,
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
        }

    def get_all_intel_patterns(self) -> list:
        with self._cursor() as c:
            c.execute("""
                SELECT payload FROM queue WHERE stage='intel_pattern' ORDER BY created_at DESC LIMIT 50
            """)
            patterns = []
            for row in c.fetchall():
                try:
                    data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    if isinstance(data, dict):
                        patterns.append(data)
                except (json.JSONDecodeError, TypeError):
                    pass
            return patterns

    def import_legacy_json(self, json_path: Path):
        if not json_path.exists():
            return
        data = json.loads(json_path.read_text())
        deployed = data.get("deployed", [])
        completed = data.get("completed", [])
        all_slugs = list(dict.fromkeys(deployed + completed))
        perf = data.get("performance", {})
        for slug in all_slugs:
            name = slug.replace("_", " ").title()
            pdata = perf.get(slug, {})
            if isinstance(pdata, dict):
                self.upsert_niche(slug, name, pdata.get("category", "Other"))
                self.update_niche_analytics(slug, pdata.get("ga4_views", 0),
                                            pdata.get("ga4_users", 0),
                                            pdata.get("ga4_score", 0))
        for item in data.get("queue", []):
            self.enqueue(item.get("slug", "unknown"), item.get("stage", "products"),
                         payload={"niche": item.get("niche", "")})
        for pid, pdata in data.get("persona_registry", {}).items():
            self.upsert_persona(pid, pdata.get("niche", ""), pdata.get("persona", {}))
            perf_data = pdata.get("performance", {})
            self.update_persona_performance(pid, perf_data.get("avg_quality", 0),
                                            perf_data.get("impressions", 0),
                                            perf_data.get("clicks", 0),
                                            perf_data.get("conversions", 0))
        logger.info(f"Migrated {len(all_slugs)} niches from legacy JSON")
