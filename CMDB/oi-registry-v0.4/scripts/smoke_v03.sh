#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose config -q
docker compose exec -T oi-api python - <<'PY'
import urllib.request
for path in ('/api/health/live','/api/health/ready'):
    url='http://127.0.0.1:8000'+path
    with urllib.request.urlopen(url,timeout=10) as r:
        print(path,r.status,r.read().decode())
PY
docker compose exec -T oi-api alembic current
