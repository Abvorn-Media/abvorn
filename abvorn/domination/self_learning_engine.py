"""Self-Learning Engine — tracks hook performance, A/B test results,
and engagement metrics per platform to optimize future content."""

import logging, json, sqlite3, hashlib
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger("abvorn.domination.self_learning")


class SelfLearningEngine:
    """SQLite-backed analytics engine that learns which hooks work.

    Tracks:
    - Hook variants tested per platform
    - Engagement metrics per hook (likes, shares, comments, CTR)
    - Optimal posting times per niche
    - Sentiment → performance correlations
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = Path(db_path or Path.home() / ".abvorn" / "domination_learn.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hook_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hook_text TEXT NOT NULL,
                    niche TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    variant_group TEXT DEFAULT 'A',
                    impressions INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    conversions INTEGER DEFAULT 0,
                    tested_at TEXT DEFAULT (datetime('now')),
                    score REAL DEFAULT 0.0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS posting_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    niche TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    hour INTEGER NOT NULL,
                    avg_engagement REAL DEFAULT 0.0,
                    sample_size INTEGER DEFAULT 1,
                    last_updated TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_url TEXT NOT NULL UNIQUE,
                    niche TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    hook_used TEXT,
                    sentiment TEXT,
                    virality_score REAL DEFAULT 0.0,
                    total_engagement INTEGER DEFAULT 0,
                    posted_at TEXT,
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_hook_niche
                ON hook_tests(niche, platform)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_perf_niche
                ON content_performance(niche, platform)
            """)
            conn.commit()

    def record_hook_test(self, hook: str, niche: str, platform: str,
                         variant: str = "A") -> int:
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "INSERT INTO hook_tests (hook_text, niche, platform, variant_group) VALUES (?, ?, ?, ?)",
                (hook, niche, platform, variant),
            )
            conn.commit()
            return cur.lastrowid

    def record_engagement(self, hook_id: int, likes: int = 0, shares: int = 0,
                          comments: int = 0, clicks: int = 0,
                          conversions: int = 0, impressions: int = 1):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                UPDATE hook_tests SET
                    likes = likes + ?,
                    shares = shares + ?,
                    comments = comments + ?,
                    clicks = clicks + ?,
                    conversions = conversions + ?,
                    impressions = impressions + ?,
                    score = (CAST(likes + ? AS REAL) + CAST(shares + ? AS REAL) * 2
                             + CAST(comments + ? AS REAL) * 3 + CAST(clicks + ? AS REAL) * 1.5
                             + CAST(conversions + ? AS REAL) * 10)
                             / MAX(impressions + ?, 1)
                WHERE id = ?
            """, (likes, shares, comments, clicks, conversions, impressions,
                  likes, shares, comments, clicks, conversions, impressions,
                  hook_id))
            conn.commit()

    def record_post_performance(self, url: str, niche: str, platform: str,
                                hook: str = "", sentiment: str = "neutral",
                                virality_score: float = 0.0,
                                total_engagement: int = 0):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO content_performance
                    (post_url, niche, platform, hook_used, sentiment,
                     virality_score, total_engagement, posted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (url, niche, platform, hook, sentiment,
                  virality_score, total_engagement))
            conn.commit()

    def record_posting_time(self, niche: str, platform: str,
                            engagement: float):
        now = datetime.now()
        day = now.strftime("%A")
        hour = now.hour
        with sqlite3.connect(str(self.db_path)) as conn:
            existing = conn.execute("""
                SELECT avg_engagement, sample_size FROM posting_insights
                WHERE niche = ? AND platform = ? AND day_of_week = ? AND hour = ?
            """, (niche, platform, day, hour)).fetchone()
            if existing:
                avg, n = existing
                new_avg = (avg * n + engagement) / (n + 1)
                conn.execute("""
                    UPDATE posting_insights SET
                        avg_engagement = ?, sample_size = ?,
                        last_updated = datetime('now')
                    WHERE niche = ? AND platform = ? AND day_of_week = ? AND hour = ?
                """, (new_avg, n + 1, niche, platform, day, hour))
            else:
                conn.execute("""
                    INSERT INTO posting_insights
                        (niche, platform, day_of_week, hour, avg_engagement)
                    VALUES (?, ?, ?, ?, ?)
                """, (niche, platform, day, hour, engagement))
            conn.commit()

    def best_hooks(self, niche: str, platform: str, limit: int = 5) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT hook_text, score, impressions, likes, shares, comments,
                       clicks, conversions, tested_at
                FROM hook_tests
                WHERE niche = ? AND platform = ? AND impressions > 0
                ORDER BY score DESC
                LIMIT ?
            """, (niche, platform, limit)).fetchall()
            return [dict(r) for r in rows]

    def best_posting_times(self, niche: str, platform: str,
                           limit: int = 5) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT day_of_week, hour, avg_engagement, sample_size
                FROM posting_insights
                WHERE niche = ? AND platform = ? AND sample_size > 1
                ORDER BY avg_engagement DESC
                LIMIT ?
            """, (niche, platform, limit)).fetchall()
            return [dict(r) for r in rows]

    def hook_performance_summary(self, niche: str) -> dict:
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM hook_tests WHERE niche = ?", (niche,)
            ).fetchone()[0]
            avg_score = conn.execute(
                "SELECT COALESCE(AVG(score), 0) FROM hook_tests WHERE niche = ? AND score > 0",
                (niche,),
            ).fetchone()[0]
            best = conn.execute("""
                SELECT hook_text, score, platform FROM hook_tests
                WHERE niche = ? ORDER BY score DESC LIMIT 1
            """, (niche,)).fetchone()
            best_dict = None
            if best:
                best_dict = {
                    "hook_text": best[0],
                    "score": best[1],
                    "platform": best[2],
                }
            return {
                "niche": niche,
                "total_hooks_tested": total,
                "average_score": round(avg_score, 2),
                "best_hook": best_dict,
            }

    def generate_report(self) -> str:
        lines = ["# Domination Self-Learning Report", ""]
        with sqlite3.connect(str(self.db_path)) as conn:
            niches = conn.execute(
                "SELECT DISTINCT niche FROM hook_tests"
            ).fetchall()
            for (niche,) in niches:
                summary = self.hook_performance_summary(niche)
                lines.append(f"## {niche.replace('-', ' ').title()}")
                lines.append(f"- Hooks tested: {summary['total_hooks_tested']}")
                lines.append(f"- Avg score: {summary['average_score']}")
                if summary["best_hook"]:
                    lines.append(f"- Best hook: \"{summary['best_hook']['hook_text'][:60]}...\" ({summary['best_hook']['score']:.1f} on {summary['best_hook']['platform']})")

                best_times = conn.execute("""
                    SELECT platform, day_of_week, hour, avg_engagement
                    FROM posting_insights WHERE niche = ?
                    ORDER BY avg_engagement DESC LIMIT 3
                """, (niche,)).fetchall()
                if best_times:
                    lines.append("- Best posting times:")
                    for p, d, h, e in best_times:
                        lines.append(f"  - {p}: {d} at {h}:00 (avg engagement: {e:.1f})")
                lines.append("")

        return "\n".join(lines)
