'use strict';
// v0.5: plan locally, publish separately, verify evidence before completing.
async function viewAutomation(){
 const [integration,summary,preview,items,rules,objects]=await Promise.all([
  api('/automation/integration').catch(()=>({enabled:false,configured:false})),
  api('/automation/summary'),api('/automation/preview'),
  api('/automation/activities?limit=200&status=pending'),api('/automation/rules'),api('/objects')]);
 const canManage=allowed(),canPublish=isAdmin()&&integration.enabled&&integration.configured;
 const ruleNames=Object.fromEntries(rules.map(r=>[r.id,r.title]));
 const oiNames=Object.fromEntries(objects.map(o=>[o.id,o.code]));
 shell(`<h1>Мероприятия ИБ · OI Registry v0.5</h1>
  <p class="subtitle">Планирование по ОИ и СВТ, контроль сроков, доказательства исполнения и сверка задач OpenProject.</p>
  <div class="grid">${[['Все мероприятия',summary.total],['Требуют выполнения',summary.pending],['Просрочено',summary.overdue],['На 30 дней',summary.due_30_days],['Завершено с документом',summary.completed],['Новых при планировании',preview.new_count]].map(([label,value])=>`<div class="card"><div class="stat">${esc(value)}</div>${esc(label)}</div>`).join('')}</div>
  <div class="card"><div class="section-head"><h2>Реестр регламентов</h2><span class="pill">${rules.filter(x=>x.active).length} активных правил</span></div>
   <p class="muted">Периодичность задаёт администратор по утверждённому локальному регламенту; система не придумывает нормативные сроки.</p>
   ${isAdmin()?`<form id="rule-form"><div class="formgrid">
     <div><label>Наименование мероприятия</label><input name="title" required minlength="3" maxlength="250" placeholder="Проверка актуальности учетных записей"></div>
     <div><label>Для каких объектов</label><select name="oi_id"><option value="">Все ОИ</option>${objects.map(o=>`<option value="${o.id}">${esc(o.code)} — ${esc(o.name)}</option>`).join('')}</select></div>
     <div><label>Область применения</label><select name="scope"><option value="oi">Каждый ОИ</option><option value="asset">Каждая СВТ</option></select></div>
     <div><label>Периодичность</label><select name="interval_months"><option value="1">Ежемесячно</option><option value="3">Ежеквартально</option><option value="6">Раз в полгода</option><option value="12">Ежегодно</option></select></div>
     <div><label>Первый контрольный срок</label><input name="first_due" type="date" required></div>
     <div><label>Ответственный (имя / должность)</label><input name="assignee" maxlength="180" placeholder="Инженер ИБ"></div>
    </div><p><button class="primary" type="submit">Создать правило</button></p></form>`:''}
   <div class="tablewrap"><table><thead><tr><th>Регламент</th><th>Область</th><th>ОИ</th><th>Первый срок</th><th>Период</th><th>Ответственный</th><th>Статус</th><th>Действие</th></tr></thead><tbody>
    ${rules.map(r=>`<tr><td>${esc(r.title)}</td><td>${r.scope==='oi'?'ОИ':'СВТ'}</td><td>${esc(r.oi_id?oiNames[r.oi_id]||r.oi_id:'Все')}</td><td>${esc(r.first_due)}</td><td>${r.interval_months} мес.</td><td>${esc(r.assignee||'Не назначен')}</td><td>${r.active?'Активно':'Выключено'}</td><td>${isAdmin()?`<button class="small" data-rule="${r.id}" data-action="${r.active?'disable':'enable'}">${r.active?'Отключить':'Включить'}</button>`:''}</td></tr>`).join('')||'<tr><td colspan="8">Правил нет. Создайте первое по утверждённому регламенту.</td></tr>'}
   </tbody></table></div></div>
  <div class="card"><h2>Планирование</h2><p>Следующее планирование добавит ${preview.new_count} записей. Задачи OpenProject автоматически не создаются.</p>
   ${canManage?'<button class="primary" id="run-plan">Обновить локальный план</button>':''}
   <p class="muted">Ознакомление и удалённый статус задачи не являются доказательством выполнения. Завершение требует загруженного документа.</p></div>
  <div class="card"><div class="section-head"><h2>Контроль исполнения</h2><span class="pill">OpenProject: ${canPublish?'подключён':'ручная синхронизация отключена'}</span></div>
   <div class="toolbar"><div class="field"><label>ОИ</label><select id="activity-oi"><option value="">Все</option>${objects.map(o=>`<option value="${o.id}">${esc(o.code)}</option>`).join('')}</select></div>
   <div class="field"><label>Статус</label><select id="activity-state"><option value="pending">Ожидают исполнения</option><option value="">Все</option><option value="completed">Завершены</option><option value="satisfied">Проверка зарегистрирована</option><option value="superseded">Отменены / устарели</option></select></div>
   <div class="field"><label>Тип</label><select id="activity-type"><option value="">Все</option><option value="attestation">Аттестация</option><option value="quarterly_inspection">Квартальная проверка</option><option value="custom_control">По регламенту</option></select></div></div>
   <div class="row between"><button class="small" id="activity-prev">← Назад</button><span class="pill" id="activity-page">Страница 1</span><button class="small" id="activity-next">Вперёд →</button></div>
   <div class="tablewrap"><table><thead><tr><th>Срок</th><th>ОИ</th><th>Мероприятие</th><th>Ответственный</th><th>Статус</th><th>OpenProject</th><th>Действия</th></tr></thead><tbody id="activity-rows"></tbody></table></div>
   <p class="muted">По 200 записей на страницу. Фильтрация выполняется на сервере, включая реестры с более чем 1200 мероприятий.</p></div>`);
 let offset=0,currentItems=items;
 const loadPage=async()=>{
  const q=new URLSearchParams({limit:'200',offset:String(offset)});
  for(const [field,id] of [['oi_id','#activity-oi'],['status','#activity-state'],['event_type','#activity-type']]){
   const value=document.querySelector(id).value;if(value)q.set(field,value);
  }
  currentItems=await api('/automation/activities?'+q.toString());
  render();
 };

 const render=()=>{
  const oi=document.querySelector('#activity-oi').value;
  const status=document.querySelector('#activity-state').value;
  const type=document.querySelector('#activity-type').value;
  const selected=currentItems;
  document.querySelector('#activity-page').textContent=`Записи ${offset+1}–${offset+selected.length}`;
  document.querySelector('#activity-prev').disabled=offset===0;
  document.querySelector('#activity-next').disabled=selected.length<200;
  document.querySelector('#activity-rows').innerHTML=selected.map(x=>`<tr>
    <td>${esc(x.deadline)}</td><td>${esc(oiNames[x.oi_id]||x.oi_id)}</td>
    <td>${esc(x.subject)}${x.rule_id?`<div class="muted">Правило #${x.rule_id}: ${esc(ruleNames[x.rule_id]||'')}</div>`:''}</td>
    <td>${esc(x.assignee||'Не назначен')}</td><td>${esc(x.status)} ${x.evidence_document_id?`<a href="/api/documents/${x.evidence_document_id}/file" target="_blank" rel="noopener noreferrer">Документ #${x.evidence_document_id}</a>`:''}</td>
    <td>${x.openproject_work_package_id?'#'+x.openproject_work_package_id+' · '+esc(x.remote_status||'статус не проверен'):esc(x.sync_status)}</td>
    <td><div class="item-actions">${canManage&&['open','acknowledged'].includes(x.status)?`<button class="small" data-complete="${x.id}">Завершить</button>`:''}
    ${canManage&&x.status==='open'?`<button class="small" data-ack="${x.id}">Ознакомлен</button>`:''}
    ${canPublish&&x.status==='open'&&x.sync_status==='not_sent'&&x.openproject_project_id?`<button class="small" data-publish="${x.id}">Создать задачу</button>`:''}
    ${isAdmin()&&x.sync_status==='published'&&x.openproject_work_package_id?`<button class="small" data-reconcile="${x.id}">Сверить статус</button>`:''}</div></td>
  </tr>`).join('')||'<tr><td colspan="7">Нет мероприятий с выбранными фильтрами</td></tr>';
  document.querySelectorAll('[data-complete]').forEach(b=>b.onclick=async()=>{
   const documentId=prompt('ID подтверждающего документа (сначала загрузите файл во вкладке «Документы»):');
   if(documentId===null)return;
   if(!/^\d+$/.test(documentId)||Number(documentId)<1){notify('Введите положительный ID документа',true);return;}
   const note=prompt('Что выполнено, кем и по какому основанию (минимум 10 символов):');
   if(note===null||note.trim().length<10)return;
   try{await api(`/automation/activities/${b.dataset.complete}/complete`,{method:'POST',json:{evidence_document_id:Number(documentId),note:note.trim()}});await viewAutomation();notify('Выполнение подтверждено документом');}catch(e){notify(e.message,true);}
  });
  document.querySelectorAll('[data-ack]').forEach(b=>b.onclick=async()=>{const note=prompt('Причина ознакомления (минимум 10 символов):');if(!note||note.trim().length<10)return;try{await api(`/automation/activities/${b.dataset.ack}/acknowledge`,{method:'POST',json:{note}});await viewAutomation();notify('Ознакомление зафиксировано');}catch(e){notify(e.message,true);}});
  document.querySelectorAll('[data-publish]').forEach(b=>b.onclick=async()=>{if(!confirm('Создать одну задачу в OpenProject? Не повторяйте запрос после сетевой ошибки без сверки.'))return;try{await api(`/automation/activities/${b.dataset.publish}/publish`,{method:'POST'});await viewAutomation();notify('Задача создана');}catch(e){notify(e.message,true);}});
  document.querySelectorAll('[data-reconcile]').forEach(b=>b.onclick=async()=>{try{const result=await api(`/automation/activities/${b.dataset.reconcile}/reconcile`,{method:'POST'});await viewAutomation();notify(`Статус OpenProject: ${result.remote.status}`);}catch(e){notify(e.message,true);}});
 };
 ['#activity-oi','#activity-state','#activity-type'].forEach(id=>document.querySelector(id).onchange=async()=>{offset=0;try{await loadPage();}catch(e){notify(e.message,true);}});
 document.querySelector('#activity-prev').onclick=async()=>{offset=Math.max(0,offset-200);try{await loadPage();}catch(e){notify(e.message,true);}};
 document.querySelector('#activity-next').onclick=async()=>{offset+=200;try{await loadPage();}catch(e){offset-=200;notify(e.message,true);}};
 document.querySelector('#run-plan')?.addEventListener('click',async()=>{if(!confirm(`Добавить ${preview.new_count} записей локально?`))return;try{await api('/automation/plan',{method:'POST'});await viewAutomation();notify('План актуализирован');}catch(e){notify(e.message,true);}});
 document.querySelector('#rule-form')?.addEventListener('submit',async e=>{e.preventDefault();const v=Object.fromEntries(new FormData(e.target).entries());v.oi_id=v.oi_id?Number(v.oi_id):null;v.interval_months=Number(v.interval_months);try{await api('/automation/rules',{method:'POST',json:v});await viewAutomation();notify('Правило создано');}catch(err){notify(err.message,true);}});
 document.querySelectorAll('[data-rule]').forEach(b=>b.onclick=async()=>{if(!confirm('Изменить состояние правила? Незавершённые записи могут быть помечены как устаревшие.'))return;try{await api(`/automation/rules/${b.dataset.rule}/${b.dataset.action}`,{method:'POST'});await viewAutomation();notify('Состояние правила изменено');}catch(e){notify(e.message,true);}});
 render();
}
