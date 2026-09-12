"""win_trigger.py - Bridge live Abvorn data into win.sh loop run briefs.

Scheduled on local Windows via Task Scheduler (and callable from the daemon's
GSC loop). Reads data/gsc_latest_summary.json and, when the SEO Growth loop's
minimum-evidence threshold is crossed (>=100 impressions or >=20 clicks over
the window), creates a run brief via `win run seo-growth --trigger signal`.

Guards:
- Skips when evidence is below the threshold.
- Skips when a seo-growth run is already pending (non-terminal in runs.jsonl).
- Skips cleanly when .win is not provisioned or the win CLI is missing.

Signal text is ASCII-only: non-ASCII in signals gets double-encoded to
mojibake when passing through the Windows ANSI codepage (see AGENTS.md).

Exit codes: 0 always (logging carries the detail; scheduler treats as ok).
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GSC_SUMMARY = REPO_ROOT / "data" / "gsc_latest_summary.json"
RUNS_LEDGER = REPO_ROOT / ".win" / "state" / "runs.jsonl"

MIN_IMPRESSIONS = 100
MIN_CLICKS = 20

TERMINAL_RUN_STATUSES = {"completed", "outcome_recorded", "cancelled", "failed"}

logger = logging.getLogger("win_trigger")


def _latest_runs(loop: str) -> list[dict]:
    if not RUNS_LEDGER.exists():
        return []
    runs = []
    with open(RUNS_LEDGER, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("loopId") == loop:
                runs.append(rec)
    runs.sort(key=lambda r: r.get("createdAt") or r.get("updatedAt") or "")
    return runs


def _run_pending(loop: str) -> bool:
    latest = _latest_runs(loop)
    if not latest:
        return False
    return latest[-1].get("status") not in TERMINAL_RUN_STATUSES


def _gsc_summary() -> dict:
    if not GSC_SUMMARY.exists():
        return {}
    try:
        return json.loads(GSC_SUMMARY.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        logger.warning("gsc summary unreadable: %s", exc)
        return {}


def _win_command() -> list[str]:
    if REPO_ROOT.joinpath(".win").exists():
        if sys.platform == "win32":
            cmd = shutil.which("win.cmd")
            if cmd:
                return [cmd]
            return ["cmd", "/c", "win.cmd"]  # rely on PATH resolution via cmd
        return [shutil.which("win") or "win"]
    return []


def _trigger_seo_growth(summary: dict, dry_run: bool = False) -> str:
    clicks = int(summary.get("total_clicks", 0) or 0)
    impressions = int(summary.get("total_impressions", 0) or 0)

    if impressions < MIN_IMPRESSIONS and clicks < MIN_CLICKS:
        msg = (
            "skip: below threshold "
            "(clicks=%d, impressions=%d, min=%d/%d)"
            % (clicks, impressions, MIN_CLICKS, MIN_IMPRESSIONS)
        )
        logger.info("win_trigger %s", msg)
        return msg

    if _run_pending("seo-growth"):
        msg = "skip: seo-growth run already pending"
        logger.info("win_trigger %s", msg)
        return msg

    cmd = _win_command()
    if not cmd:
        msg = "skip: win CLI not reachable (no .win or no win.cmd)"
        logger.info("win_trigger %s", msg)
        return msg

    signal = (
        "GSC 30d evidence crossed threshold: %d clicks, %d impressions; "
        "run SEO growth cycle" % (clicks, impressions)
    )
    if dry_run:
        msg = "dry-run: would trigger -> " + signal
        logger.info("win_trigger %s", msg)
        return msg

    full = cmd + [
        "run", "seo-growth", "--repo", str(REPO_ROOT),
        "--trigger", "signal", "--signal", signal,
    ]
    try:
        proc = subprocess.run(full, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        msg = "trigger crashed: %s" % exc
        logger.warning("win_trigger %s", msg)
        return msg
    if proc.returncode != 0:
        msg = "trigger failed (%d): %s" % (proc.returncode, (proc.stderr or proc.stdout).strip()[:200])
        logger.warning("win_trigger %s", msg)
        return msg
    msg = "triggered win run seo-growth: " + signal
    logger.info("win_trigger %s", msg)
    return msg


def main() -> int:
    ap = argparse.ArgumentParser(description="Bridge Abvorn data to win.sh loop run briefs")
    ap.add_argument("--loop", default="seo-growth", help="loop id to trigger")
    ap.add_argument("--dry-run", action="store_true", help="report intent without creating a brief")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        filename=str(REPO_ROOT / "data" / "win_trigger.log"),
        filemode="a",
    )
    if args.loop != "seo-growth":
        logger.warning("win_trigger loop %s not implemented; only seo-growth", args.loop)
        return 0

    summary = _gsc_summary()
    _trigger_seo_growth(summary, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())