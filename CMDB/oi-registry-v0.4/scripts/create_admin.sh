#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
read -rp 'Username [admin]: ' username
username="${username:-admin}"
read -rsp 'Password (min. 12 chars): ' password
printf '\n'
if [[ ${#password} -lt 12 ]]; then echo 'Password too short' >&2; exit 1; fi
printf '%s\n' "$password" | docker compose exec -T oi-api python -m app.admin "$username" admin
unset password
