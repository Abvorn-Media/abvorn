import pytest, asyncio
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