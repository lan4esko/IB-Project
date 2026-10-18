# Спецификация систем и программных компонентов

> Указаны подтверждённые версии и используемые слои образов. **Не воспринимайте floating-теги `latest`, `stable-alpine` и зависимости apt как фиксированные версии.** Перед DR зафиксировать image digest и экспортировать нужные образы в локальный реестр/носитель.

| Компонент | Назначение | Версия/артефакт | Запуск | Хранилище | Проверка |
|---|---|---|---|---|---|
| Debian | ОС VM | Debian 13 по проекту | systemd | корневая ФС | `cat /etc/os-release` |
| Docker Engine / Compose | контейнеры | уточнить локально | systemd | `/var/lib/docker` | `docker version; docker compose version` |
| OI nginx | SPA и API proxy | `nginx:stable-alpine` (доп. digest выяснить) | `oi-web` | bind `frontend/` и `nginx.conf` | `curl 127.0.0.1:8085` |
| OI FastAPI | REST, ACL, документы, аудит | OI Registry v0.4 | `oi-api` | OI PostgreSQL и `oi_documents_data` | `/api/health/ready` |
| OI PostgreSQL | реестр | `postgres:17-alpine` | `oi-db` | `oi-registry_oi_postgres_data` | `pg_isready` |
| OI Scheduler | создание локальных мероприятий | Python `app.scheduler` v0.4 | `oi-worker` | та же OI БД | `docker compose logs oi-worker` |
| OpenProject | управление проектами | 17.9.1 подтверждён ранее | `openproject-web-1` и `openproject-worker-1`, Apache | host PostgreSQL, attachments/repos — уточнить | `openproject run bundle exec rake version` |
| IB Platform FastAPI | пользователи, документы, RAG, Gateway | backend v0.5 + gateway/RAG патчи | `ib-api` | IB DB и document volume | `/health/ready` |
| IB PostgreSQL | пользователи, документы и chunks | `postgres:17-alpine` из compose | `ib-db` | `ib-platform_postgres_data` | `pg_isready` |
| Ollama | модели/эмбеддинги | версия уточняется локально | `ib-ollama` | Docker volume, уточнить | `ollama list`, `ollama ps` |
| Open WebUI | чат-интерфейс | версия/порт уточняются | Docker, имя уточнить | volume, уточнить | открыть UI и список моделей |
| Git/LazyGit | изменения | LazyGit 0.50.0 (по apt логу) | CLI | `/home/admsec/ZGT/.git` | `git status; git log` |

## Ограничения тестового стенда

- Конфигурацию CPU/RAM **не изменять в рамках этой документации**. Для медленных ответов малого LLM проверять очереди и параметры модели, не предлагать без согласования изменения ресурсов VM.
- `qwen3:0.6b` и `qwen3-embedding:0.6b` — небольшие модели для пилота. Большие загруженные веса (`qwen3.5:27b`, `gpt-oss:20b`) **не запускать** на данном стенде.
- Библиотека документов и RAG в пилоте; не делать вывод о соответствии правовым требованиям только из ответов LLM.

## Версионная дисциплина

Сопоставляйте 4 независимых значения: Git commit/tag, Alembic revision, image digest, frontend asset version. Например, отображаемая строка FastAPI `/api/health/live` может оставаться `0.2.0` при миграции OI `0005_automation`; шапка UI в исходном релизе v0.4 по ошибке сохраняла `v0.3` и была исправлена вручную. **Одна строка версии не является доказательством полной установки релиза.**
