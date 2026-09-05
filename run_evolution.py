"""Optional Relentless evolution loop for a persistent host.

Keeps a single RelentlessCore alive so drive cycles accumulate toward the
genesis child-core transfer (evolution_counter reaches 10). Requires explicit
operator approval: deploy/vps/setup.sh --with-evolution writes the
data/entitlements_state.json override; without it, evolution requests stay
blocked and this loop never self-terminates.

NOTE: when an evolution succeeds, GenesisProtocol calls os._exit(0), which
kills this process on purpose (parent dies at evolution). Run it in a
tmux/screen session for one evolution at a time.
"""
import asyncio
import logging
import os
import signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("abvorn.evolution_loop")

CYCLE_EVERY_SECONDS = int(os.environ.get("ABVORN_EVOLVE_INTERVAL", "1800"))


async def _main() -> None:
    from abvorn.core.relentless_core import RelentlessCore

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    core = RelentlessCore()
    logger.info(
        "Relentless evolution loop started (interval=%ss, version=%s)",
        CYCLE_EVERY_SECONDS,
        core.version,
    )
    while not stop.is_set():
        try:
            out = core.cycle()
            logger.info(
                "drive=%.3f action=%s role=%s version=%s",
                out.get("drive_score", 0.0),
                out.get("action", "none"),
                out.get("role", "solo"),
                out.get("version", core.version),
            )
        except Exception as e:
            logger.warning("evolution cycle failed (continuing): %s", e)
        try:
            await asyncio.wait_for(stop.wait(), timeout=CYCLE_EVERY_SECONDS)
        except asyncio.TimeoutError:
            pass
    logger.info("Evolution loop stopping.")


if __name__ == "__main__":
    asyncio.run(_main())