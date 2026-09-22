#!/usr/bin/env bash
# Sync the live Abvorn runtime (/opt/abvorn-core) from the GitHub main branch.
# Mirrors sync-abvorn.sh (site) for the daemon runtime code. On a new commit:
#   pull -> mirror flat package -> reinstall deps -> import-validate -> restart daemon.
# Import validation is the canary: a broken tree NEVER restarts the daemon.
# The no-op gate is a DEPLOY MARKER (/.deployed_commit), not "repo-src == origin main":
# repo-src can legitimately sit at origin/main without the flat package/daemon
# having that commit (e.g. commit fetched into repo-src directly). We deploy any
# commit whose hash != marker, so a deployed flat copy can never silently drift.
set -euo pipefail

REPO=/opt/abvorn-core/repo-src
FLAT=/opt/abvorn-core/abvorn
VENV=/opt/abvorn-core/venv
LOG=/var/log/abvorn-runtime-sync.log
ENV_FILE=/opt/abvorn-core/.env
MARKER=/opt/abvorn-core/.deployed_commit

notify() {
  local text="$1"
  local token chat
  token=$(grep -E '^TELEGRAM_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2-)
  chat=$(grep -E '^TELEGRAM_CHAT_ID=' "$ENV_FILE" | head -1 | cut -d= -f2-)
  if [ -n "$token" ] && [ -n "$chat" ]; then
    curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
      -d "chat_id=${chat}" --data-urlencode "text=🚨 Abvorn runtime sync: ${text}" >/dev/null 2>&1 || true
  fi
}

{
  echo "--- $(date -u +%FT%TZ) ---"
  cd "$REPO"
  git fetch origin main 2>&1 || { echo "fetch failed"; notify "fetch failed"; exit 1; }
  NEW=$(git rev-parse FETCH_HEAD)
  DEPLOYED=$(cat "$MARKER" 2>/dev/null || echo none)
  if [ "$NEW" = "$DEPLOYED" ]; then
    echo "runtime already deployed at $(git rev-parse --short "$NEW")"
    exit 0
  fi

  OLD=$(git rev-parse HEAD)
  echo "runtime sync: $(git rev-parse --short "$OLD") -> $(git rev-parse --short "$NEW")"
  git reset --hard "$NEW"

  echo "mirroring flat package"
  rsync -a --delete --exclude __pycache__ "$REPO/abvorn/" "$FLAT/" 2>&1
  cp -f "$REPO/run_daemon.py" /opt/abvorn-core/run_daemon.py
  [ -f "$REPO/run_evolution.py" ] && cp -f "$REPO/run_evolution.py" /opt/abvorn-core/run_evolution.py || true

  # The daemon imports run_cycle.build_*_page and src.* (deployment, warm_editorial,
  # humanizer, ...) everywhere: deploy_content, deploy_category_page, deploy_category_hub,
  # social, crm. Without them every category/hub/article deploy throws
  # "No module named 'run_cycle'" (or resolves a stale /opt/abvorn-core/src) and the site
  # silently keeps the old pages. Mirror both so the runtime matches the repo.
  cp -f "$REPO/run_cycle.py" /opt/abvorn-core/run_cycle.py
  rsync -a --delete --exclude __pycache__ "$REPO/src/" /opt/abvorn-core/src/ 2>&1

  echo "reinstalling deps"
  "$VENV/bin/pip" install -q -r "$REPO/requirements.txt" 2>&1 || { echo "pip failed"; notify "pip install failed"; exit 1; }

  echo "import validation (canary)"
  cd /opt/abvorn-core
  if ! "$VENV/bin/python" -c 'import src.deployment, run_cycle; print("import OK")' >/dev/null 2>&1; then
    echo "IMPORT FAILED - keeping old daemon running"; notify "import validation FAILED - daemon not restarted"; exit 1
  fi

  echo "restarting abvorn-daemon"
  if ! sudo -n systemctl restart abvorn-daemon; then
    echo "daemon restart failed"; notify "daemon restart failed"; exit 1
  fi
  sleep 3
  sudo -n systemctl is-active abvorn-daemon

  echo "$NEW" | sudo -n tee "$MARKER" >/dev/null
  echo "runtime synced to $(git -C "$REPO" rev-parse --short HEAD)"
  notify "synced to $(git -C "$REPO" rev-parse --short HEAD)"
} >> "$LOG" 2>&1