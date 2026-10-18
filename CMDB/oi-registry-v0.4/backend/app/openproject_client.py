"""Opt-in OpenProject API v3 publisher; never automatically retry uncertain requests."""
import base64
import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def enabled():
    return os.getenv('OI_OP_SYNC_ENABLED','false').strip().lower()=='true'


def configuration():
    if not enabled():raise ValueError('OpenProject sync disabled; configure OI_OP_SYNC_ENABLED=true')
    endpoint=os.getenv('OI_OP_BASE_URL','').rstrip('/')
    api_key=os.getenv('OI_OP_API_KEY','')
    type_id=os.getenv('OI_OP_TYPE_ID','')
    url=urlparse(endpoint)
    if not endpoint or not api_key or not type_id.isdigit() or int(type_id)<1:
        raise ValueError('OI_OP_BASE_URL, OI_OP_API_KEY and OI_OP_TYPE_ID are required')
    if url.scheme!='https' and not (url.scheme=='http' and url.hostname in {'host.docker.internal','127.0.0.1','localhost'} and os.getenv('OI_OP_ALLOW_LOCAL_HTTP','false')=='true'):
        raise ValueError('HTTPS required; local HTTP explicitly opt in by OI_OP_ALLOW_LOCAL_HTTP=true')
    if url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('Invalid OpenProject root URL')
    return endpoint,api_key,int(type_id)


def publish(activity, timeout=15):
    endpoint,key,type_id=configuration()
    if not activity.openproject_project_id:
        raise ValueError('Сначала задайте ID проекта OpenProject в карточке ОИ')
    marker=f'[OI-REGISTRY:{activity.event_key}]'
    # Marker allows an administrator to reconcile uncertain requests without duplicating them.
    description=(f'Контрольное мероприятие из OI Registry.\n'
        f'Ключ: {marker}\nДата контроля: {activity.deadline.isoformat()}\n'
        f'Сведения о СВТ и документах смотрите в локальном OI Registry.\n'
        f'Создание этой задачи не подтверждает выполнение контрольного мероприятия.')
    payload={'subject':activity.subject+' '+marker,
             'description':{'format':'plain','raw':description},
             '_links':{'type':{'href':f'/api/v3/types/{type_id}'}}}
    auth=base64.b64encode(('apikey:'+key).encode()).decode()
    req=Request(f'{endpoint}/api/v3/projects/{activity.openproject_project_id}/work_packages',
                data=json.dumps(payload,ensure_ascii=False).encode(),
                headers={'Authorization':'Basic '+auth,'Content-Type':'application/json',
                         'Accept':'application/hal+json'},method='POST')
    with urlopen(req,timeout=timeout) as response:
        data=json.load(response)
    work_id=data.get('id')
    if not isinstance(work_id,int) or work_id<=0:
        raise ValueError('OpenProject response lacks work package id; reconcile manually')
    return work_id
