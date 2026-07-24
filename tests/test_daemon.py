import pytest, asyncio
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