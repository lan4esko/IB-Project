#!/usr/bin/env bash
set -euo pipefail
ROOT=${1:-/home/admsec/ZGT/AI/ib-platform}
PACK=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
for file in backend/app/rag.py backend/app/ai_gateway.py backend/app/main.py backend/migrations/versions/0004_rag_chunks.py compose.gateway.yaml; do
  test -f "$file" || { echo "Missing required file: $file" >&2; exit 1; }
done
python3 - "$ROOT" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]); rag=(p/'backend/app/rag.py').read_text(); main=(p/'backend/app/main.py').read_text()
if '0004_rag_chunks' not in main and '0005_russian_fts' not in main:
    raise SystemExit('Неизвестная версия main.py: установка отменена')
if 'def search(' not in rag or 'MAX_CANDIDATES' not in rag:
    raise SystemExit('Неизвестная версия RAG: установка отменена')
if 'ai_gateway_router' not in main:
    raise SystemExit('Gateway v0.1 отсутствует: сначала установите Gateway')
PY
if grep -q '0005_russian_fts' backend/app/main.py && test -f backend/migrations/versions/0005_russian_fts.py; then
  echo 'Код v0.2 уже установлен'; exit 0
fi
umask 077
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p backups
for file in rag.py ai_gateway.py main.py; do
 cp -p "backend/app/$file" "backups/$file.pre-fts-$STAMP"
done
install -m 0644 "$PACK/patches/rag.py" backend/app/rag.py
install -m 0644 "$PACK/patches/ai_gateway.py" backend/app/ai_gateway.py
install -m 0644 "$PACK/patches/0005_russian_fts.py" backend/migrations/versions/0005_russian_fts.py
install -m 0644 "$PACK/patches/compose.gateway-tune.yaml" compose.gateway-tune.yaml
python3 - <<'PY'
from pathlib import Path
p=Path('backend/app/main.py'); s=p.read_text(); needle='version != "0004_rag_chunks"'
if s.count(needle) != 1: raise SystemExit('Не удалось обновить readiness: проверьте файл main.py')
p.write_text(s.replace(needle,'version != "0005_russian_fts"',1))
PY
python3 -m py_compile backend/app/rag.py backend/app/ai_gateway.py backend/app/main.py backend/migrations/versions/0005_russian_fts.py
printf 'Исходники v0.2 установлены, копии: backups/*pre-fts-%s\n' "$STAMP"
printf 'Теперь собери image, останови API, выполни alembic upgrade head и запусти API.\n'
