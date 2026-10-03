"""Tests for LinkedIn posting windows: which hours a live post may leave in.

Regression locked in here: the daily cap alone fixes only *how many* posts go
out, never *when*. The Ambassador loop wakes on every ``content.published`` bus
event, so it burned the day's slot on the first cycle after the 00:00 UTC
rollover - both 2026-10-02 and 2026-10-03 posts went out at 00:07 and 00:00 UTC,
roughly 2am in Paris and the previous evening in New York. Three windows per day
(now configurable) put the posts where an audience actually is.
"""

import json
from datetime import datetime, timezone

import pytest

from abvorn.core import social_budget


@pytest.fixture
def budget_file(tmp_path, monkeypatch):
    state = tmp_path / "social_budget.json"
    monkeypatch.setattr(social_budget, "_state_file", lambda: state)
    monkeypatch.delenv("ABVORN_SOCIAL_DAILY_LIMIT", raising=False)
    monkeypatch.delenv("ABVORN_SOCIAL_WINDOWS", raising=False)
    return state


def _utc(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


# --- opt-in -------------------------------------------------------------


def test_windows_track_local_time_across_dst(budget_file, monkeypatch):
    """The promise is "08:30 in Paris", not "06:30 UTC".

    Paris is UTC+1 in January and UTC+2 in July, so the same local hour is a
    different UTC hour in each. Hardcoding UTC would silently move the post an
    hour off peak twice a year; ZoneInfo is what keeps the promise.
    """
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    # The 08:30 Paris boundary is 07:30 UTC in winter (CET, UTC+1) and 06:30 UTC
    # in summer (CEST, UTC+2).
    assert social_budget.windows_open("linkedin", _utc(2026, 1, 15, 7, 29)) is False
    assert social_budget.windows_open("linkedin", _utc(2026, 1, 15, 7, 30)) is True
    assert social_budget.windows_open("linkedin", _utc(2026, 7, 15, 6, 29)) is False
    assert social_budget.windows_open("linkedin", _utc(2026, 7, 15, 6, 30)) is True
    # 09:00 New York: UTC-5 in winter, UTC-4 in summer.
    assert social_budget.windows_open("linkedin", _utc(2026, 1, 15, 14, 0)) is True
    assert social_budget.windows_open("linkedin", _utc(2026, 7, 15, 13, 0)) is True
    # 17:00 Paris: 16:00 UTC in winter, 15:00 UTC in summer.
    assert social_budget.windows_open("linkedin", _utc(2026, 1, 15, 16, 0)) is True
    assert social_budget.windows_open("linkedin", _utc(2026, 7, 15, 15, 0)) is True


def test_windows_are_off_unless_configured(budget_file):
    """Unset must mean "post any time", so the default does not depend on the
    wall clock and the rest of the suite stays deterministic."""
    assert social_budget.windows("linkedin") == ()
    assert social_budget.windows_open("linkedin") is True
    assert social_budget.check_and_consume("linkedin")[0] is True


def test_preset_parses_into_three_windows(budget_file, monkeypatch):
    monkeypatch.setenv(
        "ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS
    )
    assert social_budget.windows("linkedin") == (
        "Europe/Paris:0830-1030",
        "Europe/Paris:1700-1830",
        "America/New_York:0900-1030",
    )
    # Every preset window must be a real zone and a real range.
    for spec in social_budget.windows("linkedin"):
        parsed = social_budget._parse_window(spec)
        assert parsed is not None, spec
        zone, start, end = parsed
        assert start < end, spec


# --- window evaluation ---------------------------------------------------


def test_eu_morning_window_opens_in_utc(budget_file, monkeypatch):
    """08:30 Paris (CEST, UTC+2) = 06:30 UTC. The daemon runs on UTC, so the
    window has to be evaluated in the audience's zone, not the server's."""
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", "linkedin=Europe/Paris:0830-1030")
    assert social_budget.windows_open("linkedin", _utc(2026, 10, 3, 6, 29)) is False
    assert social_budget.windows_open("linkedin", _utc(2026, 10, 3, 6, 30)) is True
    assert social_budget.windows_open("linkedin", _utc(2026, 10, 3, 8, 30)) is False


def test_us_window_opens_in_utc(budget_file, monkeypatch):
    """09:00 New York (EDT, UTC-4) = 13:00 UTC."""
    monkeypatch.setenv(
        "ABVORN_SOCIAL_WINDOWS", "linkedin=America/New_York:0900-1030"
    )
    assert social_budget.windows_open("linkedin", _utc(2026, 10, 3, 12, 59)) is False
    assert social_budget.windows_open("linkedin", _utc(2026, 10, 3, 13, 0)) is True


def test_midnight_utc_is_not_a_posting_time(budget_file, monkeypatch):
    """The bug this fixes: 00:00 UTC is 02:00 Paris and 20:00 the previous day
    in New York. With the preset on, nothing may go out then."""
    monkeypatch.setenv(
        "ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS
    )
    assert social_budget.windows_open("linkedin", _utc(2026, 10, 3, 0, 0)) is False
    assert social_budget.windows_open("linkedin", _utc(2026, 10, 3, 0, 7)) is False


def test_window_wrapping_past_local_midnight(budget_file, monkeypatch):
    """A 2300-0200 window is open on both sides of local midnight.

    Paris is UTC+2 in October, so that is 21:00-00:00 UTC. The daemon runs on
    UTC, so this is the shape that proves the wrap logic actually works rather
    than accidentally reading the UTC clock.
    """
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", "linkedin=Europe/Paris:2300-0200")
    assert social_budget.windows_open("linkedin", _utc(2026, 10, 3, 20, 59)) is False
    assert social_budget.windows_open("linkedin", _utc(2026, 10, 3, 21, 0)) is True
    assert social_budget.windows_open("linkedin", _utc(2026, 10, 3, 23, 30)) is True
    assert social_budget.windows_open("linkedin", _utc(2026, 10, 4, 0, 0)) is False


def test_malformed_window_degrades_to_no_windows(budget_file, monkeypatch):
    """One bad operator string must not raise, and must not freeze the channel.

    Every value below parses to nothing, so the platform ends up unconstrained in
    time - the same fail-open posture copyguard takes. A typo must never be a
    permanent publishing outage.
    """
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "0")
    for bad in (
        "linkedin=Europe/Paris:830-1030",
        "linkedin=Europe/Paris:0830",
        "linkedin=Not/AZone:0800-0900",
        "linkedin=:0800-0900",
    ):
        monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", bad)
        assert social_budget.windows("linkedin") == ()
        assert social_budget.check_and_consume("linkedin")[0] is True


