# Архитектура OI Registry v0.1

```text
Debian 13 (Docker, проект oi-registry)
  Браузер на Debian ── 127.0.0.1:8085 ──> oi-web (Nginx: HTML, CSS, JS)
                                           │ /api/*
                                           v
                                          oi-api (FastAPI + Argon2id + CSRF)
                                           │             │
                                PostgreSQL: oi-db        Volume: oi_documents_data
                                volume oi_postgres_data   оригиналы с SHA-256
```

OpenProject на хосте и IB Platform существуют независимо; в v0.1 отсутствуют соединения/запись в их БД и API. Связь с проектом OpenProject — `information_objects.openproject_project_id`, заполняется вручную.

## Основные сущности

```text
information_objects (1) ─────── (N) assets
       |                           |
       +── настраиваемые поля ─────┘
                 |
          field_definitions ─── field_values ─── field_value_revisions
                                          |
field_assertion_revisions ── field_evidence ── documents
                     |                         (неизменяемые оригиналы)
                  audit_events
users ── login_sessions
```

`FieldDefinition.scope_entity_id=NULL` означает типовое поле для всех карточек `entity_type`.
Ненулевое значение означает поле, доступное только одной конкретной карточке.

`FieldEvidence.value_revision_id` указывает на конкретную версию значения поля. Изменение и последующий возврат старого текста создают новые ревизии, поэтому прежний документ автоматически не становится актуальным снова.

## Почему два типа хранения

- Обычные поля (инвентарный и заводской номера, ОС, сегмент) — типизированные колонки `assets`. Они удобно индексируются и экспортируются.
- Дополнительные поля — `field_definitions` + `field_values`, с проверкой типа в API. Для нового поля не нужна миграция PostgreSQL.
- Файлы физически хранятся на отдельном томе; PostgreSQL хранит ссылку на ключ файла, SHA-256, дату и автора.

## Расширения по версиям

- v0.2: снимки и сравнение утверждённого и фактического состава комплектов, ролевые ограничения по ОИ, импорт CSV/XLSX.
- v0.3: двусторонний обмен событиями с OpenProject API v3, шаблоны мероприятий, дедупликация задач и контроль сроков.
- v0.4: расширенные отчёты XLSX/PDF, полнотекстовый поиск по вложениям, OCR и проверка реквизитов документа.

Это дорожная карта, а не уже реализованные функции.
