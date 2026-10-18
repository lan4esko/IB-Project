#!/usr/bin/env bash
set -Eeuo pipefail
# Test only the new prompt. Does not consult RAG: must not claim verified law.
docker exec -i ib-api python - <<'PY'
import json, time, urllib.request
payload = {
    "model": "ib-gos-regul:0.2",
    "prompt": ("Организация государственного сектора эксплуатирует ГИС с персональными данными. "
               "Назови ровно три СВЕДЕНИЯ об этой системе, которые нужно дополнительно собрать, "
               "прежде чем определить применимые требования ИБ. "
               "Не перечисляй законы вместо сведений."),
    "stream": False,
    "think": False,
    "options": {"num_predict": 192, "num_ctx": 2048, "temperature": 0}
}
request = urllib.request.Request(
    "http://ollama:11434/api/generate", data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"})
start=time.monotonic()
try:
    with urllib.request.urlopen(request, timeout=90) as reply:
        result=json.load(reply)
    print("=== РЕЗУЛЬТАТ v0.2 ===")
    print(result.get("response", ""))
    print("=== МЕТРИКИ ===")
    print("seconds:", round(time.monotonic()-start, 2))
    print("tokens:", result.get("eval_count"))
    print("done_reason:", result.get("done_reason"))
except Exception as exc:
    print("ERROR:", type(exc).__name__, str(exc))
    raise SystemExit(1)
PY
