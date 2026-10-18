#!/usr/bin/env bash
# Local Git gate. Does not read secrets or make network requests.
set -Eeuo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
if [[ ! -f docs/scripts/verify_docs.py ]]; then
  echo 'Docs gate: docs/scripts/verify_docs.py missing. Cannot commit.' >&2
  exit 1
fi
python3 docs/scripts/verify_docs.py
STAGED="$(git diff --cached --name-only --diff-filter=ACMRT)"
# For code/config changes, require living docs to be part of the SAME commit.
if grep -Eq '^(CMDB/oi-registry-v0\.1/(backend|frontend|compose[^/]*\.yaml|nginx\.conf)|AI/ib-platform/|open-project/)' <<< "$STAGED"; then
  for file in docs/CHANGELOG.md docs/RELEASES.md; do
    if ! grep -Fxq "$file" <<< "$STAGED"; then
      echo "Docs gate: staged code/config change requires staged update: $file" >&2
      exit 1
    fi
  done
fi
if git diff --cached --check >/dev/null; then
 echo 'Docs gate OK (staged code + documentation checks)'
else
 echo 'Docs gate failed: git diff --cached --check' >&2
 exit 1
fi
