#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null || { echo 'Docker не установлен'; exit 1; }
docker inspect ib-ollama >/dev/null || { echo 'Не найден контейнер ib-ollama'; exit 1; }
docker exec ib-ollama ollama show qwen3:0.6b >/dev/null || { echo 'Сначала загрузите qwen3:0.6b'; exit 1; }
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
while IFS='|' read -r file alias; do
  [[ -z "${file:-}" || "${file:0:1}" == '#' ]] && continue
  { printf 'FROM qwen3:0.6b\nPARAMETER temperature 0.15\nSYSTEM """\n'
    cat prompts/00_SHARED_POLICY.md
    printf '\n'
    cat "prompts/$file"
    printf '\n"""\n'
  } > "$TMP_DIR/Modelfile"
  echo "Создаём профиль $alias (без загрузки модели в RAM)..."
  docker cp "$TMP_DIR/Modelfile" ib-ollama:/tmp/Modelfile-govsec
  docker exec ib-ollama ollama create "$alias" -f /tmp/Modelfile-govsec
  docker exec ib-ollama rm -f /tmp/Modelfile-govsec
  echo "Готово: $alias"
done <<'EOF'
01_REGULATORY_NAVIGATOR.md|ib-gos-regul:0.1
02_GIS_ATTESTATION.md|ib-gos-gis:0.1
03_ISPDN_PRIVACY.md|ib-gos-pdn:0.1
04_KII_GOSSOPKA.md|ib-gos-kii:0.1
05_RECOMMENDATIONS_OPENPROJECT.md|ib-gos-plan:0.1
EOF

echo 'Профили Ollama:'
docker exec ib-ollama ollama list
echo 'Созданы профили на основе qwen3:0.6b. Большие модели не запускались.'
