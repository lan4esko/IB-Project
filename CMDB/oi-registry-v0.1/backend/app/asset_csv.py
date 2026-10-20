"""SVT CSV importer. Preview is read-only; commit is explicitly confirmed in API."""
import csv
import hashlib
import io
from fastapi import HTTPException
from sqlalchemy import select
from app.models import Asset, InformationObject

FIELDS = ('code', 'serial_number', 'inventory_number', 'device_type', 'model', 'os_name',
          'os_version', 'network_segment', 'ip_address', 'hostname', 'domain_name',
          'seal_state', 'status', 'notes')
HEADERS = ('code', 'oi_code', *FIELDS[1:])
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 3000


def parse(raw):
    if not raw or len(raw) > MAX_BYTES:
        raise HTTPException(413, 'CSV пустой или больше 2 МБ')
    try:
        content = raw.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content, newline=''), delimiter=';')
        if tuple(reader.fieldnames or ()) != HEADERS:
            raise HTTPException(422, 'Нужен полный CSV с колонками: ' + ';'.join(HEADERS))
        rows = []
        seen = set()
        for row in reader:
            if len(rows) >= MAX_ROWS:
                raise HTTPException(413, 'Не более 3000 СВТ в одном файле')
            if None in row or any(v is None for v in row.values()):
                raise HTTPException(422, 'Неверное количество полей CSV')
            code = row['code'].strip()
            if not code or len(code) > 80 or code in seen:
                raise HTTPException(422, 'Пустой, длинный или повторяющийся код СВТ')
            seen.add(code)
            parsed = {field: row[field] for field in HEADERS}
            parsed['code'] = code
            if len(parsed['oi_code']) > 80 or any(len(value) > (10000 if key == 'notes' else 250) for key, value in parsed.items()):
                raise HTTPException(422, 'Превышена длина поля')
            if parsed['seal_state'] not in ('unknown', 'sealed', 'opened', 'unsealed_after_repair', 'seal_damaged', 'not_applicable'):
                raise HTTPException(422, 'Недопустимое состояние пломбы')
            rows.append(parsed)
        if not rows:
            raise HTTPException(422, 'CSV не содержит записей СВТ')
    except UnicodeError as exc:
        raise HTTPException(422, 'CSV должен быть в UTF-8') from exc
    except csv.Error as exc:
        raise HTTPException(422, 'Ошибка формата CSV') from exc
    return rows


def snapshot(db, rows):
    """Only impacted codes and referenced OI records; compare before commit."""
    codes = [r['code'] for r in rows]
    oi_codes = {r['oi_code'] for r in rows if r['oi_code']}
    return {
        'assets': [{f: getattr(a, f) for f in ('code', 'oi_id', *FIELDS[1:])}
                   for a in db.scalars(select(Asset).where(Asset.code.in_(codes)).order_by(Asset.code))],
        'oi': [(o.code, o.id) for o in db.scalars(select(InformationObject)
                .where(InformationObject.code.in_(oi_codes)).order_by(InformationObject.code))],
    }


def compare(db, rows, mode, marker=''):
    codes = [r['code'] for r in rows]
    found = {a.code: a for a in db.scalars(select(Asset).where(Asset.code.in_(codes)))}
    objects = {o.code: o.id for o in db.scalars(select(InformationObject))}
    conflicts = []
    actions = []
    for r in rows:
        if r['oi_code'] and r['oi_code'] not in objects:
            conflicts.append('Не найден ОИ: '+r['oi_code'])
        existing = found.get(r['code'])
        if mode == 'copy':
            actions.append({'code': r['code'], 'operation': 'copy', 'fields_changed': []})
            continue
        if existing is None:
            actions.append({'code': r['code'], 'operation': 'add', 'fields_changed': []})
            continue
        target_oi = objects.get(r['oi_code']) if r['oi_code'] else None
        differences = [field for field in FIELDS[1:] if r[field] != getattr(existing, field)]
        if existing.oi_id != target_oi:
            differences.append('oi_code')
        if mode == 'merge' and differences:
            conflicts.append('Конфликт СВТ: '+r['code']+' ['+', '.join(differences)+']')
        actions.append({'code': r['code'], 'operation': 'update' if mode == 'replace' and differences else 'unchanged',
                        'fields_changed': differences})
    return {'mode': mode, 'total': len(rows),
            'add': sum(a['operation'] in ('add', 'copy') for a in actions),
            'update': sum(a['operation'] == 'update' for a in actions),
            'unchanged': sum(a['operation'] == 'unchanged' for a in actions),
            'conflicts': conflicts, 'actions': actions, 'can_apply': not conflicts,
            'warning': 'Замена изменяет только совпадающие коды. Отсутствующие строки НЕ удаляются; история ремонтов сохраняется.'}


def apply(db, rows, mode, marker):
    objects = {o.code: o.id for o in db.scalars(select(InformationObject))}
    found = {a.code: a for a in db.scalars(select(Asset).where(Asset.code.in_(r['code'] for r in rows)))}
    for i, row in enumerate(rows):
        code = row['code']
        asset = None if mode == 'copy' else found.get(code)
        if mode == 'copy':
            code = (code[:59] + '-COPY-' + marker[:8] + '-' + str(i))[:80]
        data = {field: row[field] for field in FIELDS if field != 'code'}
        data.update({'code': code, 'oi_id': objects.get(row['oi_code']) if row['oi_code'] else None})
        if asset is None:
            db.add(Asset(**data))
        elif mode == 'replace':
            for field, value in data.items():
                setattr(asset, field, value)
    db.flush()
