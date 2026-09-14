"""Tests for the pre-publish copy gate (abvorn.core.copyguard)."""

import pytest

from abvorn.core import copyguard
from abvorn.core.copyguard import (
    CopyGateError,
    GateResult,
    _chunks,
    _redact,
    check_text,
    enabled,
    gate_copy,
    html_to_text,
    is_blocking,
)

MISS = {"rule": "EN_A_VS_AN", "category": "MISC", "issue_type": "misspelling",
        "message": "Wrong article", "replacement": "a", "context": "This is an test"}
WHITE = {"rule": "WHITESPACE_RULE", "category": "TYPOGRAPHY", "issue_type": "whitespace",
         "message": "Possible typo", "replacement": " ", "context": "a  b"}
STYLE = {"rule": "STYLE", "category": "STYLE", "issue_type": "style",
         "message": "Consider rewording", "replacement": "", "context": "foo"}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("ABVORN_COPYGUARD", raising=False)
    # Never touch a real server in tests: gate everything through fakes.
    monkeypatch.setattr(copyguard, "_Availability", type("_Av", (), {
        "available": staticmethod(lambda: True), "_known": True, "_at": 0.0}))


def test_enabled_defaults_on_and_optout(monkeypatch):
    assert enabled() is True
    for off in ("0", "false", "off", "no"):
        monkeypatch.setenv("ABVORN_COPYGUARD", off)
        assert enabled() is False
    monkeypatch.setenv("ABVORN_COPYGUARD", "1")
    assert enabled() is True


def test_is_blocking_sores_by_issue_type():
    assert is_blocking(MISS) is True
    assert is_blocking(WHITE) is False
    assert is_blocking(STYLE) is False
    assert is_blocking({**MISS, "rule": "SOME_IGNORED"}) is True  # ignore set empty


def test_is_blocking_honors_ignore_set():
    assert is_blocking(MISS, {"EN_A_VS_AN"}) is False


def test_redact_removes_model_numbers_and_collapses_spaces():
    out = _redact("We compared the Dell S2725QS, S2725QC, and LG 27UP650K-W today", set())
    assert "S2725" not in out
    assert "27UP650" not in out
    assert "  " not in out
    assert "compared" in out and "today" in out


def test_redact_applies_regex_ignore_entries():
    out = _redact("PrefixS2725QSSuffix", {r"/S2725QS/"})
    assert "S2725QS" not in out


def test_html_to_text_strips_markup():
    assert html_to_text("<h1>Hi</h1><p>Some <b>bold</b> text.</p>") == "Hi Some bold text."


def test_chunks_splits_long_text_without_loss():
    text = ("the quick brown fox jumps " * 5000).strip()
    chunks = _chunks(text)
    assert len(chunks) > 1
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_chunks_single_when_short():
    assert _chunks("short text") == ["short text"]


def test_gate_copy_block_mode_fails_on_blocking(monkeypatch):
    monkeypatch.setattr(copyguard, "check_text", lambda t, **kw: [MISS])
    res = gate_copy("This is an test", "t", mode="block")
    assert res.ok is False
    assert res.blocking == [MISS]


def test_gate_copy_block_mode_pass_on_nonblocking(monkeypatch):
    monkeypatch.setattr(copyguard, "check_text", lambda t, **kw: [WHITE, STYLE])
    res = gate_copy("a  b", "t", mode="block")
    assert res.ok is True
    assert res.blocking == []


def test_gate_copy_report_mode_never_fails(monkeypatch):
    monkeypatch.setattr(copyguard, "check_text", lambda t, **kw: [MISS])
    res = gate_copy("This is an test", "t", mode="report")
    assert res.ok is True
    assert res.issues == [MISS]


def test_gate_copy_skips_empty_and_disabled(monkeypatch):
    seen = []
    monkeypatch.setattr(copyguard, "check_text", lambda t, **kw: seen.append(t) or [])
    assert gate_copy("  ", "t", mode="block").ok is True
    assert gate_copy("", "t", mode="block").ok is True
    monkeypatch.setenv("ABVORN_COPYGUARD", "off")
    assert gate_copy("some text", "t", mode="block").ok is True
    assert seen == []


def test_check_text_empty_when_server_unavailable(monkeypatch):
    monkeypatch.setattr(copyguard, "_Availability", type("_Av", (), {
        "available": staticmethod(lambda: False)}))
    assert check_text("anything") == []


