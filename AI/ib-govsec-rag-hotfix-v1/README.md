# IB Platform: GovSec RAG hotfix v1

Исправления для установленных `ib-govsec-rag-corpus-v1` и FastAPI v0.5 + AI Gateway.

- `govsec.py`: сохраняет пустые страницы из `pdftotext` и сверяет число страниц через `pdfinfo`; теперь сканированные PDF можно направлять в Tesseract OCR. Без исправления из 19 PDF в индекс попали только 17: `fstec-137-2026` и `fsb-77` остались без текста.
- `rag.py`: временно повышает лимит сканируемых кандидатов с 2 000 до 5 000 (макс. 10 000 через `IB_RAG_MAX_CANDIDATES`). Ранние документы больше не выпадают из выдачи только из-за порядка загрузки. Это пилотный обход, не полноценный поисковый индекс PostgreSQL.

Оригиналы PDF, PostgreSQL, OpenProject, `compose*.yaml`, `.env`, Ollama и Document Hub не затрагиваются. Изменяемые исходники автоматически копируются в `.pre-hotfix-TIMESTAMP.bak`. Установщик проверяет точное совпадение исходного фрагмента; на другой версии откажется изменять файл.

## 1. Применить

```bash
cd /home/admsec/ZGT/AI
unzip -n /media/sf_/ib-govsec-rag-hotfix-v1.zip -d /home/admsec/ZGT/AI
python3 /home/admsec/ZGT/AI/ib-govsec-rag-hotfix-v1/scripts/apply.py
```

## 2. Дозапустить OCR **только** для двух отсутствующих актов

```bash
cd /home/admsec/ZGT/AI/ib-govsec-rag-corpus-v1
python3 govsec.py prepare --ocr --id fstec-137-2026 --id fsb-77
python3 - <<'PY'
import json
for row in json.load(open('corpus/prepare_report.json')):
    print(row['id'], row['status'], 'частей:', row.get('parts', 0),
          'страниц без текста:', len(row.get('pages_without_text', [])))
PY
```

`prepare --id` **заменяет** `prepare_report.json` отчётом только для выбранных файлов. Ранее подготовленные Markdown-файлы других НПА остаются на диске.

Если обе записи `prepared` и число страниц без текста `0` (или минимально ожидаемое), запустить импорт:

```bash
python3 govsec.py import --id fstec-137-2026 --id fsb-77
```

Не импортировать файл с `needs_ocr_or_no_text` или `error` без диагностики.

## 3. Пересобрать текущий Gateway/Backend

```bash
cd /home/admsec/ZGT/AI/ib-platform
docker compose -f compose.yaml -f compose.backend.yaml -f compose.postgres.yaml -f compose.auth.yaml -f compose.documents.yaml -f compose.rag.yaml -f compose.gateway.yaml config -q
docker compose -f compose.yaml -f compose.backend.yaml -f compose.postgres.yaml -f compose.auth.yaml -f compose.documents.yaml -f compose.rag.yaml -f compose.gateway.yaml build ib-api
docker compose -f compose.yaml -f compose.backend.yaml -f compose.postgres.yaml -f compose.auth.yaml -f compose.documents.yaml -f compose.rag.yaml -f compose.gateway.yaml up -d --no-deps ib-api
curl -fsS http://127.0.0.1:8001/health/ready
```

Не требуется `alembic upgrade` и перезапуск OpenProject. Заново индексировать уже импортированные части не нужно. Следующий этап: PostgreSQL FTS + проверка редакций + цитирование документов по исходным страницам.
