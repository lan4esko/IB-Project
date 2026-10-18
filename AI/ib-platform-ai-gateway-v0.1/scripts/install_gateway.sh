#!/usr/bin/env bash
set -euo pipefail
PROJECT=${1:-/home/admsec/ZGT/AI/ib-platform}
PACKAGE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$PROJECT"
test -f compose.rag.yaml && test -f backend/app/main.py || { echo 'Нужен развёрнутый backend v0.5' >&2; exit 1; }
if ! grep -q '0004_rag_chunks' backend/app/main.py; then echo 'Версия main.py не похожа на v0.5: установка прервана' >&2; exit 1; fi
if grep -q 'from app.ai_gateway import router' backend/app/main.py; then echo 'Маршруты Gateway уже установлены'; exit 0; fi
stamp=$(date +%Y%m%d-%H%M%S)
cp -p backend/app/main.py "backend/app/main.py.pre-gateway-$stamp"
install -m 0644 "$PACKAGE/backend/app/ai_gateway.py" backend/app/ai_gateway.py
cat >> backend/app/main.py <<'PY'

# Optional AI Gateway for Open WebUI: read-only RAG backed chat profiles.
from app.ai_gateway import router as ai_gateway_router
app.include_router(ai_gateway_router)
PY
install -m 0644 "$PACKAGE/compose.gateway.yaml" compose.gateway.yaml
python3 -m py_compile backend/app/ai_gateway.py backend/app/main.py
umask 077
if ! grep -q '^IB_GATEWAY_API_KEY=' .env; then
  if command -v openssl >/dev/null 2>&1; then
    printf '\nIB_GATEWAY_API_KEY=%s\n' "$(openssl rand -hex 32)" >> .env
  else
    printf '\nIB_GATEWAY_API_KEY=%s\n' "$(python3 -c 'import secrets;print(secrets.token_hex(32))')" >> .env
  fi
fi
chmod 600 .env
printf '%s\n' 'Gateway установлен в исходники. Ключ создан/сохранён в .env (не выводится).'
printf '%s\n' 'Следующий шаг: собрать Docker image через Compose (см. README).'
