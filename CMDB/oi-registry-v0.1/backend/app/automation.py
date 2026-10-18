"""Idempotent local planning of required controls; synchronization is separate and opt-in."""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from calendar import monthrange
from sqlalchemy import select, text
from app.models import Asset, AssetInspection, InformationObject, PlannedActivity


def quarter_bounds(today: date):
    quarter=(today.month-1)//3+1
    end_month=quarter*3
    end=date(today.year,end_month,monthrange(today.year,end_month)[1])
    start=date(today.year,end_month-2,1)
    return start,end,f"{today.year}Q{quarter}"


def candidates(db, today:date):
    """Only valid_until explicitly set is used; no invented universal attestation term."""
    entries=[]
    objects={o.id:o for o in db.scalars(select(InformationObject).order_by(InformationObject.id))}
    for oi in objects.values():
        if oi.attestation_valid_until and oi.attestation_valid_until <= today+timedelta(days=oi.attestation_notice_days):
            until=oi.attestation_valid_until
            entries.append(dict(event_key=f"attestation:{oi.id}:{until.isoformat()}", event_type='attestation',
                oi_id=oi.id, asset_id=None, period_key=until.isoformat(), deadline=until,
                subject=f"{oi.code}: контроль срока аттестации ОИ",openproject_project_id=oi.openproject_project_id))
    first,last,period=quarter_bounds(today)
    assets=list(db.scalars(select(Asset).order_by(Asset.id)))
    inspected=set(db.scalars(select(AssetInspection.asset_id).where(
        AssetInspection.inspected_at>=datetime(first.year,first.month,first.day,tzinfo=timezone.utc),
        AssetInspection.inspected_at<datetime((last+timedelta(days=1)).year,(last+timedelta(days=1)).month,(last+timedelta(days=1)).day,tzinfo=timezone.utc))))
    for asset in assets:
        if asset.status.lower() in {'retired','decommissioned','written_off','disposed','списан','списано'}:
            continue
        oi=objects.get(asset.oi_id)
        if not oi: continue
        entries.append(dict(event_key=f"inspection:{asset.id}:{period}",event_type='quarterly_inspection',
            oi_id=asset.oi_id,asset_id=asset.id,period_key=period,deadline=last,
            subject=f"{oi.code}: квартальная проверка СВТ {asset.code}",openproject_project_id=oi.openproject_project_id,
            inspected=asset.id in inspected))
    return entries


def plan(db, today:date, write=False):
    """Dry run by default. Database unique key guards duplicates under multiple executions."""
    if not isinstance(today,date):raise TypeError('today must be date')
    if write and db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(20261018)'))
    expected=candidates(db,today)
    active_attestation={x['event_key'] for x in expected if x['event_type']=='attestation'}
    existing={x.event_key:x for x in db.scalars(select(PlannedActivity))}
    new=[]; refreshed=0; resolved=0; superseded=0; reopened=0
    for activity in existing.values():
        if activity.event_type=='attestation' and activity.event_key not in active_attestation and activity.status in ('open','acknowledged'):
            superseded+=1
            if write:
                activity.status='superseded'
                if activity.sync_status=='published':
                    activity.sync_error='Срок аттестации обновлён: проверьте ранее созданную задачу OpenProject'
    for item in expected:
        was_inspected=item.pop('inspected',False)
        key=item['event_key']
        current=existing.get(key)
        if current is None:
            status='satisfied' if was_inspected else 'open'
            new.append({**item,'status':status,'sync_status':'not_sent'})
            if write:db.add(PlannedActivity(**item,status=status))
        elif current.event_type=='attestation' and current.status=='superseded':
            reopened+=1
            if write: current.status='open'
        elif current.event_type=='quarterly_inspection' and was_inspected and current.status in ('open','acknowledged'):
            resolved+=1
            if write: current.status='satisfied'
        elif current.status=='open':
            refreshed+=1
    if write:
        db.commit()
    return {'as_of':today.isoformat(),'candidate_count':len(expected),'new_count':len(new),
            'already_open_count':refreshed,'satisfied_existing_count':resolved,'superseded_count':superseded,'reopened_count':reopened,
            'preview':new[:50],'preview_truncated':len(new)>50,'written':write}
