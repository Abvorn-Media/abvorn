"""Multi-format platform adapters — one anchor to every platform."""

import re


def _clean_text(html_text: str) -> str:
    return re.sub(r'<[^>]+>', '', html_text).strip()


def _extract_headings(html_text: str) -> list[str]:
    return re.findall(r'<h2>(.*?)</h2>', html_text, re.IGNORECASE)


def adapt_for_x(anchor: dict) -> list[str]:
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


def adapt_for_linkedin(anchor: dict) -> dict:
    """Convert anchor into a LinkedIn article."""
    title = anchor.get("post_title", "New Post")
    intro = _clean_text(anchor.get("intro", ""))
    body = _clean_text(anchor.get("article_html", ""))
    description = anchor.get("meta_description", "")
    article = f"# {title}\n\n{description}\n\n{intro}\n\n{body[:2000]}"
    post = f"{description}\n\nFull article: [link]\n\nWhat's your pick? 👇"
    return {"title": title, "body": article[:5000], "post": post[:1300]}


def adapt_for_tiktok(anchor: dict) -> dict:
    """Convert anchor into a TikTok script."""
    heading_hook = _extract_headings(anchor.get("article_html", ""))
    hook = heading_hook[0] if heading_hook else f"Stop buying the wrong {anchor.get('niche', 'product')}"
    return {
        "hook": f"🎯 {hook}",
        "body": "Here's what most people get wrong: they buy on price, not on fit.\n\nAfter testing 20+ options, here's the ONE that wins for most people.",
        "cta": f"Link in bio for the full breakdown. Follow for more {anchor.get('niche', 'product')} reviews.",
        "duration_seconds": 45,
    }


def adapt_for_instagram(anchor: dict) -> list[str]:
    """Convert anchor into Instagram carousel slides."""
    title = anchor.get("post_title", "New Post")
    headings = _extract_headings(anchor.get("article_html", ""))
    slides = [
        f"📌 {title}\n\nSwipe for the full breakdown →",
    ]
    for h in headings[:5]:
        slides.append(f"{h}\n\nTap for details 👆")
    slides.append(f"Which one is YOUR pick? Drop it below 👇\n\nFull guide in bio 🔗")
    return slides


def adapt_for_pinterest(anchor: dict) -> dict:
    """Convert anchor into a Pinterest pin."""
    title = anchor.get("post_title", "New Post")
    description = anchor.get("meta_description", "")
    tags = ", ".join(anchor.get("tags", []))
    return {
        "title": title[:100],
        "description": f"{description[:300]}\n\n#affiliatemarketing #{tags.replace(' ', '').replace(',', ' #')[:200]}",
    }


def adapt_for_medium(anchor: dict) -> str:
    """Convert anchor into a Medium article."""
    title = anchor.get("post_title", "New Post")
    intro = _clean_text(anchor.get("intro", ""))
    body = _clean_text(anchor.get("article_html", ""))
    return f"# {title}\n\n{intro}\n\n{body[:3000]}"