const $ = id => document.getElementById(id);
const state = {modules:[],preview:null,module:null,page:1,editing:null,auth:null,organizationId:null,importTarget:null,reviewDigest:null,visibleColumns:null,views:[],excludedRows:new Set(),view:"home",compact:true,expanded:false,saving:false,deleting:false};
let recordsRequest=0,moduleRequest=0;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function api(path, options={}) {
  const headers=new Headers(options.headers||{});
  if(state.auth?.csrfToken && options.method && options.method!=='GET')headers.set('X-CSRF-Token',state.auth.csrfToken);
  if(state.organizationId)headers.set('X-Organization-Id',state.organizationId);
  const response = await fetch(path, {...options,headers,credentials:'same-origin'});
  const data = await response.json();
  if (!response.ok) { const issue = new Error(data.error || 'No se pudo completar la operación.'); issue.data=data; throw issue; }
  return data;
}
function toast(message, isError=false) {
  const node=$('toast'); node.textContent=message; node.className=isError?'error':''; node.style.display='block';
  clearTimeout(toast.timer); toast.timer=setTimeout(()=>node.style.display='none',4600);
}
function updateNavigation(){
  $('homeButton').classList.toggle('active',state.view==='home');
  $('navImport').classList.toggle('active',state.view==='import');
  $('moduleNav').querySelectorAll('[data-id]').forEach(node=>{
    const active=state.view==='module'&&node.dataset.id===state.module?.id;
    node.classList.toggle('active',active);
    if(active)node.setAttribute('aria-current','page');else node.removeAttribute('aria-current');
  });
}
function showView(name){
  state.view=name;
  if(name!=='module'){recordsRequest++;moduleRequest++;setExpanded(false);}
  for(const id of ['homeView','importView','moduleView']) $(id).hidden=id!==name+'View';
  updateNavigation();
}

