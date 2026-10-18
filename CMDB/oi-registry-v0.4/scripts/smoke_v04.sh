#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose exec -T oi-api alembic current
docker compose exec -T oi-api python - <<'PYCHECK'
import urllib.request, urllib.error, json
base='http://127.0.0.1:8000'
for path in ('/api/health/ready','/api/automation/preview'):
    try:
        with urllib.request.urlopen(base+path,timeout=10) as r:
            print(path,r.status,json.load(r))
    except urllib.error.HTTPError as e:
        if path=='/api/automation/preview' and e.code==401:
            print(path,'401 unauthenticated expected')
        else:raise
PYCHECK
