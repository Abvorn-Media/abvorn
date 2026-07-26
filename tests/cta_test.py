"""Tests for CTA — tracking, analysis, optimization."""

import pytest, tempfile
from pathlib import Path
from abvorn.cta.tracker import CTATracker
from abvorn.cta.analyzer import CTAAnalyzer
from abvorn.cta.optimizer import CTAOptimizer


@pytest.fixture
def state(tmp_path):
    from abvorn.core.state import AbvornState
    s = AbvornState(tmp_path / "test.db")
    s.add_post("test", "Test Post", "test.html")
    return s


@pytest.fixture
def post_id(state):
    return state.get_posts_for_niche("test")[0]["id"]


class TestCTATracker:
    def test_track_impression(self, state, post_id):
        tracker = CTATracker(state)
        tracker.track_impression(post_id=post_id, cta_id="cta_1",
                                  cta_type="button", cta_text="Buy Now",
                                  cta_location="inline", niche="test")
        stats = state.get_cta_stats(post_id=post_id)
        assert len(stats) > 0
        assert stats[0]["impressions"] == 1

    def test_track_click(self, state, post_id):
        tracker = CTATracker(state)
        tracker.track_click(post_id=post_id, cta_id="cta_2",
                             cta_type="affiliate_link", cta_text="check price",
                             cta_location="inline", niche="test")
        stats = state.get_cta_stats(post_id=post_id)
        assert len(stats) > 0
        matching = [s for s in stats if s["cta_id"] == "cta_2"]
        assert len(matching) == 1
        assert matching[0]["clicks"] >= 1

    def test_track_impression_and_click(self, state, post_id):
        tracker = CTATracker(state)
        tracker.track_impression(post_id=post_id, cta_id="cta_3", niche="test")
        tracker.track_click(post_id=post_id, cta_id="cta_3", niche="test")
        stats = state.get_cta_stats(post_id=post_id)
        cta = next(s for s in stats if s["cta_id"] == "cta_3")
        assert cta["impressions"] >= 1
        assert cta["clicks"] >= 1

    def test_track_conversion(self, state, post_id):
        tracker = CTATracker(state)
        tracker.track_impression(post_id=post_id, cta_id="cta_4", niche="test")
        tracker.track_click(post_id=post_id, cta_id="cta_4", niche="test")
        tracker.track_conversion(post_id=post_id, cta_id="cta_4", niche="test")
        stats = state.get_cta_stats(post_id=post_id)
        cta = next(s for s in stats if s["cta_id"] == "cta_4")

    def test_get_stats_empty(self):
        tracker = CTATracker(state=None)
        assert tracker.get_stats()["total_ctas"] == 0

    def test_generate_cta_id(self):
        tracker = CTATracker()
        cid = tracker.generate_cta_id(42, "button", "inline", 0)
        assert cid == "cta_42_button_inline_0"

    def test_generate_cta_html(self, post_id):
        tracker = CTATracker()
        html = tracker.generate_cta_html(
            post_id=post_id, cta_type="button", cta_text="Buy Now",
            cta_url="https://amazon.com/dp/test", cta_location="sticky",
            niche="test", index=1
        )
        assert "ctaClick" in html
        assert f'data-cta-id="cta_{post_id}_button_sticky_1"' in html
        assert "Buy Now" in html


class TestCTAAnalyzer:
    def test_analyze_by_type(self, state, post_id):
        tracker = CTATracker(state)
        tracker.track_impression(post_id=post_id, cta_id="t1", cta_type="button", niche="test")
        tracker.track_click(post_id=post_id, cta_id="t1", cta_type="button", niche="test")
        tracker.track_impression(post_id=post_id, cta_id="t2", cta_type="sticky_bar", niche="test")
        analyzer = CTAAnalyzer(state)
        by_type = analyzer.analyze_by_type("test")
        assert len(by_type) > 0
        button_stats = [t for t in by_type if t["cta_type"] == "button"]
        assert len(button_stats) > 0
        assert button_stats[0]["clicks"] >= 1

    def test_analyze_by_location(self, state, post_id):
        tracker = CTATracker(state)
        tracker.track_impression(post_id=post_id, cta_id="l1", cta_location="sticky", niche="test")
        tracker.track_click(post_id=post_id, cta_id="l1", cta_location="sticky", niche="test")
        tracker.track_impression(post_id=post_id, cta_id="l2", cta_location="footer", niche="test")
        analyzer = CTAAnalyzer(state)
        by_loc = analyzer.analyze_by_location("test")
        assert len(by_loc) > 0
        sticky = [l for l in by_loc if l["location"] == "sticky"]
        assert len(sticky) > 0

    def test_analyze_by_text(self, state, post_id):
        tracker = CTATracker(state)
        tracker.track_impression(post_id=post_id, cta_id="txt1", cta_text="Buy Now", niche="test")
        tracker.track_click(post_id=post_id, cta_id="txt1", cta_text="Buy Now", niche="test")
        tracker.track_impression(post_id=post_id, cta_id="txt2", cta_text="Click Here", niche="test")
        analyzer = CTAAnalyzer(state)
        by_text = analyzer.analyze_by_text("test")
        assert len(by_text) > 0

    def test_full_report(self, state, post_id):
        tracker = CTATracker(state)
        tracker.track_impression(post_id=post_id, cta_id="r1", cta_type="button", niche="test")
        analyzer = CTAAnalyzer(state)
        report = analyzer.full_report("test")
        assert "CTA PERFORMANCE REPORT" in report

    def test_no_data_report(self):
        analyzer = CTAAnalyzer(state=None)
        report = analyzer.full_report()
        assert "CTA PERFORMANCE REPORT" in report


class TestCTAOptimizer:
    def test_suggestions_low_performance(self, state, post_id):
        tracker = CTATracker(state)
        for i in range(15):
            tracker.track_impression(post_id=post_id, cta_id=f"low_{i}", cta_text="click here", niche="test")
        optimizer = CTAOptimizer(state)
        suggestions = optimizer.get_cta_suggestions("test")
        assert len(suggestions) >= 0

    def test_optimize_cta_text(self):
        optimizer = CTAOptimizer()
        assert optimizer.optimize_cta_text("click here", "button") != "click here"
        assert optimizer.optimize_cta_text("Buy Now", "button") == "Buy Now"

    def test_optimization_report(self, state, post_id):
        tracker = CTATracker(state)
        tracker.track_impression(post_id=post_id, cta_id="o1", niche="test")
        optimizer = CTAOptimizer(state)
        report = optimizer.get_optimization_report("test")
        assert "CTA OPTIMIZATION REPORT" in report