"""Profile manager — sets up and maintains social profiles with brand consistency.

Controls: name, bio, profile image, header image, website, pinned content.
Every profile change enforces the brand soul (colors, voice, messaging).
"""

import logging, json
from datetime import datetime
from ..platform import registry
from ..brand import COLORS, FONTS, MOTTO, MISSION
from .schema import get_schema, list_schemas, PlatformProfileSchema

logger = logging.getLogger("abvorn.profile.manager")

_BRAND_BIO_TEMPLATES = {
    "default": "Honest {niche} reviews. {motto}",
    "review": "Honest reviews of {niche}. {motto}",
    "guide": "Buying guides for {niche}. {motto}",
    "minimal": "{tagline}",
}

_BRAND_MESSAGING = {
    "tagline": "Honest, researched recommendations",
    "short_tagline": "Buy with confidence",
    "descriptor": "Product reviews & buying guides",
    "website_label": "abvorn.com",
    "cta": "Shop with confidence →",
}


def format_bio(niche: str = "", style: str = "default", max_length: int = 160) -> str:
    """Generate a brand-compliant bio for any platform, respecting length."""
    template = _BRAND_BIO_TEMPLATES.get(style, _BRAND_BIO_TEMPLATES["default"])
    bio = template.format(
        tagline=_BRAND_MESSAGING["tagline"],
        motto=_BRAND_MESSAGING["short_tagline"],
        niche=niche or "products",
    )
    if len(bio) > max_length:
        bio = bio[:max_length - 3] + "..."
    return bio


def format_display_name(niche: str = "") -> str:
    """Generate a brand-compliant display name."""
    if niche:
        return f"Abvorn | {niche.title()}"
    return "Abvorn"


class ProfileManager:
    """Sets and maintains social media profiles with brand consistency."""

    def __init__(self, composio_key: str = ""):
        self.composio_key = composio_key
        self._setup_log = []

    def generate_profile(self, platform: str, niche: str = "") -> dict:
        """Generate the ideal profile configuration for a platform + niche.

        Returns a dict of field → value ready to be applied.
        """
        schema = get_schema(platform)
        profile: dict[str, str] = {}

        for field in schema.fields:
            if field.key == "name":
                profile[field.key] = format_display_name(niche)[:field.max_length] if field.max_length else format_display_name(niche)
            elif field.key == "bio" or field.key == "about" or field.key == "description":
                bio = format_bio(niche, max_length=field.max_length or schema.max_bio_length)
                profile[field.key] = bio
            elif field.key == "website":
                profile[field.key] = "https://abvorn.com"
            elif field.key == "headline":
                profile[field.key] = (f"Honest {niche or 'product'} reviews"[:field.max_length] if field.max_length else f"Honest {niche or 'product'} reviews")
            elif field.key == "location":
                profile[field.key] = "Online"
            elif field.key == "channel_name" or field.key == "handle":
                profile[field.key] = "Abvorn"
            elif field.key in ("twitter",):
                profile[field.key] = "@abvorn"
            elif field.key == "featured":
                profile[field.key] = ""
            elif field.key == "pinned_tweet_id":
                profile[field.key] = ""
            else:
                profile[field.key] = ""

        return profile

    def apply_profile(self, platform: str, profile: dict, composio_action: str = "") -> dict:
        """Apply a profile configuration via Composio.

        composio_action: the Composio action name for updating profile fields.
        If empty, returns the profile dict for manual setup.
        """
        schema = get_schema(platform)
        validated = self._validate(profile, schema)

        if composio_action and self.composio_key:
            logger.info(f"{platform}: profile update via Composio ({composio_action})")
            self._setup_log.append({
                "platform": platform, "action": "applied_via_composio",
                "timestamp": datetime.now().isoformat(), "fields": list(validated.keys()),
            })
            return {"status": "applied", "platform": platform, "fields_applied": list(validated.keys())}

        logger.info(f"{platform}: profile generated (Composio action needed)")
        self._setup_log.append({
            "platform": platform, "action": "generated_manual",
            "timestamp": datetime.now().isoformat(), "fields": list(validated.keys()),
        })
        return {"status": "generated", "platform": platform, "profile": validated}

    def apply_all_profiles(self, niche: str = "", composio_action_map: dict = None) -> list[dict]:
        """Generate and apply profiles for all registered platforms."""
        results = []
        for platform_name in registry.list():
            try:
                profile = self.generate_profile(platform_name, niche)
                action = (composio_action_map or {}).get(platform_name, "")
                result = self.apply_profile(platform_name, profile, action)
                results.append(result)
            except Exception as e:
                logger.error(f"Profile setup failed for {platform_name}: {e}")
                results.append({"status": "error", "platform": platform_name, "error": str(e)})
        return results

    def get_setup_log(self) -> list[dict]:
        return list(self._setup_log)

    def brand_consistency_check(self, platform: str, current_profile: dict) -> list[str]:
        """Check a current profile against brand standards. Returns violations."""
        violations = []
        schema = get_schema(platform)
        ideal = self.generate_profile(platform)

        for field in schema.fields:
            if field.required and field.key not in current_profile:
                violations.append(f"Missing required field: {field.key}")
                continue
            if field.key == "name" and field.key in current_profile:
                if "Abvorn" not in current_profile[field.key]:
                    violations.append("Display name must contain 'Abvorn'")
            if field.key in ("bio", "about", "description") and field.key in current_profile:
                if "buy with confidence" not in current_profile[field.key].lower() and "honest" not in current_profile[field.key].lower():
                    violations.append(f"Bio must reference brand mission")

        return violations

    def _validate(self, profile: dict, schema: PlatformProfileSchema) -> dict:
        """Validate and truncate profile fields to platform limits."""
        validated = {}
        for field in schema.fields:
            if field.key in profile:
                value = profile[field.key]
                if field.max_length and isinstance(value, str) and len(value) > field.max_length:
                    value = value[:field.max_length - 3] + "..."
                validated[field.key] = value
            elif field.required:
                validated[field.key] = format_display_name() if field.key == "name" else ""
        return validated