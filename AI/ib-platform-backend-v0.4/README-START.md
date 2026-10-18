# IB Platform Backend v0.4.0 — защищённый реестр документов

Научно-технический **пилот** для существующего стенда Debian 13 / 2 vCPU / 6 ГБ RAM.
Сохраняет Docker-контейнеры Open WebUI, Ollama, OpenProject и PostgreSQL, не требует настройки промптов.

## Что реализовано

- PostgreSQL-таблицы `documents`, `document_versions`, `document_grants` (Alembic `0003_documents`).
- POST multipart UploadFile, immutable версии, SHA-256, исходное имя, тип, размер, дата, автор.
- Файлы хранятся в **отдельном** Docker-томе `ib-platform_documents_data` в виде случайных ключей, а не исходных имён.
- Проверка Bearer-сессии, роль создателя и гранты `read`/`write`; права связанного объекта информатизации применяются **дополнительно** к документным.
- Скачивание только после проверки ACL и SHA-256 с принудительным `attachment`, `nosniff`, `no-store`.
- Лимит **10 МБ на файл** на текущем стенде (`IB_MAX_UPLOAD_MB`), разрешённые расширения PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, ODT, ODS, ODP.
- Аудит создания, новой версии, предоставления доступа и попытки скачивания.

**Не реализованы:** OCR, анализ содержимого, антивирус, RAG, дедупликация, полнотекстовый поиск, версионирование внешней SMB-шары, virus scanning, доступ из Open WebUI и Nextcloud, per-user AD-ACL. Это API хранения, а не готовая система рекомендаций. Содержимое не проверяется на совпадение MIME и расширения. Не выставляйте API в Интернет.

## Обновление с работающего v0.3

### 1. Полный бэкап PostgreSQL + сохранение исходников

```bash
cd /home/admsec/ZGT/AI/ib-platform
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
docker exec ib-db pg_dump -U ibplatform -d ibplatform -Fc > "backups/ibplatform-pre-v04-$STAMP.dump"
test -s "backups/ibplatform-pre-v04-$STAMP.dump" || { echo 'Бэкап БД не создан'; exit 1; }
chmod 600 "backups/ibplatform-pre-v04-$STAMP.dump"
cp -a backend "../backend-v0.3-before-v04-$STAMP"
```

Текущее сохранение файлов бэкапом PostgreSQL **не покрывается**: новый документный том после установки тоже нужно регулярно резервировать отдельно.

### 2. Архив из Windows в `/media/sf_/`

Скопируйте архив `ib-platform-backend-v0.4.zip` в общую папку VirtualBox и выполните:

```bash
cd /home/admsec/ZGT/AI
unzip -n /media/sf_/ib-platform-backend-v0.4.zip -d /home/admsec/ZGT/AI
cd /home/admsec/ZGT/AI/ib-platform
cp -a ../ib-platform-backend-v0.4/backend/. ./backend/
cp ../ib-platform-backend-v0.4/compose.documents.yaml ./compose.documents.yaml
```

Не заменяйте `.env`, `compose.yaml`, `compose.backend.yaml`, `compose.postgres.yaml`, `compose.auth.yaml` и **не удаляйте** Docker volumes.

### 3. Подготовка обновлённого API

```bash
dc4() {
  docker compose -f compose.yaml -f compose.backend.yaml -f compose.postgres.yaml \
    -f compose.auth.yaml -f compose.documents.yaml "$@"
}
dc4 config -q
dc4 build ib-api
```

### 4. Небольшое окно недоступности backend (остальные сервисы не затрагиваем)

```bash
docker stop ib-api
dc4 run --rm --no-deps ib-api alembic upgrade head
dc4 run --rm --no-deps ib-api alembic current
# Ожидается 0003_documents (head)
dc4 up -d --no-deps ib-api
curl -fsS http://127.0.0.1:8001/health/live; echo
curl -fsS http://127.0.0.1:8001/health/ready; echo
dc4 ps
```

Если миграция завершилась ошибкой, **не переключайте API**. Не используйте `down -v` или `alembic downgrade`; восстановление по дампу потребует отдельной согласованной процедуры.

### 5. Проверка входа и тестовой загрузки

Не помещайте пароль в shell history или в команду curl:

```bash
read -r -s -p 'Пароль admin: ' IB_PASSWORD; echo
TOKEN=$(printf '%s' "$IB_PASSWORD" \
 | python3 -c 'import json,sys; print(json.dumps({"username":"admin","password":sys.stdin.read()}))' \
 | curl -fsS -H 'Content-Type: application/json' --data-binary @- \
    http://127.0.0.1:8001/api/v1/auth/login \
 | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
unset IB_PASSWORD
printf 'Пробный документ\n' > /tmp/ib-demo.txt
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -F 'title=Учебный документ' \
  -F 'file=@/tmp/ib-demo.txt' \
  http://127.0.0.1:8001/api/v1/documents; echo
curl -fsS -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8001/api/v1/documents; echo
unset TOKEN
rm -f /tmp/ib-demo.txt
```

Сам токен и пароль в отчёт не вставлять. API-документация: `http://127.0.0.1:8001/docs`.

## API

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/v1/documents` | Новый документ: `multipart` поля `title`, `file`, опционально `info_object_id` |
| GET | `/api/v1/documents` | Список документов, отфильтрованный по ACL |
| GET | `/api/v1/documents/{id}` | Метаданные |
| GET | `/api/v1/documents/{id}/versions` | Все версии и хеши |
| POST | `/api/v1/documents/{id}/versions` | Новая неизменяемая версия |
| GET | `/api/v1/documents/{id}/download` | Скачать последнюю версию |
| GET | `/api/v1/documents/{id}/versions/{version}/download` | Скачать указанную версию |
| GET/PUT/DELETE | `/api/v1/documents/{id}/acl[/{user_id}]` | Разрешения, только администратор |

## Тесты исходников

```bash
cd /home/admsec/ZGT/AI/ib-platform/backend
python3 -m pytest tests/test_v03.py tests/test_v04.py -q
```

Требования: `pip install -r requirements.txt -r requirements-dev.txt` в отдельном виртуальном окружении, не в системный Python Debian.

## Важно про API-файлы

- Оригиналы лежат в **именованном томе**, не в bind-mounted файлах с Windows и не в базе PostgreSQL.
- Учебный лимит загрузки сейчас 10 МБ; для больших архивов позже сделаем прямую индексацию с SMB через коннектор и фоновые очереди.
- На время переноса системы потребуются бэкапы **и** PostgreSQL, **и** `ib-platform_documents_data`, **и** Docker volumes Ollama/WebUI.
- При параллельной записи версии уникальный индекс не даст записать один номер дважды; повторите конфликтующий запрос.
