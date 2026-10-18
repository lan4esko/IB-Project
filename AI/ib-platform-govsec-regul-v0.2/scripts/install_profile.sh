#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null
# Versioned new alias; original ib-gos-regul:0.1 is untouched.
docker exec ib-ollama ollama show qwen3:0.6b >/dev/null
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
{
  printf 'FROM qwen3:0.6b\nPARAMETER temperature 0.1\nPARAMETER num_ctx 2048\nPARAMETER num_predict 192\nSYSTEM """\n'
  cat prompts/SYSTEM.md
  printf '\n"""\n'
} > "$TMP"
docker cp "$TMP" ib-ollama:/tmp/ib-gos-regul-v02-Modelfile >/dev/null
docker exec ib-ollama ollama create ib-gos-regul:0.2 -f /tmp/ib-gos-regul-v02-Modelfile
docker exec ib-ollama rm -f /tmp/ib-gos-regul-v02-Modelfile
printf '\nГотово: ib-gos-regul:0.2. Профиль 0.1 не изменён.\n'
