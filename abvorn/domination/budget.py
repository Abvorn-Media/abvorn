"""APIBudget — monthly quota tracker for third-party APIs.

Tracks every external API call (Pexels, Open Web Ninja, Composio)
against configurable monthly limits. Blocks calls when budget exhausted.
"""

import logging, json, time
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger("abvorn.domination.budget")

BUDGET_DIR = Path.home() / ".abvorn" / "budget"
BUDGET_FILE = BUDGET_DIR / "usage.json"

# Default monthly limits (hard caps)
DEFAULT_LIMITS = {
    "pexels": 200,           # free tier: 200 req/hour, but we cap at 200/month to be safe
    "openweb_ninja": 100,    # hard limit from plan
    "composio": 500,         # depends on plan
}

WARN_THRESHOLD = 0.8  # warn at 80% usage


class APIBudget:
    """Tracks API usage against monthly budgets.

    Usage:
        budget = APIBudget()
        if budget.can_call("pexels"):
            result = fetch_from_pexels()
            budget.record_call("pexels")
        else:
            result = fallback_data()
    """

    def __init__(self, limits: dict | None = None):
        BUDGET_DIR.mkdir(parents=True, exist_ok=True)
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        self._usage = self._load()
        self._session_calls = []

    @property
    def _month_key(self) -> str:
        return datetime.now().strftime("%Y-%m")

    def _load(self) -> dict:
        if BUDGET_FILE.exists():
            try:
                return json.loads(BUDGET_FILE.read_text())
            except (json.JSONDecodeError, Exception):
                pass
        return {}

    def _save(self):
        BUDGET_FILE.write_text(json.dumps(self._usage, indent=2))

    def _ensure_month(self, api: str):
        if api not in self._usage:
            self._usage[api] = {}
        if self._month_key not in self._usage[api]:
            self._usage[api][self._month_key] = {
                "calls": 0,
                "last_reset": datetime.now().isoformat(),
            }

    def can_call(self, api: str) -> bool:
        """Check if API has remaining quota for this month."""
        limit = self.limits.get(api)
        if limit is None:
            return True  # no cap configured
        self._ensure_month(api)
        used = self._usage[api][self._month_key]["calls"]
        remaining = limit - used
        if remaining <= 0:
            logger.warning(f"[Budget] {api}: quota exhausted ({used}/{limit}) — blocked")
            return False
        if remaining / limit < (1 - WARN_THRESHOLD):
            logger.warning(f"[Budget] {api}: {used}/{limit} used this month ({(used/limit)*100:.0f}%)")
        return True

    def record_call(self, api: str, count: int = 1):
        """Record one or more API calls."""
        self._ensure_month(api)
        self._usage[api][self._month_key]["calls"] += count
        self._session_calls.append({
            "api": api,
            "count": count,
            "timestamp": datetime.now().isoformat(),
        })
        self._save()

    def used(self, api: str) -> int:
        """Get current month's usage for an API."""
        self._ensure_month(api)
        return self._usage[api][self._month_key]["calls"]

    def remaining(self, api: str) -> int:
        limit = self.limits.get(api)
        if limit is None:
            return -1
        return max(0, limit - self.used(api))

    def percent(self, api: str) -> float:
        limit = self.limits.get(api)
        if limit is None:
            return 0.0
        return round(self.used(api) / limit * 100, 1)

    def summary(self) -> dict:
        month = self._current_month()
        result = {}
        for api in self.limits:
            self._ensure_month(api)
            used = self._usage[api][month]["calls"]
            result[api] = {
                "month": month,
                "used": used,
                "limit": self.limits[api],
                "remaining": max(0, self.limits[api] - used),
                "percent": round(used / self.limits[api] * 100, 1) if self.limits[api] else 0,
                "can_call": used < self.limits[api],
            }
        return result

    def report(self) -> str:
        lines = ["# API Budget Report", ""]
        for api, info in self.summary().items():
            bar_len = 20
            filled = int(info["percent"] / 100 * bar_len)
            bar = "#" * filled + "." * (bar_len - filled)
            status = "OK" if info["can_call"] else "BLOCKED"
            lines.append(f"[{status:>7}] {api:>15}: [{bar}] {info['used']:>3}/{info['limit']:<3} ({info['percent']:>5}%)")
        lines.append("")
        lines.append(f"Session calls: {len(self._session_calls)}")
        return "\n".join(lines)
