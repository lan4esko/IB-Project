'use strict';
// v0.7.0-rc1: safe query builder, asset media and OI inspection UX.

async function viewAssetQuery(){
  const fields=(await loadFields('asset')).filter(f=>f.active && !f.scope_entity_id);
  const system=[['code','Код СВТ'],['oi_code','ОИ'],['serial_number','Заводской номер'],
    ['inventory_number','Инвентарный номер'],['device_type','Тип СВТ'],['model','Модель'],
    ['os_name','ОС'],['os_version','Версия ОС'],['network_segment','Сегмент'],
    ['ip_address','IP'],['hostname','Имя узла'],['domain_name','Домен'],
    ['seal_state','Пломба'],['status','Статус'],['notes','Примечания'],
    ['savz_name','САВЗ'],['savz_version','Версия САВЗ'],
    ['szi_nsd_name','СЗИ от НСД'],['szi_nsd_version','Версия СЗИ от НСД']];
  const opts=[...system,...fields.map(f=>['custom:'+f.id,f.name])];
  const dropdown=opts.map(([id,label])=>`<option value="${esc(id)}">${esc(label)}</option>`).join('');
  const filters=[];
  shell(`<div class="section-head"><h1>Построитель запросов СВТ</h1><button id="builder-back">К реестру</button></div>
    <p class="subtitle">Выбор колонок и фильтров без SQL. Доступны типовые поля главного администратора.</p>
    <div class="card"><h2>Колонки в CSV</h2><div id="builder-cols" class="checkrow">${opts.map(([id,label])=>`<label><input type="checkbox" value="${esc(id)}" ${['code','oi_code','serial_number'].includes(id)?'checked':''}> ${esc(label)}</label>`).join('')}</div></div>
    <div class="card"><h2>Фильтры (до 8, объединение И)</h2><button id="builder-add-filter" type="button">+ Условие</button><div id="builder-filters"></div></div>
    <div class="toolbar"><button id="builder-preview" class="primary">Предпросмотр</button><button id="builder-export">Экспорт CSV</button></div><div id="builder-result"></div>`);
  document.querySelector('#builder-back').onclick=()=>route('assets');
  function renderFilters(){document.querySelector('#builder-filters').innerHTML=filters.map((f,i)=>`<div class="row" data-builder-filter="${i}">
    <select data-part="field">${opts.map(([id,label])=>`<option value="${esc(id)}" ${f.field===id?'selected':''}>${esc(label)}</option>`).join('')}</select>
    <select data-part="op"><option value="eq" ${f.op==='eq'?'selected':''}>Равно</option><option value="contains" ${f.op==='contains'?'selected':''}>Содержит</option>
    <option value="empty" ${f.op==='empty'?'selected':''}>Пусто</option><option value="not_empty" ${f.op==='not_empty'?'selected':''}>Не пусто</option></select>
    <input data-part="value" maxlength="250" value="${esc(f.value)}" placeholder="Значение">
    <button type="button" data-filter-remove="${i}">×</button></div>`).join('');
    document.querySelectorAll('[data-builder-filter]').forEach(el=>el.querySelectorAll('[data-part]').forEach(input=>input.onchange=()=>{const i=Number(el.dataset.builderFilter);filters[i][input.dataset.part]=input.value;}));
    document.querySelectorAll('[data-filter-remove]').forEach(btn=>btn.onclick=()=>{filters.splice(Number(btn.dataset.filterRemove),1);renderFilters();});
  }
  document.querySelector('#builder-add-filter').onclick=()=>{if(filters.length>=8){notify('Максимум 8 фильтров',true);return;}filters.push({field:opts[0][0],op:'eq',value:''});renderFilters();};
  function payload(){return {columns:[...document.querySelectorAll('#builder-cols input:checked')].map(x=>x.value),filters};}
  document.querySelector('#builder-preview').onclick=async()=>{try{const result=await api('/assets/query/preview',{method:'POST',json:payload()});
    document.querySelector('#builder-result').innerHTML=`<div class="card"><h2>Предпросмотр: ${result.rows.length} записей ${result.truncated?'(показаны первые 200)':''}</h2><div class="tablewrap"><table><thead><tr>${result.columns.map(c=>`<th>${esc(c.label)}</th>`).join('')}</tr></thead><tbody>${result.rows.map(r=>`<tr>${result.columns.map(c=>`<td>${esc(r[c.id])}</td>`).join('')}</tr>`).join('')||'<tr><td>Нет данных</td></tr>'}</tbody></table></div></div>`;
  }catch(e){notify(e.message,true);}};
  document.querySelector('#builder-export').onclick=async()=>{try{
    const resp=await fetch('/api/assets/query/export.csv',{method:'POST',credentials:'same-origin',
      headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify(payload())});
    if(!resp.ok){let detail;try{detail=(await resp.json()).detail;}catch{detail='HTTP '+resp.status;}throw Error(detail);}
    const url=URL.createObjectURL(await resp.blob());const link=document.createElement('a');link.href=url;link.download='svt-selected.csv';document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
  }catch(e){notify(e.message,true);}};
}

