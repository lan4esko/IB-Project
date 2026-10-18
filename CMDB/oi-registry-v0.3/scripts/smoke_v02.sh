#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
check=$(docker compose exec -T oi-api alembic current)
printf '%s\n' "$check"
if [[ "$check" != *"0003_asset_lifecycle"* ]]; then echo 'Unexpected Alembic revision' >&2; exit 1; fi
curl -fsS http://127.0.0.1:8085/api/health/ready
printf '\n'
code=$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8085/api/inspections/quarterly-status)
if [[ "$code" != "401" ]]; then echo "Unauthenticated inspections HTTP $code, expected 401" >&2; exit 1; fi
printf 'OI Registry v0.2 smoke OK (unauthenticated inspection access: HTTP %s)\n' "$code"
