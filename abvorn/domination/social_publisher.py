"""Social Publisher — publishes content to social platforms via Composio
or export-ready file generation when Composio is unavailable."""

import logging, json
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("abvorn.domination.social_publisher")

EXPORT_DIR = Path.home() / ".abvorn" / "exports"

from ..deploy.composio_client import ComposioClient

# Composio v3 tool slugs. Only platforms with a live connected account get a
# direct backend; everything else falls back to export files (TikTok/Pinterest
# by design, Instagram whenever the image-container flow is not wired, and any
# platform without a connected account).
PLATFORM_ACTIONS = {
    "x": {
        "toolkit": "twitter",
        "slug": "TWITTER_CREATION_OF_A_POST",
        "params_fn": lambda script: {"text": _extract_text(script)[:280]},
    },
    "linkedin": {
        "toolkit": "linkedin",
        "slug": "LINKEDIN_CREATE_LINKED_IN_POST",
        "params_fn": lambda script: _linkedin_params(script),
    },
    "instagram": {"slug": None, "toolkit": None, "export_only": True},
    "facebook": {"slug": None, "toolkit": None, "export_only": True},
    "tiktok": {"slug": None, "toolkit": None, "export_only": True},
    "pinterest": {"slug": None, "toolkit": None, "export_only": True},
    "medium": {"slug": None, "toolkit": None, "export_only": True},
}


def _extract_text(script: dict | list | str) -> str:
    if isinstance(script, str):
        return script
    if isinstance(script, list):
        return "\n".join(str(s) for s in script)
    if isinstance(script, dict):
        return script.get("text", script.get("caption", script.get("body", str(script))))
    return str(script)


def _linkedin_params(script: dict) -> dict:
    commentary = (
        script.get("post")
        or script.get("commentary")
        or script.get("body")
        or _extract_text(script)
    )
    return {"commentary": commentary[:3000]}


class SocialPublisher:
    """Publishes generated scripts to social platforms via Composio.

    Falls back to export files when:
    - Composio is not installed
    - API key is not configured
    - Platform is export-only (TikTok, Pinterest, Instagram)
    - No connected account exists for a platform
    """

    def __init__(self, composio_key: str = ""):
        self.composio_key = composio_key
        self.composio = None
        self._results = []
        self._client = ComposioClient(api_key=composio_key)
        if self._client.available:
            self.composio = self._client.client

    def publish(self, script: dict, platform: str, niche: str = "",
                media_paths: list[str] | None = None) -> dict:
        mapping = PLATFORM_ACTIONS.get(platform)
        if not mapping:
            return {"status": "error", "platform": platform, "reason": "unknown_platform"}

        # MASTER SWITCH: nothing posts to live social until explicitly enabled.
        from ..core.social_gate import require_social_publishing

        if not require_social_publishing():
            return self._export(script, platform, niche)

        # Platform scoping: with the gate ON, only explicitly allowed platforms go live.
        from ..deploy.social import _allowed_platforms
        allowed = _allowed_platforms()
        if allowed is not None and platform not in allowed:
            return self._export(script, platform, niche)

        if mapping.get("export_only") or not self._client.available:
            return self._export(script, platform, niche)

        params = mapping["params_fn"](script)
        if platform == "linkedin":
            params["author"] = self._client.linkedin_author_urn()

        try:
            self._client.execute(mapping["toolkit"], mapping["slug"], params)
            result = {"status": "posted", "platform": platform, "tool": mapping["slug"]}
            self._results.append(result)
            logger.info(f"{platform}: posted via {mapping['slug']}")
            return result
        except Exception as e:
            logger.warning(f"{platform}: Composio failed — exporting instead: {e}")
            return self._export(script, platform, niche)

    def publish_all(self, scripts: dict, niche: str = "") -> list[dict]:
        results = []
        for platform, script in scripts.items():
            r = self.publish(script, platform, niche)
            results.append(r)
        return results

    def _export(self, script: dict | list | str, platform: str,
                niche: str) -> dict:
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        niche_slug = niche.replace(" ", "_") if niche else "general"
        export_dir = EXPORT_DIR / niche_slug / platform
        export_dir.mkdir(parents=True, exist_ok=True)

        export_file = export_dir / f"{date_str}.json"
        export_data = {
            "platform": platform,
            "niche": niche,
            "script": script,
            "generated_at": datetime.now().isoformat(),
        }
        export_file.write_text(json.dumps(export_data, indent=2), encoding="utf-8")

        text_file = export_dir / f"{date_str}.txt"
        text_file.write_text(_extract_text(script), encoding="utf-8")

        result = {
            "status": "exported",
            "platform": platform,
            "niche": niche,
            "export_path": str(export_file),
            "text_path": str(text_file),
        }
        self._results.append(result)
        logger.info(f"{platform}: exported to {export_file}")
        return result

    def get_results(self) -> list[dict]:
        return list(self._results)

    def can_post_direct(self) -> bool:
        return self._client.available