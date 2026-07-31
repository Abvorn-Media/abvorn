"""Price alert system for Abvorn."""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DB_PATH = Path("data/price_alerts.db")


def _ensure_db() -> None:
    try:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(_DB_PATH)
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                chat_id TEXT,
                asin TEXT NOT NULL,
                target_price REAL NOT NULL,
                current_price REAL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            )
            """
        )
        con.commit()
        con.close()
    except Exception as e:
        logger.warning("Price alerts DB init skipped: %s", e)


class PriceAlertSystem:
    """Persist and evaluate user price alerts."""

    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self.db_path = db_path
        _ensure_db()

    def add_alert(
        self,
        asin: str,
        target_price: float,
        current_price: Optional[float] = None,
        email: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> bool:
        if not asin or target_price is None:
            return False
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO price_alerts (email, chat_id, asin, target_price, current_price, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
                """,
                (email, chat_id, asin, float(target_price), current_price, datetime.now().isoformat()),
            )
            con.commit()
            con.close()
            return True
        except Exception as e:
            logger.warning("Add alert failed: %s", e)
            return False

    def check_alerts(self, asin: str, current_price: float) -> List[Dict[str, Any]]:
        if asin is None or current_price is None:
            return []
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                """
                SELECT id, email, chat_id, target_price FROM price_alerts
                WHERE asin = ? AND status = 'active' AND target_price >= ?
                """,
                (asin, float(current_price)),
            )
            rows = cur.fetchall()
            con.close()
            return [
                {
                    "id": r[0],
                    "email": r[1],
                    "chat_id": r[2],
                    "target_price": r[3],
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning("Alert check failed for %s: %s", asin, e)
            return []

    def trigger_alert(self, alert_id: int) -> bool:
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                "UPDATE price_alerts SET status = 'triggered' WHERE id = ?",
                (alert_id,),
            )
            con.commit()
            con.close()
            return True
        except Exception as e:
            logger.warning("Alert trigger failed for %s: %s", alert_id, e)
            return False

    def get_alerts_for_user(self, email: Optional[str] = None, chat_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not email and not chat_id:
            return []
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            if email:
                cur.execute(
                    "SELECT asin, target_price, current_price, status, created_at FROM price_alerts WHERE email = ?",
                    (email,),
                )
            else:
                cur.execute(
                    "SELECT asin, target_price, current_price, status, created_at FROM price_alerts WHERE chat_id = ?",
                    (chat_id,),
                )
            rows = cur.fetchall()
            con.close()
            return [
                {
                    "asin": r[0],
                    "target_price": r[1],
                    "current_price": r[2],
                    "status": r[3],
                    "created_at": r[4],
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning("Alert fetch failed: %s", e)
            return []
