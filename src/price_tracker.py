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

    def get_latest_prices(self) -> Dict[str, float]:
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                """
                SELECT product_id, MAX(timestamp), price
                FROM price_history
                GROUP BY product_id
                ORDER BY product_id
                """
            )
            rows = cur.fetchall()
            con.close()
            return {row[0]: row[2] for row in rows if row[2] is not None}
        except Exception as e:
            logger.warning("Latest prices fetch failed: %s", e)
            return {}

    # ── CamelCamelCamel Integration ─────────────────────────────────────
    def fetch_camel_history(self, asin: str) -> List[Dict[str, Any]]:
        """Best-effort CamelCamelCamel price-history fetch.

        CamelCamelCamel does not expose a public JSON API anymore, so this
        attempts a lightweight page scrape of the product history table as a
        fallback when our own price_history.db has sparse data.
        """
        if not asin:
            return []
        try:
            import requests  # local import so the module still loads without requests
            url = f"https://camelcamelcamel.com/product/{asin}"
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; Abvorn/1.0; +https://abvorn.com)",
                "Accept": "text/html,application/xhtml+xml",
            }
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code != 200:
                return []
            text = resp.text
            # Extract price history table rows from CamelCamelCamel HTML
            # The history table has rows like: <td>2024-01-01</td><td>$199.99</td>...
            import re
            rows = re.findall(
                r'<td>(\d{4}-\d{2}-\d{2})</td>\s*<td[^>]*>\s*\$?([0-9]+(?:\.[0-9]{2})?)',
                text,
            )
            if not rows:
                return []
            result = []
            for date_str, price_str in rows[:120]:
                try:
                    result.append({"date": date_str, "price": float(price_str)})
                except ValueError:
                    continue
            return result
        except Exception as e:
            logger.warning("CamelCamelCamel fetch failed for %s: %s", asin, e)
            return []

    def get_enriched_history(self, product_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Return merged history: local DB first, CamelCamelCamel, then PriceGhost as fallback."""
        local = self.get_history(product_id, days=days)
        if len(local) >= 3:
            return local
        camel = self.fetch_camel_history(product_id)
        if camel and len(camel) > len(local):
            return camel
        ghost = self._fetch_priceghost_history(product_id)
        if ghost and len(ghost) > len(local):
            return ghost
        return local

    def _fetch_priceghost_history(self, product_id: str) -> List[Dict[str, Any]]:
        try:
            from src.priceghost_client import get_priceghost
            client = get_priceghost()
            watches = client.get_watches(limit=50)
            watch = next((w for w in watches if product_id in w.get("url", "")), None)
            if not watch:
                watch = client.create_watch(url=f"https://www.amazon.com/dp/{product_id}")
            if not watch:
                return []
            history = client.get_price_history(watch["id"], limit=30)
            return [{"date": h.get("created_at", ""), "price": float(h.get("price", 0))} for h in history if h.get("price") is not None]
        except Exception:
            return []

    def create_priceghost_watch(self, product_id: str, product_url: str, target_price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        try:
            from src.priceghost_client import get_priceghost
            client = get_priceghost()
            return client.create_watch(url=product_url, target_price=target_price)
        except Exception:
            return None
