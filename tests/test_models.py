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
    p.mark_error(RuntimeError("Error code: 429 - Rate limit reached for model"))
    assert p._banned_until - time.time() <= 120

    p = AIProvider("test5", "sk-test-key", model="gpt-4o")
    p.mark_error(RuntimeError("Error code: 429 - you have no credits remaining"))
    assert p._banned_until - time.time() > 1800

    p = AIProvider("test6", "sk-test-key", model="gpt-4o")
    p.mark_error(RuntimeError("Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` on tokens per day (TPD): Limit 200000, Used 199645"))
    # TPD exhaustion bans until the next UTC midnight (+60s), not a flat 60s.
    # Assert that value directly instead of "> 6 * 3600": the midnight-based
    # duration is only over 6h before 18:00 UTC, so the old floor failed for the
    # last six hours of every day even though models.py was correct.
    to_midnight = 86400 - (time.time() % 86400)
    remaining = p._banned_until - time.time()
    assert to_midnight - 5 <= remaining <= to_midnight + 65

    p = AIProvider("test4", "sk-test-key", model="gpt-4o")
    p.mark_error(RuntimeError("Error code: 500 - server"))
    assert p._banned_until - time.time() <= 120


def test_transport_error_ban_escalates_for_unreachable_endpoint():
    """A permanently unreachable endpoint must not be retried every 60s forever.

    The daemon's gemini/openai endpoints time out on every call. With a flat
    60s ban each attempt burned ~30s, and when the healthy providers were
    briefly banned too the router reported "All AI providers exhausted" and
    the content pipeline returned None.
    """
    from abvorn.core.models import AIProvider

    first = AIProvider("dead-first", "sk-test-key", model="gpt-4o")
    first.mark_error(RuntimeError("Request timed out."))
    assert 0 < first._banned_until - time.time() <= 120

    second = AIProvider("dead-second", "sk-test-key", model="gpt-4o")
    for _ in range(2):
        second.mark_error(RuntimeError("Request timed out."))
    assert second._banned_until - time.time() > 10 * 60

    third = AIProvider("dead-third", "sk-test-key", model="gpt-4o")
    for _ in range(3):
        third.mark_error(RuntimeError("<urlopen error [WinError 10060] A connection attempt failed>"))
    assert third._banned_until - time.time() > 6 * 3600


def test_transport_ban_streak_resets_after_success():
    """A single network blip must not permanently sideline a healthy provider."""
    from abvorn.core.models import AIProvider

    p = AIProvider("flaky", "sk-test-key", model="gpt-4o")
    p.mark_error(RuntimeError("Request timed out."))
    assert p._banned_until - time.time() <= 120

    p._record_success(
        MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))], usage=MagicMock(total_tokens=1)),
        time.time(),
    )
    p.mark_error(RuntimeError("Request timed out."))
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


def test_ask_waits_for_transient_ban_and_retries():
    from abvorn.core.models import ModelRouter, AIProvider
    router = ModelRouter.__new__(ModelRouter)
    a = AIProvider("groq", "key", "http://fake", "openai/gpt-oss-120b")
    a.ban(2)  # recovers in ~2s (transient rate-limit-style ban)
    a.client = MagicMock()
    a.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="recovered"))],
        usage=MagicMock(total_tokens=5),
    )
    router.providers = [a]
    result = router.ask("test prompt")
    assert result == "recovered"
    assert a.available  # ban has cleared


def test_ask_does_not_wait_for_long_ban():
    from abvorn.core.models import ModelRouter, AIProvider
    router = ModelRouter.__new__(ModelRouter)
    a = AIProvider("cerebras", "key", "http://fake", "gpt-oss-120b")
    a.ban(12 * 3600)  # auth/billing-style long ban
    a.client = MagicMock()
    router.providers = [a]
    result = router.ask("test prompt")
    assert result is None  # no wait, returns exhausted immediately


def test_ask_prefers_least_used_verified_provider():
    from abvorn.core.models import ModelRouter, AIProvider
    router = ModelRouter.__new__(ModelRouter)
    heavy = AIProvider("groq", "key", "http://fake", "openai/gpt-oss-120b")
    heavy.verified = True
    heavy.last_ok = time.time()
    heavy._day_tokens = 150000  # nearly burned through today's TPD
    heavy.client = MagicMock()
    heavy.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="still-alive"))],
        usage=MagicMock(total_tokens=5),
    )
    light = AIProvider("groq-oss-20", "key", "http://fake", "openai/gpt-oss-20b")
    light.verified = True
    light.last_ok = time.time()
    light._day_tokens = 1000  # fresh budget
    light.client = MagicMock()
    light.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="fresh-model"))],
        usage=MagicMock(total_tokens=5),
    )
    router.providers = [heavy, light]
    result = router.ask("test prompt")
    assert result == "fresh-model"
    assert light.total_calls == 1
    assert heavy.total_calls == 0


