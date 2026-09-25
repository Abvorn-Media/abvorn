import pytest, asyncio, threading
from unittest.mock import MagicMock, patch
from abvorn.daemon import AbvornDaemon
from abvorn.core.bus import AgentBus


def _hermetic_daemon(*, stagger: int | None = None):
    """Construct an AbvornDaemon without touching live surfaces.

    The constructor fires ModelRouter.probe() (real provider calls) and the
    bus otherwise binds to the SHARED ~/.abvorn/bus.db, so a stray real
    content.researched event would trigger live LLM generation. Hermetic
    construction stubs probe and swaps the bus for an in-memory one.
    """
    with (
        patch("abvorn.core.models.ModelRouter.probe", return_value=None),
        patch("abvorn.daemon.AgentBus", lambda *a, **k: AgentBus(":memory:")),
    ):
        daemon = AbvornDaemon(":memory:")
    if stagger is not None:
        daemon.optimization_first_run_stagger = stagger
    return daemon


def test_daemon_start_stop():
    """Daemon should start agents, run briefly, and stop cleanly.

    Hermetic: the GSC/GA4/domination/telegram loops all run on their first
    pass and hit live endpoints, so they are replaced with no-ops — the
    test is deterministic regardless of upstream API health. Regression:
    ModelRouter.probe() and the first-pass loops hung on a slow provider
    endpoint and timed the test out."""
    async def _noop():
        return None

    async def test():
        daemon = _hermetic_daemon()
        daemon._gsc_loop = _noop
        daemon._domination_loop = _noop
        daemon._analytics_feedback_loop = _noop
        daemon._telegram_poll_loop = _noop
        with patch("abvorn.engagement.watcher.MentionWatcher.poll", return_value=[]):
            await daemon.start()
            await asyncio.sleep(0.5)
            await daemon.stop()
        assert daemon.running == False
    asyncio.run(test())


def test_optimization_loop_invokes_optimizer_cycle():
    """The hourly optimization loop must construct and drive the
    OptimizationDaemon's run_cycle — regression for the audit finding that
    the optimizer was never started."""
    async def test():
        daemon = _hermetic_daemon(stagger=0)
        daemon.running = True
        fake = MagicMock()
        fake.should_run.return_value = True
        fake.run_cycle.return_value = {
            "cycle_id": "test1234",
            "timestamp": "2026-01-01T00:00:00",
            "actions": [{"type": "hook_benchmark", "detail": "no data"}],
        }
        with patch("abvorn.daemon.OptimizationDaemon", return_value=fake):
            task = asyncio.create_task(daemon._optimization_loop())
            await asyncio.sleep(0.2)
            daemon.running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        fake.run_cycle.assert_called_once()
    asyncio.run(test())


def test_bus_loop_processes_signal_once():
    async def test():
        daemon = _hermetic_daemon()
        daemon.running = True
        calls = 0

        async def run_cycle():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)

        daemon.run_domination_cycle = run_cycle
        task = asyncio.create_task(daemon._bus_loop())
        daemon.bus.publish("domination.signal", {"source": "test"})
        await asyncio.sleep(0.05)
        daemon.running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert calls == 1

    asyncio.run(test())


def test_domination_cycle_rejects_overlapping_run():
    async def test():
        daemon = _hermetic_daemon()
        daemon._phase3_inited = True
        daemon.domination = MagicMock()
        started = threading.Event()
        release = threading.Event()

        def run_cycle():
            started.set()
            release.wait(1)
            return {
                "status": "complete",
                "niche": "mechanical-keyboards",
                "title": "Keyboard guide",
            }

        daemon.domination.run_cycle = MagicMock(side_effect=run_cycle)
        daemon.health = MagicMock()
        daemon.notifier = MagicMock()

        first = asyncio.create_task(daemon.run_domination_cycle())
        while not started.is_set():
            await asyncio.sleep(0)
        second = await daemon.run_domination_cycle()
        release.set()
        first_result = await first

        assert first_result["status"] == "complete"
        assert second == {"status": "already_running"}
        assert daemon.domination.run_cycle.call_count == 1

    asyncio.run(test())