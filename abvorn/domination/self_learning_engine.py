"""Self-Learning Engine — tracks hook performance, A/B test results,
and engagement metrics per platform to optimize future content."""

import logging, sqlite3
from pathlib import Path
from datetime import datetime

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

    def posted_urls(self) -> set[str]:
        """URLs already recorded as posted (used to avoid re-posting repeats)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT DISTINCT post_url FROM content_performance"
            ).fetchall()
            return {r[0] for r in rows if r[0]}

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
        with sqlite3.connect(str(self.db_path)) as conn:
            self._record_posting_time(conn, niche, platform, datetime.now(),
                                      engagement)

    def record_posting_time_at(self, niche: str, platform: str,
                               engagement: float, when: datetime):
        """Record a posting insight for a specific posted_at datetime, so
        historical content (old cycles, GA4 feedback) lands in the right
        day/hour bucket instead of today's."""
        with sqlite3.connect(str(self.db_path)) as conn:
            self._record_posting_time(conn, niche, platform, when, engagement)

    def _record_posting_time(self, conn, niche: str, platform: str,
                             when: datetime, engagement: float):
        day = when.strftime("%A")
        hour = when.hour
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

    def feed_ga4_engagement(self, analytics_by_slug: dict,
                            clicks_by_slug: dict | None = None,
                            site_url: str = "") -> int:
        """Close the learning loop: map real GA4 page metrics onto the hooks
        and posting times we actually recorded.

        For every content_performance row (a URL we posted), look up the
        page's views/users from GA4 and its affiliate clicks, then:
          1. accumulate them into the matching hook_tests row
             (impressions=views, likes=users, clicks=affiliate clicks) so
             best_hooks() reflects real measured traction, and
          2. fold the engagement into posting_insights under the _actual_
             posted_at day/hour (record_posting_time_at), not "today".

        Slugs are derived exactly like pull_ga4_analytics(): the first path
        segment after the site's base path. Pass the site URL so the base
        path (e.g. https://abvorn.com/reviews) is stripped the same way.

        Returns the number of content rows consumed.
        """
        clicks_by_slug = clicks_by_slug or {}
        if not analytics_by_slug:
            return 0

        from urllib.parse import urlparse

        base_path = urlparse(site_url).path.rstrip("/")

        def _slug(url: str) -> str:
            u = urlparse(url)
            path = u.path
            if base_path and path.startswith(base_path + "/"):
                path = path[len(base_path):]
            parts = [p for p in path.strip("/").split("/") if p]
            return parts[0] if parts else ""

        consumed = 0
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT post_url, niche, platform, hook_used, posted_at "
                "FROM content_performance ORDER BY id"
            ).fetchall()
            for row in rows:
                slug = _slug(row["post_url"] or "")
                ga = analytics_by_slug.get(slug)
                if not ga:
                    continue
                views = int(ga.get("views", 0))
                users = int(ga.get("users", 0))
                clicks = int((clicks_by_slug.get(slug) or {}).get("clicks", 0))
                engagement = float(views + users * 2 + clicks * 10)

                hook_id = self._latest_hook_id(conn, row)
                if hook_id is not None:
                    self.record_engagement(
                        hook_id,
                        impressions=views or 1,
                        likes=users,
                        clicks=clicks,
                    )

                posted_at = row["posted_at"]
                try:
                    if not posted_at:
                        when = datetime.now()
                    else:
                        when = datetime.fromisoformat(posted_at.strip().replace(" ", "T"))
                except ValueError:
                    when = datetime.now()
                self._record_posting_time(conn, row["niche"], row["platform"],
                                          when, engagement)
                consumed += 1
        return consumed

    def _latest_hook_id(self, conn, perf_row) -> int | None:
        """The most recent hook_tests row that matches a content_performance row."""
        hook = perf_row["hook_used"]
        if not hook:
            return None
        found = conn.execute("""
            SELECT id FROM hook_tests
            WHERE hook_text = ? AND niche = ? AND platform = ?
            ORDER BY id DESC LIMIT 1
        """, (hook, perf_row["niche"], perf_row["platform"])).fetchone()
        return found["id"] if found else None

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
