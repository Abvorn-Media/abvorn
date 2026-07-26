import logging
import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.state import AbvornState

logger = logging.getLogger("abvorn.seo.linking")


class InternalLinker:
    def __init__(self, state: "AbvornState | None" = None):
        self.state = state

    def suggest_links(self, content: dict, niche: str, max_links: int = 3) -> list[dict]:
        if not self.state:
            return []

        posts = self.state.get_posts_for_niche(niche)
        if not posts:
            return []

        current_title = content.get("post_title", "").lower()
        article_text = _strip_html(content.get("article_html", "")).lower()
        niche_words = set(niche.lower().split())

        scored = []
        for post in posts:
            post_title = post.get("title", "")
            if post_title.lower() == current_title:
                continue

            post_words = set(post_title.lower().split())
            overlap = niche_words & post_words
            word_ratio = len(overlap) / max(len(niche_words), 1) if niche_words else 0
            title_sim = SequenceMatcher(None, current_title, post_title.lower()).ratio()

            keyword_hits = sum(1 for w in post_words if w in article_text)
            keyword_ratio = min(keyword_hits / max(len(post_words), 1), 1.0)

            relevance = round((word_ratio * 0.3 + title_sim * 0.3 + keyword_ratio * 0.4), 2)

            if relevance > 0.1:
                slug = _make_slug(post_title)
                scored.append({
                    "text": post_title,
                    "url": f"/{slug}/",
                    "relevance": relevance,
                    "existing_post_title": post_title,
                })

        scored.sort(key=lambda x: x["relevance"], reverse=True)
        return scored[:max_links]

    def build_internal_links_html(self, content: dict, niche: str) -> str:
        links = self.suggest_links(content, niche)
        if not links:
            return ""

        items = "".join(
            f'<li><a href="{link["url"]}">{link["text"]}</a></li>'
            for link in links
        )
        return f'<div class="related-posts"><h3>Related Articles</h3><ul>{items}</ul></div>'


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _make_slug(title: str) -> str:
    slug = title.lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9-]", "", slug)[:80]
