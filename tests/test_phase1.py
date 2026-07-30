#!/usr/bin/env python3
"""
Phase 1 test suite: Entitlements enforcement + Social Permission + Nervous System wiring.
"""

import os
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.entitlements import EntitlementsFramework, Entitlement
from src.social_permission import (
    SocialPermissionFramework,
    create_social_permission_framework,
    THRESHOLDS,
)
from src.nervous_system import create_nervous_system

PASS_COUNT = 0
FAIL_COUNT = 0


def assert_true(condition, msg):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  PASS: {msg}")
    else:
        FAIL_COUNT += 1
        print(f"  FAIL: {msg}")


def assert_false(condition, msg):
    assert_true(not condition, msg)


def assert_equal(actual, expected, msg):
    assert_true(actual == expected, f"{msg} (got {actual!r}, expected {expected!r})")


def test_entitlements_system_and_admin_always_allowed():
    ef = EntitlementsFramework()
    assert_true(ef.check("system", "publish", "content") is True,
                "system user can publish")
    assert_true(ef.check("admin", "delete", "content") is True,
                "admin user can delete")
    assert_true(ef.check("system", "anything", "any") is True,
                "system user can do anything")
    assert_true(ef.check("admin", "unknown_action", "resource") is True,
                "admin user can do unknown actions")


def test_entitlements_unknown_user_denied():
    ef = EntitlementsFramework()
    result = ef.check("unknown_user", "publish", "content")
    assert_false(result, "unknown user denied publish")


def test_entitlements_grant_permission():
    ef = EntitlementsFramework()
    ef.grant("editor", "publish")
    assert_true(ef.check("editor", "publish", "content"),
                "granted user can publish")
    assert_false(ef.check("editor", "delete", "content"),
                 "granted user cannot delete without grant")


def test_entitlements_revoke_permission():
    ef = EntitlementsFramework()
    ef.revoke("admin", "publish")
    assert_true(ef.check("admin", "publish", "content"),
                "admin still allowed after revoke (admin bypass)")


def test_entitlements_audit_log_populated():
    ef = EntitlementsFramework()
    ef.check("test_user", "publish", "content")
    assert_true(len(ef.audit_log) > 0, "audit log has entries")
    last = ef.audit_log[-1]
    assert_equal(last["type"], "check", "last audit entry is a check")
    assert_equal(last["user"], "test_user", "audit entry has correct user")
    assert_equal(last["action"], "publish", "audit entry has correct action")
    assert_equal(last["resource"], "content", "audit entry has correct resource")


def test_entitlements_audit_file_created():
    ef = EntitlementsFramework()
    ef.check("file_test_user", "publish", "content")
    audit_path = Path("data/audit.log")
    assert_true(audit_path.exists(), "data/audit.log exists")
    content = audit_path.read_text(encoding="utf-8")
    assert_true("file_test_user" in content, "audit log contains user")
    assert_true("publish" in content, "audit log contains action")


def test_social_permission_framework_accepts_nervous_system():
    ns = create_nervous_system()
    sp = create_social_permission_framework(nervous_system=ns)
    assert_true(sp.nervous_system is ns,
                "SocialPermissionFramework stores nervous_system reference")


def test_social_permission_without_nervous_system():
    sp = create_social_permission_framework(nervous_system=None)
    report = sp.act(0.5, metrics={})
    assert_equal(report["level"], "caution",
                 "score 0.5 maps to caution level")


def test_social_permission_action_mapping():
    ns = create_nervous_system()
    sp = create_social_permission_framework(nervous_system=ns)
    report = sp.act(0.15, metrics={})
    assert_equal(report["level"], "critical",
                 "score 0.15 maps to critical level")
    critical_actions = [a for a in report["actions"] if a.get("auto_execute")]
    assert_true(len(critical_actions) > 0,
                "critical level has auto-execute actions")


def test_social_permission_level_thresholds():
    assert_equal(THRESHOLDS.get_level(0.9), "global", "0.9 -> global")
    assert_equal(THRESHOLDS.get_level(0.75), "country", "0.75 -> country")
    assert_equal(THRESHOLDS.get_level(0.5), "caution", "0.5 -> caution")
    assert_equal(THRESHOLDS.get_level(0.15), "critical", "0.15 -> critical")
    assert_equal(THRESHOLDS.get_level(0.1), "critical", "0.1 -> critical")


def test_nervous_system_stub_methods():
    ns = create_nervous_system()
    ns.pause_low_performing_niches()
    ns.pause_expansion()
    ns.scale_infrastructure()
    ns.expand_niches()
    ns.add_features()
    ns.increase_frequency()
    ns.refine_content()
    ns.optimize_providers()
    assert_true(True, "All NervousSystem stub methods callable without error")


def test_social_permission_metrics_passed_through():
    ns = create_nervous_system()
    sp = create_social_permission_framework(nervous_system=ns)
    metrics = {
        "economic_surplus": 0.25,
        "user_engagement": 0.3,
        "trust_score": 0.4,
    }
    report = sp.act(0.45, metrics=metrics)
    assert_equal(report.get("metrics"), metrics,
                 "metrics passed through to report")


def main():
    print("=" * 60)
    print("Phase 1 Test Suite: Entitlements + Social Permission + Nervous System")
    print("=" * 60)

    test_entitlements_system_and_admin_always_allowed()
    test_entitlements_unknown_user_denied()
    test_entitlements_grant_permission()
    test_entitlements_revoke_permission()
    test_entitlements_audit_log_populated()
    test_entitlements_audit_file_created()
    test_social_permission_framework_accepts_nervous_system()
    test_social_permission_without_nervous_system()
    test_social_permission_action_mapping()
    test_social_permission_level_thresholds()
    test_nervous_system_stub_methods()
    test_social_permission_metrics_passed_through()

    print()
    print("=" * 60)
    total = PASS_COUNT + FAIL_COUNT
    print(f"Results: {PASS_COUNT} passed, {FAIL_COUNT} failed out of {total}")
    if FAIL_COUNT == 0:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)
    return FAIL_COUNT == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)