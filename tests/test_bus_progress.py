"""Regression tests for the bus watermark that broke the tv redeploy loop.

The bug: DeployAgent and SocialAmbassador remembered the last 200 handled event
ids and treated anything outside that window as unhandled. The backlog was
~460 drafted events deep, so the same `tv` ids fell out of the window and were
rediscovered every cycle - re-deploying the tv page and re-announcing it forever.
"""

from abvorn.core import bus_progress


class FakeState:
    def __init__(self, initial=None):
        self.meta = dict(initial or {})
        self.writes = []

    def get_meta(self, key, default=None):
        return self.meta.get(key, default)

    def set_meta(self, key, value):
        self.meta[key] = value
        self.writes.append((key, value))


def _event(i):
    return {"id": i, "message": {"niche": "tv"}, "created_at": f"2026-10-01T00:{i:02d}:00"}


class TestWatermark:
    def test_unhandled_events_pass_through(self):
        state = FakeState()
        events = [_event(1), _event(2), _event(3)]
        assert [e["id"] for e in bus_progress.fresh_events(state, "k", events)] == [1, 2, 3]

    def test_advance_then_filters(self):
        state = FakeState()
        bus_progress.advance(state, "k", [1, 2])
        assert [e["id"] for e in bus_progress.fresh_events(state, "k", [_event(2), _event(3)])] == [3]

    def test_the_regression_that_caused_the_tv_flood(self):
        """A backlog far deeper than any fixed-size window must still retire.

        This is the exact production shape: 663 drafted events, 200 remembered.
        Under the old set-based logic every id outside the window came back as
        "fresh" on the next cycle, forever.
        """
        state = FakeState()
        backlog = [_event(i) for i in range(1, 664)]

        # Simulate the old code: remember only the newest 200 handled ids.
        stored = []
        first_pass = [e["id"] for e in backlog if e["id"] not in set(stored)]
        assert len(first_pass) == 663
        stored = sorted(set(stored) | set(first_pass))[-200:]

        # Second pass under the old logic still sees the evicted backlog.
        still_fresh = [i for i in backlog if i["id"] not in set(stored)]
        assert still_fresh, "old logic would have replayed evicted ids"
        assert len(still_fresh) == 663 - 200 == 463

        # The watermark retires all of them in one pass.
        bus_progress.advance(state, "deployagent_drafted_watermark", first_pass)
        assert bus_progress.fresh_events(state, "deployagent_drafted_watermark", backlog) == []

    def test_watermark_is_monotonic(self):
        state = FakeState()
        bus_progress.advance(state, "k", [100])
        assert bus_progress.advance(state, "k", [50]) == 100
        assert bus_progress.read_watermark(state, "k") == 100

    def test_repeated_advance_does_not_move_backwards(self):
        state = FakeState()
        bus_progress.advance(state, "k", [500])
        bus_progress.advance(state, "k", [500])
        bus_progress.advance(state, "k", [10])
        assert bus_progress.read_watermark(state, "k") == 500

    def test_state_is_a_single_integer_not_a_growing_list(self):
        """State must not grow with the backlog - that was the original defect."""
        state = FakeState()
        for batch in range(50):
            ids = list(range(batch * 20, batch * 20 + 20))
            bus_progress.advance(state, "k", ids)
        assert state.meta["k"] == 999
        assert isinstance(state.meta["k"], int)


class TestLegacyMigration:
    def test_migrates_from_the_truncated_id_list(self):
        """An upgrading deployment must not replay its backlog."""
        legacy = [1309746, 1309747, 1400000]
        state = FakeState({"deployagent_drafted_watermark": legacy})
        mark = bus_progress.read_watermark(state, "deployagent_drafted_watermark")
        assert mark == 1400000
        # Below the mark: retired, not replayed.
        assert bus_progress.fresh_events(state, "deployagent_drafted_watermark", [_event(1309746)]) == []
        # Above the mark: still fresh.
        assert len(bus_progress.fresh_events(state, "deployagent_drafted_watermark", [_event(1400001)])) == 1

    def test_watermark_beats_legacy_list_once_written(self):
        state = FakeState({"k": [100, 200]})
        bus_progress.advance(state, "k", [300])
        assert bus_progress.read_watermark(state, "k") == 300
        state.meta["k_legacy_leftover"] = [400]
        assert bus_progress.read_watermark(state, "k") == 300

    def test_empty_legacy_list(self):
        state = FakeState({"k": []})
        assert bus_progress.read_watermark(state, "k") == 0

    def test_dict_envelope_form(self):
        state = FakeState({"k": {"watermark": 77}})
        assert bus_progress.read_watermark(state, "k") == 77