# --- JSON recovery -----------------------------------------------------------
# Models return 200s with fenced/preambled JSON, and Groq returns a 400 when its
# json_object validator dislikes the output. Both used to throw away a paid
# completion ("Draft JSON parse failed") and ban the only working provider.

def test_parse_json_accepts_plain_fenced_and_preambled():
    from abvorn.core.models import parse_json
    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('```\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here is the JSON:\n{"a": 1}\nHope that helps.') == {"a": 1}
    assert parse_json('["one", "two"]') == ["one", "two"]
    assert parse_json('{"a": ') is None
    assert parse_json("not json at all") is None
    assert parse_json("") is None
    assert parse_json(None) is None


def test_parse_json_passes_dicts_through():
    from abvorn.core.models import parse_json
    payload = {"already": "parsed"}
    assert parse_json(payload) is payload


def test_providers_sharing_a_key_share_one_lock():
    """Groq's model aliases share one account/rate-limit bucket. Concurrent
    calls with the same key get 403 'Forbidden' from Groq's abuse protection,
    so they must be serialized even across different agent threads."""
    from abvorn.core.models import ModelRouter

    router = ModelRouter({"GROQ_KEY": "sk-groq", "OPENAI_KEY": "sk-openai"})
    by_name = {p.name: p for p in router.providers}
    groq = by_name["groq"]
    assert groq._key_lock is by_name["groq-oss-20"]._key_lock
    assert groq._key_lock is by_name["groq-qwen-27"]._key_lock
    assert groq._key_lock is not by_name["openai"]._key_lock


def test_same_key_calls_never_overlap():
    import threading
    from abvorn.core.models import AIProvider

    lock = threading.RLock()
    a = AIProvider("a", "shared-key", "http://fake", "m", min_gap=0, key_lock=lock)
    b = AIProvider("b", "shared-key", "http://fake", "m", min_gap=0, key_lock=lock)

    active = 0
    peak = 0
    guard = threading.Lock()

    def fake_create(**kwargs):
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with guard:
            active -= 1
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok"))],
            usage=MagicMock(total_tokens=1),
        )

    for p in (a, b):
        p.client = MagicMock()
        p.client.chat.completions.create.side_effect = fake_create

    threads = [threading.Thread(target=lambda p=p: p.call([{"role": "user", "content": "hi"}])) for p in (a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak == 1


def test_forbidden_ban_escalates_instead_of_jumping_to_twelve_hours():
    """A 403 is ambiguous (revoked key vs Groq abuse protection). A flat 12h
    ban took the only working provider offline for a transient block; the ban
    must start short and grow only while the block persists."""
    from abvorn.core.models import AIProvider
    p = AIProvider("groq", "sk-test-key", model="openai/gpt-oss-120b")
    err = RuntimeError("Error code: 403 - {'error': {'message': 'Forbidden'}}")

    bans = []
    for _ in range(4):
        p._banned_until = 0
        p.mark_error(err)
        bans.append(round(p._banned_until - time.time()))

    assert 55 <= bans[0] <= 61          # first 403: one minute
    assert bans[1] > bans[0]            # then escalate
    assert all(b <= 6 * 3600 + 2 for b in bans)
    assert p._forbidden_streak == 4

    # A success resets the streak so a later transient 403 is cheap again.
    resp = MagicMock(
        usage=MagicMock(total_tokens=1),
        choices=[MagicMock(message=MagicMock(content="ok"))],
    )
    p._record_success(resp, time.time())
    assert p._forbidden_streak == 0


def test_json_validation_error_is_not_a_ban():
    """A 400 caused by malformed model JSON is a prompt problem, not provider
    death: banning it removed Groq - the only working provider - from the pool
    and left the daemon looping on 'All providers banned'."""
    from abvorn.core.models import AIProvider
    p = AIProvider("groq", "sk-test-key", model="gpt-4o")
    p.mark_error(RuntimeError(
        "Error code: 400 - {'error': {'message': 'Failed to generate JSON. "
        "Please adjust your prompt.'}}"
    ))
    assert p.available
    assert p.failures == 1


def test_json_mode_400_retries_as_plain_text():
    from abvorn.core.models import AIProvider
    import openai
    p = AIProvider("groq", "sk-test-key", model="openai/gpt-oss-120b")
    p.client = MagicMock()
    bad = openai.BadRequestError(
        "Error code: 400 - Failed to generate JSON",
        response=MagicMock(status_code=400),
        body={},
    )
    p.client.chat.completions.create.side_effect = [
        bad,
        MagicMock(
            choices=[MagicMock(message=MagicMock(content='```json\n{"ok": true}\n```'))],
            usage=MagicMock(total_tokens=7),
        ),
    ]
    text = p.call([{"role": "user", "content": "hi"}], json_mode=True)
    from abvorn.core.models import parse_json
    assert parse_json(text) == {"ok": True}
    # second attempt must drop response_format so the provider will answer
    assert "response_format" not in p.client.chat.completions.create.call_args.kwargs