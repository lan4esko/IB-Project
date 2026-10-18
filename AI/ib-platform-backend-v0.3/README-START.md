# IB Platform Backend v0.3.0 — учетные записи, сессии, RBAC и ACL объектов

Это пилотная версия. Промпты не меняются. Источники v0.2 и данные PostgreSQL сохраняются.
Работает с уже установленными Debian 13, Docker Compose, Ollama, Open WebUI и **отдельной** PostgreSQL `ib-db`.

## Состав

- Пароли пользователей хранятся как scrypt-хеши с уникальными случайными солями.
- Логин, отзыв сессий, смена пароля, 8-часовые opaque Bearer-токены; в PostgreSQL хранятся только SHA-256 хеши токенов.
- Роли `admin`, `security`, `operator`, `auditor`, `viewer`.
- ACL `read` / `write` на объекты информатизации. Мероприятия наследуют ACL своего объекта.
- Администратор управляет пользователями и ACL; создатель объекта получает `write`.
- Нормативные акты и требования в v0.3 — общая база для аутентифицированных пользователей; редактировать их могут `admin` и `security`.
- Технический аудит сохраняет идентификатор пользователя, выполняющего изменение (без хранения паролей и токенов).
- Существующие записи нормативных актов, мероприятий и объектов сохраняются.

Обращение к API старым заголовком `X-API-Key` **отключено** (`IB_ALLOW_LEGACY_API_KEY=false`), иначе ACL можно обойти. До внедрения интеграционных сервисных учётных записей используйте Bearer-сессии.

## Установка на уже работающей v0.2

Вставлять только команды из блоков, без строк ожидаемых результатов или приглашения `root@srv-debian#`.

```bash
cd /home/admsec/ZGT/AI/ib-platform
mkdir -p backups
# Дампы PostgreSQL — перед изменением схемы и кода.
docker exec ib-db pg_dump -U ibplatform -d ibplatform -Fc > backups/ibplatform-pre-v03.dump
test -s backups/ibplatform-pre-v03.dump && chmod 600 backups/ibplatform-pre-v03.dump
cp -a backend ../backend-v0.2-backup
```

Распакуйте архив `ib-platform-backend-v0.3.zip` в `/home/admsec/ZGT/AI/`, затем:

```bash
cd /home/admsec/ZGT/AI/ib-platform
cp -a ../ib-platform-backend-v0.3/backend/. ./backend/
cp ../ib-platform-backend-v0.3/compose.auth.yaml ./compose.auth.yaml
```

**Не заменяйте** `.env`, `compose.yaml`, `compose.backend.yaml`, `compose.postgres.yaml` и не удаляйте Docker-тома.

Создайте краткую функцию Compose (действует только в текущем терминале):

```bash
dc3() {
  docker compose -f compose.yaml -f compose.backend.yaml \
    -f compose.postgres.yaml -f compose.auth.yaml "$@"
}
dc3 config -q
dc3 config --services
```

В списке должны быть `ollama`, `open-webui`, `ib-db`, `ib-api`. Проверьте, что старые контейнеры работают, а PostgreSQL healthy.

```bash
# 1. Собираем новый образ, не трогая работающий API.
dc3 build ib-api

# 2. Короткое окно обслуживания только backend API.
docker stop ib-api

# 3. Дополнительные таблицы, индекс и поле для аудита.
dc3 run --rm --no-deps ib-api alembic upgrade head
dc3 run --rm --no-deps ib-api alembic current
# Ожидается: 0002_users_acl (head)

# 4. Создание первого администратора через защищённый ввод пароля.
# Не добавляйте пароль в CLI-аргументы, историю shell, .env или журнал установки.
dc3 run --rm --no-deps ib-api python -m app.bootstrap_admin

# 5. Переключаем только ib-api на v0.3.
dc3 up -d --no-deps ib-api
curl -fsS http://127.0.0.1:8001/health/live
curl -fsS http://127.0.0.1:8001/health/ready
dc3 ps
```

Ожидаем `version:0.3.0`, `database:postgresql`; обе модели и OpenProject сохраняются.

### Как протестировать авторизацию, не записав пароль в историю команд

Используйте логин, который ввели при `bootstrap_admin` (по умолчанию `admin`).

```bash
read -r -p 'Имя администратора: ' IB_USERNAME
export IB_USERNAME
read -r -s -p 'Пароль: ' IB_PASSWORD; echo
TOKEN=$(printf '%s' "$IB_PASSWORD" | python3 -c 'import json,os,sys; print(json.dumps({"username":os.environ["IB_USERNAME"],"password":sys.stdin.read()}))' \
 | curl -fsS -H 'Content-Type: application/json' --data-binary @- http://127.0.0.1:8001/api/v1/auth/login \
 | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
unset IB_PASSWORD
curl -fsS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8001/api/v1/auth/me
# Не печатайте токен и не передавайте его другим людям.
```

Проверка прав и пользователей:

```bash
curl -fsS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8001/api/v1/users
curl -fsS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8001/api/v1/models/catalog
unset TOKEN IB_USERNAME
```

Подробная OpenAPI-схема доступна по http://127.0.0.1:8001/docs.

## Если миграция не прошла

Не запускайте v0.3 до успешной `alembic upgrade head` и создания администратора.
Не делайте `alembic downgrade`, `docker compose down -v` или `docker system prune`.
Сохранённый дамп `backups/ibplatform-pre-v03.dump` позволяет восстановить PostgreSQL, но восстановление — отдельная операция с остановленным API, которую нужно предварительно согласовать и проверить.

## Что ещё не готово

- Полноценные ACL на документы и нормативные акты: пока акты/требования общие; ACL действуют для объектов и мероприятий.
- Единая аутентификация с Open WebUI / AD / LDAP, OIDC, MFA, админ UI, сервисные учётные записи.
- Rate limiting, сброс пароля по безопасному каналу, политика ротации и защита от перебора; **не публикуйте API наружу**.
- Журнал аудита не является неизменяемым доказательством, не подписан и не отправляется во внешний защищённый журнал.
- Тесты миграции `0002_users_acl` на реальном PostgreSQL нужно проверить на стенде: локальные автоматические тесты используют SQLite.
- Не запускайте в этой подключённой к Интернету VM обработку секретных документов.

## Тесты исходников

```bash
cd backend
python3 -m pytest tests/test_v03.py -q
```

В `backend/tests/legacy_v02` сохранены старые тесты для аудита различий, но они несовместимы с новой обязательной Bearer-аутентификацией.
