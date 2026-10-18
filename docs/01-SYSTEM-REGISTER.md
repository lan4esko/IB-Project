# Реестр систем, расположений и ответственности

| Подсистема | Местонахождение | Стек/версия | Признак состояния | Источник |
|---|---|---|---|---|
| Гипервизор | VirtualBox, VM `srv-debian` | Debian 13 (по проекту) | Рабочая VM подтверждена по терминалу | [ФАКТ] |
| OI Registry | `/home/admsec/ZGT/CMDB/oi-registry-v0.1` | Nginx + FastAPI + PostgreSQL 17 + Alembic, v0.4/0005 | 18.10: контейнеры healthy; UI доступен | [ФАКТ] |
| OI Scheduler | Docker Compose `oi-worker` в проекте `oi-registry` | Python `app.scheduler` | 18.10: выполнено локальное планирование; не публикует в OP | [ФАКТ] |
| OI Backup | `/home/admsec/ZGT/CMDB/BACKUPS` | tar.gz (pg_dump + документы + исходники + config) + SHA256 | 18.10 создан `oi-registry-20261018-135111.tar.gz` | [ФАКТ] |
| OpenProject | на самом хосте Debian, **не Docker OI** | OpenProject package 17.9.1; systemd; host PostgreSQL, Apache | версия проверялась ранее | [ФАКТ] |
| IB Platform | `/home/admsec/ZGT/AI/ib-platform` | Docker FastAPI `ib-api`, PostgreSQL `ib-db`, AI Gateway/RAG | пилот развёрнут ранее; уточнить текущие Compose-слои | [ФАКТ/ПРОВЕРИТЬ] |
| Ollama | контейнер `ib-ollama` | локальные модели и embeddings | применялись `qwen3:0.6b`, `qwen3-embedding:0.6b` | [ФАКТ/ИСХОДНИК] |
| Open WebUI | Docker-часть IB Platform | веб-UI для моделей | порт/адрес проверить локально | [ИСХОДНИК/ПРОВЕРИТЬ] |
| GovSec RAG | IB Platform/PostgreSQL | русский FTS, документные чанки, AI Gateway | исходные журналы: ~19 PDF, ~2942 чанка; текущие числа проверять | [ФАКТ] |
| Git/LazyGit | `/home/admsec/ZGT/.git` | `main`, `feature/openproject-integration` по прежним командам | **первый commit не был подтверждён** | [ФАКТ] |
| Документация ZGT | `/home/admsec/ZGT/docs` | Markdown/Mermaid/scripts | создаётся данным пакетом | [ДОК] |

## Неизвестные параметры, требующие очной инвентаризации

Уточнить в [local/README.md](local/README.md): фактический IP/hostname серверов, VIP/прокси и сертификаты, доступные VLAN, имена PostgreSQL для OpenProject, полную команду запуска IB Compose, версию Ollama и Open WebUI, policy Docker daemon, расписание бэкапов OpenProject и IB Platform, перечень сертификатов и доверенных корней, модели и версии в Ollama, сетевой путь к сервису OpenProject из контейнера `oi-api`.

## Эксплуатационные границы

- Восстановление OI Registry **не восстанавливает автоматически OpenProject и IB Platform**.
- Вход пользователей OI Registry локальный (admin/editor/requester), а не полноценное AD SSO.
- Связь ОИ с OpenProject — поле `openproject_project_id`, без гарантии соответствия реальному проекту до проверки.
- OI Registry допускает хранение сведений об объектах, но **не является автоматически аттестованной ИС**; доступность режимных данных в ней требует отдельного решения.
