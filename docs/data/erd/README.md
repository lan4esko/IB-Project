# OI Registry v0.7.0-rc1 — полная логическая ER-схема
**Источник:** `CMDB/oi-registry-v0.1/backend/app/models.py` из пакета v0.7.0-rc1. Эта модель построена по SQLAlchemy ORM, а не чтением PostgreSQL на сервере пользователя.
**Всего:** 31 таблица, 341 поле, 67 физических внешних ключей.
## Обозначения
- **PK** — первичный ключ; **FK** — внешний ключ; **UQ** — уникальность одного столбца; **NULL** — поле допускает отсутствие значения; **NOT NULL** — обязательность в самой БД (не путать с обязательностью в форме).
- Сплошная линия в SVG: внешний ключ; пунктирная: поле внешнего ключа допускает `NULL`. Серые таблицы на тематических диаграммах — внешние опорные сущности, показаны только с ключом `id`.
- Имена и типы колонок взяты из ORM. Уникальные составные ограничения не дублируются в метке каждого поля; см. секцию ограничений.
## Схемы
- [Общая схема, 31 таблица (SVG)](00_full_schema_31_tables.svg); [ПОЛНАЯ схема с 341 полем (SVG)](00_all_fields_31_tables.svg); [Mermaid](00_full_schema_31_tables.mmd)
- [ОИ, СВТ, комплектующие и носители (SVG)](01_core_inventory.svg), [Mermaid](01_core_inventory.mmd)
- [Заявки, ремонт и проверки СВТ (SVG)](02_requests_repairs.svg), [Mermaid](02_requests_repairs.mmd)
- [Проверки ОИ и управление конфигурацией (SVG)](03_oi_reviews_config.svg), [Mermaid](03_oi_reviews_config.mmd)
- [Конструктор полей и документы (SVG)](04_fields_documents.svg), [Mermaid](04_fields_documents.mmd)
- [Пользователи, аудит и мероприятия (SVG)](05_users_planning.svg), [Mermaid](05_users_planning.mmd)

