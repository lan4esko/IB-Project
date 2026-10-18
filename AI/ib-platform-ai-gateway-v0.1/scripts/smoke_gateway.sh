#!/usr/bin/env bash
set -euo pipefail
cd /home/admsec/ZGT/AI/ib-platform
secret=$(sed -n 's/^IB_GATEWAY_API_KEY=//p' .env | tail -n 1)
test "${#secret}" -ge 32 || { echo 'Ключ Gateway не задан' >&2; exit 1; }
BASE=http://127.0.0.1:8001/openai/v1
unauth=$(curl -sS -o /dev/null -w '%{http_code}' "$BASE/models")
printf 'Без ключа: HTTP %s\n' "$unauth"
test "$unauth" = 401
body=$(curl -fsS -H "Authorization: Bearer $secret" "$BASE/models")
MODELS="$body" python3 - <<'PY'
import json,os
v=json.loads(os.environ['MODELS'])
print('Профили Gateway:',*[x['id'] for x in v['data']],sep='\n  ')
assert any(x['id']=='ib-gos-regul:0.2' for x in v['data'])
assert all('27b' not in x['id'] and 'gpt-oss' not in x['id'] for x in v['data'])
PY
# Unlikely search string; if not found the gateway responds without calling an LLM.
answer=$(curl -fsS --max-time 100 -H "Authorization: Bearer $secret" -H 'Content-Type: application/json' \
  -d '{"model":"ib-gos-regul:0.2","stream":false,"messages":[{"role":"user","content":"Несуществующий_термин_ZXQCV_1328479"}]}' \
  "$BASE/chat/completions")
ANSWER="$answer" python3 - <<'PY'
import json,os
v=json.loads(os.environ['ANSWER'])
print('Ответ Gateway:',v['choices'][0]['message']['content'][:300])
PY
unset secret body answer
