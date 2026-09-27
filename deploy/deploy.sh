#!/usr/bin/env bash
# One-shot deploy / update on a Linux server (Ubuntu/Debian).
#   bash deploy.sh                 # first run creates .env and stops
#   bash deploy.sh                 # after filling .env: builds and starts
# Env overrides: REPO, BRANCH, DIR, WEB_PORT
set -euo pipefail

REPO="${REPO:-https://github.com/Nikitok95/Robots.git}"
BRANCH="${BRANCH:-claude/macro-dashboard-rates-crypto-4rir90}"
DIR="${DIR:-/opt/macro-dashboard}"

log() { printf '\n==> %s\n' "$*"; }
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

log "Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | $SUDO sh
fi
$SUDO docker compose version >/dev/null

log "Code: $REPO ($BRANCH) -> $DIR"
if [ -d "$DIR/.git" ]; then
  $SUDO git -C "$DIR" fetch origin "$BRANCH"
  $SUDO git -C "$DIR" checkout -B "$BRANCH" "origin/$BRANCH"   # .env is untracked and kept
else
  $SUDO git clone -b "$BRANCH" "$REPO" "$DIR"
fi
cd "$DIR"

if [ ! -f .env ]; then
  $SUDO cp .env.example .env
  $SUDO chmod 600 .env
  log "Created $DIR/.env — fill FRED_API_KEY and SOSOVALUE_API_KEY, then run this script again."
  exit 1
fi
for k in FRED_API_KEY SOSOVALUE_API_KEY; do
  grep -Eq "^$k=.+" .env || echo "WARNING: $k is empty in .env — these metrics will show 'нет данных'"
done

PORT="$(grep -E '^WEB_PORT=' .env | cut -d= -f2)"; PORT="${WEB_PORT:-${PORT:-8080}}"
if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$PORT\$" && ! $SUDO docker compose ps --status running 2>/dev/null | grep -q frontend; then
  echo "ERROR: port $PORT is already used by another service. Set WEB_PORT in .env to a free port." >&2
  exit 1
fi

log "Build and start"
$SUDO docker compose up -d --build

log "Waiting for API"
for i in $(seq 1 60); do
  if curl -fsS "http://localhost:$PORT/api/health" >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS "http://localhost:$PORT/api/health" >/dev/null || { echo "API did not come up; see: docker compose logs backend" >&2; exit 1; }

log "Live source check (python -m app.verify)"
$SUDO docker compose exec -T backend python -m app.verify || true

log "Done: http://$(hostname -I 2>/dev/null | awk '{print $1}'):$PORT"
