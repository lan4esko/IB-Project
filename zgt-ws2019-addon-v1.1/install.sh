#!/usr/bin/env bash
set -euo pipefail
THIS="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${1:-/home/admsec/ZGT}"
DOCS="$ROOT/docs"
if [[ ! -f "$DOCS/README.md" || ! -f "$DOCS/CHANGELOG.md" ]]; then
  echo "ERROR: Base ZGT docs not found in $DOCS. Install docs-1.0 first." >&2
  exit 1
fi
for item in \
  operations/WS2019-VIRTUALBOX-MIGRATION.md \
  diagrams/04-ws2019-publication.mmd \
  diagrams/05-ws2019-bridged.mmd \
  templates/WS2019-NETWORK-PASSPORT.md \
  scripts/ws2019-network-inventory.ps1; do
  mkdir -p "$(dirname "$DOCS/$item")"
  if [[ -e "$DOCS/$item" ]]; then
    if cmp -s "$THIS/docs/$item" "$DOCS/$item"; then
      echo "Already current: $item"
    else
      echo "WARNING: Existing file differs; preserving it: $DOCS/$item" >&2
    fi
  else
    cp -- "$THIS/docs/$item" "$DOCS/$item"
    echo "Installed: $item"
  fi
done
if ! grep -Fq 'operations/WS2019-VIRTUALBOX-MIGRATION.md' "$DOCS/README.md"; then
  cat >> "$DOCS/README.md" <<'EOF'

## Перенос на Windows Server 2019 / VirtualBox (docs-ws2019-1.1)

- [Сеть, NAT/Bridged, Nginx reverse proxy, маршрутизация, диагностика](operations/WS2019-VIRTUALBOX-MIGRATION.md)
- [Схема NAT + Port Forwarding](diagrams/04-ws2019-publication.mmd)
- [Схема Bridged Adapter](diagrams/05-ws2019-bridged.mmd)
- [Шаблон сетевого паспорта](templates/WS2019-NETWORK-PASSPORT.md)
- [Инвентаризация WS2019 без секретов](scripts/ws2019-network-inventory.ps1)
EOF
fi
if ! grep -Fq 'docs-ws2019-1.1' "$DOCS/CHANGELOG.md"; then
  cat >> "$DOCS/CHANGELOG.md" <<'EOF'

## docs-ws2019-1.1 — 2026-10-18

- Добавлено руководство по миграции Debian VirtualBox VM на Windows Server 2019.
- Разделены сетевые модели: NAT Port Forwarding, Bridged Adapter, альтернативный RRAS/Host-Only.
- Добавлены конфигурация Nginx TLS reverse proxy, правила Windows Defender Firewall, DNS/ACL, проверка Hyper-V, диагностика и rollback.
- Добавлены Mermaid-схемы, шаблон сетевого паспорта и read-only PowerShell-инвентаризация.
- Весь целевой WS2019-контур отмечен как [ПЛАН] до фактической приёмки.
EOF
fi
if [[ -f "$DOCS/RELEASES.md" ]] && ! grep -Fq 'docs-ws2019-1.1' "$DOCS/RELEASES.md"; then
  cat >> "$DOCS/RELEASES.md" <<'EOF'

## Сетевое внедрение WS2019 / документация docs-ws2019-1.1

**[ПЛАН]** Разработано руководство Debian Nginx + VirtualBox NAT/Bridged + WS2019 + L3 ACL. На целевом хосте не тестировалось; статус обновлять по протоколу приёмки после ввода в эксплуатацию.
EOF
fi
if [[ -f "$DOCS/02-TOPOLOGY.md" ]] && ! grep -Fq 'WS2019-VIRTUALBOX-MIGRATION.md' "$DOCS/02-TOPOLOGY.md"; then
  cat >> "$DOCS/02-TOPOLOGY.md" <<'EOF'

## Целевая топология WS2019 (пока не внедрена)

**[ПЛАН]** Отдельный регламент: [перенос Debian/VirtualBox на WS2019, NAT/Bridge и маршрутизация](operations/WS2019-VIRTUALBOX-MIGRATION.md). Схемы: [NAT Port Forwarding](diagrams/04-ws2019-publication.mmd), [Bridged Adapter](diagrams/05-ws2019-bridged.mmd). Реальные IP не подтверждены; заполнить закрытый сетевой паспорт после внедрения.
EOF
fi
if [[ -f "$DOCS/DOCS_VERSION" ]] && grep -Fxq 'docs-1.0' "$DOCS/DOCS_VERSION"; then
  printf 'docs-1.1\n' > "$DOCS/DOCS_VERSION"
fi
if [[ -f "$DOCS/scripts/verify_docs.py" ]]; then
  python3 "$DOCS/scripts/verify_docs.py"
fi
echo "Completed docs-only update: $DOCS/operations/WS2019-VIRTUALBOX-MIGRATION.md"
