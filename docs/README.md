# ZGT — эксплуатационная и архитектурная документация

**Базовое состояние:** 18.10.2026; **документарный выпуск:** `docs-1.0`.
**Область:** Debian 13 / VirtualBox, OpenProject, OI Registry, IB Platform, PostgreSQL, Ollama, Open WebUI, RAG, Git/LazyGit, резервные копии, локальные и проектируемые интеграции.
**Режим:** документация доступна полностью офлайн. Внешние ссылки в инструкциях не требуются.

> **Критично:** это пакет, собранный по доступным исходным релизам и фактическим журналам развёртывания. Он НЕ является автоматическим снимком текущего сервера. Признаки `[ФАКТ]`, `[ИСХОДНИК]`, `[ПЛАН]`, `[ПРОВЕРИТЬ]` разъяснены ниже. Перед аварийным восстановлением сверяйте инвентаризацию на месте.

## Начните отсюда

| Когда нужен документ | Файл |
|---|---|
| Система не работает, дежурство | [00-FIRST-RESPONSE.md](00-FIRST-RESPONSE.md) |
| Где что находится, кому принадлежит | [01-SYSTEM-REGISTER.md](01-SYSTEM-REGISTER.md) |
| Топология и связи | [02-TOPOLOGY.md](02-TOPOLOGY.md); [SVG схемы](diagrams/01-zgt-context.svg); [diagrams/](diagrams/) |
| Архитектура всей платформы | [03-ARCHITECTURE.md](03-ARCHITECTURE.md) |
| Спецификация и зависимости | [04-COMPONENT-SPEC.md](04-COMPONENT-SPEC.md) |
| Реестр, карточки, роли, аудит | [systems/OI-REGISTRY.md](systems/OI-REGISTRY.md) |
| Управление задачами/проектами | [systems/OPENPROJECT.md](systems/OPENPROJECT.md) |
| ИИ, поиск, нормативные документы | [systems/IB-PLATFORM.md](systems/IB-PLATFORM.md); [systems/RAG-LLM.md](systems/RAG-LLM.md); [systems/GOVSEC-CORPUS.md](systems/GOVSEC-CORPUS.md) |
| ИИ-агенты и материалы разработки | [systems/AI-DEV-WORKFLOWS.md](systems/AI-DEV-WORKFLOWS.md) |
| Запуск/остановка, обслуживание | [operations/START-STOP.md](operations/START-STOP.md); [operations/DAILY-RUNBOOK.md](operations/DAILY-RUNBOOK.md) |
| Причины ошибок, диагностика | [operations/INCIDENTS.md](operations/INCIDENTS.md); [operations/DIAGNOSTIC-TREE.md](operations/DIAGNOSTIC-TREE.md) |
| Бэкапы/восстановление | [operations/BACKUP.md](operations/BACKUP.md); [operations/RESTORE-DR.md](operations/RESTORE-DR.md) |
| Безопасность, контур, риски | [operations/SECURITY-AIRGAP.md](operations/SECURITY-AIRGAP.md) |
| Git, LazyGit, релизы | [operations/GIT-RELEASES.md](operations/GIT-RELEASES.md) |
| API, интеграции | [integrations/OPENPROJECT-API.md](integrations/OPENPROJECT-API.md); [integrations/SMB-AD-ROADMAP.md](integrations/SMB-AD-ROADMAP.md) |
| Что уже сделано и что только планируется | [RELEASES.md](RELEASES.md); [CHANGELOG.md](CHANGELOG.md) |
| Как обновлять эти документы | [DOCUMENTATION-POLICY.md](DOCUMENTATION-POLICY.md) |
| Проверить фактический сервер без секретов | [scripts/collect_inventory.sh](scripts/collect_inventory.sh) |

## Маркировка достоверности

- **[ФАКТ]**: подтверждено предоставленными журналами вывода команд; отражает момент проверки, не бесконечную гарантию.
- **[ИСХОДНИК]**: явно реализовано в предоставленных релизах; может отличаться от развёрнутого экземпляра после ручных исправлений.
- **[ПЛАН]**: предложение, ТЗ, нефункционирующая интеграция; не включайте в эксплуатационный регламент как готовую функцию.
- **[ПРОВЕРИТЬ]**: неизвестно без локальных команд, прав администратора или инвентаризационного акта.

## Политика конфиденциальности

Запрещено добавлять в Git и пакет: `.env`, пароли, ключи OpenProject/Ollama/AD, `pg_dump`, оригинальные документы и сканы ОИ, содержимое журналов с ПДн, фактические сетевые адреса режимных сегментов без согласования. Инвентаризационный отчёт сохранять локально в `docs/local/`, который исключён из Git. Резервные копии — **не** в Git.

## Первое размещение

Распаковать ZIP в `/home/admsec/ZGT`, чтобы появился `/home/admsec/ZGT/docs/README.md`. Архив содержит только `docs/` и безопасные примеры. Рекомендовано проверить `git status`, затем добавить `docs/` отдельным коммитом. Для новых релизов использовать инструкцию [DOCUMENTATION-POLICY.md](DOCUMENTATION-POLICY.md).