async function viewAssetMedia(arg){
  if(!arg?.id)return route('assets');
  const id=arg.id;
  const [svt,mni,zmni]=await Promise.all([api('/assets/'+id),api('/assets/'+id+'/mni'),api('/assets/'+id+'/zmni')]);
  shell(`<div class="section-head"><h1>МНИ и ЗМНИ — ${esc(svt.code)}</h1><button id="media-back">К карточке СВТ</button></div>
  <p class="subtitle">МНИ — внутренние диски. ЗМНИ — защищённые носители с файлом-контейнером. Это разные реестры.</p>
  <div class="card"><h2>МНИ — внутренние диски (${mni.length})</h2><div class="tablewrap"><table><thead><tr><th>Тип</th><th>Заводской номер</th><th>Учётный номер</th><th></th></tr></thead><tbody>${mni.map(x=>`<tr><td>${esc(x.media_type)}</td><td>${esc(x.serial_number)}</td><td>${esc(x.accounting_number)}</td><td>${allowed()?`<button data-mni-edit="${x.id}" class="small">Исправить</button>`:""}</td></tr>`).join('')||'<tr><td colspan="4">Нет записей</td></tr>'}</tbody></table></div>
  ${allowed()?`<form id="mni-add" class="formgrid"><div><label>Тип HDD/SSD</label><input name="media_type" maxlength="60" placeholder="SSD"></div><div><label>Заводской номер</label><input name="serial_number" required maxlength="150"></div><div><label>Учётный номер</label><input name="accounting_number" required maxlength="150"></div><div class="full"><button class="primary">Добавить МНИ</button></div></form>`:''}</div>
  <div class="card"><h2>ЗМНИ — защищённые носители (${zmni.length})</h2><div class="tablewrap"><table><thead><tr><th>Заводской номер</th><th>Учётный номер</th><th>Версия ПО ЗМНИ</th><th>Имя контейнера</th><th>Дата выпуска</th><th></th></tr></thead><tbody>${zmni.map(x=>`<tr><td>${esc(x.serial_number)}</td><td>${esc(x.accounting_number)}</td><td>${esc(x.software_version)}</td><td>${esc(x.container_filename)}</td><td>${esc(x.container_issued_on||'—')}</td><td><button data-zmni-history="${x.id}" class="small">История</button> ${allowed()?`<button data-zmni-edit="${x.id}" class="small">Исправить №</button> <button data-zmni-renew="${x.id}" class="small">Перевыпуск</button>`:''}</td></tr>`).join('')||'<tr><td colspan="6">Нет записей</td></tr>'}</tbody></table></div>
  ${allowed()?`<form id="zmni-add" class="formgrid"><div><label>Заводской номер</label><input name="serial_number" required maxlength="150"></div><div><label>Учётный номер</label><input name="accounting_number" required maxlength="150"></div><div><label>Версия ПО ЗМНИ</label><input name="software_version" maxlength="120"></div><div><label>Имя файла контейнера</label><input name="container_filename" maxlength="255"></div><div><label>Дата выпуска</label><input name="container_issued_on" type="date"></div><div class="full"><button class="primary">Добавить ЗМНИ</button></div></form>`:''}</div>`);
  document.querySelector('#media-back').onclick=()=>route('detail',{type:'asset',id});
  document.querySelector('#mni-add')?.addEventListener('submit',async e=>{e.preventDefault();try{await api(`/assets/${id}/mni`,{method:'POST',json:Object.fromEntries(new FormData(e.target))});await viewAssetMedia(arg);notify('МНИ учтён');}catch(err){notify(err.message,true);}});
  document.querySelector('#zmni-add')?.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.container_issued_on=data.container_issued_on||null;try{await api(`/assets/${id}/zmni`,{method:'POST',json:data});await viewAssetMedia(arg);notify('ЗМНИ учтён');}catch(err){notify(err.message,true);}});
  document.querySelectorAll('[data-mni-edit]').forEach(b=>b.onclick=async()=>{
    const x=mni.find(y=>y.id===Number(b.dataset.mniEdit));if(!x)return;
    const serial=prompt('Заводской номер МНИ',x.serial_number);if(serial===null)return;
    const accounting=prompt('Учётный номер МНИ',x.accounting_number);if(accounting===null)return;
    const type=prompt('Тип МНИ (HDD/SSD)',x.media_type);if(type===null)return;
    try{await api(`/assets/${id}/mni/${x.id}`,{method:'PATCH',json:{serial_number:serial,accounting_number:accounting,media_type:type}});
      await viewAssetMedia(arg);notify('Номера МНИ исправлены');}catch(e){notify(e.message,true);}
  });
  document.querySelectorAll('[data-zmni-edit]').forEach(b=>b.onclick=async()=>{
    const x=zmni.find(y=>y.id===Number(b.dataset.zmniEdit));if(!x)return;
    const serial=prompt('Заводской номер ЗМНИ',x.serial_number);if(serial===null)return;
    const accounting=prompt('Учётный номер ЗМНИ',x.accounting_number);if(accounting===null)return;
    const version=prompt('Версия ПО ЗМНИ',x.software_version);if(version===null)return;
    try{await api(`/assets/${id}/zmni/${x.id}`,{method:'PATCH',json:{serial_number:serial,accounting_number:accounting,software_version:version}});
      await viewAssetMedia(arg);notify('Сведения ЗМНИ исправлены');}catch(e){notify(e.message,true);}
  });
  document.querySelectorAll('[data-zmni-history]').forEach(b=>b.onclick=async()=>{try{const history=await api(`/assets/${id}/zmni/${b.dataset.zmniHistory}/history`);alert(history.map(h=>`${h.container_issued_on||'—'} · ${h.container_filename}`).join('\n')||'Переизданий не зарегистрировано');}catch(e){notify(e.message,true);}});
  document.querySelectorAll('[data-zmni-renew]').forEach(b=>b.onclick=async()=>{
    const item=zmni.find(x=>x.id===Number(b.dataset.zmniRenew));const filename=prompt('Новое имя файла контейнера',item.container_filename);
    if(filename===null)return;const issued=prompt('Дата выпуска контейнера (ГГГГ-ММ-ДД)',new Date().toISOString().slice(0,10));if(!issued)return;
    try{await api(`/assets/${id}/zmni/${item.id}/container`,{method:'POST',json:{container_filename:filename,container_issued_on:issued}});await viewAssetMedia(arg);notify('Перевыпуск контейнера зарегистрирован');}catch(e){notify(e.message,true);}
  });
}

