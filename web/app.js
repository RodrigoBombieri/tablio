const $ = id => document.getElementById(id);
const state = {modules:[],preview:null,module:null,page:1,editing:null};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function api(path, options={}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) { const issue = new Error(data.error || 'No se pudo completar la operación.'); issue.data=data; throw issue; }
  return data;
}
function toast(message, isError=false) {
  const node=$('toast'); node.textContent=message; node.className=isError?'error':''; node.style.display='block';
  clearTimeout(toast.timer); toast.timer=setTimeout(()=>node.style.display='none',4600);
}
function showView(name){for(const id of ['homeView','importView','moduleView']) $(id).hidden=id!==name+'View'; $('homeButton').classList.toggle('active',name==='home');}
async function refreshModules(){
  state.modules=await api('/api/modules');
  $('moduleNav').innerHTML=state.modules.map(m=>`<button data-id="${esc(m.id)}" type="button">▦ <span>${esc(m.name)}</span></button>`).join('');
  $('moduleCards').innerHTML=state.modules.length?state.modules.map(m=>`<button class="module-card" data-id="${esc(m.id)}" type="button"><span class="card-icon">▦</span><strong>${esc(m.name)}</strong><small>${m.count} registros · Abrir módulo →</small></button>`).join(''):'<div class="empty">Todavía no hay módulos. Importá una planilla para empezar.</div>';
  document.querySelectorAll('[data-id]').forEach(node=>node.addEventListener('click',()=>openModule(node.dataset.id)));
}
function home(){showView('home');$('breadcrumbs').innerHTML='Mi organización <span>/</span> Inicio';refreshModules().catch(e=>toast(e.message,true));}
function startImport(){state.preview=null;$('uploadPanel').hidden=false;$('reviewPanel').hidden=true;$('fileInput').value='';$('breadcrumbs').innerHTML='Mi organización <span>/</span> Nueva importación';showView('import');setStep(1);}
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
function renderReview(){
  const p=state.preview;$('uploadPanel').hidden=true;$('reviewPanel').hidden=false;setStep(2);
  const fields=p.fields.map((f,i)=>`<tr data-index="${i}"><td><input type="checkbox" class="include" checked aria-label="Incluir ${esc(f.label)}"></td><td><input type="text" class="label" value="${esc(f.label)}" aria-label="Etiqueta de ${esc(f.label)}"><br><small>Columna ${f.sourceColumn+1}${f.formulaCount?' · Calculada':''}</small></td><td><select class="type" aria-label="Tipo de ${esc(f.label)}" ${f.formulaCount?'disabled':''}>${['text','integer','decimal','currency','date','boolean','enum'].map(t=>`<option value="${t}" ${t===f.type?'selected':''}>${({text:'Texto',integer:'Entero',decimal:'Decimal',currency:'Importe',date:'Fecha',boolean:'Sí / No',enum:'Opciones'})[t]}</option>`).join('')}</select></td><td><input type="checkbox" class="required" ${f.required?'checked':''} aria-label="Obligatorio ${esc(f.label)}"></td><td><input type="number" min="0" max="6" class="scale" value="${f.scale??2}" aria-label="Decimales de ${esc(f.label)}"></td><td><input type="text" class="options" value="${esc(f.options.join(', '))}" placeholder="Separadas por coma" aria-label="Opciones de ${esc(f.label)}"></td><td><small>${f.emptyCount} vacíos<br>${esc(f.formula?'='+f.formula:f.examples.slice(0,2).join(' · '))}</small></td></tr>`).join('');
  const issues=p.formulaIssues||[];
  const issueList=issues.length?`<section class="formula-issues"><h3>Fórmulas para corregir (${issues.length})</h3><p>Corregí la expresión en su fila y columna. Las referencias deben ser de la misma fila. También podés excluir la columna completa.</p>${issues.map(issue=>`<label>Fila ${issue.row}, columna ${issue.column} (${esc(issue.field)})<input class="formula-correction" data-key="${issue.row}:${issue.column}" value="${esc(issue.formula)}"><small>${esc(issue.message)}</small></label>`).join('')}</section>`:'';
  $('reviewPanel').innerHTML=`<div class="panel"><div class="review-header"><div><h2>Revisá la estructura</h2><p>${p.rowCount} registros · ${p.fields.length} columnas detectadas</p></div><button class="button secondary" id="changeFile" type="button">Cambiar archivo</button></div><div class="review-content"><label for="sheetSelect">Hoja del libro</label><select class="name-input" id="sheetSelect">${p.sheets.map(s=>`<option ${s===p.sheet?'selected':''}>${esc(s)}</option>`).join('')}</select><label for="moduleName">Nombre del módulo</label><input class="name-input" id="moduleName" value="${esc(p.sheet)}" maxlength="80"><div class="table-scroll"><table class="field-table"><thead><tr><th>Usar</th><th>Columna</th><th>Tipo</th><th>Obligatorio</th><th>Decimales</th><th>Opciones</th><th>Muestra</th></tr></thead><tbody>${fields}</tbody></table></div>${issueList}<p class="upload-note">Revisá las opciones y los tipos. Los importes se interpretan en ARS. Los datos se validan completos antes de guardarse.</p><div id="importErrors"></div></div><div class="review-actions"><span class="hint">Ningún registro se importará si hay errores.</span><button class="button primary" id="confirmImport" type="button">Confirmar e importar →</button></div></div>`;
  $('changeFile').onclick=startImport;
  $('sheetSelect').onchange=async()=>{try{state.preview=await api(`/api/preview?token=${encodeURIComponent(p.token)}&sheet=${encodeURIComponent($('sheetSelect').value)}`);renderReview();}catch(e){toast(e.message,true)}};
  $('confirmImport').onclick=confirmImport;
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
  return {schemaVersion:1,name:$('moduleName').value.trim(),primaryFieldId:fields.find(f=>f.type==='text')?.id||fields[0].id,fields};
}
async function confirmImport(){
  try{
    const schema=collectSchema();$('confirmImport').disabled=true;setStep(3);
    const formulaCorrections={};document.querySelectorAll('.formula-correction').forEach(node=>formulaCorrections[node.dataset.key]=node.value.trim());
    const result=await api('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:state.preview.token,sheet:state.preview.sheet,schema,formulaCorrections})});
    toast(`${result.count??0} registros importados.`);await refreshModules();await openModule(result.moduleId);
  }catch(e){setStep(2);$('confirmImport').disabled=false;if(e.data?.errors){$('importErrors').innerHTML='<div class="error-list"><strong>'+e.data.errorCount+' errores de validación:</strong><ul>'+e.data.errors.slice(0,12).map(x=>`<li>Fila ${x.row}, columna ${x.column} (${esc(x.field)}): ${esc(x.message)}</li>`).join('')+'</ul></div>';}else toast(e.message,true)}
}
async function openModule(id){
  try{state.module=await api('/api/modules/'+id);state.page=1;showView('module');const schema=state.module.schema;
    $('breadcrumbs').innerHTML=`Mi organización <span>/</span> ${esc(schema.name)}`;$('moduleTitle').textContent=schema.name;
    $('filterField').innerHTML='<option value="">Sin filtro</option>'+schema.fields.map(f=>`<option value="${esc(f.id)}">${esc(f.label)}</option>`).join('');$('searchInput').value='';$('filterValue').value='';$('filterField').value='';updateOperators();await loadRecords();
  }catch(e){toast(e.message,true)}
}
function updateOperators(){
  const f=state.module?.schema.fields.find(x=>x.id===$('filterField').value);const kind=f?.type;
  const options=kind==='text'?[['contains','Contiene'],['eq','Igual'],['empty','Está vacío'],['not_empty','No está vacío']]:['integer','decimal','currency','date'].includes(kind)?[['eq','Igual'],['gt',kind==='date'?'Posterior a':'Mayor que'],['lt',kind==='date'?'Anterior a':'Menor que'],['empty','Está vacío'],['not_empty','No está vacío']]:[['eq','Igual'],['empty','Está vacío'],['not_empty','No está vacío']];
  $('filterOp').innerHTML=options.map(([v,t])=>`<option value="${v}">${t}</option>`).join('');$('filterOp').disabled=!f;$('filterValue').disabled=!f;
  if(f?.type==='enum')$('filterValue').placeholder=f.options.join(', ');else $('filterValue').placeholder='Valor';
}
let searchTimer;
async function loadRecords(){
  if(!state.module)return;
  const id=state.module.id,params=new URLSearchParams({page:String(state.page),q:$('searchInput').value});
  if($('filterField').value){params.set('field',$('filterField').value);params.set('op',$('filterOp').value);params.set('value',$('filterValue').value)}
  try{
    const data=await api(`/api/modules/${id}/records?${params}`);state.records=data.items;
    $('moduleDescription').textContent=`${data.total} ${data.total===1?'registro':'registros'} · Información lista para consultar y editar`;
    const fields=state.module.schema.fields;
    $('recordsArea').innerHTML=data.items.length?`<div class="records-scroll"><table class="records-table"><thead><tr>${fields.map(f=>`<th>${esc(f.label)}</th>`).join('')}<th>Acciones</th></tr></thead><tbody>${data.items.map(r=>`<tr>${fields.map(f=>`<td>${displayValue(r.values[f.id],f)}</td>`).join('')}<td><button data-edit="${r.id}">Editar</button> <button class="delete" data-delete="${r.id}">Eliminar</button></td></tr>`).join('')}</tbody></table></div>`:'<div class="data-empty">No hay registros para mostrar.</div>';
    $('recordsArea').querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>openRecord(state.records.find(r=>r.id===b.dataset.edit)));
    $('recordsArea').querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>removeRecord(b.dataset.delete));
    $('pageInfo').textContent=`Página ${data.page} de ${Math.max(1,Math.ceil(data.total/25))} · ${data.total} registros`;
    $('prevPage').disabled=data.page<=1;$('nextPage').disabled=data.page*25>=data.total;
  }catch(e){toast(e.message,true)}
}
function displayValue(value,field){if(value===null||value===undefined||value==='')return '<span style="color:#a0aaa0">—</span>';if(field.type==='boolean')return value?'Sí':'No';if(field.type==='currency')return 'ARS '+Number(value).toLocaleString('es-AR',{minimumFractionDigits:field.scale,maximumFractionDigits:field.scale});return esc(value)}
function openRecord(record=null){
  state.editing=record;$('dialogEyebrow').textContent=record?'EDITAR REGISTRO':'NUEVO REGISTRO';$('dialogTitle').textContent=state.module.schema.name;
  $('recordFields').innerHTML=state.module.schema.fields.map(f=>{
    const value=record?.values[f.id]??'';let control;
    if(f.formula)control=`<input data-field="${f.id}" value="${esc(value)}" readonly aria-label="${esc(f.label)} calculado"><small>Se calcula con =${esc(f.formula)}</small>`;
    else if(f.type==='boolean')control=`<select data-field="${f.id}"><option value="">Sin valor</option><option value="true" ${value===true?'selected':''}>Sí</option><option value="false" ${value===false?'selected':''}>No</option></select>`;
    else if(f.type==='enum')control=`<select data-field="${f.id}"><option value="">Seleccionar</option>${f.options.map(o=>`<option value="${esc(o)}" ${value===o?'selected':''}>${esc(o)}</option>`).join('')}</select>`;
    else control=`<input data-field="${f.id}" type="${f.type==='date'?'date':f.type==='integer'||f.type==='decimal'||f.type==='currency'?'number':'text'}" ${f.type==='integer'?'step="1"':f.type==='decimal'||f.type==='currency'?`step="${1/(10**f.scale)}"`:''} value="${esc(value)}" ${f.required?'required':''}>`;
    return `<label class="${f.type==='text'?'wide':''}">${esc(f.label)}${f.required?' *':''}${control}</label>`;
  }).join('');$('recordDialog').showModal();
}
async function saveRecord(event){
  event.preventDefault();const values={};for(const f of state.module.schema.fields){const node=document.querySelector(`[data-field="${f.id}"]`);values[f.id]=node.value===''?null:f.type==='boolean'?node.value==='true':node.value;}
  const id=state.module.id,edit=state.editing;const url=`/api/modules/${id}/records${edit?'/'+edit.id:''}`;
  try{await api(url,{method:edit?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({values})});$('recordDialog').close();toast(edit?'Registro actualizado.':'Registro creado.');await loadRecords();await refreshModules();}catch(e){toast(e.message,true)}
}
async function removeRecord(id){if(!confirm('¿Eliminar este registro?'))return;try{await api(`/api/modules/${state.module.id}/records/${id}`,{method:'DELETE'});toast('Registro eliminado.');await loadRecords();await refreshModules();}catch(e){toast(e.message,true)}}

$('homeButton').onclick=home;$('startImport').onclick=startImport;$('importBack').onclick=home;$('fileInput').onchange=e=>upload(e.target.files[0]);
$('searchInput').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.page=1;loadRecords()},250)};
$('filterField').onchange=()=>{updateOperators();state.page=1;loadRecords()};$('filterOp').onchange=()=>{state.page=1;loadRecords()};$('filterValue').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.page=1;loadRecords()},250)};
$('clearFilter').onclick=()=>{$('filterField').value='';$('filterValue').value='';updateOperators();state.page=1;loadRecords()};
$('prevPage').onclick=()=>{state.page--;loadRecords()};$('nextPage').onclick=()=>{state.page++;loadRecords()};
$('newRecordButton').onclick=()=>openRecord();$('recordForm').onsubmit=saveRecord;$('closeDialog').onclick=()=> $('recordDialog').close();$('cancelDialog').onclick=()=> $('recordDialog').close();
$('exportButton').onclick=()=>{window.location.href=`/api/modules/${state.module.id}/export`};
home();
