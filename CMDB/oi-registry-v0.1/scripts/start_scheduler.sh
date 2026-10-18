#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose config -q
docker compose --profile automation up -d --no-deps oi-worker
docker compose --profile automation ps oi-worker
echo 'Daily local planning is enabled. No automatic OpenProject publication.'
