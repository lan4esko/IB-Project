# 00. Полный мануал установки OpenProject (что и как было сделано)

Документ фиксирует **всю проделанную работу** по развёртыванию OpenProject на
сервере `srv-debian`: исходное состояние, принятые решения, точные команды и
проверки. Его можно использовать как инструкцию для воспроизведения установки
с нуля на аналогичном сервере.

- **Дата:** 13.10.2026
- **ОС:** Debian 13 (trixie), root
- **OpenProject:** 17.9.1, пакетная установка (DEB), редакция Community
- **Итог:** HTTPS-доступ через Apache2, локальный PostgreSQL 17, memcached, Git+SVN

Сопутствующие эксплуатационные мануалы — `01`…`06`. Сводка — `README.md`.

---

## 1. Исходное состояние сервера

- Debian 13 (trixie), работа под `root`, из предустановленного — только `git`.
- Пакет OpenProject **уже установлен, но не сконфигурирован**:
  - `dpkg`: `openproject 17.9.1-1790851919.c7ec3ef.debian12 amd64`
  - APT-источник: `…/stable/17/debian/ 12 main`
  - `/etc/openproject` и `/var/db/openproject` существуют, но пусты.
- Apache2 активен на порту 80 (отдаёт дефолтную страницу).
- СУБД нет, memcached нет.
- Железо: 2 vCPU, ~6 ГБ RAM, 170 ГБ диска (ниже официального минимума).
- Адреса: hostname `srv-debian`, LAN `192.168.0.198`, публичный `195.170.198.48`.
- Своих SSL-сертификатов нет.

---

## 2. Принятые решения и их причины

| Решение | Причина |
|---------|---------|
| Пакетная установка (DEB), не Docker | Выбор заказчика; пакет уже стоял на сервере |
| Продолжить на **неподдерживаемом** Debian 13 | Пакет уже установлен; для реального продакшена рекомендован Docker (см. мануал 06) |
| PostgreSQL 17 поставить **вручную** | Мастер не умеет ставить PostgreSQL на Debian 13 — знает версии ОС только до Debian 12 |
| Подключить БД как **существующую** (`postgres/autoinstall = reuse`) | Обход ограничения выше; для PostgreSQL это штатный режим |
| **Самоподписанный** TLS-сертификат | Домена пока нет; заменяется на реальный по мануалу 02 |
| hostname `srv-debian` | «Пока как есть», адрес изменится позже (мануал 01) |
| Email админа `admin@example.net` | Заглушка, реальный появится позже (мануал 03) |
| Язык `ru` | Требование |
| Репозитории Git + SVN, memcached | Требование |
| **Не** устанавливать «активатор лицензии» | Это обход платного лицензирования; Enterprise активируется только легальным токеном (мануал 04) |

---

## 3. Пошаговая установка (точные команды)

### Шаг 1. Обновление списков пакетов

```bash
apt-get update
```

### Шаг 2. Установка PostgreSQL 17 и memcached из репозитория Debian

```bash
export DEBIAN_FRONTEND=noninteractive
apt-get install -y postgresql-17 postgresql-client-17 memcached
```

Проверка:

```bash
pg_lsclusters              # кластер 17/main на порту 5432
systemctl is-active memcached
```

### Шаг 3. Роль и база данных PostgreSQL

```bash
PGPASS=$(openssl rand -hex 24)
install -d -m 700 /root/openproject-secrets
printf '%s\n' "$PGPASS" > /root/openproject-secrets/pg_password
chmod 600 /root/openproject-secrets/pg_password

su - postgres -c "psql -p 5432 -c \"CREATE ROLE openproject LOGIN SUPERUSER PASSWORD '$PGPASS';\""
su - postgres -c "createdb -p 5432 -O openproject openproject"

# проверка подключения по TCP с паролем
PGPASSWORD="$PGPASS" PGHOST=127.0.0.1 PGPORT=5432 PGUSER=openproject PGDATABASE=openproject \
  psql --no-password -c "select current_user, current_database();"
```

Роль делается `SUPERUSER`, как это делает штатный мастер, — иначе миграции не
смогут создать расширения (`pg_trgm`, `btree_gist`, `unaccent`).

### Шаг 4. Самоподписанный TLS-сертификат

