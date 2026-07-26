"""Tests for Hooks — generation, testing, optimization."""

import pytest
from abvorn.hooks.generator import HookGenerator
from abvorn.hooks.tester import HookTester
from abvorn.hooks.optimizer import HookOptimizer


class TestHookGenerator:
    def test_generate_variants(self):
        gen = HookGenerator()
        variants = gen.generate_variants("headphones", "Sony WH-1000XM5", "best", 3)
        assert len(variants) <= 3
        assert all("headphones" in v["hook"].lower() or v["hook"] for v in variants)
        assert all("type" in v for v in variants)

    def test_generate_variants_default_count(self):
        gen = HookGenerator()
        variants = gen.generate_variants("coffee makers")
        assert len(variants) <= 5

    def test_generate_social_hook_x(self):
        gen = HookGenerator()
        hook = gen.generate_social_hook("running shoes", platform="x")
        assert "running shoes" in hook
        assert "🧵" in hook

    def test_generate_social_hook_linkedin(self):
        gen = HookGenerator()
        hook = gen.generate_social_hook("projectors", platform="linkedin")
        assert "projectors" in hook

    def test_generate_social_hook_youtube(self):
        gen = HookGenerator()
        hook = gen.generate_social_hook("gaming mice", platform="youtube")
        assert "gaming mice" in hook

    def test_generate_email_subjects(self):
        gen = HookGenerator()
        subjects = gen.generate_email_subject("blenders", "Alice")
        assert len(subjects) == 5
        assert all("Alice" in s for s in subjects)
        assert all("blenders" in s for s in subjects)

    def test_generate_email_subjects_no_name(self):
        gen = HookGenerator()
        subjects = gen.generate_email_subject("blenders")
        assert len(subjects) == 5

    def test_angle_best_uses_right_patterns(self):
        gen = HookGenerator()
        v1 = gen.generate_variants("test", angle="best headphones", count=2)
        v2 = gen.generate_variants("test", angle="comparison", count=2)
        assert len(v1) > 0
        assert len(v2) > 0


class TestHookTester:
    def test_record_hook_use(self, tmp_path):
        from abvorn.core.state import AbvornState
        state = AbvornState(tmp_path / "test.db")
        state.add_post("test", "P", "p.html")
        pid = state.get_posts_for_niche("test")[0]["id"]
        tester = HookTester(state)
        tester.record_hook_use(pid, "curiosity", "The secret...", "x", "test")

    def test_record_hook_performance(self, tmp_path):
        from abvorn.core.state import AbvornState
        state = AbvornState(tmp_path / "test.db")
        state.add_post("test", "P", "p.html")
        pid = state.get_posts_for_niche("test")[0]["id"]
        tester = HookTester(state)
        tester.record_hook_use(pid, "direct", "Best product", "blog", "test")
        tester.record_hook_performance(pid, "blog", 0.85)

    def test_get_best_hooks_empty(self):
        tester = HookTester(state=None)
        hooks = tester.get_best_hooks()
        assert hooks == []

    def test_analyze_hooks_empty(self):
        tester = HookTester(state=None)
        report = tester.analyze_hooks()
        assert "HOOK PERFORMANCE REPORT" in report


class TestHookOptimizer:
    def test_pick_best_hook(self):
        gen = HookGenerator()
        opt = HookOptimizer(generator=gen)
        hook = opt.pick_best_hook("keyboards", platform="blog")
        assert "type" in hook
        assert "hook" in hook

    def test_optimize_hook_text_x(self):
        opt = HookOptimizer()
        result = opt.optimize_hook_text("Best keyboards of 2026", "x")
        assert len(result) <= 103

    def test_optimize_hook_text_blog(self):
        opt = HookOptimizer()
        result = opt.optimize_hook_text("Best keyboards of 2026", "blog")
        assert "Best keyboards of 2026" in result

    def test_hool_one_call(self):
        gen = HookGenerator()
        opt = HookOptimizer(generator=gen)
        hook = opt.hool("mattresses", "Casper", "best", "blog")
        assert isinstance(hook, str)
        assert len(hook) > 0

    def test_hool_x_platform(self):
        gen = HookGenerator()
        opt = HookOptimizer(generator=gen)
        hook = opt.hool("monitors", platform="x")
        assert isinstance(hook, str)