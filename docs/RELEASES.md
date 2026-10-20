# Реестр выпусков ZGT — состояние на 20.10.2026

Источник статусов — доступные исходники + **переданные журналы администрирования**, а не автоматическое чтение сервера. Каждый вывод ограничен датой и конкретным стендом.

| Компонент | Релиз / миграция | Статус | Подтверждение |
|---|---|---|---|
| OI Registry | v0.1 / 0001 | Исторический | базовый паспорт ОИ/СВТ |
| OI Registry | v0.2 / 0002–0003 | Исторический, ранее внедрён | предыдущие логи |
| OI Registry | v0.3 / 0004 | Исторический, ранее внедрён | предыдущие логи |
| OI Registry | v0.4 / 0005 | Исторический, ранее внедрён | 18.10 перед обновлением показан `0005_automation` |
| **OI Registry production** | **v0.5 / 0006** | **Внедрена (18.10.2026)** | Git `48d0534`, `0006_control_rules (head)`, smoke OK, `oi-api` healthy, опубликована ветка `feature/oi-registry-v0.5` |
| **OI Registry test** | **v0.6-alpha / 0007** | **Тестовая, НЕ production** | 20.10 открыт UI на `18085` и вход `admin`; `0007_oi_transfer_approvals (head)` подтверждено выводом 20.10; приёмка импорта не завершена |
| OI Registry backup | full backup | Создавался локальный снимок | 18.10 архив и SHA256 созданы; **внешняя копия / полное DR не подтверждены** |
| OpenProject | пакет 17.9.1 | Установлен на Debian ранее | `openproject run bundle exec rake version` |
| IB Platform | backend + AI/RAG/Gateway | Пилотный состав | версии/контейнеры текущего дня требуют сверки |
| IB Document Hub | SMB/AD/OCR v0.6 | Только ТЗ | не вводить как внедрённую часть OI Registry |
| Git ZGT | `main` + feature ветки | Привязан GitHub | v0.5 отправлена в feature 18.10; v0.6-alpha ожидает doc review и push |
| Документация | **docs-1.5** | Редакция для v0.6-alpha | локальная проверка `verify_docs.py`; после публикации заполнить Git SHA |

## Дисциплина версий

Одновременно учитывать Git SHA/ветку, Alembic current, Docker image digest и frontend asset. Локальная шапка `v0.5` в исходном `frontend/app.js` **не доказывает**, что тест v0.6-alpha старый. Для v0.6 нужен отдельный показ `0007_oi_transfer_approvals (head)` и завершённые тесты.

## Релизные материалы

- [v0.5 — требования, установка и ограничения](releases/oi-registry-v0.5.md).
- [v0.6-alpha — текущий технический паспорт](releases/oi-registry-v0.6-alpha.md).
- [Матрица требований v0.6](requirements/OI-REGISTRY-V06-TRACEABILITY.md).
- [Приёмка тестовой v0.6](operations/OI-REGISTRY-V06-ACCEPTANCE.md).

## Заполнить после проверки

Тестовый SHA Git `feature/oi-registry-v0.6-alpha`, выход `alembic current`, лог pytest/приёмки PostgreSQL, digest образа API, внешний бэкап и результат восстановления. До этого статус **alpha**, не `v0.6.0` и не merge в `main`.


## OI Registry v0.6.1-alpha — код-кандидат от 2026-10-20

- Исправление паспортов ОИ / СВТ и новый раздел заявок, CSV с безопасным подтверждением.
- Изменение схемы: Alembic `0008_registry_v061` поверх `0007_oi_transfer_approvals`.
- Описаны отдельные TLS-proxy и безопасный проброс порта VirtualBox.
- **Только проект обновления**; установка на пользовательском PostgreSQL и проверка браузерного HTTPS не подтверждены.
- [Досье релиза](releases/oi-registry-v0.6.1-alpha.md) · [Эксплуатация](operations/OI-REGISTRY-V061-OPERATIONS.md).

## OI Registry v0.6.2-alpha — тестовый хотфикс, готов к проверке

`0009_requests_no_type` поверх `0008_registry_v061`. Убирает тип системы из заявок, сохраняет исторические поля, улучшает обновление CSRF. [Досье](releases/oi-registry-v0.6.2-alpha.md). Не опубликован на GitHub и не подтверждён на PostgreSQL пользователя.

## OI Registry v0.7.0-rc1 — 20.10.2026

**Только тестовый релиз-кандидат:** `0010_oi_reviews`, `0011_svt_media_protection`, конструктор полей ОИ/СВТ/Заявок, CSV импорт для admin, построитель запросов, отдельный учёт МНИ/ЗМНИ, устранение нарушений по проверкам ОИ. Исходные 45 тестов FastAPI SQLite прошли, миграция SQLite `0009 → 0011` прошла. **Установка на тестовой VM Debian и PostgreSQL не подтверждена.** Версию нельзя называть внедрённой. [Релиз](releases/oi-registry-v0.7.0-rc1.md).

## Docs-1.5 — пакет публикации v0.7.0-rc1 (20.10.2026)

- В разделе [`docs/data/erd/`](data/erd/README.md) опубликованы **31 таблица, 341 поле, 67 FK** на основании SQLAlchemy ORM v0.7.0-rc1; это модель **исходников**, а не `pg_catalog` рабочего PostgreSQL.
- [Публикация отдельной ветки](operations/OI-REGISTRY-V07-GIT-PUBLISH.md): архив-наложение, проверка diff и секретов, затем commit/push после проверки.
- Статус v0.7.0-rc1 остаётся **release candidate**, не production. После фактического push здесь нужно зафиксировать Git SHA и ссылку на ветку.
