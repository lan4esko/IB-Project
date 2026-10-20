"""Safe selectable-column query builder; never accepts executable SQL."""
import csv
import io
from fastapi import HTTPException
from sqlalchemy import and_, cast, exists, func, or_, select, String
from app.models import Asset, InformationObject, FieldDefinition, FieldValue

SYSTEM_COLUMNS = {
    'code':'Код СВТ', 'oi_code':'ОИ', 'serial_number':'Заводской номер',
    'inventory_number':'Инвентарный номер','device_type':'Тип СВТ',
    'model':'Модель','os_name':'ОС','os_version':'Версия ОС',
    'network_segment':'Сегмент', 'ip_address':'IP-адрес','hostname':'Имя узла',
    'domain_name':'Домен','seal_state':'Пломба', 'status':'Статус',
    'notes':'Примечания','savz_name':'САВЗ','savz_version':'Версия САВЗ',
    'szi_nsd_name':'СЗИ от НСД','szi_nsd_version':'Версия СЗИ от НСД',
}
OPERATORS = ('eq','contains','empty','not_empty')


def validate(db, columns, filters):
    if not (1 <= len(columns) <= 40) or len(set(columns)) != len(columns):
        raise HTTPException(422,'Выберите от 1 до 40 уникальных столбцов')
    if len(filters) > 8:
        raise HTTPException(422,'Не более 8 фильтров')
    ids = {int(k.split(':')[1]) for k in columns+[f.get('field','') for f in filters]
           if isinstance(k,str) and k.startswith('custom:') and k.split(':')[1].isdigit()}
    defs = {d.id:d for d in db.scalars(select(FieldDefinition).where(
        FieldDefinition.entity_type=='asset',FieldDefinition.active.is_(True),
        FieldDefinition.scope_entity_id.is_(None),FieldDefinition.id.in_(ids)))} if ids else {}
    for key in columns+[f.get('field') for f in filters]:
        if key in SYSTEM_COLUMNS: continue
        if not isinstance(key,str) or not key.startswith('custom:') or not key[7:].isdigit() or int(key[7:]) not in defs:
            raise HTTPException(422,'Недоступное поле: '+str(key)[:80])
    for f in filters:
        if not isinstance(f,dict) or f.get('op') not in OPERATORS or not isinstance(f.get('value',''),str) or len(f.get('value',''))>250:
            raise HTTPException(422,'Неверный фильтр')
    return defs


def compile_query(db,columns,filters):
    defs=validate(db,columns,filters)
    stmt=select(Asset,InformationObject.code.label('oi_code')).outerjoin(
        InformationObject,Asset.oi_id==InformationObject.id)
    for f in filters:
        key=f['field'];op=f['op'];value=f.get('value','')
        if key.startswith('custom:'):
            id_=int(key[7:]);predicate=(FieldValue.entity_type=='asset') & (
                FieldValue.field_id==id_) & (FieldValue.entity_id==Asset.id)
            if op=='empty':
                stmt=stmt.where(~exists(select(FieldValue.id).where(predicate,
                    FieldValue.value_text!='')))
            elif op=='not_empty':
                stmt=stmt.where(exists(select(FieldValue.id).where(predicate,
                    FieldValue.value_text!='')))
            else:
                filter_value=value.casefold()
                expr=FieldValue.value_text
                stmt=stmt.where(exists(select(FieldValue.id).where(predicate,
                    expr==filter_value if op=='eq' else expr.contains(filter_value,autoescape=True))))
        else:
            expression=InformationObject.code if key=='oi_code' else getattr(Asset,key)
            expression=cast(expression,String)
            if op=='empty': condition=or_(expression.is_(None),expression=='')
            elif op=='not_empty':condition=and_(expression.is_not(None),expression!='')
            elif op=='eq': condition=func.lower(expression)==value.casefold()
            else:condition=expression.ilike('%'+value.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%',escape='\\')
            stmt=stmt.where(condition)
    return stmt.order_by(Asset.code,Asset.id),defs


def rows(db, columns, filters, limit):
    stmt, defs=compile_query(db,columns,filters)
    data=list(db.execute(stmt.limit(limit+1)))
    truncated=len(data)>limit
    data=data[:limit]
    keys=[r.id for r,_ in data]
    custom={}
    custom_ids=[int(c[7:]) for c in columns if c.startswith('custom:')]
    if keys and custom_ids:
        for v in db.scalars(select(FieldValue).where(FieldValue.entity_type=='asset',
                FieldValue.entity_id.in_(keys),FieldValue.field_id.in_(custom_ids))):
            custom[(v.entity_id,v.field_id)]=v.value
    labels={**SYSTEM_COLUMNS,**{'custom:'+str(id_):d.name for id_,d in defs.items()}}
    result=[]
    for a,oi_code in data:
        result.append({key: (oi_code or '' if key=='oi_code' else
                    custom.get((a.id,int(key[7:]))) if key.startswith('custom:') else getattr(a,key))
                       for key in columns})
    return {'columns':[{'id':c,'label':labels[c]} for c in columns],
            'rows':result,'truncated':truncated}


def to_csv(result):
    buf=io.StringIO(newline='');writer=csv.writer(buf,delimiter=';',lineterminator='\r\n')
    writer.writerow([c['label'] for c in result['columns']])
    for row in result['rows']:
        vals=[]
        for c in result['columns']:
            value=row[c['id']]
            value='' if value is None else str(value)
            if value.lstrip().startswith(('=','+','-','@','\t','\r')):
                value="'"+value
            vals.append(value)
        writer.writerow(vals)
    return '\ufeff'+buf.getvalue()
