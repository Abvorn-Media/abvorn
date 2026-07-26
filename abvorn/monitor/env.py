"""Environment — safe dev/prod/staging modes with dry-run support."""

import os
import logging

logger = logging.getLogger("abvorn.monitor.env")

ENV_KEY = "ABVORN_ENV"
VALID_MODES = {"development", "staging", "production"}


class EnvMode:
    """Controls whether the system actually deploys vs dry-runs."""

    def __init__(self):
        self._mode = os.environ.get(ENV_KEY, "development").lower()
        if self._mode not in VALID_MODES:
            logger.warning(f"Unknown ABVORN_ENV '{self._mode}', falling back to development")
            self._mode = "development"

    @property
    def is_production(self) -> bool:
        return self._mode == "production"

    @property
    def is_staging(self) -> bool:
        return self._mode == "staging"

    @property
    def is_development(self) -> bool:
        return self._mode == "development"

    @property
    def should_deploy(self) -> bool:
        """True if this environment should push to GitHub/social."""
        return self._mode in ("production", "staging")

    @property
    def should_post_social(self) -> bool:
        """True if this environment should post to social media."""
        return self._mode == "production"

    @property
    def label(self) -> str:
        return self._mode.upper()

    def format_status(self) -> str:
        """Return human-readable env status for Telegram."""
        lines = [f"<b>Environment: {self.label}</b>"]
        lines.append(f"  Deploy to GitHub: {'YES' if self.should_deploy else 'NO (dry-run)'}")
        lines.append(f"  Post to social: {'YES' if self.should_post_social else 'NO'}")
        lines.append(f"  Set ABVORN_ENV=production to go live")
        return "\n".join(lines)
