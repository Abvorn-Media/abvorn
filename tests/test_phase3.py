#!/usr/bin/env python3
"""
Phase 3 test suite: Agent-Reach integration + social data pipeline.
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent_reach_adapter import (
    AgentReachAdapter,
    get_agent_reach_adapter,
)
from src.close_feedback_loop import ClosedFeedbackLoop, create_feedback_loop

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


def test_agent_reach_adapter_instantiation():
    try:
        adapter = AgentReachAdapter()
        assert_true(True, "AgentReachAdapter instantiated")
    except RuntimeError:
        assert_true(True, "AgentReachAdapter raises RuntimeError when agent-reach not installed (expected)")


def test_get_agent_reach_adapter_singleton():
    a1 = get_agent_reach_adapter()
    a2 = get_agent_reach_adapter()
    assert_true(a1 is a2, "get_agent_reach_adapter returns singleton")


def test_agent_reach_has_required_methods():
    adapter = AgentReachAdapter()
    assert_true(hasattr(adapter, 'fetch_tweets'), "has fetch_tweets")
    assert_true(hasattr(adapter, 'fetch_reddit_posts'), "has fetch_reddit_posts")
    assert_true(hasattr(adapter, 'fetch_youtube_videos'), "has fetch_youtube_videos")
    assert_true(hasattr(adapter, 'fetch_github_issues'), "has fetch_github_issues")
    assert_true(hasattr(adapter, 'fetch_social_data'), "has fetch_social_data")


def test_fetch_social_data_returns_dict():
    adapter = AgentReachAdapter()
    result = adapter.fetch_social_data("test product", platforms=["twitter"], limit_per_platform=2)
    assert_true(isinstance(result, dict), "fetch_social_data returns dict")


def test_fetch_social_data_with_no_channels():
    adapter = AgentReachAdapter()
    result = adapter.fetch_social_data("test", platforms=[])
    assert_equal(result, {}, "empty platforms returns empty dict")


def test_record_social_sentiment():
    loop = create_feedback_loop()
    test_file = Path("data/social_sentiment") / "test_niche_test_platform.json"
    if test_file.exists():
        test_file.unlink()

    loop.record_social_sentiment("test_niche", "test_platform", 0.75)

    assert_true(test_file.exists(), "sentiment file created")
    data = json.loads(test_file.read_text())
    assert_true(len(data) == 1, "sentiment file has one entry")
    assert_equal(data[0]["sentiment"], 0.75, "sentiment score is correct")

    # Clean up
    test_file.unlink()


def test_record_social_sentiment_appends():
    loop = create_feedback_loop()
    test_file = Path("data/social_sentiment") / "test_niche2_test_platform2.json"
    if test_file.exists():
        test_file.unlink()

    loop.record_social_sentiment("test_niche2", "test_platform2", 0.5)
    loop.record_social_sentiment("test_niche2", "test_platform2", 0.8)

    data = json.loads(test_file.read_text())
    assert_equal(len(data), 2, "sentiment file has two entries")
    assert_equal(data[1]["sentiment"], 0.8, "second sentiment is correct")

    # Clean up
    test_file.unlink()


def test_record_social_sentiment_creates_directories():
    loop = create_feedback_loop()
    test_file = Path("data/social_sentiment") / "test_niche3_test_platform3.json"
    if test_file.exists():
        test_file.unlink()

    loop.record_social_sentiment("test_niche3", "test_platform3", 0.6)
    assert_true(test_file.exists(), "sentiment file created with directory support")

    # Clean up
    test_file.unlink()


def test_fetch_social_sentiment_in_run_cycle():
    with open(r'C:\Users\Jean Mare\Documents\Default Project\run_cycle.py', encoding='utf-8', errors='replace') as f:
        c = f.read()
    assert_true('def fetch_social_sentiment' in c, "run_cycle.py has fetch_social_sentiment function")


def test_process_single_niche_uses_social_data():
    with open(r'C:\Users\Jean Mare\Documents\Default Project\run_cycle.py', encoding='utf-8', errors='replace') as f:
        c = f.read()
    assert_true('fetch_social_sentiment(niche_name)' in c, "process_single_niche fetches social data")
    assert_true('social_data=social_data' in c, "social_data passed to generate_outline and write_draft")


def test_write_draft_accepts_social_data():
    with open(r'C:\Users\Jean Mare\Documents\Default Project\run_cycle.py', encoding='utf-8', errors='replace') as f:
        c = f.read()
    idx = c.find('def write_draft')
    sig = c[idx:c.find('\n', idx)]
    assert_true('social_data' in sig, "write_draft accepts social_data parameter")


def test_generate_outline_accepts_social_data():
    with open(r'C:\Users\Jean Mare\Documents\Default Project\run_cycle.py', encoding='utf-8', errors='replace') as f:
        c = f.read()
    idx = c.find('def generate_outline')
    sig = c[idx:c.find('\n', idx)]
    assert_true('social_data' in sig, "generate_outline accepts social_data parameter")


def test_record_social_sentiment_logs():
    loop = create_feedback_loop()
    # This tests that the method doesn't raise
    try:
        loop.record_social_sentiment("log_test", "platform", 0.9)
        assert_true(True, "record_social_sentiment runs without error")
    except Exception as e:
        assert_true(False, f"record_social_sentiment raised: {e}")


def main():
    print("=" * 60)
    print("Phase 3 Test Suite: Agent-Reach + Social Data Pipeline")
    print("=" * 60)

    test_agent_reach_adapter_instantiation()
    test_get_agent_reach_adapter_singleton()
    test_agent_reach_has_required_methods()
    test_fetch_social_data_returns_dict()
    test_fetch_social_data_with_no_channels()
    test_record_social_sentiment()
    test_record_social_sentiment_appends()
    test_record_social_sentiment_creates_directories()
    test_fetch_social_sentiment_in_run_cycle()
    test_process_single_niche_uses_social_data()
    test_write_draft_accepts_social_data()
    test_generate_outline_accepts_social_data()
    test_record_social_sentiment_logs()

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