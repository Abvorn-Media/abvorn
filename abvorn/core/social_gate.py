"""social_gate.py — Master switch for direct social publishing.

While the gate is OFF, every social publisher exports a draft file instead of
calling Composio. Flip it ON only when you're ready to post for real.

Control methods (any of these enables publishing):
  - env var  ABVORN_SOCIAL_PUBLISH=1
  - state meta  social_publish_enabled  = true  (persisted in state.db)
  - file      data/social_publish.enabled  (marker file)

Default: DISABLED. New checkouts are safe — nothing posts until you opt in.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger("abvorn.social_gate")

_MARKER_FILE = "data/social_publish.enabled"


def is_social_publishing_enabled(state=None) -> bool:
    """Return True only when publishing has been explicitly enabled."""
    # 1. Env var override (highest priority).
    if os.environ.get("ABVORN_SOCIAL_PUBLISH", "").strip() in ("1", "true", "True", "yes"):
        return True
    # 2. Marker file in the repo.
    marker = Path(_MARKER_FILE)
    if marker.exists():
        return True
    # 3. Persisted state meta (set via set_meta('social_publish_enabled', True)).
    if state is not None:
        try:
            if state.get_meta("social_publish_enabled", False):
                return True
        except Exception:
            pass
    return False


def require_social_publishing(state=None) -> bool:
    """Convenience wrapper for callers: returns True if posting is allowed."""
    ok = is_social_publishing_enabled(state)
    if not ok:
        logger.info("SOCIAL PUBLISH GATE OFF — exporting drafts instead of posting")
    return ok
