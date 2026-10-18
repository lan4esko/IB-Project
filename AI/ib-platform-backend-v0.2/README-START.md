# IB Platform Backend v0.2.0 — PostgreSQL + Alembic

**Пилотное обновление v0.1 → v0.2.** Действующие Docker volumes НЕ удаляются.
OpenProject и его PostgreSQL НЕ затрагиваются. Не выполнять `down -v`.

## 1. Безопасная подготовка

```bash
cd /home/admsec/ZGT/AI/ib-platform
mkdir -p backups
# Не копируйте .env из архива (его здесь нет).
# Убедитесь, что ./backend соответствует текущему v0.1:
ls backend/app/main.py compose.backend.yaml .env
# Backup SQLite через SQLite backup API (корректная копия при активном API):
docker exec ib-api python -c 'import sqlite3; sqlite3.connect("/data/platform.db").backup(sqlite3.connect("/data/pre-postgres-backup.db"))'
docker cp ib-api:/data/pre-postgres-backup.db ./backups/platform-pre-postgres.db
chmod 600 ./backups/platform-pre-postgres.db
```

## 2. Обновление исходников

Распакуйте архив рядом с проектом, затем:

```bash
cp -a ../ib-platform-backend-v0.2/backend/. ./backend/
cp -a ../ib-platform-backend-v0.2/compose.postgres.yaml .
# Не заменяйте compose.yaml, compose.backend.yaml и .env!
```

## 3. Переменная пароля и проверка Compose

```bash
# Выберите пароль в hex, пригодный для URL без дополнительного кодирования.
grep -q '^IB_PG_PASSWORD=' .env || printf 'IB_PG_PASSWORD=%s\n' "$(openssl rand -hex 24)" >> .env
chmod 600 .env
export COMPOSE="-f compose.yaml -f compose.backend.yaml -f compose.postgres.yaml"
docker compose $COMPOSE config -q
# Внимательно проверьте, что затрагиваются лишь ib-db и ib-api:
docker compose $COMPOSE config --services
```

## 4. Запуск PostgreSQL без вмешательства в другие контейнеры

```bash
docker compose $COMPOSE up -d --no-deps ib-db
docker compose $COMPOSE ps ib-db
```

## 5. Миграция схемы PostgreSQL

```bash
# Одноразовый контейнер на образе нового backend, основной ib-api ещё использует SQLite.
docker compose $COMPOSE build ib-api
docker compose $COMPOSE run --rm --no-deps ib-api alembic upgrade head
docker compose $COMPOSE run --rm --no-deps ib-api alembic current
```

## 6. Перенос записей SQLite (если есть)

```bash
# Продолжаем до переключения рабочего ib-api; скрипт строго проверяет пустоту PostgreSQL.
docker compose $COMPOSE run --rm --no-deps ib-api python -m app.migrate_sqlite
```

Если импорт сообщает об отсутствии /data/platform.db, проверьте исходный Docker volume. Ничего не удаляйте.

## 7. Только после успешного импорта переключаем API

```bash
docker compose $COMPOSE up -d --no-deps ib-api
curl -fsS http://127.0.0.1:8001/health/live
curl -fsS http://127.0.0.1:8001/health/ready
```

Таблицы в PostgreSQL развернуты через Alembic, и API подключён к PostgreSQL.

## 8. Откат (без удаления данных)

```bash
# Вернуть конфигурацию v0.1 со SQLite и уже существующим образом ib-platform-api:0.1.0.
docker compose -f compose.yaml -f compose.backend.yaml up -d --no-deps ib-api
# Старый SQLite volume остаётся на месте.
```

Обратите внимание: после переключения на PostgreSQL изменения в нём при откате не появятся в SQLite автоматически.

## Ограничения

Это ещё не production: общий API-ключ, отсутствуют RBAC, ACL, OCR, RAG, управление документами,
механизм полной верификации доказательств и UI администратора.
До введения многопользовательской аутентификации не публикуйте API в сеть.
