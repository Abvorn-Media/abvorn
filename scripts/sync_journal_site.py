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

REPO_DIR = Path(os.environ.get("ABVORN_SYNC_REPO_DIR", "/opt/abvorn-core/repo-src"))
RUNTIME_DATA = Path(os.environ.get("ABVORN_SYNC_DATA_DIR", "/opt/abvorn-core/data"))
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


def mirror_journal(tracked: Path, runtime_copy: Path) -> bool:
    """Copy the tracked journal into the runtime dir unless they are the same
    file — the local task points both env vars at one checkout, and copy2 onto
    itself raises WinError 32."""
    if not tracked.exists() or tracked.resolve() == runtime_copy.resolve():
        return False
    try:
        shutil.copy2(tracked, runtime_copy)
        logger.info("mirrored journal -> %s", runtime_copy)
        return True
    except Exception as e:
        logger.warning("journal mirror failed: %s", e)
        return False


def changed_journal_paths(repo_dir: Path) -> list[str]:
    """The two files this job owns that actually changed, as repo-relative paths."""
    changed = _git(["status", "--porcelain"], repo_dir).stdout
    lines = changed.splitlines()
    paths = []
    if any("evolution_journal.json" in line for line in lines):
        paths.append("data/evolution_journal.json")
    if any("docs/journal/index.html" in line for line in lines):
        paths.append("docs/journal/index.html")
    return paths


def publish_via_api(repo_dir: Path, changed: list[str], message: str, secrets: dict = None) -> bool:
    """Commit the changed journal files through the GitHub API.

    git-over-HTTPS to github.com times out on the local Windows host (while
    api.github.com works), so the Task Scheduler mirror clone can no longer
    push. GitHubDeployer._commit_file re-reads the branch head on every attempt,
    which also survives concurrent CI/deploy commits.
    """
    if secrets is None:
        from abvorn.core.secrets import load_secrets

        secrets = load_secrets()
    token = secrets.get("GITHUB_TOKEN", "")
    repo_name = secrets.get("GITHUB_REPO", "Abvorn-Media/abvorn")
    if not token:
        logger.error("journal API publish needs GITHUB_TOKEN")
        return False
    try:
        from github import Github

        from abvorn.deploy.github import GitHubDeployer

        repo = Github(token).get_repo(repo_name)
        deployer = GitHubDeployer(token=token, repo=repo_name)
        for rel in changed:
            path = repo_dir / rel
            deployer._commit_file(repo, rel, path.read_text(encoding="utf-8"), message)
        logger.info("published %d journal file(s) via GitHub API", len(changed))
        return True
    except Exception as e:
        logger.error("journal API publish failed: %s", e)
        return False


def prepare_repo(repo_dir: Path, publish_api: bool = False) -> bool:
    """Put the build source at a clean origin/main snapshot.

    CI/VPS use git, where egress works. The local Windows host cannot reach
    github.com over git HTTPS (the mirror push timed out after 300s), so API
    mode builds from the current local checkout instead of fetching.
    """
    if publish_api:
        logger.info("API publish mode: building from local checkout (no git fetch/reset)")
        return True
    try:
        _git(["fetch", "origin"], repo_dir)
        _git(["reset", "--hard", "origin/main"], repo_dir)
        _git(["clean", "-fd", "docs/journal", "data/evolution_journal.json"], repo_dir, check=False)
    except Exception as e:
        logger.error("repo reset failed: %s", e)
        return False
    return True


def main(argv: list[str] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    publish_api = "--publish-api" in argv

    # Repo must exist and be on main (deploy source of truth).
    if not (REPO_DIR / ".git").exists():
        logger.error("repo-src missing: %s", REPO_DIR)
        return 1

    if not prepare_repo(REPO_DIR, publish_api=publish_api):
        return 1

    # Refresh neural-memory graph stats from the repo on disk so the journal
    # page embeds live counters. graphify-out/ and data/neural_memory_state.json
    # are gitignored, so the refresh must run wherever the repo actually lives
    # (this script, on the VPS, or on a GitHub Actions runner). Best-effort: a
    # missing graphifyy install skips the refresh without failing the sync.
    try:
        os.chdir(REPO_DIR)
        from abvorn.core.neural_memory import NeuralMemory

        memory = NeuralMemory(str(REPO_DIR))
        result = memory.ingest_all()
        counts = {
            k: (v.get("entities"), v.get("relationships"))
            for k, v in result.items()
            if isinstance(v, dict)
        }
        logger.info("graph refresh: %s", counts)
    except Exception as e:
        logger.warning("graph refresh skipped: %s", e)

    # Mirror the freshly computed graph state into the runtime data dir so the
    # harvest stamps live counters onto any new entries it appends.
    fresh_state = REPO_DIR / "data" / "neural_memory_state.json"
    runtime_state = RUNTIME_DATA / "neural_memory_state.json"
    if fresh_state.exists() and fresh_state.resolve() != runtime_state.resolve():
        try:
            RUNTIME_DATA.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fresh_state, runtime_state)
            logger.info("graph state mirrored -> %s", runtime_state)
        except Exception as e:
            logger.warning("graph state mirror failed: %s", e)

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
    mirror_journal(REPO_DIR / "data" / "evolution_journal.json", RUNTIME_DATA / "evolution_journal.json")

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
    changed_paths = changed_journal_paths(REPO_DIR)
    if not changed_paths:
        logger.info("no journal changes to publish")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit_message = f"journal: sync live evolution entries ({stamp})"

    # Local host cannot reach github.com over git HTTPS. Publish through the
    # API instead; CI keeps using the git path below (it has working git egress).
    if publish_api:
        if publish_via_api(REPO_DIR, changed_paths, commit_message):
            logger.info("pushed journal sync to origin/main via API")
            return 0
        return 1

    # Commit + push (one retry against a concurrent push from CI).
    try:
        _git(["add", "data/evolution_journal.json", "docs/journal/index.html"], REPO_DIR)
        _git(["commit", "-m", commit_message], REPO_DIR)
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