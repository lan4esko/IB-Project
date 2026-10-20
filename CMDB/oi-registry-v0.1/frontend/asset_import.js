'use strict';
// SVT inventory CSV: 3 distinct modes; explicit preview + second confirmation enforced server-side.
function mountAssetCsvImport(container){
  if(!isAdmin())return;
  const section=document.createElement('section');section.className='card';
  section.innerHTML=`<h2>Импорт СВТ (CSV)</h2><p class="subtitle">Для импорта нужен полный CSV из кнопки «Выгрузить полный CSV для импорта». Вариант выбирается заново при каждой операции.</p>
  <p><a href="/api/assets/export.csv">Выгрузить полный CSV для импорта</a></p>
  <form id="asset-preview-form" class="formgrid"><div><label>CSV (UTF-8 с BOM, разделитель ;)</label><input type="file" accept=".csv" required id="asset-csv-file"></div>
  <div><label>Режим</label><select id="asset-import-mode" required><option value="">Выберите для этой операции</option><option value="merge">1. Объединить без конфликтов</option><option value="copy">2. Создать независимые копии СВТ</option><option value="replace">3. Заменить совпадающие коды; остальных не удалять</option></select></div>
  <div class="full"><button class="primary">Предпросмотр всех трёх вариантов</button></div></form>
  <div id="asset-preview"></div>`;
  container.append(section);
  const form=section.querySelector('#asset-preview-form');
  form.onsubmit=async e=>{
    e.preventDefault();const mode=section.querySelector('#asset-import-mode').value;
    const file=section.querySelector('#asset-csv-file').files[0];if(!mode||!file)return;
    const data=new FormData();data.append('mode',mode);data.append('file',file);
    try{
      const result=await api('/assets/import/preview',{method:'POST',body:data});
      const desc={merge:'Объединить',copy:'Копировать',replace:'Заменить совпадающие коды'};
      section.querySelector('#asset-preview').innerHTML=`<h3>Предпросмотр CSV</h3><p>Выбран режим: <strong>${esc(desc[mode])}</strong>. Изменения ещё не внесены.</p><div class="tablewrap"><table><thead><tr><th>Режим</th><th>Всего</th><th>Новые</th><th>Обновить</th><th>Конфликты</th></tr></thead><tbody>${Object.entries(result.comparisons).map(([key, v])=>`<tr><td>${esc(desc[key])}</td><td>${v.total}</td><td>${v.add}</td><td>${v.update}</td><td>${esc(v.conflicts.join('; ')||'Нет')}</td></tr>`).join('')}</tbody></table></div><p>${esc(result.selected.warning)}</p><details class="card"><summary>Подробный план для выбранного режима (${result.selected.actions.length} записей)</summary><div class="tablewrap"><table><thead><tr><th>Код СВТ</th><th>Операция</th><th>Поля, которые изменятся</th></tr></thead><tbody>${result.selected.actions.map(item=>`<tr><td>${esc(item.code)}</td><td>${esc(item.operation)}</td><td>${esc(item.fields_changed.join(', '))}</td></tr>`).join('')}</tbody></table></div></details>
      ${result.selected.can_apply?`<p><label><input type="checkbox" id="asset-approved"> Я сверил изменения и подтверждаю выбранный режим</label></p><p>Для повторного подтверждения введите: <code>${esc(result.confirmation_phrase)}</code></p><input id="asset-confirm-phrase" autocomplete="off"><p><button id="asset-commit" class="primary">Выполнить транзакцию</button></p>`:'<p class="banner">Импорт заблокирован конфликтами</p>'}`;
      const btn=section.querySelector('#asset-commit');if(btn)btn.onclick=async()=>{
        if(!section.querySelector('#asset-approved').checked){notify('Подтвердите просмотр',true);return;}
        const confirmation_phrase=section.querySelector('#asset-confirm-phrase').value;
        if(confirmation_phrase!==result.confirmation_phrase){notify('Фраза подтверждения не совпадает',true);return;}
        const req=new FormData();req.append('mode',mode);req.append('file',file);req.append('plan_id',result.plan_id);req.append('confirmation_phrase',confirmation_phrase);
        btn.disabled=true;
        try{await api('/assets/import/commit',{method:'POST',body:req});await route('assets');notify('Импорт СВТ завершён');}catch(error){notify(error.message,true);btn.disabled=false;}
      };
    }catch(error){notify(error.message,true);section.querySelector('#asset-preview').replaceChildren();}
  };
}
