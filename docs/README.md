# Документация ZGT — навигация и текущие версии

**Документарная редакция:** `docs-1.5` (20.10.2026). **Основной принцип:** отделять реализованный код, выполненную эксплуатационную проверку и планы. Документация составлена по переданным исходникам, пакетам v0.5/v0.6-alpha и журналам администратора; это не автоматический снимок текущего сервера.

## OI Registry v0.7.0-rc1 — новая разработка

- [Описание версии и ограничения](releases/oi-registry-v0.7.0-rc1.md)
- [Матрица ТЗ → реализация](requirements/OI-REGISTRY-V07-TRACEABILITY.md)
- [Модель ЗМНИ/МНИ и CSV-построителя](data/OI-V07-MEDIA-AND-QUERIES.md)
- [Полная ER-схема с таблицами, полями и связями](data/erd/README.md)
- [Публикация v0.7.0-rc1 в GitHub](operations/OI-REGISTRY-V07-GIT-PUBLISH.md)
- [Установка и приёмка тестовой системы](operations/OI-REGISTRY-V07-RUNBOOK.md)
- **Статус:** 45 тестов Python при предыдущей сборке, миграция SQLite `0009 → 0011` успешна; **тест на рабочем PostgreSQL и HTTPS ещё не выполнен**.

## С чего начать

| Задача | Документы |
|---|---|
| Архитектура платформы | [03-ARCHITECTURE.md](03-ARCHITECTURE.md), [04-COMPONENT-SPEC.md](04-COMPONENT-SPEC.md) |
| Состояние серверов и сервисов | [01-SYSTEM-REGISTER.md](01-SYSTEM-REGISTER.md), [02-TOPOLOGY.md](02-TOPOLOGY.md) |
| OI Registry: таблицы и возможности | [systems/OI-REGISTRY.md](systems/OI-REGISTRY.md), [data/OI-DATA-MODEL.md](data/OI-DATA-MODEL.md) |
| **ТЗ v0.6: требование ↔ реализация** | [requirements/OI-REGISTRY-V06-TRACEABILITY.md](requirements/OI-REGISTRY-V06-TRACEABILITY.md) |
| **v0.6.1: заявки, независимые СВТ, журнал ремонта** | [operations/OI-REGISTRY-V061-OPERATIONS.md](operations/OI-REGISTRY-V061-OPERATIONS.md) |
| **HTTPS и VirtualBox NAT** | [operations/OI-REGISTRY-V061-HTTPS.md](operations/OI-REGISTRY-V061-HTTPS.md) |
| **Импорт/экспорт: точный формат** | [data/OI-TRANSFER-FORMAT.md](data/OI-TRANSFER-FORMAT.md), [operations/OI-REGISTRY-V06-TRANSFER.md](operations/OI-REGISTRY-V06-TRANSFER.md) |
| **Проверка тестовой v0.6 перед публикацией** | [operations/OI-REGISTRY-V06-ACCEPTANCE.md](operations/OI-REGISTRY-V06-ACCEPTANCE.md) |
| Релизы v0.5/v0.6 | [RELEASES.md](RELEASES.md), [releases/oi-registry-v0.5.md](releases/oi-registry-v0.5.md), [releases/oi-registry-v0.6-alpha.md](releases/oi-registry-v0.6-alpha.md), [CHANGELOG.md](CHANGELOG.md) |
| Установка и обслуживание | [operations/START-STOP.md](operations/START-STOP.md), [operations/UPGRADE.md](operations/UPGRADE.md), [operations/DAILY-RUNBOOK.md](operations/DAILY-RUNBOOK.md) |
| Бэкап/авария | [operations/BACKUP.md](operations/BACKUP.md), [operations/RESTORE-DR.md](operations/RESTORE-DR.md), [operations/INCIDENTS.md](operations/INCIDENTS.md), [operations/DIAGNOSTIC-TREE.md](operations/DIAGNOSTIC-TREE.md) |
| Интеграции | [integrations/OPENPROJECT-API.md](integrations/OPENPROJECT-API.md), [integrations/SMB-AD-ROADMAP.md](integrations/SMB-AD-ROADMAP.md) |
| AI, RAG, нормативные материалы | [systems/IB-PLATFORM.md](systems/IB-PLATFORM.md), [systems/RAG-LLM.md](systems/RAG-LLM.md), [systems/GOVSEC-CORPUS.md](systems/GOVSEC-CORPUS.md), [systems/AI-DEV-WORKFLOWS.md](systems/AI-DEV-WORKFLOWS.md) |
| OpenProject | [systems/OPENPROJECT.md](systems/OPENPROJECT.md) |
| Источники и правила ведения docs | [REFERENCES.md](REFERENCES.md), [DOCUMENTATION-POLICY.md](DOCUMENTATION-POLICY.md) |
| Git и релизная дисциплина | [operations/GIT-RELEASES.md](operations/GIT-RELEASES.md), [operations/PRE-PUSH-SECURITY.md](operations/PRE-PUSH-SECURITY.md) |
| Перенос WS2019 | [operations/WS2019-VIRTUALBOX-MIGRATION.md](operations/WS2019-VIRTUALBOX-MIGRATION.md), [diagrams/04-ws2019-publication.mmd](diagrams/04-ws2019-publication.mmd), [diagrams/05-ws2019-bridged.mmd](diagrams/05-ws2019-bridged.mmd) |
| Локальные факты стенда | [local/README.md](local/README.md), [scripts/collect_inventory.sh](scripts/collect_inventory.sh) |