def test_number_agreement_flags_singular_after_count():
    """The exact regression that shipped live: LanguageTool is blind to
    'We compared 4 Monitor', so the deterministic guard must catch it."""
    issues = copyguard._number_agreement_issues(
        "Tired of Matter certification delays? We compared 4 Tv so you don't "
        "have to guess. We compared 4 Smart home devices too."
    )
    keys = [i["rule"] for i in issues]
    assert "NUMBER_NOUN_AGREEMENT" in keys
    flagged = [i for i in issues if i["rule"] == "NUMBER_NOUN_AGREEMENT"]
    assert any("Tv" in i["context"] for i in flagged)
    # smart-home renders as "Smart home devices" (plural 'devices') -> clean
    assert all("devices" not in i["context"] for i in flagged)


def test_number_agreement_flags_bare_smart_home_phrase():
    issues = copyguard._number_agreement_issues("We compared 4 Smart home so you don't have to guess.")
    assert any(i["rule"] == "NUMBER_NOUN_AGREEMENT" for i in issues)


def test_number_agreement_allows_plural_nouns():
    issues = copyguard._number_agreement_issues(
        "We compared 4 monitors. We tested 8 TVs. We reviewed 12 Mice side by side."
    )
    assert [i["rule"] for i in issues] == []


def test_number_agreement_singular_count_passes():
    assert copyguard._number_agreement_issues("We compared 1 Tv today.") == []


def test_number_agreement_is_blocking():
    issues = copyguard._number_agreement_issues("We compared 4 Monitor.")
    assert issues and is_blocking(issues[0]) is True


def test_check_text_deterministic_runs_without_server(monkeypatch):
    monkeypatch.setattr(copyguard, "_Availability", type("_Av", (), {
        "available": staticmethod(lambda: False)}))
    issues = check_text("We compared 4 Monitor in our lab.")
    assert any(i["rule"] == "NUMBER_NOUN_AGREEMENT" for i in issues)


def test_gate_copy_block_mode_fails_on_number_agreement(monkeypatch):
    """Block mode must fail on the deterministic guard even when the
    LanguageTool server is down (server-independent net stays armed)."""
    monkeypatch.setattr(copyguard, "_Availability", type("_Av", (), {
        "available": staticmethod(lambda: False)}))
    res = gate_copy("We compared 4 Monitor.", "t", mode="block")
    assert res.ok is False
    assert "NUMBER_NOUN_AGREEMENT" in {i["rule"] for i in res.blocking}


def test_social_publisher_blocks_live_posts(monkeypatch):
    from abvorn.domination.social_publisher import SocialPublisher

    monkeypatch.setenv("ABVORN_SOCIAL_PUBLISH", "1")
    monkeypatch.setenv("ABVORN_SOCIAL_PLATFORMS", "x")
    fake_result = GateResult(ok=False, blocking=[MISS], issues=[MISS])
    monkeypatch.setattr(copyguard, "gate_copy", lambda t, label, mode="report": fake_result)

    pub = SocialPublisher(composio_key="test_key")
    monkeypatch.setattr(pub, "_will_post_live", lambda platform, mapping: True)
    with pytest.raises(CopyGateError):
        pub.publish({"text": "This is an test"}, "x", "laptops")


def test_social_publisher_exports_with_gate_off(monkeypatch, tmp_path):
    from abvorn.domination.social_publisher import SocialPublisher, EXPORT_DIR

    monkeypatch.setenv("ABVORN_SOCIAL_PUBLISH", "0")
    monkeypatch.setattr("abvorn.domination.social_publisher.EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(copyguard, "gate_copy",
                        lambda t, label, mode="report": GateResult(ok=True))

    pub = SocialPublisher(composio_key="test_key")
    result = pub.publish({"text": "Best laptops compared."}, "x", "laptops")
    assert result["status"] == "exported"


def test_listmonk_gates_bad_copy(monkeypatch):
    from abvorn.core.listmonk_client import ListmonkClient

    fake_result = GateResult(ok=False, blocking=[MISS], issues=[MISS])
    monkeypatch.setattr(copyguard, "gate_copy", lambda t, label, mode="report": fake_result)
    client = ListmonkClient(base_url="http://localhost:9999")
    with pytest.raises(CopyGateError):
        client.send_transactional_email("a@b.com", "Subject", "<p>This is an test</p>")


def test_listmonk_allows_clean_copy(monkeypatch):
    from abvorn.core.listmonk_client import ListmonkClient

    monkeypatch.setattr(copyguard, "gate_copy",
                        lambda t, label, mode="report": GateResult(ok=True))
    monkeypatch.setattr(
        ListmonkClient, "_request",
        lambda self, method, path, **kw: {"ok": True},
    )
    client = ListmonkClient(base_url="http://localhost:9999")
    client.send_transactional_email("a@b.com", "Subject", "<p>Clean copy.</p>")