async function viewOIReviews(arg){
  if(!arg?.id)return route('objects');
  const id=arg.id;const [oi,reviews]=await Promise.all([api('/objects/'+id),api('/objects/'+id+'/reviews')]);
  shell(`<div class="section-head"><h1>Проверки ОИ — ${esc(oi.code)}</h1><button id="reviews-back">К карточке ОИ</button></div>
  <p class="subtitle">Отчёт по SMB, выявленные недостатки и нарушения, индивидуальная отметка об устранении.</p>
  ${allowed()?`<div class="card"><h2>Добавить проверку</h2><form id="review-add" class="formgrid"><div><label>Дата</label><input name="reviewed_on" type="date" required></div><div><label>Проверяющий</label><input name="reviewer" required maxlength="180"></div><div><label>Путь отчёта в SMB-шаре</label><input name="report_smb_path" placeholder="\\\\server\\share\\report.pdf" maxlength="2048"></div><div><label>Примечание</label><textarea name="notes"></textarea></div><div class="full"><button class="primary">Создать проверку</button></div></form></div>`:''}
  ${reviews.map(r=>`<div class="card"><div class="section-head"><h2>Проверка #${r.id} от ${esc(r.reviewed_on)}</h2><span class="pill">Не устранено: ${r.open_count}</span></div>
  <p>Проверяющий: ${esc(r.reviewer)}. Отчёт: <code>${esc(r.report_smb_path||'не указан')}</code></p><p>${esc(r.notes)}</p>
  <div class="tablewrap"><table><thead><tr><th>Вид</th><th>Недостаток / нарушение</th><th>Устранение</th><th>Статус</th></tr></thead><tbody>
  ${r.findings.map(f=>`<tr><td>${f.category==='violation'?'Нарушение':'Недостаток'}</td><td>${esc(f.description)}</td><td>${esc(f.corrective_action)}</td><td>${allowed()?`<label><input type="checkbox" data-finding="${r.id}:${f.id}" ${f.resolved?'checked':''}> Устранено</label>`:f.resolved?'Устранено':'Не устранено'}</td></tr>`).join('')||'<tr><td colspan="4">Замечаний нет</td></tr>'}</tbody></table></div>
  ${allowed()?`<form data-review-add-finding="${r.id}" class="formgrid"><div><label>Категория</label><select name="category"><option value="deficiency">Недостаток</option><option value="violation">Нарушение</option></select></div><div><label>Описание замечания</label><input name="description" required maxlength="10000"></div><div><label>Корректирующее действие</label><input name="corrective_action" maxlength="10000"></div><div class="full"><button>Добавить пункт</button></div></form>`:''}</div>`).join('')||'<p class="muted">Проверок ещё нет.</p>'}`);
  document.querySelector('#reviews-back').onclick=()=>route('detail',{type:'oi',id});
  document.querySelector('#review-add')?.addEventListener('submit',async e=>{e.preventDefault();try{await api(`/objects/${id}/reviews`,{method:'POST',json:Object.fromEntries(new FormData(e.target))});await viewOIReviews(arg);notify('Проверка создана');}catch(err){notify(err.message,true);}});
  document.querySelectorAll('[data-review-add-finding]').forEach(f=>f.onsubmit=async e=>{e.preventDefault();try{await api(`/objects/${id}/reviews/${f.dataset.reviewAddFinding}/findings`,{method:'POST',json:Object.fromEntries(new FormData(f))});await viewOIReviews(arg);notify('Замечание добавлено');}catch(err){notify(err.message,true);}});
  document.querySelectorAll('[data-finding]').forEach(check=>check.onchange=async()=>{const [review,finding]=check.dataset.finding.split(':');let action='';if(check.checked){action=prompt('Что сделано для устранения?','');if(action===null){check.checked=false;return;}}
    try{await api(`/objects/${id}/reviews/${review}/findings/${finding}`,{method:'PATCH',json:{resolved:check.checked,corrective_action:action}});await viewOIReviews(arg);notify('Отметка сохранена');}catch(err){check.checked=!check.checked;notify(err.message,true);}
  });
}
