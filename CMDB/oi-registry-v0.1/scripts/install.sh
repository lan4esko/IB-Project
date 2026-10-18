#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
umask 077
if [[ ! -f .env ]]; then
  python3 - <<'PY'
import secrets
from pathlib import Path
Path('.env').write_text('OI_DB_PASSWORD='+secrets.token_hex(32)+'\nOI_SESSION_SECRET='+secrets.token_hex(48)+'\nOI_COOKIE_SECURE=false\nOI_PORT=8085\n')
PY
  chmod 600 .env
  echo 'Created private .env'
else
  echo 'Using existing .env (unchanged)'
fi
for program in docker python3; do
  command -v "$program" >/dev/null || { echo "Missing program: $program"; exit 1; }
done
docker compose config -q
docker compose up -d --build
ready=0
for _ in $(seq 1 45); do
  if docker compose exec -T oi-api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=3)" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
if [[ "$ready" != "1" ]]; then
  echo 'API did not become ready. Inspect: docker compose logs --tail 80 oi-api' >&2
  exit 1
fi
printf '\nBrowser: http://127.0.0.1:8085\n'
printf 'Create admin: bash scripts/create_admin.sh\n'
printf 'If backend is starting, wait for its healthcheck.\n'
