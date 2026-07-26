import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, PropertyMock

from abvorn.archive.tracker import ContentFreshnessTracker
from abvorn.archive.refresher import ContentRefresher
from abvorn.archive.living import LivingArchiver


class MockState:
    """Dict-based mock for AbvornState archive methods."""

    def __init__(self):
        self.snapshots = {}
        self.refresh_logs = []
        self.posts = []

    def get_posts_for_niche(self, niche_slug):
        return self.posts

    def save_archive_snapshot(self, post_id, content, freshness_score):
        self.snapshots[post_id] = {
            "post_id": post_id,
            "content": content,
            "freshness_score": freshness_score,
            "last_refreshed": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    def get_archive_snapshot(self, post_id):
        return self.snapshots.get(post_id)

    def log_archive_refresh(self, post_id, refresh_type, changes, new_freshness):
        self.refresh_logs.append({
            "post_id": post_id,
            "refresh_type": refresh_type,
            "changes_json": changes,
            "new_freshness": new_freshness,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    def get_refresh_history(self, post_id, limit=10):
        return [log for log in self.refresh_logs if log["post_id"] == post_id][:limit]

    def get_all_archive_snapshots(self):
        return list(self.snapshots.values())

    def get_stale_snapshots(self, max_days=30):
        return [
            s for s in self.snapshots.values()
            if s["last_refreshed"] is None
        ]


FRESH_CONTENT = {
    "post_title": "Best Gadgets of 2026",
    "meta_description": "Our expert guide to the best gadgets this year.",
    "article_html": "<p>These gadgets are amazing and priced at $29.</p>",
    "seo_score": 85,
    "niche": "gadgets",
}

STALE_DATE_CONTENT = {
    "post_title": "Old Gadgets Review",
    "meta_description": "Review of gadgets from last year.",
    "article_html": "<p>We reviewed these on 01/15/2025 and 03/20/2025. Prices start at $49.</p>",
    "seo_score": 75,
    "niche": "gadgets",
}

NO_SEO_CONTENT = {
    "post_title": "SEO-free Article",
    "meta_description": "",
    "article_html": "<p>Just some text with no prices or dates.</p>",
    "niche": "gadgets",
}


class TestFreshnessTrackerNewContent:
    def test_freshness_tracker_new_content(self):
        tracker = ContentFreshnessTracker()
        result = tracker.check_freshness(FRESH_CONTENT)
        assert result["freshness_score"] == 100
        assert result["needs_refresh"] is False
        assert result["stale_sections"] == []
        assert result["has_prices"] is True
        assert result["has_dates"] is False
        assert result["has_seo_score"] is True

    def test_freshness_tracker_stale_dates(self):
        state = MockState()
        state.posts = [{"id": 1, "created_at": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()}]
        tracker = ContentFreshnessTracker(state)
        result = tracker.check_freshness(STALE_DATE_CONTENT, post_id=1)
        assert result["has_dates"] is True
        assert result["date_count"] >= 2
        assert "dates" in result["stale_sections"]
        assert result["freshness_score"] < 100
        assert result["needs_refresh"] is True

    def test_freshness_tracker_no_seo(self):
        tracker = ContentFreshnessTracker()
        result = tracker.check_freshness(NO_SEO_CONTENT)
        assert result["has_seo_score"] is False
        assert "seo" in result["stale_sections"]
        assert result["freshness_score"] == 75
        assert result["freshness_score"] < 100

    def test_freshness_tracker_needs_refresh(self):
        state = MockState()
        state.posts = [{"id": 1, "created_at": (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()}]
        tracker = ContentFreshnessTracker(state)
        result = tracker.check_freshness(STALE_DATE_CONTENT, post_id=1)
        assert result["needs_refresh"] is True
        assert result["freshness_score"] < 60

    def test_track_deployment(self):
        state = MockState()
        tracker = ContentFreshnessTracker(state)
        tracker.track_deployment(1, FRESH_CONTENT, "gadgets")
        assert 1 in state.snapshots
        assert state.snapshots[1]["freshness_score"] == 100

    def test_get_stale_content(self):
        state = MockState()
        state.snapshots[1] = {
            "post_id": 1, "content": FRESH_CONTENT, "freshness_score": 100,
            "last_refreshed": None, "created_at": datetime.now(timezone.utc).isoformat()
        }
        tracker = ContentFreshnessTracker(state)
        stale = tracker.get_stale_content(max_age_days=30)
        assert len(stale) == 1
        assert stale[0]["post_id"] == 1

    def test_get_freshness_report(self):
        state = MockState()
        state.snapshots[1] = {
            "post_id": 1, "content": FRESH_CONTENT, "freshness_score": 100,
            "last_refreshed": None, "created_at": datetime.now(timezone.utc).isoformat()
        }
        state.snapshots[2] = {
            "post_id": 2, "content": NO_SEO_CONTENT, "freshness_score": 50,
            "last_refreshed": None, "created_at": datetime.now(timezone.utc).isoformat()
        }
        tracker = ContentFreshnessTracker(state)
        report = tracker.get_freshness_report()
        assert report["total"] == 2
        assert report["fresh"] == 1
        assert report["stale"] == 1
        assert report["average_freshness"] == 75.0


class TestContentRefresher:
    def test_refresher_prices(self):
        refresher = ContentRefresher()
        content = {"article_html": "<p>Only $29.99 and $49 for this item.</p>"}
        result = refresher.refresh_prices(content)
        assert result["prices_found"] == 2
        assert "$29.99" in result["prices_flagged"]
        assert "$49" in result["prices_flagged"]

    def test_refresher_rankings(self):
        refresher = ContentRefresher()
        content = {"article_html": "<p>The best product is #1 on our list.</p>"}
        result = refresher.refresh_rankings(content)
        assert result["ranking_markers_found"] >= 2

    def test_refresher_meta(self):
        refresher = ContentRefresher()
        content = {
            "post_title": "Best Gadgets",
            "meta_description": "Best Gadgets guide for you",
            "niche": "gadgets"
        }
        result = refresher.refresh_meta(content)
        assert "Best Gadgets" not in result["meta_description"]

    def test_refresher_meta_no_change(self):
        refresher = ContentRefresher()
        content = {
            "post_title": "Best Gadgets",
            "meta_description": "A completely different description that does not repeat the title.",
            "niche": "gadgets"
        }
        result = refresher.refresh_meta(content)
        assert result["meta_description"] == content["meta_description"]


class TestLivingArchiver:
    def test_living_archiver_archive_content(self):
        state = MockState()
        archiver = LivingArchiver(state=state)
        archiver.archive_content(FRESH_CONTENT, 1)
        assert 1 in state.snapshots
        assert state.snapshots[1]["freshness_score"] == 100

    def test_living_archiver_refresh_fresh(self):
        state = MockState()
        state.snapshots[1] = {
            "post_id": 1, "content": FRESH_CONTENT, "freshness_score": 100,
            "last_refreshed": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        archiver = LivingArchiver(state=state)
        result = archiver.refresh_post(post_id=1)
        assert result["status"] == "fresh"

    def test_living_archiver_refresh_stale(self):
        state = MockState()
        stale = dict(STALE_DATE_CONTENT)
        stale["post_title"] = "Stale Post"
        stale["meta_description"] = "Old meta description that includes the post_title."
        state.posts = [{"id": 1, "created_at": (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()}]
        state.snapshots[1] = {
            "post_id": 1, "content": stale, "freshness_score": 30,
            "last_refreshed": None, "created_at": (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        }
        archiver = LivingArchiver(state=state)
        result = archiver.refresh_post(post_id=1)
        assert result["status"] == "refreshed"
        assert "changes" in result

    def test_living_archiver_not_found(self):
        state = MockState()
        archiver = LivingArchiver(state=state)
        result = archiver.refresh_post(post_id=999)
        assert result["status"] == "not_found"

    def test_living_archiver_no_state(self):
        archiver = LivingArchiver(state=None)
        result = archiver.refresh_post(post_id=1)
        assert result["status"] == "error"

    def test_living_archiver_get_report(self):
        state = MockState()
        state.snapshots[1] = {
            "post_id": 1, "content": FRESH_CONTENT, "freshness_score": 100,
            "last_refreshed": None, "created_at": datetime.now(timezone.utc).isoformat()
        }
        archiver = LivingArchiver(state=state)
        report = archiver.get_archive_report()
        assert "freshness" in report
        assert "recent_refreshes" in report
        assert "needs_attention" in report
        assert report["freshness"]["total"] == 1

    def test_refresh_all_stale(self):
        state = MockState()
        stale = dict(STALE_DATE_CONTENT)
        stale["post_title"] = "Refresh Me"
        stale["meta_description"] = "Refresh me description with the post_title repeating."
        state.posts = [{"id": 1, "created_at": (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()}]
        state.snapshots[1] = {
            "post_id": 1, "content": stale, "freshness_score": 30,
            "last_refreshed": None, "created_at": (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        }
        archiver = LivingArchiver(state=state)
        results = archiver.refresh_all_stale(age_days=30)
        assert len(results) == 1
        assert results[0]["post_id"] == 1
        assert results[0]["result"]["status"] == "refreshed"
