#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${OI_REGISTRY_TARGET:-/home/admsec/ZGT/CMDB/oi-registry-v0.1}"
if [[ ! -s "$TARGET/.env" || ! -f "$TARGET/compose.yaml" ]]; then
  echo "ERROR: Existing OI Registry v0.1 directory with .env not found: $TARGET" >&2
  exit 1
fi
for bin in docker python3 tar; do command -v "$bin" >/dev/null || { echo "Missing $bin" >&2; exit 1; }; done
cd "$TARGET"
if ! docker compose config -q; then echo 'ERROR: Current Compose configuration broken'; exit 1; fi
if ! docker compose exec -T oi-db pg_isready -U oi_registry -d oi_registry >/dev/null; then
  echo 'ERROR: oi-db must be healthy before upgrade'; exit 1
fi
if ! docker compose exec -T oi-api python -c 'import urllib.request;urllib.request.urlopen("http://127.0.0.1:8000/api/health/ready",timeout=5)' >/dev/null 2>&1; then
  echo 'ERROR: oi-api must be healthy before upgrade'; exit 1
fi

echo '==> 1/6 Backing up PostgreSQL and original documents'
bash scripts/backup.sh
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="backups/pre-v02-sources-${STAMP}.tar.gz"
tar -czf "$BACKUP" backend frontend
chmod 600 "$BACKUP"
echo "Sources backup: $TARGET/$BACKUP"
echo '==> 2/6 Copying release backend while old API is still running'
cp -a "$SOURCE/backend/app/." "$TARGET/backend/app/"
cp -a "$SOURCE/backend/migrations/." "$TARGET/backend/migrations/"
cp -a "$SOURCE/backend/requirements.txt" "$TARGET/backend/requirements.txt"
cp -a "$SOURCE/tests/test_asset_lifecycle.py" "$TARGET/tests/test_asset_lifecycle.py"
cp -a "$SOURCE/tests/test_configuration.py" "$TARGET/tests/test_configuration.py"
echo '==> 3/6 Building API image while old API remains online'
docker compose build oi-api
echo '==> 4/6 Stopping only oi-api and applying migrations'
docker compose stop oi-api
docker compose run --rm --no-deps oi-api alembic upgrade head
echo '==> 5/6 Starting upgraded API'
docker compose up -d --no-deps --force-recreate oi-api
READY=0
for _ in $(seq 1 45); do
 if docker compose exec -T oi-api python -c 'import urllib.request;urllib.request.urlopen("http://127.0.0.1:8000/api/health/ready",timeout=4)' >/dev/null 2>&1; then READY=1; break; fi
 sleep 2
done
if [[ "$READY" != 1 ]]; then
 echo 'ERROR: upgraded API not ready. Inspect: docker compose logs --tail 120 oi-api' >&2
 echo "Recovery backups are in $TARGET/backups. Do NOT erase PostgreSQL volume." >&2
 exit 1
fi
echo '==> 6/6 Updating frontend after API is ready'
cp -a "$SOURCE/frontend/." "$TARGET/frontend/"
docker compose exec -T oi-api alembic current
printf '
Upgrade complete. Browser: http://127.0.0.1:8085
'
printf 'Existing .env, administrator, database, Docker volumes and OpenProject are unchanged.
'
