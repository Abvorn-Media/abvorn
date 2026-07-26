"""Platform adapters — each platform registers itself via the @register decorator.

Adding a new platform:
  1. Write an adapter function
  2. Decorate with @registry.register("name", label="Name", ...)
  3. Done. No other file changes needed.
"""

import re
from . import registry
from .voice import get_voice


def _clean_text(html_text: str) -> str:
    return re.sub(r'<[^>]+>', '', html_text).strip()


def _extract_headings(html_text: str) -> list[str]:
    return re.findall(r'<h2>(.*?)</h2>', html_text, re.IGNORECASE)


@registry.register("x", label="X", content_types=["thread"],
                   max_length=280, category="social",
                   schedule_profile={"best_days": ["Tuesday", "Wednesday", "Thursday"],
                                      "best_hours": list(range(8, 16)),
                                      "min_gap_hours": 4, "max_per_day": 3, "cadence": "daily"},
                   voice_profile=get_voice("x"))
def x_adapter(anchor: dict) -> list[str]:
    """Convert anchor content into an X thread (8-12 posts)."""
    title = anchor.get("post_title", "New Post")
    intro = _clean_text(anchor.get("intro", ""))
    headings = _extract_headings(anchor.get("article_html", ""))
    thread = [
        f"🧵 {title}",
        intro[:280] if intro else f"After testing 20+ products, here's what we found.",
    ]
    for h in headings[:5]:
        thread.append(f"{h} — The full breakdown in our guide.")
    thread.append(f"Full guide: [link] What's your experience with these?")
    return [t[:280] for t in thread]


@registry.register("linkedin", label="LinkedIn", content_types=["article", "post"],
                   max_length=5000, supports_html=True, category="social",
                   schedule_profile={"best_days": ["Tuesday", "Wednesday", "Thursday"],
                                      "best_hours": list(range(8, 13)),
                                      "min_gap_hours": 24, "max_per_day": 1, "cadence": "daily"},
                   voice_profile=get_voice("linkedin"))
def linkedin_adapter(anchor: dict) -> dict:
    """Convert anchor into a LinkedIn article + post."""
    title = anchor.get("post_title", "New Post")
    intro = _clean_text(anchor.get("intro", ""))
    body = _clean_text(anchor.get("article_html", ""))
    description = anchor.get("meta_description", "")
    article = f"# {title}\n\n{description}\n\n{intro}\n\n{body[:2000]}"
    post = f"{description}\n\nFull article: [link]\n\nWhat's your pick? 👇"
    return {"title": title, "body": article[:5000], "post": post[:1300]}


@registry.register("tiktok", label="TikTok", content_types=["script"],
                   max_length=0, category="social", is_export_only=True,
                   schedule_profile={"best_days": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
                                      "best_hours": list(range(14, 22)),
                                      "min_gap_hours": 6, "max_per_day": 2, "cadence": "daily"})
def tiktok_adapter(anchor: dict) -> dict:
    """Convert anchor into a TikTok script."""
    heading_hook = _extract_headings(anchor.get("article_html", ""))
    hook = heading_hook[0] if heading_hook else f"Stop buying the wrong {anchor.get('niche', 'product')}"
    return {
        "hook": f"🎯 {hook}",
        "body": "Here's what most people get wrong: they buy on price, not on fit.\n\nAfter testing 20+ options, here's the ONE that wins for most people.",
        "cta": f"Link in bio for the full breakdown. Follow for more {anchor.get('niche', 'product')} reviews.",
        "duration_seconds": 45,
    }


@registry.register("instagram", label="Instagram", content_types=["carousel"],
                   max_length=2200, category="social", is_export_only=True,
                   schedule_profile={"best_days": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
                                      "best_hours": list(range(9, 19)),
                                      "min_gap_hours": 12, "max_per_day": 1, "cadence": "daily"})
def instagram_adapter(anchor: dict) -> list[str]:
    """Convert anchor into Instagram carousel slides."""
    title = anchor.get("post_title", "New Post")
    headings = _extract_headings(anchor.get("article_html", ""))
    slides = [f"📌 {title}\n\nSwipe for the full breakdown →"]
    for h in headings[:5]:
        slides.append(f"{h}\n\nTap for details 👆")
    slides.append(f"Which one is YOUR pick? Drop it below 👇\n\nFull guide in bio 🔗")
    return slides


@registry.register("pinterest", label="Pinterest", content_types=["pin"],
                   max_length=500, category="social", is_export_only=True,
                   schedule_profile={"best_days": ["Saturday", "Sunday"],
                                      "best_hours": list(range(20, 24)),
                                      "min_gap_hours": 24, "max_per_day": 1, "cadence": "weekly"})
def pinterest_adapter(anchor: dict) -> dict:
    """Convert anchor into a Pinterest pin."""
    title = anchor.get("post_title", "New Post")
    description = anchor.get("meta_description", "")
    tags = ", ".join(anchor.get("tags", []))
    return {
        "title": title[:100],
        "description": f"{description[:300]}\n\n#affiliatemarketing #{tags.replace(' ', '').replace(',', ' #')[:200]}",
    }


@registry.register("medium", label="Medium", content_types=["article"],
                   max_length=5000, supports_html=True, category="social",
                   schedule_profile={"best_days": ["Monday","Tuesday","Wednesday","Thursday","Friday"],
                                      "best_hours": list(range(8, 15)),
                                      "min_gap_hours": 48, "max_per_day": 0, "cadence": "per_post"})
def medium_adapter(anchor: dict) -> str:
    """Convert anchor into a Medium article."""
    title = anchor.get("post_title", "New Post")
    intro = _clean_text(anchor.get("intro", ""))
    body = _clean_text(anchor.get("article_html", ""))
    return f"# {title}\n\n{intro}\n\n{body[:3000]}"


# ─── Future Platform Stubs ──────────────────────────────────────────

@registry.register("facebook", label="Facebook", content_types=["post", "link"],
                   max_length=63206, supports_html=False, category="social",
                   schedule_profile={"best_days": ["Tuesday","Wednesday","Thursday","Friday"],
                                      "best_hours": list(range(9, 15)),
                                      "min_gap_hours": 12, "max_per_day": 2, "cadence": "daily"})
def facebook_adapter(anchor: dict) -> dict:
    """Convert anchor into a Facebook post. Stub — ready for API integration."""
    title = anchor.get("post_title", "New Post")
    description = anchor.get("meta_description", "")
    return {
        "message": f"{title}\n\n{description}\n\nFull guide: [link]",
        "link": "[link]",
    }


@registry.register("youtube", label="YouTube", content_types=["video_script", "description"],
                   max_length=5000, supports_media=True, category="video", is_export_only=True,
                   schedule_profile={"best_days": ["Thursday","Friday","Saturday","Sunday"],
                                      "best_hours": list(range(10, 17)),
                                      "min_gap_hours": 72, "max_per_day": 1, "cadence": "weekly"})
def youtube_adapter(anchor: dict) -> dict:
    """Convert anchor into a YouTube script + description. Stub — ready for implementation."""
    title = anchor.get("post_title", "New Post")
    headings = _extract_headings(anchor.get("article_html", ""))
    return {
        "title": title,
        "script": f"INTRO: {anchor.get('intro', '')}\n\nMAIN: {' → '.join(headings[:5])}",
        "description": f"{anchor.get('meta_description', '')}\n\n🔗 Full guide: [link]\n#affiliatemarketing",
        "thumbnail_suggestions": ["comparison shot", "product hero", "before/after"],
    }