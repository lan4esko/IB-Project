# Первый час аварии: краткая памятка дежурному

**Начинать с проверки, не с переустановки.** Запишите UTC/местное время инцидента, симптом, кто сообщил, последний релиз, есть ли бэкап. Не публикуйте `.env`, токены, дампы или полные логи в переписке.

## 0. Сохранить следы

```bash
hostnamectl
uptime
date -Is
systemctl is-active docker
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
sudo systemctl --no-pager --full status openproject-web-1 openproject-worker-1 apache2
```

Если OpenProject использует иной набор systemd-юнитов, сначала обнаружьте их через `systemctl list-units --type=service 'openproject*'`. `apache2` здесь — по ранее подтверждённой установке, но конфигурацию прослушивания проверяйте на месте.

## 1. OI Registry: приложение и PostgreSQL

```bash
cd /home/admsec/ZGT/CMDB/oi-registry-v0.1
sudo docker compose ps
curl -fsS http://127.0.0.1:8085/api/health/ready; echo
sudo docker compose exec -T oi-api alembic current
sudo docker compose logs --tail=80 oi-api oi-db oi-web
sudo docker compose --profile automation logs --tail=50 oi-worker
```

Ожидаемая миграция на 18.10.2026: `0005_automation (head)`. Для Web порта — `127.0.0.1:8085`. При ошибке входа не сбрасывайте пароль/не удаляйте записи, пока не выяснена причина. Если `curl` возвращает v0.4 JS, а Firefox v0.3 — см. [INCIDENTS](operations/INCIDENTS.md#old-ui).

## 2. IB Platform: наличие и здоровье

```bash
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
curl -fsS --max-time 5 http://127.0.0.1:8001/health/ready; echo
sudo docker logs --tail=80 ib-api
sudo docker logs --tail=80 ib-db
sudo docker logs --tail=60 ib-ollama
```

Порт `8001` относится к известному слою API из исходников; проверьте фактические bind/listen. Команды `docker logs` выполняются только для реально существующих контейнеров. Не запускайте большие LLM для диагностики.

## 3. OpenProject

```bash
sudo systemctl status openproject-web-1 openproject-worker-1 apache2 --no-pager
sudo openproject run bundle exec rake version
sudo journalctl -u openproject-web-1 -n 60 --no-pager
sudo journalctl -u openproject-worker-1 -n 60 --no-pager
```

Зафиксированная ранее версия: `17.9.1`. Рабочая служба не является контейнером `oi-registry`, перезапуск Compose реестра на неё не должен влиять.

## 4. Есть ли доступный бэкап и не заполнен ли диск

```bash
sudo df -h
sudo ls -lah /home/admsec/ZGT/CMDB/BACKUPS/
sudo systemctl list-timers --all | grep -E 'oi-registry|backup' || true
```

**Не выполнять при первой диагностике:** `docker compose down -v`, `docker volume rm`, `docker system prune --volumes`, `pg_resetwal`, пересоздание `.env`, SQL `DROP`/`TRUNCATE`, `git reset --hard` без сохранения локальных изменений, удаление индексов RAG. Любое восстановление сначала на изолированном стенде.

## 5. Маршрут принятия решения

- Сломался только frontend → `curl`/кэш/монтирование Nginx → [INCIDENTS](operations/INCIDENTS.md).
- `oi-db` healthy, `oi-api` нет → логи FastAPI/Alembic, `.env` проверять по факту наличия без печати содержимого.
- Всё приложение недоступно → Docker/systemd/диск/место/сеть.
- Нет мероприятий → `oi-worker`/лог планирования/дата и timezone/заполненные даты аттестации.
- Задачи OpenProject не появляются → ручная публикация по умолчанию, не считать ошибкой; [OPENPROJECT-API](integrations/OPENPROJECT-API.md).
- Повреждение БД/файлов → прекратить запись, сохранить исходные тома, применить план DR [RESTORE-DR](operations/RESTORE-DR.md).

В карточке инцидента документировать **систему, факт, симптом, время, команду, результат, выполненное изменение и проверку результата**.