def test_malformed_window_does_not_disable_its_valid_siblings(budget_file, monkeypatch):
    """A typo in one window must not take the working ones down with it."""
    monkeypatch.setenv(
        "ABVORN_SOCIAL_WINDOWS",
        "linkedin=Europe/Paris:830-1030|Europe/Paris:0830-1030",
    )
    assert social_budget.windows("linkedin") == ("Europe/Paris:0830-1030",)


def test_env_replaces_defaults_and_omission_unconstrains(budget_file, monkeypatch):
    """Naming only linkedin must not constrain some other platform."""
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", "linkedin=Europe/Paris:0800-0900")
    assert social_budget.windows("instagram") == ()
    assert social_budget.windows_open("instagram") is True


# --- one post per window per day -----------------------------------------


def test_one_post_per_window_not_one_per_day(budget_file, monkeypatch):
    """Inside the same window the second attempt is refused; a different window
    later in the day is allowed. This is what spreads three posts across the
    day instead of clumping them in one burst."""
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "3")

    ok, reason = social_budget.check_and_consume("linkedin")
    assert ok is False, "must respect the clock, not the default wall time"
    assert "outside posting windows" in reason or "posting window" in reason


def test_three_windows_allow_three_posts(budget_file, monkeypatch):
    """The whole point of the preset: one post per window, three windows."""
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "3")

    slots = [
        _utc(2026, 10, 3, 7, 0),    # 09:00 Paris - EU morning
        _utc(2026, 10, 3, 15, 30),  # 17:30 Paris - overlap
        _utc(2026, 10, 3, 13, 30),  # 09:30 New York - US morning
    ]
    for moment in slots:
        allowed, reason = social_budget.check_and_consume_at(platform="linkedin", now=moment)
        assert allowed is True, f"{moment}: {reason}"

    assert social_budget.used_today("linkedin") == 3
    # A fourth post has no window left, and neither does re-using a spent one.
    allowed, reason = social_budget.check_and_consume_at(
        platform="linkedin", now=_utc(2026, 10, 3, 13, 45)
    )
    assert allowed is False


def test_window_claim_persists_across_a_restart(budget_file, monkeypatch):
    """A redeploy mid-window must not let the same window post twice."""
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "3")
    moment = _utc(2026, 10, 3, 7, 0)
    assert social_budget.check_and_consume_at("linkedin", now=moment)[0] is True

    # Same file on disk, fresh in-memory cache - what a daemon restart sees.
    data = json.loads(budget_file.read_text(encoding="utf-8"))
    assert data["windows"]["linkedin"] == ["Europe/Paris:0830-1030"]
    assert social_budget.check_and_consume_at("linkedin", now=moment)[0] is False


