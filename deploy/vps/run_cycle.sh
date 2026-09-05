#!/usr/bin/env bash
# Abvorn content cycle runner for the VPS.
# Pulls latest, heals encoding, generates content, commits, and pushes back
# to GitHub (which redeploys the live site). Notifies Telegram on failure.
set -euo pipefail

cd /opt/abvorn/abvorn

set -a
if [ -f .env ]; then
  # shellcheck source=/dev/null
  . ./.env
fi
set +a

git pull --rebase --autostash >/dev/null 2>&1 || true

python() { /opt/abvorn/venv/bin/python "$@"; }

python scripts/check_publish_content.py --fix >/dev/null 2>&1 || true

if ! python run_cycle.py --batch > data/cycle-run.log 2>&1; then
  CODE=$?
  if [ -n "${TELEGRAM_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      --data-urlencode "text=🚨 Abvorn VPS content cycle failed (exit ${CODE}). Log: /opt/abvorn/abvorn/data/cycle-run.log" \
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