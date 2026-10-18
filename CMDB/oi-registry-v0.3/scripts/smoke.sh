#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a
source .env
set +a
curl --fail --silent --show-error "http://127.0.0.1:${OI_PORT:-8085}/api/health/live"
printf '\n'
curl --fail --silent --show-error "http://127.0.0.1:${OI_PORT:-8085}/api/health/ready"
printf '\n'
docker compose ps
