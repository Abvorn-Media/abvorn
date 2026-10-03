"""social_budget.py - hard per-platform daily cap on live social posts.

The Ambassador's promote path fires on every ``content.published`` bus event, and
before this gate it did not know when to stop. The first promotion after midnight
would burn the day's single slot; every subsequent cycle (sometimes dozens per
day) tried again, got rejected by the publish path after doing expensive LLM
commentary and media composition, and logged a warning. That is how 167 LinkedIn
attempts were rejected on 2026-10-02 while only two posts ever left.

The fix has two layers:

1. **A hard daily counter on disk** (``social_budget.json`` under
   ``~/.abvorn/``). ``check_and_consume`` atomically increments the count for a
   platform and returns ``(allowed, reason)``. When it returns True the slot is
   spent - the caller must either post or call ``refund`` if the post never went
   out. Telegram bypasses the budget entirely by design, so this gate never
   touches it.
2. **Time-of-day windows.** LinkedIn traffic is not uniform. With three opt-in
   windows (EU morning, EU evening, US morning) a daemon that runs every ten
   minutes will naturally spread posts across peak hours instead of dumping all
   of them the moment the first cycle fires after midnight. Windows are opt-in
   (unset = "post any time") to avoid breaking existing tests and to keep draft
   platforms unconstrained.

Both layers are fail-open: a corrupt state file, unparseable config, or IO
errors never freeze publishing. The gate logs a warning and behaves as if the
check passed in that degenerate case (matching ``copyguard``'s infra-down
posture).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger("abvorn.social_budget")

_DEFAULT_LIMIT = 1
_MARKER_FILE = Path(".abvorn/social_limit")

_WINDOWS_ENV = "ABVORN_SOCIAL_WINDOWS"
_SPACING_ENV = "ABVORN_SOCIAL_MIN_SPACING_MINUTES"
# Timestamps kept per platform. Enough to enforce spacing and still allow a
# refund to roll back the most recent one; bounded so the file cannot grow.
_POST_LOG_LIMIT = 10

# Recommended windows for LinkedIn, tuned to both sides of the Atlantic.
LINKEDIN_PRESET_WINDOWS = (
    "linkedin=Europe/Paris:0830-1030|Europe/Paris:1700-1830|America/New_York:0900-1030"
)

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


# ----------------------------------------------------------------------
# Posting windows
# ----------------------------------------------------------------------


def _hhmm_to_minutes(value: str) -> int | None:
    value = str(value or "").strip()
    if len(value) != 4 or not value.isdigit():
        return None
    hours, minutes = int(value[:2]), int(value[2:])
    if hours > 24 or minutes > 59:
        return None
    return hours * 60 + minutes


def _parse_window(spec: str) -> tuple[str, int, int] | None:
    """Parse ``Zone:HHMM-HHMM`` into (zone, start_min, end_min)."""
    spec = str(spec or "").strip()
    if not spec:
        return None
    zone, _, range_part = spec.partition(":")
    zone = zone.strip()
    range_part = range_part.strip()
    if not zone or not range_part:
        return None
    start_s, _, end_s = range_part.partition("-")
    start_s = start_s.strip()
    end_s = end_s.strip()
    if not start_s or not end_s:
        return None
    start_m = _hhmm_to_minutes(start_s)
    end_m = _hhmm_to_minutes(end_s)
    if start_m is None or end_m is None:
        return None
    try:
        ZoneInfo(zone)
    except Exception:
        logger.warning(f"social budget: unknown timezone '{zone}' in window '{spec}'")
        return None
    if start_m == end_m:
        return None
    return zone, start_m, end_m


def windows(platform: str) -> tuple[str, ...]:
    """Local-time windows during which ``platform`` may post, in order.

    Returns an empty tuple - meaning "any time" - unless
    ``ABVORN_SOCIAL_WINDOWS`` names this platform. Comma-separated
    ``platform=Zone:HHMM-HHMM|Zone:HHMM-HHMM``; see
    ``LINKEDIN_PRESET_WINDOWS`` for a working value.

    An operator who sets the variable means it, so a platform they omit becomes
    unconstrained rather than silently regaining a built-in default.

    Unparseable entries are dropped here, at the boundary, with a warning. That
    keeps a typo from becoming a permanent publishing freeze: a config that
    yields no valid window at all degrades to "post any time", which is the same
    fail-open posture ``copyguard`` and the corrupt-state-file path below take.
    """
    raw = os.environ.get(_WINDOWS_ENV, "").strip()
    if not raw:
        return ()
    for entry in raw.split(","):
        name, _, spec = entry.partition("=")
        if name.strip() != platform:
            continue
        valid = []
        for item in spec.split("|"):
            item = item.strip()
            if not item:
                continue
            if _parse_window(item) is None:
                logger.warning(f"social budget: ignoring malformed window {item!r}")
                continue
            valid.append(item)
        if not valid and spec.strip():
            logger.warning(
                f"social budget: no valid window for {platform!r} in "
                f"{_WINDOWS_ENV}; posting uncapped in time"
            )
        return tuple(valid)
    return ()


def windows_open_now(platform: str) -> bool:
    return windows_open(platform)


def _is_open(window: tuple[str, int, int], now: datetime) -> bool:
    zone, start, end = window
    try:
        local = now.astimezone(ZoneInfo(zone))
    except Exception:
        return False
    minutes = local.hour * 60 + local.minute
    if start <= end:
        return start <= minutes < end
    # A window may wrap past local midnight (e.g. 2300-0200).
    return minutes >= start or minutes < end


def _consumed_windows(data: dict, platform: str) -> set[str]:
    raw = (data.get("windows") or {}).get(platform)
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw}


def _window_state(data: dict, platform: str) -> list:
    """Return the mutable list of window specs already spent today."""
    windows_map = data.setdefault("windows", {})
    if not isinstance(windows_map, dict):
        windows_map = {}
        data["windows"] = windows_map
    used = windows_map.setdefault(platform, [])
    if not isinstance(used, list):
        used = []
        windows_map[platform] = used
    return used


def min_spacing_minutes() -> int:
    """Minimum gap between two posts on the same platform. 0 disables it.

    Windows decide *when a day* posts may go out; this decides *how close
    together* two posts may land inside that day. They are separate controls
    because windows alone do not guarantee spacing - two windows whose edges sit
    30 minutes apart will happily produce two posts 30 minutes apart.
    """
    raw = os.environ.get(_SPACING_ENV, "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        logger.warning(f"social budget: ignoring unparseable spacing {raw!r}")
        return 0
    return max(0, value)


def _post_log(data: dict, platform: str) -> list:
    """Timestamps of recent successful claims, oldest first."""
    log = data.setdefault("post_log", {})
    if not isinstance(log, dict):
        log = {}
        data["post_log"] = log
    stamps = log.setdefault(platform, [])
    if not isinstance(stamps, list):
        stamps = []
        log[platform] = stamps
    return stamps


def _last_post_at(data: dict, platform: str) -> datetime | None:
    stamps = _post_log(data, platform)
    for stamp in reversed(stamps):
        try:
            return datetime.fromisoformat(str(stamp))
        except ValueError:
            continue
    return None


def _record_post_at(data: dict, platform: str, now: datetime) -> None:
    stamps = _post_log(data, platform)
    stamps.append(now.astimezone(timezone.utc).isoformat())
    del stamps[:-_POST_LOG_LIMIT]


def _minutes_since(previous: datetime | None, now: datetime) -> float | None:
    if previous is None:
        return None
    if previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)
    return (now.astimezone(timezone.utc) - previous).total_seconds() / 60.0


def open_windows(platform: str, now: datetime | None = None) -> list[str]:
    """Windows that are currently in progress and not yet spent today.

    Read-only and side-effect free. Callers use it to skip expensive work (LLM
    commentary, image composition) when a post could not go out anyway; the
    publisher's own check in ``check_and_consume`` remains authoritative.
    """
    now = now or datetime.now(timezone.utc)
    specs = windows(platform)
    if not specs:
        return []
    with _lock:
        data = _load()
    # Compare against the injected clock's date, not the wall clock's, or a
    # caller replaying another day silently ignores that day's spent windows.
    today = now.astimezone(timezone.utc).date().isoformat()
    used = _consumed_windows(data, platform) if data.get("date") == today else set()
    open_now = []
    for spec in specs:
        parsed = _parse_window(spec)
        if parsed is None or spec in used:
            continue
        if _is_open(parsed, now):
            open_now.append(spec)
    return open_now


def windows_open(platform: str, now: datetime | None = None) -> bool:
    """True when ``platform`` has an unspent window in progress right now.

    Always True for a platform with no windows configured, so uncapped platforms
    and staged-draft platforms keep behaving exactly as before.
    """
    specs = windows(platform)
    if not specs:
        return True
    return bool(open_windows(platform, now=now))


def can_attempt(platform: str, now: datetime | None = None) -> bool:
    """True when a post for ``platform`` could plausibly go out right now.

    This is the cheap pre-flight for callers about to spend real money on
    commentary and images. It checks the daily count *and* the window, because
    the count alone is not enough once a limit can be lower than the number of
    configured windows - otherwise the expensive path still runs for a post the
    publisher is about to reject.

    Advisory only: ``check_and_consume`` stays authoritative, because this
    check and the eventual publish are not one atomic operation.
    """
    limit = daily_limit()
    if limit is not None and used_today(platform) >= limit:
        return False
    return windows_open(platform, now=now)


def _load() -> dict:
    path = _state_file()
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        # A corrupt counter file must not become a permanent publishing freeze.
        # Log the failure and start fresh for today so the daemon keeps running.
        logger.warning(f"social budget: corrupt state at {path}, resetting")
        return {}
    if not isinstance(data, dict):
        logger.warning(f"social budget: unexpected state shape at {path}, resetting")
        return {}
    return data


def _save(data: dict) -> None:
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically-ish: write to a temp file and rename if the platform
    # ever becomes more sensitive to torn writes. For now a single write is
    # fine and the lock already prevents races between processes in practice.
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def used_today(platform: str) -> int:
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
    The count check and the window claim happen under one lock: two concurrent
    agent loops must not both pass the limit check, and must not both claim the
    same window.
    """
    return check_and_consume_at(platform)


