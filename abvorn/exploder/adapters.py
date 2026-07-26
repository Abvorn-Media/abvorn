"""Re-exports from platform registry — maintains backward compatibility."""

from ..platform.adapters import (
    x_adapter as adapt_for_x,
    linkedin_adapter as adapt_for_linkedin,
    tiktok_adapter as adapt_for_tiktok,
    instagram_adapter as adapt_for_instagram,
    pinterest_adapter as adapt_for_pinterest,
    medium_adapter as adapt_for_medium,
)

from ..platform.adapters import (
    facebook_adapter as adapt_for_facebook,
    youtube_adapter as adapt_for_youtube,
)

__all__ = [
    "adapt_for_x", "adapt_for_linkedin", "adapt_for_tiktok",
    "adapt_for_instagram", "adapt_for_pinterest", "adapt_for_medium",
    "adapt_for_facebook", "adapt_for_youtube",
]