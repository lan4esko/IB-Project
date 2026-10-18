"use strict";
async function viewAutomation(){
 const [status,preview,items]=await Promise.all([api('/automation/integration').catch(()=>({enabled:false,configured:false})),api('/automation/preview'),api('/automation/activities?limit=500')]);
 const total=items.length;
 const open=items.filter(x=>x.status==='open');
 const due=items.filter(x=>x.deadline<new Date().toISOString().slice(0,10)&&x.status==='open');
 const canManage=allowed();
 const canPublish=isAdmin()&&status.enabled&&status.configured;
 shell(`<h1>Плановые мероприятия ИБ</h1><p class="subtitle">Аттестация ОИ и ежеквартальные проверки СВТ. Планирование локальное: отправка в OpenProject только после ручного подтверждения администратором.</p>
 <div class="grid">${[['Всего записей',total],['Открыто',open.length],['Просрочено',due.length],['Новых при следующем планировании',preview.new_count]].map(([a,b])=>`<div class="card"><div class="stat">${b}</div>${a}</div>`).join('')}</div>
 <div class="card"><h2>Управление</h2><p>OpenProject: ${status.enabled&&status.configured?'подключение включено — отправка только вручную':'синхронизация отключена'}. Квартальные задачи могут создаваться массово в локальном реестре, но автоматически не отправляются.</p>${canManage?'<button class="primary" id="run-plan">Обновить план мероприятий</button>':''}<p><small>Подтверждение мероприятия означает только ознакомление. Не доказывает выполнение проверки или аттестации.</small></p></div>
 <div class="card"><h2>Список мероприятий</h2><div class="row"><label>Тип <select id="auto-type"><option value="">Все</option><option value="attestation">Аттестация</option><option value="quarterly_inspection">Квартальная проверка</option></select></label><label>Состояние <select id="auto-status"><option value="">Все</option><option value="open">Открытые</option><option value="satisfied">Проверка зарегистрирована</option><option value="acknowledged">Ознакомлен</option></select></label></div><div class="tablewrap"><table><thead><tr><th>Контрольный срок</th><th>Тип</th><th>Мероприятие</th><th>Состояние</th><th>OpenProject</th><th>Операции</th></tr></thead><tbody id="auto-rows"></tbody></table></div></div>`);
 const render=()=>{
  const type=document.querySelector('#auto-type').value,st=document.querySelector('#auto-status').value;
  const filtered=items.filter(x=>(!type||x.event_type===type)&&(!st||x.status===st));
  document.querySelector('#auto-rows').innerHTML=filtered.map(x=>`<tr><td>${esc(x.deadline)}</td><td>${x.event_type==='attestation'?'Аттестация ОИ':'Квартальная проверка'}</td><td>${esc(x.subject)}</td><td>${esc(x.status)}</td><td>${x.openproject_work_package_id?'#'+x.openproject_work_package_id:esc(x.sync_status)}</td><td>${canManage&&x.status==='open'?`<button class="small" data-ack="${x.id}">Ознакомлен</button>`:''}${canPublish&&x.status==='open'&&x.sync_status==='not_sent'&&x.openproject_project_id?`<button class="small" data-publish="${x.id}">В OpenProject</button>`:''}</td></tr>`).join('')||'<tr><td colspan="6">Записей не найдено</td></tr>';
  document.querySelectorAll('[data-ack]').forEach(b=>b.onclick=async()=>{const note=prompt('Причина ознакомления (не менее 10 символов). Это не подтверждает выполнение работ:');if(!note||note.trim().length<10)return;try{await api('/automation/activities/'+b.dataset.ack+'/acknowledge',{method:'POST',json:{note}});await viewAutomation();notify('Ознакомление зафиксировано');}catch(e){notify(e.message,true);}});
  document.querySelectorAll('[data-publish]').forEach(b=>b.onclick=async()=>{if(!confirm('Создать ОДНУ задачу в OpenProject? Повторная отправка после сбоя выполняется только вручную после сверки.'))return;try{await api('/automation/activities/'+b.dataset.publish+'/publish',{method:'POST'});await viewAutomation();notify('Создана задача OpenProject');}catch(e){notify(e.message,true);}});
 };
 document.querySelector('#auto-type').onchange=render;document.querySelector('#auto-status').onchange=render;
 document.querySelector('#run-plan')?.addEventListener('click',async()=>{if(!confirm(`Добавить ${preview.new_count} контрольных записей локально? Отправки в OpenProject не будет.`))return;try{await api('/automation/plan',{method:'POST'});await viewAutomation();notify('План обновлён');}catch(e){notify(e.message,true);}});
 render();
}
