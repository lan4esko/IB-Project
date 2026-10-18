# 06. Обновление и особенности Debian 13

## ⚠️ Главное ограничение

Debian 13 (trixie) **не входит** в список поддерживаемых ОС пакетной установки
OpenProject. Официально поддерживаются только:

- Ubuntu 22.04 / 20.04
- Debian 12 / 11
- RHEL / AlmaLinux / Rocky 9
- SLES 15

Пакет в APT собран для **Debian 12** (`...debian12...`).
Поэтому:

- Мастер установки **сам не умеет ставить PostgreSQL** на Debian 13
  (`postgres/bin/preinstall` знает только версии ОС до 12). В этой установке
  PostgreSQL 17 поставлен вручную из репозитория Debian, а мастеру указано
  «использовать существующую БД» (`postgres/autoinstall = reuse`).
- Обновление пакета OpenProject может сломать зависимости или после apt upgrade
  потребовать ручного вмешательства.
- **Для боевого сервера на новой ОС рекомендуется Docker-установка** вместо
  пакетной: <https://www.openproject.org/docs/installation-and-operations/installation/docker/>

Также железо ниже рекомендованного минимума: 2 vCPU (нужно ≥4) и ~6 ГБ RAM
(минимум 4 ГБ, рекомендуется больше). Пересборка ассетов на таких ресурсах идёт
долго и может упасть по памяти.

---

## Обновление (если решишь обновлять в рамках пакетной установки)

```bash
# 1. Бэкап (обязательно!) — см. мануал 05
# 2. Обновить список пакетов и сам OpenProject
sudo apt update
sudo apt install --only-upgrade openproject
# 3. Прогнать мастер и дождаться миграций + ассетов
sudo openproject configure
# 4. Проверить
sudo systemctl status openproject
curl -kI https://srv-debian/
```

Версию смотри так:

```bash
dpkg -l | grep openproject
openproject run env | grep -i version || true
cat /opt/openproject/CHANGELOG.md | head
```

---

## Что НЕ надо делать

- Не запускай `apt upgrade` «вслепую» на этом хосте: обновление всего дистрибутива
  может подтянуть несовместимые зависимости.
- Не удаляй `/etc/openproject` и `/var/db/openproject` — это конфигурация и данные.
- Не меняй версию PostgreSQL (например на 18) без необходимости: данные лежат в
  кластере `postgresql@17-main` (см. `pg_lsclusters`).

---

## Полезные команды диагностики

```bash
pg_lsclusters                          # кластеры PostgreSQL
sudo -u postgres psql -l               # список БД
systemctl status openproject apache2 postgresql memcached
journalctl -u openproject -n 100 --no-pager
tail -f /var/log/openproject/*.log
sudo apache2ctl configtest
```