```bash
CNF=$(mktemp)
cat > "$CNF" <<'EOF'
[req]
distinguished_name = dn
x509_extensions = v3
prompt = no
[dn]
CN = srv-debian
O = OpenProject
[v3]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt
[alt]
DNS.1 = srv-debian
DNS.2 = localhost
IP.1 = 127.0.0.1
IP.2 = 192.168.0.198
IP.3 = 195.170.198.48
EOF

openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout /etc/ssl/private/openproject.key \
  -out /etc/ssl/certs/openproject.crt \
  -config "$CNF"
rm -f "$CNF"

chmod 640 /etc/ssl/private/openproject.key
chown root:ssl-cert /etc/ssl/private/openproject.key
usermod -aG ssl-cert www-data
```

### Шаг 5. Ответы мастера (неинтерактивная конфигурация)

Мастер читает ответы из `/etc/openproject/installer.dat` (формат: `ключ значение`).
Значения ниже были записаны заранее, поэтому `openproject configure` прошёл без
диалогов.

```bash
PGPASS=$(cat /root/openproject-secrets/pg_password)
APIKEY=$(openssl rand -hex 16)
WRAPTOKEN=$(openssl rand -hex 16)
DB=/etc/openproject/installer.dat

{
  printf 'openproject/edition default\n'
  printf 'postgres/autoinstall reuse\n'
  printf 'postgres/db_host 127.0.0.1\n'
  printf 'postgres/db_port 5432\n'
  printf 'postgres/db_username openproject\n'
  printf 'postgres/db_password %s\n' "$PGPASS"
  printf 'postgres/db_name openproject\n'
  printf 'server/autoinstall install\n'
  printf 'server/variant apache2\n'
  printf 'server/hostname srv-debian\n'
  printf 'server/server_path_prefix \n'
  printf 'server/ssl yes\n'
  printf 'server/ssl_cert /etc/ssl/certs/openproject.crt\n'
  printf 'server/ssl_key /etc/ssl/private/openproject.key\n'
  printf 'server/ssl_ca \n'
  printf 'repositories/api-key %s\n' "$APIKEY"
  printf 'repositories/svn-install install\n'
  printf 'repositories/svn-path /var/db/openproject/svn\n'
  printf 'repositories/apache-wrapper-token %s\n' "$WRAPTOKEN"
  printf 'repositories/git-install install\n'
  printf 'repositories/git-path /var/db/openproject/git\n'
  printf 'repositories/git-http-backend /usr/lib/git-core/git-http-backend/\n'
  printf 'memcached/autoinstall install\n'
  printf 'openproject/admin_email admin@example.net\n'
  printf 'openproject/default_language ru\n'
} > "$DB"

chmod 640 "$DB"; chown openproject:openproject "$DB"
```

> Строки `server/server_path_prefix ` и `server/ssl_ca ` намеренно оставлены
> с пустым значением (пробел в конце) — чтобы мастер не пытался задать вопрос
> в неинтерактивном режиме.

### Шаг 6. Запуск конфигурации

```bash
openproject configure          # долго: миграции БД + сиды + пересборка ассетов
```

Выполнилось с кодом `0`. Что происходит внутри: миграции схемы, загрузка сидов
(в т.ч. демо-данных), пересборка Rails-ассетов, генерация конфигов Apache,
запуск systemd-сервисов `openproject`, `openproject-web-1`, `openproject-worker-1`.

> На 2 vCPU / ~3 ГБ свободной RAM шаг занимает много времени и грузит память.
> Запускай в `tmux`, чтобы обрыв SSH не прервал процесс.

### Шаг 7. Пароль администратора

При сидировании учётная запись `admin` создаётся **без пароля**. Пароль задан
вручную (требуются строчные, прописные, цифры и спецсимвол):

```bash
ADMPASS="Aa1!$(openssl rand -base64 18 | tr -dc 'A-Za-z0-9' | cut -c1-14)"
printf '%s\n' "$ADMPASS" > /root/openproject-secrets/admin_password
chmod 600 /root/openproject-secrets/admin_password

cat > /tmp/op_setpw.rb <<RUBY
u = User.find_by(login: "admin")
pw = "$ADMPASS"
u.password = pw
u.password_confirmation = pw
u.force_password_change = false
u.save!
puts "OK: password set for #{u.login}"
RUBY
chmod 644 /tmp/op_setpw.rb
openproject run rails runner /tmp/op_setpw.rb
rm -f /tmp/op_setpw.rb
```

Файл создаётся в `/tmp` (не в `/root`), потому что `rails runner` выполняется от
пользователя `openproject` и не имеет доступа к `/root`.

---

