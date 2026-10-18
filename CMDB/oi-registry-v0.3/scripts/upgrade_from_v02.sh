#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${OI_REGISTRY_TARGET:-/home/admsec/ZGT/CMDB/oi-registry-v0.1}"
if [[ ! -s "$TARGET/.env" || ! -f "$TARGET/compose.yaml" ]]; then
  echo "ERROR: Existing OI Registry directory with .env not found: $TARGET" >&2; exit 1
fi
for bin in docker python3 tar; do command -v "$bin" >/dev/null || { echo "Missing $bin" >&2; exit 1; }; done
cd "$TARGET"
docker compose config -q
if ! docker compose exec -T oi-db pg_isready -U oi_registry -d oi_registry >/dev/null; then
 echo 'ERROR: oi-db not ready';exit 1
fi
if ! docker compose exec -T oi-api python -c 'import urllib.request;urllib.request.urlopen("http://127.0.0.1:8000/api/health/ready",timeout=5)' >/dev/null 2>&1; then
 echo 'ERROR: current API not healthy';exit 1
fi
REV="$(docker compose exec -T oi-api alembic current 2>&1)"
if ! grep -q '0003_asset_lifecycle' <<<"$REV"; then
 echo "ERROR: v0.3 upgrade requires v0.2 installed (0003_asset_lifecycle). Current: $REV" >&2
 echo "First run the v0.2 upgrade package; do not delete any volumes." >&2
 exit 1
fi
printf '==> 1/6: Backing up database and original documents\n'
bash scripts/backup.sh
STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="backups/pre-v03-code-${STAMP}.tar.gz"
tar -czf "$ARCHIVE" backend frontend
chmod 600 "$ARCHIVE"
printf 'Code backup: %s\n' "$TARGET/$ARCHIVE"
printf '==> 2/6: Installing source code\n'
cp -a "$SOURCE/backend/app/." "$TARGET/backend/app/"
cp -a "$SOURCE/backend/migrations/." "$TARGET/backend/migrations/"
cp -a "$SOURCE/frontend/." "$TARGET/frontend/"
cp -a "$SOURCE/tests/test_governance.py" "$TARGET/tests/test_governance.py"
printf '==> 3/6: Building API image\n'
docker compose build oi-api
printf '==> 4/6: Stopping API for schema migration\n'
docker compose stop oi-api
docker compose run --rm --no-deps oi-api alembic upgrade head
printf '==> 5/6: Starting API with new schema\n'
docker compose up -d --no-deps --force-recreate oi-api
READY=0
for _ in $(seq 1 60); do
 if docker compose exec -T oi-api python -c 'import urllib.request;urllib.request.urlopen("http://127.0.0.1:8000/api/health/ready",timeout=4)' >/dev/null 2>&1; then READY=1;break;fi
 sleep 2
done
if [[ "$READY" != 1 ]]; then
 echo 'ERROR: API did not become ready. Run: docker compose logs --tail=100 oi-api' >&2
 echo 'Backups preserved. Do not delete volumes.' >&2
 exit 1
fi
printf '==> 6/6: Verifying migration\n'
docker compose exec -T oi-api alembic current
bash scripts/smoke_v03.sh
printf '\nUpgrade completed. Open: http://127.0.0.1:8085 (Ctrl+Shift+R).\n'
