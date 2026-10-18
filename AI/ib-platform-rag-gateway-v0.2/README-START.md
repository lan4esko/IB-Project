# IB Platform — GovSec RAG + AI Gateway v0.2 (пилот)

Рабочая база: Debian 13, FastAPI v0.5 + AI Gateway v0.1, PostgreSQL 17,
миграция `0004_rag_chunks` и 19 нормативных PDF (2942 фрагмента по журналу).
Не ставить поверх ещё не законченного обновления Document Hub v0.6.

## Что исправлено

1. Лексический поиск в PostgreSQL через `to_tsvector('russian')`,
   `to_tsquery` и GIN-индекс. **Нет ограничения по дате загрузки корпуса**;
   запрос сначала выбирает SQL-кандидатов по всему индексу, затем ранжирует
   до 1200 найденных совпадений. Hybrid остаётся пилотным JSON-сканированием
   до 5000 последних фрагментов: полноценный pgvector ещё не реализован.
2. Вопрос с номером акта `№117` или `152-ФЗ` ограничивает выдачу документами,
   где номер найден в названии (при явном ФСТЭК/ФСБ учитывается орган).
   Список документов строится по реестру PostgreSQL. Для неизвестного номера
   отказывается подменять нормативный источник другим.
3. Шесть источников вместо четырёх. В выводе **реальные короткие цитаты** рядом
   с ID и SHA-256; список источников **не объявляется** доказательством каждого
   вывода модели. RAG всегда использует исходные документы, не веб-поиск.
4. Лимит генерации 384 токена, контекст 4096; оповещение при `done_reason=length`.
   Для слабой Qwen 0.6B это НЕ гарантирует качество: нельзя выдавать ответы за
   юридическую экспертизу без сверки с актуальным официальным текстом.

## Перед установкой

```bash
cd /home/admsec/ZGT/AI/ib-platform
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
docker exec ib-db pg_dump -U ibplatform -d ibplatform -Fc \
  > "backups/ibplatform-pre-fts-$STAMP.dump"
test -s "backups/ibplatform-pre-fts-$STAMP.dump" && echo 'Backup OK'
chmod 600 "backups/ibplatform-pre-fts-$STAMP.dump"
```

Если архив лежит в `/media/sf_`:

```bash
cd /home/admsec/ZGT/AI
unzip -n /media/sf_/ib-platform-rag-gateway-v0.2.zip -d /home/admsec/ZGT/AI
bash /home/admsec/ZGT/AI/ib-platform-rag-gateway-v0.2/scripts/install.sh
```

Объявите функцию в **том же** терминале:

```bash
cd /home/admsec/ZGT/AI/ib-platform
dcf() {
  docker compose \
    -f compose.yaml \
    -f compose.backend.yaml \
    -f compose.postgres.yaml \
    -f compose.auth.yaml \
    -f compose.documents.yaml \
    -f compose.rag.yaml \
    -f compose.gateway.yaml \
    -f compose.gateway-tune.yaml "$@"
}
```

Обновление включает новую миграцию, поэтому последовательность обязательна:

```bash
dcf config -q
dcf build ib-api
docker stop ib-api
dcf run --rm --no-deps ib-api alembic upgrade head
dcf run --rm --no-deps ib-api alembic current
```

Ожидаем `0005_russian_fts (head)`. Если не произошло — **не запускайте
обновлённый API**, пришлите журнал ошибки. После успешной миграции:

```bash
dcf up -d --no-deps --force-recreate ib-api
curl -fsS http://127.0.0.1:8001/health/ready
echo
docker exec ib-db psql -U ibplatform -d ibplatform \
  -c "SELECT indexname FROM pg_indexes WHERE indexname='ix_document_chunks_content_fts_ru';"
```

Для функциональной проверки Gateway подставляет секрет из переменных окружения
контейнера, **не печатает** его:

```bash
docker exec -i ib-api python - <<'PY'
import os, json, urllib.request
req=urllib.request.Request(
  'http://127.0.0.1:8000/openai/v1/chat/completions',
  data=json.dumps({'model':'ib-gos-regul:0.2', 'stream':False,
                   'messages':[{'role':'user','content':'Что предусматривает приказ ФСТЭК России №117 в отношении защиты информации в ГИС? Укажи фрагменты источников.'}]}).encode(),
  headers={'Authorization':'Bearer '+os.environ['IB_GATEWAY_API_KEY'],
           'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=140) as r:
  payload=json.load(r)
print(payload['choices'][0]['message']['content'])
PY
```

## Ограничения и безопасность

- Не меняет пользователей, OpenProject, Ollama, Open WebUI, документные файлы.
- Состояние источников и редакций по-прежнему требует официальной проверки;
  особенно базовый приказ ФСТЭК №117 и последующие изменения №137.
- При установке `install.sh` сохраняет копии трёх файлов в `backups/`.
- Новая миграция добавляет один GIN-индекс; SQL DDL применяется к реальному PostgreSQL
  после резервной копии. На SQLite проверен только переход 0004 → 0005.
- Не публикуйте API-ключи, пароли и вывод содержимого `.env` в переписке.
- Откат после миграции: верните исходники из `backups/` или восстановите исходное
  приложение, учтите ожидаемую Alembic-версию; автоматический откат не выполняется.