## 4. Проверка после установки

```bash
# Сервисы
for s in openproject openproject-web-1 openproject-worker-1 apache2 postgresql memcached; do
  printf '%-22s %s\n' "$s" "$(systemctl is-active $s)"
done

# Порты
ss -ltnp | grep -E ':80|:443|:6000|:5432|:11211'

# Веб-доступ (ожидается 302 — страница входа)
curl -skI https://srv-debian/ -H 'Host: srv-debian' | head -1
curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}\n' http://192.168.0.198/ -H 'Host: srv-debian'

# Настройки приложения
openproject config:get OPENPROJECT_HOST__NAME     # srv-debian
sudo -u postgres psql -d openproject -c "select 1;"
```

Все проверки прошли успешно.

---

## 5. Итоговое состояние

| Параметр | Значение |
|----------|----------|
| URL | `https://srv-debian/`, `https://192.168.0.198/`, `https://195.170.198.48/` |
| HTTP | редирект 80 → 443 |
| Логин админа | `admin` |
| Пароль админа | в `/root/openproject-secrets/admin_password` и в `README.md` |
| БД | PostgreSQL 17, `127.0.0.1:5432`, БД/пользователь `openproject` |
| Приложение | Puma на `127.0.0.1:6000` |
| Кэш | memcached `127.0.0.1:11211` |
| Протокол | HTTPS, HSTS включён |
| host_name | `srv-debian` (`OPENPROJECT_HOST__NAME`) |
| Язык | `ru` |
| Репозитории | Git `/var/db/openproject/git`, SVN `/var/db/openproject/svn` |
| Вложения | `/var/db/openproject/files` |
| Логи | `/var/log/openproject/` |

Версии рантайма (встроены в пакет): Ruby 4.0.6, Node 24.18.0, Rails 8.1.3.1, Puma 8.0.2.

---

## 6. Секреты

| Файл | Содержимое |
|------|------------|
| `/root/openproject-secrets/pg_password` | пароль роли PostgreSQL `openproject` |
| `/root/openproject-secrets/admin_password` | пароль веб-пользователя `admin` |

Пароль БД также продублирован в `/etc/openproject/conf.d/00_addon_postgres` (это
штатно для пакетной установки). Держи `/root/openproject-secrets` в тайне, смени
пароли после первого входа.

---

## 7. Возможные проблемы и решения

| Проблема | Причина / решение |
|----------|-------------------|
| `https://…` отдаёт 503 | Бэкенд Puma ещё не поднялся. Подожди 30–60 с, проверь `systemctl status openproject-web-1`. |
| 400 `Invalid host_name configuration` | Обращаешься по адресу, не совпадающему с `host_name`. Обращайся по `srv-debian` или смени `OPENPROJECT_HOST__NAME` (мануал 01). |
| `openproject configure` падает на шаге PostgreSQL | На Debian 13 автоустановка БД не поддерживается — БД должна ставиться вручную и подключаться как `reuse`. |
| Браузер ругается на сертификат | Самоподписанный сертификат; замени по мануалу 02. |
| Долго/падает пересборка ассетов | Мало RAM. Запускай в `tmux`, закрой лишние процессы, повтори. |
| `Permission denied /root/...` в `rails runner` | Runner работает от `openproject`; используй `/tmp` для скриптов. |

---

## 8. Воспроизведение «в одну страницу»

```bash
# 1. Пакеты
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql-17 postgresql-client-17 memcached

# 2. БД (см. шаг 3 выше) — создать роль openproject и базу openproject
# 3. Сертификат (см. шаг 4) — /etc/ssl/certs/openproject.crt + /etc/ssl/private/openproject.key
# 4. Ответы мастера (см. шаг 5) — /etc/openproject/installer.dat
# 5. Конфигурация
openproject configure

# 6. Пароль админа (см. шаг 7)
```

Полные тексты всех шагов — выше в разделах 3.1–3.7.

---

## 9. Эксплуатация (кратко)

- Управление: `systemctl {status,restart} openproject`, `systemctl reload apache2`.
- Переконфигурация: `openproject reconfigure` (интерактивно).
- Смена адреса/домена: мануал `01`, скрипт `scripts/set-hostname.sh`.
- Замена сертификата: мануал `02`.
- Email/пароль админа: мануал `03`.
- Enterprise-токен (легально): мануал `04`.
- Бэкап/восстановление: мануал `05`.
- Обновление и риски Debian 13: мануал `06`.
