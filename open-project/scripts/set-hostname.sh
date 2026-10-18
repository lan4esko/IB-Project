#!/usr/bin/env bash
# Неинтерактивная смена имени хоста OpenProject (пакетная установка).
# Использование: sudo ./set-hostname.sh НОВОЕ_ИМЯ [CERT] [KEY]
#
# Меняет server/hostname в /etc/openproject/installer.dat и запускает
# `openproject configure`, который перегенерирует конфиги Apache,
# conf.d/server и настройку OPENPROJECT_HOST__NAME.

set -euo pipefail

NEW_HOST="${1:-}"
CERT="${2:-}"
KEY="${3:-}"

if [[ -z "$NEW_HOST" ]]; then
  echo "Использование: $0 НОВОЕ_ИМЯ [CERT] [KEY]" >&2
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запусти от root (sudo)." >&2
  exit 1
fi

DB=/etc/openproject/installer.dat
cp -a "$DB" "${DB}.bak.$(date +%Y%m%d%H%M%S)"

set_answer() {
  local key="$1" value="$2"
  sed -i "\|^${key} |d" "$DB"
  printf '%s %s\n' "$key" "$value" >> "$DB"
}

echo ">> Устанавливаю server/hostname = ${NEW_HOST}"
set_answer "server/hostname" "$NEW_HOST"

if [[ -n "$CERT" ]]; then
  echo ">> Устанавливаю server/ssl_cert = ${CERT}"
  set_answer "server/ssl_cert" "$CERT"
fi
if [[ -n "$KEY" ]]; then
  echo ">> Устанавливаю server/ssl_key = ${KEY}"
  set_answer "server/ssl_key" "$KEY"
fi

chmod 640 "$DB"
chown openproject:openproject "$DB"

echo ">> Запускаю 'openproject configure' (миграции БД + пересборка ассетов, может быть долго)..."
openproject configure

echo ">> Готово. Проверка:"
openproject config:get OPENPROJECT_HOST__NAME || true
grep SERVER_HOSTNAME /etc/openproject/conf.d/server || true
