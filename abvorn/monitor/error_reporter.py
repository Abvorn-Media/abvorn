"""ErrorReporter — catches, logs, and reports errors across all subsystems."""

import json
import logging
import traceback
import sys
from datetime import datetime, timedelta

logger = logging.getLogger("abvorn.monitor")

STORAGE_KEY = "monitor:errors"
RATE_LIMIT_MINUTES = 60


class ErrorReporter:
    """Central error tracking — stores, deduplicates, and reports via Telegram."""

    def __init__(self, state, notifier=None):
        self._state = state
        self._notifier = notifier

    def record(self, subsystem: str, error: Exception, context: dict = None) -> dict:
        """Record an error, rate-limit by type, notify if first in window."""
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        error_type = type(error).__name__
        error_key = f"{subsystem}:{error_type}"

        entry = {
            "subsystem": subsystem,
            "error_type": error_type,
            "message": str(error)[:500],
            "traceback": tb[-2000:],
            "context": context or {},
            "key": error_key,
            "timestamp": datetime.now().isoformat(),
        }

        errors = self._load_errors()
        errors.append(entry)
        self._save_errors(errors)

        if self._should_notify(errors, error_key):
            self._notify(entry)
            return {"recorded": True, "notified": True}

        return {"recorded": True, "notified": False}

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Return most recent errors."""
        return self._load_errors()[-limit:]

    def get_summary(self) -> dict:
        """Group errors by subsystem + type with counts."""
        errors = self._load_errors()
        counts = {}
        for e in errors:
            key = e.get("key", "unknown")
            counts[key] = counts.get(key, 0) + 1
        return {
            "total": len(errors),
            "unique_types": len(counts),
            "by_key": counts,
            "last_error": errors[-1] if errors else None,
        }

    def format_report(self) -> str:
        """Format error summary for Telegram."""
        summary = self.get_summary()
        lines = [f"<b>Error Report</b>", f"Total errors: {summary['total']}", f"Unique types: {summary['unique_types']}", ""]
        for key, count in sorted(summary["by_key"].items(), key=lambda x: -x[1]):
            lines.append(f"  {key}: {count}x")
        if summary["last_error"]:
            last = summary["last_error"]
            lines.append("")
            lines.append(f"<b>Last:</b> {last['subsystem']} / {last['error_type']}")
            lines.append(f"  {last['message'][:200]}")
        return "\n".join(lines)

    def _load_errors(self) -> list:
        raw = self._state.get_meta(STORAGE_KEY, "[]")
        return json.loads(raw) if isinstance(raw, str) else raw

    def _save_errors(self, errors: list):
        cutoff = datetime.now() - timedelta(days=7)
        errors = [e for e in errors if datetime.fromisoformat(e["timestamp"]) > cutoff]
        self._state.set_meta(STORAGE_KEY, json.dumps(errors[-500:], default=str))

    def _should_notify(self, errors: list, key: str) -> bool:
        recent = [e for e in errors if e.get("key") == key and e.get("timestamp")]
        if len(recent) <= 1:
            return True
        last_time = datetime.fromisoformat(recent[-2]["timestamp"])
        return datetime.now() - last_time > timedelta(minutes=RATE_LIMIT_MINUTES)

    def _notify(self, entry: dict):
        if not self._notifier:
            return
        msg = (
            f"\U0001f6a8 <b>Bug Detected</b>\n"
            f"<b>Subsystem:</b> {entry['subsystem']}\n"
            f"<b>Type:</b> {entry['error_type']}\n"
            f"<b>Message:</b> {entry['message'][:300]}"
        )
        try:
            self._notifier.send(msg)
        except Exception:
            pass


class DaemonGuard:
    """Wraps daemon cycle calls with error recording."""

    def __init__(self, reporter: ErrorReporter):
        self._reporter = reporter

    def guard(self, subsystem: str, fn, *args, context: dict = None, **kwargs):
        """Execute fn, record any exception, re-raise."""
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            self._reporter.record(subsystem, e, context=context)
            raise

    def safe(self, subsystem: str, fn, *args, context: dict = None, default=None, **kwargs):
        """Execute fn, record exception, return default on failure."""
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            self._reporter.record(subsystem, e, context=context)
            return default
