import logging
from typing import Optional
from datetime import datetime
from .tracker import ContentFreshnessTracker
from .refresher import ContentRefresher
logger = logging.getLogger("abvorn.archive.living")

class LivingArchiver:
    """Orchestrates the living document lifecycle."""

    def __init__(self, state=None, router=None, seo_pipeline=None, humanizer=None):
        self.state = state
        self.tracker = ContentFreshnessTracker(state)
        self.refresher = ContentRefresher(router)
        self.seo_pipeline = seo_pipeline
        self.humanizer = humanizer

    def archive_content(self, content: dict, post_id: int):
        if not self.state:
            logger.warning("No state — cannot archive content")
            return
        freshness = self.tracker.check_freshness(content, post_id)
        self.state.save_archive_snapshot(post_id, content, freshness["freshness_score"])
        logger.info(f"Archived post {post_id} with freshness {freshness['freshness_score']}")

    def refresh_post(self, state=None, post_id: int = None) -> dict:
        s = state or self.state
        if not s:
            return {"status": "error", "error": "No state available"}

        snapshot = s.get_archive_snapshot(post_id)
        if not snapshot:
            return {"status": "not_found"}

        content = snapshot["content"]
        freshness = self.tracker.check_freshness(content, post_id)

        if not freshness["needs_refresh"]:
            return {"status": "fresh", "freshness_score": freshness["freshness_score"]}

        stale = freshness["stale_sections"]
        sections_to_refresh = []
        if "prices" in stale:
            sections_to_refresh.append("prices")
        if "seo" in stale:
            sections_to_refresh.append("meta")
            sections_to_refresh.append("schema")

        updated = self.refresher.regenerate_content(
            content,
            niche=content.get("niche", ""),
            sections=sections_to_refresh if sections_to_refresh else None
        )

        changes = updated.get("_refresh_changes", ["unknown"])

        if self.seo_pipeline and ("seo" in stale or "meta" in stale):
            try:
                score = self.seo_pipeline.score_content(updated)
                updated["seo_score"] = score
                if score > snapshot.get("freshness_score", 0):
                    changes.append("seo_improved")
            except Exception as e:
                logger.warning(f"SEO re-score failed: {e}")

        if self.humanizer and ("content" in stale):
            try:
                result = self.humanizer.humanize(updated.get("article_html", ""))
                if result.get("humanized"):
                    updated["article_html"] = result["humanized"]
                    changes.append("rehumanized")
            except Exception as e:
                logger.warning(f"Re-humanize failed: {e}")

        new_freshness = self.tracker.check_freshness(updated, post_id)
        self.state.save_archive_snapshot(post_id, updated, new_freshness["freshness_score"])
        self.state.log_archive_refresh(post_id, "full" if not sections_to_refresh else "partial", changes, new_freshness["freshness_score"])

        return {
            "status": "refreshed",
            "changes": changes,
            "old_freshness": freshness["freshness_score"],
            "new_freshness": new_freshness["freshness_score"]
        }

    def refresh_all_stale(self, state=None, age_days: int = 30) -> list:
        s = state or self.state
        if not s:
            logger.warning("No state — cannot refresh stale content")
            return []
        stale = self.tracker.get_stale_content(s, age_days)
        results = []
        for item in stale:
            result = self.refresh_post(state=s, post_id=item["post_id"])
            results.append({"post_id": item["post_id"], "result": result})
            logger.info(f"Refreshed post {item['post_id']}: {result['status']}")
        return results

    def get_archive_report(self, state=None) -> dict:
        s = state or self.state
        freshness = self.tracker.get_freshness_report(s)
        if not s:
            return {"freshness": freshness, "recent_refreshes": []}
        try:
            snapshots = s.get_all_archive_snapshots()
            recent = []
            for snap in snapshots[:5]:
                history = s.get_refresh_history(snap["post_id"], limit=3)
                recent.extend(history)
        except Exception:
            recent = []
        return {
            "freshness": freshness,
            "recent_refreshes": recent[:10] if recent else [],
            "needs_attention": [snap for snap in (s.get_all_archive_snapshots() if s else []) if snap["freshness_score"] < 40][:5]
        }