function currentOrg(){return state.auth?.organizations.find(o=>o.id===state.organizationId)}
function canWrite(){return ['owner','admin','editor'].includes(currentOrg()?.role)}
function renderAccount(){
  $('organizationSelect').innerHTML=state.auth.organizations.map(o=>`<option value="${esc(o.id)}" ${o.id===state.organizationId?'selected':''}>${esc(o.name)}</option>`).join('');
  $('sidebarOrg').textContent=currentOrg()?.name||'Organización';$('sidebarUser').textContent=state.auth.user.name;
  $('usersButton').hidden=currentOrg()?.role!=='owner';
  $('activityButton').hidden=!['owner','admin'].includes(currentOrg()?.role);
  $('startImport').hidden=!canWrite();$('navImport').hidden=!canWrite();$('newRecordButton').hidden=!canWrite();$('reimportButton').hidden=!canWrite();
  $('appShell').hidden=false;$('loginView').hidden=true;$('accessView').hidden=true;
}
async function boot(){
  const accessToken=new URLSearchParams(location.hash.slice(1)).get('access');
  if(accessToken){await showAccessToken(accessToken);return;}
  try{
    state.auth=await api('/api/me');
    state.organizationId=state.auth.organizations.find(o=>o.id===state.organizationId)?.id||state.auth.organizations[0]?.id||null;
    renderAccount();home();
  }catch(e){$('appShell').hidden=true;$('accessView').hidden=true;$('loginView').hidden=false;}
}
let activeAccessToken=null;
async function showAccessToken(token){
  $('appShell').hidden=true;$('loginView').hidden=true;$('accessView').hidden=false;$('accessError').textContent='';
  try{const info=await api('/api/access-token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});activeAccessToken=token;
    $('accessTitle').textContent=info.kind==='reset'?'Elegí una nueva contraseña':'Aceptar invitación';
    $('accessDescription').textContent=info.kind==='reset'?`Vas a cambiar la contraseña de ${info.email}. Este enlace sirve una sola vez.`:info.existing?`Ya tenés una cuenta con ${info.email}. Ingresá tu contraseña actual para sumar esta organización.`:`Vas a entrar con ${info.email}. Elegí una contraseña para tu cuenta.`;
    $('accessPasswordLabel').firstChild.textContent=info.existing&&info.kind==='invite'?'Contraseña actual':'Contraseña nueva (mínimo 12 caracteres)';
    $('accessPassword').autocomplete=info.existing&&info.kind==='invite'?'current-password':'new-password';
    $('accessSubmit').textContent=info.kind==='reset'?'Guardar contraseña':'Aceptar invitación';
  }catch(e){activeAccessToken=null;$('accessTitle').textContent='Este enlace no está disponible';$('accessDescription').textContent='Pedí un enlace nuevo a la persona que administra Tablio.';$('accessPasswordLabel').hidden=true;$('accessSubmit').hidden=true;}
}
$('accessForm').onsubmit=async event=>{event.preventDefault();if(!activeAccessToken)return;try{await api('/api/redeem-token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:activeAccessToken,password:$('accessPassword').value})});activeAccessToken=null;$('accessPassword').value='';history.replaceState({},'',location.pathname);$('accessView').hidden=true;await boot();toast('Listo. Ingresá con tu cuenta.')}catch(e){$('accessError').textContent=e.message}};
async function login(event){
  event.preventDefault();$('loginError').textContent='';
  try{await api('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('loginEmail').value,password:$('loginPassword').value})});$('loginPassword').value='';await boot();}
  catch(e){$('loginError').textContent=e.message;}
}
async function logout(){try{await api('/api/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});}catch(e){}recordsRequest++;moduleRequest++;setExpanded(false);state.auth=null;state.organizationId=null;await boot();}
async function refreshModules(){
  state.modules=await api('/api/modules');
  $('moduleNav').innerHTML=state.modules.map(m=>`<button data-id="${esc(m.id)}" title="${esc(m.name)}" type="button">▦ <span>${esc(m.name)}</span><span class="nav-count">${m.count}</span></button>`).join('');
  $('moduleCards').innerHTML=state.modules.length?state.modules.map(m=>`<button class="module-card" data-id="${esc(m.id)}" type="button"><span class="card-top"><span class="card-icon" aria-hidden="true">▦</span><span class="card-arrow" aria-hidden="true">↗</span></span><strong title="${esc(m.name)}">${esc(m.name)}</strong><small>${m.count.toLocaleString('es-AR')} registros · Abrir módulo</small></button>`).join(''):'<div class="empty">Tu próximo sistema empieza con una planilla.<br>Importá un archivo Excel para crear tu primer módulo.</div>';
  document.querySelectorAll('[data-id]').forEach(node=>node.addEventListener('click',()=>openModule(node.dataset.id)));
  $('moduleCount').textContent=state.modules.length.toLocaleString('es-AR');
  $('recordCount').textContent=state.modules.reduce((sum,m)=>sum+m.count,0).toLocaleString('es-AR');
  updateNavigation();
  renderHomeAttention();
}
async function renderHomeAttention(){
  const target=$('homeAttention');
  if(!target)return;
  if(!state.modules.length){target.innerHTML='<p class="empty">Importá una planilla para ver qué necesita atención.</p>';return;}
  try{
    const reports=await Promise.all(state.modules.map(async m=>({module:m,report:await api(`/api/modules/${m.id}/insights`)})));
    const cards=reports.flatMap(({module,report})=>report.groups.map(g=>`<button class="attention-card" type="button" data-attention-module="${esc(module.id)}"><strong>${g.count} · ${esc(g.title)}</strong><span>${esc(module.name)}</span><small>${esc(g.explanation)}</small></button>`));
    target.innerHTML=cards.length?cards.join(''):'<p class="empty">No hay avisos por ahora. Podés seguir trabajando con tus módulos.</p>';
    target.querySelectorAll('[data-attention-module]').forEach(b=>b.onclick=()=>openModule(b.dataset.attentionModule));
  }catch(e){target.innerHTML='<p class="empty">No se pudo cargar el resumen.</p>'}
}
async function renderModuleAttention(){
  const target=$('moduleAttention');if(!state.module)return;
  try{
    const report=await api(`/api/modules/${state.module.id}/insights`);
    state.moduleInsights=report;
    const groupHtml=report.groups.map(g=>`<div class="attention-card"><strong>${g.count} · ${esc(g.title)}</strong><p>${esc(g.explanation)}</p><small>Ejemplos: ${esc(g.examples.join(' · '))}</small></div>`).join('');
    const orders=report.orders.length?`<details><summary>Ver sugerencias de compra (${report.orderCount})</summary><div class="order-list">${report.orders.map(o=>`<div><strong>${esc(o.name)}: pedir ${esc(o.suggestedQuantity)}</strong><p>${esc(o.reason)}</p></div>`).join('')}</div><p>Son sugerencias para revisar; Tablio no envía pedidos automáticamente.</p></details>`:'';
    target.innerHTML=`<h2>Qué necesita atención</h2><p>${esc(report.guidance)}</p>${groupHtml||'<p>No hay avisos con los datos disponibles.</p>'}${orders}`;
  }catch(e){target.textContent='No se pudo cargar el resumen de este módulo.'}
}
function home(){showView('home');$('breadcrumbs').innerHTML=esc(currentOrg()?.name)+' <span>/</span> Inicio';refreshModules().catch(e=>toast(e.message,true));}
function startImport(target=null){if(!canWrite())return;state.importTarget=target;state.reviewDigest=null;state.preview=null;state.excludedRows.clear();$('uploadPanel').hidden=false;$('reviewPanel').hidden=true;$('fileInput').value='';const updating=!!target;$('importEyebrow').textContent=updating?'ACTUALIZAR DATOS':'NUEVO MÓDULO';$('importTitle').textContent=updating?'Actualizar desde Excel':'Importar una planilla';$('importDescription').textContent=updating?'Elegí el Excel actualizado. Antes de guardar, vas a ver qué registros se agregarán y cuáles cambiarán. Los que no figuren en el archivo quedarán como están.':'Subí un archivo Excel y revisá cómo Tablio interpreta sus columnas.';$('breadcrumbs').innerHTML=esc(currentOrg()?.name)+' <span>/</span> '+(updating?'Actualizar datos':'Nueva importación');showView('import');setStep(1);}
function setStep(n){document.querySelectorAll('.step').forEach((s,i)=>s.classList.toggle('on',i<n));}
async function upload(file){
  if(!file||!file.name.toLowerCase().endsWith('.xlsx')) return toast('Elegí un archivo XLSX.',true);
  if(file.size>5*1024*1024)return toast('El archivo supera 5 MiB.',true);
  try{
    toast('Analizando planilla…');
    state.preview=await api('/api/analyze',{method:'POST',headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},body:file});
    $('toast').style.display='none';renderReview();
  }catch(e){toast(e.message,true);}
}
function formulaIssueMarkup(issues){
  if(!issues.length)return '';
  const rows=[...new Set(issues.map(issue=>issue.row))];
  return `<section class="formula-issues" id="formulaIssueList"><h3>Fórmulas para corregir <span id="formulaIssueCount">(${issues.length})</span></h3><p>Corregí cada fórmula o excluí solo la fila afectada. Las demás filas y columnas se conservarán.</p><p id="excludedRowsSummary" role="status"></p>${rows.map(row=>`<div class="formula-column" data-issue-row="${row}"><div class="formula-column-head"><strong>Fila ${row}</strong><button class="button secondary" type="button" data-exclude-row="${row}">Excluir esta fila</button></div>${issues.filter(issue=>issue.row===row).map(issue=>`<label>Columna ${issue.column}: ${esc(issue.field)}<input class="formula-correction" data-key="${issue.row}:${issue.column}" value="${esc(issue.formula)}"><small>${esc(issue.message)}</small></label>`).join('')}</div>`).join('')}</section>`;
}
function bindFormulaRows(issues){
  const list=$('formulaIssueList');if(!list)return;
  function update(){
    const count=issues.filter(issue=>!state.excludedRows.has(issue.row)).length;
    $('formulaIssueCount').textContent=`(${count})`;
    $('excludedRowsSummary').innerHTML=state.excludedRows.size?`${state.excludedRows.size} ${state.excludedRows.size===1?'fila excluida':'filas excluidas'} del módulo. <button class="button secondary" type="button" id="undoExcludedRows">Volver a incluir</button>`:'';
    if($('undoExcludedRows'))$('undoExcludedRows').onclick=()=>{state.excludedRows.clear();list.querySelectorAll('[data-issue-row]').forEach(node=>node.hidden=false);update()};
  }
  list.querySelectorAll('[data-exclude-row]').forEach(button=>button.onclick=()=>{state.excludedRows.add(Number(button.dataset.excludeRow));button.closest('[data-issue-row]').hidden=true;update()});
  update();
}
function renderReview(){
  const p=state.preview;$('uploadPanel').hidden=true;$('reviewPanel').hidden=false;setStep(2);
  if(state.importTarget){renderReimportReview();return;}
  const fields=p.fields.map((f,i)=>`<tr data-index="${i}"><td><input type="checkbox" class="include" ${f.ignored?'':'checked'} aria-label="Incluir ${esc(f.label)}"></td><td><input type="text" class="label" value="${esc(f.label)}" aria-label="Etiqueta de ${esc(f.label)}"><br><small>Columna ${f.sourceColumn+1}${f.formulaCount?' · Calculada':''}</small></td><td><select class="type" aria-label="Tipo de ${esc(f.label)}" ${f.formulaCount?'disabled':''}>${['text','integer','decimal','currency','date','boolean','enum'].map(t=>`<option value="${t}" ${t===f.type?'selected':''}>${({text:'Texto',integer:'Entero',decimal:'Decimal',currency:'Importe',date:'Fecha',boolean:'Sí / No',enum:'Opciones'})[t]}</option>`).join('')}</select></td><td><input type="checkbox" class="required" ${f.required?'checked':''} aria-label="Obligatorio ${esc(f.label)}"></td><td><input type="number" min="0" max="6" class="scale" value="${f.scale??2}" aria-label="Decimales de ${esc(f.label)}"></td><td><input type="text" class="options" value="${esc(f.options.join(', '))}" placeholder="Separadas por coma" aria-label="Opciones de ${esc(f.label)}"></td><td><small>${f.emptyCount} vacíos<br>${esc(f.formula?'='+f.formula:f.examples.slice(0,2).join(' · '))}</small></td></tr>`).join('');
  const issues=p.formulaIssues||[];
  const issueList=formulaIssueMarkup(issues);
  $('reviewPanel').innerHTML=`<div class="panel"><div class="review-header"><div><h2>Revisá la estructura</h2><p>${p.rowCount} registros · ${p.fields.length} columnas detectadas</p></div><button class="button secondary" id="changeFile" type="button">Cambiar archivo</button></div><div class="review-content"><label for="sheetSelect">Hoja del libro</label><select class="name-input" id="sheetSelect">${p.sheets.map(s=>`<option ${s===p.sheet?'selected':''}>${esc(s)}</option>`).join('')}</select><label for="moduleName">Nombre del módulo</label><input class="name-input" id="moduleName" value="${esc(p.sheet)}" maxlength="80"><details class="review-help"><summary>¿Cómo elijo los tipos de columna?</summary><p><strong>Texto:</strong> nombres y códigos con ceros iniciales. <strong>Entero / Decimal:</strong> cantidades. <strong>Importe:</strong> valores en ARS. <strong>Opciones:</strong> lista separada por comas. Marcá <strong>Obligatorio</strong> para exigir un valor.</p></details><div class="table-scroll" role="region" aria-label="Configuración de columnas, desplazable" tabindex="0"><table class="field-table"><thead><tr><th>Usar</th><th>Columna</th><th>Tipo</th><th>Obligatorio</th><th>Decimales</th><th>Opciones</th><th>Muestra</th></tr></thead><tbody>${fields}</tbody></table></div>${issueList}<p class="upload-note">Revisá las opciones y los tipos. Los importes se interpretan en ARS. Podés comprobar todas las filas antes de guardar.</p><div id="importErrors" role="alert"></div><div id="dataCorrections"></div><div id="sampleRows"></div></div><div class="review-actions"><span class="hint">Ningún registro se guardará si hay errores.</span><div><button class="button secondary" id="validateImport" type="button">Comprobar datos</button> <button class="button primary" id="confirmImport" type="button">Guardar módulo →</button></div></div></div>`;
  const suggested=p.fields.some(f=>/habilitaci[oó]n|factibilidad/i.test(f.label))?'habilitaciones':'general';
  $('moduleName').insertAdjacentHTML('afterend',`<label for="templateSelect">¿Qué tipo de planilla es?</label><select class="name-input" id="templateSelect"><option value="general">Otra planilla</option><option value="habilitaciones" ${suggested==='habilitaciones'?'selected':''}>Habilitaciones</option><option value="minimercado">Minimercado</option><option value="corralon">Corralón de materiales</option></select>${(p.warnings||[]).length?`<div class="import-warnings"><strong>Revisá estos detalles del Excel</strong><ul>${p.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul></div>`:''}`);
  $('changeFile').onclick=()=>startImport();
  for(const issue of issues){
    if(p.fields[issue.column-1]?.formulaCount)continue;
    const input=Array.from($('formulaIssueList')?.querySelectorAll('.formula-correction')||[]).find(node=>node.dataset.key===`${issue.row}:${issue.column}`);
    if(input){input.value='';input.placeholder='Escribí el valor correcto, sin =';input.setAttribute('aria-label',`Valor fijo para la fila ${issue.row}, columna ${issue.column}`);}
  }
  bindFormulaRows(issues);
  $('sheetSelect').onchange=async()=>{try{state.preview=await api(`/api/preview?token=${encodeURIComponent(p.token)}&sheet=${encodeURIComponent($('sheetSelect').value)}`);state.excludedRows.clear();renderReview();}catch(e){toast(e.message,true)}};
  $('confirmImport').onclick=confirmImport;
  $('validateImport').onclick=validateImport;
  document.querySelectorAll('.field-table tbody tr').forEach(row=>{const update=()=>{const included=row.querySelector('.include').checked,kind=row.querySelector('.type').value;row.classList.toggle('excluded',!included);row.querySelector('.scale').disabled=!included||!['decimal','currency'].includes(kind);row.querySelector('.options').disabled=!included||kind!=='enum'};row.querySelector('.type').onchange=update;row.querySelector('.include').onchange=update;update()});
}
function collectSchema(){
  const fields=[];
  document.querySelectorAll('.field-table tbody tr').forEach(row=>{
    if(!row.querySelector('.include').checked)return;
    const source=state.preview.fields[Number(row.dataset.index)];const type=row.querySelector('.type').value;
    const field={id:source.id,label:row.querySelector('.label').value.trim(),sourceColumn:source.sourceColumn,type,required:row.querySelector('.required').checked};
    if(type==='decimal'||type==='currency')field.scale=Number(row.querySelector('.scale').value);
    if(type==='enum')field.options=row.querySelector('.options').value.split(',').map(v=>v.trim()).filter(Boolean);
    fields.push(field);
  });
  if(!fields.length)throw new Error('Elegí al menos una columna.');
  return {schemaVersion:1,name:$('moduleName').value.trim(),template:$('templateSelect').value,primaryFieldId:fields.find(f=>f.type==='text')?.id||fields[0].id,fields};
}
function collectCorrections(){
  const formulaCorrections={},dataCorrections={};
  document.querySelectorAll('.formula-correction').forEach(node=>{if(node.value.trim()&&!state.excludedRows.has(Number(node.dataset.key.split(':')[0])))formulaCorrections[node.dataset.key]=node.value.trim()});
  document.querySelectorAll('.data-correction').forEach(node=>{if(!state.excludedRows.has(Number(node.dataset.key.split(':')[0])))dataCorrections[node.dataset.key]=node.value});
  return {formulaCorrections,dataCorrections,excludedRows:[...state.excludedRows]};
}
function showValidation(result){
  const prior=collectCorrections(),previous=prior.dataCorrections;
  const errors=result.errors||[];
  $('importErrors').innerHTML=errors.length?`<div class="error-list" role="alert"><strong>Hay ${result.errorCount} ${result.errorCount===1?'celda para corregir':'celdas para corregir'}.</strong><p>Escribí el valor correcto debajo de cada mensaje y volvé a comprobar.</p></div>`:'<p class="success-note" role="status">Todas las filas están listas para guardar.</p>';
  const problemKeys=new Set(errors.filter(e=>e.code!=='INVALID_FORMULA').map(e=>`${e.row}:${e.column}`));
  const staticFormulaKeys=new Set((state.preview.formulaIssues||[]).map(e=>`${e.row}:${e.column}`));
  const formulaErrors=errors.filter(e=>e.code==='INVALID_FORMULA'&&e.formula&&!staticFormulaKeys.has(`${e.row}:${e.column}`));
  const formulaKeys=new Set(formulaErrors.map(e=>`${e.row}:${e.column}`));
  $('dataCorrections').innerHTML=errors.filter(e=>e.code!=='INVALID_FORMULA').map(e=>{const key=`${e.row}:${e.column}`;return `<label class="cell-fix">Fila ${e.row} · ${esc(e.field)}<small>${esc(e.message)}</small><input class="data-correction" data-key="${key}" value="${esc(previous[key]??'')}" aria-label="Valor correcto para fila ${e.row}, ${esc(e.field)}"></label>`}).join('')+Object.entries(previous).filter(([key])=>!problemKeys.has(key)).map(([key,value])=>`<input type="hidden" class="data-correction" data-key="${esc(key)}" value="${esc(value)}">`).join('')+formulaErrors.map(e=>{const key=`${e.row}:${e.column}`;return `<label class="cell-fix">Fórmula de la fila ${e.row} · ${esc(e.field)}<small>${esc(e.message)}</small><input class="formula-correction" data-key="${key}" value="${esc(prior.formulaCorrections[key]??e.formula)}" aria-label="Fórmula correcta para fila ${e.row}, ${esc(e.field)}"></label>`}).join('')+Object.entries(prior.formulaCorrections).filter(([key])=>!staticFormulaKeys.has(key)&&!formulaKeys.has(key)).map(([key,value])=>`<input type="hidden" class="formula-correction" data-key="${esc(key)}" value="${esc(value)}">`).join('');
  $('sampleRows').innerHTML=result.sample?.length?`<h3>Vista previa de las primeras ${result.sample.length} filas</h3><div class="table-scroll"><table class="records-table"><thead><tr><th>Fila de Excel</th>${state.preview.fields.filter(f=>document.querySelector(`.field-table tr[data-index="${state.preview.fields.indexOf(f)}"] .include`)?.checked).map(f=>`<th>${esc(f.label)}</th>`).join('')}</tr></thead><tbody>${result.sample.map(r=>`<tr><td>${r.row}</td>${state.preview.fields.filter(f=>document.querySelector(`.field-table tr[data-index="${state.preview.fields.indexOf(f)}"] .include`)?.checked).map(f=>`<td>${esc(r.values[f.id])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:'';
  if(errors.length)$('dataCorrections').querySelector('input')?.focus();
}
async function validateImport(){
  try{const body={token:state.preview.token,sheet:state.preview.sheet,schema:collectSchema(),...collectCorrections()};const result=await api('/api/import/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});showValidation(result);return result.errorCount===0;}catch(e){toast(e.message,true);return false;}
}
async function confirmImport(){
  try{
    if(!await validateImport())return;
    const schema=collectSchema();$('confirmImport').disabled=true;setStep(3);
    const result=await api('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:state.preview.token,sheet:state.preview.sheet,schema,...collectCorrections()})});
    toast(`${result.count??0} registros importados.`);await refreshModules();await openModule(result.moduleId);
  }catch(e){setStep(2);$('confirmImport').disabled=false;if(e.data?.errors)showValidation(e.data);else toast(e.message,true)}
}
function renderReimportReview(){
  const p=state.preview,schema=state.importTarget.schema;
  const keys=schema.fields.filter(f=>f.sourceColumn!==null&&f.sourceColumn!==undefined&&!f.formula);
  const issues=p.formulaIssues||[];
  const preferred=keys.find(f=>/^(cod\.?|c[oó]digo|sku|id|n[º°o]\.?)/i.test(f.label))?.id||schema.primaryFieldId;
  $('reviewPanel').innerHTML=`<div class="panel"><div class="review-header"><div><h2>Revisá el Excel actualizado</h2><p>${p.rowCount} filas encontradas</p></div><button class="button secondary" id="changeFile" type="button">Cambiar archivo</button></div><div class="review-content"><label for="sheetSelect">Hoja del libro</label><select class="name-input" id="sheetSelect">${p.sheets.map(s=>`<option ${s===p.sheet?'selected':''}>${esc(s)}</option>`).join('')}</select><label for="keyField">Columna principal para identificar cada fila</label><select class="name-input" id="keyField">${keys.map(f=>`<option value="${esc(f.id)}" ${f.id===preferred?'selected':''}>${esc(f.label)}</option>`).join('')}</select><label for="keyFieldExtra">Si se repite, distinguir también por</label><select class="name-input" id="keyFieldExtra"><option value="">No usar otra columna</option>${keys.map(f=>`<option value="${esc(f.id)}">${esc(f.label)}</option>`).join('')}</select><label for="keyFieldThird">Y, si hace falta, por una tercera columna</label><select class="name-input" id="keyFieldThird"><option value="">No usar tercera columna</option>${keys.map(f=>`<option value="${esc(f.id)}">${esc(f.label)}</option>`).join('')}</select><p class="upload-note">Si una columna tiene valores repetidos, agregá otra que distinga las filas. Revisá los cambios antes de guardar; las filas ausentes no se borrarán.</p>${formulaIssueMarkup(issues)}<div id="importErrors" role="alert"></div><div id="dataCorrections"></div><div id="changePreview"></div></div><div class="review-actions"><span class="hint">Primero revisá los cambios. Nada se guarda todavía.</span><div><button class="button secondary" id="previewChanges" type="button">Revisar cambios</button> <button class="button primary" id="confirmReimport" type="button" disabled>Guardar cambios →</button></div></div></div>`;
  bindFormulaRows(issues);
  $('changeFile').onclick=()=>startImport(state.importTarget);
  $('sheetSelect').onchange=async()=>{try{state.preview=await api(`/api/preview?token=${encodeURIComponent(p.token)}&sheet=${encodeURIComponent($('sheetSelect').value)}`);state.reviewDigest=null;state.excludedRows.clear();renderReview()}catch(e){toast(e.message,true)}};
  $('previewChanges').onclick=previewChanges;$('confirmReimport').onclick=confirmReimport;
  for(const id of ['keyField','keyFieldExtra','keyFieldThird'])$(id).onchange=()=>{if($('keyFieldExtra').value===$('keyField').value)$('keyFieldExtra').value='';if($('keyFieldThird').value=== $('keyField').value||$('keyFieldThird').value===$('keyFieldExtra').value)$('keyFieldThird').value='';state.reviewDigest=null;$('confirmReimport').disabled=true;$('changePreview').innerHTML='';$('importErrors').innerHTML='';};
}
function reimportBody(){const primary=$('keyField').value,extra=$('keyFieldExtra').value,third=$('keyFieldThird').value;return {token:state.preview.token,sheet:state.preview.sheet,moduleId:state.importTarget.id,keyFieldId:primary,keyFieldIds:[primary,...(extra?[extra]:[]),...(third?[third]:[])],...collectCorrections()}}
async function previewChanges(){
  state.reviewDigest=null;$('confirmReimport').disabled=true;
  try{const result=await api('/api/reimport/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(reimportBody())});
    const saved=collectCorrections(),staticFormulaKeys=new Set((state.preview.formulaIssues||[]).map(e=>`${e.row}:${e.column}`));$('importErrors').innerHTML='';$('dataCorrections').innerHTML=Object.entries(saved.dataCorrections).map(([key,value])=>`<input type="hidden" class="data-correction" data-key="${esc(key)}" value="${esc(value)}">`).join('')+Object.entries(saved.formulaCorrections).filter(([key])=>!staticFormulaKeys.has(key)).map(([key,value])=>`<input type="hidden" class="formula-correction" data-key="${esc(key)}" value="${esc(value)}">`).join('');state.reviewDigest=result.digest;
    const fields=state.importTarget.schema.fields;
    $('changePreview').innerHTML=`<div class="change-summary" role="status"><strong>${result.created} nuevos · ${result.updated} con cambios · ${result.unchanged} sin cambios</strong><p>Solo se guardarán los nuevos y los que cambiaron. Los demás registros quedan como están.</p></div><h3>Ejemplos de cambios</h3>${result.changes.length?`<div class="change-list">${result.changes.map(c=>`<div><strong>${c.action==='create'?'Nuevo':'Se actualizará'}: ${esc(c.key)}</strong>${c.action==='update'?`<ul>${fields.filter(f=>c.old?.[f.id]!==c.new[f.id]).map(f=>`<li>${esc(f.label)}: ${esc(c.old?.[f.id]??'vacío')} → ${esc(c.new[f.id]??'vacío')}</li>`).join('')}</ul>`:'<p>Se agregará este registro.</p>'}</div>`).join('')}</div>`:'<p>No hay cambios para guardar.</p>'}<p class="upload-note">Se muestran hasta 20 ejemplos. El resumen incluye todas las filas.</p>`;
    $('confirmReimport').disabled=!result.created&&!result.updated;
  }catch(e){const d=e.data||{};const problems=d.errors||d.conflicts||[];
    const suggestion=d.suggestedKeyFieldIds,fields=state.importTarget.schema.fields;
    const suggestedLabels=suggestion?.map(id=>fields.find(f=>f.id===id)?.label);
    $('importErrors').innerHTML=suggestion?`<div class="error-list" role="alert"><strong>La identificación elegida se repite.</strong><p>Encontramos una combinación de columnas que distingue las filas del módulo y del Excel sin eliminar registros.</p><button class="button secondary" type="button" id="useSuggestedKey">Usar ${esc(suggestedLabels.join(' + '))} y revisar cambios</button></div>`:problems.length?`<div class="error-list" role="alert"><strong>${d.errorCount??d.conflictCount} problemas por corregir</strong><p>Elegí otra columna principal o agregá columnas para distinguir las filas repetidas. No se guardará ningún cambio hasta resolverlas.</p><ul>${problems.map(x=>`<li>Fila ${x.row??'del módulo'}: ${esc(x.message)}${x.key!==undefined?` (clave: ${esc(x.key)})`:''}</li>`).join('')}</ul></div>`:'';
    if(suggestion)$('useSuggestedKey').onclick=()=>{$('keyField').value=suggestion[0];$('keyFieldExtra').value=suggestion[1];$('keyFieldThird').value=suggestion[2]||'';previewChanges()};
    const prior=collectCorrections(),previous=prior.dataCorrections;const editErrors=(d.errors||[]).filter(x=>x.code!=='INVALID_FORMULA');const editKeys=new Set(editErrors.map(x=>`${x.row}:${x.column}`));const staticFormulaKeys=new Set((state.preview.formulaIssues||[]).map(x=>`${x.row}:${x.column}`));const formulaErrors=(d.errors||[]).filter(x=>x.code==='INVALID_FORMULA'&&x.formula&&!staticFormulaKeys.has(`${x.row}:${x.column}`));const formulaKeys=new Set(formulaErrors.map(x=>`${x.row}:${x.column}`));$('dataCorrections').innerHTML=editErrors.map(x=>`<label class="cell-fix">Fila ${x.row} · ${esc(x.field)}<small>${esc(x.message)}</small><input class="data-correction" data-key="${x.row}:${x.column}" value="${esc(previous[`${x.row}:${x.column}`]??'')}" aria-label="Valor correcto para fila ${x.row}, ${esc(x.field)}"></label>`).join('')+Object.entries(previous).filter(([key])=>!editKeys.has(key)).map(([key,value])=>`<input type="hidden" class="data-correction" data-key="${esc(key)}" value="${esc(value)}">`).join('')+formulaErrors.map(x=>{const key=`${x.row}:${x.column}`;return `<label class="cell-fix">Fórmula de la fila ${x.row} · ${esc(x.field)}<small>${esc(x.message)}</small><input class="formula-correction" data-key="${key}" value="${esc(prior.formulaCorrections[key]??x.formula)}"></label>`}).join('')+Object.entries(prior.formulaCorrections).filter(([key])=>!staticFormulaKeys.has(key)&&!formulaKeys.has(key)).map(([key,value])=>`<input type="hidden" class="formula-correction" data-key="${esc(key)}" value="${esc(value)}">`).join('');
    if(!problems.length)toast(e.message,true);
  }
}
async function confirmReimport(){
  if(!state.reviewDigest)return;
  $('confirmReimport').disabled=true;
  try{const result=await api('/api/reimport/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...reimportBody(),digest:state.reviewDigest})});toast(`${result.created} registros nuevos y ${result.updated} actualizados.`);await refreshModules();await openModule(result.moduleId)}
  catch(e){toast(e.message,true);state.reviewDigest=null;$('confirmReimport').disabled=true;}
}
async function openModule(id){
  const request=++moduleRequest;recordsRequest++;
  try{const module=await api('/api/modules/'+id);if(request!==moduleRequest)return;state.module=module;state.page=1;state.records=[];showView('module');const schema=state.module.schema;
    $('breadcrumbs').innerHTML=`${esc(currentOrg()?.name)} <span>/</span> ${esc(schema.name)}`;$('moduleTitle').textContent=schema.name;
    $('schemaButton').hidden=!canWrite();$('undoImportButton').hidden=!canWrite()||!state.module.canUndoImport;state.visibleColumns=new Set(schema.fields.map(f=>f.id));
    $('filterField').innerHTML='<option value="">Sin filtro</option>'+schema.fields.map(f=>`<option value="${esc(f.id)}">${esc(f.label)}</option>`).join('');$('sortField').innerHTML='<option value="">Orden original</option>'+schema.fields.map(f=>`<option value="${esc(f.id)}">${esc(f.label)}</option>`).join('');$('sortField').value='';$('sortDirection').value='asc';$('searchInput').value='';$('filterValue').value='';$('filterField').value='';$('columnsMenu').open=false;renderColumns();updateOperators();renderRecords(false);await refreshViews();await renderModuleAttention();await loadRecords();
  }catch(e){if(request===moduleRequest){$('recordsArea').setAttribute('aria-busy','false');toast(e.message,true)}}
}
function renderColumns(){
  const fields=state.module.schema.fields;
  $('columnsList').innerHTML=fields.map(f=>`<label><input type="checkbox" data-column="${esc(f.id)}" ${state.visibleColumns.has(f.id)?'checked':''}> ${esc(f.label)}</label>`).join('');
  $('columnCount').textContent=`${state.visibleColumns.size} / ${fields.length} columnas`;
  $('columnsList').querySelectorAll('[data-column]').forEach(input=>input.onchange=()=>{if(input.checked)state.visibleColumns.add(input.dataset.column);else if(state.visibleColumns.size>1)state.visibleColumns.delete(input.dataset.column);else{input.checked=true;toast('Dejá al menos una columna visible.',true);return}renderColumns();renderRecords()});
}
async function refreshViews(){
  state.views=await api(`/api/modules/${state.module.id}/views`);
  $('savedViewSelect').innerHTML='<option value="">Elegir vista</option>'+state.views.map(v=>`<option value="${esc(v.id)}">${esc(v.name)}</option>`).join('');$('deleteViewButton').hidden=true;
}
function updateOperators(){
  const f=state.module?.schema.fields.find(x=>x.id===$('filterField').value);const kind=f?.type;
  const options=kind==='text'?[['contains','Contiene'],['eq','Igual'],['empty','Está vacío'],['not_empty','No está vacío']]:['integer','decimal','currency','date'].includes(kind)?[['eq','Igual'],['gt',kind==='date'?'Posterior a':'Mayor que'],['lt',kind==='date'?'Anterior a':'Menor que'],['empty','Está vacío'],['not_empty','No está vacío']]:[['eq','Igual'],['empty','Está vacío'],['not_empty','No está vacío']];
  $('filterOp').innerHTML=options.map(([v,t])=>`<option value="${v}">${t}</option>`).join('');$('filterOp').disabled=!f;
  $('filterValue').value='';$('filterChoice').value='';
  const choices=f?.type==='boolean'?[['true','Sí'],['false','No']]:f?.type==='enum'?f.options.map(v=>[v,v]):[];
  $('filterChoice').innerHTML='<option value="">Elegir valor…</option>'+choices.map(([value,label])=>`<option value="${esc(value)}">${esc(label)}</option>`).join('');
  $('filterValue').type=kind==='date'?'date':'text';
  $('filterValue').inputMode=['integer','decimal','currency'].includes(kind)?'decimal':'text';
  $('filterValue').placeholder=['integer','decimal','currency'].includes(kind)?'Ej.: 1234.50':'Escribí un valor';
  updateFilterInput();
}
function updateFilterInput(){
  const f=state.module?.schema.fields.find(x=>x.id===$('filterField').value);
  const empty=['empty','not_empty'].includes($('filterOp').value);
  const choice=['boolean','enum'].includes(f?.type);
  $('filterChoice').hidden=!choice;$('filterValue').hidden=choice;
  $('filterChoice').disabled=!f||empty;$('filterValue').disabled=!f||empty;
  $('filterHint').textContent=!f?'La búsqueda encuentra coincidencias en las columnas de texto.':empty?'Este filtro no necesita un valor.':choice?'Elegí un valor para aplicar el filtro. Se combina con tu búsqueda.':f.type==='date'?'Elegí una fecha para aplicar el filtro. Se combina con tu búsqueda.':'Escribí un valor para aplicar el filtro. Se combina con tu búsqueda.';
}
function filterTerm(){return $('filterChoice').hidden?$('filterValue').value:$('filterChoice').value;}
let searchTimer;
async function loadRecords(){
  if(!state.module)return;
  const request=++recordsRequest;
  const id=state.module.id,params=new URLSearchParams({page:String(state.page),q:$('searchInput').value});
  const term=filterTerm(),empty=['empty','not_empty'].includes($('filterOp').value);
  if($('filterField').value&&(empty||term!=='')){params.set('field',$('filterField').value);params.set('op',$('filterOp').value);params.set('value',term)}
  if($('sortField').value){params.set('sort',$('sortField').value);params.set('direction',$('sortDirection').value)}
  $('recordsArea').setAttribute('aria-busy','true');
  try{
    const data=await api(`/api/modules/${id}/records?${params}`);
    if(request!==recordsRequest||state.module?.id!==id)return;
    const lastPage=Math.max(1,Math.ceil(data.total/25));
    if(state.page>lastPage){state.page=lastPage;return await loadRecords();}
    state.records=data.items;
    $('moduleDescription').textContent=`${data.total} ${data.total===1?'registro':'registros'} · Información lista para consultar y editar`;
    renderRecords(state.renderedModule===id&&state.renderedPage===state.page);
    state.renderedModule=id;state.renderedPage=state.page;
    $('pageInfo').textContent=`Página ${data.page} de ${lastPage} · ${data.total} registros`;
    $('prevPage').disabled=data.page<=1;$('nextPage').disabled=data.page*25>=data.total;
  }catch(e){if(request===recordsRequest)toast(e.message,true)}
  finally{if(request===recordsRequest)$('recordsArea').setAttribute('aria-busy','false');}
}
function renderRecords(preserveScroll=true){
  if(!state.module)return;
  const previous=$('recordsArea').querySelector('.records-scroll');
  const scroll=preserveScroll?{left:previous?.scrollLeft||0,top:previous?.scrollTop||0}:{left:0,top:0};
  const fields=state.module.schema.fields.filter(f=>state.visibleColumns.has(f.id));
  const numeric=f=>['integer','decimal','currency'].includes(f.type);
  const width=f=>f.type==='text'?200:f.type==='boolean'?100:f.type==='date'?130:150;
  const actionsWidth=canWrite()?(state.moduleInsights?.stockFieldId?230:145):0;
  const widthTotal=fields.reduce((sum,f)=>sum+width(f),actionsWidth);
  const kinds={text:'Aa',integer:'#',decimal:'#',currency:'$',date:'◷',boolean:'◉',enum:'≡'};
  $('columnCount').textContent=`${fields.length} / ${state.module.schema.fields.length} columnas`;
  $('moduleView').classList.toggle('compact',state.compact);
  $('recordsArea').innerHTML=state.records.length?`<div class="records-scroll" role="region" aria-label="Tabla de registros, desplazable" tabindex="0"><table class="records-table" style="width:max(100%, ${widthTotal}px)"><colgroup>${fields.map(f=>`<col style="width:${width(f)}px">`).join('')}${canWrite()?`<col style="width:${actionsWidth}px">`:''}</colgroup><thead><tr>${fields.map(f=>`<th scope="col" class="${numeric(f)?'numeric':''}" title="${esc(f.label)}"><span class="head-label"><span class="field-kind" aria-hidden="true">${f.formula?'ƒ':kinds[f.type]}</span>${esc(f.label)}</span></th>`).join('')}${canWrite()?'<th scope="col" class="actions-cell">Acciones</th>':''}</tr></thead><tbody>${state.records.map(r=>`<tr>${fields.map(f=>`<td class="${numeric(f)?'numeric':''}" data-label="${esc(f.label)}"><span class="cell-value" title="${esc(r.values[f.id]??'Sin valor')}">${displayValue(r.values[f.id],f)}</span></td>`).join('')}${canWrite()?`<td class="actions-cell" data-label="Acciones"><div class="row-actions"><button data-edit="${esc(r.id)}" aria-label="Editar registro ${esc(r.values[state.module.schema.primaryFieldId]??'')}">Editar</button><button class="delete" data-delete="${esc(r.id)}" aria-label="Eliminar registro ${esc(r.values[state.module.schema.primaryFieldId]??'')}">Eliminar</button>${state.moduleInsights?.stockFieldId?`<button type="button" class="movement-button" data-sale="${esc(r.id)}">Registrar venta</button><button type="button" class="movement-button" data-receipt="${esc(r.id)}">Entrada de mercadería</button>`:''}</div></td>`:''}</tr>`).join('')}</tbody></table></div>`:'<div class="data-empty"><strong>No hay registros para mostrar</strong><p>Probá otra búsqueda o agregá un nuevo registro.</p></div>';
  $('recordsArea').querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>openRecord(state.records.find(r=>r.id===b.dataset.edit)));
  $('recordsArea').querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>removeRecord(b.dataset.delete));
  $('recordsArea').querySelectorAll('[data-sale]').forEach(b=>b.onclick=()=>openMovement(state.records.find(r=>r.id===b.dataset.sale),'sale'));
  $('recordsArea').querySelectorAll('[data-receipt]').forEach(b=>b.onclick=()=>openMovement(state.records.find(r=>r.id===b.dataset.receipt),'receipt'));
  const viewport=$('recordsArea').querySelector('.records-scroll');
  if(viewport){viewport.scrollLeft=scroll.left;viewport.scrollTop=scroll.top;}
}
function setExpanded(expanded){
  state.expanded=expanded;document.body.classList.toggle('table-expanded',expanded);
  $('expandTable').setAttribute('aria-pressed',String(expanded));
  $('expandTable').textContent=expanded?'⤡ Volver a vista normal':'⤢ Ampliar';
  document.querySelector('.sidebar').inert=expanded;
  document.querySelector('.topbar').inert=expanded;
}
function displayValue(value,field){
  if(value===null||value===undefined||value==='')return '<span class="cell-empty">—</span>';
  if(field.type==='boolean')return `<span class="status-pill ${value?'yes':'no'}">${value?'Sí':'No'}</span>`;
  if(field.type==='enum')return `<span class="status-pill enum">${esc(value)}</span>`;
  if(field.type==='currency')return 'ARS '+Number(value).toLocaleString('es-AR',{minimumFractionDigits:field.scale,maximumFractionDigits:field.scale});
  return esc(value);
}
function openRecord(record=null){
  if(!canWrite())return;
  $('recordError').hidden=true;state.editing=record;$('dialogEyebrow').textContent=record?'EDITAR REGISTRO':'NUEVO REGISTRO';$('dialogTitle').textContent=state.module.schema.name;
  $('recordFields').innerHTML=state.module.schema.fields.map(f=>{
    const value=record?.values[f.id]??'';let control;
    if(f.formula)control=`<input data-field="${f.id}" value="${esc(value)}" readonly aria-label="${esc(f.label)} calculado"><small>Se calcula con =${esc(f.formula)}</small>`;
    else if(f.type==='boolean')control=`<select data-field="${f.id}" ${f.required?'required':''}><option value="">Sin valor</option><option value="true" ${value===true?'selected':''}>Sí</option><option value="false" ${value===false?'selected':''}>No</option></select>`;
    else if(f.type==='enum')control=`<select data-field="${f.id}" ${f.required?'required':''}><option value="">Seleccionar</option>${f.options.map(o=>`<option value="${esc(o)}" ${value===o?'selected':''}>${esc(o)}</option>`).join('')}</select>`;
    else control=`<input data-field="${f.id}" type="${f.type==='date'?'date':f.type==='integer'||f.type==='decimal'||f.type==='currency'?'number':'text'}" ${f.type==='integer'?'step="1"':f.type==='decimal'||f.type==='currency'?`step="${1/(10**f.scale)}"`:''} value="${esc(value)}" ${f.required?'required':''}>`;
    return `<label class="${f.type==='text'?'wide':''}">${esc(f.label)}${f.required?' *':''}${control}</label>`;
  }).join('');$('recordDialog').showModal();
}
async function saveRecord(event){
  event.preventDefault();if(state.saving)return;const values={};for(const f of state.module.schema.fields){const node=document.querySelector(`[data-field="${f.id}"]`);values[f.id]=node.value===''?null:f.type==='boolean'?node.value==='true':node.value;}
  const id=state.module.id,edit=state.editing;const url=`/api/modules/${id}/records${edit?'/'+edit.id:''}`;
  state.saving=true;$('recordError').hidden=true;$('saveRecordButton').disabled=true;$('saveRecordButton').textContent='Guardando…';$('closeDialog').disabled=true;$('cancelDialog').disabled=true;
  try{await api(url,{method:edit?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({values})});$('recordDialog').close();toast(edit?'Registro actualizado.':'Registro creado.');await loadRecords();await refreshModules();await renderModuleAttention();}catch(e){$('recordError').textContent=e.message;$('recordError').hidden=false;}
  finally{state.saving=false;$('saveRecordButton').disabled=false;$('saveRecordButton').textContent='Guardar cambios';$('closeDialog').disabled=false;$('cancelDialog').disabled=false;}
}
function removeRecord(id){
  const record=state.records.find(r=>r.id===id);if(!record)return;
  state.pendingDelete={id,moduleId:state.module.id};$('deleteError').hidden=true;
  $('deleteRecordName').textContent=String(record.values[state.module.schema.primaryFieldId]??'Registro sin nombre');
  $('deleteDialog').showModal();
}
async function deleteRecord(event){
  event.preventDefault();if(!state.pendingDelete||state.deleting)return;
  const {id,moduleId}=state.pendingDelete;state.deleting=true;$('confirmDelete').disabled=true;$('confirmDelete').textContent='Eliminando…';$('closeDelete').disabled=true;$('cancelDelete').disabled=true;
  try{await api(`/api/modules/${moduleId}/records/${id}`,{method:'DELETE'});$('deleteDialog').close();state.pendingDelete=null;toast('Registro eliminado.');if(state.module?.id===moduleId){await loadRecords();await renderModuleAttention();}await refreshModules();}
  catch(e){$('deleteError').textContent=e.message;$('deleteError').hidden=false;}
  finally{state.deleting=false;$('confirmDelete').disabled=false;$('confirmDelete').textContent='Eliminar registro';$('closeDelete').disabled=false;$('cancelDelete').disabled=false;}
}
function openMovement(record,kind){
  if(!record)return;
  state.movement={recordId:record.id,kind};
  const name=record.values[state.module.schema.primaryFieldId]||'este producto';
  $('movementTitle').textContent=kind==='sale'?'Registrar venta':'Registrar entrada de mercadería';
  $('movementDescription').textContent=`${name}. El stock actual se actualizará al guardar.`;
  $('movementQuantity').value='';$('movementDialog').showModal();$('movementQuantity').focus();
}
$('cancelMovement').onclick=()=>$('movementDialog').close();
$('movementForm').onsubmit=async event=>{
  event.preventDefault();if(!state.movement)return;
  const {recordId,kind}=state.movement;
  try{
    await api(`/api/modules/${state.module.id}/records/${recordId}/movements`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,quantity:$('movementQuantity').value})});
    state.module.canUndoImport=false;$('undoImportButton').hidden=true;
    $('movementDialog').close();toast(kind==='sale'?'Venta registrada y stock actualizado.':'Entrada registrada y stock actualizado.');
    await renderModuleAttention();await loadRecords();
  }catch(e){toast(e.message,true)}
};

$('homeButton').onclick=home;$('startImport').onclick=()=>startImport();$('navImport').onclick=()=>startImport();$('chooseFile').onclick=()=>$('fileInput').click();$('importBack').onclick=home;$('fileInput').onchange=e=>upload(e.target.files[0]);
$('searchInput').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.page=1;loadRecords()},250)};
$('filterField').onchange=()=>{updateOperators();state.page=1;loadRecords()};$('filterOp').onchange=()=>{updateFilterInput();state.page=1;loadRecords()};$('filterValue').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.page=1;loadRecords()},250)};$('filterChoice').onchange=()=>{state.page=1;loadRecords()};
$('clearFilter').onclick=()=>{clearTimeout(searchTimer);$('searchInput').value='';$('filterField').value='';$('filterValue').value='';$('filterChoice').value='';updateOperators();state.page=1;loadRecords()};
$('sortField').onchange=()=>{state.page=1;loadRecords()};$('sortDirection').onchange=()=>{state.page=1;loadRecords()};
$('saveViewButton').onclick=async()=>{const name=prompt('¿Qué nombre querés darle a esta vista? Por ejemplo: Productos con poco stock');if(!name)return;const query={q:$('searchInput').value,field:$('filterField').value,op:$('filterField').value?$('filterOp').value:'',value:filterTerm(),sort:$('sortField').value,direction:$('sortDirection').value,columns:[...state.visibleColumns]};try{const saved=await api(`/api/modules/${state.module.id}/views`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,query})});await refreshViews();$('savedViewSelect').value=saved.id;$('deleteViewButton').hidden=false;toast('Vista guardada para tu usuario.')}catch(e){toast(e.message,true)}};
$('savedViewSelect').onchange=()=>{const view=state.views.find(v=>v.id===$('savedViewSelect').value);$('deleteViewButton').hidden=!view;if(!view)return;const q=view.query;$('searchInput').value=q.q||'';$('filterField').value=q.field||'';updateOperators();if(q.op)$('filterOp').value=q.op;$('filterValue').value=q.value||'';$('filterChoice').value=q.value||'';updateFilterInput();$('sortField').value=q.sort||'';$('sortDirection').value=q.direction||'asc';state.visibleColumns=new Set((q.columns||state.module.schema.fields.map(f=>f.id)).filter(fid=>state.module.schema.fields.some(f=>f.id===fid)));if(!state.visibleColumns.size)state.visibleColumns.add(state.module.schema.fields[0].id);renderColumns();state.page=1;loadRecords()};
$('deleteViewButton').onclick=async()=>{const id=$('savedViewSelect').value;if(!id||!confirm('¿Eliminar esta vista guardada? Los registros no se borrarán.'))return;try{await api(`/api/modules/${state.module.id}/views/${id}`,{method:'DELETE'});await refreshViews();toast('Vista eliminada.')}catch(e){toast(e.message,true)}};
$('prevPage').onclick=()=>{state.page--;loadRecords()};$('nextPage').onclick=()=>{state.page++;loadRecords()};
$('newRecordButton').onclick=()=>openRecord();$('recordForm').onsubmit=saveRecord;$('recordDialog').oncancel=event=>{if(state.saving)event.preventDefault()};$('deleteForm').onsubmit=deleteRecord;$('deleteDialog').oncancel=event=>{if(state.deleting)event.preventDefault()};$('closeDelete').onclick=()=>$('deleteDialog').close();$('cancelDelete').onclick=()=>$('deleteDialog').close();$('closeDialog').onclick=()=> $('recordDialog').close();$('cancelDialog').onclick=()=> $('recordDialog').close();$('densityButton').onclick=()=>{state.compact=!state.compact;$('densityButton').setAttribute('aria-pressed',String(state.compact));$('densityButton').textContent=state.compact?'Filas compactas':'Filas cómodas';$('moduleView').classList.toggle('compact',state.compact)};$('expandTable').onclick=()=>setExpanded(!state.expanded);document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('recordDialog').open&&!$('deleteDialog').open){if(state.expanded){setExpanded(false);$('expandTable').focus()}}});
let schemaDraft=[];
function syncSchemaDraft(){schemaDraft=schemaDraft.map((f,i)=>{const row=document.querySelector(`[data-schema-index="${i}"]`);if(!row)return f;return {...f,label:row.querySelector('.schema-label').value,type:row.querySelector('.schema-type')?.value||f.type,required:row.querySelector('.schema-required').checked,options:row.querySelector('.schema-options-input').value.split(',').map(x=>x.trim()).filter(Boolean)}})}
function renderSchemaFields(){
  $('schemaFields').innerHTML=`<label class="schema-name">Nombre del módulo<input id="schemaName" value="${esc(state.module.schema.name)}" maxlength="80" required></label><p>Los campos existentes conservan sus datos. Los campos nuevos empiezan vacíos.</p>${schemaDraft.map((f,i)=>`<div class="schema-row" data-schema-index="${i}"><label>Nombre del campo<input class="schema-label" value="${esc(f.label)}" maxlength="80" required></label><label>Tipo de dato ${i<state.module.schema.fields.length?`<strong>${esc(({text:'Texto',integer:'Número entero',decimal:'Número decimal',currency:'Importe',date:'Fecha',boolean:'Sí / No',enum:'Opciones'})[f.type])}</strong>`:`<select class="schema-type">${['text','integer','decimal','currency','date','boolean','enum'].map(t=>`<option value="${t}" ${f.type===t?'selected':''}>${esc(({text:'Texto',integer:'Número entero',decimal:'Número decimal',currency:'Importe',date:'Fecha',boolean:'Sí / No',enum:'Opciones'})[t])}</option>`).join('')}</select>`}</label><label class="schema-check"><input class="schema-required" type="checkbox" ${f.required?'checked':''}> Obligatorio</label><label class="schema-options" ${f.type==='enum'?'':'hidden'}>Opciones, separadas por coma<input value="${esc((f.options||[]).join(', '))}" class="schema-options-input" placeholder="Ejemplo: Pendiente, Listo"></label></div>`).join('')}`;
  $('schemaName').parentElement.insertAdjacentHTML('afterend',`<label class="schema-name">Tipo de planilla<select id="schemaTemplate"><option value="general">Otra planilla</option><option value="habilitaciones">Habilitaciones</option><option value="minimercado">Minimercado</option><option value="corralon">Corralón de materiales</option></select></label>`);
  $('schemaTemplate').value=state.module.schema.template||'general';
  $('schemaFields').querySelectorAll('.schema-type').forEach(select=>select.onchange=()=>{const row=select.closest('.schema-row');row.querySelector('.schema-options').hidden=select.value!=='enum'});
}
$('schemaButton').onclick=()=>{schemaDraft=state.module.schema.fields.map(f=>({...f}));renderSchemaFields();$('schemaDialog').showModal()};
$('closeSchema').onclick=()=>$('schemaDialog').close();
$('addFieldButton').onclick=()=>{if(schemaDraft.length>=30)return toast('El módulo admite hasta 30 campos.',true);const moduleName=$('schemaName').value;syncSchemaDraft();const next=Math.max(0,...schemaDraft.map(f=>Number(f.id.slice(1))||0))+1;schemaDraft.push({id:`f${next}`,label:'Nuevo campo',type:'text',required:false,sourceColumn:null});renderSchemaFields();$('schemaName').value=moduleName;$('schemaFields').scrollTop=$('schemaFields').scrollHeight};
$('templateFieldsButton').onclick=()=>{
  const template=$('schemaTemplate').value;
  if(!['minimercado','corralon'].includes(template)){toast('Los campos sugeridos están disponibles para minimercado y corralón.',true);return;}
  const moduleName=$('schemaName').value;syncSchemaDraft();
  let next=Math.max(0,...schemaDraft.map(f=>Number(f.id.slice(1))||0))+1;
  const suggested=[['Stock actual','decimal',2],['Stock mínimo','decimal',2],['Ventas 30 días','decimal',2],['Días de entrega','integer',null]];
  let added=0;
  for(const [label,type,scale] of suggested){
    if(schemaDraft.some(f=>f.label.toLocaleLowerCase('es-AR')===label.toLocaleLowerCase('es-AR')))continue;
    if(schemaDraft.length>=30)break;
    schemaDraft.push({id:`f${next++}`,label,type,scale,required:false,sourceColumn:null});added++;
  }
  renderSchemaFields();$('schemaName').value=moduleName;$('schemaTemplate').value=template;
  toast(added?`${added} campos sugeridos agregados. Guardá la configuración y completá sus datos.`:'No hay espacio o esos campos ya existen.');
};
$('schemaForm').onsubmit=async event=>{event.preventDefault();const fields=schemaDraft.map((f,i)=>{const row=document.querySelector(`[data-schema-index="${i}"]`),type=row.querySelector('.schema-type')?.value||f.type;const item={...f,label:row.querySelector('.schema-label').value.trim(),type,required:row.querySelector('.schema-required').checked};if(type==='enum')item.options=row.querySelector('.schema-options-input').value.split(',').map(x=>x.trim()).filter(Boolean);if(type==='decimal'||type==='currency')item.scale=f.scale??2;return item});try{await api(`/api/modules/${state.module.id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:state.module.schema.revision||1,name:$('schemaName').value.trim(),template:$('schemaTemplate').value,primaryFieldId:state.module.schema.primaryFieldId,fields})});$('schemaDialog').close();toast('Configuración guardada.');await refreshModules();await openModule(state.module.id)}catch(e){toast(e.message,true)}};
$('reimportButton').onclick=()=>startImport(state.module);
$('undoImportButton').onclick=async()=>{if(!state.module?.canUndoImport)return;if(!confirm('¿Deshacer esta importación? Se quitará el módulo completo. Esta opción solo aparece si nadie modificó sus datos.'))return;try{await api(`/api/modules/${state.module.id}/undo-import`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});state.module=null;home();toast('Importación deshecha. Podés volver a subir el Excel.')}catch(e){toast(e.message,true)}};
$('historyButton').onclick=async()=>{try{const history=await api(`/api/modules/${state.module.id}/reimports`);$('historyList').innerHTML=history.length?history.map(run=>`<div class="history-row"><div><strong>${esc(new Date(run.created_at+'Z').toLocaleString('es-AR'))}</strong><p>${run.created} nuevos · ${run.updated} actualizados ${run.undone_at?'· Deshecho':''}</p></div>${canWrite()&&!run.undone_at?`<button class="button secondary" data-undo="${esc(run.id)}" type="button">Deshacer</button>`:''}</div>`).join(''):'<p>Todavía no hay actualizaciones desde Excel.</p>';$('historyList').querySelectorAll('[data-undo]').forEach(b=>b.onclick=async()=>{if(!confirm('¿Deshacer esta actualización? Solo se puede si nadie editó sus registros después.'))return;try{await api(`/api/modules/${state.module.id}/reimports/${b.dataset.undo}`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});$('historyDialog').close();toast('Actualización deshecha.');await loadRecords();await refreshModules();await renderModuleAttention();}catch(e){toast(e.message,true)}});$('historyDialog').showModal()}catch(e){toast(e.message,true)}};
$('closeHistory').onclick=()=>$('historyDialog').close();
$('exportButton').onclick=async()=>{
  try{
    const response=await fetch(`/api/modules/${state.module.id}/export`,{headers:{'X-Organization-Id':state.organizationId},credentials:'same-origin'});
    if(!response.ok)throw new Error((await response.json()).error||'No se pudo exportar.');
    const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download=`tablio-${state.module.id.slice(0,8)}.xlsx`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){toast(e.message,true)}
};
$('loginForm').onsubmit=login;$('logoutButton').onclick=logout;
$('passwordButton').onclick=()=>$('passwordDialog').showModal();
$('cancelPassword').onclick=()=>$('passwordDialog').close();
$('passwordForm').onsubmit=async event=>{event.preventDefault();try{await api('/api/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(event.target)))});event.target.reset();$('passwordDialog').close();state.auth=null;state.organizationId=null;await boot();toast('Contraseña actualizada. Volvé a ingresar.')}catch(e){toast(e.message,true)}};
$('organizationSelect').onchange=()=>{state.organizationId=$('organizationSelect').value;state.module=null;renderAccount();home()};
$('newOrgButton').onclick=async()=>{const name=prompt('Nombre de la nueva organización:');if(!name)return;try{const result=await api('/api/organizations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});state.auth=await api('/api/me');state.organizationId=result.id;renderAccount();home();}catch(e){toast(e.message,true)}};
async function refreshUsers(){
  const users=await api('/api/users');
  $('usersList').innerHTML=users.map(u=>`<div class="user-row"><div><strong>${esc(u.name)}</strong><small>${esc(u.email)}</small></div><select data-role="${esc(u.id)}" ${u.role==='owner'?'disabled':''}>${['owner','admin','editor','viewer'].filter(r=>r!=='owner'||u.role==='owner').map(r=>`<option value="${r}" ${r===u.role?'selected':''}>${({owner:'Propietario',admin:'Administrador',editor:'Editor',viewer:'Lector'})[r]}</option>`).join('')}</select><button data-reset="${esc(u.email)}" type="button">Recuperar acceso</button>${u.role==='owner'?'':`<button data-remove="${esc(u.id)}" type="button">Quitar</button>`}</div>`).join('');
  $('usersList').querySelectorAll('[data-role]').forEach(node=>node.onchange=async()=>{try{await api(`/api/users/${node.dataset.role}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:node.value})});toast('Rol actualizado.');await refreshUsers();}catch(e){toast(e.message,true);await refreshUsers()}});
  $('usersList').querySelectorAll('[data-remove]').forEach(node=>node.onclick=async()=>{if(!confirm('¿Quitar el acceso de este usuario a la organización?'))return;try{await api(`/api/users/${node.dataset.remove}`,{method:'DELETE'});await refreshUsers()}catch(e){toast(e.message,true)}});
  $('usersList').querySelectorAll('[data-reset]').forEach(node=>node.onclick=async()=>{if(!confirm(`¿Crear un enlace para que ${node.dataset.reset} cambie su contraseña? El enlace vence en una hora.`))return;try{const result=await api('/api/password-resets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:node.dataset.reset})});showAccessLink(result.token,'Recuperar acceso: compartí este enlace solo con la persona indicada. Vence en una hora.')}catch(e){toast(e.message,true)}});
}
function showAccessLink(token,message){const link=`${location.origin}/#access=${encodeURIComponent(token)}`;const node=$('accessLinkResult');node.hidden=false;node.innerHTML=`<strong>${esc(message)}</strong><input readonly aria-label="Enlace privado" value="${esc(link)}"><button class="button secondary" id="copyAccessLink" type="button">Copiar enlace</button>`;$('copyAccessLink').onclick=async()=>{try{await navigator.clipboard.writeText(link);toast('Enlace copiado.')}catch(e){node.querySelector('input').select();toast('Seleccioná y copiá el enlace.')}};}
$('usersButton').onclick=async()=>{try{await refreshUsers();$('usersDialog').showModal()}catch(e){toast(e.message,true)}};
$('closeUsers').onclick=()=>$('usersDialog').close();
$('inviteForm').onsubmit=async event=>{event.preventDefault();const form=event.target,body=Object.fromEntries(new FormData(form));try{const result=await api('/api/invitations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});form.reset();showAccessLink(result.token,'Invitación lista. Compartí este enlace solo con la persona indicada. Vence en 7 días.')}catch(e){toast(e.message,true)}};
$('createUserForm').onsubmit=async event=>{event.preventDefault();const form=event.target,body=Object.fromEntries(new FormData(form));try{await api('/api/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});form.reset();await refreshUsers();toast('Usuario creado.')}catch(e){toast(e.message,true)}};
$('membershipForm').onsubmit=async event=>{event.preventDefault();const form=event.target,body=Object.fromEntries(new FormData(form));try{await api('/api/memberships',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});form.reset();await refreshUsers();toast('Membresía agregada.')}catch(e){toast(e.message,true)}};
$('activityButton').onclick=async()=>{try{const events=await api('/api/activity');const labels={module_imported:'Importó una planilla',reimport_applied:'Actualizó datos desde Excel',reimport_undone:'Deshizo una actualización',record_created:'Agregó un registro',record_updated:'Editó un registro',record_deleted:'Eliminó un registro',module_configured:'Configuró un módulo',user_created:'Creó un usuario',member_added:'Agregó una persona',member_removed:'Quitó una persona',member_role_changed:'Cambió un permiso',invitation_created:'Creó una invitación',invitation_accepted:'Aceptó una invitación',password_reset_issued:'Creó un enlace de recuperación',password_reset_completed:'Cambió una contraseña'};$('activityList').innerHTML=events.length?events.map(e=>`<div class="history-row"><div><strong>${esc(labels[e.action]||e.action)}</strong><p>${esc(e.actor)} · ${esc(new Date(e.createdAt+'Z').toLocaleString('es-AR'))}</p></div></div>`).join(''):'<p>Todavía no hay actividad.</p>';$('activityDialog').showModal()}catch(e){toast(e.message,true)}};
$('closeActivity').onclick=()=>$('activityDialog').close();
boot();
