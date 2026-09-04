"""unified_database.py — Abvorn Data Intelligence Layer (Foundation).

Centralized SQLite database that the rest of the Evolution Stack builds on.
Single source of truth for subscribers, price alerts, campaigns, economics,
engagement and system metrics.
"""

import os
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class UnifiedDatabase:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.environ.get("ABVORN_DB_PATH", "data/abvorn_unified.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        conn = self._connect()
        c = conn.cursor()

        # Subscribers
        c.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                source TEXT,
                lead_magnet TEXT,
                subscribed_at TEXT,
                status TEXT DEFAULT 'active',
                preferences TEXT,
                listmonk_id INTEGER,
                email_count INTEGER DEFAULT 0,
                last_email TEXT
            )
        """)

        # Subscriber segments
        c.execute("""
            CREATE TABLE IF NOT EXISTS subscriber_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscriber_id INTEGER,
                segment_type TEXT,
                segment_value TEXT,
                created_at TEXT,
                FOREIGN KEY (subscriber_id) REFERENCES subscribers(id)
            )
        """)

        # Email campaigns
        c.execute("""
            CREATE TABLE IF NOT EXISTS email_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                subject TEXT,
                content TEXT,
                listmonk_campaign_id INTEGER,
                sent_at TEXT,
                recipients INTEGER,
                opened INTEGER DEFAULT 0,
                clicked INTEGER DEFAULT 0
            )
        """)

        # Email logs
        c.execute("""
            CREATE TABLE IF NOT EXISTS email_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscriber_id INTEGER,
                campaign_id INTEGER,
                sent_at TEXT,
                opened_at TEXT,
                clicked_at TEXT,
                FOREIGN KEY (subscriber_id) REFERENCES subscribers(id),
                FOREIGN KEY (campaign_id) REFERENCES email_campaigns(id)
            )
        """)

        # Price alerts
        c.execute("""
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                asin TEXT,
                product_name TEXT,
                target_price REAL,
                current_price REAL,
                status TEXT DEFAULT 'active',
                created_at TEXT,
                triggered_at TEXT,
                FOREIGN KEY (email) REFERENCES subscribers(email)
            )
        """)

        # Engagement events
        c.execute("""
            CREATE TABLE IF NOT EXISTS engagement_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscriber_id INTEGER,
                event_type TEXT,
                event_data TEXT,
                product_id TEXT,
                timestamp TEXT,
                FOREIGN KEY (subscriber_id) REFERENCES subscribers(id)
            )
        """)

        # Economic records
        c.execute("""
            CREATE TABLE IF NOT EXISTS economic_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT,
                niche TEXT,
                revenue REAL,
                cost_ai REAL,
                cost_compute REAL,
                cost_affiliate REAL,
                profit REAL,
                timestamp TEXT
            )
        """)

        # AI cost log (A3: durable per-provider cost tracking)
        c.execute("""
            CREATE TABLE IF NOT EXISTS cost_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT,
                model TEXT,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                rate_per_1k_in REAL DEFAULT 0.0,
                rate_per_1k_out REAL DEFAULT 0.0,
                cost REAL DEFAULT 0.0,
                source TEXT,
                timestamp TEXT
            )
        """)

        # System metrics
        c.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drive_score REAL,
                ambition_level REAL,
                total_niches INTEGER,
                total_articles INTEGER,
                total_clicks INTEGER,
                timestamp TEXT
            )
        """)

        # Hindsight reflections (ReflectionStore records)
        c.execute("""
            CREATE TABLE IF NOT EXISTS reflections (
                id TEXT PRIMARY KEY,
                generation INTEGER,
                content_id TEXT,
                platform TEXT,
                original_content TEXT,
                performance_data TEXT,
                what_worked TEXT,
                what_failed TEXT,
                why_worked TEXT,
                why_failed TEXT,
                key_learnings TEXT,
                meta_reflection TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT,
                generated_by TEXT
            )
        """)

        conn.commit()

        # Indexes on frequently queried columns
        c.execute("CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_subscribers_status ON subscribers(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_subscribers_subscribed_at ON subscribers(subscribed_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_price_alerts_status ON price_alerts(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_price_alerts_email ON price_alerts(email)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_engagement_events_sub ON engagement_events(subscriber_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_engagement_events_ts ON engagement_events(timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_economic_records_ts ON economic_records(timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cost_log_ts ON cost_log(timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cost_log_provider ON cost_log(provider)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_metrics_ts ON system_metrics(timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_reflections_created_at ON reflections(created_at)")

        conn.commit()
        conn.close()
        logger.info("Data intelligence: unified database initialized")

    def add_subscriber(self, email: str, name: str = "", source: str = "unknown",
                       lead_magnet: str = "", preferences: dict = None,
                       listmonk_id: int = None) -> int:
        conn = self._connect()
        c = conn.cursor()
        now = datetime.now().isoformat()
        try:
            c.execute("""
                INSERT INTO subscribers
                (email, name, source, lead_magnet, subscribed_at, status, preferences, listmonk_id)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            """, (email, name, source, lead_magnet, now,
                  json.dumps(preferences or {}), listmonk_id))
            sid = c.lastrowid
            conn.commit()
            conn.close()
            return sid
        except sqlite3.IntegrityError:
            c.execute("""
                UPDATE subscribers SET name=?, source=?, lead_magnet=?, preferences=?, listmonk_id=?
                WHERE email=?
            """, (name, source, lead_magnet, json.dumps(preferences or {}), listmonk_id, email))
            conn.commit()
            sid = c.lastrowid
            conn.close()
            return sid

    def get_subscriber(self, email: str) -> Optional[Dict]:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT * FROM subscribers WHERE email = ?", (email,))
        row = c.fetchone()
        columns = [desc[0] for desc in c.description]
        conn.close()
        if row:
            return dict(zip(columns, row))
        return None

    def add_subscriber_segment(self, subscriber_id: int, segment_type: str, segment_value: str):
        conn = self._connect()
        c = conn.cursor()
        c.execute("""
            INSERT INTO subscriber_segments (subscriber_id, segment_type, segment_value, created_at)
            VALUES (?, ?, ?, ?)
        """, (subscriber_id, segment_type, segment_value, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def get_subscribers_by_segment(self, segment_type: str, segment_value: str) -> List[Dict]:
        conn = self._connect()
        c = conn.cursor()
        c.execute("""
            SELECT s.* FROM subscribers s
            JOIN subscriber_segments ss ON s.id = ss.subscriber_id
            WHERE ss.segment_type = ? AND ss.segment_value = ?
        """, (segment_type, segment_value))
        rows = c.fetchall()
        columns = [desc[0] for desc in c.description]
        conn.close()
        return [dict(zip(columns, row)) for row in rows]

    def add_price_alert(self, email: str, asin: str, product_name: str,
                        target_price: float, current_price: float) -> int:
        conn = self._connect()
        c = conn.cursor()
        c.execute("""
            INSERT INTO price_alerts (email, asin, product_name, target_price, current_price, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
        """, (email, asin, product_name, target_price, current_price, datetime.now().isoformat()))
        conn.commit()
        c.execute("SELECT last_insert_rowid()")
        aid = c.fetchone()[0]
        conn.close()
        return aid

    def get_triggered_alerts(self) -> List[Dict]:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT * FROM price_alerts WHERE status = 'active' AND current_price <= target_price")
        rows = c.fetchall()
        columns = [desc[0] for desc in c.description]
        conn.close()
        return [dict(zip(columns, row)) for row in rows]

    def create_campaign(self, name: str, subject: str, content: str,
                        listmonk_campaign_id: int = None) -> int:
        conn = self._connect()
        c = conn.cursor()
        c.execute("""
            INSERT INTO email_campaigns (name, subject, content, listmonk_campaign_id, sent_at, recipients)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (name, subject, content, listmonk_campaign_id, datetime.now().isoformat()))
        conn.commit()
        c.execute("SELECT last_insert_rowid()")
        cid = c.fetchone()[0]
        conn.close()
        return cid

    def log_email_send(self, subscriber_id: int, campaign_id: int):
        conn = self._connect()
        c = conn.cursor()
        c.execute("""
            INSERT INTO email_logs (subscriber_id, campaign_id, sent_at)
            VALUES (?, ?, ?)
        """, (subscriber_id, campaign_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def sync_subscribers_from_listmonk(self, listmonk_client):
        subscribers = listmonk_client.get_subscribers()
        for sub in subscribers:
            self.add_subscriber(
                email=sub['email'],
                name=sub.get('name', ''),
                source='listmonk_sync',
                listmonk_id=sub.get('id')
            )
        logger.info("Data intelligence: synced %s subscribers from Listmonk", len(subscribers))

    def import_economic_records(self, file_path: str = "data/economic_records.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
            conn = self._connect()
            c = conn.cursor()
            for r in records:
                c.execute("""
                    INSERT INTO economic_records
                    (article_id, niche, revenue, cost_ai, cost_compute, cost_affiliate, profit, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (r.get('article_id'), r.get('niche'), r.get('revenue', 0),
                      r.get('cost_ai', 0), r.get('cost_compute', 0), r.get('cost_affiliate', 0),
                      r.get('profit', 0), r.get('timestamp', datetime.now().isoformat())))
            conn.commit()
            conn.close()
            logger.info("Imported %s economic records", len(records))
        except Exception as e:
            logger.error("Failed to import economic records: %s", e)

    def log_cost(self, provider: str, model: str, tokens_in: int = 0,
                 tokens_out: int = 0, rate_per_1k_in: float = 0.0,
                 rate_per_1k_out: float = 0.0, cost: float = 0.0,
                 source: str = ""):
        """Persist a per-provider AI cost entry (A3)."""
        conn = self._connect()
        c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO cost_log
                (provider, model, tokens_in, tokens_out, rate_per_1k_in, rate_per_1k_out,
                 cost, source, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                provider, model, tokens_in, tokens_out, rate_per_1k_in, rate_per_1k_out,
                cost, source, datetime.now().isoformat(),
            ))
            conn.commit()
            return c.lastrowid
        except Exception as e:
            logger.error("Failed to log cost: %s", e)
            return None
        finally:
            conn.close()

    def get_cost_summary(self) -> Dict[str, Any]:
        """Aggregate durable AI cost from cost_log."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(cost), 0), COUNT(*) FROM cost_log")
        total_cost, count = c.fetchone()
        c.execute("SELECT COALESCE(SUM(cost), 0) FROM cost_log WHERE source = 'affiliate'")
        affiliate_cost = c.fetchone()[0]
        conn.close()
        return {
            "total_cost": round(total_cost, 6),
            "entries": count,
            "affiliate_cost": round(affiliate_cost, 6),
        }

    def get_summary(self) -> Dict:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM subscribers")
        total_subscribers = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM price_alerts WHERE status = 'active'")
        active_alerts = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(profit), 0) FROM economic_records")
        total_profit = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM email_campaigns")
        total_campaigns = c.fetchone()[0]
        conn.close()
        return {
            "total_subscribers": total_subscribers,
            "active_alerts": active_alerts,
            "total_profit": total_profit,
            "total_campaigns": total_campaigns
        }

    def save_reflection(self, reflection: Dict[str, Any]) -> bool:
        """Persist a reflection record (INSERT OR REPLACE by id)."""
        def _dumps(value):
            return json.dumps(value) if value is not None else None

        try:
            conn = self._connect()
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO reflections (
                    id, generation, content_id, platform,
                    original_content, performance_data,
                    what_worked, what_failed, why_worked, why_failed,
                    key_learnings, meta_reflection, status,
                    created_at, updated_at, generated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                reflection.get("id"),
                reflection.get("generation"),
                reflection.get("content_id"),
                reflection.get("platform"),
                _dumps(reflection.get("original_content")),
                _dumps(reflection.get("performance_data")),
                _dumps(reflection.get("what_worked")),
                _dumps(reflection.get("what_failed")),
                _dumps(reflection.get("why_worked")),
                _dumps(reflection.get("why_failed")),
                _dumps(reflection.get("key_learnings")),
                _dumps(reflection.get("meta_reflection")),
                reflection.get("status"),
                reflection.get("created_at"),
                reflection.get("updated_at"),
                reflection.get("generated_by"),
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error("Failed to save reflection: %s", e)
            return False

    def get_recent_reflections(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent reflections as dicts with JSON fields decoded."""
        def _loads(value):
            if value is None:
                return None
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return value

        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT * FROM reflections ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        columns = [desc[0] for desc in c.description]
        conn.close()
        results = []
        for row in rows:
            record = dict(zip(columns, row))
            for field in ("original_content", "performance_data", "what_worked",
                          "what_failed", "why_worked", "why_failed",
                          "key_learnings", "meta_reflection"):
                record[field] = _loads(record.get(field))
            results.append(record)
        return results

    def get_reflection_summary(self) -> Dict[str, Any]:
        """Aggregate reflection counts by platform."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM reflections")
        total = c.fetchone()[0]
        c.execute("SELECT platform, COUNT(*) FROM reflections GROUP BY platform")
        platforms = dict(c.fetchall())
        conn.close()
        return {"total": total, "platforms": platforms}


_instance = None


def get_unified_db() -> UnifiedDatabase:
    global _instance
    if _instance is None:
        _instance = UnifiedDatabase()
    return _instance