class TestHostileState:
    def test_none_state(self):
        assert bus_progress.read_watermark(None, "k") == 0
        assert bus_progress.fresh_events(None, "k", [_event(1)]) == [_event(1)]
        assert bus_progress.advance(None, "k", [1]) == 0

    def test_garbage_value_reads_as_nothing_handled_not_everything(self):
        state = FakeState({"k": "not-a-number"})
        assert bus_progress.read_watermark(state, "k") == 0
        # Must not treat everything as handled.
        assert len(bus_progress.fresh_events(state, "k", [_event(9)])) == 1

    def test_state_read_failure_does_not_replay_backlog(self):
        class BrokenState(FakeState):
            def get_meta(self, key, default=None):
                raise RuntimeError("db locked")

        state = BrokenState()
        bus_progress.advance(state, "k", [])  # cannot read -> cannot write a bogus mark
        assert bus_progress.read_watermark(state, "k") == 0

    def test_negative_watermark_clamped(self):
        state = FakeState({"k": -50})
        assert bus_progress.read_watermark(state, "k") == 0

    def test_bool_is_not_an_int_watermark(self):
        state = FakeState({"k": True})
        assert bus_progress.read_watermark(state, "k") == 0

    def test_event_without_id_is_skipped_not_looped_forever(self):
        state = FakeState()
        events = [{"message": {}}, _event(5)]
        fresh = bus_progress.fresh_events(state, "k", events)
        assert [e["id"] for e in fresh] == [5]

    def test_string_event_ids(self):
        state = FakeState()
        events = [{"id": "7"}, {"id": "8"}]
        fresh = bus_progress.fresh_events(state, "k", events)
        assert [e["id"] for e in fresh] == ["7", "8"]

    def test_fresh_events_sorted_oldest_first(self):
        state = FakeState()
        events = [_event(9), _event(3), _event(6)]
        assert [e["id"] for e in bus_progress.fresh_events(state, "k", events)] == [3, 6, 9]


class TestAmbassadorHeadline:
    def _agent(self):
        from abvorn.agents.ambassador import SocialAmbassador
        return SocialAmbassador.__new__(SocialAmbassador)

    def test_real_title_wins(self):
        assert self._agent()._headline("tv", title="Best OLED TVs of 2026", slug="tv") == \
            "Just published: Best OLED TVs of 2026"

    def test_two_different_articles_get_different_headlines(self):
        a = self._agent()
        h1 = a._headline("tv", title="Roku 55 Inch Select Series Review", slug="tv")
        h2 = a._headline("tv", title="Insignia 50 Class F50 Review", slug="tv")
        assert h1 != h2

    def test_same_niche_twice_is_identical(self):
        """The old bug: same niche => byte-identical text, always."""
        a = self._agent()
        assert a._headline("tv", title="", slug="") == a._headline("tv", title="", slug="")

    def test_slug_is_humanised_not_leaked_raw(self):
        head = self._agent()._headline("tv", slug="amazon-echo-show-5-newest-model")
        assert head == "Just published our amazon echo show 5 newest model guide!"
        assert "-" not in head

    def test_whitespace_and_quotes_cleaned(self):
        head = self._agent()._headline("tv", title='  "Best   TVs"\n')
        assert head == "Just published: Best TVs"

    def test_niche_fallback_last(self):
        assert self._agent()._headline("tv") == "Just published our tv guide!"

    def test_title_fallback_reads_a_real_article_from_state(self):
        """Deploys with no pipeline payload still name a real article."""
        agent = self._agent()

        class State:
            def get_posts_for_niche(self, niche):
                return [{"title": "Roku 55 Inch Select Series Review", "niche": niche}]

        agent.state = State()
        assert agent._latest_title_for_niche("tv") == "Roku 55 Inch Select Series Review"

    def test_title_fallback_survives_a_broken_state(self):
        agent = self._agent()

        class State:
            def get_posts_for_niche(self, niche):
                raise RuntimeError("db locked")

        agent.state = State()
        assert agent._latest_title_for_niche("tv") == ""

    def test_title_fallback_with_no_state(self):
        agent = self._agent()
        agent.state = None
        assert agent._latest_title_for_niche("tv") == ""