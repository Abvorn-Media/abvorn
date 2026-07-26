"""Platform-specific schedule planning — uses registry for platform definitions."""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("abvorn.schedule.planner")

from ..platform import registry

WEEKDAY_INDEX = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2,
    "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6,
}

_DEFAULT_PEAKS = {
    "best_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "best_hours": list(range(9, 17)),
    "min_gap_hours": 12,
    "max_per_day": 1,
    "cadence": "daily",
}


def _get_peaks(platform: str) -> dict:
    """Get schedule profile for a platform, from registry or default."""
    profile = registry.schedule_profile(platform)
    if profile:
        return profile
    if registry.has(platform):
        return _DEFAULT_PEAKS
    raise ValueError(f"Unknown platform: '{platform}'. Available: {', '.join(registry.list())}")


class PlatformPlanner:
    """Determines optimal posting times per platform."""

    def _peaks(self, platform: str) -> dict:
        return _get_peaks(platform)

    def is_good_time(self, platform: str) -> bool:
        peaks = self._peaks(platform)
        now = datetime.now(timezone.utc)
        if now.strftime("%A") not in peaks["best_days"]:
            return False
        return now.hour in peaks["best_hours"]

    def next_good_time(self, platform: str) -> str:
        peaks = self._peaks(platform)
        now = datetime.now(timezone.utc)
        candidate = now.replace(minute=0, second=0, microsecond=0)
        for _ in range(14):
            day_name = candidate.strftime("%A")
            if day_name in peaks["best_days"] and candidate.hour in peaks["best_hours"]:
                if candidate > now:
                    return candidate.isoformat()
            candidate += timedelta(hours=1)
        return (now + timedelta(days=14)).isoformat()

    def time_until_next(self, platform: str) -> float:
        next_time = datetime.fromisoformat(self.next_good_time(platform))
        return (next_time - datetime.now(timezone.utc)).total_seconds()

    def min_gap_met(self, platform: str, last_post_time: str | None = None) -> bool:
        peaks = self._peaks(platform)
        if last_post_time is None:
            return True
        last = datetime.fromisoformat(last_post_time)
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed >= peaks["min_gap_hours"] * 3600