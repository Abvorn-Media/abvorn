"""Social Publisher — publishes content to social platforms via Composio
or export-ready file generation when Composio is unavailable."""

import logging, json, re
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
        "url_share_slug": "LINKEDIN_CREATE_ARTICLE_OR_URL_SHARE",
        "params_fn": lambda script: _linkedin_params(script),
    },
    "telegram": {
        "toolkit": "telegram",
        "params_fn": lambda script: {"text": _extract_text(script)[:3800]},
    },
    "instagram": {
        "toolkit": "instagram",
        "flow": "carousel",
        "slug": "INSTAGRAM_CREATE_POST",
    },
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
    commentary = str(commentary or "").strip()
    if not commentary:
        commentary = (
            str(script.get("headline") or script.get("title") or "").strip()
            or "After comparing real specs, prices, and owner feedback across the top options, here's what stands out."
        )
    params = {"commentary": commentary[:3000]}
    raw_url = str(script.get("url", "") or "").strip()
    if raw_url:
        params["url"] = raw_url
        params["title"] = str(script.get("title", "") or "")[:200]
        params["description"] = str(script.get("body", "") or "")[:350]
    return params


def _linkedin_url_share_args(params: dict) -> dict | None:
    raw_url = params.get("url")
    if not raw_url:
        return None
    return {
        "author": params["author"],
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": params["commentary"]},
                "shareMediaCategory": "ARTICLE",
                "media": [{
                    "status": "READY",
                    "originalUrl": raw_url,
                    "title": {"text": params.get("title", "") or ""},
                    "description": {"text": params.get("description", "") or ""},
                }],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }


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
            return self._export(script, platform, niche, media_paths=media_paths)

        # Platform scoping: with the gate ON, only explicitly allowed platforms go live.
        from ..deploy.social import _allowed_platforms
        allowed = _allowed_platforms()
        if allowed is not None and platform not in allowed:
            return self._export(script, platform, niche, media_paths=media_paths)

        # Telegram posts via the Bot API directly — no Composio connection needed.
        # Product photos go along as a media group when they exist.
        if platform == "telegram":
            params = mapping["params_fn"](script)
            return self._publish_telegram(params, script, platform, niche, media_paths)

        if mapping.get("export_only") or not self._client.available:
            return self._export(script, platform, niche, media_paths=media_paths)

        if mapping.get("flow") == "carousel":
            return self._publish_instagram_carousel(script, platform, niche, media_paths)

        params = mapping["params_fn"](script)
        if platform == "linkedin":
            params["author"] = self._client.linkedin_author_urn()

        try:
            share_slug = mapping.get("url_share_slug") if platform == "linkedin" else None
            share_args = _linkedin_url_share_args(params) if share_slug else None
            if share_args:
                try:
                    self._client.execute(mapping["toolkit"], share_slug, share_args)
                    result = {"status": "posted", "platform": platform, "tool": share_slug}
                    self._results.append(result)
                    logger.info(f"{platform}: posted via {share_slug}")
                    return result
                except Exception as e:
                    logger.warning(f"{platform}: URL-share failed — falling back: {e}")
            self._client.execute(mapping["toolkit"], mapping["slug"], params)
            result = {"status": "posted", "platform": platform, "tool": mapping["slug"]}
            self._results.append(result)
            logger.info(f"{platform}: posted via {mapping['slug']}")
            return result
        except Exception as e:
            logger.warning(f"{platform}: Composio failed — exporting instead: {e}")
            return self._export(script, platform, niche, media_paths=media_paths)

    def publish_all(self, scripts: dict, niche: str = "",
                    media_paths: list[str] | None = None,
                    media_by_platform: dict | None = None) -> list[dict]:
        results = []
        for platform, script in scripts.items():
            platform_media = (media_by_platform or {}).get(platform, media_paths)
            r = self.publish(script, platform, niche, media_paths=platform_media)
            results.append(r)
        return results

    def _honest_instagram_caption(self, script: dict | list | str, niche: str) -> str:
        """Build a caption that never claims physical hands-on testing.

        We do research-based comparison (specs, prices, owner feedback) — not
        physical product testing — so any caption carrying a false-testing
        marker is replaced with neutral, honest phrasing. For a carousel
        (list of slides) the caption is the hook slide, not the whole deck.
        """
        if isinstance(script, list) and script:
            caption = str(script[0]) or ""
        else:
            caption = _extract_text(script)
        caption = caption.replace("\U0001F4CC", "").replace("\U0001F517", "").strip()
        caption = re.sub(r"\s+", " ", caption)[:2000]
        from ..platform.adapters import _has_false_testing_claim
        if not caption or _has_false_testing_claim(caption):
            caption = (
                f"After comparing specs, prices, and real owner feedback for "
                f"{niche or 'these products'}, here's what stands out."
            )
        return caption[:2200]

    def _resize_for_instagram(self, media_paths: list[str]) -> list[str]:
        """Resize images to 1080x1350 (IG 4:5 feed format) into the export cache.

        Never returns an unresized original: a failed resize drops that image
        instead of posting a wrong-size/low-quality frame."""
        try:
            from .cinematic_filter import CinematicFilter
            filter_ = CinematicFilter()
        except Exception:
            return []
        resized = []
        cache_dir = Path.home() / ".abvorn" / "exports" / "instagram"
        cache_dir.mkdir(parents=True, exist_ok=True)
        for i, path in enumerate(media_paths[:10]):
            if not Path(path).exists():
                continue
            import time
            out = cache_dir / f"ig_{int(time.time() * 1000)}_{i}.jpg"
            try:
                done = filter_.resize_for_platform(path, "instagram", str(out))
                if done and Path(done).exists():
                    resized.append(str(done))
            except Exception as e:
                logger.warning(f"instagram resize failed for {path}: {e}")
        return resized

    def _publish_telegram(self, params: dict, script: dict | list | str,
                          platform: str, niche: str,
                          media_paths: list[str] | None = None) -> dict:
        """Post to Telegram via the Bot API (no Composio needed).

        When real product photos exist they go out as a media group with the
        hook as its caption; the full post with link preview follows as a
        normal message. Either leg can degrade to text-only / export.
        """
        from ..deploy.social import TelegramDeployer
        media_paths = media_paths or []
        deployer = TelegramDeployer()
        try:
            if media_paths:
                # Reuse pre-composed platform media as-is; assert presence only.
                existing = [p for p in media_paths if Path(p).exists()]
                if existing:
                    result = deployer.post_media_group(
                        existing, params.get("text", "")[:3800]
                    )
                    if result.get("status") == "posted":
                        logger.info(f"telegram: posted {len(existing)} photos via Bot API sendMediaGroup")
                    else:
                        logger.warning(f"telegram: media group {result.get('status')} — falling back to text")
                        result = deployer.post({"text": params.get("text", "")}, enable_preview=True)
                else:
                    result = deployer.post({"text": params.get("text", "")}, enable_preview=True)
            else:
                result = deployer.post({"text": params.get("text", "")}, enable_preview=True)
        except Exception as e:
            logger.warning(f"telegram: Bot API failed — exporting instead: {e}")
            return self._export(script, platform, niche, media_paths=media_paths)
        if result.get("status") == "posted":
            self._results.append(result)
            logger.info(f"telegram: posted ({media_paths and 'media+text' or 'text'})")
            return result
        logger.warning(f"telegram: {result.get('status')} ({result.get('error')}) — exporting instead")
        return self._export(script, platform, niche, media_paths=media_paths)

    def _publish_instagram_carousel(self, script: dict | list | str, platform: str,
                                    niche: str, media_paths: list[str] | None) -> dict:
        media_paths = media_paths or []
        if len(media_paths) < 2:
            logger.warning("instagram: carousel needs >=2 images — exporting instead")
            return self._export(script, platform, niche, media_paths=media_paths)

        caption = self._honest_instagram_caption(script, niche)
        images = self._resize_for_instagram(media_paths)
        try:
            result_data = self._client.instagram_publish_carousel(caption, images)
            result = {
                "status": "posted",
                "platform": platform,
                "tool": "INSTAGRAM_CREATE_POST",
                "data": result_data,
            }
            self._results.append(result)
            logger.info(f"instagram: carousel posted ({result_data})")
            return result
        except Exception as e:
            logger.warning(f"instagram: Composio failed — exporting instead: {e}")
            return self._export(script, platform, niche, media_paths=media_paths)

    def _export(self, script: dict | list | str, platform: str,
                niche: str, media_paths: list[str] | None = None) -> dict:
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        niche_slug = niche.replace(" ", "_") if niche else "general"
        export_dir = EXPORT_DIR / niche_slug / platform
        export_dir.mkdir(parents=True, exist_ok=True)

        # Ship composed media alongside the export JSON so the draft is complete
        # (Pinterest pins, LinkedIn/X share cards, etc.) even when the gate is OFF.
        media_list: list[str] = []
        for i, path in enumerate(media_paths or []):
            if not Path(path).exists():
                continue
            dest = export_dir / f"{date_str}_media_{i}.jpg"
            try:
                import shutil
                shutil.copy2(path, dest)
                media_list.append(dest.name)
            except OSError:
                continue

        export_file = export_dir / f"{date_str}.json"
        export_data = {
            "platform": platform,
            "niche": niche,
            "script": script,
            "media": media_list,
            "media_paths": [str(Path(p)) for p in (media_paths or []) if Path(p).exists()],
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
            "media": media_list,
        }
        self._results.append(result)
        logger.info(f"{platform}: exported to {export_file}")
        return result

    def get_results(self) -> list[dict]:
        return list(self._results)

    def can_post_direct(self) -> bool:
        return self._client.available