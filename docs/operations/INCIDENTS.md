# База типовых инцидентов и способы восстановления работоспособности

Диагностировать сверху вниз; команды ниже выполняют проверку или ограниченный перезапуск, **не удаляют базу**. Для ошибок миграции и повреждения БД приостановить запись и сохранить снимок томов/журналы до дальнейших изменений.

## OI веб-портал пустой, 502 или недоступен

```bash
cd /home/admsec/ZGT/CMDB/oi-registry-v0.1
sudo docker compose ps
curl -i --max-time 5 http://127.0.0.1:8085/
curl -i --max-time 5 http://127.0.0.1:8085/api/health/ready
sudo docker compose logs --tail=100 oi-web oi-api
```

- 502 от Nginx и `oi-api` unhealthy → изучить `oi-api`, а не редактировать frontend.
- API ready 200, но не работает UI → Nginx static bind, browser cache, JavaScript errors (F12 Console/Network).
- `connect refused` → контейнер/порт binding, Docker daemon; проверить `ss -lntp`, не менять firewall автоматически.
- Браузер Windows/другой VM открывает `localhost`: это **его** машина, а не Debian. Проверить NAT forwarding/прокси; порт по текущему Compose привязан к Debian loopback.

## old-ui

Исходный пакет OI v0.4 содержал ошибочную `v0.3` в шапке. В октябре 2026 UI исправлялся копированием статических файлов из релиза и изменением версии/asset query параметров. Признак: `curl http://127.0.0.1:8085/app.js` отдаёт v0.4, Firefox показывает v0.3 без вкладки «Мероприятия ИБ».

```bash
cd /home/admsec/ZGT/CMDB/oi-registry-v0.1
curl -fsS http://127.0.0.1:8085/app.js | grep -E 'Registry|Мероприятия ИБ' | head -5
curl -fsS http://127.0.0.1:8085/index.html | grep -E 'app.js|automation.js'
```

В Firefox приватное окно → `?reload=<новая-версия>`; F12 → Network, Disable Cache, сверить actual response `/app.js?...`. Только после проверки версии файлов исправлять ссылки `?v=...` в index.html и выполнять контролируемый reload. Не подменять `main.py` и не откатывать БД ради надписи в шапке.

## Ошибка API 401 / 403

401 = нет сессии / срок истёк / cookie, 403 = роль/CSRF/правило доступа. Проверить URL, cookie secure settings, персональную роль/активность учётной записи и CSRF, не менять массово пароль администратора и не отключать проверку разрешений. Для `requester` доступ к чужим документам/изменению CMDB должен быть запрещён.

## Контейнер OI API не стартует после обновления

```bash
sudo docker compose logs --tail=200 oi-api
sudo docker compose exec -T oi-api alembic current
sudo docker compose ps
```

Если `oi-api` недоступен, `exec` не сработает: используйте отдельный read-only просмотр файла миграции/отчёт установщика. Ревизия для v0.4 `0005_automation`. Не запускать многократно скрипт обновления, пока не установлена точная точка сбоя. Сначала сохранить бэкап и текущие файлы, затем восстанавливать контролируемо и согласованно с версией схемы.

## OI DB unhealthy / PostgreSQL ошибка

Проверить `docker compose logs oi-db`, заполнение ФС, права Docker volume, последние изменения. Не удалять volume и не запускать `pg_resetwal` без отдельного плана DBA. При невозможности восстановления PostgreSQL использовать логический dump на новом стенде, а не копировать файлы PG работающей БД.

## Нет или повторяются мероприятия

- Нет контрольной даты `attestation_valid_until` → алгоритм не создаёт аттестационное событие.
- Не видна новая инспекция → убедиться, что СВТ действующая, правильные timezone/квартал, лог `oi-worker` и `status` записи.
- Worker работает по циклу от времени старта (`sleep 86400`), не строго в 03:00; после перезапуска запускает план сразу.
- При дубликатах не создавать записи вручную SQL; проверить `event_key`, уникальность и целостность Alembic.
- `acknowledged` != факт проведённой инспекции, `satisfied` != устранение всех обнаруженных нарушений.

## OpenProject API не создаёт задачу

В v0.4 автоматическое создание намеренно отключено. Проверьте `GET /api/automation/integration` под admin, `OI_OP_BASE_URL`, `OI_OP_TYPE_ID`, права сервисной УЗ и ID проекта. 401/403/422 объясняют разные проблемы. При таймауте POST или `needs_review` перед новой отправкой **найти задачу по `[OI-REGISTRY:...]`**, иначе можно создать дубль.

## Пустой RAG/галлюцинации Ollama

```bash
sudo docker logs --tail=100 ib-api
sudo docker exec ib-ollama ollama list
sudo docker exec ib-ollama ollama ps
```

Отдельно проверить наличие документов, успешность индекса, состояние PostgreSQL FTS, текстовый слой PDF и корректную редакцию НПА. Не пытаться исправить RAG запуском больших моделей.

## Бэкап не создался или не проверяется

Проверить свободное место и права `BACKUPS` (700), журналы `backup_full.sh`, наличие обоих файлов и `verify_backup.sh`. Script при исключении пытается вернуть остановленные приложения, но **обязательно** проверить `docker compose ps` после сбоя. Ошибка SHA256 означает непригодность копии до выяснения причины.

## Host/Docker/Git

- Docker не стартует → `systemctl status docker`, `journalctl -u docker`, свободное место, файловая система, ошибка daemon config.
- LazyGit `Not in a git repository` → `cd /home/admsec/ZGT`; отсутствие первого Git commit не значит, что его восстановит LazyGit автоматически.
- Git author unknown → локально `git config --local user.name ...` и `user.email` (не публиковать личные сведения без необходимости); коммит повторить после проверки.
- `git diff --cached --check` обнаружил trailing whitespace → исправить только соответствующую строку и заново stage.