def test_refund_releases_the_window(budget_file, monkeypatch):
    """A Composio outage inside a peak hour must not burn one of three windows."""
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "3")
    moment = _utc(2026, 10, 3, 7, 0)
    assert social_budget.check_and_consume_at("linkedin", now=moment)[0] is True
    assert social_budget.open_windows("linkedin", now=moment) == []

    social_budget.refund("linkedin")
    assert social_budget.open_windows("linkedin", now=moment) == [
        "Europe/Paris:0830-1030"
    ]


def test_window_state_is_reset_next_day(budget_file, monkeypatch):
    """A stale window claim from yesterday must not block today's first window."""
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "3")
    budget_file.write_text(
        json.dumps(
            {
                "date": "1999-01-01",
                "counts": {"linkedin": 3},
                "windows": {"linkedin": ["Europe/Paris:0830-1030"]},
            }
        ),
        encoding="utf-8",
    )
    assert social_budget.open_windows("linkedin", _utc(2026, 10, 3, 7, 0)) == [
        "Europe/Paris:0830-1030"
    ]


def test_daily_cap_still_wins_over_window_count(budget_file, monkeypatch):
    """Limit 1 with three windows must still only post once."""
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "1")
    assert social_budget.check_and_consume_at(
        "linkedin", now=_utc(2026, 10, 3, 7, 0)
    )[0] is True
    allowed, reason = social_budget.check_and_consume_at(
        "linkedin", now=_utc(2026, 10, 3, 15, 30)
    )
    assert allowed is False
    assert "already at 1/1" in reason


def test_uncapped_platform_ignores_windows(budget_file, monkeypatch):
    """0 disables the count but not the clock - only an explicit empty window
    list makes a platform time-unconstrained."""
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", "linkedin=Europe/Paris:0800-0900")
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "0")
    allowed, reason = social_budget.check_and_consume_at(
        "linkedin", now=_utc(2026, 10, 3, 3, 0)
    )
    assert allowed is False
    assert "outside posting windows" in reason


def test_telegram_is_untouched_by_linkedin_windows(budget_file, monkeypatch):
    """Telegram returns before the budget gate entirely; this locks the fact
    that adding LinkedIn windows cannot leak into it."""
    monkeypatch.setenv(
        "ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS
    )
    assert social_budget.windows("telegram") == ()
    assert social_budget.windows_open("telegram", _utc(2026, 10, 3, 0, 0)) is True


def test_can_attempt_combines_count_and_window(budget_file, monkeypatch):
    """The cheap pre-flight must consider the daily count too.

    Windows alone are not enough: with three windows configured but a limit of
    2, the third window is open and unusable. Checking only the window would
    keep paying for commentary and image composition for a guaranteed reject.
    """
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "2")
    first = _utc(2026, 10, 3, 7, 0)
    second = _utc(2026, 10, 3, 15, 30)
    third = _utc(2026, 10, 3, 13, 30)

    assert social_budget.can_attempt("linkedin", first) is True
    social_budget.check_and_consume_at("linkedin", now=first)
    assert social_budget.can_attempt("linkedin", second) is True
    social_budget.check_and_consume_at("linkedin", now=second)

    # Third window is open, but the count is spent - must not attempt.
    assert social_budget.open_windows("linkedin", third) == [
        "America/New_York:0900-1030"
    ]
    assert social_budget.can_attempt("linkedin", third) is False


def test_can_attempt_is_true_without_windows(budget_file):
    """No windows configured must not change any existing behaviour."""
    assert social_budget.can_attempt("linkedin") is True


def test_status_reports_spent_windows(budget_file, monkeypatch):
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "3")
    social_budget.check_and_consume_at("linkedin", now=_utc(2026, 10, 3, 7, 0))
    snap = social_budget.status()
    assert snap["used"]["linkedin"] == 1
    assert snap["windows"]["linkedin"] == ["Europe/Paris:0830-1030"]


# --- the Ambassador gate: skip the expensive work, not just the publish ----


class _FakeSocial:
    # Falsy so ``_promote_niche`` does not also append "facebook"; this test is
    # about the window gate, not about the platform roster.
    composio = None

    def __init__(self):
        self.calls = []

    def post(self, content, platform, media_paths=None):
        self.calls.append(platform)
        return {"status": "posted", "platform": platform}


def _ambassador(social):
    from abvorn.agents.ambassador import SocialAmbassador

    amb = SocialAmbassador.__new__(SocialAmbassador)
    amb.social = social
    amb.router = None
    amb.state = None
    amb.notifier = None
    amb._perception = {}
    return amb


