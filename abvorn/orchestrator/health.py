"""Health monitoring — tracks cycle success, failures, and system health."""

import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("abvorn.orchestrator.health")


class HealthMonitor:
    """Tracks system health, cycle success rates, and provides status checks."""

    def __init__(self, state_db: str = None):
        from ..core.state import AbvornState
        self.state_path = Path(state_db) if state_db else Path.home() / ".abvorn" / "state.db"
        self.state = AbvornState(self.state_path)

    def check(self) -> dict:
        """Run a health check on all subsystems."""
        issues = []
        try:
            niches = self.state.get_all_niches()
            if niches is None:
                issues.append("state_unreachable")
        except Exception as e:
            issues.append(f"state_error: {e}")
        return {"healthy": len(issues) == 0, "issues": issues, "checked_at": datetime.now().isoformat()}

    def log_cycle(self, niche: str, success: bool, duration_s: float):
        """Log a completed cycle for tracking."""
        key = f"cycle_{niche}"
        existing = self.state.get_meta(key, {"total": 0, "successes": 0, "failures": 0, "total_duration": 0})
        existing["total"] += 1
        existing["total_duration"] += duration_s
        if success:
            existing["successes"] += 1
        else:
            existing["failures"] += 1
        self.state.set_meta(key, existing)
        agg = self.state.get_meta("_cycle_agg", {"total": 0, "successes": 0, "failures": 0, "total_duration": 0})
        agg["total"] += 1
        agg["total_duration"] += duration_s
        if success:
            agg["successes"] += 1
        else:
            agg["failures"] += 1
        self.state.set_meta("_cycle_agg", agg)
        logger.info(f"Cycle for '{niche}': {'SUCCESS' if success else 'FAIL'} ({duration_s:.0f}s)")

    def get_stats(self) -> dict:
        """Get aggregate cycle statistics."""
        agg = self.state.get_meta("_cycle_agg", {"total": 0, "successes": 0, "failures": 0})
        return {
            "total_cycles": agg.get("total", 0),
            "successes": agg.get("successes", 0),
            "failures": agg.get("failures", 0),
            "success_rate": round(agg.get("successes", 0) / max(agg.get("total", 1), 1), 2),
            "avg_duration_s": 0,
        }