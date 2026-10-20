# Формат ZIP экспорта одного ОИ (`oi-registry-object/1`)

**Статус:** точный контракт **v0.6-alpha [ИСХОДНИК]**, не формат полного архива восстановления. Реализация: `CMDB/oi-registry-v0.1/backend/app/object_transfer.py`.

## Структура ZIP

```text
manifest.json
 data.json                 # паспорт ОИ и перечень СВТ (возвращается при импорте)
 tables/assets.csv         # СВТ, аварийный просмотр
 tables/repairs.csv        # история выполненных работ, ТОЛЬКО ЧТЕНИЕ
 tables/service_requests.csv # обращения, ТОЛЬКО ЧТЕНИЕ
 README-RECOVERY.txt      # ограничения архива
```

**Примечание:** в реальном ZIP имена путей без начальных пробелов; отступы выше только для визуального разделения.

## Машинные данные

`data.json` содержит ключи `format`, `object`, `assets`. `format` равен `oi-registry-object/1`.

`object` включает поля: `code`, `name`, `classification`, `location`, `status`, `attestation_issued_on`, `attestation_valid_until`, `attestation_notice_days`, `notes`.

Каждая запись `assets` включает: `code`, `serial_number`, `inventory_number`, `device_type`, `model`, `os_name`, `os_version`, `network_segment`, `ip_address`, `hostname`, `domain_name`, `seal_state`, `status`, `notes`.

**Важно:** текущий формат переносит не все поля базы ОИ и не все связи. Например, `openproject_project_id`, `attestation_document_id`, связанные документы/пользовательские поля и история аттестаций не попадают в `data.json`. ZIP не переносит авторизацию, пользователей и секреты.

`manifest.json` содержит: `format`, `object_code`, `sha256_data`, `restorable_sections`, `read_only_sections`, `warning`. Значение `sha256_data` — SHA256 **только** байтов `data.json`. Не подтверждает целостность каждого CSV или подлинность архивного файла. Цифровой подписи нет.

CSV используют UTF-8 BOM и разделитель `;`. Применяется защита от интерпретации начала значения как формулы электронной таблицы. При отсутствии строк соответствующий CSV может быть пустым, без заголовка.

## Ограничения импорта

- Метод: загрузка ZIP через `multipart/form-data` (а не импорт одиночного CSV).
- Размер передаваемого ZIP: максимум 8 МиБ; общий распакованный объём: максимум 16 МиБ; максимум 3000 СВТ; проверяется фиксированный перечень файлов без дубликатов.
- Не импортируются `repairs.csv`, `service_requests.csv`: они предназначены для чтения сотрудником при недоступности приложения.
- Совпадение кодов ОИ/СВТ проверяется на уровне приложения, включая глобальную уникальность кода СВТ.
- Для реальной катастрофоустойчивости нужны согласованные полные PostgreSQL+documents backup, защищённое внешнее хранение и практическая проверка восстановления.

## API и ответственность

| Метод | Маршрут | Результат |
|---|---|---|
| `GET` | `/api/objects/{oi_id}/transfer.zip` | Скачать ZIP одного ОИ, admin only |
| `POST` | `/api/objects/transfer/preview` | Выбор `mode`, ZIP; сравнительный отчёт, `plan_id`, уникальная фраза, 10-минутный срок, **нет изменений паспортов** |
| `POST` | `/api/objects/transfer/commit` | Тот же ZIP, режим, `plan_id`, фраза; проверка и SQL-транзакция, admin only |

Оба `POST` требуют обычной сессионной авторизации и CSRF-заголовка. Не публикуйте реальные ZIP и API-сеансы в GitHub. Примеры запросов без секретов см. в [процедуре импорта](../operations/OI-REGISTRY-V06-TRANSFER.md).
