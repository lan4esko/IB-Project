# Запуск, остановка и перезапуск сервисов

Работать под администратором Debian в согласованное окно. **Не используйте `docker compose down -v`** и не уничтожайте Docker volumes. Перед перезапуском выясните причину отказа и сохраните логи.

## OI Registry (точный рабочий каталог)

```bash
cd /home/admsec/ZGT/CMDB/oi-registry-v0.1
sudo systemctl start docker
sudo docker compose up -d
sudo docker compose --profile automation up -d oi-worker
sudo docker compose ps
curl -fsS http://127.0.0.1:8085/api/health/ready; echo
```

Сервисный restart только веб-интерфейса: `sudo docker compose restart oi-web`. Только API: `sudo docker compose restart oi-api` (не лечит ошибки миграции). Только worker: `sudo docker compose --profile automation restart oi-worker`. Общий останов перед обслуживанием приложения без удаления томов: `sudo docker compose --profile automation stop oi-worker oi-api oi-web`, базу останавливать только при действительно необходимом контролируемом обслуживании.

Для чтения логов:

```bash
sudo docker compose logs --tail=100 oi-api oi-db oi-web
sudo docker compose --profile automation logs --tail=100 oi-worker
sudo docker compose exec -T oi-api alembic current
```

## OpenProject на хосте

```bash
sudo systemctl status openproject-web-1 openproject-worker-1 apache2 --no-pager
sudo openproject run bundle exec rake version
```

Если проблема локализована в web service и понятна причина, согласуйте `sudo systemctl restart openproject-web-1`. Аналогично worker, не перезапускайте хостовый PostgreSQL вслепую: он обслуживает отдельное приложение. Доступный URL OpenProject фиксируется в локальной инвентаризации.

## IB Platform

Установка использует многослойный Compose. **Сначала удостовериться в наличии всех перечисленных файлов**, иначе пользоваться командами из предыдущих релизов нельзя:

```bash
cd /home/admsec/ZGT/AI/ib-platform
ls -1 compose*.yaml
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
```

Если все слои доступны, команда безопасной проверки конфигурации (не печатает секреты):

```bash
sudo docker compose -f compose.yaml -f compose.backend.yaml  -f compose.postgres.yaml -f compose.auth.yaml  -f compose.documents.yaml -f compose.rag.yaml  -f compose.gateway.yaml -f compose.gateway-tune.yaml config -q
```

После положительной проверки можно использовать **точно тот же перечень** с `up -d`, но только по фактической конфигурации на сервере. Не запускайте одновременно несовместимые Compose-проекты с одинаковыми именами контейнеров. Для быстрого просмотра состояния без применения конфигурации достаточно `docker ps`, `docker logs ib-api`, `curl localhost:8001/health/ready`.

## После перезапуска

Обязательно проверить HTTP-здоровье, доступ к документам, миграцию Alembic, работоспособность планировщика, API-авторизацию и место на диске. Не считать «контейнер запущен» равнозначным «пользователи могут работать».
