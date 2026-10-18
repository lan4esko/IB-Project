# Backend ИБ-платформы, пилот v0.1.0

Этот пакет **добавляет** backend к уже работающим `ib-ollama`/`ib-webui`, не меняет существующий `compose.yaml` и никак не изменяет установленный OpenProject.

## Что реализовано
- Авторизация API единым тестовым ключом через `X-API-Key`. **Это не пользовательские роли и не SSO.**
- Реестр нормативных актов с отдельными редакциями.
- Реестр требований с явной ссылкой на акт и пункт.
- Реестр объектов информатизации с этапами жизненного цикла.
- Мероприятия, сроки, статусы и поля подтверждений.
- Технический аудит операций создания/изменения (без атрибуции пользователю).
- Чтение каталога моделей и состояния Ollama в реальном времени.
- Проверка соединения с OpenProject API v3 и чтение проектов по API-ключу (опционально).
- HTTP `/docs` (Swagger), `/health/live`.

## Что НЕ реализовано
Пользователи, SSO, ACL, RAG, OCR, полнотекстовая индексация, семантический поиск, обработка реальных нормативных актов, полнота аудита, экспорт документов, очередь заданий, интерфейс администратора, реальная верификация доказательств, полноценные миграции БД, контроль конкурентного доступа и интеграция задач OpenProject. Это прототип API и данных, не готовая к эксплуатации ИБ-система.

## Установка в существующий проект
Работай под root. В Debian файл `backend/` и `compose.backend.yaml` должны оказаться в каталоге `/home/admsec/ZGT/AI/ib-platform/` рядом с существующим `compose.yaml`. **Не заменяй** существующий `compose.yaml` и `.env`.

```sh
cd /home/admsec/ZGT/AI/ib-platform
# После копирования файлов из архива сюда:
[ -f .env ] || { echo 'Missing .env'; exit 1; }
if ! grep -q '^IB_PLATFORM_API_KEY=' .env; then
  printf '\nIB_PLATFORM_API_KEY=%s\n' "$(openssl rand -hex 32)" >> .env
fi
chmod 600 .env
docker compose -f compose.yaml -f compose.backend.yaml config -q
docker compose -f compose.yaml -f compose.backend.yaml up -d --build ib-api
docker compose -f compose.yaml -f compose.backend.yaml ps
curl -sS http://127.0.0.1:8001/health/live
```

Тест ключа:
```sh
API_KEY=$(sed -n 's/^IB_PLATFORM_API_KEY=//p' .env | tail -n 1)
curl -fsS -H "X-API-Key: $API_KEY" http://127.0.0.1:8001/api/v1/models/catalog | python3 -m json.tool
curl -fsS -H "X-API-Key: $API_KEY" http://127.0.0.1:8001/api/v1/models/installed | python3 -m json.tool
unset API_KEY
```

API-документация: http://127.0.0.1:8001/docs (локально на Debian). Открывать UI только из доверенного интерфейса, поскольку Swagger сам по себе не заменяет авторизацию API и не защищён от обнаружения.

## Опциональное подключение OpenProject

OpenProject использует локальный самоподписанный TLS сертификат. Для валидной проверки имени `srv-debian`:

```sh
cd /home/admsec/ZGT/AI/ib-platform
mkdir -p certs
cp /etc/ssl/certs/openproject.crt certs/openproject.crt
chmod 644 certs/openproject.crt
```

Добавь в `.env` значения (строго без пробелов вокруг `=`):
```
OPENPROJECT_URL=https://srv-debian
OPENPROJECT_CA_BUNDLE=/certs/openproject.crt
OPENPROJECT_API_KEY=...   # API ключ отдельной непривилегированной учётной записи, не пароль админа
```

После изменения `.env`:
```
docker compose -f compose.yaml -f compose.backend.yaml up -d --force-recreate ib-api
```

Проверка read-only:
```sh
API_KEY=$(sed -n 's/^IB_PLATFORM_API_KEY=//p' .env | tail -n 1)
curl -sS -H "X-API-Key: $API_KEY" http://127.0.0.1:8001/api/v1/integrations/openproject/status
unset API_KEY
```

## Локальные тесты в виртуальном окружении разработчика
```
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

## База данных
На пилоте используется отдельная SQLite в Docker-томе `ib_backend_data`, **не PostgreSQL OpenProject**. Перед промышленным использованием: PostgreSQL в отдельной БД, Alembic миграции, RBAC/ACL и доказуемые процессы аудита.

**Не выполнять `docker compose down -v`** — команда с `-v` удаляет тома и данные моделей/Open WebUI/backend.
