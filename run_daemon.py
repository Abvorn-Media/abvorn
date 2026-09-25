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
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
)
logger = logging.getLogger("abvorn.entrypoint")


def _enable_file_logging() -> Path | None:
    """Mirror the root logger to a rotating file.

    Scheduled-task and systemd launches capture no stdout, so without this the
    daemon's log is unreachable and failures are silent.
    """
    try:
        path = Path.home() / ".abvorn" / "daemon.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logging.getLogger().addHandler(handler)
        return path
    except Exception as e:
        logging.getLogger(__name__).warning(
            "file logging unavailable, stdout only: %s", e)
        return None


async def _main() -> None:
    from abvorn.daemon import AbvornDaemon

    log_path = _enable_file_logging()
    logger.info("Daemon log file: %s", log_path or "unavailable (stdout only)")

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