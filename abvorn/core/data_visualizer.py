"""data_visualizer.py — Abvorn dashboard chart generator.

Reads the unified database and emits PNG charts (economic trend,
subscriber growth, niche performance) plus a compact JSON summary.
"""

import sqlite3
from pathlib import Path

from abvorn.core.unified_database import get_unified_db


class DataVisualizer:
    def __init__(self):
        self.db = get_unified_db()
        self.output_dir = Path("docs/visualizations")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_charts(self):
        charts = {}
        charts["economic_trend"] = self._plot_economic_trend()
        charts["subscriber_growth"] = self._plot_subscriber_growth()
        charts["niche_performance"] = self._plot_niche_performance()
        return charts

    def _plot_economic_trend(self) -> str:
        try:
            import pandas as pd
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            return ""
        conn = sqlite3.connect(self.db.db_path)
        df = pd.read_sql_query("SELECT timestamp, profit FROM economic_records ORDER BY timestamp", conn)
        conn.close()
        if df.empty:
            return ""
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df['timestamp'], df['profit'], color='#c98a2c')
        ax.set_title('Economic Profit Over Time')
        ax.grid(True, alpha=0.3)
        out = self.output_dir / "economic_trend.png"
        plt.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return str(out)

    def _plot_subscriber_growth(self) -> str:
        try:
            import pandas as pd
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            return ""
        conn = sqlite3.connect(self.db.db_path)
        df = pd.read_sql_query("SELECT subscribed_at FROM subscribers ORDER BY subscribed_at", conn)
        conn.close()
        if df.empty:
            return ""
        df['subscribed_at'] = pd.to_datetime(df['subscribed_at'])
        df['cum'] = range(1, len(df) + 1)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df['subscribed_at'], df['cum'], color='#4caf50')
        ax.set_title('Subscriber Growth')
        ax.grid(True, alpha=0.3)
        out = self.output_dir / "subscriber_growth.png"
        plt.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return str(out)

    def _plot_niche_performance(self) -> str:
        try:
            import pandas as pd
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            return ""
        conn = sqlite3.connect(self.db.db_path)
        df = pd.read_sql_query(
            "SELECT niche, SUM(profit) as profit FROM economic_records GROUP BY niche ORDER BY profit DESC", conn)
        conn.close()
        if df.empty:
            return ""
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(df['niche'], df['profit'], color='#c98a2c')
        ax.set_title('Niche Performance by Profit')
        ax.set_xlabel('Total Profit ($)')
        out = self.output_dir / "niche_performance.png"
        plt.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return str(out)

    def get_json_summary(self) -> dict:
        conn = sqlite3.connect(self.db.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as total FROM subscribers")
        total_subscribers = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(profit), 0) as total FROM economic_records")
        total_profit = c.fetchone()[0]
        conn.close()
        return {"subscribers": total_subscribers, "total_profit": total_profit}