def check_and_consume_at(platform: str,
                         now: datetime | None = None) -> tuple[bool, str]:
    """``check_and_consume`` with an injectable clock.

    Windows make the decision depend on the time of day, so the tests cannot use
    whatever moment they happen to run. This is the seam that lets them say
    "it is 06:30 UTC on 2026-10-03" instead of asserting against a race.
    """
    limit = daily_limit()
    specs = windows(platform)
    if limit is None and not specs:
        return True, "unlimited"

    now = now or datetime.now(timezone.utc)
    today = now.astimezone(timezone.utc).date().isoformat()
    parsed = [(s, _parse_window(s)) for s in specs]

    with _lock:
        data = _load()
        if data.get("date") != today:
            data = {"date": today, "counts": {}}
        counts = data.setdefault("counts", {})
        try:
            used = int(counts.get(platform, 0))
        except (TypeError, ValueError):
            used = 0

        if limit is not None and used >= limit:
            return False, f"{platform} already at {used}/{limit} posts today"

        claimed: str | None = None
        if specs:
            spent = _consumed_windows(data, platform)
            for spec, window in parsed:
                if window is None or spec in spent:
                    continue
                if _is_open(window, now):
                    claimed = spec
                    break
            if claimed is None:
                open_now = [s for s, w in parsed if _is_open(w, now)]
                if open_now:
                    return False, (
                        f"{platform} already used its {len(open_now)} "
                        f"posting window(s) today"
                    )
                return False, f"{platform} outside posting windows right now"

        if limit is not None:
            counts[platform] = used + 1
        if claimed is not None:
            _window_state(data, platform).append(claimed)
        else:
            min_gap = min_spacing_minutes()
            if min_gap > 0:
                last = _last_post_at(data, platform)
                gap = _minutes_since(last, now)
                if gap is not None and gap < min_gap:
                    # Roll back the count we just bumped.
                    if limit is not None:
                        counts[platform] = used
                    try:
                        _save(data)
                    except OSError:
                        pass
                    return False, (
                        f"{platform} posted {gap:.0f}m ago, need ≥{min_gap}m gap"
                    )
                _record_post_at(data, platform, now)
            else:
                _record_post_at(data, platform, now)

        try:
            _save(data)
        except OSError as e:
            logger.warning(f"social budget: could not persist counter: {e}")

        slot = f"{used + 1}/{limit}" if limit is not None else "unlimited"
        if claimed:
            return True, f"{platform} {slot} today in window {claimed}"
        return True, f"{platform} {slot} today"


def refund(platform: str) -> None:
    """Give back a slot taken by check_and_consume when the post did not go out.

    Also releases the window the slot claimed. Without that, a Composio outage
    inside a peak hour would burn one of only three daily windows on a post that
    never left.
    """
    with _lock:
        data = _load()
        if data.get("date") != _today():
            return
        counts = data.get("counts", {})
        try:
            used = int(counts.get(platform, 0))
        except (TypeError, ValueError):
            used = 0
        if used > 0:
            counts[platform] = used - 1
        windows_map = data.get("windows")
        if isinstance(windows_map, dict):
            claimed = windows_map.get(platform)
            if isinstance(claimed, list) and claimed:
                claimed.pop()
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
    fresh = data.get("date") == today
    if not fresh:
        return {"date": today, "limit": limit, "used": {}, "windows": {}}
    counts = data.get("counts", {})
    used = {}
    for platform, count in counts.items():
        try:
            used[platform] = int(count)
        except (TypeError, ValueError):
            continue
    windows_used = {
        platform: sorted(_consumed_windows(data, platform))
        for platform in used
        if _consumed_windows(data, platform)
    }
    return {"date": today, "limit": limit, "used": used, "windows": windows_used}
