# API v0.2

- `GET/POST /api/assets/{id}/components`; `POST /api/assets/{id}/components/{component_id}/remove`
- `GET/POST /api/objects/{id}/peripherals`; `GET/POST /api/assets/{id}/peripherals`; `POST /api/assets/{id}/peripherals/{link_id}/revoke`
- `GET/POST /api/assets/{id}/security-tools`; `POST /api/assets/{id}/security-tools/{tool_id}/remove`
- `GET/POST /api/assets/{id}/requests`; `POST /api/assets/{id}/requests/{request_id}/close`
- `GET/POST /api/assets/{id}/works`
- `GET/POST /api/assets/{id}/inspections`; `GET /api/inspections/quarterly-status`
- `GET/POST /api/objects/{id}/baselines`; `POST /api/objects/{id}/baselines/{baseline_id}/approve`; `GET /api/objects/{id}/configuration/compare`
- `GET/POST /api/objects/{id}/changes`; `PATCH /api/objects/{id}/changes/{change_id}`

All mutating calls require admin session and CSRF header; all records are audited. `seal_state_after` is required after repair. Inactive components and previous inspections are retained, not deleted. v0.2 schema migrations: `0002_configuration`, `0003_asset_lifecycle`. Tested against disposable SQLite and old v0.1 SQLite schema; PostgreSQL target needs runtime acceptance testing on Debian.