## Таблицы и все поля
### ОИ, СВТ, комплектующие и носители
#### `information_objects` (15 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `code` | `VARCHAR(80)` | UQ | — |
| `name` | `VARCHAR(250)` | NOT NULL | — |
| `classification` | `VARCHAR(250)` | NOT NULL | — |
| `location` | `VARCHAR(250)` | NOT NULL | — |
| `status` | `VARCHAR(40)` | NOT NULL | — |
| `attestation_issued_on` | `DATE` | NULL | — |
| `attestation_valid_until` | `DATE` | NULL | — |
| `attestation_document_id` | `INTEGER` | NULL | — |
| `attestation_smb_path` | `TEXT` | NOT NULL | — |
| `attestation_notice_days` | `INTEGER` | NOT NULL | — |
| `openproject_project_id` | `INTEGER` | NULL | — |
| `notes` | `TEXT` | NOT NULL | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `assets` (22 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `code` | `VARCHAR(80)` | UQ | — |
| `oi_id` | `INTEGER` | FK, NULL | `information_objects.id` |
| `serial_number` | `VARCHAR(150)` | NOT NULL | — |
| `inventory_number` | `VARCHAR(150)` | NOT NULL | — |
| `device_type` | `VARCHAR(100)` | NOT NULL | — |
| `model` | `VARCHAR(200)` | NOT NULL | — |
| `os_name` | `VARCHAR(150)` | NOT NULL | — |
| `os_version` | `VARCHAR(100)` | NOT NULL | — |
| `network_segment` | `VARCHAR(150)` | NOT NULL | — |
| `ip_address` | `VARCHAR(60)` | NOT NULL | — |
| `hostname` | `VARCHAR(250)` | NOT NULL | — |
| `domain_name` | `VARCHAR(250)` | NOT NULL | — |
| `seal_state` | `VARCHAR(36)` | NOT NULL | — |
| `status` | `VARCHAR(40)` | NOT NULL | — |
| `savz_name` | `VARCHAR(200)` | NOT NULL | — |
| `savz_version` | `VARCHAR(120)` | NOT NULL | — |
| `szi_nsd_name` | `VARCHAR(200)` | NOT NULL | — |
| `szi_nsd_version` | `VARCHAR(120)` | NOT NULL | — |
| `notes` | `TEXT` | NOT NULL | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `asset_mni` (6 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `asset_id` | `INTEGER` | FK | `assets.id` |
| `serial_number` | `VARCHAR(150)` | NOT NULL | — |
| `accounting_number` | `VARCHAR(150)` | NOT NULL | — |
| `media_type` | `VARCHAR(60)` | NOT NULL | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |
**Составная уникальность:** (`asset_id`, `serial_number`)

#### `asset_zmni` (8 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `asset_id` | `INTEGER` | FK | `assets.id` |
| `serial_number` | `VARCHAR(150)` | NOT NULL | — |
| `accounting_number` | `VARCHAR(150)` | NOT NULL | — |
| `software_version` | `VARCHAR(120)` | NOT NULL | — |
| `container_filename` | `VARCHAR(255)` | NOT NULL | — |
| `container_issued_on` | `DATE` | NULL | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |
**Составная уникальность:** (`asset_id`, `serial_number`)

#### `zmni_container_history` (6 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `zmni_id` | `INTEGER` | FK | `asset_zmni.id` |
| `container_filename` | `VARCHAR(255)` | NOT NULL | — |
| `container_issued_on` | `DATE` | NULL | — |
| `recorded_by` | `INTEGER` | FK | `users.id` |
| `recorded_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `asset_components` (12 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `asset_id` | `INTEGER` | FK | `assets.id` |
| `kind` | `VARCHAR(35)` | NOT NULL | — |
| `manufacturer` | `VARCHAR(150)` | NOT NULL | — |
| `model` | `VARCHAR(200)` | NOT NULL | — |
| `serial_number` | `VARCHAR(150)` | NOT NULL | — |
| `inventory_number` | `VARCHAR(150)` | NOT NULL | — |
| `installed_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `removed_at` | `TIMESTAMPTZ` | NULL | — |
| `removal_reason` | `TEXT` | NOT NULL | — |
| `document_id` | `INTEGER` | FK, NULL | `documents.id` |
| `created_by` | `INTEGER` | FK | `users.id` |

#### `asset_security_tools` (11 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `asset_id` | `INTEGER` | FK | `assets.id` |
| `name` | `VARCHAR(250)` | NOT NULL | — |
| `version` | `VARCHAR(120)` | NOT NULL | — |
| `license_ref` | `VARCHAR(150)` | NOT NULL | — |
| `expires_on` | `VARCHAR(10)` | NOT NULL | — |
| `installed_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `removed_at` | `TIMESTAMPTZ` | NULL | — |
| `removal_reason` | `TEXT` | NOT NULL | — |
| `document_id` | `INTEGER` | FK, NULL | `documents.id` |
| `created_by` | `INTEGER` | FK | `users.id` |

#### `shared_peripherals` (14 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `oi_id` | `INTEGER` | FK | `information_objects.id` |
| `kind` | `VARCHAR(35)` | NOT NULL | — |
| `name` | `VARCHAR(250)` | NOT NULL | — |
| `serial_number` | `VARCHAR(150)` | NOT NULL | — |
| `ip_address` | `VARCHAR(60)` | NOT NULL | — |
| `manufacturer` | `VARCHAR(150)` | NOT NULL | — |
| `model` | `VARCHAR(200)` | NOT NULL | — |
| `inventory_number` | `VARCHAR(150)` | NOT NULL | — |
| `media_present` | `BOOLEAN` | NOT NULL | — |
| `media_kind` | `VARCHAR(100)` | NOT NULL | — |
| `media_serial_number` | `VARCHAR(150)` | NOT NULL | — |
| `media_inventory_number` | `VARCHAR(150)` | NOT NULL | — |
| `created_by` | `INTEGER` | FK | `users.id` |

#### `asset_peripheral_access` (13 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `asset_id` | `INTEGER` | FK | `assets.id` |
| `peripheral_id` | `INTEGER` | FK | `shared_peripherals.id` |
| `allowed_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `revoked_at` | `TIMESTAMPTZ` | NULL | — |
| `reason` | `TEXT` | NOT NULL | — |
| `connection_type` | `VARCHAR(32)` | NOT NULL | — |
| `driver_name` | `VARCHAR(250)` | NOT NULL | — |
| `driver_version` | `VARCHAR(120)` | NOT NULL | — |
| `driver_smb_path` | `VARCHAR(700)` | NOT NULL | — |
| `driver_sha256` | `VARCHAR(64)` | NOT NULL | — |
| `driver_document_id` | `INTEGER` | NULL | — |
| `created_by` | `INTEGER` | FK | `users.id` |

### Заявки, ремонт и проверки СВТ
#### `registry_requests` (9 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `segment` | `VARCHAR(150)` | NOT NULL | — |
| `full_name` | `VARCHAR(180)` | NOT NULL | — |
| `system_type_id` | `INTEGER` | FK, NULL | `system_types.id` |
| `ip_address` | `VARCHAR(60)` | NOT NULL | — |
| `scan_smb_path` | `TEXT` | NOT NULL | — |
| `asset_id` | `INTEGER` | FK, NULL | `assets.id` |
| `created_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `system_types` (4 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `name` | `VARCHAR(180)` | UQ | — |
| `active` | `BOOLEAN` | NOT NULL | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `oi_proposals` (14 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `requester_id` | `INTEGER` | FK | `users.id` |
| `code` | `VARCHAR(80)` | NOT NULL | — |
| `name` | `VARCHAR(250)` | NOT NULL | — |
| `classification` | `VARCHAR(250)` | NOT NULL | — |
| `location` | `VARCHAR(250)` | NOT NULL | — |
| `notes` | `TEXT` | NOT NULL | — |
| `document_id` | `INTEGER` | FK, NULL | `documents.id` |
| `status` | `VARCHAR(32)` | NOT NULL | — |
| `review_note` | `TEXT` | NOT NULL | — |
| `reviewed_by` | `INTEGER` | FK, NULL | `users.id` |
| `reviewed_at` | `TIMESTAMPTZ` | NULL | — |
| `created_oi_id` | `INTEGER` | FK, NULL | `information_objects.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `service_requests` (12 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `asset_id` | `INTEGER` | FK | `assets.id` |
| `reporter` | `VARCHAR(180)` | NOT NULL | — |
| `reported_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `subject` | `VARCHAR(350)` | NOT NULL | — |
| `fault_description` | `TEXT` | NOT NULL | — |
| `status` | `VARCHAR(30)` | NOT NULL | — |
| `openproject_work_package_id` | `INTEGER` | NULL | — |
| `document_id` | `INTEGER` | FK, NULL | `documents.id` |
| `created_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `closed_at` | `TIMESTAMPTZ` | NULL | — |

#### `work_entries` (14 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `asset_id` | `INTEGER` | FK | `assets.id` |
| `service_request_id` | `INTEGER` | FK, NULL | `service_requests.id` |
| `performed_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `performer` | `VARCHAR(180)` | NOT NULL | — |
| `work_type` | `VARCHAR(40)` | NOT NULL | — |
| `actions` | `TEXT` | NOT NULL | — |
| `result` | `TEXT` | NOT NULL | — |
| `seal_state_after` | `VARCHAR(36)` | NOT NULL | — |
| `seal_note` | `TEXT` | NOT NULL | — |
| `document_page` | `INTEGER` | NULL | — |
| `document_id` | `INTEGER` | FK, NULL | `documents.id` |
| `created_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `asset_inspections` (14 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `asset_id` | `INTEGER` | FK | `assets.id` |
| `inspected_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `inspector` | `VARCHAR(180)` | NOT NULL | — |
| `subject_user` | `VARCHAR(180)` | NOT NULL | — |
| `checklist` | `JSON` | NOT NULL | — |
| `violation_categories` | `JSON` | NOT NULL | — |
| `finding_summary` | `TEXT` | NOT NULL | — |
| `corrective_action` | `TEXT` | NOT NULL | — |
| `document_page` | `INTEGER` | NULL | — |
| `status` | `VARCHAR(30)` | NOT NULL | — |
| `document_id` | `INTEGER` | FK, NULL | `documents.id` |
| `created_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

### Проверки ОИ и управление конфигурацией
#### `oi_reviews` (8 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `oi_id` | `INTEGER` | FK | `information_objects.id` |
| `reviewed_on` | `DATE` | NOT NULL | — |
| `reviewer` | `VARCHAR(180)` | NOT NULL | — |
| `report_smb_path` | `TEXT` | NOT NULL | — |
| `notes` | `TEXT` | NOT NULL | — |
| `created_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `oi_review_findings` (10 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `review_id` | `INTEGER` | FK | `oi_reviews.id` |
| `category` | `VARCHAR(20)` | NOT NULL | — |
| `description` | `TEXT` | NOT NULL | — |
| `corrective_action` | `TEXT` | NOT NULL | — |
| `resolved` | `BOOLEAN` | NOT NULL | — |
| `resolved_at` | `TIMESTAMPTZ` | NULL | — |
| `resolved_by` | `INTEGER` | FK, NULL | `users.id` |
| `created_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `configuration_baselines` (13 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `oi_id` | `INTEGER` | FK | `information_objects.id` |
| `version` | `VARCHAR(80)` | NOT NULL | — |
| `status` | `VARCHAR(20)` | NOT NULL | — |
| `snapshot` | `JSON` | NOT NULL | — |
| `snapshot_sha256` | `VARCHAR(64)` | NOT NULL | — |
| `notes` | `TEXT` | NOT NULL | — |
| `document_id` | `INTEGER` | FK, NULL | `documents.id` |
| `created_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `approved_by` | `INTEGER` | FK, NULL | `users.id` |
| `approved_at` | `TIMESTAMPTZ` | NULL | — |
| `approval_note` | `TEXT` | NOT NULL | — |
**Составная уникальность:** (`oi_id`, `version`)

#### `configuration_changes` (14 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `oi_id` | `INTEGER` | FK | `information_objects.id` |
| `asset_id` | `INTEGER` | FK, NULL | `assets.id` |
| `change_type` | `VARCHAR(30)` | NOT NULL | — |
| `status` | `VARCHAR(24)` | NOT NULL | — |
| `summary` | `VARCHAR(350)` | NOT NULL | — |
| `justification` | `TEXT` | NOT NULL | — |
| `document_id` | `INTEGER` | FK, NULL | `documents.id` |
| `openproject_work_package_id` | `INTEGER` | NULL | — |
| `created_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `updated_by` | `INTEGER` | FK, NULL | `users.id` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `resolution` | `TEXT` | NOT NULL | — |

### Конструктор полей и документы
#### `field_definitions` (8 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `entity_type` | `VARCHAR(20)` | NOT NULL | — |
| `scope_entity_id` | `INTEGER` | NULL | — |
| `name` | `VARCHAR(150)` | NOT NULL | — |
| `field_type` | `VARCHAR(20)` | NOT NULL | — |
| `options` | `JSON` | NOT NULL | — |
| `required` | `BOOLEAN` | NOT NULL | — |
| `active` | `BOOLEAN` | NOT NULL | — |
**Составная уникальность:** (`entity_type`, `scope_entity_id`, `name`)

#### `field_values` (8 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `entity_type` | `VARCHAR(20)` | NOT NULL | — |
| `entity_id` | `INTEGER` | NOT NULL | — |
| `field_id` | `INTEGER` | FK | `field_definitions.id` |
| `value` | `JSON` | NULL | — |
| `value_text` | `TEXT` | NOT NULL | — |
| `updated_by` | `INTEGER` | FK | `users.id` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | — |
**Составная уникальность:** (`entity_type`, `entity_id`, `field_id`)

#### `field_value_revisions` (7 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `entity_type` | `VARCHAR(20)` | NOT NULL | — |
| `entity_id` | `INTEGER` | NOT NULL | — |
| `field_id` | `INTEGER` | FK | `field_definitions.id` |
| `value` | `JSON` | NULL | — |
| `updated_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `field_assertion_revisions` (7 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `entity_type` | `VARCHAR(20)` | NOT NULL | — |
| `entity_id` | `INTEGER` | NOT NULL | — |
| `field_key` | `VARCHAR(80)` | NOT NULL | — |
| `value_hash` | `VARCHAR(64)` | NOT NULL | — |
| `changed_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `field_evidence` (13 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `entity_type` | `VARCHAR(20)` | NOT NULL | — |
| `entity_id` | `INTEGER` | NOT NULL | — |
| `field_key` | `VARCHAR(80)` | NOT NULL | — |
| `value_hash` | `VARCHAR(64)` | NOT NULL | — |
| `value_revision_id` | `INTEGER` | FK | `field_assertion_revisions.id` |
| `document_id` | `INTEGER` | FK | `documents.id` |
| `kind` | `VARCHAR(20)` | NOT NULL | — |
| `locator_type` | `VARCHAR(30)` | NOT NULL | — |
| `locator_value` | `VARCHAR(150)` | NOT NULL | — |
| `comment` | `VARCHAR(500)` | NOT NULL | — |
| `created_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `documents` (10 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `title` | `VARCHAR(250)` | NOT NULL | — |
| `original_filename` | `VARCHAR(255)` | NOT NULL | — |
| `storage_key` | `VARCHAR(64)` | UQ | — |
| `content_type` | `VARCHAR(120)` | NOT NULL | — |
| `sha256` | `VARCHAR(64)` | NOT NULL | — |
| `size_bytes` | `INTEGER` | NOT NULL | — |
| `supersedes_id` | `INTEGER` | FK, NULL | `documents.id` |
| `created_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

### Пользователи, аудит и мероприятия
#### `planned_activities` (24 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `event_key` | `VARCHAR(200)` | UQ | — |
| `event_type` | `VARCHAR(35)` | NOT NULL | — |
| `oi_id` | `INTEGER` | FK | `information_objects.id` |
| `asset_id` | `INTEGER` | FK, NULL | `assets.id` |
| `period_key` | `VARCHAR(32)` | NOT NULL | — |
| `deadline` | `DATE` | NOT NULL | — |
| `subject` | `VARCHAR(350)` | NOT NULL | — |
| `status` | `VARCHAR(30)` | NOT NULL | — |
| `sync_status` | `VARCHAR(30)` | NOT NULL | — |
| `openproject_project_id` | `INTEGER` | NULL | — |
| `openproject_work_package_id` | `INTEGER` | NULL | — |
| `sync_error` | `VARCHAR(500)` | NOT NULL | — |
| `last_sync_at` | `TIMESTAMPTZ` | NULL | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `rule_id` | `INTEGER` | FK, NULL | `control_rules.id` |
| `assignee` | `VARCHAR(180)` | NOT NULL | — |
| `evidence_document_id` | `INTEGER` | FK, NULL | `documents.id` |
| `completion_note` | `TEXT` | NOT NULL | — |
| `completed_by` | `INTEGER` | FK, NULL | `users.id` |
| `completed_at` | `TIMESTAMPTZ` | NULL | — |
| `remote_status` | `VARCHAR(120)` | NOT NULL | — |
| `remote_checked_at` | `TIMESTAMPTZ` | NULL | — |

#### `control_rules` (10 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `title` | `VARCHAR(250)` | NOT NULL | — |
| `scope` | `VARCHAR(16)` | NOT NULL | — |
| `oi_id` | `INTEGER` | FK, NULL | `information_objects.id` |
| `first_due` | `DATE` | NOT NULL | — |
| `interval_months` | `INTEGER` | NOT NULL | — |
| `assignee` | `VARCHAR(180)` | NOT NULL | — |
| `active` | `BOOLEAN` | NOT NULL | — |
| `created_by` | `INTEGER` | FK | `users.id` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `oi_transfer_approvals` (10 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `VARCHAR(36)` | PK | — |
| `actor_id` | `INTEGER` | FK | `users.id` |
| `object_code` | `VARCHAR(80)` | NOT NULL | — |
| `mode` | `VARCHAR(12)` | NOT NULL | — |
| `archive_digest` | `VARCHAR(64)` | NOT NULL | — |
| `baseline_digest` | `VARCHAR(64)` | NOT NULL | — |
| `confirm_digest` | `VARCHAR(64)` | NOT NULL | — |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `used_at` | `TIMESTAMPTZ` | NULL | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `audit_events` (10 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `actor_id` | `INTEGER` | FK | `users.id` |
| `action` | `VARCHAR(80)` | NOT NULL | — |
| `entity_type` | `VARCHAR(40)` | NOT NULL | — |
| `entity_id` | `INTEGER` | NOT NULL | — |
| `details` | `JSON` | NOT NULL | — |
| `request_id` | `VARCHAR(36)` | NOT NULL | — |
| `source_ip` | `VARCHAR(60)` | NOT NULL | — |
| `user_agent` | `VARCHAR(256)` | NOT NULL | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `users` (9 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `username` | `VARCHAR(100)` | UQ | — |
| `password_hash` | `VARCHAR(255)` | NOT NULL | — |
| `role` | `VARCHAR(20)` | NOT NULL | — |
| `display_name` | `VARCHAR(180)` | NOT NULL | — |
| `must_change_password` | `BOOLEAN` | NOT NULL | — |
| `created_by` | `INTEGER` | NULL | — |
| `active` | `BOOLEAN` | NOT NULL | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

#### `login_sessions` (6 полей)
| Поле | Тип | Признаки | Ссылка FK |
|---|---|---|---|
| `id` | `INTEGER` | PK | — |
| `user_id` | `INTEGER` | FK | `users.id` |
| `token_hash` | `VARCHAR(64)` | UQ | — |
| `csrf_hash` | `VARCHAR(64)` | NOT NULL | — |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | — |

## Отношения без настоящего внешнего ключа
- `field_values.entity_type + entity_id`, `field_value_revisions.entity_type + entity_id`, `field_assertion_revisions.entity_type + entity_id`, `field_evidence.entity_type + entity_id`, `audit_events.entity_type + entity_id`: логические полиморфные ссылки на ОИ/СВТ/заявки; PostgreSQL **не обеспечивает** FK-целостность этих связей.
- `field_definitions.scope_entity_id`: числовая область действия без FK, по `entity_type`.
- `information_objects.attestation_document_id`: устаревший числовой идентификатор без FK; актуальная ссылка на аттестационный документ — `attestation_smb_path TEXT`.
- `asset_peripheral_access.driver_document_id`: INTEGER, но FK на `documents` в ORM не объявлен.
- `openproject_project_id`/`openproject_work_package_id`: внешние идентификаторы OpenProject, а не FK внутри этой PostgreSQL.
## Важные особенности
- `assets.oi_id NULL` — СВТ существует без ОИ.
- `asset_mni` и `asset_zmni` — разные таблицы. По ЗМНИ учёт `serial_number`, `accounting_number`, `software_version`, `container_filename`, `container_issued_on`; история отдельная `zmni_container_history`.
- `registry_requests.system_type_id` и `system_types` остаются в модели как **устаревшая совместимость**, хотя «Тип системы» убран из интерфейса v0.6.2.
- `registry_requests` (административные заявки) не то же самое, что `service_requests` (неисправности). `work_entries` хранит фактические работы; `service_request_id` может быть `NULL`, т. е. профилактика без заявки возможна.
- `oi_reviews` / `oi_review_findings` — проверки ОИ и устранение каждого замечания, а `asset_inspections` — проверки конкретных СВТ.
- `documents` — метаданные оригинала; сами файловые байты хранятся в отдельном Docker-томе; SMB-пути как строки не становятся внешними ключами PostgreSQL.
- `0010_oi_reviews` и `0011_svt_media_protection` входят в пакет v0.7.0-rc1; их применение на реальной PostgreSQL пользователя не подтверждено исходниками.
