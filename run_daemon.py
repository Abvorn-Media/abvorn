"""Abvorn daemon entrypoint (24/7 organism).

Run from the repo root:

    python run_daemon.py

On SIGTERM (systemd stop/restart) the daemon shuts down its loops
gracefully and exits 0.
"""
import asyncio
import contextlib
import logging
import signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("abvorn.entrypoint")


async def _main() -> None:
    from abvorn.daemon import AbvornDaemon

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    daemon = AbvornDaemon()
    run_task = asyncio.create_task(daemon.start())
    logger.info("Abvorn daemon entrypoint running; awaiting shutdown signal")
    await stop.wait()
    logger.info("Shutdown signal received — stopping daemon")
    try:
        await asyncio.wait_for(daemon.stop(), timeout=30)
    except Exception as e:
        logger.warning("Daemon stop raised: %s", e)
    run_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await run_task


if __name__ == "__main__":
    asyncio.run(_main())