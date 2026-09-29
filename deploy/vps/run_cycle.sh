#!/usr/bin/env bash
# Abvorn content cycle runner for the VPS.
# Pulls latest, heals encoding, generates content, commits, and pushes back
# to GitHub (which redeploys the live site). Notifies Telegram on failure.
set -euo pipefail

# The live install is /opt/abvorn-core; the old /opt/abvorn/abvorn path no longer
# exists on the host, so a hardcoded cd here aborted the cycle on the first line.
ABVORN_ROOT="${ABVORN_ROOT:-/opt/abvorn-core}"
ABVORN_PYTHON="${ABVORN_PYTHON:-${ABVORN_ROOT}/venv/bin/python}"

cd "$ABVORN_ROOT"

set -a
if [ -f .env ]; then
  # shellcheck source=/dev/null
  . ./.env
fi
set +a

git pull --rebase --autostash >/dev/null 2>&1 || true

python() { "$ABVORN_PYTHON" "$@"; }

python scripts/check_publish_content.py --fix >/dev/null 2>&1 || true

CODE=0
python run_cycle.py --batch > data/cycle-run.log 2>&1 || CODE=$?
if [ "$CODE" -ne 0 ]; then
  if [ -n "${TELEGRAM_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      --data-urlencode "text=🚨 Abvorn VPS content cycle failed (exit ${CODE}). Log: ${ABVORN_ROOT}/data/cycle-run.log" \
      -d "parse_mode=HTML" >/dev/null 2>&1 || true
  fi
  exit "$CODE"
fi

python scripts/check_publish_content.py >/dev/null 2>&1 || true

for p in docs/ data/; do
  [ -e "$p" ] && git add "$p"
done

if git diff --cached --quiet; then
  echo "No changes to commit"
else
  git -c user.name="Abvorn Bot" -c user.email="bot@abvorn.com" \
    commit -m "chore: content cycle $(date -u +'%Y-%m-%d %H:%M UTC')"
  git push
fi

echo "Content cycle complete $(date -u +'%Y-%m-%d %H:%M UTC')"