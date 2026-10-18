# Проектный blueprint развёртывания (для Codex)

Это **не утверждение**, что сервисы уже развернуты. Codex обязан превратить blueprint в реальные pinned Compose конфигурации, исполняемые скрипты и доказать работоспособность на Ubuntu guest.

## Схема сети

- Браузер в разрешённой LAN -> `443/tcp` в Ubuntu VM (`gateway`). Опционально SSH доступ только admin подсети.
- `gateway` -> `open-webui`, `business-portal`, `openproject` по внутренней сети Docker.
- `business-portal` -> `app-api` -> `postgres-app`, `vector-store`, `ollama`, `document-store` по внутренним Docker сетям.
- `ingest-worker` -> разрешённые SMB host(s) внутри закрытой сети (`445/tcp`) с read-only правами.
- `app-api` -> OpenProject внутренний API v3, при необходимости LDAP/LDAPS на доверенном AD host.
- Никаких прямых LAN-публикаций `11434`, `5432`, `6333`, worker/admin metrics.
- `OFFLINE_MODE=true` не заменяет firewall; внешние egress адреса блокируются на сетевом уровне. При этом необходимо разрешить конкретные внутренние SMB/AD/OpenProject/DNS/NTP направления.

## Persistent volumes

- `openwebui_data` — история/пресеты в границах выбранного Open WebUI режима.
- `ollama_data` — полностью загруженные модели и манифесты.
- `app_db_data` — бизнес-реестр, документы/метаданные, конфиги и audit references.
- `document_objects` — версии исходных импортированных файлов с ACL, не публичный статический каталог.
- `vector_data` — векторный индекс, при необходимости rebuildable.
- `openproject_db_data` и `openproject_assets` — отдельные штатные тома с согласованным backup.
- `artifacts_data` — drafts/exports с версионированием и контролем чтения.
- `backup_staging` — защищенная staging зона только на время согласованной операции.

## Приоритет запуска

1. БД и системные зависимости (`health`/`readiness`, миграции).
2. Ollama модели/embedding, документы и индекс (отсутствие внешних загрузок).
3. API и портал.
4. OpenProject CE stack.
5. Nginx/TLS, Open WebUI и smoke-тесты маршрутизации.
6. Рабочие jobs: nightly sync/OCR/backup по планировщику, ограничение concurrency.

## Условия production readiness

- Https trust chain настроен и проверен.
- Нет дефолтных аккаунтов и секретов.
- ACL и выгрузки проходят negative tests.
- SMTP, analytics, update-check и внешние CDN не обязательны и не используются.
- Время внутри Ubuntu синхронизируется только с разрешенным внутренним источником.
- Ресурсные лимиты заданы для Ollama, OCR, OpenProject и БД, чтобы 32GiB RAM не уходили в OOM.
- Бэкап восстановлен в отдельном тестовом окружении.
- Документы с гостайной не допускаются в текущую среду.

## Очерёдность по дискам и HDD RAID

По возможности отдельные виртуальные диски для БД/индексов и импортированных файлов, но не ставить SSD как обязательное требование при имеющемся HDD RAID. Измерить реальный IOPS и пропускную способность. Индексировать дельтами и вынести OCR в off-hours; проверять, что фоновые задачи не вызывают постоянное зависание OpenProject.

## 3 вида сборок

- `dev`: для работы Codex с интернетом и **только публичными/обезличенными** материалами.
- `test-airgap`: без исходящего доступа наружу, отдельные синтетические SMB/AD тестовые сервисы.
- `release`: pinned digests, secrets через безопасный bootstrap, offline installer, без dev tools и утечек.

Состав `ops/`: `prepare-online`, `export-airgap`, `install-offline`, `verify-airgap`, `backup`, `restore`, `upgrade-offline`, `diagnose`; конкретные команды создавать и выполнять в VM на соответствующей фазе.