## Достоверность и версии

- **[ФАКТ]** — подтверждено сообщённым журналом / скриншотом, с указанием даты и границы проверки.
- **[ИСХОДНИК]** — реализовано в переданном Python/JS/Alembic, но само по себе не свидетельствует о внедрении.
- **[ПЛАН]** — согласованная идея/требование, отсутствующее в текущем пакете.
- **[ПРОВЕРИТЬ]** — требуется локальное подтверждение без секретов.

| Контур | Состояние на дату редакции |
|---|---|
| OI Registry production v0.5 | **[ФАКТ]** `0006_control_rules`, `smoke_v05.sh` OK, API healthy, 18.10.2026 |
| OI Registry test v0.6.1-alpha | **[ФАКТ]** скриншоты интерфейса на `18085` и создания СВТ (20.10), включая ошибку CSRF; **[ПРОВЕРИТЬ]** подтверждение миграции `0008` и исправление ошибки на PostgreSQL |
| OI Registry test v0.6-alpha | **[ФАКТ]** администратор вошёл на `18085`, ревизия БД `0007_oi_transfer_approvals (head)` подтверждена выводом 20.10.2026; **[ПРОВЕРИТЬ]** три сценария импорта на PostgreSQL и восстановление |
| Код v0.7.0-rc1 | **[ИСХОДНИК]** МНИ/ЗМНИ, проверки ОИ, конструктор полей, построитель запросов и импорт CSV; **[ПРОВЕРИТЬ]** реальный PostgreSQL `0011`, интерфейс, TLS |
| Перенос всего ОИ с документами и историей | **[ПЛАН]**, в alpha доступен только ограниченный паспорт/СВТ |

## Безопасность документации

Не хранить в Git `.env`, пароли, токены, оригиналы аттестационных документов, рабочие дампы и резервные копии. Экспорт ОИ содержит инфраструктурные сведения и не должен публиковаться в репозитории. Архивы проекта перед отправкой проверять на секреты и персональные данные. Подробнее — [предпубликационная проверка](operations/PRE-PUSH-SECURITY.md).

### Корректировка OI Registry v0.6.2-alpha

- [Удаление обязательного «Типа системы» из заявок и обработка устаревшего CSRF](releases/oi-registry-v0.6.2-alpha.md).
