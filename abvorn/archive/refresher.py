import logging, re
from datetime import datetime, timezone
from typing import Optional, List
logger = logging.getLogger("abvorn.archive.refresher")

class ContentRefresher:
    """Regenerates stale sections of content while preserving fresh parts."""

    def __init__(self, router=None):
        self.router = router

    def refresh_prices(self, content: dict) -> dict:
        article = content.get("article_html", "")
        prices = re.findall(r'(\$\d+\.?\d*)', article)
        return {
            "content": content,
            "prices_found": len(prices),
            "prices_flagged": [p for p in prices],
            "notes": [f"Flagged {len(prices)} prices for verification"]
        }

    def refresh_rankings(self, content: dict) -> dict:
        article = content.get("article_html", "")
        ranking_markers = re.findall(r'(best|top|#1|number one|leading|premier)', article, re.IGNORECASE)
        return {
            "content": content,
            "ranking_markers_found": len(ranking_markers),
            "notes": [f"Found {len(ranking_markers)} ranking claims that may need re-evaluation"]
        }

    def refresh_meta(self, content: dict) -> dict:
        updated = dict(content)
        title = updated.get("post_title", "")
        meta = updated.get("meta_description", "")
        if meta and title and title.lower() in meta.lower():
            updated["meta_description"] = f"Looking for the best {content.get('niche', 'products')}? Our expert guide covers everything you need to know."
        return updated

    def refresh_schema(self, content: dict, seo_pipeline=None) -> dict:
        if seo_pipeline and hasattr(seo_pipeline, 'schema_builder'):
            try:
                schema = seo_pipeline.schema_builder.build(content.get("post_title", ""), content.get("article_html", ""))
                if schema:
                    content["schema"] = schema
            except Exception as e:
                logger.warning(f"Schema refresh failed: {e}")
        return content

    def regenerate_content(self, content: dict, niche: str, router=None, sections: Optional[List[str]] = None) -> dict:
        r = router or self.router
        if not r:
            logger.warning("No router available for content regeneration")
            return content

        updated = dict(content)
        changes = []

        if sections is None or "meta" in sections:
            meta_result = self.refresh_meta(updated)
            updated["meta_description"] = meta_result.get("meta_description", updated.get("meta_description", ""))
            changes.append("meta")

        if sections is None or "schema" in sections:
            updated = self.refresh_schema(updated)
            changes.append("schema")

        if sections is None:
            changes.append("full_content")

        updated["_refresh_changes"] = changes
        updated["_refreshed_at"] = datetime.now(timezone.utc).isoformat()
        return updated
