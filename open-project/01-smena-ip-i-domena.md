# 01. Смена IP-адреса, домена и hostname

Когда у сервера появится постоянный адрес (домен), OpenProject нужно
«переучить» на него. Меняются три вещи:

1. **Имя приложения** (`OPENPROJECT_HOST__NAME`, таблица настроек `host_name`) —
   используется в ссылках, письмах, интеграциях, URL репозиториев. Это самое важное.
2. **Имя сервера для Apache** (`SERVER_HOSTNAME`, `ServerName` в vhost).
3. **SSL-сертификат** — должен быть выпущен на новое имя (см. мануал 02).

---

## Вариант A (рекомендуемый): `openproject reconfigure`

Штатный официальный способ. Мастер заново пройдёт по вопросам и перегенерирует
все конфиги.

```bash
sudo openproject reconfigure
```

В диалогах:

- **Hostname** — впиши новый адрес (например `project.example.com` или новый IP).
- **SSL** — оставь `yes`; при необходимости укажи новые пути к сертификату/ключу.
- Остальные вопросы (БД, Apache, memcached, язык и т.д.) — оставь без изменений
  (значения уже подставлены из `/etc/openproject/installer.dat`).

После завершения мастер сам перезапустит приложение и Apache.

> ⏳ Важно: `reconfigure` каждый раз заново прогоняет миграции БД и
> **пересобирает Rails-ассеты** (`RECOMPILE_RAILS_ASSETS`). На 2 vCPU / ~3 ГБ
> RAM это может занимать от нескольких минут до получаса и легко упирается в
> память. Запускай в `tmux`/`screen`, чтобы обрыв SSH не прервал процесс:
> ```bash
> sudo apt install -y tmux
> tmux new -s op
> sudo openproject reconfigure
> # отсоединиться: Ctrl+B, затем D
> ```

---

## Вариант B: неинтерактивно (скрипт)

Если нужно менять адрес часто или автоматизированно — правим ответы мастера и
запускаем `configure` без диалогов.

```bash
sudo /home/admsec/ZGT/open-project/scripts/set-hostname.sh project.example.com
```

Скрипт:

1. меняет `server/hostname` в `/etc/openproject/installer.dat`;
2. запускает `openproject configure` (неинтерактивно).

Те же тяжёлые шаги (миграции + ассеты), но без ручного ввода.

---

## Вариант C: быстрая правка «на живую» (без полного reconfigure)

Когда нужно только чтобы **приложение** начало генерировать ссылки/письма на
новый адрес, без пересборки ассетов.

```bash
# 1. Имя хоста приложения (пишется в /etc/openproject/conf.d/other)
sudo openproject config:set OPENPROJECT_HOST__NAME="project.example.com"

# 2. Имя сервера для Apache (файл conf.d/server — имеет приоритет над other)
sudo sed -i 's|^export SERVER_HOSTNAME=.*|export SERVER_HOSTNAME="project.example.com"|' \
  /etc/openproject/conf.d/server

# 3. ServerName в виртуальном хосте
sudo sed -i 's|ServerName .*|ServerName project.example.com|g' \
  /etc/apache2/sites-available/openproject.conf

# 4. Применить
sudo systemctl restart openproject
sudo systemctl reload apache2
```

> ⚠️ Вариант C не обновляет базовые URL репозиториев Git/SVN в настройках
> (`repository_checkout_data`). Если пользуешься репозиториями OpenProject —
> после смены адреса прогони вариант A, чтобы ссылки на клонирование тоже
> обновились.

---

## Если меняется и протокол (HTTPS → HTTP или наоборот)

Определяется переменными в `conf.d/other`:

```bash
sudo openproject config:set OPENPROJECT_HTTPS="true"    # true = https
sudo openproject config:set OPENPROJECT_HSTS="true"     # HSTS-заголовок (только для https)
sudo systemctl restart openproject
```

Для перехода на HTTP без SSL проще снова пройти `openproject reconfigure` и
ответить `server/ssl = no`.

---

## Проверка после смены адреса

```bash
# что видит приложение
sudo openproject run env | grep -E 'SERVER_HOSTNAME|OPENPROJECT_HOST__NAME|OPENPROJECT_HTTPS'
sudo openproject config:get OPENPROJECT_HOST__NAME

# что отдаёт веб-сервер
curl -kI https://НОВЫЙ_АДРЕС/

# настройка host_name в БД
sudo openproject run rails runner 'puts Setting.host_name'
```

Ожидаемо: `Setting.host_name` и `OPENPROJECT_HOST__NAME` равны новому адресу,
Apache отвечает редиректом 80 → 443 и отдаёт HTTP 200 по HTTPS.

---

## Частые проблемы

| Симптом | Причина / решение |
|---------|-------------------|
| App выдаёт «Invalid host_name configuration» | `Setting.host_name` не совпадает с адресом в браузере. Поправь `OPENPROJECT_HOST__NAME` (вариант A или C) и перезапусти приложение. |
| Поле «Host name» в UI серое/недоступно | Так и задумано: значение «пришпилено» переменной `OPENPROJECT_HOST__NAME`. Меняй через `config:set`, а не в UI. |
| Браузер ругается на сертификат | Сертификат выпущен на старый адрес. Замени сертификат (мануал 02). |
| Ссылки в письмах старые | Не задан `OPENPROJECT_HOST__NAME` или приложение не перезапущено. |
| Apache не стартует после правок | `sudo apache2ctl configtest` покажет синтаксис; откати правку. |
