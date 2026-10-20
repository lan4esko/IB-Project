'use strict';
// v0.6.2: no mandatory system type. Previous type links are preserved only in storage.
async function loadAllAssetsForRegistryRequests(){
  const result=[];
  for(let offset=0;offset<10000;offset+=1000){
    const response=await api('/assets?limit=1000&offset='+offset);
    result.push(...response.items);
    if(result.length>=response.total || response.items.length===0)break;
  }
  return result;
}
async function viewRegistryRequests(){
  const [requests,assets,defs]=await Promise.all([api('/registry-requests'),loadAllAssetsForRegistryRequests(),loadFields('request')]);
  const activeDefs=defs.filter(d=>d.active);const aopts=assets.map(a=>`<option value="${a.id}">${esc(a.code)} (${esc(a.oi_code||'без ОИ')})</option>`).join('');
  shell(`<div class="section-head"><h1>Заявки</h1><p class="subtitle">Сегмент, ФИО, IP-адрес, путь скана заявки в SMB и ссылка на СВТ. Ремонты ведутся отдельно в журнале СВТ.</p></div>
  <div class="card"><h2>Реестр заявок</h2><div class="tablewrap"><table><thead><tr><th>ID</th><th>Сегмент</th><th>ФИО</th><th>IP</th><th>Скан заявки</th><th>СВТ</th><th></th></tr></thead><tbody>
  ${requests.map(r=>`<tr><td>${r.id}</td><td>${esc(r.segment)}</td><td>${esc(r.full_name)}</td><td>${esc(r.ip_address)}</td><td><code>${esc(r.scan_smb_path)}</code></td><td>${esc(r.asset_code||'—')}</td><td>${allowed()?`<button class="small" data-request-edit="${r.id}">Изменить</button>`:''}</td></tr>`).join('')||'<tr><td colspan="7">Заявок нет</td></tr>'}</tbody></table></div></div>
  ${allowed()?`<div class="card"><h2 id="request-editor-title">Новая заявка</h2><form id="registry-request-form"><div class="formgrid">
    <div><label>Сегмент</label><input name="segment" maxlength="150"></div>
    <div><label>ФИО</label><input name="full_name" required maxlength="180"></div>
    <div><label>IP-адрес</label><input name="ip_address" placeholder="192.0.2.15 или IPv6"></div>
    <div><label>Путь скана в SMB-шаре</label><input name="scan_smb_path" maxlength="2048" placeholder="\\\\server\\share\\request.pdf"></div>
    <div><label>СВТ по реестру</label><select name="asset_id"><option value="">Без связи с СВТ</option>${aopts}</select></div>
    ${activeDefs.map(d=>`<div><label>${esc(d.name)} ${d.required?'*':''}</label>${fieldEditor(d).replace('name="value"',`name="custom:${d.id}"`)}</div>`).join('')}
    </div><div class="toolbar"><button type="submit" class="primary">Сохранить заявку</button><button type="button" id="request-reset">Очистить</button></div></form></div>`:''}`);
  let editing=null;
  const form=document.querySelector('#registry-request-form');
  document.querySelector('#request-reset')?.addEventListener('click',()=>{editing=null;form.reset();document.querySelector('#request-editor-title').textContent='Новая заявка';});
  document.querySelectorAll('[data-request-edit]').forEach(b=>b.onclick=()=>{
    const data=requests.find(r=>r.id===Number(b.dataset.requestEdit));if(!data)return;
    editing=data.id;
    for(const d of activeDefs){const ctrl=form.elements['custom:'+d.id];if(ctrl)ctrl.value=data.custom_fields?.[String(d.id)]??'';}
    for(const name of ['segment','full_name','ip_address','scan_smb_path','asset_id']) form.elements[name].value=data[name]??'';
    document.querySelector('#request-editor-title').textContent='Изменение заявки #'+data.id;
    form.scrollIntoView({behavior:'smooth'});
  });
  if(form)form.onsubmit=async e=>{
    e.preventDefault();const data=Object.fromEntries(new FormData(form));data.asset_id=data.asset_id?Number(data.asset_id):null;data.custom_fields={};for(const d of activeDefs){let value=data['custom:'+d.id];delete data['custom:'+d.id];if(d.field_type==='boolean')value=value==='true';else if(d.field_type==='number')value=value===''?null:Number(value);data.custom_fields[String(d.id)]=value;}
    try{await api('/registry-requests'+(editing?'/'+editing:''),{method:editing?'PATCH':'POST',json:data});await viewRegistryRequests();notify('Заявка сохранена');}catch(error){notify(error.message,true);}
  };
}
