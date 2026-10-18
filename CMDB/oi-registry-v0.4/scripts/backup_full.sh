#!/usr/bin/env bash
# OI Registry centralized consistent snapshot.
set -Eeuo pipefail
umask 077
TARGET="${OI_REGISTRY_TARGET:-/home/admsec/ZGT/CMDB/oi-registry-v0.1}"
DEST="${OI_BACKUP_DIR:-/home/admsec/ZGT/CMDB/BACKUPS}"
[[ "$DEST" = /* && "$TARGET" = /* ]] || { echo 'TARGET and BACKUP_DIR must be absolute paths' >&2; exit 1; }
[[ -s "$TARGET/.env" && -f "$TARGET/compose.yaml" ]] || { echo "Installed OI Registry not found: $TARGET" >&2; exit 1; }
[[ "$DEST" != "$TARGET"* ]] || { echo 'Backup destination must be outside the application directory' >&2; exit 1; }
for exe in docker python3 tar sha256sum flock; do command -v "$exe" >/dev/null || { echo "Missing: $exe" >&2; exit 1; }; done
mkdir -p "$DEST"
chmod 700 "$DEST"
# One backup process per installation; prevents overlapping writes.
exec 9>"$DEST/.oi-registry-backup.lock"
flock -n 9 || { echo 'Another OI backup is already running' >&2; exit 1; }
cd "$TARGET"
docker compose config -q
docker compose exec -T oi-db pg_isready -U oi_registry -d oi_registry >/dev/null
STAMP="$(date +%Y%m%d-%H%M%S)"
WORK="$(mktemp -d "$DEST/.backup-in-progress-${STAMP}-XXXXXXXX")"
ARCHIVE="$DEST/oi-registry-${STAMP}.tar.gz"
TMP_ARCHIVE="$DEST/.oi-registry-${STAMP}.$$.tar.gz.tmp"
STOPPED=()
finish() {
  rc=$?
  trap - EXIT INT TERM
  if ((${#STOPPED[@]})); then
    echo 'Restarting previously running OI Registry services...'
    if ! docker compose start "${STOPPED[@]}"; then
      echo 'ATTENTION: Could not restart OI Registry services. Start them manually.' >&2
      rc=1
    fi
  fi
  if [[ -n "${WORK:-}" && -d "$WORK" ]]; then rm -rf -- "$WORK"; fi
  [[ -n "${TMP_ARCHIVE:-}" ]] && rm -f -- "$TMP_ARCHIVE"
  exit "$rc"
}
trap finish EXIT INT TERM
# Prevent DB->attachment mismatch: no API writes while snapshotting.
services="$(docker compose config --services)"
for service in oi-api oi-worker; do
  if grep -Fxq "$service" <<< "$services"; then
    if docker compose ps --status running --services | grep -Fxq "$service"; then
      STOPPED+=("$service")
    fi
  fi
done
if ((${#STOPPED[@]})); then
  echo "Temporarily stopping writers: ${STOPPED[*]}"
  docker compose stop "${STOPPED[@]}"
fi
printf 'Backing up PostgreSQL...\n'
docker compose exec -T oi-db pg_dump -U oi_registry -d oi_registry -Fc > "$WORK/database.dump"
[[ -s "$WORK/database.dump" ]] || { echo 'Empty PostgreSQL dump' >&2; exit 1; }
# pg_restore -l validates the custom dump header/catalog.
docker compose exec -T oi-db pg_restore -l < "$WORK/database.dump" >/dev/null
printf 'Backing up original documents...\n'
# One-shot container mounts exact same Docker volume without starting API.
docker compose run --rm --no-deps -T --entrypoint python oi-api -c \
'import sys,tarfile; f=tarfile.open(fileobj=sys.stdout.buffer,mode="w|gz");f.add("/data/documents",arcname="documents",recursive=True);f.close()' \
> "$WORK/documents.tar.gz"
[[ -s "$WORK/documents.tar.gz" ]] || { echo 'Empty document backup stream' >&2; exit 1; }
# Save release, compose and scripts; exclude application runtime secrets & old backup directory.
files=(backend frontend compose.yaml nginx.conf scripts)
for optional in README-START.md docs RELEASE_SHA256.txt compose.override.yaml; do [[ -e "$optional" ]] && files+=("$optional"); done
tar --create --gzip --file "$WORK/application.tar.gz" "${files[@]}"
cp -- .env "$WORK/config.env"
chmod 600 "$WORK"/*
export OI_BK_TEMP="$WORK" OI_BK_STAMP="$STAMP"
python3 - <<'PY'
import hashlib,json,os,pathlib,datetime
root=pathlib.Path(os.environ['OI_BK_TEMP'])
names=['database.dump','documents.tar.gz','application.tar.gz','config.env']
entries=[]
for name in names:
    h=hashlib.sha256(); size=0
    with (root/name).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            size+=len(block);h.update(block)
    entries.append({'file':name,'sha256':h.hexdigest(),'size':size})
manifest={'format':'oi-registry-backup','format_version':1,
 'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'includes':['PostgreSQL logical dump','Document volume','Application source','Private environment'],
 'files':entries,'restore_note':'Use docs/RESTORE.md; do not overwrite running volumes.'}
(root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
PY
printf 'Packaging one complete backup file...\n'
tar -czf "$TMP_ARCHIVE" -C "$WORK" database.dump documents.tar.gz application.tar.gz config.env manifest.json
tar -tzf "$TMP_ARCHIVE" > /dev/null
chmod 600 "$TMP_ARCHIVE"
# Avoid silently replacing backup if two invocations share a second.
if [[ -e "$ARCHIVE" ]]; then echo "Backup already exists: $ARCHIVE" >&2; exit 1; fi
mv -- "$TMP_ARCHIVE" "$ARCHIVE"
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
chmod 600 "$ARCHIVE.sha256"
printf '\nBACKUP OK: %s\nCHECKSUM: %s\n' "$ARCHIVE" "$ARCHIVE.sha256"
printf 'Copy both files to a protected external location. The archive contains sensitive credentials.\n'
