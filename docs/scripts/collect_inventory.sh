#!/usr/bin/env bash
# Read-only offline inventory of the deployed ZGT server. Does not print env, DB records or secrets.
set -Eeuo pipefail
umask 077
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS="$(dirname "$SCRIPT_DIR")"
OUT_DIR="$DOCS/local"
mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"
OUT="$OUT_DIR/inventory-$(date +%Y%m%d-%H%M%S).md"
log() { printf '%s\n' "$*"; }
run() {
  local title="$1"; shift
  log "### $title"
  log '```text'
  "$@" 2>&1 || log '(ошибка выполнения / нет сервиса / нет прав)'
  log '```'
}
{
  log '# Локальная инвентаризация ZGT (не добавлять в Git)'
  log "Дата: $(date -Is)"
  log 'Скрипт не читает .env, пароли, содержимое документов или строки PostgreSQL.'
  run 'ОС' cat /etc/os-release
  run 'Ядро' uname -r
  run 'Контроль времени' timedatectl status
  run 'Состояние Docker' systemctl is-active docker
  if command -v docker >/dev/null 2>&1; then
    run 'Версия Docker' docker --version
    run 'Версия Compose' docker compose version
    run 'Список контейнеров (только имя, образ, статус)' \
       docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
  fi
  OI=/home/admsec/ZGT/CMDB/oi-registry-v0.1
  if [[ -f "$OI/compose.yaml" && -s "$OI/.env" ]]; then
    pushd "$OI" >/dev/null
    run 'OI сервисы' docker compose ps --format 'table {{.Service}}\t{{.Status}}'
    run 'OI миграция Alembic' docker compose exec -T oi-api alembic current
    run 'OI HTTP readiness' curl -fsS --max-time 5 http://127.0.0.1:8085/api/health/ready
    popd >/dev/null
  fi
  if command -v openproject >/dev/null 2>&1; then
    run 'Версия OpenProject' openproject run bundle exec rake version
  fi
  run 'Сервисы OpenProject (кратко)' systemctl is-active openproject-web-1 openproject-worker-1 apache2
  if command -v curl >/dev/null 2>&1; then
    run 'IB readiness' curl -fsS --max-time 5 http://127.0.0.1:8001/health/ready
  fi
  run 'Файловые системы, без путей личных документов' df -h / /home
  if git -C /home/admsec/ZGT rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    run 'Git ветка' git -C /home/admsec/ZGT branch --show-current
    run 'Git commit' git -C /home/admsec/ZGT log -1 --format='%h %s'
  fi
  log ''
  log 'Дополнить вручную в защищённом журнале: сетевые пути/IP, OpenProject URL, владельцев, версии Open WebUI/моделей, внешнее хранилище backup и дату DR.'
} > "$OUT"
chmod 600 "$OUT"
printf 'Inventory saved locally (NOT FOR GIT): %s\n' "$OUT"
