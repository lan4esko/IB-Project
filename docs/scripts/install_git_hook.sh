#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(git rev-parse --show-toplevel)"
SRC="$ROOT/docs/scripts/pre-commit-docs.sh"
DEST="$(git -C "$ROOT" rev-parse --git-path hooks/pre-commit)"
[[ -f "$SRC" ]] || { echo "Missing: $SRC" >&2; exit 1; }
if [[ -e "$DEST" ]]; then
 echo "Existing hook preserved: $DEST" >&2
 echo 'Merge docs gate into existing hook manually; nothing overwritten.' >&2
 exit 2
fi
install -m 755 "$SRC" "$DEST"
echo "Local Git pre-commit docs gate installed: $DEST"
