#!/usr/bin/env bash
# Upgrade existing working installation /oi-registry-v0.1 (currently v0.3) to v0.4.
set -Eeuo pipefail
umask 077
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${OI_REGISTRY_TARGET:-/home/admsec/ZGT/CMDB/oi-registry-v0.1}"
[[ -f "$TARGET/compose.yaml" && -s "$TARGET/.env" ]] || { echo 'ERROR: existing OI Registry with .env not found' >&2; exit 1; }
for tool in docker tar python3; do command -v "$tool" >/dev/null || { echo "ERROR missing: $tool" >&2; exit 1; }; done
cd "$TARGET"
# Avoid accidental upgrade of an unrelated or already-upgraded installation.
docker compose config -q
CURRENT="$(docker compose exec -T oi-api alembic current 2>&1)"
if ! grep -q '0004_governance' <<< "$CURRENT"; then
  echo "ERROR: expected installed v0.3: 0004_governance, got $CURRENT" >&2
  echo 'Do not run install.sh or delete Docker volumes. Check installed migrations.' >&2
  exit 1
fi
docker compose exec -T oi-db pg_isready -U oi_registry -d oi_registry >/dev/null
printf '==> 1/7 Creating one complete backup in /home/admsec/ZGT/CMDB/BACKUPS\n'
OI_REGISTRY_TARGET="$TARGET" bash "$SOURCE/scripts/backup_full.sh"
printf '==> 2/7 Saving the current API image for recovery\n'
STAMP="$(date +%Y%m%d-%H%M%S)"
OLD_IMAGE="$(docker image inspect oi-registry-oi-api:latest --format '{{.Id}}')"
docker tag "$OLD_IMAGE" "oi-registry-oi-api:pre-v04-$STAMP"
echo "Old image tag: oi-registry-oi-api:pre-v04-$STAMP"
printf '==> 3/7 Updating backend source; .env and Docker volumes unchanged\n'
cp -a "$SOURCE/backend/app/." "$TARGET/backend/app/"
cp -a "$SOURCE/backend/migrations/." "$TARGET/backend/migrations/"
cp -a "$SOURCE/compose.override.yaml" "$TARGET/compose.override.yaml"
cp -a "$SOURCE/scripts/backup_full.sh" "$SOURCE/scripts/verify_backup.sh" "$SOURCE/scripts/smoke_v04.sh" "$SOURCE/scripts/start_scheduler.sh" "$TARGET/scripts/"
cp -a "$SOURCE/tests/test_automation.py" "$TARGET/tests/test_automation.py"
mkdir -p "$TARGET/docs"
cp -a "$SOURCE/docs/AUTOMATION_DESIGN.md" "$SOURCE/docs/BACKUP_AND_RESTORE.md" "$TARGET/docs/"
# Do NOT update frontend until the new API is verified healthy.
docker compose config -q
printf '==> 4/7 Building v0.4 API while previous container is running\n'
docker compose build oi-api
printf '==> 5/7 Stopping API and migrating schema to 0005_automation\n'
docker compose stop oi-api
docker compose run --rm --no-deps oi-api alembic upgrade head
printf '==> 6/7 Restarting API and checking readiness\n'
docker compose up -d --no-deps --force-recreate oi-api
READY=0
for _ in $(seq 1 45); do
  if docker compose exec -T oi-api python -c 'import urllib.request;urllib.request.urlopen("http://127.0.0.1:8000/api/health/ready",timeout=4)' >/dev/null 2>&1; then
    READY=1; break
  fi
  sleep 2
done
if [[ "$READY" != 1 ]]; then
    echo 'ERROR: API not ready. Preserve BACKUPS, check docker compose logs --tail=100 oi-api.' >&2
    exit 1
fi
REV="$(docker compose exec -T oi-api alembic current)"
if ! grep -q '0005_automation' <<< "$REV"; then
  echo "ERROR: expected 0005_automation; received $REV" >&2
  exit 1
fi
printf '==> 7/7 Activating frontend and daily local worker\n'
cp -a "$SOURCE/frontend/." "$TARGET/frontend/"
bash "$TARGET/scripts/start_scheduler.sh"
bash "$TARGET/scripts/smoke_v04.sh"
printf '\nUpgrade OK. OI Registry v0.4: http://127.0.0.1:8085 (Ctrl+Shift+R).\n'
printf 'OpenProject automatic publication is DISABLED by default.\n'
printf 'Backup archive is in /home/admsec/ZGT/CMDB/BACKUPS.\n'
