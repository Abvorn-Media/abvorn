#!/usr/bin/env bash
# Abvorn VPS bootstrap (Oracle Free Tier Ampere A1 / Ubuntu 22.04 ARM).
# Idempotent: safe to re-run.
#
#   sudo bash setup.sh                          # profile build; prompts for secrets
#   sudo bash setup.sh --env-file /tmp/.env     # use a prepared .env
#   sudo bash setup.sh --skip-cycle             # don't run an initial content cycle
#   sudo bash setup.sh --no-daemon              # install cycle only, skip the daemon
#   sudo bash setup.sh --with-evolution         # approve genesis child-core spawn
#
# Installs: python3.11 + deps, git, pango libs, systemd units:
#   abvorn-daemon.service   (24/7 organism)
#   abvorn-cycle.timer      (content cycle every 6h, offset from CI)
set -euo pipefail

APP_DIR="${ABVORN_APP_DIR:-/opt/abvorn}"
APP_USER="${ABVORN_APP_USER:-abvorn}"
REPO_URL="${ABVORN_REPO_URL:-https://github.com/Abvorn-Media/abvorn.git}"
REPO_BRANCH="main"
ENV_FILE=""
SKIP_CYCLE=0
NO_DAEMON=0
WITH_EVOLUTION=0

while [ $# -gt 0 ]; do
  case "$1" in
    --env-file) ENV_FILE="${2:-}"; shift 2 ;;
    --skip-cycle) SKIP_CYCLE=1; shift ;;
    --no-daemon) NO_DAEMON=1; shift ;;
    --with-evolution) WITH_EVOLUTION=1; shift ;;
    *) echo "unknown option: $1"; exit 2 ;;
  esac
done

as_user() { runuser -u "$APP_USER" -- "$@"; }

step() { echo; echo "==> $*"; }

step "Install system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq software-properties-common git curl ca-certificates \
  sqlite3 libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf-2.0-0 >/dev/null
if ! command -v python3.11 >/dev/null 2>&1; then
  add-apt-repository -y ppa:deadsnakes/ppa >/dev/null
  apt-get update -qq
  apt-get install -y -qq python3.11 python3.11-venv python3.11-dev >/dev/null
fi

step "Create app user '$APP_USER'"
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$APP_USER"
fi
mkdir -p "$APP_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

step "Clone or refresh repo"
if [ ! -d "$APP_DIR/abvorn/.git" ]; then
  as_user git clone -b "$REPO_BRANCH" --single-branch "$REPO_URL" "$APP_DIR/abvorn"
else
  as_user git -C "$APP_DIR/abvorn" pull --rebase --autostash
fi
chmod +x "$APP_DIR/abvorn/deploy/vps/run_cycle.sh"

step "Create Python venv + install deps"
if [ ! -x "$APP_DIR/venv/bin/python" ]; then
  as_user python3.11 -m venv "$APP_DIR/venv"
fi
as_user "$APP_DIR/venv/bin/pip" install --upgrade pip -q
as_user "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/abvorn/requirements.txt"

step "Provision .env"
if [ ! -f "$APP_DIR/abvorn/.env" ]; then
  if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$APP_DIR/abvorn/.env"
  else
    cp "$APP_DIR/abvorn/deploy/vps/.env.example" "$APP_DIR/abvorn/.env"
    echo "Please edit $APP_DIR/abvorn/.env to add your secrets, then re-run:"
    echo "  sudo bash $APP_DIR/abvorn/deploy/vps/setup.sh --skip-cycle"
    exit 0
  fi
else
  echo ".env already present (leaving untouched)"
fi

step "Materialize boardroom secrets.json for the daemon"
chmod 600 "$APP_DIR/abvorn/.env"
as_user "$APP_DIR/venv/bin/python" "$APP_DIR/abvorn/deploy/vps/make_secrets_json.py" \
  "$APP_DIR/abvorn/.env" "/home/$APP_USER/.abvorn/boardroom/secrets.json"
chown "$APP_USER:$APP_USER" "/home/$APP_USER/.abvorn/boardroom/secrets.json"
chmod 600 "/home/$APP_USER/.abvorn/boardroom/secrets.json"

if [ "$WITH_EVOLUTION" = "1" ]; then
  step "Approve genesis/evolution entitlements (operator approval)"
  cat > "$APP_DIR/abvorn/data/entitlements_state.json" <<'EOF'
{
  "approved_actions": ["spawn_child", "evolve_generation", "terminate_parent"],
  "approved_at": "operator-approved-via-setup.sh"
}
EOF
  chown "$APP_USER:$APP_USER" "$APP_DIR/abvorn/data/entitlements_state.json"
  echo "WARNING: run_evolution.py may now self-terminate the parent on evolution."
fi

step "Run an initial content cycle (populates state before daemon start)"
if [ "$SKIP_CYCLE" != "1" ]; then
  as_user "$APP_DIR/abvorn/deploy/vps/run_cycle.sh" || true
else
  echo "Skipped (--skip-cycle)"
fi

step "Install systemd units"
SVC="$APP_DIR/abvorn/deploy/vps/systemd"
if [ -f "$SVC/abvorn-cycle.timer" ] && [ -f "$SVC/abvorn-cycle.service" ]; then
  cp "$SVC/abvorn-cycle.timer" "$SVC/abvorn-cycle.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable abvorn-cycle.timer >/dev/null
  systemctl start abvorn-cycle.timer || true
  echo "cycle timer: enabled (next: $(systemctl list-timers abvorn-cycle.timer --no-pager | grep -oP 'in \S+\s+\S+' | head -1 || echo 'see systemctl list-timers'))"
else
  echo "cycle units not found in $SVC — skipped"
fi

if [ "$NO_DAEMON" != "1" ] && [ -f "$SVC/abvorn-daemon.service" ]; then
  cp "$SVC/abvorn-daemon.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable abvorn-daemon >/dev/null
  systemctl start abvorn-daemon || true
  echo "daemon: enabled and started"
else
  echo "daemon: skipped (--no-daemon or unit missing)"
fi

echo
echo "DONE. Useful commands:"
echo "  systemctl status abvorn-daemon abvorn-cycle.timer"
echo "  journalctl -u abvorn-daemon -f"
echo "  journalctl -u abvorn-cycle -f"
echo "Logs for cycles: tail -n 100 $APP_DIR/abvorn/data/cycle-run.log"