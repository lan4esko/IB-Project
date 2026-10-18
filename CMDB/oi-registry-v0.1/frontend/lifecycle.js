'use strict';
// UI extensions v0.2. Shared api(), state, shell(), esc(), route() defined in app.js.
const componentNames = {system_unit:'Системный блок',disk:'Накопитель (HDD/SSD)',keyboard:'Клавиатура',mouse:'Мышь',power_supply:'Блок питания',monitor:'Монитор',printer:'Локальный принтер',other:'Другое'};
const sealNames={unknown:'Не установлено',sealed:'Опечатан',opened:'Корпус вскрыт',unsealed_after_repair:'Не опечатан после ремонта',seal_damaged:'Повреждена пломба',not_applicable:'Не требуется'};
const kindOptions=(entries,selected)=>Object.entries(entries).map(([k,v])=>`<option value="${esc(k)}" ${k===selected?'selected':''}>${esc(v)}</option>`).join('');
const val=x=>esc(x??'');
const dt=x=>x?new Date(x).toLocaleString('ru-RU'):'—';
const docInfo=(d,page)=>d?`<a href="/api/documents/${Number(d)}/file${page?`#page=${Number(page)}`:''}" target="_blank" rel="noopener noreferrer">Документ #${Number(d)}${page?` · стр. ${Number(page)}`:''}</a>`:'—';
const documentSelect=(docs)=>`<select name="document_id"><option value="">Без документа</option>${docs.map(d=>`<option value="${d.id}">#${d.id} ${esc(d.title)}</option>`).join('')}</select>`;
const field=(name,label,extra='')=>`<div class="field"><label>${label}</label><input name="${name}" ${extra}></div>`;
const area=(name,label,required=true)=>`<div class="field full"><label>${label}</label><textarea name="${name}" ${required?'required':''}></textarea></div>`;
const formData=(form)=>Object.fromEntries(new FormData(form).entries());
const givenId=(value)=>value?Number(value):null;
const whenISO=(value)=>value?new Date(value).toISOString():null;
const period=(d)=>{const t=new Date(d);return `${t.getFullYear()}-Q${Math.floor(t.getMonth()/3)+1}`;};
async function mutation(path, data, method='POST', current){
  try {await api(path,{method,json:data});await route(current.view,current.arg);notify('Сохранено');}
  catch(e){notify(e.message,true);}
}
function connectForms(container, maps, current){
  for(const [name, spec] of Object.entries(maps)){
    const form=container.querySelector(`[data-form="${name}"]`);
    if(!form)continue;
    form.onsubmit=async e=>{
      e.preventDefault();const raw=formData(form);let data;
      try{data=spec.transform?spec.transform(raw):raw;await mutation(spec.path,data,'POST',current);}catch(err){notify(err.message,true);}
    };
  }
}
function table(headers,items){return `<div class="tablewrap"><table><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${items.join('')||`<tr><td colspan="${headers.length}" class="muted">Пока нет записей</td></tr>`}</tbody></table></div>`;}
function docField(docs){return `<div class="field"><label>Документ / акт / протокол</label>${documentSelect(docs)}</div>`;}
function cap(title,content){return `<details class="card" open><summary class="click"><strong>${title}</strong></summary><div style="padding-top:12px">${content}</div></details>`;}
function componentView(id,cs,docs){
  const rows=cs.map(c=>`<tr><td>${val(componentNames[c.kind]||c.kind)}</td><td>${val(c.manufacturer)} ${val(c.model)}</td><td>${val(c.serial_number)}</td><td>${val(c.inventory_number)}</td><td>${c.removed_at?`Выведено ${dt(c.removed_at)}`:'В составе'}</td><td>${docInfo(c.document_id)}</td><td>${allowed()&&!c.removed_at?`<button class="small" data-retire-comp="${c.id}">Вывести из состава</button>`:''}</td></tr>`);
  return cap('Комплектующие: системный блок, диски, монитор, периферия', table(['Компонент','Модель','Заводской №','Инвентарный №','Состояние','Документ',''],rows)+
  (allowed()?`<form data-form="component" class="formgrid"><div class="field"><label>Компонент</label><select name="kind">${kindOptions(componentNames)}</select></div>${field('manufacturer','Производитель')}${field('model','Модель')}${field('serial_number','Заводской/серийный номер','required maxlength="150"')}${field('inventory_number','Инвентарный №')} ${docField(docs)}<div class="full"><button class="primary" type="submit">Добавить комплектующее</button></div></form>`:''));
}
function peripheralView(oi,asset,available,access){
  const rows=access.map(x=>`<tr><td>${val(x.peripheral.name)}<div class="muted">${val(x.peripheral.manufacturer)} ${val(x.peripheral.model)}</div></td><td>${val(x.peripheral.serial_number)} / ${val(x.peripheral.inventory_number)}<div class="muted">МНИ: ${x.peripheral.media_present?'есть':'нет'} ${val(x.peripheral.media_serial_number)}</div></td><td>${val(x.peripheral.ip_address)}<div class="muted">${val(x.connection_type)} · ${val(x.driver_name)} ${val(x.driver_version)}</div><small>${val(x.driver_smb_path)}</small></td><td>${x.revoked_at?'Доступ отозван':'Разрешено'}</td><td>${allowed()?`<button class="small" data-edit-mfp="${x.peripheral.id}" data-oi-id="${oi}">Исправить карточку</button> `:''}${allowed()&&!x.revoked_at?`<button class="small" data-revoke-periph="${x.id}">Отозвать</button>`:''}</td></tr>`);
  return cap('МФУ и общие сетевые устройства ОИ',table(['Устройство','Заводской №','IP','Разрешение',''],rows)+
  (allowed()?`<h3>Разрешить СВТ использовать устройство ОИ</h3><form data-form="peripheral-grant" class="formgrid"><div><label>МФУ / принтер</label><select name="peripheral_id" required><option value="">Выбрать</option>${available.map(d=>`<option value="${d.id}">${val(d.name)} · ${val(d.serial_number)}</option>`).join('')}</select></div>${field('reason','Основание разрешения','required minlength="5"')}<div><label>Способ подключения</label><select name="connection_type"><option value="lan">LAN / IP</option><option value="usb">USB</option><option value="print_server">Сервер печати</option><option value="other">Иное</option></select></div>${field('driver_name','Наименование драйвера')}${field('driver_version','Версия драйвера')}${field('driver_smb_path','SMB-путь к пакету драйвера','placeholder="smb://server/share/driver.pkg"')}${field('driver_sha256','SHA-256 драйвера (если известен)')}<div class="full"><button type="submit">Разрешить</button></div></form><h3>Зарегистрировать новое МФУ в составе ОИ</h3><form data-form="peripheral" class="formgrid">${field('name','Имя МФУ','required')}${field('serial_number','Заводской №','required')} ${field('ip_address','IP МФУ')}${field('manufacturer','Производитель')}${field('model','Модель')}${field('inventory_number','Учётный номер МФУ')}<div><label><input name="media_present" type="checkbox" style="width:auto"> Есть внутренний МНИ</label></div>${field('media_kind','Тип МНИ')}${field('media_serial_number','Заводской номер МНИ')}${field('media_inventory_number','Учётный номер МНИ')}<div class="full"><button type="submit">Зарегистрировать МФУ</button></div></form>`:''));
}
function securityView(id,tools,docs){
 const rows=tools.map(t=>`<tr><td>${val(t.name)}</td><td>${val(t.version)}</td><td>${val(t.license_ref)}</td><td>${val(t.expires_on)}</td><td>${t.removed_at?'Выведено':'Установлено'}</td><td>${docInfo(t.document_id)}</td><td>${allowed()&&!t.removed_at?`<button class="small" data-retire-tool="${t.id}">Снять</button>`:''}</td></tr>`);
 return cap('Средства защиты информации',table(['Наименование','Версия','Лицензия','Срок','Статус','Документ',''],rows)+
 (allowed()?`<form data-form="tool" class="formgrid">${field('name','Наименование СЗИ','required')}${field('version','Версия')}${field('license_ref','Номер лицензии/основание')}${field('expires_on','Дата окончания','type="date"')} ${docField(docs)}<div class="full"><button class="primary" type="submit">Добавить СЗИ</button></div></form>`:''));
}
function serviceView(id,requests,works,docs){
  const rr=requests.map(r=>`<tr><td>#${r.id}</td><td>${dt(r.reported_at)}</td><td>${val(r.reporter)}</td><td>${val(r.subject)}<div class="muted">${val(r.fault_description)}</div></td><td>${val(r.status)}</td><td>${docInfo(r.document_id)}</td><td>${allowed()&&r.status==='open'?`<button class="small" data-close-request="${r.id}">Закрыть</button>`:''}</td></tr>`);
  const ww=works.map(w=>`<tr><td>${dt(w.performed_at)}</td><td>${val(w.performer)}</td><td>${val(w.work_type)}</td><td>${val(w.actions)}<div class="muted">${val(w.result)}</div></td><td>${val(sealNames[w.seal_state_after])}<div class="muted">${val(w.seal_note)}</div></td><td>${docInfo(w.document_id,w.document_page)}</td></tr>`);
  return cap('Журнал обращений и неисправностей',table(['№','Дата','Заявитель','Вопрос / неисправность','Статус','Документ',''],rr)+
  (allowed()?`<form data-form="request" class="formgrid">${field('reporter','Кто обратился','required')}${field('subject','Тема обращения','required minlength="5"')}${area('fault_description','Описание неисправности / обращения')}${field('openproject_work_package_id','ID задачи OpenProject (если есть)','type="number" min="1"')}${docField(docs)}<div class="full"><button class="primary" type="submit">Зарегистрировать обращение</button></div></form>`:''))+
  cap('Журнал выполненных работ и опечатывания',table(['Когда','Исполнитель','Вид работы','Действия / результат','Корпус после работ','Документ'],ww)+
  (allowed()?`<form data-form="work" class="formgrid"><div class="field"><label>Связанное обращение</label><select name="service_request_id"><option value="">Не связано</option>${requests.filter(r=>r.status==='open').map(r=>`<option value="${r.id}">#${r.id} ${val(r.subject)}</option>`).join('')}</select></div>${field('performer','Кто выполнял работы','required')}${field('performed_at','Дата и время работ','type="datetime-local"')}<div class="field"><label>Вид работы</label><select name="work_type">${kindOptions({diagnostics:'Диагностика',repair:'Ремонт',replacement:'Замена оборудования',configuration:'Настройка',preventive:'Профилактика',other:'Другое'})}</select></div>${area('actions','Какие работы проведены')}${area('result','Результат работ')}<div class="field"><label>Состояние корпуса после работы (обязательно)</label><select name="seal_state_after">${kindOptions(sealNames,'unknown')}</select></div>${field('seal_note','Причина вскрытия / отметка об отсутствии пломбы')} ${docField(docs)}${field('document_page','Страница документа','type="number" min="1"')}<div class="full"><button class="primary" type="submit">Добавить запись в журнал работ</button></div></form>`:''));
}
function inspectionView(id,checks,quarter,docs){
 const labels={unauthorized_content:'Запрещённая информация (только факт и категория)',installed_software:'Разрешённое ПО',removable_media:'Съёмные носители',access_controls:'Настройки доступа',antivirus:'Антивирус / СЗИ',seals:'Пломбы и физический доступ'};
 const selectCheck=key=>`<div><label>${labels[key]}</label><select name="check_${key}">${kindOptions({not_checked:'Не проверялось',ok:'Без нарушений',violation:'Обнаружено нарушение',not_applicable:'Неприменимо'},'not_checked')}</select></div>`;
 const rows=checks.map(c=>`<tr><td>${dt(c.inspected_at)}<div class="muted">${val(c.quarter)}</div></td><td>${val(c.inspector)}</td><td>${val(c.status)}</td><td>${val(c.violation_categories.join(', '))}<div class="muted">${val(c.finding_summary)}</div></td><td>${val(c.corrective_action)}</td><td>${docInfo(c.document_id,c.document_page)}</td></tr>`);
 return cap(`Квартальные проверки ИБ · ${quarter.year} Q${quarter.quarter}`,`<div class="hint">${quarter.results[0]?.inspected?'В этом квартале есть запись проверки':'В текущем квартале проверка ещё не зарегистрирована'}. Фиксируем тип нарушения и ссылку на акт; содержимое запрещённых файлов в журнал не копируем.</div>`+table(['Дата','Проверяющий','Итог','Нарушения','Меры','Документ'],rows)+
 (allowed()?`<form data-form="inspection" class="formgrid">${field('inspector','ФИО проверяющего','required')}${field('subject_user','Пользователь СВТ / учётная запись (при необходимости)')}${field('inspected_at','Дата проверки','type="datetime-local"')}${Object.keys(labels).map(selectCheck).join('')}<div><label>Результат</label><select name="status">${kindOptions({passed:'Без нарушений',violations:'Есть нарушения',review_required:'Требуется анализ'},'review_required')}</select></div>${field('violation_categories','Категории нарушений (через запятую)','placeholder="unauthorized_files, physical_security"')}${area('finding_summary','Что установлено (без записи запрещённого содержимого)')}${area('corrective_action','Что необходимо исправить',false)}${docField(docs)}${field('document_page','Страница акта','type="number" min="1"')}<div class="full"><button class="primary" type="submit">Сохранить акт проверки</button></div></form>`:''));
}
async function viewLifecycle(arg){
 const id=Number(arg?.id);if(!id)return route('assets');
 const asset=await api(`/assets/${id}`);
 const [components,security,requests,works,inspections,available,access,docs,quarter]=await Promise.all([
  api(`/assets/${id}/components`),api(`/assets/${id}/security-tools`),api(`/assets/${id}/requests`),
  api(`/assets/${id}/works`),api(`/assets/${id}/inspections`),api(`/objects/${asset.oi_id}/peripherals`),
  api(`/assets/${id}/peripherals`),api('/documents'),api(`/inspections/quarterly-status?oi_id=${asset.oi_id}`)]);
 const thisQuarter={...quarter,results:quarter.results.filter(x=>x.asset_id===id)};
 shell(`<div class="section-head"><div><button id="go-back" class="small">← Паспорт СВТ</button><h1>${esc(asset.code)} · Электронный формуляр</h1><p class="subtitle">${esc(asset.hostname)} · ${esc(asset.domain_name)} · ${esc(asset.ip_address)} · ${esc(asset.os_name)} ${esc(asset.os_version)}</p></div><div><span class="pill">Корпус: ${val(sealNames[asset.seal_state])}</span></div></div>
 ${componentView(id,components,docs)}${peripheralView(asset.oi_id,id,available,access)}${securityView(id,security,docs)}${serviceView(id,requests,works,docs)}${inspectionView(id,inspections,thisQuarter,docs)}`);
 document.querySelector('#go-back').onclick=()=>route('detail',{type:'asset',id});
 const current={view:'lifecycle',arg};
 const maps={
   component:{path:`/assets/${id}/components`,transform:r=>({...r,document_id:givenId(r.document_id)})},
   peripheral:{path:`/objects/${asset.oi_id}/peripherals`,transform:r=>({kind:'mfp',...r,media_present:!!r.media_present})},
   'peripheral-grant':{path:`/assets/${id}/peripherals`,transform:r=>({...r,peripheral_id:Number(r.peripheral_id)})},
   tool:{path:`/assets/${id}/security-tools`,transform:r=>({...r,document_id:givenId(r.document_id)})},
   request:{path:`/assets/${id}/requests`,transform:r=>({...r,openproject_work_package_id:givenId(r.openproject_work_package_id),document_id:givenId(r.document_id)})},
   work:{path:`/assets/${id}/works`,transform:r=>({...r,service_request_id:givenId(r.service_request_id),document_id:givenId(r.document_id),performed_at:whenISO(r.performed_at),document_page:givenId(r.document_page)})},
   inspection:{path:`/assets/${id}/inspections`,transform:r=>{
     const checklist={};for(const k of ['unauthorized_content','installed_software','removable_media','access_controls','antivirus','seals']){checklist[k]=r['check_'+k];delete r['check_'+k];}
     return {...r,checklist,violation_categories:r.violation_categories.split(',').map(x=>x.trim()).filter(Boolean),
             inspected_at:whenISO(r.inspected_at),document_id:givenId(r.document_id),document_page:givenId(r.document_page)};
   }}
 };
 connectForms(document,maps,current);
 const retire=(selector,url,txt)=>document.querySelectorAll(`[${selector}]`).forEach(b=>b.onclick=async()=>{
   const reason=prompt(txt);if(!reason||reason.trim().length<10)return;
   await mutation(url(b),{reason},'POST',current);
 });
 retire('data-retire-comp',b=>`/assets/${id}/components/${b.dataset.retireComp}/remove`,'Основание снятия комплектующего (не менее 10 символов)');
 retire('data-retire-tool',b=>`/assets/${id}/security-tools/${b.dataset.retireTool}/remove`,'Причина удаления СЗИ (не менее 10 символов)');
 document.querySelectorAll('[data-edit-mfp]').forEach(button=>button.onclick=async()=>{
   const mfp=available.find(x=>x.id===Number(button.dataset.editMfp));if(!mfp)return;
   const update={};
   for(const [key,label] of [['manufacturer','Производитель'],['model','Модель'],['serial_number','Заводской номер МФУ'],['inventory_number','Учётный номер МФУ'],['media_kind','Тип МНИ'],['media_serial_number','Заводской номер МНИ'],['media_inventory_number','Учётный номер МНИ']]){
     const next=prompt(label,mfp[key]||'');if(next===null)return;update[key]=next.trim();
   }
   try{await api(`/objects/${asset.oi_id}/peripherals/${mfp.id}`,{method:'PATCH',json:update});await route('lifecycle',arg);notify('Сведения МФУ обновлены с записью в журнале');}catch(error){notify(error.message,true);}
 });
 retire('data-revoke-periph' ,b=>`/assets/${id}/peripherals/${b.dataset.revokePeriph}/revoke`,'Причина отзыва разрешения (не менее 10 символов)');
 document.querySelectorAll('[data-close-request]').forEach(b=>b.onclick=async()=>{
   const resolution=prompt('Результат устранения неисправности (нужна запись в журнале работ и состояние пломбы)');
   if(!resolution||resolution.trim().length<10)return;
   await mutation(`/assets/${id}/requests/${b.dataset.closeRequest}/close`,{resolution},'POST',current);
 });
}

async function viewBaselines(arg){
 const id=Number(arg?.id);if(!id)return route('objects');
 const [oi,baselines,changes,docs]=await Promise.all([api(`/objects/${id}`),api(`/objects/${id}/baselines`),api(`/objects/${id}/changes`),api('/documents')]);
 let compare=null;
 if(baselines.length){try{compare=await api(`/objects/${id}/configuration/compare?baseline_id=${baselines[0].id}`);}catch(e){compare={error:e.message};}}
 const bRows=baselines.map(b=>`<tr><td>${val(b.version)}</td><td>${val(b.status)}</td><td>${dt(b.created_at)}</td><td>${docInfo(b.document_id)}</td><td>${val(b.snapshot_sha256.slice(0,16))}…</td><td>${isAdmin()&&b.status==='draft'?`<button class="small" data-approve="${b.id}">Подтвердить</button>`:''}</td></tr>`);
 const cRows=changes.map(c=>`<tr><td>#${c.id}</td><td>${val(c.change_type)}</td><td>${val(c.summary)}</td><td>${val(c.status)}</td><td>${val(c.openproject_work_package_id)}</td><td>${allowed()&&!['implemented','rejected','cancelled'].includes(c.status)?`<button class="small" data-progress="${c.id}" data-status="${c.status}">Решение</button>`:''}</td></tr>`);
 shell(`<div class="section-head"><div><button id="go-back" class="small">← Карточка ОИ</button><h1>${val(oi.code)} — Комплект и изменения</h1><p class="subtitle">Утверждённые версии не перезаписываются; новая версия создаётся отдельно.</p></div></div>
 ${cap('Снимки состава',table(['Версия','Статус','Когда','Документ','SHA-256',''],bRows)+(allowed()?`<form data-form="baseline" class="formgrid">${field('version','Версия комплекта, например 1.0','required')}${area('notes','Основание формирования комплекта')}${docField(docs)}<div class="full"><button type="submit" class="primary">Зафиксировать состав (черновик)</button></div></form>`:''))}
 ${cap('Сравнение с последним снимком',compare?(compare.error?`<p class="banner">${val(compare.error)}</p>`:`<p>${compare.matches?'Состав соответствует снимку':'Есть расхождения с сохранённым снимком'}</p><pre class="details">${val(JSON.stringify(compare.changes,null,2))}</pre>`):'<p class="muted">Снимок пока не создан</p>')}
 ${cap('Заявки на изменения конфигурации',table(['№','Тип','Причина','Статус','Задача OpenProject',''],cRows)+(allowed()?`<form data-form="change" class="formgrid"><div><label>Вид изменения</label><select name="change_type">${kindOptions({repair:'Ремонт',replacement:'Замена',software:'ПО',network:'Сеть',addition:'Добавление',removal:'Исключение',other:'Другое'})}</select></div>${field('summary','Кратко о мероприятии','required')}${area('justification','Основание и оценка необходимости')}${field('asset_id','ID СВТ (если требуется)','type="number" min="1"')}${field('openproject_work_package_id','ID задачи OpenProject (вручную)','type="number" min="1"')}${docField(docs)}<div class="full"><button class="primary" type="submit">Создать заявку</button></div></form>`:''))}`);
 document.querySelector('#go-back').onclick=()=>route('detail',{type:'oi',id});
 const current={view:'baselines',arg};
 connectForms(document,{
   baseline:{path:`/objects/${id}/baselines`,transform:r=>({...r,document_id:givenId(r.document_id)})},
   change:{path:`/objects/${id}/changes`,transform:r=>({...r,asset_id:givenId(r.asset_id),document_id:givenId(r.document_id),openproject_work_package_id:givenId(r.openproject_work_package_id)})},
 },current);
 document.querySelectorAll('[data-approve]').forEach(b=>b.onclick=async()=>{
   const document_id=Number(prompt('ID подтверждающего документа (обязательно):')||0);
   const approval_note=prompt('Обоснование утверждения (минимум 10 символов):');
   if(!document_id||!approval_note||approval_note.trim().length<10)return;
   await mutation(`/objects/${id}/baselines/${b.dataset.approve}/approve`,{confirmation:true,document_id,approval_note},'POST',current);
 });
 document.querySelectorAll('[data-progress]').forEach(b=>b.onclick=async()=>{
   const choices={proposed:['under_review','cancelled'],under_review:['approved','rejected','cancelled'],approved:['implemented','cancelled']};
   const status=prompt(`Доступные переходы: ${choices[b.dataset.status].join(', ')}`,choices[b.dataset.status][0]);
   if(!choices[b.dataset.status].includes(status))return;
   const resolution=prompt('Обоснование решения (минимум 10 символов):');if(!resolution||resolution.trim().length<10)return;
   try{await api(`/objects/${id}/changes/${b.dataset.progress}`,{method:'PATCH',json:{status,resolution}});await route(current.view,current.arg);notify('Решение сохранено');}catch(e){notify(e.message,true);}
 });
}
