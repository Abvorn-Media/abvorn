"""Registry-aware social deployer — posts to any registered platform via Composio."""

import logging
from ..platform import registry

logger = logging.getLogger("abvorn.deploy.social")

try:
    from composio import ComposioToolSet, Action
    HAS_COMPOSIO = True
except ImportError:
    HAS_COMPOSIO = False
    Action = object

SOCIAL_ACTIONS = {
    "x": {
        "actions": ["X_CREATE_TWEET", "TWITTER_CREATE_TWEET", "TWITTER_POST_TWEET"],
        "params_fn": lambda adapted: {"text": adapted[0][:280]},
    },
    "linkedin": {
        "actions": ["LINKEDIN_CREATE_POST", "LINKEDIN_POST_CREATE", "LINKEDIN_CREATE_ARTICLE"],
        "params_fn": lambda adapted: {"text": adapted.get("post", adapted.get("body", ""))[:3000]},
    },
    "facebook": {
        "actions": ["FACEBOOK_CREATE_POST", "FACEBOOK_POST_CREATE"],
        "params_fn": lambda adapted: {"message": adapted.get("message", "")[:63206]},
    },
    "medium": {
        "actions": ["MEDIUM_CREATE_POST", "MEDIUM_PUBLISH_POST"],
        "params_fn": lambda adapted: {"title": adapted.get("title", "Post"), "content": adapted.get("body", "")[:5000]},
    },
    "instagram": {
        "actions": ["INSTAGRAM_CREATE_POST", "INSTAGRAM_CREATE_MEDIA_POST"],
        "params_fn": lambda adapted: {"caption": adapted[0][:2200]},
    },
}


class SocialDeployer:
    """Posts content to registered social platforms via Composio."""

    def __init__(self, composio_key: str = ""):
        self.composio_key = composio_key
        self.composio = None
        if composio_key and HAS_COMPOSIO:
            try:
                self.composio = ComposioToolSet(api_key=composio_key)
                logger.info("Composio client initialized")
            except Exception as e:
                logger.warning(f"Composio init failed: {e}")
        self._posted = []
        self._results = []

    def post(self, content: dict, platform: str) -> dict:
        """Post adapted content to a single platform."""
        if not registry.has(platform):
            return {"status": "error", "reason": f"unknown_platform:{platform}"}

        # MASTER SWITCH: nothing posts to live social until explicitly enabled.
        from ..core.social_gate import require_social_publishing

        config = registry.get(platform)
        adapted = config.adapter_fn(content)

        if not require_social_publishing():
            self._posted.append(platform)
            logger.info(f"{platform}: publish gate OFF — draft staged (not posted)")
            return {"status": "staged", "platform": platform, "data": adapted}

        if config.is_export_only:
            logger.info(f"{platform}: export-only — adapted content ready")
            self._posted.append(platform)
            return {"status": "exported", "platform": platform, "data": adapted}

        if not self.composio_key or not self.composio:
            logger.warning(f"No Composio key — {platform} post skipped")
            return {"status": "skipped", "platform": platform, "reason": "no_composio_key"}

        mapping = SOCIAL_ACTIONS.get(platform)
        if not mapping:
            logger.warning(f"No Composio action mapping for {platform}")
            return {"status": "error", "platform": platform, "reason": "no_action_mapping"}

        params = mapping["params_fn"](adapted)
        last_error = ""

        for action_name in mapping["actions"]:
            action = getattr(Action, action_name, None)
            if not action:
                continue
            try:
                self.composio.execute_action(action, params=params)
                self._posted.append(platform)
                result = {"status": "posted", "platform": platform, "action": action_name}
                self._results.append(result)
                logger.info(f"{platform}: posted via {action_name}")
                return result
            except Exception as e:
                last_error = str(e)[:100]
                logger.debug(f"{platform} via {action_name}: {last_error}")

        result = {"status": "failed", "platform": platform, "error": last_error}
        self._results.append(result)
        logger.warning(f"{platform}: all actions failed — {last_error}")
        return result

    def post_to_all(self, content: dict, platforms: list[str] = None) -> list[dict]:
        """Post content to all (or specified) platforms."""
        targets = platforms or registry.list(category="social")
        results = []
        for p in targets:
            if p == "youtube":
                logger.info(f"{p}: stub platform — skipping (ready for integration)")
                results.append({"status": "stub", "platform": p})
                continue
            results.append(self.post(content, p))
        return results

    def export(self, content: dict, platform: str) -> dict:
        """Export content for an export-only platform (TikTok, IG, etc.)."""
        return self.post(content, platform)

    @property
    def posted(self) -> list[str]:
        return list(self._posted)

    @property
    def results(self) -> list[dict]:
        return list(self._results)