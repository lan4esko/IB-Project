# Резервное копирование: что копировать, где и чем проверять

## Матрица бэкапов

| Система | Минимальные обязательные данные | Место текущего/предлагаемого хранения | Реальная проверка |
|---|---|---|---|
| OI Registry | PostgreSQL `oi_registry`, документы, исходники, `.env` | **[ФАКТ]** `/home/admsec/ZGT/CMDB/BACKUPS/` | 18.10 архив сформирован; DR на отдельном стенде не подтверждён |
| OpenProject | host PostgreSQL, attachments, конфигурация, Git/SVN repos | **[ФАКТ]** `sudo openproject run backup` создавал набор в `/var/db/openproject/backup/` | восстановление не подтверждено |
| IB Platform | PG `ibplatform`, документы, Compose/.env, модели/веса/профили, зависимости | **[ПРОВЕРИТЬ]** отдельные локальные backup-папки; единый проверенный архив пока не подтверждён | не подтверждено |
| Git и docs | исходники и документация без секретов | локальный `.git`, **плюс защищённое внешнее зеркало/носитель** | remote ранее отсутствовал |

**Рекомендуемая политика:** выделить независимое от системного диска защищённое хранилище и отдельный комплект бэкапов для каждого сервиса. Факт наличия локальной копии не защищает от отказа VM/диска или вредоносного шифрования.

## OI Registry: единый архив

```bash
cd /home/admsec/ZGT/CMDB/oi-registry-v0.1
sudo bash scripts/backup_full.sh
sudo ls -lh /home/admsec/ZGT/CMDB/BACKUPS/
```

Из каждого запуска копируем два файла:

```text
CMDB/BACKUPS/
  oi-registry-YYYYMMDD-HHMMSS.tar.gz
  oi-registry-YYYYMMDD-HHMMSS.tar.gz.sha256
```

Содержимое tar.gz: `database.dump` (`pg_dump -Fc`), `documents.tar.gz` (исходные документы), `application.tar.gz` (backend/frontend/scripts/docs/Compose), `config.env` (секреты), `manifest.json` (SHA256 компонентов). **Не печатать `config.env`**.

Скрипт останавливает активные writer-сервисы API/worker на время снимка, затем пытается вернуть их состояние; проверяйте `docker compose ps`. Контроль:

```bash
sudo bash scripts/verify_backup.sh /home/admsec/ZGT/CMDB/BACKUPS/REAL_ARCHIVE_NAME.tar.gz
```

`REAL_ARCHIVE_NAME.tar.gz` заменить именем **реально существующего** файла. `BACKUP VERIFIED OK` = целостность архива, но не гарантия успешной проверки восстановления.

Автоматический таймер (`oi-registry-backup.timer`) был подготовлен отдельным модулем; его **наличие в конкретной рабочей установке не подтверждено**. Проверять:

```bash
sudo systemctl status oi-registry-backup.timer --no-pager
sudo systemctl list-timers --all | grep oi-registry || true
```

Восстановление на новом сервере — [RESTORE-DR.md](RESTORE-DR.md).

## OpenProject

```bash
sudo openproject run backup
sudo ls -lah /var/db/openproject/backup/
```

Из предыдущего успешного запуска были отдельные `postgresql-dump-*.pgdump`, `attachments-backup-*.tar.gz`, `conf-*.tar.gz`, `git-repositories-*.tar.gz`, `svn-repositories-*.tar.gz` (точные имена проверять по выводу). **Копировать комплект с одной датой целиком**, плюс сохранять версии пакета/зависимостей и протокол восстановления. Не считать OpenProject backup «всё в одном OI archive».

## IB Platform

Исторически применялось:

```bash
cd /home/admsec/ZGT/AI/ib-platform
mkdir -p backups
# Требуется администратор и работающий контейнер ib-db:
set -o pipefail
sudo docker exec ib-db pg_dump -U ibplatform -d ibplatform -Fc   > "backups/ibplatform-$(date +%Y%m%d-%H%M%S).dump"
```

Этот SQL dump **не включает** оригиналы загруженных документов, модели Ollama, Compose, `.env` и файлы сертификатов. Для IB обязателен отдельный регламент консистентной полной копии. Важно не архивировать docker volume PostgreSQL с работающим процессом копированием `cp`.

## Безопасность и контроль

- Права локальных секретных архивов `0600`, каталог `0700`, ограниченное число администраторов; SHA256 — не шифрование.
- Передача на внешний носитель только с санкционированным шифрованием/доступом; запрещён обычный открытый обмен через `/media/sf_/`.
- Хранение и ротацию копий согласовывать с классификацией данных и сроком их хранения; **не выполнять автоматическое удаление без утверждённой политики**.
- Документировать время копирования, размер, checksum, ответственного, способ транспортировки и дату успешного теста DR.
