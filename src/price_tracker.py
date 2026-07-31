"""Price history tracking for Abvorn product reviews."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DB_PATH = Path("data/price_history.db")


def _ensure_db() -> None:
    try:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(_DB_PATH)
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                product_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                price REAL NOT NULL,
                retailer TEXT NOT NULL DEFAULT 'amazon',
                PRIMARY KEY (product_id, timestamp)
            )
            """
        )
        con.commit()
        con.close()
    except Exception as e:
        logger.warning("Price history DB init skipped: %s", e)


class PriceTracker:
    """Persists per-product price snapshots and returns sparkline data."""

    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self.db_path = db_path
        _ensure_db()

    def record_price(
        self,
        product_id: str,
        price: Optional[float],
        retailer: str = "amazon",
    ) -> None:
        if not product_id or price is None:
            return
        try:
            price = float(str(price).replace("$", "").replace(",", "").strip())
        except (ValueError, TypeError):
            return
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO price_history (product_id, timestamp, price, retailer)
                VALUES (?, ?, ?, ?)
                """,
                (product_id, datetime.now().isoformat(), price, retailer),
            )
            con.commit()
            con.close()
        except Exception as e:
            logger.warning("Price record skipped for %s: %s", product_id, e)

    def get_history(
        self, product_id: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        if not product_id:
            return []
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cutoff = datetime.now() - timedelta(days=days)
            cur.execute(
                """
                SELECT timestamp, price FROM price_history
                WHERE product_id = ? AND timestamp > ?
                ORDER BY timestamp ASC
                """,
                (product_id, cutoff.isoformat()),
            )
            rows = cur.fetchall()
            con.close()
            return [{"date": r[0], "price": r[1]} for r in rows]
        except Exception as e:
            logger.warning("Price history fetch failed for %s: %s", product_id, e)
            return []

    def get_latest(self, product_id: str) -> Optional[float]:
        history = self.get_history(product_id, days=30)
        if history:
            return history[-1].get("price")
        return None
