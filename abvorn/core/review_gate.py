"""review_gate.py — Human-in-the-loop gate for content deploys.

The automated QualityGate (abvorn.gate) scores content but never routes it past
a human. This gate adds the missing sanity-checker: while it is ON, every page
write through write_checked() is staged under data/review_queue/ instead of
landing in docs/. A human reviews the staged pages and either approves them
(moving them into place) or rejects them.

Control methods (any of these ENABLES the gate):
  - env var  ABVORN_CONTENT_REVIEW=1
  - state meta  content_review_enabled  = true  (persisted in state.db)
  - file      data/content_review.enabled  (marker file)

Default: DISABLED. New checkouts publish directly, exactly as before.
"""

import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger("abvorn.review_gate")

_MARKER_FILE = "data/content_review.enabled"
_QUEUE_DIR = Path("data/review_queue")


def is_content_review_enabled(state=None) -> bool:
    """Return True when generated content must be reviewed before deploy."""
    # 1. Env var override (highest priority).
    if os.environ.get("ABVORN_CONTENT_REVIEW", "").strip() in ("1", "true", "True", "yes"):
        return True
    # 2. Marker file in the repo.
    if Path(_MARKER_FILE).exists():
        return True
    # 3. Persisted state meta (set via set_meta('content_review_enabled', True)).
    if state is not None:
        try:
            if state.get_meta("content_review_enabled", False):
                return True
        except Exception:
            pass
    return False


def require_content_review(state=None) -> bool:
    """Convenience wrapper for callers: True when content must be reviewed."""
    ok = is_content_review_enabled(state)
    if ok:
        logger.info("CONTENT REVIEW GATE ON — staging pages for human review")
    return ok


def _queue_target(path: Path) -> Path:
    """Map a docs/... path to its staging location under data/review_queue/."""
    path = Path(path)
    parts = path.parts
    # Strip the leading docs/ (or data/review_queue/) if present.
    if parts and parts[0] == "docs":
        parts = parts[1:]
    elif parts and parts[0] == "data" and len(parts) > 1 and parts[1] == "review_queue":
        parts = parts[2:]
    return _QUEUE_DIR.joinpath(*parts) if parts else _QUEUE_DIR


def write_gated(path: Path, text: str, state=None) -> Path:
    """Write a page through the review gate.

    Returns the path that was actually written. With the gate OFF this is the
    requested path (normal publish). With the gate ON the page is staged under
    data/review_queue/ and the staged path is returned.
    """
    path = Path(path)
    if not is_content_review_enabled(state):
        path.write_text(text, encoding="utf-8")
        return path
    staged = _queue_target(path)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text(text, encoding="utf-8")
    logger.info(f"CONTENT REVIEW: staged {path} -> {staged}")
    return staged


def list_staged() -> list:
    """List staged pages awaiting review (paths relative to data/review_queue/)."""
    if not _QUEUE_DIR.exists():
        return []
    return sorted(
        str(p.relative_to(_QUEUE_DIR))
        for p in _QUEUE_DIR.rglob("*")
        if p.is_file()
    )


def approve_staged(state=None) -> list:
    """Promote every staged page into its real docs/ location.

    Returns the list of promoted paths. Only pages staged while the gate was ON
    are moved; a page that never reached the queue is left untouched.
    """
    if not _QUEUE_DIR.exists():
        return []
    promoted = []
    for staged in sorted(_QUEUE_DIR.rglob("*")):
        if not staged.is_file():
            continue
        rel = staged.relative_to(_QUEUE_DIR)
        target = Path("docs") / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged), str(target))
        promoted.append(str(target))
        logger.info(f"CONTENT REVIEW: approved {staged} -> {target}")
    return promoted


def reject_staged() -> list:
    """Delete every staged page without publishing it."""
    if not _QUEUE_DIR.exists():
        return []
    removed = []
    for staged in sorted(_QUEUE_DIR.rglob("*")):
        if staged.is_file():
            staged.unlink()
            removed.append(str(staged))
    return removed


def review_status(state=None) -> dict:
    """Compact status dict for dashboards and Telegram."""
    staged = list_staged()
    return {
        "gate_on": is_content_review_enabled(state),
        "staged_count": len(staged),
        "staged": staged[:20],
    }