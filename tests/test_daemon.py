import pytest, asyncio
from unittest.mock import MagicMock, patch
from abvorn.daemon import AbvornDaemon

def test_daemon_start_stop():
    """Daemon should start agents, run briefly, and stop cleanly."""
    async def test():
        daemon = AbvornDaemon(":memory:")
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
        daemon = AbvornDaemon(":memory:")
        daemon.running = True
        daemon.optimization_first_run_stagger = 0
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