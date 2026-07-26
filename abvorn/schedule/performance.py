"""Post performance tracker — records publish times + engagement, enables optimization."""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("abvorn.schedule.performance")


class PostPerformanceTracker:
    """Tracks when posts are published and what engagement they get.

    Over time, this data reveals the true optimal posting times per platform.
    """

    def __init__(self, state=None):
        self._state = state
        self._records: list[dict] = []
        self._min_records_for_analysis = 10

    def record_post(self, platform: str, niche: str, posted_at: str = None,
                    engagement: float = 0.0, metric: str = "unknown") -> dict:
        """Record a post publish event. Returns the record."""
        record = {
            "platform": platform,
            "niche": niche,
            "posted_at": posted_at or datetime.now(timezone.utc).isoformat(),
            "day_of_week": datetime.now(timezone.utc).strftime("%A"),
            "hour_utc": datetime.now(timezone.utc).hour,
            "engagement": engagement,
            "metric": metric,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._records.append(record)
        logger.debug(f"Recorded post: {platform} at {record['hour_utc']}:00 UTC on {record['day_of_week']}")
        return record

    def update_engagement(self, platform: str, posted_at: str, engagement: float):
        """Update engagement for a previously recorded post."""
        for r in self._records:
            if r["platform"] == platform and r["posted_at"] == posted_at:
                r["engagement"] = engagement
                logger.debug(f"Updated engagement for {platform} post: {engagement}")
                return True
        return False

    def get_records(self, platform: str = None, min_engagement: float = 0) -> list[dict]:
        """Get filtered records."""
        records = self._records
        if platform:
            records = [r for r in records if r["platform"] == platform]
        if min_engagement > 0:
            records = [r for r in records if r["engagement"] >= min_engagement]
        return list(records)

    def analyze_by_hour(self, platform: str) -> dict:
        """Analyze which hours perform best for a platform.

        Returns {hour: {"avg_engagement": float, "count": int, "rank": int}}
        """
        records = [r for r in self._records
                   if r["platform"] == platform and r["engagement"] > 0]
        if len(records) < self._min_records_for_analysis:
            return {"status": "insufficient_data", "records": len(records),
                    "needed": self._min_records_for_analysis}

        by_hour: dict[int, list[float]] = {}
        for r in records:
            h = r["hour_utc"]
            if h not in by_hour:
                by_hour[h] = []
            by_hour[h].append(r["engagement"])

        results = {}
        for hour, engagements in by_hour.items():
            results[hour] = {
                "avg_engagement": round(sum(engagements) / len(engagements), 4),
                "count": len(engagements),
            }

        sorted_hours = sorted(results.items(), key=lambda x: x[1]["avg_engagement"], reverse=True)
        for rank, (hour, data) in enumerate(sorted_hours, 1):
            results[hour]["rank"] = rank

        return {"status": "analyzed", "platform": platform,
                "records": len(records), "by_hour": results,
                "top_hours": [h for h, _ in sorted_hours[:5]]}

    def analyze_by_day(self, platform: str) -> dict:
        """Analyze which days perform best for a platform.

        Returns {day: {"avg_engagement": float, "count": int, "rank": int}}
        """
        records = [r for r in self._records
                   if r["platform"] == platform and r["engagement"] > 0]
        if len(records) < self._min_records_for_analysis:
            return {"status": "insufficient_data", "records": len(records),
                    "needed": self._min_records_for_analysis}

        by_day: dict[str, list[float]] = {}
        for r in records:
            d = r["day_of_week"]
            if d not in by_day:
                by_day[d] = []
            by_day[d].append(r["engagement"])

        results = {}
        for day, engagements in by_day.items():
            results[day] = {
                "avg_engagement": round(sum(engagements) / len(engagements), 4),
                "count": len(engagements),
            }

        sorted_days = sorted(results.items(), key=lambda x: x[1]["avg_engagement"], reverse=True)
        for rank, (day, data) in enumerate(sorted_days, 1):
            results[day]["rank"] = rank

        return {"status": "analyzed", "platform": platform,
                "records": len(records), "by_day": results,
                "top_days": [d for d, _ in sorted_days[:3]]}

    def get_optimization_suggestions(self, platform: str) -> dict:
        """Get suggested schedule changes based on real performance data."""
        hour_analysis = self.analyze_by_hour(platform)
        day_analysis = self.analyze_by_day(platform)

        suggestions = {"status": "insufficient_data", "platform": platform}

        if hour_analysis.get("status") == "analyzed":
            suggestions["suggested_hours"] = hour_analysis.get("top_hours", [])
            suggestions["status"] = "partial"

        if day_analysis.get("status") == "analyzed":
            suggestions["suggested_days"] = day_analysis.get("top_days", [])
            suggestions["status"] = "ready" if suggestions.get("suggested_hours") else "partial"

        suggestions["hour_analysis"] = hour_analysis
        suggestions["day_analysis"] = day_analysis
        return suggestions

    def record_count(self) -> int:
        return len(self._records)

    def set_min_records(self, n: int):
        self._min_records_for_analysis = n