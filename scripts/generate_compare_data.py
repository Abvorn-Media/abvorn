"""Generate comparison data artifacts from price_history.db."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.price_tracker import PriceTracker


def main() -> None:
    base = Path("docs/data")
    base.mkdir(parents=True, exist_ok=True)

    tracker = PriceTracker()

    latest = tracker.get_latest_prices()
    with open(base / "latest_prices.json", "w", encoding="utf-8") as f:
        json.dump(latest, f, indent=2)

    sparkline_buf = []
    for product_id, rows in _all_history(tracker):
        prices = [r["price"] for r in rows]
        if len(prices) >= 1:
            sparkline_buf.append({
                "id": product_id,
                "prices": prices[-14:],
            })
    with open(base / "price_sparklines.json", "w", encoding="utf-8") as f:
        json.dump(sparkline_buf, f, indent=2)

    print(f"Wrote {len(latest)} latest prices, {len(sparkline_buf)} sparklines.")


def _all_history(tracker, days=30):
    con = sqlite3.connect(tracker.db_path)
    cur = con.cursor()
    cutoff = datetime.now() - timedelta(days=days)
    cur.execute(
        """
        SELECT product_id, timestamp, price FROM price_history
        WHERE timestamp > ? ORDER BY product_id ASC, timestamp ASC
        """,
        (cutoff.isoformat(),),
    )
    rows = cur.fetchall()
    con.close()
    by_id = {}
    for pid, ts, price in rows:
        by_id.setdefault(pid, []).append({"date": ts, "price": price})
    return by_id.items()


if __name__ == "__main__":
    main()
