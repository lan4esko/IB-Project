# IB Platform Backend v0.5 — локальный поиск по документам

Обновление с **v0.4 / Alembic `0003_documents`** на **v0.5 / Alembic `0004_rag_chunks`**.

Возможности: приватная индексация TXT/MD/CSV (UTF-8), текстовых PDF (до 20 стр.), DOCX; извлечение текста, порционные фрагменты, выдача с документом/версией/SHA-256, текущей ACL и страницей PDF. Режим `lexical` работает без LLM. Для `semantic` при индексировании и `hybrid` при поиске используется Ollama `/api/embed` и уже установленная `qwen3-embedding:0.6b`.

## Ограничения тестового стенда

- До 2 МБ на индексируемый файл, 48 фрагментов, до 2000 фрагментов в поиске; полные оригиналы могут храниться в v0.4 до 10 МБ.
- Не выполняется OCR; сканированные PDF без текстового слоя отклоняются.
- Excel/PowerPoint можно загружать в vault, но индексатор их пока не поддерживает.
- Поиск выполняется сравнением на уровне приложения по ограниченной выборке; **не подходит для 100 ГБ SMB**, масштабируемый поиск на PostgreSQL + pgvector и сервис индексации — будущие версии.
- Результаты — только **цитируемые найденные фрагменты**, без генерации выводов и без выполнения инструкций из документов.
- `mode=lexical` не вызывает Ollama и подходит для слабой VM. `mode=semantic` по выбору пользователя загружает embedding-модель и может быть медленным.
- Все результаты проходят те же проверки ACL документа и связанного объекта информатизации, что и скачивание. По умолчанию ищутся только **последние версии** документов.
- Индексирование — по запросу уполномоченного пользователя. Нет автоматического сканирования или SMB-монтирования.

## Установка (root на Debian)

1. Создать бэкап PG через `docker exec ib-db pg_dump -U ibplatform -d ibplatform -Fc > backups/pg-pre-v05.dump` и сохранить `backend` предыдущего релиза.
2. Извлечь архив в `/home/admsec/ZGT/AI`, чтобы появилась `ib-platform-backend-v0.5/`.
3. `cd /home/admsec/ZGT/AI/ib-platform` и выполнить `cp -a ../ib-platform-backend-v0.5/backend/. ./backend/` и `cp ../ib-platform-backend-v0.5/compose.rag.yaml .`.
4. Определить функцию dc5 со всеми шестью Compose-файлами (включая `compose.rag.yaml`). Выполнить `dc5 config -q; dc5 build ib-api`.
5. Только после успешной сборки: `docker stop ib-api`; затем `dc5 run --rm --no-deps ib-api alembic upgrade head`.
6. Проверить `dc5 run --rm --no-deps ib-api alembic current` = `0004_rag_chunks (head)`.
7. Запустить `dc5 up -d --no-deps ib-api`, проверить `/health/live` и `/health/ready`. Ожидается v0.5.0/PostgreSQL.

## API

Все маршруты в Swagger `/docs`, вход через `POST /api/v1/auth/login` и Bearer-токен.

- `POST /api/v1/rag/documents/{id}/index` JSON `{"mode":"lexical"}` (или `{"mode":"semantic"}`), опционально `"version": 1`. Требует право записи в документ и роль admin/security/operator.
- `GET /api/v1/rag/documents/{id}/status` — состояние индекса текущей версии.
- `POST /api/v1/rag/search` JSON `{"query":"плановая проверка", "top_k":5, "mode":"lexical"}`. Возвращает текст, оценку, идентификатор версии, страницу и hash.

Никогда не выводите access_token/пароли в отчёты. Не запускайте `docker compose down -v` и не удаляйте Docker Volumes.
