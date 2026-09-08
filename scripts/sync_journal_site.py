"""sync_journal_site.py — Server-side Evolution Journal sync + publish.

Runs on the VPS as a recurring systemd job (abvorn-journal-sync). One-shot
pipeline that keeps the journal page genuinely live:

  1. Harvest fresh runtime signals from the daemon's data dir
     (/opt/abvorn-core/data) — GSC insights, relentless drive actions, daily
     reflections — and append them to the repo-tracked
     data/evolution_journal.json (via ABVORN_JOURNAL_PATH).
  2. Mirror the same journal into the runtime data dir so the live
     /api/evolution/public poll reads the identical entries.
  3. Rebuild docs/journal/index.html from the refreshed journal (through
     write_checked, so the mojibake guard still applies).
  4. Commit + push to origin main; nginx + GitHub Pages pick it up.

Idempotent: append_entry skips rows already represented, and an unchanged
journal produces no commit. Never raises past the gate checks.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("sync_journal_site")

REPO_DIR = Path("/opt/abvorn-core/repo-src")
RUNTIME_DATA = Path("/opt/abvorn-core/data")
SITE_BASE = os.environ.get("SITE_URL", "https://abvorn.com").rstrip("/")

# Target the repo-tracked journal for both harvest and page rebuild.
os.environ["ABVORN_JOURNAL_PATH"] = str(REPO_DIR / "data" / "evolution_journal.json")
# Make the repo's abvorn/ + src/ packages importable regardless of CWD.
sys.path.insert(0, str(REPO_DIR))


def _git(cmd: list, repo_dir: Path, check: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_dir), *cmd],
            capture_output=True,
            text=True,
            check=check,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        logger.warning("git %s failed: %s", " ".join(cmd), e.stderr.strip())
        raise


def main() -> int:
    # Repo must exist and be on main (deploy source of truth).
    if not (REPO_DIR / ".git").exists():
        logger.error("repo-src missing: %s", REPO_DIR)
        return 1

    # Base the commit on the current origin/main. The runtime-sync timer
    # hard-resets repo-src to origin/main every ~10 min, so regenerate on a
    # clean tree each run instead of rebasing onto local work.
    try:
        _git(["fetch", "origin"], REPO_DIR)
        _git(["reset", "--hard", "origin/main"], REPO_DIR)
        _git(["clean", "-fd", "docs/journal", "data/evolution_journal.json"], REPO_DIR, check=False)
    except Exception as e:
        logger.error("repo reset failed: %s", e)
        return 1

    # Sync the tracked journal from real runtime signals.
    try:
        from abvorn.core import journal_sync

        added = journal_sync.sync_journal_from_sources(RUNTIME_DATA)
        logger.info("harvested %d new journal entries", added)
    except Exception as e:
        logger.error("journal harvest failed: %s", e)
        return 1

    # Mirror the tracked journal into the runtime data dir so the live poll
    # and the built page read the same entries.
    tracked = REPO_DIR / "data" / "evolution_journal.json"
    runtime_copy = RUNTIME_DATA / "evolution_journal.json"
    if tracked.exists():
        try:
            shutil.copy2(tracked, runtime_copy)
            logger.info("mirrored journal -> %s", runtime_copy)
        except Exception as e:
            logger.warning("journal mirror failed: %s", e)

    # Rebuild the journal page from the refreshed snapshot.
    try:
        os.chdir(REPO_DIR)
        from src.deployment import build_journal_page, write_checked

        journal_dir = REPO_DIR / "docs" / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        write_checked(journal_dir / "index.html", build_journal_page(SITE_BASE), "journal page")
        logger.info("rebuilt docs/journal/index.html")
    except Exception as e:
        logger.error("journal page rebuild failed: %s", e)
        return 1

    # Nothing to publish when the harvest + rebuild changed nothing.
    changed = _git(["status", "--porcelain"], REPO_DIR).stdout
    touched = [l for l in changed.splitlines() if "evolution_journal.json" in l
               or "docs/journal/index.html" in l]

    if not touched:
        logger.info("no journal changes to publish")
        return 0

    # Commit + push (one retry against a concurrent push from CI).
    try:
        _git(["add", "data/evolution_journal.json", "docs/journal/index.html"], REPO_DIR)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        _git(["commit", "-m", f"journal: sync live evolution entries ({stamp})"], REPO_DIR)
        for attempt in range(2):
            try:
                _git(["push", "origin", "main"], REPO_DIR)
                break
            except Exception:
                if attempt == 0:
                    _git(["fetch", "origin"], REPO_DIR)
                    _git(["rebase", "origin/main"], REPO_DIR)
                else:
                    raise
        logger.info("pushed journal sync to origin/main")
    except Exception as e:
        logger.error("journal sync publish failed: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())