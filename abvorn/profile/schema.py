"""Per-platform profile schemas — defines what fields each platform supports."""

from dataclasses import dataclass, field
from typing import Optional

from ..platform import registry


@dataclass
class ProfileField:
    """A single field in a platform profile."""
    key: str
    label: str
    type: str = "text"            # text, url, image, multi_text, select
    max_length: int = 0           # 0 = no limit
    required: bool = False
    description: str = ""


@dataclass
class PlatformProfileSchema:
    """Complete profile schema for one platform."""
    platform: str
    fields: list[ProfileField] = field(default_factory=list)
    supports_images: bool = False
    supports_pinning: bool = False
    supports_featured: bool = False
    supports_links: bool = False
    max_bio_length: int = 0


# ─── Schema Definitions ───────────────────────────────────────────

PROFILE_SCHEMAS: dict[str, PlatformProfileSchema] = {
    "x": PlatformProfileSchema(
        platform="x",
        fields=[
            ProfileField("name", "Display Name", max_length=50, required=True),
            ProfileField("bio", "Bio", type="multi_text", max_length=160, required=True,
                         description="Your bio text"),
            ProfileField("website", "Website", type="url"),
            ProfileField("location", "Location", max_length=30),
            ProfileField("pinned_tweet_id", "Pinned Tweet ID", description="ID of tweet to pin"),
        ],
        supports_images=True, supports_pinning=True, supports_links=True,
        max_bio_length=160,
    ),
    "linkedin": PlatformProfileSchema(
        platform="linkedin",
        fields=[
            ProfileField("headline", "Headline", max_length=220, required=True),
            ProfileField("about", "About Section", type="multi_text", max_length=2600,
                         required=True),
            ProfileField("website", "Website", type="url"),
            ProfileField("featured", "Featured Content", type="multi_text"),
        ],
        supports_images=True, supports_featured=True, supports_links=True,
        max_bio_length=2600,
    ),
    "instagram": PlatformProfileSchema(
        platform="instagram",
        fields=[
            ProfileField("name", "Display Name", max_length=30, required=True),
            ProfileField("bio", "Bio", max_length=150, required=True),
            ProfileField("website", "Website", type="url"),
        ],
        supports_images=True, supports_links=True,
        max_bio_length=150,
    ),
    "facebook": PlatformProfileSchema(
        platform="facebook",
        fields=[
            ProfileField("name", "Page Name", max_length=75, required=True),
            ProfileField("bio", "About / Bio", type="multi_text", max_length=255,
                         required=True),
            ProfileField("website", "Website", type="url"),
            ProfileField("description", "Short Description", max_length=155),
        ],
        supports_images=True, supports_links=True,
        max_bio_length=255,
    ),
    "youtube": PlatformProfileSchema(
        platform="youtube",
        fields=[
            ProfileField("channel_name", "Channel Name", max_length=70, required=True),
            ProfileField("description", "Channel Description", type="multi_text",
                         max_length=5000, required=True),
            ProfileField("website", "Website", type="url"),
            ProfileField("handle", "Channel Handle", max_length=30, required=True),
        ],
        supports_images=True, supports_links=True,
        max_bio_length=5000,
    ),
    "tiktok": PlatformProfileSchema(
        platform="tiktok",
        fields=[
            ProfileField("name", "Display Name", max_length=30, required=True),
            ProfileField("bio", "Bio", max_length=80, required=True),
            ProfileField("website", "Website", type="url"),
        ],
        supports_images=True, supports_links=True,
        max_bio_length=80,
    ),
    "pinterest": PlatformProfileSchema(
        platform="pinterest",
        fields=[
            ProfileField("name", "Profile Name", max_length=50, required=True),
            ProfileField("bio", "About", max_length=500, required=True),
            ProfileField("website", "Website", type="url"),
        ],
        supports_images=True, supports_links=True,
        max_bio_length=500,
    ),
    "medium": PlatformProfileSchema(
        platform="medium",
        fields=[
            ProfileField("name", "Display Name", max_length=50, required=True),
            ProfileField("bio", "Bio", max_length=160, required=True),
            ProfileField("twitter", "X/Twitter Handle"),
            ProfileField("website", "Website", type="url"),
        ],
        supports_images=True, supports_links=True,
        max_bio_length=160,
    ),
}


def get_schema(platform: str) -> PlatformProfileSchema:
    """Get the profile schema for a platform."""
    if platform not in PROFILE_SCHEMAS:
        # Auto-generate basic schema for unregistered platforms
        return PlatformProfileSchema(
            platform=platform,
            fields=[
                ProfileField("name", "Display Name", required=True),
                ProfileField("bio", "Bio", type="multi_text", required=True),
            ],
            max_bio_length=200,
        )
    return PROFILE_SCHEMAS[platform]


def list_schemas() -> dict[str, PlatformProfileSchema]:
    """Return all profile schemas, including ones from the registry."""
    schemas = dict(PROFILE_SCHEMAS)
    for name in registry.list():
        if name not in schemas:
            schemas[name] = PlatformProfileSchema(platform=name)
    return schemas