"""Registry-aware social deployer — posts to any registered platform via Composio."""

import logging
import os
from pathlib import Path

from ..platform import registry

logger = logging.getLogger("abvorn.deploy.social")

try:
    from src.deployment import check_encoding, repair_mojibake
    HAS_ENCODING_GUARD = True
except ImportError:
    HAS_ENCODING_GUARD = False
    check_encoding = None
    repair_mojibake = None

from .composio_client import ComposioClient, HAS_COMPOSIO

# Composio v3 (SDK >= 0.21) — tools are raw slugs on a modern REST API.
# Only platforms with a live connected account get a backend here; the
# publication pipeline resolves the account, toolkit version, and author
# identity at runtime from the Composio platform.
COMPOSIO_TOOLS = {
    "x": {"toolkit": "twitter", "slug": "TWITTER_CREATION_OF_A_POST"},
    "linkedin": {
        "toolkit": "linkedin",
        "slug": "LINKEDIN_CREATE_LINKED_IN_POST",
        # Article/URL share renders the link-preview card (visual + link).
        "url_share_slug": "LINKEDIN_CREATE_ARTICLE_OR_URL_SHARE",
    },
}


def _allowed_platforms() -> set | None:
    """Which platforms may go live when the gate is ON.

    Scoping comes from env ABVORN_SOCIAL_PLATFORMS (highest priority) or the
    data/social_platforms.txt file (one name per line). None means "no scoping
    — every registered platform is allowed", preserving legacy behaviour.
    """
    raw = os.environ.get("ABVORN_SOCIAL_PLATFORMS", "").strip()
    if not raw:
        try:
            raw = Path("data/social_platforms.txt").read_text(encoding="utf-8").strip()
        except OSError:
            raw = ""
    if not raw:
        return None
    return {p.strip().lower() for p in raw.replace(",", "\n").splitlines() if p.strip()}


