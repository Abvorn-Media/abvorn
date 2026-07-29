"""Feedback loop — tracks engagement, measures performance, feeds insights back."""

import json
import os
import logging
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("abvorn.feedback_loop")

PERF_DB = Path("data/performance")
PERF_DB_FILE = PERF_DB / "hook_performance.db"

FEEDBACK_LEARNINGS_FILE = Path("data/feedback_learnings.json")


class FeedbackLoop:
    """
    Tracks engagement, analyzes performance, and feeds insights back.

    Three core functions:
    1. track_engagement — record metrics from posts
    2. analyze_performance — identify what works best
    3. save_learning — persist insights to the system knowledge base
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or PERF_DB_FILE
        PERF_DB.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS hook_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                hook_style TEXT,
                product_id TEXT,
                engagement_score REAL,
                views INTEGER,
                likes INTEGER,
                comments INTEGER,
                shares INTEGER,
                saves INTEGER,
                completion_rate REAL,
                timestamp TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS content_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                product_id TEXT,
                content_type TEXT,
                score REAL,
                timestamp TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS system_learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                learning_type TEXT,
                key TEXT,
                value TEXT,
                confidence REAL,
                applied BOOLEAN,
                timestamp TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def track_engagement(self, platform: str, post_data: Dict[str, Any]):
        """Track engagement metrics for a published post."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        metrics = {
            'views': post_data.get('views', 0),
            'likes': post_data.get('likes', 0),
            'comments': post_data.get('comments', 0),
            'shares': post_data.get('shares', 0),
            'saves': post_data.get('saves', 0),
            'completion_rate': post_data.get('completion_rate', 0.0),
        }

        score = self._calculate_score(metrics)

        c.execute('''
            INSERT INTO hook_performance 
            (platform, hook_style, product_id, engagement_score, views, likes, comments, shares, saves, completion_rate, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            platform,
            post_data.get('hook_style', 'unknown'),
            post_data.get('product_id', 'unknown'),
            score,
            metrics['views'],
            metrics['likes'],
            metrics['comments'],
            metrics['shares'],
            metrics['saves'],
            metrics['completion_rate'],
            datetime.now().isoformat(),
        ))

        conn.commit()
        conn.close()
        logger.info(f"Tracked engagement on {platform}: score={score:.3f}")

    def _calculate_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate weighted engagement score from raw metrics."""
        weights = {
            'views': 0.1,
            'likes': 0.3,
            'comments': 0.5,
            'shares': 0.8,
            'saves': 0.6,
            'completion_rate': 0.9,
        }

        score = 0.0
        total_weight = 0.0

        for metric, value in metrics.items():
            if metric not in weights:
                continue
            if metric == 'completion_rate':
                normalized = value / 100.0 if value else 0
            elif metric == 'views':
                normalized = min(value / 5000.0, 1.0)
            elif metric == 'likes':
                normalized = min(value / 500.0, 1.0)
            elif metric in ('comments', 'shares', 'saves'):
                normalized = min(value / 50.0, 1.0)
            else:
                normalized = min(value / 1000.0, 1.0)

            score += normalized * weights[metric]
            total_weight += weights[metric]

        return min(score / total_weight, 1.0) if total_weight > 0 else 0.0

    def get_best_hook_style(self, platform: str) -> Optional[str]:
        """Get the best-performing hook style for a platform."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute('''
            SELECT hook_style, AVG(engagement_score) as avg_score
            FROM hook_performance
            WHERE platform = ?
            GROUP BY hook_style
            HAVING COUNT(*) >= 3
            ORDER BY avg_score DESC
            LIMIT 1
        ''', (platform,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def get_platform_report(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get per-platform performance report."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute('''
            SELECT platform, 
                   AVG(engagement_score) as avg_score, 
                   COUNT(*) as post_count,
                   SUM(views) as total_views,
                   SUM(likes) as total_likes,
                   SUM(shares) as total_shares
            FROM hook_performance
            WHERE timestamp > ?
            GROUP BY platform
            ORDER BY avg_score DESC
        ''', (cutoff,))
        rows = c.fetchall()
        conn.close()
        return [
            {
                "platform": r[0],
                "avg_score": round(r[1], 3),
                "post_count": r[2],
                "total_views": r[3],
                "total_likes": r[4],
                "total_shares": r[5],
            }
            for r in rows
        ]

    def get_hook_report(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get per-hook-style performance report."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute('''
            SELECT hook_style, 
                   AVG(engagement_score) as avg_score, 
                   COUNT(*) as post_count
            FROM hook_performance
            WHERE timestamp > ?
            GROUP BY hook_style
            ORDER BY avg_score DESC
        ''', (cutoff,))
        rows = c.fetchall()
        conn.close()
        return [
            {
                "hook_style": r[0],
                "avg_score": round(r[1], 3),
                "post_count": r[2],
            }
            for r in rows
        ]

    def save_learning(self, learning_type: str, key: str, 
                       value: Any, confidence: float):
        """Save a system learning for future reference."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute('''
            INSERT INTO system_learnings (learning_type, key, value, confidence, applied, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            learning_type,
            key,
            json.dumps(value),
            confidence,
            False,
            datetime.now().isoformat(),
        ))
        conn.commit()
        conn.close()
        logger.info(f"Learning saved: {learning_type} / {key} (confidence={confidence})")

    def get_learnings(self, learning_type: str = None, 
                        limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve stored learnings."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        if learning_type:
            c.execute('''
                SELECT learning_type, key, value, confidence, applied, timestamp
                FROM system_learnings
                WHERE learning_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (learning_type, limit))
        else:
            c.execute('''
                SELECT learning_type, key, value, confidence, applied, timestamp
                FROM system_learnings
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
        rows = c.fetchall()
        conn.close()
        return [
            {
                "learning_type": r[0],
                "key": r[1],
                "value": json.loads(r[2]),
                "confidence": r[3],
                "applied": bool(r[4]),
                "timestamp": r[5],
            }
            for r in rows
        ]

    def get_performance_report(self, days: int = 30) -> Dict[str, Any]:
        """Get a comprehensive performance report."""
        return {
            "period_days": days,
            "generated_at": datetime.now().isoformat(),
            "platforms": self.get_platform_report(days),
            "hooks": self.get_hook_report(days),
            "learnings_count": len(self.get_learnings()),
        }

    def apply_learning(self, key: str) -> bool:
        """Mark a learning as applied."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute('''
            UPDATE system_learnings SET applied = 1 WHERE key = ?
        ''', (key,))
        updated = c.rowcount > 0
        conn.commit()
        conn.close()
        if updated:
            logger.info(f"Learning applied: {key}")
        return updated


def save_report_json(report: Dict[str, Any], path: Path = None):
    """Save a performance report as JSON."""
    path = path or Path("data/reports") / f"report_{datetime.now().strftime('%Y%m%d')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Report saved: {path}")
    return str(path)


if __name__ == "__main__":
    loop = FeedbackLoop()

    # Test tracking
    loop.track_engagement("tiktok", {
        'platform': 'tiktok',
        'hook_style': 'curiosity_gap',
        'product_id': 'test-123',
        'views': 5000,
        'likes': 300,
        'comments': 50,
        'shares': 20,
        'saves': 100,
        'completion_rate': 0.7,
    })

    # Test report
    report = loop.get_performance_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))