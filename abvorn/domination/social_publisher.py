"""Social Publisher — publishes content to social platforms via Composio
or export-ready file generation when Composio is unavailable."""

import logging, json
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("abvorn.domination.social_publisher")

EXPORT_DIR = Path.home() / ".abvorn" / "exports"

try:
    from composio import ComposioToolSet, Action
    HAS_COMPOSIO = True
except ImportError:
    HAS_COMPOSIO = False
    Action = object


PLATFORM_ACTIONS = {
    "x": {
        "actions": ["X_CREATE_TWEET", "TWITTER_CREATE_TWEET", "TWITTER_POST_TWEET"],
        "params_fn": lambda script: {"text": _extract_text(script)[:280]},
    },
    "linkedin": {
        "actions": ["LINKEDIN_CREATE_POST", "LINKEDIN_POST_CREATE"],
        "params_fn": lambda script: _linkedin_params(script),
    },
    "instagram": {
        "actions": ["INSTAGRAM_CREATE_POST", "INSTAGRAM_CREATE_MEDIA_POST"],
        "params_fn": lambda script: {"caption": _extract_text(script)[:2200]},
    },
    "facebook": {
        "actions": ["FACEBOOK_CREATE_POST", "FACEBOOK_POST_CREATE"],
        "params_fn": lambda script: {"message": _extract_text(script)[:63206]},
    },
    "tiktok": {
        "actions": [],
        "params_fn": lambda script: {},
        "export_only": True,
    },
    "pinterest": {
        "actions": [],
        "params_fn": lambda script: {},
        "export_only": True,
    },
    "medium": {
        "actions": ["MEDIUM_CREATE_POST", "MEDIUM_PUBLISH_POST"],
        "params_fn": lambda script: _medium_params(script),
    },
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
    return {
        "text": script.get("headline", script.get("hook", "")),
        "body": script.get("body", str(script))[:3000],
    }


def _medium_params(script: dict) -> dict:
    text = _extract_text(script)
    return {"title": "New Post", "content": text[:5000]}


class SocialPublisher:
    """Publishes generated scripts to social platforms via Composio.

    Falls back to export files when:
    - Composio is not installed
    - API key is not configured
    - Platform is export-only (TikTok, Pinterest)
    """

    def __init__(self, composio_key: str = ""):
        self.composio_key = composio_key
        self.composio = None
        self._results = []
        self._init_composio()

    def _init_composio(self):
        if not HAS_COMPOSIO:
            logger.info("Composio not installed — export-only mode")
            return
        if not self.composio_key:
            logger.info("No Composio key — export-only mode")
            return
        try:
            self.composio = ComposioToolSet(api_key=self.composio_key)
            logger.info("Composio client initialized")
        except Exception as e:
            logger.warning(f"Composio init failed: {e}")

    def publish(self, script: dict, platform: str, niche: str = "",
                media_paths: list[str] | None = None) -> dict:
        mapping = PLATFORM_ACTIONS.get(platform)
        if not mapping:
            return {"status": "error", "platform": platform, "reason": "unknown_platform"}

        if mapping.get("export_only") or not self.composio:
            return self._export(script, platform, niche)

        params = mapping["params_fn"](script)
        last_error = ""

        for action_name in mapping["actions"]:
            action = getattr(Action, action_name, None)
            if not action:
                continue
            try:
                self.composio.execute_action(action, params=params)
                result = {"status": "posted", "platform": platform, "action": action_name}
                self._results.append(result)
                logger.info(f"{platform}: posted via {action_name}")
                return result
            except Exception as e:
                last_error = str(e)[:200]
                logger.debug(f"{platform} via {action_name}: {last_error}")

        if last_error:
            logger.warning(f"{platform}: Composio failed — exporting instead")
            return self._export(script, platform, niche)

        return {"status": "failed", "platform": platform, "error": last_error}

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
        return HAS_COMPOSIO and self.composio is not None
