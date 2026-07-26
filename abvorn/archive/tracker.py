import re, logging
from datetime import datetime, timezone
from typing import Optional
logger = logging.getLogger("abvorn.archive.tracker")

class ContentFreshnessTracker:
    """Tracks and evaluates content freshness."""

    def __init__(self, state=None):
        self.state = state

    def check_freshness(self, content: dict, post_id: Optional[int] = None) -> dict:
        stale_sections = []
        deductions = 0
        article = content.get("article_html", "")

        price_matches = re.findall(r'\$\d+\.?\d*', article)
        has_prices = len(price_matches) > 0
        price_count = len(price_matches)

        date_matches = re.findall(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}', article)
        has_dates = len(date_matches) > 0
        date_count = len(date_matches)

        days_since_publish = 0
        if post_id and self.state:
            for niche_slug in [content.get("niche", "")]:
                posts = self.state.get_posts_for_niche(niche_slug)
                break
            for p in posts:
                if p["id"] == post_id:
                    created = datetime.fromisoformat(p["created_at"])
                    days_since_publish = (datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc)).days
                    break

        if price_count > 0 and days_since_publish > 14:
            stale_sections.append("prices")
            deductions += 20
        if date_count > 0 and days_since_publish > 30:
            stale_sections.append("dates")
            deductions += 15

        seo_score = content.get("seo_score", 0)
        has_seo_score = seo_score > 0
        if not has_seo_score or seo_score < 50:
            stale_sections.append("seo")
            deductions += 25

        if days_since_publish > 60:
            deductions += 20
            if "content" not in stale_sections:
                stale_sections.append("content")
        elif days_since_publish > 30:
            deductions += 10

        freshness_score = max(0, min(100, 100 - deductions))

        return {
            "freshness_score": freshness_score,
            "stale_sections": stale_sections,
            "has_prices": has_prices,
            "price_count": price_count,
            "has_dates": has_dates,
            "date_count": date_count,
            "has_seo_score": has_seo_score,
            "days_since_publish": days_since_publish,
            "needs_refresh": freshness_score < 60
        }

    def track_deployment(self, post_id: int, content: dict, niche: str):
        if not self.state:
            logger.warning("No state available for tracking deployment")
            return
        freshness = self.check_freshness(content, post_id)
        self.state.save_archive_snapshot(post_id, content, freshness["freshness_score"])
        logger.info(f"Tracked deployment for post {post_id} (freshness: {freshness['freshness_score']})")

    def get_stale_content(self, state=None, max_age_days: int = 30) -> list:
        s = state or self.state
        if not s:
            logger.warning("No state available for stale content query")
            return []
        snapshots = s.get_stale_snapshots(max_age_days)
        result = []
        for snap in snapshots:
            result.append({
                "post_id": snap["post_id"],
                "content": snap["content"],
                "freshness_score": snap["freshness_score"],
                "last_refreshed": snap.get("last_refreshed"),
                "days_stale": max_age_days
            })
        return result

    def get_freshness_report(self, state=None) -> dict:
        s = state or self.state
        if not s:
            return {"total": 0, "fresh": 0, "stale": 0, "average_freshness": 0}
        snapshots = s.get_all_archive_snapshots()
        if not snapshots:
            return {"total": 0, "fresh": 0, "stale": 0, "average_freshness": 0}
        total = len(snapshots)
        scores = [snap["freshness_score"] for snap in snapshots]
        fresh = sum(1 for sc in scores if sc >= 60)
        stale = total - fresh
        avg = sum(scores) / total if total > 0 else 0
        return {"total": total, "fresh": fresh, "stale": stale, "average_freshness": round(avg, 1)}
