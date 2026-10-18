# 05. Резервное копирование и восстановление

Бэкапить нужно три вещи:

| Что | Где |
|-----|-----|
| База данных PostgreSQL | `openproject` на `127.0.0.1:5432` |
| Вложения и файлы | `/var/db/openproject/files` |
| Конфигурация | `/etc/openproject` , `/etc/ssl/*/openproject.*` , `/etc/apache2/sites-available/openproject.conf` |
| (опц.) репозитории Git/SVN | `/var/db/openproject/git`, `/var/db/openproject/svn` |

Пароль БД: `/root/openproject-secrets/pg_password`
(тот же пароль продублирован в `/etc/openproject/conf.d/00_addon_postgres`).

---

## Бэкап

```bash
sudo mkdir -p /var/backups/openproject
DATE=$(date +%Y%m%d-%H%M%S)
ROOT=/var/backups/openproject

# 1. База данных
sudo PGPASSWORD="$(sudo cat /root/openproject-secrets/pg_password)" \
  pg_dump -h 127.0.0.1 -U openproject -Fc openproject \
  -f "$ROOT/openproject-db-$DATE.dump"

# 2. Файлы и конфигурация
sudo tar czf "$ROOT/openproject-files-$DATE.tar.gz" -C /var/db/openproject files
sudo tar czf "$ROOT/openproject-config-$DATE.tar.gz" \
  /etc/openproject /etc/apache2/sites-available/openproject.conf \
  /etc/ssl/certs/openproject.crt /etc/ssl/private/openproject.key

echo "Готово: $ROOT/*$DATE*"
```

Скрипт лучше повесить в cron (например раз в сутки ночью).

---

## Восстановление

```bash
DATE=20260101-030000   # подставь свой
ROOT=/var/backups/openproject

# 1. Остановить приложение
sudo systemctl stop openproject

# 2. База (пересоздать)
sudo -u postgres dropdb --if-exists openproject
sudo -u postgres createdb -O openproject openproject
sudo PGPASSWORD="$(sudo cat /root/openproject-secrets/pg_password)" \
  pg_restore -h 127.0.0.1 -U openproject -d openproject --no-owner \
  "$ROOT/openproject-db-$DATE.dump"

# 3. Файлы и конфигурация
sudo tar xzf "$ROOT/openproject-files-$DATE.tar.gz" -C /var/db/openproject
sudo tar xzf "$ROOT/openproject-config-$DATE.tar.gz" -C /

# 4. Запуск
sudo systemctl restart openproject
sudo systemctl reload apache2
```

Проверь: вход в веб-интерфейс, наличие проектов, вложений и репозиториев.
