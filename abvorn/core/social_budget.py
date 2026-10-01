"""social_budget.py - hard per-platform daily cap on live social posts.

The Ambassador's promote path fires on every ``content.published`` bus event, and
the content loop emits those far faster than intended: 19 LinkedIn posts in two
hours on 2026-10-01, every one carrying the same "Just published our tv guide!"
headline. The cadence guards in ``daemon.py`` do not govern that path -
``_domination_loop`` (4h) and ``_full_cycle_loop`` (12h) belong to the daemon,
while the Ambassador posts whenever its agent loop happens to notice an event -
so nothing downstream capped it.

This module is the last gate before a request leaves for Composio. It counts
posts per platform per UTC day and refuses the overflow. Because the check sits
in the publisher rather than in any one caller, no path can bypass it: bus
signals, the Ambassador, the domination orchestrator and the full-cycle path all
pass through here.

Control (highest priority first):
  - env var  ``ABVORN_SOCIAL_DAILY_LIMIT=2``   (0 disables the cap entirely)
  - marker   ``data/social_daily_limit.txt``   (one integer)
  - default  1 post per platform per day

Counters persist to ``~/.abvorn/social_budget.json`` so a daemon restart does not
hand the day back a fresh allowance. Local date is UTC so the rollover is the
same everywhere and a redeploy cannot shift the boundary.

A budget slot is only consumed by a post that actually goes live. Staged drafts,
exports and skipped posts are free, otherwise turning the copy gate off for a
review would silently burn the day's allowance.
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("abvorn.social_budget")

_MARKER_FILE = "data/social_daily_limit.txt"
_DEFAULT_LIMIT = 1

# One lock for the whole process. The check-then-consume in check_and_consume()
# has to be atomic or two concurrent agent loops can both read the last slot and
# both post it.
_lock = threading.Lock()


def _state_file() -> Path:
    # Env override exists so the test suite (and anyone dry-running a publish
    # path by hand) never reads or spends the real daily allowance.
    override = os.environ.get("ABVORN_SOCIAL_BUDGET_FILE", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".abvorn" / "social_budget.json"


def daily_limit() -> int | None:
    """Posts allowed per platform per day. None means unlimited.

    Follows the same override ladder as ``social_gate`` so operators tune this
    the way they already tune the master switch.
    """
    raw = os.environ.get("ABVORN_SOCIAL_DAILY_LIMIT", "").strip()
    if raw == "":
        try:
            raw = Path(_MARKER_FILE).read_text(encoding="utf-8").strip()
        except OSError:
            raw = ""
    if raw == "":
        return _DEFAULT_LIMIT
    try:
        limit = int(raw)
    except ValueError:
        logger.warning(f"social budget: ignoring unparseable limit {raw!r}")
        return _DEFAULT_LIMIT
    if limit <= 0:
        return None
    return limit


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _load() -> dict:
    path = _state_file()
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        # A corrupt counter file must not become a permanent publishing freeze.
        logger.warning("social budget: unreadable state file, starting fresh")
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _save(data: dict) -> None:
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    # Replace rather than truncate so a crash mid-write cannot leave a partial
    # file that reads as "no posts made today".
    os.replace(tmp, path)


def used_today(platform: str) -> int:
    """Posts already made to ``platform`` today. Read-only; safe to call freely."""
    limit_free = daily_limit() is None
    if limit_free:
        return 0
    with _lock:
        data = _load()
    if data.get("date") != _today():
        return 0
    try:
        return int(data.get("counts", {}).get(platform, 0))
    except (TypeError, ValueError):
        return 0


def budget_remaining(platform: str) -> int | None:
    """Posts left for ``platform`` today. None means unlimited."""
    limit = daily_limit()
    if limit is None:
        return None
    return max(0, limit - used_today(platform))


def check_and_consume(platform: str) -> tuple[bool, str]:
    """Atomically take one post slot for ``platform``.

    Returns ``(allowed, reason)``. When allowed is True a slot has already been
    consumed, so the caller must post or call ``refund`` to give it back.
    """
    limit = daily_limit()
    if limit is None:
        return True, "unlimited"
    today = _today()
    with _lock:
        data = _load()
        if data.get("date") != today:
            data = {"date": today, "counts": {}}
        counts = data.setdefault("counts", {})
        try:
            used = int(counts.get(platform, 0))
        except (TypeError, ValueError):
            used = 0
        if used >= limit:
            return False, f"{platform} already at {used}/{limit} posts today"
        counts[platform] = used + 1
        try:
            _save(data)
        except OSError as e:
            # Fail open on our own IO trouble, matching copyguard: never let a
            # counter write become an outage. The count is advisory here.
            logger.warning(f"social budget: could not persist counter: {e}")
        return True, f"{platform} {used + 1}/{limit} today"


def refund(platform: str) -> None:
    """Give back a slot taken by check_and_consume when the post did not go out."""
    with _lock:
        data = _load()
        if data.get("date") != _today():
            return
        counts = data.get("counts", {})
        try:
            used = int(counts.get(platform, 0))
        except (TypeError, ValueError):
            return
        if used > 0:
            counts[platform] = used - 1
        try:
            _save(data)
        except OSError as e:
            logger.warning(f"social budget: could not persist refund: {e}")


def status() -> dict:
    """Today's usage, for logging and /status style reporting."""
    limit = daily_limit()
    with _lock:
        data = _load()
    today = _today()
    if data.get("date") != today:
        return {"date": today, "limit": limit, "used": {}}
    counts = data.get("counts", {})
    used = {}
    for platform, count in counts.items():
        try:
            used[platform] = int(count)
        except (TypeError, ValueError):
            continue
    return {"date": today, "limit": limit, "used": used}