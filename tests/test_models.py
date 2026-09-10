"""Tests for cost-aware model routing."""
import time
import pytest
from unittest.mock import MagicMock


def test_task_model_mapping():
    from abvorn.core.models import TASK_MODELS
    assert "research" in TASK_MODELS
    assert "draft" in TASK_MODELS
    assert TASK_MODELS["research"] == "haiku"
    assert TASK_MODELS["draft"] == "sonnet"


def test_cost_tracker_initializes():
    from abvorn.core.models import ModelCostTracker
    t = ModelCostTracker()
    assert t is not None
    assert t.session_calls == []


def test_cost_tracker_record_call():
    from abvorn.core.models import ModelCostTracker
    t = ModelCostTracker()
    t.record_call("qwen", "haiku", "research", 150, 1200, True)
    assert len(t.session_calls) == 1


def test_cost_tracker_stats():
    from abvorn.core.models import ModelCostTracker
    t = ModelCostTracker()
    t.record_call("qwen", "haiku", "research", 200, 1000, True)
    t.record_call("deepseek", "sonnet", "draft", 500, 5000, True)
    stats = t.get_stats()
    assert stats["total_calls"] == 2
    assert stats["total_tokens"] == 700
    assert stats["estimated_cost_usd"] > 0


def test_cost_tracker_empty_stats():
    from abvorn.core.models import ModelCostTracker
    t = ModelCostTracker()
    stats = t.get_stats()
    assert stats["total_calls"] == 0


def test_retry_on_transient_error():
    from abvorn.core.models import AIProvider
    provider = AIProvider("test", "sk-test-key", model="gpt-4o")
    provider.client = MagicMock()
    import openai
    mock_resp = MagicMock(status_code=429)
    provider.client.chat.completions.create.side_effect = [
        openai.APIStatusError("rate limit", response=mock_resp, body={}),
        openai.APIStatusError("rate limit", response=mock_resp, body={}),
        MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))], usage=MagicMock(total_tokens=10)),
    ]
    result, meta = provider.call_with_metadata([{"role": "user", "content": "hi"}])
    assert result == "ok"
    assert provider.failures == 0


def test_auth_error_fails_fast():
    from abvorn.core.models import AIProvider
    provider = AIProvider("test", "sk-test-key", model="gpt-4o")
    provider.client = MagicMock()
    import openai
    provider.client.chat.completions.create.side_effect = openai.AuthenticationError(
        "401 auth failed", response=MagicMock(status_code=401), body={}
    )
    with pytest.raises(openai.AuthenticationError):
        provider.call_with_metadata([{"role": "user", "content": "hi"}])
    assert provider.client.chat.completions.create.call_count == 1


def test_ask_task_routing():
    from abvorn.core.models import ModelRouter, AIProvider
    router = ModelRouter.__new__(ModelRouter)
    router.providers = [
        AIProvider("qwen", "key", "http://fake", "qwen3.5-flash"),
        AIProvider("deepseek", "key", "http://fake", "deepseek-chat"),
    ]
    for p in router.providers:
        p.client = MagicMock()
        p.client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="result"))],
            usage=MagicMock(total_tokens=10),
        )
    result = router.ask("test prompt", task="research")
    assert result == "result"


def test_ban_fallback():
    from abvorn.core.models import ModelRouter, AIProvider
    router = ModelRouter.__new__(ModelRouter)
    a = AIProvider("qwen", "key", "http://fake", "qwen3.5-flash")
    a.client = MagicMock()
    a.client.chat.completions.create.side_effect = RuntimeError("fail")
    b = AIProvider("deepseek", "key", "http://fake", "deepseek-chat")
    b.client = MagicMock()
    b.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="fallback_ok"))],
        usage=MagicMock(total_tokens=10),
    )
    router.providers = [a, b]
    result = router.ask("test prompt", task="draft")
    assert result == "fallback_ok"


def test_call_wraps_call_with_metadata():
    from abvorn.core.models import AIProvider
    provider = AIProvider("test", "sk-test-key", model="gpt-4o")
    provider.client = MagicMock()
    provider.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="simple"))],
        usage=MagicMock(total_tokens=5),
    )
    result = provider.call([{"role": "user", "content": "hi"}])
    assert result == "simple"


def test_mark_error_ban_durations():
    from abvorn.core.models import AIProvider
    p = AIProvider("test", "sk-test-key", model="gpt-4o")
    p.mark_error(RuntimeError("Error code: 401 - auth"))
    assert p._banned_until - time.time() > 12 * 3600 - 5

    p = AIProvider("test2", "sk-test-key", model="gpt-4o")
    p.mark_error(RuntimeError("Error code: 402 - payment"))
    assert p._banned_until - time.time() > 12 * 3600 - 5

    p = AIProvider("test3", "sk-test-key", model="gpt-4o")
    p.mark_error(RuntimeError("Error code: 429 - rate limit"))
    assert 500 <= p._banned_until - time.time() <= 700

    p = AIProvider("test4", "sk-test-key", model="gpt-4o")
    p.mark_error(RuntimeError("Error code: 500 - server"))
    assert p._banned_until - time.time() <= 120


def test_probe_marks_dead_provider():
    from abvorn.core.models import ModelRouter, AIProvider
    router = ModelRouter.__new__(ModelRouter)
    a = AIProvider("qwen", "key", "http://fake", "qwen3.5-flash")
    a.client = MagicMock()
    a.client.chat.completions.create.side_effect = RuntimeError("boom")
    b = AIProvider("deepseek", "key", "http://fake", "deepseek-chat")
    b.client = MagicMock()
    b.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="probe"))],
        usage=MagicMock(total_tokens=5),
    )
    router.providers = [a, b]
    router.probe()
    import time
    time.sleep(0.2)
    assert not a.available
    assert b.available
    assert b.verified


def test_ask_prefers_verified_provider():
    from abvorn.core.models import ModelRouter, AIProvider
    router = ModelRouter.__new__(ModelRouter)
    a = AIProvider("qwen", "key", "http://fake", "qwen3.5-flash")
    a.verified = True
    a.last_ok = time.time()
    a.client = MagicMock()
    a.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="verified_first"))],
        usage=MagicMock(total_tokens=5),
    )
    b = AIProvider("deepseek", "key", "http://fake", "deepseek-chat")
    b.client = MagicMock()
    b.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="unverified"))],
        usage=MagicMock(total_tokens=5),
    )
    router.providers = [b, a]
    result = router.ask("test prompt")
    assert result == "verified_first"
    assert a.total_calls == 1
    assert b.total_calls == 0