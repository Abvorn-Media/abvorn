"""Schedule optimizer — uses real performance data to adjust platform schedules."""

import logging
from datetime import timezone
from ..platform import registry
from .performance import PostPerformanceTracker

logger = logging.getLogger("abvorn.schedule.optimizer")

_MIN_RECORDS = 15


class ScheduleOptimizer:
    """Analyzes post performance data and adjusts platform schedules.

    Cycle:
    1. Track all posts with platform + timestamp + engagement
    2. After 15+ records per platform, analyze which hours/days perform best
    3. Suggest updated schedule_profile for the registry
    4. Apply when confidence is high (consistent top performers)
    """

    def __init__(self, tracker: PostPerformanceTracker):
        self.tracker = tracker
        self._auto_apply = False

    def enable_auto_apply(self):
        """Enable automatic application of optimizations."""
        self._auto_apply = True

    def disable_auto_apply(self):
        self._auto_apply = False

    def optimize_platform(self, platform: str) -> dict:
        """Analyze performance data for a platform and return optimization result."""
        suggestions = self.tracker.get_optimization_suggestions(platform)
        changes = {}

        if suggestions.get("status") in ("partial", "ready"):
            current_profile = registry.schedule_profile(platform)
            if not current_profile:
                return {"platform": platform, "status": "no_profile"}

            if "suggested_hours" in suggestions and suggestions["suggested_hours"]:
                new_hours = suggestions["suggested_hours"]
                old_hours = current_profile.get("best_hours", [])
                if set(new_hours) != set(old_hours):
                    changes["best_hours"] = {"from": old_hours, "to": new_hours}
                    logger.info(f"{platform}: hours optimized {old_hours} → {new_hours}")

            if "suggested_days" in suggestions and suggestions["suggested_days"]:
                new_days = suggestions["suggested_days"]
                old_days = current_profile.get("best_days", [])
                if set(new_days) != set(old_days):
                    changes["best_days"] = {"from": old_days, "to": new_days}
                    logger.info(f"{platform}: days optimized {old_days} → {new_days}")

        result = {
            "platform": platform,
            "status": suggestions.get("status", "insufficient_data"),
            "records_analyzed": suggestions.get("hour_analysis", {}).get("records", 0),
            "changes_proposed": changes,
        }

        if self._auto_apply and changes:
            result["applied"] = self._apply_changes(platform, changes)
        else:
            result["applied"] = False

        return result

    def optimize_all(self) -> list[dict]:
        """Run optimization for all registered platforms."""
        results = []
        for platform in registry.list():
            try:
                result = self.optimize_platform(platform)
                results.append(result)
            except Exception as e:
                logger.error(f"Optimization failed for {platform}: {e}")
                results.append({"platform": platform, "status": "error", "error": str(e)})
        return results

    def get_optimization_report(self) -> dict:
        """Generate a full optimization report across all platforms."""
        total_records = self.tracker.record_count()
        platforms_ready = 0
        platforms_pending = 0
        changes_made = 0

        details = {}
        for platform in registry.list():
            suggestions = self.tracker.get_optimization_suggestions(platform)
            status = suggestions.get("status", "insufficient_data")
            if status == "ready":
                platforms_ready += 1
            elif status == "partial":
                platforms_pending += 1
            record_count = suggestions.get("hour_analysis", {}).get("records", 0)
            details[platform] = {"status": status, "records": record_count}

        return {
            "total_records": total_records,
            "platforms_ready_for_optimization": platforms_ready,
            "platforms_with_partial_data": platforms_pending,
            "platforms_total": len(registry.list()),
            "min_records_needed": _MIN_RECORDS,
            "details": details,
        }

    def _apply_changes(self, platform: str, changes: dict) -> bool:
        """Apply schedule changes to the registry."""
        try:
            config = registry.get(platform)
            profile = config.schedule_profile or {}
            for key, change in changes.items():
                profile[key] = change["to"]
            logger.info(f"{platform}: schedule profile updated via optimization")
            return True
        except Exception as e:
            logger.error(f"Failed to apply changes to {platform}: {e}")
            return False