class TelegramDeployer:
    """Posts a message to a Telegram channel or private chat using the Bot API."""

    def __init__(self, token: str = "", chat_id: str = "", channel: str = ""):
        self.token = token or os.environ.get("TELEGRAM_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.channel = channel or os.environ.get("ABVORN_TELEGRAM_CHANNEL", "")
        if not self.token or not self.chat_id:
            try:
                from ..core.secrets import load_secrets
                secrets = load_secrets()
                self.token = self.token or secrets.get("TELEGRAM_TOKEN", "")
                self.chat_id = self.chat_id or secrets.get("TELEGRAM_CHAT_ID", "")
            except Exception:
                pass

    def post(self, adapted: dict) -> dict:
        if not self.token:
            return {"status": "error", "platform": "telegram", "reason": "no_telegram_token"}
        target = self.channel or self.chat_id
        if not target:
            return {"status": "error", "platform": "telegram", "reason": "no_telegram_chat_id"}
        import requests
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": target,
            "text": adapted.get("text", "")[:4000],
            "link_preview_options": {"is_disabled": True},
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            data = resp.json()
        except Exception as e:
            return {"status": "failed", "platform": "telegram", "error": str(e)[:200]}
        if resp.status_code == 200 and data.get("ok"):
            return {"status": "posted", "platform": "telegram", "chat_id": target}
        return {"status": "failed", "platform": "telegram", "error": f"{resp.status_code} {str(data)[:200]}"}


class SocialDeployer:
    """Posts content to registered social platforms via Composio."""

    def __init__(self, composio_key: str = ""):
        self.composio_key = composio_key
        self.composio = None
        self._client = ComposioClient(api_key=composio_key)
        if self._client.available:
            self.composio = self._client.client
        self._posted = []
        self._results = []

    def _toolkit_version(self, toolkit: str) -> str | None:
        """Resolve the publishable toolkit version from the Composio API."""
        return self._client.toolkit_version(toolkit)

    def _connection(self, toolkit: str):
        """Return (user_id, connected_account_id, version) for a toolkit, cached.

        The connection is resolved from the live list of connected accounts so
        the deployer survives account rotation without code changes.
        """
        return self._client.connection(toolkit)

    def _linkedin_author_urn(self) -> str:
        """Resolve the author URN for LinkedIn posts (env override or discovery)."""
        return self._client.linkedin_author_urn()

    def _params_for(self, platform: str, adapted) -> dict:
        if platform == "x":
            text = adapted[0][:280] if isinstance(adapted, list) and adapted else str(adapted)[:280]
            return {"text": text}
        if platform == "linkedin":
            commentary = (
                adapted.get("post", adapted.get("body", ""))
                if isinstance(adapted, dict) else str(adapted)
            )
            params = {"author": self._linkedin_author_urn(), "commentary": commentary[:3000]}
            if isinstance(adapted, dict):
                raw_url = str(adapted.get("url", "") or "").strip()
                if raw_url:
                    params["url"] = raw_url
                    params["title"] = str(adapted.get("title", ""))[:200]
                    params["description"] = str(adapted.get("body", ""))[:350]
            return params
        raise ValueError(f"no params builder for {platform}")

    def _exec_linkedin_url_share(self, uid, caid, version, share_slug, params):
        """Post a LinkedIn article/URL share (link-preview card).

        Returns the execute response on success, or None so the caller can fall
        through to the plain text post when the card path fails.
        """
        try:
            args = {
                "author": params["author"],
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": params["commentary"]},
                        "shareMediaCategory": "ARTICLE",
                        "media": [{
                            "status": "READY",
                            "originalUrl": params["url"],
                            "title": {"text": params.get("title", "") or ""},
                            "description": {"text": params.get("description", "") or ""},
                        }],
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }
            resp = self.composio.tools.execute(
                slug=share_slug,
                arguments=args,
                user_id=uid,
                connected_account_id=caid,
                version=version,
            )
            if resp and resp.get("successful"):
                return resp
            logger.warning(f"linkedin: URL-share failed — {str(resp.get('error'))[:160]}")
        except Exception as e:
            logger.warning(f"linkedin: URL-share exception — {str(e)[:160]}")
        return None

    @staticmethod
    def _sanitize_encoding(adapted, platform: str):
        """Repair mojibake in adapted content and raise if any survives.

        Adapted content is a string, a list (e.g. X/IG), or a dict (e.g.
        LinkedIn). The guard repairs known double-encoding and then blocks the
        post entirely if any mojibake signature remains — corrupted text must
        never reach a live platform.
        """
        if not HAS_ENCODING_GUARD:
            return adapted

        def _fix(value):
            if isinstance(value, str):
                return repair_mojibake(value)
            return value

        def _check(value, where=""):
            if isinstance(value, str):
                check_encoding(value, label=f"social post ({platform}{where})")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    _check(item, f"[{i}]")
            elif isinstance(value, dict):
                for k, item in value.items():
                    _check(item, f".{k}")

        # Repair first, then block if any mojibake signature survives.
        if isinstance(adapted, str):
            adapted = _fix(adapted)
            _check(adapted)
            return adapted
        if isinstance(adapted, list):
            adapted = [_fix(item) if isinstance(item, str) else item for item in adapted]
            _check(adapted)
            return adapted
        if isinstance(adapted, dict):
            adapted = {k: (_fix(v) if isinstance(v, str) else v) for k, v in adapted.items()}
            _check(adapted)
            return adapted
        return adapted

    def post(self, content: dict, platform: str) -> dict:
        """Post adapted content to a single platform."""
        if not registry.has(platform):
            return {"status": "error", "reason": f"unknown_platform:{platform}"}

        # MASTER SWITCH: nothing posts to live social until explicitly enabled.
        from ..core.social_gate import require_social_publishing

        config = registry.get(platform)
        adapted = config.adapter_fn(content)

        # Encoding guard: block mojibake from reaching live social platforms.
        # Social posts don't round-trip through files like the docs/ pipeline,
        # but corrupted source text would still pass straight through to the API.
        adapted = self._sanitize_encoding(adapted, platform)

        if not require_social_publishing():
            self._posted.append(platform)
            logger.info(f"{platform}: publish gate OFF — draft staged (not posted)")
            return {"status": "staged", "platform": platform, "data": adapted}

        # Platform scoping: with the gate ON, only explicitly allowed platforms
        # go live; everything else stays staged.
        allowed = _allowed_platforms()
        if allowed is not None and platform not in allowed:
            self._posted.append(platform)
            logger.info(f"{platform}: not in allowed list — draft staged (not posted)")
            return {"status": "staged", "platform": platform, "data": adapted}

        if config.is_export_only:
            logger.info(f"{platform}: export-only — adapted content ready")
            self._posted.append(platform)
            return {"status": "exported", "platform": platform, "data": adapted}

        if platform == "telegram":
            result = TelegramDeployer().post(adapted)
            self._posted.append(platform)
            self._results.append(result)
            logger.info(f"telegram: {result.get('status')}")
            return result

        if not self.composio_key or not self.composio:
            logger.warning(f"No Composio key — {platform} post skipped")
            return {"status": "skipped", "platform": platform, "reason": "no_composio_key"}

        mapping = COMPOSIO_TOOLS.get(platform)
        if not mapping:
            logger.warning(f"No Composio v3 backend for {platform}")
            return {"status": "error", "platform": platform, "reason": "no_composio_backend"}

        uid, caid, version = self._connection(mapping["toolkit"])
        if not uid or not caid or not version:
            result = {
                "status": "failed",
                "platform": platform,
                "reason": f"no_resolved_composio_connection:{mapping['toolkit']}",
            }
            self._results.append(result)
            logger.warning(f"{platform}: {result['reason']}")
            return result

        try:
            params = self._params_for(platform, adapted)
        except Exception as e:
            result = {"status": "failed", "platform": platform, "reason": str(e)[:200]}
            self._results.append(result)
            logger.warning(f"{platform}: params failed — {result['reason']}")
            return result

        try:
            resp = None
            share_slug = mapping.get("url_share_slug") if platform == "linkedin" else None
            if share_slug and params.get("url"):
                resp = self._exec_linkedin_url_share(uid, caid, version, share_slug, params)
                if resp is not None:
                    self._posted.append(platform)
                    result = {"status": "posted", "platform": platform, "tool": share_slug}
                    self._results.append(result)
                    logger.info(f"{platform}: posted via {share_slug}")
                    return result
                logger.warning(f"{platform}: URL-share failed — falling back to text post")
            if resp is None:
                resp = self.composio.tools.execute(
                    slug=mapping["slug"],
                    arguments=params,
                    user_id=uid,
                    connected_account_id=caid,
                    version=version,
                )
            if resp and resp.get("successful"):
                self._posted.append(platform)
                result = {"status": "posted", "platform": platform, "tool": mapping["slug"]}
                self._results.append(result)
                logger.info(f"{platform}: posted via {mapping['slug']}")
                return result
            result = {
                "status": "failed",
                "platform": platform,
                "error": str(resp.get("error") or "unknown execution failure")[:300],
            }
        except Exception as e:
            result = {"status": "failed", "platform": platform, "error": str(e)[:200]}
        self._results.append(result)
        logger.warning(f"{platform}: composio execution failed — {result.get('error')}")
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