def _pin_ambassador_clock(monkeypatch, moment):
    """Point the Ambassador's ``can_attempt`` at a frozen moment.

    ``_promote_niche`` calls ``can_attempt(platform)`` with no argument, so the
    clock has to be injected behind it rather than through the signature.
    """
    from abvorn.agents import ambassador as amb_mod

    monkeypatch.setattr(
        amb_mod, "can_attempt",
        lambda platform: social_budget.can_attempt(platform, moment),
    )


def _spy_on_expensive_work(monkeypatch):
    """Record every call that costs an LLM call or an image render."""
    calls = {"media": [], "craft": []}

    def fake_media_for(_self, niche, platform, url="", title=""):
        calls["media"].append(platform)
        return []

    async def fake_craft(_self, item, media_paths=None):
        calls["craft"].append(item["platform"])
        return {"status": "posted", "platform": item["platform"]}

    monkeypatch.setattr(
        "abvorn.agents.ambassador.SocialAmbassador._media_for", fake_media_for
    )
    monkeypatch.setattr(
        "abvorn.agents.ambassador.SocialAmbassador._craft_and_post", fake_craft
    )
    return calls


def _promote(amb):
    import asyncio

    return asyncio.run(
        amb._promote_niche(
            "wireless-headphones", url="https://abvorn.com/reviews/wireless-headphones/"
        )
    )


def test_promote_skips_expensive_work_outside_a_window(budget_file, monkeypatch):
    """The 165 wasted cycles on 2026-10-02 were not the publish call - they were
    the LLM commentary and image composition that happened before it and was then
    thrown away. This asserts nothing expensive is attempted for LinkedIn.

    ``x`` is deliberately still allowed through: the LinkedIn window must not
    leak into the other platforms, and X is not window-constrained.
    """
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "3")
    # 03:00 UTC = 05:00 Paris = 23:00 the previous day in New York. No window.
    _pin_ambassador_clock(monkeypatch, _utc(2026, 10, 3, 3, 0))
    calls = _spy_on_expensive_work(monkeypatch)

    result = _promote(_ambassador(_FakeSocial()))

    assert "linkedin" not in calls["craft"], "paid for commentary outside a window"
    assert "linkedin" not in calls["media"], "rendered a card outside a window"
    statuses = {r["platform"]: r["status"] for r in result["results"]}
    assert statuses["linkedin"] == "window_closed"
    assert statuses["x"] == "posted"


def test_promote_still_works_inside_a_window(budget_file, monkeypatch):
    """Positive control: the gate must not silence the channel entirely.

    ``x`` is left window-free on purpose - this is also the regression that keeps
    a LinkedIn-only window from leaking into the other platforms.
    """
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "3")
    _pin_ambassador_clock(monkeypatch, _utc(2026, 10, 3, 7, 0))
    calls = _spy_on_expensive_work(monkeypatch)

    result = _promote(_ambassador(_FakeSocial()))

    assert calls["craft"] == ["x", "linkedin"]
    assert calls["media"] == ["x", "linkedin"]
    statuses = {r["platform"]: r["status"] for r in result["results"]}
    assert statuses["linkedin"] == "posted"
    assert statuses["x"] == "posted"


def test_promote_skips_once_the_days_allowance_is_gone(budget_file, monkeypatch):
    """Even inside a window, a spent count must stop the spend.

    This is the case that would otherwise be missed: the window is wide open, so
    a window-only check says yes and the pipeline pays for a post the budget
    gate is about to reject."""
    monkeypatch.setenv("ABVORN_SOCIAL_WINDOWS", social_budget.LINKEDIN_PRESET_WINDOWS)
    monkeypatch.setenv("ABVORN_SOCIAL_DAILY_LIMIT", "3")
    morning = _utc(2026, 10, 3, 7, 0)
    social_budget.check_and_consume_at("linkedin", now=morning)
    social_budget.check_and_consume_at("linkedin", now=_utc(2026, 10, 3, 15, 30))
    social_budget.check_and_consume_at("linkedin", now=_utc(2026, 10, 3, 13, 30))
    _pin_ambassador_clock(monkeypatch, morning)
    calls = _spy_on_expensive_work(monkeypatch)

    result = _promote(_ambassador(_FakeSocial()))

    assert "linkedin" not in calls["craft"]
    statuses = {r["platform"]: r["status"] for r in result["results"]}
    assert statuses["linkedin"] == "window_closed"
    # x has no windows and its own untouched count, so it is unaffected.
    assert statuses["x"] == "posted"