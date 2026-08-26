"""Tests for the entitlements system and reflection feedback loop."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestEntitlements:
    def test_read_actions_auto_approved(self):
        from abvorn.core.entitlements import Entitlements, Permission

        e = Entitlements()
        result = e.check("query_brain", agent="test_agent")
        assert result["allowed"] is True
        assert result["requires_approval"] is False

    def test_write_actions_auto_approved(self):
        from abvorn.core.entitlements import Entitlements

        e = Entitlements()
        result = e.check("generate_content", agent="test_agent")
        assert result["allowed"] is True

    def test_deploy_requires_approval(self):
        from abvorn.core.entitlements import Entitlements

        with tempfile.TemporaryDirectory() as tmp:
            with patch("abvorn.core.entitlements.ENTITLEMENTS_FILE",
                       Path(tmp) / "entitlements.json"):
                e = Entitlements()
                result = e.check("deploy_to_github", agent="test_agent")
                assert result["allowed"] is False
                assert result["requires_approval"] is True
                assert len(e.get_pending()) == 1

    def test_terminate_requires_approval(self):
        from abvorn.core.entitlements import Entitlements

        with tempfile.TemporaryDirectory() as tmp:
            with patch("abvorn.core.entitlements.ENTITLEMENTS_FILE",
                       Path(tmp) / "entitlements.json"):
                e = Entitlements()
                result = e.check("spawn_child", agent="genesis_protocol")
                assert result["allowed"] is False
                assert result["permission_level"] == "TERMINATE"

    def test_approve_deny_cycle(self):
        from abvorn.core.entitlements import Entitlements

        with tempfile.TemporaryDirectory() as tmp:
            with patch("abvorn.core.entitlements.ENTITLEMENTS_FILE",
                       Path(tmp) / "entitlements.json"):
                e = Entitlements()
                e.check("deploy_to_github", agent="test")
                assert len(e.get_pending()) == 1

                assert e.approve(0) is True
                assert len(e.get_pending()) == 0
                assert len(e.get_audit_log()) == 1
                assert e.get_audit_log()[0]["status"] == "approved"

    def test_unknown_action_defaults_to_read(self):
        from abvorn.core.entitlements import Entitlements

        e = Entitlements()
        result = e.check("some_unknown_action", agent="test")
        assert result["allowed"] is True


class TestReflectionFeedbackLoop:
    def test_reflection_store_has_get_learnings(self):
        from abvorn.core.reflection import ReflectionStore

        store = ReflectionStore()
        # Should return empty list without crashing
        learnings = store.get_learnings_for_niche("wireless-headphones", limit=3)
        assert isinstance(learnings, list)

    def test_surplus_metrics_returns_dict(self):
        from abvorn.core.reflection import ReflectionStore

        store = ReflectionStore()
        metrics = store.get_surplus_metrics()
        assert isinstance(metrics, dict)
        assert "status" in metrics

    def test_pipeline_loads_reflection_learnings(self):
        from abvorn.content.pipeline import _load_reflection_learnings

        # Should not crash even with no reflections
        learnings = _load_reflection_learnings("test-niche")
        assert isinstance(learnings, list)
