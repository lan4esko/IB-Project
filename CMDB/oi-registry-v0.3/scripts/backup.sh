#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
umask 077
mkdir -p backups
stamp="$(date +%Y%m%d-%H%M%S)"
pgfile="backups/oi-registry-$stamp.dump"
filesfile="backups/oi-documents-$stamp.tar.gz"
docker compose exec -T oi-db pg_dump -U oi_registry -d oi_registry -Fc > "$pgfile"
test -s "$pgfile" || { echo 'Database backup failure' >&2; exit 1; }
docker compose exec -T oi-api python -c 'import tarfile,sys; t=tarfile.open(fileobj=sys.stdout.buffer,mode="w|gz"); t.add("/data/documents",arcname="documents"); t.close()' > "$filesfile"
test -s "$filesfile" || { echo 'Document backup failure' >&2; exit 1; }
chmod 600 "$pgfile" "$filesfile"
sha256sum "$pgfile" "$filesfile"
printf '\nDatabase: %s\nDocuments: %s\nKeep both files together and test restoration on a separate stand.\n' "$pgfile" "$filesfile"
