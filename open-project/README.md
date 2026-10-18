# Установка OpenProject — README

**Сервер:** `srv-debian` (Debian 13 trixie)
**Дата установки:** 13.10.2026
**Версия OpenProject:** 17.9.1 (пакетная установка, DEB)
**Редакция:** Community
**Протокол:** HTTPS (самоподписанный сертификат)

---

## Кратко: что получилось

| Параметр | Значение |
|----------|----------|
| Веб-доступ | `https://srv-debian/` , `https://192.168.0.198/` , `https://195.170.198.48/` |
| HTTP | редирект 80 → 443 |
| Логин администратора | `admin` |
| Пароль администратора | `Aa1!VdkpTz291dgkta` |
| Email администратора | `admin@example.net` (заглушка, менять по мануалу 03) |
| Язык по умолчанию | `ru` |
| База данных | PostgreSQL 17, `127.0.0.1:5432`, БД и пользователь `openproject` |
| Кэш | memcached `127.0.0.1:11211` |
| Репозитории | Git и SVN включены |
| Демо-данные | загружены (проект «Демо-проект») |

> 🔐 Пароль администратора продублирован в `/root/openproject-secrets/admin_password`,
> пароль БД — в `/root/openproject-secrets/pg_password`. Держи их в секрете и смени
> после первого входа.

---

## Доступ и первый вход

1. Открой в браузере `https://srv-debian/` (или по IP сервера).
2. Браузер покажет предупреждение о самоподписанном сертификате — это ожидаемо,
   прими исключение. После появления домена сертификат заменяется (мануал 02).
3. Войди: логин `admin`, пароль `Aa1!VdkpTz291dgkta`.
4. Сразу поменяй email администратора (мануал 03) и пароль.

Проверка из консоли:

```bash
curl -skI https://srv-debian/ -H 'Host: srv-debian'   # ожидается 302
sudo systemctl status openproject apache2 postgresql memcached
```

---

## Что было сделано (пошагово)

1. `apt-get update`.
2. Установлены пакеты: `postgresql-17`, `postgresql-client-17`, `memcached`
   из репозитория Debian 13.
3. Создана роль PostgreSQL `openproject` (superuser — как делает штатный мастер)
   и база `openproject` на порту 5432.
4. Сгенерирован самоподписанный TLS-сертификат
   `/etc/ssl/certs/openproject.crt` + `/etc/ssl/private/openproject.key`
   (SAN: `srv-debian`, `localhost`, `127.0.0.1`, `192.168.0.198`, `195.170.198.48`).
5. Заполнены ответы мастера в `/etc/openproject/installer.dat`:
   Apache2 + SSL, hostname `srv-debian`, существующая БД (reuse), memcached,
   Git + SVN, язык `ru`, email `admin@example.net`.
6. Выполнена команда `openproject configure` — миграции БД, сиды (демо-данные),
   пересборка Rails-ассетов, запуск сервисов. Завершилась с кодом `0`.
7. Задан пароль существующей учётной записи `admin`.

### ⚠️ Важное отклонение от штатной установки

Мастер OpenProject **не поддерживает установку PostgreSQL на Debian 13**
(скрипт `postgres/bin/preinstall` знает версии ОС только до Debian 12).
Поэтому PostgreSQL 17 поставлен **вручную** из репозитория Debian, а мастеру
указано использовать уже существующую БД (`postgres/autoinstall = reuse`).
Для PostgreSQL это полностью штатный режим, но при переустановке ОС/БД учти это.

---

## Текущее состояние

```text
openproject           active
openproject-web-1     active   (Puma, 127.0.0.1:6000)
openproject-worker-1  active   (GoodJob worker)
apache2               active   (порты 80, 443)
postgresql            active   (порт 5432)
memcached             active   (порт 11211)
```

Исполняемые версии: Ruby 4.0.6, Node 24.18.0, Rails 8.1.3.1, Puma 8.0.2
(всё встроено в пакет в `/opt/openproject`).

---

## Расположение файлов

| Что | Путь |
|-----|------|
| Код приложения | `/opt/openproject` |
| Ответы мастера установки | `/etc/openproject/installer.dat` |
| Переменные окружения | `/etc/openproject/conf.d/` |
| Виртуальные хосты Apache | `/etc/apache2/sites-available/openproject.conf` |
| Доп. конфиги Apache | `/etc/openproject/addons/apache2/` |
| TLS-сертификат / ключ | `/etc/ssl/certs/openproject.crt`, `/etc/ssl/private/openproject.key` |
| Логи приложения | `/var/log/openproject/` |
| Вложения, Git, SVN | `/var/db/openproject/` |
| Секреты установки | `/root/openproject-secrets/` |
| **Эта документация** | `/home/admsec/ZGT/open-project/` |

---

## Управление

```bash
sudo systemctl status openproject        # состояние приложения
sudo systemctl restart openproject        # перезапуск
sudo systemctl reload apache2             # перечитать конфиг Apache
sudo openproject logs --tail              # логи приложения
sudo openproject reconfigure              # переконфигурация (интерактивно)
```

---

## Особенности этой конфигурации (прочитать)

- **Debian 13 не поддерживается** пакетной установкой OpenProject (пакет собран
  для Debian 12). Работает, но обновления могут ломаться. Для продакшена на
  новых ОС рекомендуется Docker. Подробнее — мануал 06.
- **Ресурсы ниже нормы:** 2 vCPU (рекомендуется ≥4) и ~6 ГБ RAM. Любой
  `openproject reconfigure` заново пересобирает ассеты — это долго и грузит память;
  запускай в `tmux`.
- **HSTS включён** (`OPENPROJECT_HSTS=true`) — браузеры будут требовать HTTPS.
- **Поле «Host name» в UI заблокировано** — имя хоста задано переменной
  `OPENPROJECT_HOST__NAME`. Меняется только через `config:set` / `reconfigure`
  (мануал 01).

---

## Мануалы

0. [Полный мануал установки (что и как было сделано)](00-USTANOVKA.md) ← воспроизведение с нуля
1. [Смена IP-адреса / домена / hostname](01-smena-ip-i-domena.md)
2. [Замена SSL-сертификата](02-ssl-sertifikat.md)
3. [Смена email администратора](03-email-administratora.md)
4. [Легальная активация Enterprise](04-enterprise-licenziya.md)
5. [Резервное копирование и восстановление](05-rezervnoe-kopirovanie.md)
6. [Обновление и особенности Debian 13](06-obnovlenie-i-osobennosti.md)

Скрипт для неинтерактивной смены адреса: `scripts/set-hostname.sh`.
