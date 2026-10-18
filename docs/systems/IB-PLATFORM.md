# IB Platform — состав, версии, эксплуатационная модель

**[ФАКТ/ИСХОДНИК]** Тестовая рабочая установка Debian: `/home/admsec/ZGT/AI/ib-platform`. Конвейер: FastAPI (`ib-api`) → PostgreSQL 17 (`ib-db`) → документы/RAG → Ollama (`ib-ollama`) → Open WebUI. Подключение AI Gateway к Open WebUI и RAG установлено ранее; текущую конфигурацию Compose проверить очно.

## Слои Compose, известные из релиза backend v0.5 + Gateway/RAG v0.2

В проекте исторически использовались `compose.yaml`, `compose.backend.yaml`, `compose.postgres.yaml`, `compose.auth.yaml`, `compose.documents.yaml`, `compose.rag.yaml`, `compose.gateway.yaml`, `compose.gateway-tune.yaml` (точное наличие и порядок проверить). Вариант диагностической функции:

```bash
cd /home/admsec/ZGT/AI/ib-platform
ibdc() {
  docker compose -f compose.yaml -f compose.backend.yaml     -f compose.postgres.yaml -f compose.auth.yaml     -f compose.documents.yaml -f compose.rag.yaml     -f compose.gateway.yaml -f compose.gateway-tune.yaml "$@"
}
# ТОЛЬКО если все эти файлы реально существуют:
ibdc config -q
ibdc ps
```

Никогда не запускать `docker compose up -d` с неполным набором слоёв, не разобравшись в `docker compose config`: он может изменить окружение. Исходники v0.5 содержат port `127.0.0.1:8001:8000` для API и `ollama:11434` внутри сети. Точные значения действующего стенда фиксируются локальным снимком.

## Возможности

- Backend v0.5: учётные записи/ACL, загрузка документов с версиями, индексация текстовых PDF/DOCX/TXT/MD/CSV, лексический и эмбеддинговый поиск по ограниченной выборке.
- Позднее установленный патч RAG/Gateway v0.2: PostgreSQL русский FTS (GIN), фильтрация номеров актов, ссылки на короткие фрагменты, шестёрка источников; hybrid остаётся пилотным, а не полноценным индексом pgvector.
- API Gateway предоставляет OpenAI-compatible `/openai/v1/models` и `/openai/v1/chat/completions` для Open WebUI через отдельный серверный ключ, но не гарантирует пользовательский аудит конечного собеседника.
- ~19 нормативных PDF и ~2942 фрагмента отражены в предыдущих журналах; значения не константы системы и требуют пересчёта в живой БД.
- Пять ролей госсекторных советников реализуются промпт-профилями поверх `qwen3:0.6b`; это тестирование UX, не юридический эксперт.

## Известные технические ограничения

- Не считать SMB/AD Document Hub v0.6 внедрённым; пока существует техническое задание (см. [SMB-AD-ROADMAP](../integrations/SMB-AD-ROADMAP.md)).
- OCR сканированных PDF, DOC/XLS и XSLX на всей SMB-шаре не подтверждены в действующем конвейере; правила парсеров зависят от этапа.
- Малая `qwen3:0.6b` не должна служить источником нормативного заключения. Ссылку на документ/чанк требуется сопоставить с исходным документом и редакцией.
- Не загружать гостайну или запрещённые политикой сведения в пилот.
- Документы общей библиотеки и конфиденциальные данные ОИ не эквивалентны по правам; требуется валидация модели доступа.

## Проверки

```bash
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
curl -fsS http://127.0.0.1:8001/health/live; echo
curl -fsS http://127.0.0.1:8001/health/ready; echo
sudo docker logs --tail=80 ib-api
sudo docker logs --tail=80 ib-db
sudo docker exec ib-ollama ollama list
sudo docker exec ib-ollama ollama ps
```

Проверка токенизированных endpoints выполняется локально без отображения ключа в shell history, скриншотах или документах. Убедитесь, что RAG выдаёт **реальный источник**, а не выдуманный номер акта.

## Данные и резервирование

PostgreSQL `ibplatform` в Docker volume `ib-platform_postgres_data` (по исходникам), документные оригиналы — `ib-platform_documents_data`, модельные веса — отдельный Ollama volume (фактическое имя выяснить). **Нужен самостоятельный, проверенный end-to-end бэкап**, который покрывает PG, документы, настройки, исходники, модели/манифесты и восстановление; OI BACKUPS не включает эти ресурсы автоматически.
