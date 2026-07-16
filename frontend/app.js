const CFG = window.EXAM_CONFIG || {};
const API = (CFG.apiBase || "/api");
let ID_TOKEN = sessionStorage.getItem("id_token") || "";
let MODELS = null; // cache de /api/models

/* ---------------- Cognito Hosted UI (PKCE) ---------------- */
function b64url(buf){return btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');}
async function sha256(s){return await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));}
function rand(n){const a=new Uint8Array(n);crypto.getRandomValues(a);return b64url(a.buffer);}
function redirectUri(){return window.location.origin + "/";}
function hostedBase(){return `https://${CFG.cognitoDomain}.auth.${CFG.region}.amazoncognito.com`;}
async function login(){
  const v = rand(48); sessionStorage.setItem("pkce_verifier", v);
  const ch = b64url(await sha256(v));
  const u = new URL(hostedBase()+"/oauth2/authorize");
  u.search = new URLSearchParams({response_type:"code", client_id:CFG.clientId, redirect_uri:redirectUri(),
    scope:"openid email profile", code_challenge_method:"S256", code_challenge:ch}).toString();
  window.location = u.toString();
}
async function exchangeCode(code){
  const v = sessionStorage.getItem("pkce_verifier")||"";
  const r = await fetch(hostedBase()+"/oauth2/token",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},
    body:new URLSearchParams({grant_type:"authorization_code",client_id:CFG.clientId,code,redirect_uri:redirectUri(),code_verifier:v})});
  if(!r.ok) throw new Error("Falha no login."); const t=await r.json();
  ID_TOKEN=t.id_token; sessionStorage.setItem("id_token",ID_TOKEN);
  if(t.refresh_token) sessionStorage.setItem("refresh_token", t.refresh_token);
  window.history.replaceState({},"","/");
}
async function refreshToken(){
  const rt=sessionStorage.getItem("refresh_token"); if(!rt) return false;
  try{
    const r=await fetch(hostedBase()+"/oauth2/token",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},
      body:new URLSearchParams({grant_type:"refresh_token",client_id:CFG.clientId,refresh_token:rt})});
    if(!r.ok) return false; const t=await r.json(); if(!t.id_token) return false;
    ID_TOKEN=t.id_token; sessionStorage.setItem("id_token",ID_TOKEN); return true;
  }catch(e){ return false; }
}
function logout(){ sessionStorage.clear();
  const u=new URL(hostedBase()+"/logout"); u.search=new URLSearchParams({client_id:CFG.clientId,logout_uri:redirectUri()}).toString();
  window.location=u.toString(); }
function claims(){ try{return JSON.parse(atob(ID_TOKEN.split('.')[1]));}catch(e){return {};} }
function isAdmin(){ const g=claims()["cognito:groups"]||[]; return (Array.isArray(g)?g:[g]).includes("admin"); }

/* ---------------- API ---------------- */
async function api(path, opts={}, _retried){
  const r=await fetch(API+path,{...opts,headers:{"Content-Type":"application/json","Authorization":"Bearer "+ID_TOKEN,...(opts.headers||{})}});
  if(r.status===401 && !_retried){
    // Token expirado: tenta renovar silenciosamente; se falhar, volta ao login.
    if(await refreshToken()) return api(path, opts, true);
    login(); throw new Error("Sessão expirada. Redirecionando para o login…");
  }
  const txt=await r.text(); const data=txt?JSON.parse(txt):{};
  if(!r.ok) throw new Error(data.message||("Erro "+r.status)); return data;
}
async function models(){ if(!MODELS){ try{ MODELS=(await api("/models")).models||[]; }catch(e){ MODELS=[]; } } return MODELS; }
const esc = s => String(s??"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const el = id => document.getElementById(id);
const h = html => { el("view").innerHTML = html; };
function toggleSide(force){
  const open = (force===undefined) ? !document.body.classList.contains("side-open") : force;
  document.body.classList.toggle("side-open", open);
}

/* ---------------- Upload assíncrono (fire-and-forget) ---------------- */
async function submitCorrection(type, file, options){
  const ext=(file.name.split('.').pop()||"png").toLowerCase();
  const s=await api("/submissions",{method:"POST",body:JSON.stringify({type,fileExt:ext,options})});
  await fetch(s.uploadUrl,{method:"PUT",headers:{"Content-Type":file.type||"application/octet-stream"},body:file});
  await api(`/submissions/${s.submissionId}/confirm`,{method:"POST"});
  return s.submissionId;
}

/* ---------------- Menu ---------------- */
const GROUPS = [
  ["Prova Discursiva", [["ex-corrige","Correção"],["ex-criar","Criação"],["ex-hist","Histórico"]]],
  ["Redação", [["red-rubrica","Rubricas"],["red-corrige","Correção"],["red-hist","Histórico"]]],
  ["Prova Objetiva", [["cartao-load","Carregar cartão"],["cartao-read","Ler cartão (OpenCV)"],["cartao-tpl","Templates"],["cartao-hist","Histórico"]]],
  ["Configuração", [["modelos","Modelos"]]],
  ["Analytics", [["analytics","Dados Analíticos"],["evaluation","Evaluation"]]],
];
function renderNav(active){
  el("nav").innerHTML = GROUPS.map(([g,items])=>`<div class="grp"><div class="gh">${g}</div>`+
    items.map(([k,t])=>`<a href="#${k}" class="${k===active?'active':''}">${t}</a>`).join("")+`</div>`).join("");
  const c=claims(); el("who").textContent=(c.email||"")+(isAdmin()?" · admin":" · professor");
}

/* ---------------- Correção (assíncrona) ---------------- */
async function viewCorrecao(type){
  const isEssay = type==="essay";
  const extra = isEssay
    ? `<label>Rubricas (uma ou mais)</label><select id="rubrics" multiple size="4"></select>`
    : `<label>Estratégia de correção</label>
       <select id="strategy" onchange="toggleGab()"><option value="model">Conhecimento do modelo</option><option value="gabarito">Gabarito</option></select>
       <div id="gabwrap" style="display:none"><label>Prova (gabarito)</label><select id="examId"><option value="">—</option></select></div>`;
  h(`<h2>Correção de ${isEssay?"Redação":"Prova Discursiva"}</h2>
     <div class="card">
       <label>Arquivo</label>
       <label class="filedrop">
         <input type="file" id="file" accept=".png,.jpg,.jpeg,.pdf" onchange="onFile(this)">
         <div id="fileprompt">📎 Clique para selecionar (PNG, JPG ou PDF)</div>
         <img id="preview" alt="pré-visualização">
         <div id="filename" class="muted"></div>
       </label>
       ${extra}
       <div style="margin-top:14px"><button id="btn" onclick="doSubmit('${type}')">Enviar para correção</button></div>
     </div><div id="out"></div>`);
  if(isEssay){ const r=await api("/rubrics");
    el("rubrics").innerHTML=(r.items||[]).map(x=>`<option value="${x.rubricId}" ${x.isDefault?"selected":""}>${esc(x.name)}</option>`).join(""); }
  else { const e=await api("/exams");
    el("examId").innerHTML='<option value="">—</option>'+(e.items||[]).map(x=>`<option value="${x.examId}">${esc(x.title||x.examId)}</option>`).join(""); toggleGab(); }
}
function toggleGab(){ const w=el("gabwrap"); if(w) w.style.display=(el("strategy").value==="gabarito")?"":"none"; }
function onFile(input){
  const f=input.files[0], img=el("preview"), fn=el("filename"), pr=el("fileprompt");
  if(!f){ img.style.display="none"; fn.textContent=""; pr.style.display=""; pr.textContent="📎 Clique para selecionar (PNG, JPG ou PDF)"; return; }
  fn.textContent=`${f.name} · ${Math.round(f.size/1024)} KB`;
  if((f.type||"").startsWith("image/")){ img.src=URL.createObjectURL(f); img.style.display="block"; pr.style.display="none"; }
  else { img.style.display="none"; pr.style.display=""; pr.textContent="📄 "+f.name; }
}
async function doSubmit(type){
  const f=el("file").files[0]; if(!f) return alert("Selecione um arquivo.");
  const options = type==="essay" ? {rubricIds:[...el("rubrics").selectedOptions].map(o=>o.value)}
    : (el("strategy").value==="gabarito" ? {strategy:"gabarito", examId:el("examId").value} : {strategy:"model"});
  if(type==="exam" && el("strategy").value==="gabarito" && !el("examId").value) return alert("Selecione a prova (gabarito).");
  el("btn").disabled=true; el("out").innerHTML='<div class="card muted">Enviando…</div>';
  try{
    const id=await submitCorrection(type,f,options);
    el("out").innerHTML=`<div class="card"><div class="toast">✅ Enviado para correção (assíncrona). O resultado aparece em
      <b>${type==="essay"?"Redação › Histórico":"Prova Discursiva › Histórico"}</b> quando concluir.</div>
      <p class="muted">Protocolo: ${id.slice(0,8)}</p>
      <button class="sec" onclick="location.hash='${type==="essay"?"red-hist":"ex-hist"}'">Ir para o Histórico</button></div>`;
  }catch(e){ el("out").innerHTML=`<div class="card danger">${esc(e.message)}</div>`; el("btn").disabled=false; }
}

/* ---------------- Histórico + detalhe ---------------- */
async function viewHistorico(type){
  h(`<h2>Histórico — ${type==="essay"?"Redação":"Prova Discursiva"}</h2><div class="card muted">Carregando…</div>`);
  const r=await api("/submissions"+(isAdmin()?"?all=true":""));
  const items=(r.items||[]).filter(s=>s.type===type).sort((a,b)=>(b.createdAt||"").localeCompare(a.createdAt||""));
  h(`<div class="hdr"><h2>Histórico — ${type==="essay"?"Redação":"Prova Discursiva"}</h2>
    <button class="sec" onclick="viewHistorico('${type}')">↻ Atualizar</button></div>
    <div class="card"><table><tr><th>Protocolo</th><th>ID_Exam</th><th>Status</th><th>Nota</th><th>Data</th></tr>
    ${items.length?items.map(s=>`<tr class="clk" onclick="viewDetail('${s.submissionId}','${type}')">
      <td>${s.submissionId.slice(0,8)}</td><td>${esc(s.idExam||"—")}</td><td><span class="pill ${s.status}">${s.status}</span></td>
      <td>${(s.result&&s.result.grade!=null)?s.result.grade:"—"}</td><td>${esc(s.createdAt||"")}</td></tr>`).join("")
      :'<tr><td colspan="5" class="muted">Nenhuma submissão ainda.</td></tr>'}</table>
    <p class="muted">Clique numa linha para ver o resultado completo. Atualiza ao recarregar.</p></div>`);
}
const fmt = v => (v==null?"—":v);
function thumbs(cur, onup, ondown){
  return `<span class="thumbs">
    <button class="thumb${cur==='up'?' up':''}" title="Correção/transcrição OK" onclick="${onup}">👍</button>
    <button class="thumb${cur==='down'?' down':''}" title="Correção/transcrição não OK" onclick="${ondown}">👎</button></span>`;
}
function footer(c, rubric){
  const tin=c.tokensIn||0, tout=c.tokensOut||0;
  const tk=(tin||tout)?` · tokens: ${tin+tout} (entrada ${tin} / saída ${tout})`:"";
  const rub=rubric?` · rubrica ${esc(rubric)}`:"";
  const rate=c.correctionId?`<div class="rateline"><span class="rate">Esta correção está OK?
    ${thumbs(c.rating,`rateCor('${c.correctionId}','up')`,`rateCor('${c.correctionId}','down')`)}</span></div>`:"";
  return `<div class="foot">Modelo: ${esc(c.modelUsed)}${c.isChallenger?" · challenger":""}${rub}${tk}</div>${rate}`;
}
function _findCor(cid){ for(const g of Object.values(_det.groups)){ const c=(g||[]).find(x=>x.correctionId===cid); if(c) return c; } return null; }
async function rateCor(cid, val){
  const c=_findCor(cid); if(!c) return; const nv=c.rating===val?"":val;
  try{ await api(`/corrections/${cid}/rating`,{method:"PUT",body:JSON.stringify({rating:nv})}); c.rating=nv; renderDetail(); }
  catch(e){ alert(e.message); }
}
async function rateTr(idx, val){
  const t=_det.trs.find(x=>(x.index!=null?x.index:_det.trs.indexOf(x))===idx); if(!t) return;
  const nv=t.rating===val?"":val;
  try{ await api(`/submissions/${_det.submissionId}/transcription-rating`,{method:"PUT",body:JSON.stringify({index:idx,rating:nv})}); t.rating=nv; renderDetail(); }
  catch(e){ alert(e.message); }
}
async function toggleImg(id){
  const box=el("imgbox"); if(!box) return;
  if(box.dataset.open==="1"){ box.dataset.open="0"; box.innerHTML=`<button class="sec" onclick="toggleImg('${id}')">🖼️ Ver imagem original</button>`; return; }
  box.innerHTML='<span class="muted">Carregando imagem…</span>';
  try{ const r=await api(`/submissions/${id}/image`); box.dataset.open="1";
    const media = r.ext==="pdf" ? `<a href="${r.url}" target="_blank">Abrir PDF original em nova aba</a>`
      : `<img src="${r.url}" style="max-width:100%;border-radius:8px;border:1px solid var(--line);margin-top:8px">`;
    box.innerHTML=`<button class="sec" onclick="toggleImg('${id}')">Ocultar imagem</button><div>${media}</div>`;
  }catch(e){ box.innerHTML=`<span class="danger">${esc(e.message)}</span> <button class="sec" onclick="toggleImg('${id}')">tentar de novo</button>`; }
}
let _det=null;
async function viewDetail(id, type){
  h('<div class="card muted">Carregando resultado…</div>');
  let d; try{ d=await api(`/submissions/${id}/corrections`); }catch(e){ return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const sub=d.submission||{};
  const back=`<button class="ghost" onclick="viewHistorico('${type}')">← Voltar</button>`;
  if(sub.status!=="DONE"){ return h(`${back}<h2>Resultado</h2><div class="card"><span class="pill ${sub.status}">${sub.status}</span>
    ${sub.status==="FAILED"?`<p class="danger">${esc(sub.errorMessage||"Falha")}</p>`:'<p class="muted">Ainda processando. Use ↻ Atualizar em instantes.</p>'}</div>`); }
  let title = type==="essay" ? "Redação" : "Prova Discursiva";
  const examId=(sub.options||{}).examId;
  if(type==="exam" && examId){ try{ const ex=await api("/exams/"+examId); if(ex && ex.title) title=ex.title; }catch(e){} }
  // Transcrições (novo formato lista; fallback para o formato antigo singular).
  let trs=(sub.result&&sub.result.transcriptions)||null;
  if(!trs){ const t=(sub.result&&sub.result.transcription)||{}; trs=[{index:0,model:((d.corrections||[])[0]||{}).transcriptionModel||"",result:t}]; }
  const groups={}; (d.corrections||[]).forEach(c=>{ const i=c.transcriptionIndex||0; (groups[i]=groups[i]||[]).push(c); });
  Object.values(groups).forEach(g=>g.sort((a,b)=>(a.isChallenger?1:0)-(b.isChallenger?1:0)));
  _det={id,type,title,submissionId:sub.submissionId,trs,groups,selTr:0,selCor:0,idExam:sub.idExam||""};
  renderDetail();
}
function mlabel(m){ return ((m||"").replace(/^(global|us|eu|apac)\./,"").replace(/-\d{8}-v\d+:\d+$/,"").replace(/-v\d+:\d+$/,"")) || m || "—"; }
function renderDetail(){
  const d=_det; const back=`<button class="ghost" onclick="viewHistorico('${d.type}')">← Voltar</button>`;
  const tr = d.trs[d.selTr] || d.trs[0];
  const trIdx = tr.index!=null?tr.index:d.selTr;
  const grp = (d.groups[trIdx] || d.groups[0] || []);
  const cor = grp[d.selCor] || grp[0];
  const trTabs = d.trs.length>1 ? `<div class="tabs">${d.trs.map((t,i)=>`<button class="tab ${i===d.selTr?'on':''}" onclick="selTr(${i})">Transcrição ${i+1} · ${esc(mlabel(t.model))}${t.isChallenger?"":" (oficial)"}</button>`).join("")}</div>`:"";
  const corTabs = grp.length>1 ? `<div class="tabs">${grp.map((c,i)=>`<button class="tab ${i===d.selCor?'on':''}" onclick="selCor(${i})">Correção ${i+1} · ${esc(mlabel(c.modelUsed))}</button>`).join("")}</div>`:"";
  const trRate=`<div class="rateline"><span class="rate">Esta transcrição${d.trs.length>1?" "+(d.selTr+1):""} está OK?
    ${thumbs(tr.rating,`rateTr(${trIdx},'up')`,`rateTr(${trIdx},'down')`)}</span></div>`;
  const transcCard = d.type==="essay"
    ? `<div class="card"><h3>Transcrição</h3><p class="muted" style="white-space:pre-wrap">${esc((tr.result||{}).text||"")}</p>${trRate}</div>`
    : `<div class="card"><h3>Transcrição ${d.trs.length>1?"("+(d.selTr+1)+")":""}</h3>
       <p class="muted">A transcrição por questão aparece dentro da correção abaixo.</p>${trRate}</div>`;
  const corCard = cor ? (d.type==="essay"?renderEssayCard(cor):renderExamCard(cor, tr.result||{})) : '<div class="card muted">Sem correção para esta transcrição.</div>';
  h(`${back}<h2>${esc(d.title)}</h2>
     <div class="card" id="imgbox">${d.idExam?`<p class="muted">ID_Exam: <b>${esc(d.idExam)}</b></p>`:""}<button class="sec" onclick="toggleImg('${d.submissionId}')">🖼️ Ver imagem original</button></div>
     ${d.trs.length>1?'<p class="muted">Escolha a transcrição e, dentro dela, a correção do modelo desejado.</p>':""}
     ${trTabs}${transcCard}${corTabs}${corCard}`);
}
function selTr(i){ _det.selTr=i; _det.selCor=0; renderDetail(); }
function selCor(i){ _det.selCor=i; renderDetail(); }
function renderEssayCard(c){ const r=c.result||{}; return `<div class="card">
  <h3>Nota total: ${fmt(r.totalScore)}</h3>
  ${(r.criteria||[]).map(cr=>`<div class="crit"><span class="score">${fmt(cr.score)}/${fmt(cr.maxScore)}</span>
    <b>${esc(cr.name)}</b><div class="muted" style="white-space:pre-wrap">${esc(cr.feedback||"")}</div></div>`).join("")}
  ${r.feedback?`<p class="muted"><b>Comentário geral:</b> ${esc(r.feedback)}</p>`:""}
  ${footer(c, c.rubricId)}</div>`; }
function renderExamCard(c, transc){ const r=c.result||{}; const tq=transc.transcricao||[]; return `<div class="card">
  <h3>Nota total: ${fmt(r.notaTotal)}</h3>
  ${(r.questoes||[]).map((q,i)=>{ const t=tq[i]||{}; return `<div class="crit">
    <span class="score">${fmt(q.nota)}/${fmt(q.notaMaxima)}</span><b>Questão ${i+1}</b>
    ${t.question?`<div class="qtext">${esc(t.question)}</div>`:""}
    <div class="ansl">Resposta transcrita</div><div class="muted" style="white-space:pre-wrap">${esc(t.resposta||"—")}</div>
    <hr class="sep">
    <div class="ansl">Comentário</div><div class="muted" style="white-space:pre-wrap">${esc(q.justificativa||"")}</div></div>`;}).join("")}
  ${footer(c)}</div>`; }

/* ---------------- Criação de prova ---------------- */
function viewCriar(){
  h(`<h2>Criação de Prova Discursiva</h2><div class="card"><label>Título</label><input id="title">
    <div id="questions"></div><div style="margin-top:10px"><button class="sec" onclick="addQuestion()">+ Questão</button>
    <button onclick="saveExam()">Salvar prova</button></div></div><div id="out"></div>`);
  addQuestion();
}
function addQuestion(){
  const d=document.createElement("div"); d.className="card"; d.innerHTML=
   `<label>Enunciado</label><textarea class="q-prompt"></textarea>
    <label>Resposta de referência</label><textarea class="q-answer"></textarea>
    <div class="row"><div><label>Nota máxima</label><input class="q-max" type="number" value="10"></div>
    <div style="flex:none;align-self:flex-end"><button class="sec" onclick="wizard(this)">✨ Sugerir resposta</button></div></div>`;
  el("questions").appendChild(d);
}
async function wizard(btn){
  const card=btn.closest(".card"); const q=card.querySelector(".q-prompt").value.trim();
  if(!q) return alert("Escreva o enunciado primeiro."); btn.disabled=true; btn.textContent="Gerando…";
  try{ const r=await api("/exams/new/suggest-answer",{method:"POST",body:JSON.stringify({question:q})});
       card.querySelector(".q-answer").value=r.resposta||""; }
  catch(e){ alert(e.message); } finally{ btn.disabled=false; btn.textContent="✨ Sugerir resposta"; }
}
async function saveExam(){
  const questions=[...document.querySelectorAll("#questions .card")].map(c=>({
    prompt:c.querySelector(".q-prompt").value, referenceAnswer:c.querySelector(".q-answer").value,
    maxScore:Number(c.querySelector(".q-max").value)||10}));
  try{ await api("/exams",{method:"POST",body:JSON.stringify({title:el("title").value,questions,status:"active"})});
       el("out").innerHTML='<div class="card toast">Prova salva.</div>'; }
  catch(e){ el("out").innerHTML=`<div class="card danger">${esc(e.message)}</div>`; }
}

/* ---------------- Rubricas (CRUD) ---------------- */
async function viewRubricas(){
  h('<h2>Rubricas de Redação</h2><div class="card muted">Carregando…</div>');
  const r=await api("/rubrics");
  h(`<h2>Rubricas de Redação</h2>
    <div style="margin-bottom:12px"><button onclick="rubricEditor()">+ Nova rubrica</button></div>
    <div class="card"><table><tr><th>Nome</th><th>Versão</th><th>Total</th><th>Padrão</th><th></th></tr>
    ${(r.items||[]).map(x=>`<tr><td>${esc(x.name)}</td><td>${x.version}</td><td>${x.totalMaxScore||sumMax(x.criteria)}</td>
      <td>${x.isDefault?"✓":""}</td><td><button class="ghost" onclick='rubricEditor(${JSON.stringify(x).replace(/'/g,"&#39;")})'>Editar</button></td></tr>`).join("")}
    </table></div>`);
}
const sumMax = crit => (crit||[]).reduce((a,c)=>a+(Number(c.maxScore)||0),0);
function rubricEditor(rub){
  rub = rub || {name:"",criteria:[{name:"",maxScore:200,description:""}],isDefault:false};
  const rows = (rub.criteria||[]).map(c=>critRow(c)).join("");
  h(`<button class="ghost" onclick="viewRubricas()">← Voltar</button>
     <h2>${rub.rubricId?"Editar":"Nova"} rubrica</h2>
     <div class="card"><label>Nome</label><input id="r-name" value="${esc(rub.name)}">
     <label><input type="checkbox" id="r-default" ${rub.isDefault?"checked":""} style="width:auto"> Rubrica padrão</label>
     <h3>Critérios</h3><div id="crits">${rows}</div>
     <button class="sec" onclick="addCrit()">+ Critério</button>
     <div style="margin-top:12px"><button onclick="saveRubric('${rub.rubricId||""}')">Salvar</button>
     <span class="muted" id="r-total"></span></div></div><div id="out"></div>`);
  updTotal();
}
function critRow(c){ return `<div class="crit critrow"><div class="row">
  <div style="flex:2"><label>Nome</label><input class="c-name" value="${esc(c.name||"")}"></div>
  <div style="flex:none;width:110px"><label>Nota máx.</label><input class="c-max" type="number" value="${c.maxScore||0}" oninput="updTotal()"></div>
  <div style="flex:none;align-self:flex-end"><button class="ghost danger" onclick="this.closest('.critrow').remove();updTotal()">✕</button></div></div>
  <label>Descrição</label><textarea class="c-desc">${esc(c.description||"")}</textarea></div>`; }
function addCrit(){ const d=document.createElement("div"); d.innerHTML=critRow({maxScore:0}); el("crits").appendChild(d.firstChild); updTotal(); }
function updTotal(){ const t=[...document.querySelectorAll(".c-max")].reduce((a,i)=>a+(Number(i.value)||0),0);
  if(el("r-total")) el("r-total").textContent=` Total: ${t} pontos`; }
async function saveRubric(id){
  const criteria=[...document.querySelectorAll("#crits .critrow")].map(row=>({
    name:row.querySelector(".c-name").value, maxScore:Number(row.querySelector(".c-max").value)||0,
    description:row.querySelector(".c-desc").value}));
  const body={name:el("r-name").value, isDefault:el("r-default").checked, status:"active",
    criteria, totalMaxScore:criteria.reduce((a,c)=>a+c.maxScore,0)};
  try{
    if(id) await api("/rubrics/"+id,{method:"PUT",body:JSON.stringify(body)});
    else await api("/rubrics",{method:"POST",body:JSON.stringify(body)});
    viewRubricas();
  }catch(e){ el("out").innerHTML=`<div class="card danger">${esc(e.message)}</div>`; }
}

/* ---------------- Configuração de Modelos ---------------- */
let _priceModels=[];
async function viewModelos(){
  h('<h2>Configuração de Modelos</h2><div class="card muted">Carregando…</div>');
  const [mc, ms, pr] = await Promise.all([api("/model-config"), models(), api("/pricing")]);
  const prices=(pr&&pr.prices)||{};
  const opt = sel => `<option value="">—</option>`+ms.map(m=>`<option value="${m.id}" ${m.id===sel?"selected":""}>${esc(m.label)} ${m.kind==="profile"?"·perfil":""}</option>`).join("")
    + (sel && !ms.some(m=>m.id===sel)?`<option value="${sel}" selected>${esc(sel)} (atual)</option>`:"");
  const MODES=[["single","Desligado (usar só o primário)"],["ab","A/B — usar UMA ou OUTRA por %"],["both","Ambos — rodar as duas e comparar"]];
  const radios=(cap,cur)=>`<div class="radios">${MODES.map(([v,t])=>
    `<label class="rb"><input type="radio" name="m-${cap}" value="${v}" ${(cur||'single')===v?'checked':''} onchange="updModeUI('${cap}')"> ${t}</label>`).join("")}</div>`;
  const nice={transcription:"Transcrição (leitura da imagem)",essay:"Correção de Redação",exam:"Correção de Prova",author:"Wizard de Resposta",answersheet:"Leitura de Cartão Resposta"};
  const used=[...new Set((mc.items||[]).flatMap(c=>[c.primaryModel,c.challengerModel]).filter(Boolean))];
  _priceModels=used;
  h(`<h2>Configuração de Modelos</h2>
    <p class="muted">${ms.length} modelos multimodais (·perfil = inference profile, recomendado).
    A <b>Transcrição</b> lê a imagem/PDF e extrai o texto antes da correção.</p>
    ${(mc.items||[]).map(c=>{const mode=c.mode||'single';return `<div class="card"><h3>${nice[c.capability]||c.capability}</h3>
      <label>Modelo primário</label><select id="p-${c.capability}">${opt(c.primaryModel)}</select>
      <label>Segundo modelo</label>${radios(c.capability,mode)}
      <div id="chal-${c.capability}" style="display:${mode==='single'?'none':''}">
        <label>Segundo modelo (challenger)</label><select id="c-${c.capability}">${opt(c.challengerModel)}</select></div>
      <div id="pct-${c.capability}" style="display:${mode==='ab'?'':'none'};max-width:200px">
        <label>% para o 2º modelo (A/B)</label><input id="ab-${c.capability}" type="number" min="0" max="100" value="${(c.abPolicy&&c.abPolicy.percent)||0}"></div>
      ${isAdmin()?`<div style="margin-top:10px"><button onclick="saveModel('${c.capability}')">Salvar</button></div>`:'<p class="muted">Somente admin edita.</p>'}
      </div>`;}).join("")}
    <div class="card"><h3>Preços por modelo (US$ por 1k tokens)</h3>
      <p class="muted">Cada modelo tem preço próprio. Preencha entrada/saída dos modelos que usa; vazio = estimativa por família.</p>
      ${used.length?`<table><tr><th>Modelo</th><th class="num">Entrada /1k</th><th class="num">Saída /1k</th></tr>
        ${used.map((m,i)=>`<tr><td>${esc(m)}</td>
          <td class="num"><input id="pin-${i}" type="number" step="0.0001" style="width:120px" value="${(prices[m]&&prices[m].in)??''}"></td>
          <td class="num"><input id="pout-${i}" type="number" step="0.0001" style="width:120px" value="${(prices[m]&&prices[m].out)??''}"></td></tr>`).join("")}</table>
        ${isAdmin()?`<div style="margin-top:10px"><button onclick="savePrices()">Salvar preços</button></div>`:''}`
        :'<p class="muted">Configure os modelos acima primeiro.</p>'}</div>
    <p class="muted"><b>A/B</b>: cada prova vai para um modelo só (sorteado pela %); compare no agregado (Analytics).
    <b>Ambos</b>: roda os dois em toda prova — no histórico você alterna entre as correções de cada modelo.</p>
    <div id="out"></div>`);
}
function updModeUI(cap){
  const mode=(document.querySelector(`input[name="m-${cap}"]:checked`)||{}).value||"single";
  const ch=el("chal-"+cap), pc=el("pct-"+cap);
  if(ch) ch.style.display = mode==="single"?"none":"";
  if(pc) pc.style.display = mode==="ab"?"":"none";
}
async function saveModel(cap){
  const mode=(document.querySelector(`input[name="m-${cap}"]:checked`)||{}).value||"single";
  try{ await api("/model-config/"+cap,{method:"PUT",body:JSON.stringify({
    primaryModel:el("p-"+cap).value, challengerModel:(el("c-"+cap)||{}).value||"", mode,
    abPolicy:{percent:Number((el("ab-"+cap)||{}).value)||0}})}); el("out").innerHTML='<div class="card toast">Salvo.</div>'; }
  catch(e){ el("out").innerHTML=`<div class="card danger">${esc(e.message)}</div>`; }
}
async function savePrices(){
  const prices={};
  _priceModels.forEach((m,i)=>{ const vi=el("pin-"+i).value, vo=el("pout-"+i).value;
    if(vi!==""||vo!==""){ prices[m]={in:Number(vi)||0, out:Number(vo)||0}; }});
  try{ await api("/pricing",{method:"PUT",body:JSON.stringify({prices})}); el("out").innerHTML='<div class="card toast">Preços salvos.</div>'; }
  catch(e){ el("out").innerHTML=`<div class="card danger">${esc(e.message)}</div>`; }
}

/* ---------------- Analytics (gráficos) ---------------- */
function bars(title, data){
  const max=Math.max(1,...data.map(d=>d[1]));
  return `<div class="card"><h3>${title}</h3>${data.length?data.map(([l,v])=>`<div class="barrow">
    <span class="barlabel">${esc(l)}</span><span class="bar"><span class="barfill" style="width:${(v/max*100).toFixed(1)}%"></span></span>
    <span class="barval">${v}</span></div>`).join(""):'<p class="muted">Sem dados.</p>'}</div>`;
}
function modelTable(title, obj, money){
  const rows=Object.entries(obj||{});
  const f=v=> money?("$ "+Number(v||0).toFixed(4)):(v||0);
  return `<div class="card"><h3>${title}</h3>${rows.length?`<table>
    <tr><th>Modelo</th><th class="num">Entrada</th><th class="num">Saída</th><th class="num">Total</th></tr>
    ${rows.map(([m,v])=>`<tr><td>${esc(m)}</td><td class="num">${f(v.in)}</td><td class="num">${f(v.out)}</td><td class="num">${f(v.total)}</td></tr>`).join("")}</table>`
    :'<p class="muted">Sem dados.</p>'}</div>`;
}
async function viewAnalytics(){
  h('<h2>Dados Analíticos</h2><div class="card muted">Carregando…</div>');
  const a=await api("/analytics"); const s=a.submissions||{}; const g=a.grades||{};
  const money=v=> v!=null?("$ "+Number(v).toFixed(4)):"—";
  const kpi=(l,v)=>`<div class="kpi"><span class="muted">${l}</span><b>${v??"—"}</b></div>`;
  h(`<h2>Dados Analíticos</h2>
    <div class="card"><div class="kpis">
      ${kpi("Submissões",s.total||0)}
      ${kpi("Média redação",(g.essay&&g.essay.avg)??"—")}
      ${kpi("Média prova",(g.exam&&g.exam.avg)??"—")}
      ${kpi("Tokens (total)",(a.tokens&&a.tokens.total)??"—")}
      ${kpi("Custo total",money(a.cost&&a.cost.total))}
    </div>
    <p class="muted">Tokens: entrada ${(a.tokens&&a.tokens.in)||0} / saída ${(a.tokens&&a.tokens.out)||0}.
    Custo: entrada ${money(a.cost&&a.cost.in)} / saída ${money(a.cost&&a.cost.out)} (estimativa).</p></div>
    ${bars("Submissões por status", Object.entries(s.byStatus||{}))}
    ${bars("Submissões por tipo", Object.entries(s.byType||{}))}
    ${bars("Distribuição de notas — Redação", Object.entries(g.essayHistogram||{}))}
    ${bars("Correções por modelo", Object.entries(a.byModel||{}))}
    ${modelTable("Tokens por modelo (entrada / saída / total)", a.tokensByModel, false)}
    ${modelTable("Custo por modelo — US$ (entrada / saída / total)", a.costByModel, true)}`);
}

/* ---------------- Cartão Resposta — Carregar (servidor, assíncrono) ---------------- */
async function viewCartaoLoad(){
  h(`<h2>Carregar cartão (leitura no servidor)</h2><div class="card muted">Carregando…</div>`);
  let tpls=[]; try{ tpls=(await api("/card-templates")).items||[]; }catch(e){}
  const withRef=tpls.filter(t=>t.hasReference);
  const tplOpts=withRef.length?withRef.map(t=>`<option value="${t.templateId}">${esc(t.name)} · ${t.totalQuestions}q</option>`).join("")
    :'<option value="">— nenhum template com referência —</option>';
  h(`<h2>Carregar cartão (leitura no servidor · OMR)</h2>
     <div class="card">
       <label>Template (obrigatório)</label>
       <select id="tpl">${tplOpts}</select>
       <label>Arquivos do cartão (pode selecionar vários para lote)</label>
       <label class="filedrop">
         <input type="file" id="file" accept=".png,.jpg,.jpeg" multiple onchange="onFileMulti(this)">
         <div id="fileprompt">📎 Clique para selecionar 1 ou mais imagens (PNG/JPG)</div>
         <div id="filename" class="muted"></div>
       </label>
       <p class="muted">Leitura <b>determinística no servidor</b> (OpenCV): alinha cada foto à referência do template
       (posição/rotação/zoom) e lê as marcações — escala para <b>upload em massa</b>. O resultado aparece em <b>Histórico</b>.</p>
       ${withRef.length?"":'<p class="danger">Nenhum template com imagem de referência. Crie/edite um template em <b>Templates</b> e salve com a imagem do cartão.</p>'}
       <div style="margin-top:14px"><button id="btn" onclick="doSubmitCartao()" ${withRef.length?"":"disabled"}>Enviar para leitura</button></div>
     </div><div id="out"></div>`);
}
function onFileMulti(input){ const n=input.files.length; const fn=el("filename");
  if(fn) fn.textContent = n? (n===1? input.files[0].name : n+" arquivos selecionados") : ""; }
async function doSubmitCartao(){
  const files=[...el("file").files]; if(!files.length) return alert("Selecione ao menos um arquivo.");
  const t=el("tpl"); if(!t || !t.value) return alert("Selecione um template.");
  const opts={templateId:t.value};
  el("btn").disabled=true;
  const ids=[]; let done=0, fail=0;
  const prog=()=>{ el("out").innerHTML=`<div class="card muted">Enviando ${done+fail} de ${files.length}… (${fail} falha(s))</div>`; };
  prog();
  for(const f of files){
    try{ ids.push(await submitCorrection("answersheet", f, opts)); done++; }
    catch(e){ fail++; }
    prog();
  }
  el("out").innerHTML=`<div class="card"><div class="toast">✅ ${done} cartão(ões) enviado(s) para leitura no servidor${fail?` · ${fail} falha(s)`:""}.
    Os resultados aparecem em <b>Prova Objetiva › Histórico</b> conforme concluem.</div>
    <button class="sec" onclick="location.hash='cartao-hist'">Ir para o Histórico</button></div>`;
  el("btn").disabled=false;
}
async function viewCartaoHist(){
  h(`<h2>Histórico — Cartão Resposta</h2><div class="card muted">Carregando…</div>`);
  const r=await api("/submissions"+(isAdmin()?"?all=true":""));
  const items=(r.items||[]).filter(s=>s.type==="answersheet").sort((a,b)=>(b.createdAt||"").localeCompare(a.createdAt||""));
  const nmarks=s=>{ const rd=((s.result||{}).readings||[])[0]; return rd?(rd.answers||[]).length:"—"; };
  h(`<div class="hdr"><h2>Histórico — Cartão Resposta</h2>
    <button class="sec" onclick="viewCartaoHist()">↻ Atualizar</button></div>
    <div class="card"><table><tr><th>Protocolo</th><th>ID_Exam</th><th>Status</th><th>Questões lidas</th><th>Data</th></tr>
    ${items.length?items.map(s=>`<tr class="clk" onclick="viewCartaoDetail('${s.submissionId}')">
      <td>${s.submissionId.slice(0,8)}</td><td>${esc(s.idExam||"—")}</td><td><span class="pill ${s.status}">${s.status}</span></td>
      <td>${nmarks(s)}</td><td>${esc(s.createdAt||"")}</td></tr>`).join("")
      :'<tr><td colspan="5" class="muted">Nenhum cartão enviado ainda.</td></tr>'}</table>
    <p class="muted">Clique numa linha para ver as marcações e a imagem.</p></div>`);
}
let _cart=null;
async function viewCartaoDetail(id){
  h('<div class="card muted">Carregando…</div>');
  let s; try{ s=await api(`/submissions/${id}`); }catch(e){ return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const back=`<button class="ghost" onclick="viewCartaoHist()">← Voltar</button>`;
  if(s.status!=="DONE"){ return h(`${back}<h2>Cartão Resposta</h2><div class="card"><span class="pill ${s.status}">${s.status}</span>
    ${s.status==="FAILED"?`<p class="danger">${esc(s.errorMessage||"Falha")}</p>`:'<p class="muted">Ainda processando. Use ↻ Atualizar em instantes.</p>'}</div>`); }
  _cart={id, readings:((s.result||{}).readings)||[], sel:0, idExam:s.idExam||""};
  renderCartao();
}
function markLabel(a){ const m=(typeof a==="string")?a:(a&&a.marcada);
  if(m==="-") return '<span style="color:var(--bad);font-weight:600">em branco</span>';
  if(m==="*"){ const ms=(a&&a.marcadas&&a.marcadas.length)?(": "+a.marcadas.map(esc).join(", ")):"";
    return `<span style="color:var(--warn);font-weight:600">⚠ múltiplas${ms}</span>`; }
  return `<b>${esc(m)}</b>`; }
function renderCartao(){
  const c=_cart; const rd=c.readings[c.sel]||c.readings[0]||{answers:[]};
  const back=`<button class="ghost" onclick="viewCartaoHist()">← Voltar</button>`;
  const tabs=c.readings.length>1?`<div class="tabs">${c.readings.map((r,i)=>`<button class="tab ${i===c.sel?'on':''}" onclick="selCart(${i})">Leitura ${i+1} · ${esc(mlabel(r.model))}</button>`).join("")}</div>`:"";
  const ans=rd.answers||[];
  const grid=ans.length?`<table><tr><th>Questão</th><th>Alternativa marcada</th></tr>
    ${ans.map(a=>`<tr style="${a.marcada==='*'?'background:#3a2e08':(a.marcada==='-'?'background:#3f1212':'')}"><td>${esc(a.questao)}</td><td>${markLabel(a)}</td></tr>`).join("")}</table>`
    :'<p class="muted">Nenhuma marcação identificada.</p>';
  const foot=(rd.tokensIn||rd.tokensOut)?`<div class="foot">Modelo: ${esc(mlabel(rd.model))} · tokens: ${(rd.tokensIn||0)+(rd.tokensOut||0)}</div>`:"";
  const idline=c.idExam?`<p class="muted">ID_Exam: <b>${esc(c.idExam)}</b></p>`:"";
  h(`${back}<h2>Cartão Resposta</h2>
     <div class="card" id="imgbox">${idline}<button class="sec" onclick="toggleImg('${c.id}')">🖼️ Ver imagem do cartão</button></div>
     ${c.readings.length>1?'<p class="muted">Leituras de modelos diferentes (modo Ambos). Escolha para comparar.</p>':""}
     ${tabs}
     <div class="card"><h3>Alternativas marcadas</h3>${grid}${foot}</div>`);
}
function selCart(i){ _cart.sel=i; renderCartao(); }

/* ---------------- Cartão — Templates (editor visual) ---------------- */
let _tpl=null, _tplImg=null, _tplDraw=null, _drag=null, _tplSel=-1, _tplEdit=null;
async function viewCartaoTemplates(){
  h(`<div class="hdr"><h2>Templates de Cartão</h2></div><div class="card muted">Carregando…</div>`);
  let items=[]; try{ items=(await api("/card-templates")).items||[]; }catch(e){ return h(`<div class="card danger">${esc(e.message)}</div>`); }
  h(`<div class="hdr"><h2>Templates de Cartão</h2><button onclick="tplEditor()">+ Novo template</button></div>
     <div class="card"><table><tr><th>Nome</th><th>Questões</th><th>Alt.</th><th>Blocos</th><th></th></tr>
     ${items.length?items.map(t=>`<tr><td>${esc(t.name)}</td><td>${t.totalQuestions}</td><td>${t.alternatives}</td><td>${(t.blocks||[]).length}</td>
       <td><button class="ghost" onclick='tplEditor(${JSON.stringify(t).replace(/'/g,"&#39;")})'>Editar</button>
       ${isAdmin()?`<button class="ghost danger" onclick="tplDelete('${t.templateId}')">✕</button>`:""}</td></tr>`).join("")
       :'<tr><td colspan="5" class="muted">Nenhum template ainda.</td></tr>'}</table>
     <p class="muted">O template define onde ficam as bolhas (blocos) e quantas questões/alternativas — usado na leitura com OpenCV.</p></div>`);
}
async function tplDelete(id){ if(!confirm("Excluir este template?")) return;
  try{ await api("/card-templates/"+id,{method:"DELETE"}); viewCartaoTemplates(); }catch(e){ alert(e.message); } }
function tplEditor(t){
  t = t || {name:"",alternatives:5,blocks:[]};
  _tpl={templateId:t.templateId||"",name:t.name||"",alternatives:t.alternatives||5,sensitivity:t.sensitivity||50,
        blocks:(t.blocks||[]).map(b=>({firstQuestion:b.firstQuestion,questions:b.questions,alternatives:b.alternatives||t.alternatives||5,rect:{...b.rect}}))};
  _tplImg=null; _tplDraw=null; _drag=null; _tplSel=-1; _tplEdit=null;
  h(`<button class="ghost" onclick="viewCartaoTemplates()">← Voltar</button>
     <h2>${_tpl.templateId?"Editar":"Novo"} template</h2>
     <div class="card">
       <div class="row"><div><label>Nome</label><input id="t-name" value="${esc(_tpl.name)}"></div>
         <div style="flex:none;width:150px"><label>Alternativas (padrão)</label><input id="t-alt" type="number" min="2" max="10" value="${_tpl.alternatives}" onchange="if(el('b-alt'))el('b-alt').value=this.value; tplDrawCanvas()"></div>
         <div style="flex:none;width:160px"><label>Sensibilidade (%)</label><input id="t-sens" type="number" min="5" max="95" value="${_tpl.sensitivity||50}"></div></div>
       <p class="muted" style="margin-top:-4px">Sensibilidade = limiar de preenchimento usado na leitura (OpenCV). Menor = detecta marcas mais fracas.</p>
       <label>Imagem-demo do cartão (para medir — de preferência em branco)</label>
       <label class="filedrop" style="padding:16px">
         <input type="file" accept="image/*" onchange="tplLoadImg(this)">
         <div id="t-fileprompt">📎 Selecionar imagem-demo do cartão</div>
         <div id="t-filename" class="muted"></div>
       </label>
       <div class="row" style="margin-top:6px">
         <div style="flex:none"><button class="sec" onclick="tplWizard()">✨ Detectar blocos (wizard)</button></div>
       </div>
       <div id="t-msg" class="muted" style="margin-top:8px;min-height:18px"></div>
       <div style="overflow:auto;border:1px solid var(--line);border-radius:8px;margin-top:8px;background:#0b1020">
         <canvas id="t-canvas" style="display:block;max-width:100%;touch-action:none"
           onpointerdown="tplDown(event)" onpointermove="tplMove(event)" onpointerup="tplUp(event)"></canvas></div>
       <h3>Adicionar bloco manualmente</h3>
       <p class="muted">Informe a 1ª questão e o nº de questões, clique em <b>desenhar</b> e <b>arraste</b> sobre a área das bolhas (só as bolhas A–${String.fromCharCode(64+(_tpl.alternatives||5))}, sem o número da questão).</p>
       <div class="row"><div style="flex:none;width:110px"><label>1ª questão</label><input id="b-first" type="number" min="1" value="1"></div>
         <div style="flex:none;width:120px"><label>Nº de questões</label><input id="b-qs" type="number" min="1" value="15"></div>
         <div style="flex:none;width:130px"><label>Nº de alternativas</label><input id="b-alt" type="number" min="2" max="10" value="${_tpl.alternatives}"></div>
         <div style="flex:none;align-self:flex-end"><button class="sec" id="b-draw" onclick="tplStartBlock()">+ Adicionar bloco (desenhar)</button></div></div>
       <div id="b-list"></div>
       <div style="margin-top:14px"><button onclick="tplSave()">Salvar template</button></div>
     </div>`);
  tplDrawCanvas(); tplRenderList();
  // ao editar, carrega a imagem de referência (S3) para mostrar os blocos sobre ela
  if(_tpl.templateId){ api("/card-templates/"+_tpl.templateId+"/reference").then(r=>{
    if(r && r.url){ const im=new Image(); im.crossOrigin="anonymous"; im.onload=()=>{ _tplImg=im; tplDrawCanvas(); }; im.src=r.url; } }).catch(()=>{}); }
}
function tplLoadImg(input){ const f=input.files[0]; if(!f) return;
  const pr=el("t-fileprompt"), fn=el("t-filename");
  if(pr) pr.textContent="🖼️ "+f.name; if(fn) fn.textContent="Imagem carregada — desenhe os blocos ou use o wizard.";
  const img=new Image(); img.onload=()=>{ _tplImg=img; tplDrawCanvas(); }; img.src=URL.createObjectURL(f); }
function tplCanvasSize(){ const cv=el("t-canvas"); const maxW=Math.min(900,(cv.parentElement.clientWidth||900)-2);
  if(_tplImg){ const s=Math.min(1,maxW/_tplImg.width); cv.width=Math.round(_tplImg.width*s); cv.height=Math.round(_tplImg.height*s); }
  else { cv.width=Math.min(maxW,480); cv.height=Math.round(cv.width*1.3); } }
function tplDrawCanvas(){ const cv=el("t-canvas"); if(!cv) return; tplCanvasSize();
  const ctx=cv.getContext("2d"); ctx.clearRect(0,0,cv.width,cv.height);
  if(_tplImg){ ctx.drawImage(_tplImg,0,0,cv.width,cv.height); }
  else { ctx.fillStyle="#334155"; ctx.font="14px sans-serif"; ctx.textAlign="center";
    ctx.fillText("Carregue a imagem-demo do cartão acima", cv.width/2, cv.height/2); ctx.textAlign="left"; }
  const defAlt=Number((el("t-alt")||{}).value)||_tpl.alternatives||5;
  _tpl.blocks.forEach((b,idx)=>{ const alt=b.alternatives||defAlt;
    const x=b.rect.x*cv.width,y=b.rect.y*cv.height,w=b.rect.w*cv.width,hh=b.rect.h*cv.height;
    const sel=idx===_tplSel;
    ctx.strokeStyle=sel?"#f59e0b":"#22d3ee"; ctx.lineWidth=sel?3:2; ctx.strokeRect(x,y,w,hh);
    ctx.fillStyle=sel?"#f59e0b":"#22d3ee"; ctx.font="12px sans-serif"; ctx.fillText("#"+(idx+1)+" Q"+b.firstQuestion+" ("+alt+" alt)", x+2, y>12?y-3:y+12);
    ctx.fillStyle="rgba(34,197,94,0.95)";
    for(let r=0;r<b.questions;r++) for(let c=0;c<alt;c++){
      const cx=x+w*(c+0.5)/alt, cy=y+hh*(r+0.5)/b.questions;
      ctx.beginPath(); ctx.arc(cx,cy,2.2,0,7); ctx.fill(); }
    if(sel){ ctx.fillStyle="#fbbf24"; const H=_handles(b,cv);
      for(const k in H){ ctx.fillRect(H[k][0]-4,H[k][1]-4,8,8); } } }); }
function tplStartBlock(){
  if(!_tplImg){ alert("Carregue a imagem-demo do cartão primeiro."); return; }
  if(_tplDraw){ _tplDraw=null; tplSyncDrawBtn(); el("t-msg").textContent="Desenho cancelado."; return; }
  const first=Number(el("b-first").value)||1, qs=Number(el("b-qs").value)||1, alt=Number(el("b-alt").value)||5;
  _tplDraw={first,qs,alt}; tplSyncDrawBtn();
  el("t-msg").innerHTML=`<b style="color:var(--warn)">Modo desenho ativo:</b> arraste sobre as bolhas do bloco (Q${first}–${first+qs-1}, ${alt} alternativas).`; }
function tplSyncDrawBtn(){ const b=el("b-draw"); if(!b) return;
  b.textContent=_tplDraw?"✏️ Desenhando… (clique p/ cancelar)":"+ Adicionar bloco (desenhar)";
  b.classList.toggle("btnon", !!_tplDraw); }
function tplPt(ev){ const cv=el("t-canvas"); const r=cv.getBoundingClientRect();
  const sx=cv.width/r.width, sy=cv.height/r.height;
  return {x:Math.max(0,Math.min(cv.width,(ev.clientX-r.left)*sx)), y:Math.max(0,Math.min(cv.height,(ev.clientY-r.top)*sy))}; }
function _pxRect(b,cv){ return {x:b.rect.x*cv.width,y:b.rect.y*cv.height,w:b.rect.w*cv.width,h:b.rect.h*cv.height}; }
function _handles(b,cv){ const r=_pxRect(b,cv);
  return {nw:[r.x,r.y],n:[r.x+r.w/2,r.y],ne:[r.x+r.w,r.y],e:[r.x+r.w,r.y+r.h/2],
          se:[r.x+r.w,r.y+r.h],s:[r.x+r.w/2,r.y+r.h],sw:[r.x,r.y+r.h],w:[r.x,r.y+r.h/2]}; }
function _hitHandle(b,cv,px,py){ const H=_handles(b,cv), tol=10;
  for(const k in H){ if(Math.abs(px-H[k][0])<=tol && Math.abs(py-H[k][1])<=tol) return k; } return null; }
function _hitBlock(px,py,cv){ for(let i=_tpl.blocks.length-1;i>=0;i--){ const r=_pxRect(_tpl.blocks[i],cv);
  if(px>=r.x&&px<=r.x+r.w&&py>=r.y&&py<=r.y+r.h) return i; } return -1; }
function tplDown(ev){ const cv=el("t-canvas"); const p=tplPt(ev); ev.preventDefault();
  if(_tplDraw){ _drag={x0:p.x,y0:p.y,x1:p.x,y1:p.y}; return; }   // desenhando bloco novo
  // seleção / mover / redimensionar
  if(_tplSel>=0){ const hk=_hitHandle(_tpl.blocks[_tplSel],cv,p.x,p.y);
    if(hk){ _tplEdit={mode:"resize",handle:hk,rect0:_pxRect(_tpl.blocks[_tplSel],cv),p0:p}; return; } }
  const idx=_hitBlock(p.x,p.y,cv);
  if(idx>=0){ _tplSel=idx; _tplEdit={mode:"move",rect0:_pxRect(_tpl.blocks[idx],cv),p0:p}; tplDrawCanvas(); tplRenderList(); }
  else { _tplSel=-1; _tplEdit=null; tplDrawCanvas(); tplRenderList(); } }
function tplMove(ev){ const cv=el("t-canvas"); const p=tplPt(ev);
  if(_tplDraw && _drag){ _drag.x1=p.x; _drag.y1=p.y; tplDrawCanvas();
    const ctx=cv.getContext("2d"); ctx.strokeStyle="#f59e0b"; ctx.lineWidth=2;
    ctx.strokeRect(Math.min(_drag.x0,_drag.x1),Math.min(_drag.y0,_drag.y1),Math.abs(_drag.x1-_drag.x0),Math.abs(_drag.y1-_drag.y0)); return; }
  if(!_tplEdit){ // feedback de cursor
    if(_tplSel>=0 && _hitHandle(_tpl.blocks[_tplSel],cv,p.x,p.y)) cv.style.cursor="crosshair";
    else if(_hitBlock(p.x,p.y,cv)>=0) cv.style.cursor="move"; else cv.style.cursor="default"; return; }
  const b=_tpl.blocks[_tplSel], r0=_tplEdit.rect0, dx=p.x-_tplEdit.p0.x, dy=p.y-_tplEdit.p0.y;
  let nx=r0.x,ny=r0.y,nw=r0.w,nh=r0.h;
  if(_tplEdit.mode==="move"){ nx=r0.x+dx; ny=r0.y+dy; }
  else { const hk=_tplEdit.handle;
    if(hk.includes("w")){ nx=r0.x+dx; nw=r0.w-dx; }
    if(hk.includes("e")){ nw=r0.w+dx; }
    if(hk.includes("n")){ ny=r0.y+dy; nh=r0.h-dy; }
    if(hk.includes("s")){ nh=r0.h+dy; } }
  if(nw<10){ if(_tplEdit.mode==="resize" && _tplEdit.handle.includes("w")) nx=r0.x+r0.w-10; nw=10; }
  if(nh<10){ if(_tplEdit.mode==="resize" && _tplEdit.handle.includes("n")) ny=r0.y+r0.h-10; nh=10; }
  nx=Math.max(0,Math.min(cv.width-nw,nx)); ny=Math.max(0,Math.min(cv.height-nh,ny));
  b.rect={x:nx/cv.width,y:ny/cv.height,w:nw/cv.width,h:nh/cv.height}; tplDrawCanvas(); }
function tplUp(ev){ const cv=el("t-canvas");
  if(_tplDraw && _drag){ const x=Math.min(_drag.x0,_drag.x1),y=Math.min(_drag.y0,_drag.y1),
      w=Math.abs(_drag.x1-_drag.x0),hh=Math.abs(_drag.y1-_drag.y0); _drag=null;
    if(w<10||hh<10){ tplDrawCanvas(); el("t-msg").textContent="Retângulo muito pequeno; tente de novo."; return; }
    _tpl.blocks.push({firstQuestion:_tplDraw.first,questions:_tplDraw.qs,alternatives:_tplDraw.alt,
      rect:{x:x/cv.width,y:y/cv.height,w:w/cv.width,h:hh/cv.height}});
    const last=_tpl.blocks[_tpl.blocks.length-1]; el("b-first").value=last.firstQuestion+last.questions;
    _tplSel=_tpl.blocks.length-1; _tplDraw=null; tplSyncDrawBtn();
    el("t-msg").textContent="Bloco adicionado. Clique nele para mover/redimensionar, ou desenhe o próximo."; tplDrawCanvas(); tplRenderList(); return; }
  _tplEdit=null; }
function tplRenderList(){ const box=el("b-list"); if(!box) return;
  box.innerHTML=_tpl.blocks.length?_tpl.blocks.map((b,i)=>`<div class="barrow" style="${i===_tplSel?'outline:1px solid var(--warn);border-radius:6px':''}">
    <span class="clk" onclick="tplSelBlock(${i})" style="flex:1;cursor:pointer">#${i+1} · Q${b.firstQuestion}–${b.firstQuestion+b.questions-1} (${b.questions} questões · ${b.alternatives||_tpl.alternatives} alternativas)</span>
    <button class="ghost danger" onclick="tplDelBlock(${i})">remover</button></div>`).join("")
    :'<p class="muted">Nenhum bloco ainda. Desenhe um bloco ou use o wizard.</p>';
  if(_tpl.blocks.length && _tplSel>=0) box.insertAdjacentHTML("beforeend",'<p class="muted">Bloco selecionado: arraste na imagem para mover, ou os quadradinhos para redimensionar.</p>'); }
function tplSelBlock(i){ _tplSel=i; _tplEdit=null; tplDrawCanvas(); tplRenderList(); }
function tplDelBlock(i){ _tpl.blocks.splice(i,1); _tplSel=-1; _tplEdit=null; tplDrawCanvas(); tplRenderList(); }

/* Wizard: detecta bolhas (contornos circulares) e agrupa em blocos por coluna. */
function _cluster1d(sorted, gap){ const out=[]; let g=[];
  sorted.forEach(v=>{ if(!g.length||v-g[g.length-1]<=gap) g.push(v); else { out.push(g.reduce((a,b)=>a+b,0)/g.length); g=[v]; } });
  if(g.length) out.push(g.reduce((a,b)=>a+b,0)/g.length); return out; }
function _median(a){ if(!a.length) return 0; const s=a.slice().sort((x,y)=>x-y); return s[Math.floor(s.length/2)]; }
function _detectBlocks(cells, W, H){
  const rmed=_median(cells.map(c=>c.r))||6;
  const xcols=_cluster1d(cells.map(c=>c.x).sort((a,b)=>a-b), rmed*1.2);
  if(xcols.length<2) return [];
  const gaps=[]; for(let i=1;i<xcols.length;i++) gaps.push(xcols[i]-xcols[i-1]);
  const gmed=_median(gaps)||rmed*2;
  const bounds=[]; let start=0;
  for(let i=1;i<xcols.length;i++){ if((xcols[i]-xcols[i-1])>gmed*1.8){ bounds.push([xcols[start],xcols[i-1]]); start=i; } }
  bounds.push([xcols[start],xcols[xcols.length-1]]);
  const blocks=[];
  bounds.forEach(([x0,x1])=>{ const mem=cells.filter(c=>c.x>=x0-rmed && c.x<=x1+rmed); if(mem.length<3) return;
    const yc=_cluster1d(mem.map(c=>c.y).sort((a,b)=>a-b), rmed*1.2);
    const xc=_cluster1d(mem.map(c=>c.x).sort((a,b)=>a-b), rmed*1.2);
    const minx=Math.min(...mem.map(c=>c.x-c.r)), maxx=Math.max(...mem.map(c=>c.x+c.r));
    const miny=Math.min(...mem.map(c=>c.y-c.r)), maxy=Math.max(...mem.map(c=>c.y+c.r));
    blocks.push({x:minx,y:miny,w:maxx-minx,h:maxy-miny,questions:yc.length,alternatives:xc.length}); });
  blocks.sort((a,b)=>a.x-b.x); let q=1; blocks.forEach(b=>{ b.firstQuestion=q; q+=b.questions; });
  return blocks;
}
async function tplWizard(){
  if(!_tplImg){ alert("Carregue a imagem-demo do cartão primeiro."); return; }
  el("t-msg").textContent="Carregando OpenCV.js (~10MB, só na 1ª vez)…";
  try{ await loadOpenCV(); }catch(e){ el("t-msg").innerHTML=`<span class="danger">${esc(e.message)}</span>`; return; }
  el("t-msg").textContent="Detectando bolhas…";
  try{
    const cv0=el("t-canvas"); const W=cv0.width, H=cv0.height;
    const tmp=document.createElement("canvas"); tmp.width=W; tmp.height=H; tmp.getContext("2d").drawImage(_tplImg,0,0,W,H);
    let src=cv.imread(tmp), gray=new cv.Mat(), bin=new cv.Mat();
    cv.cvtColor(src,gray,cv.COLOR_RGBA2GRAY); cv.GaussianBlur(gray,gray,new cv.Size(3,3),0);
    cv.adaptiveThreshold(gray,bin,255,cv.ADAPTIVE_THRESH_MEAN_C,cv.THRESH_BINARY_INV,15,8);
    let contours=new cv.MatVector(), hier=new cv.Mat();
    cv.findContours(bin,contours,hier,cv.RETR_LIST,cv.CHAIN_APPROX_SIMPLE);
    const cells=[]; const imgArea=W*H;
    for(let i=0;i<contours.size();i++){ const c=contours.get(i);
      const a=cv.contourArea(c), rect=cv.boundingRect(c), per=cv.arcLength(c,true);
      const circ=per>0?(4*Math.PI*a)/(per*per):0, ar=rect.width/(rect.height||1);
      if(a>imgArea*0.00003 && a<imgArea*0.004 && ar>0.6 && ar<1.7 && circ>0.55 && rect.width>6)
        cells.push({x:rect.x+rect.width/2, y:rect.y+rect.height/2, r:(rect.width+rect.height)/4});
      c.delete(); }
    src.delete(); gray.delete(); bin.delete(); contours.delete(); hier.delete();
    if(cells.length<10){ el("t-msg").innerHTML='<span class="danger">Não consegui detectar as bolhas. Adicione os blocos manualmente (desenhando).</span>'; return; }
    const blocks=_detectBlocks(cells, W, H);
    if(!blocks.length){ el("t-msg").innerHTML='<span class="danger">Detecção inconclusiva. Adicione manualmente.</span>'; return; }
    _tpl.blocks=blocks.map(b=>({firstQuestion:b.firstQuestion,questions:b.questions,alternatives:b.alternatives||5,rect:{x:b.x/W,y:b.y/H,w:b.w/W,h:b.h/H}}));
    const alts=_median(blocks.map(b=>b.alternatives)); if(alts>=2){ el("t-alt").value=Math.round(alts); if(el("b-alt")) el("b-alt").value=Math.round(alts); }
    el("t-msg").innerHTML=`Detectados <b>${blocks.length} blocos</b> e ${cells.length} bolhas (${blocks.reduce((a,b)=>a+b.questions,0)} questões). <b>Revise</b> os pontos verdes e ajuste/remova blocos se preciso.`;
    tplDrawCanvas(); tplRenderList();
  }catch(e){ el("t-msg").innerHTML=`<span class="danger">Falha no wizard: ${esc(e.message)}. Use o modo manual.</span>`; }
}
function tplRefBlob(){ return new Promise(res=>{ if(!_tplImg) return res(null);
  const maxW=1000, s=Math.min(1,maxW/_tplImg.width);
  const c=document.createElement("canvas"); c.width=Math.round(_tplImg.width*s); c.height=Math.round(_tplImg.height*s);
  c.getContext("2d").drawImage(_tplImg,0,0,c.width,c.height);
  c.toBlob(b=>res(b),"image/jpeg",0.7); }); }
async function tplSave(){ const name=(el("t-name").value||"").trim(); if(!name) return alert("Informe o nome.");
  const alternatives=Number(el("t-alt").value)||5; if(!_tpl.blocks.length) return alert("Adicione ao menos um bloco.");
  const sensitivity=Number(el("t-sens").value)||50;
  if(!_tplImg && !_tpl.templateId) return alert("Carregue a imagem-demo do cartão (usada como referência do reconhecimento automático).");
  const body={name,alternatives,sensitivity,blocks:_tpl.blocks};
  el("t-msg").textContent="Salvando…";
  try{
    let tid=_tpl.templateId;
    if(tid) await api("/card-templates/"+tid,{method:"PUT",body:JSON.stringify(body)});
    else { const r=await api("/card-templates",{method:"POST",body:JSON.stringify(body)}); tid=r.templateId; }
    const blob=await tplRefBlob();
    if(blob){ el("t-msg").textContent="Enviando imagem de referência…";
      const up=await api("/card-templates/"+tid+"/reference",{method:"POST"});
      await fetch(up.uploadUrl,{method:"PUT",headers:{"Content-Type":"image/jpeg"},body:blob}); }
    viewCartaoTemplates();
  }catch(e){ el("t-msg").innerHTML=`<span class="danger">${esc(e.message)}</span>`; } }

/* ---------------- Cartão — Ler (OpenCV.js no navegador) ---------------- */
let _rimg=null, _tplsCache=[], _rres=null, _rfile=null;
function loadOpenCV(){ return new Promise((resolve,reject)=>{
  if(window.cv && window.cv.Mat) return resolve();
  const ready=()=>{ if(window.cv && window.cv.Mat) resolve();
    else if(window.cv){ window.cv.onRuntimeInitialized=()=>resolve(); } else reject(new Error("OpenCV não inicializou.")); };
  if(window.cv){ ready(); return; }
  const s=document.createElement("script"); s.src="/opencv.js"; s.async=true;
  s.onload=()=>{ if(window.cv && typeof window.cv.then==="function"){ window.cv.then(m=>{ window.cv=m; resolve(); }); } else ready(); };
  s.onerror=()=>reject(new Error("Falha ao carregar OpenCV.js (~10MB). Verifique a conexão."));
  document.head.appendChild(s); }); }
let _rcorners=null, _radjW=0, _radjH=0, _rbase=null, _rphase="none", _rdragC=-1, _refImg=null, _refFor="", _rIdExam="";
function cvDetectQr(){ _rIdExam=""; if(!_rimg||!(window.cv&&cv.Mat)) return;
  try{ const maxW=1400, s=Math.min(1,maxW/_rimg.width);
    const c=document.createElement("canvas"); c.width=Math.round(_rimg.width*s); c.height=Math.round(_rimg.height*s);
    c.getContext("2d").drawImage(_rimg,0,0,c.width,c.height);
    let src=cv.imread(c), qr=new cv.QRCodeDetector(), pts=new cv.Mat(), st=new cv.Mat();
    let data=qr.detectAndDecode(src,pts,st); src.delete(); pts.delete(); st.delete();
    _rIdExam=(data||"").trim(); }catch(e){ _rIdExam=""; } }
async function viewCartaoRead(){
  h(`<div class="hdr"><h2>Ler cartão (OpenCV, no navegador)</h2></div><div class="card muted">Carregando templates…</div>`);
  try{ _tplsCache=(await api("/card-templates")).items||[]; }catch(e){ _tplsCache=[]; }
  const opts=_tplsCache.length?_tplsCache.map(t=>`<option value="${t.templateId}">${esc(t.name)} · ${t.totalQuestions}q</option>`).join("")
    :'<option value="">— crie um template primeiro (menu Templates) —</option>';
  h(`<div class="hdr"><h2>Ler cartão (OpenCV, no navegador)</h2></div>
     <div class="card">
       <label>Template</label><select id="r-tpl" onchange="cvTplChange()">${opts}</select>
       <label>Imagem do cartão (foto ou arquivo)</label>
       <label class="filedrop" style="padding:16px">
         <input type="file" accept="image/*" onchange="cvLoadImg(this)">
         <div id="r-fileprompt">📎 Selecionar ou fotografar o cartão</div>
         <div id="r-filename" class="muted"></div>
       </label>
       <label class="rb" style="margin-top:8px"><input type="checkbox" id="r-persp" checked onchange="cvPerspToggle()"> Reconhecer automaticamente a área das respostas (posição, rotação, zoom)</label>
       <label style="margin-top:8px">Sensibilidade (limiar de preenchimento): <span id="thv">50</span>% <span class="muted">(vem do template)</span></label>
       <input id="thr" type="range" min="20" max="90" value="50" oninput="el('thv').textContent=this.value; if(_rbase&&_rphase==='read')cvOMR()">
       <div id="r-controls" style="margin-top:8px"></div>
       <p class="muted">Tudo roda no seu navegador via OpenCV.js. Alternativa lida = <b>verde</b>; em branco = <b>vermelho</b>; múltiplas = <b>amarelo</b>.</p>
       <div id="r-status" class="muted"></div>
       <div style="overflow:auto;border:1px solid var(--line);border-radius:8px;margin-top:8px;background:#0b1020">
         <canvas id="r-canvas" style="display:block;max-width:100%;touch-action:none"
           onpointerdown="rDown(event)" onpointermove="rMove(event)" onpointerup="rUp(event)"></canvas></div>
       <div id="r-out"></div>
     </div>`);
  cvTplChange();
}
function cvTemplate(){ const id=(el("r-tpl")||{}).value; return _tplsCache.find(t=>t.templateId===id); }
async function cvTplChange(){ const t=cvTemplate(); if(!t) return; const s=t.sensitivity||50;
  if(el("thr")){ el("thr").value=s; el("thv").textContent=s; }
  if(t.referenceUrl===undefined){ if(t.hasReference){ try{ const r=await api("/card-templates/"+t.templateId+"/reference"); t.referenceUrl=r.url||""; }catch(e){ t.referenceUrl=""; } } else t.referenceUrl=""; }
  if(_rimg){ if(el("r-persp").checked) cvAuto(); else cvReadRaw(); }
  else if(_rbase && _rphase==="read") cvOMR(); }
function cvLoadImg(input){ const f=input.files[0]; if(!f) return; _rfile=f;
  const pr=el("r-fileprompt"), fn=el("r-filename");
  if(pr) pr.textContent="🖼️ "+f.name; if(fn) fn.textContent=Math.round(f.size/1024)+" KB";
  const img=new Image(); img.onload=async()=>{ _rimg=img; el("r-status").textContent="Carregando OpenCV.js (~10MB, só na 1ª vez)…";
    try{ await loadOpenCV(); el("r-status").textContent=""; cvDetectQr();
      if(el("r-persp").checked) cvAuto(); else cvReadRaw(); }
    catch(e){ el("r-status").innerHTML=`<span class="danger">${esc(e.message)}</span>`; } };
  img.src=URL.createObjectURL(f); }
function cvPerspToggle(){ if(!_rimg) return; if(el("r-persp").checked) cvAuto(); else cvReadRaw(); }
function cvControls(){ const c=el("r-controls"); if(!c) return;
  if(_rphase==="adjust") c.innerHTML='<button onclick="cvReadNow()">🔍 Ler cartão</button> <span class="muted">arraste os cantos para as bordas da folha</span>';
  else if(_rphase==="read") c.innerHTML='<button class="sec" onclick="cvAuto()">🔄 Reconhecer de novo</button> <button class="ghost" onclick="cvEnterAdjust()">↺ Ajustar cantos manualmente</button>';
  else c.innerHTML=''; }
/* --- reconhecimento automático da área das respostas (feature matching + homografia) --- */
function cvAuto(){ const tpl=cvTemplate();
  if(!tpl){ return; }
  if(!tpl.referenceUrl){ el("r-status").innerHTML='<span class="muted">Template sem imagem de referência. Edite o template e salve com a imagem do cartão, ou ajuste os cantos manualmente.</span>'; cvEnterAdjust(); return; }
  if(_refImg && _refFor===tpl.templateId){ cvDoAlign(); return; }
  el("r-status").textContent="Preparando referência…";
  const im=new Image(); im.crossOrigin="anonymous"; im.onload=()=>{ _refImg=im; _refFor=tpl.templateId; cvDoAlign(); };
  im.onerror=()=>{ el("r-status").innerHTML='<span class="danger">Falha ao carregar a referência; ajuste manual.</span>'; cvEnterAdjust(); };
  im.src=tpl.referenceUrl; }
function cvDoAlign(){
  el("r-status").textContent="Reconhecendo a área das respostas…";
  let base=null; try{ base=cvAlignHomography(_rimg,_refImg); }catch(e){ base=null; }
  if(!base){ el("r-status").innerHTML='<span class="danger">Não consegui reconhecer automaticamente (poucos pontos em comum). Ajuste os cantos manualmente abaixo.</span>'; cvEnterAdjust(); return; }
  _rbase=base; _rphase="read"; cvControls(); cvOMR();
  el("r-status").innerHTML=`<span class="muted">Área reconhecida automaticamente (${base._matches||0} pontos). Confira, corrija se preciso e salve.</span>`; }
function cvAlignHomography(photoImg, refImg){
  const maxW=1000;
  const rs=Math.min(1,maxW/refImg.width), RW=Math.round(refImg.width*rs), RH=Math.round(refImg.height*rs);
  const refC=document.createElement("canvas"); refC.width=RW; refC.height=RH; refC.getContext("2d").drawImage(refImg,0,0,RW,RH);
  const ps=Math.min(1,maxW/photoImg.width), PW=Math.round(photoImg.width*ps), PH=Math.round(photoImg.height*ps);
  const phC=document.createElement("canvas"); phC.width=PW; phC.height=PH; phC.getContext("2d").drawImage(photoImg,0,0,PW,PH);
  let refM=cv.imread(refC), phM=cv.imread(phC), g1=new cv.Mat(), g2=new cv.Mat();
  cv.cvtColor(refM,g1,cv.COLOR_RGBA2GRAY); cv.cvtColor(phM,g2,cv.COLOR_RGBA2GRAY);
  let orb=new cv.ORB(1500);
  let kp1=new cv.KeyPointVector(), kp2=new cv.KeyPointVector(), d1=new cv.Mat(), d2=new cv.Mat(), mask=new cv.Mat();
  let base=null;
  try{
    orb.detectAndCompute(g1,mask,kp1,d1); orb.detectAndCompute(g2,mask,kp2,d2);
    if(d1.rows>10 && d2.rows>10){
      let bf=new cv.BFMatcher(cv.NORM_HAMMING,true), matches=new cv.DMatchVector();
      bf.match(d2,d1,matches);   // query = foto (d2), train = referência (d1)
      const arr=[]; for(let i=0;i<matches.size();i++) arr.push(matches.get(i));
      arr.sort((a,b)=>a.distance-b.distance);
      const good=arr.slice(0, Math.max(15, Math.floor(arr.length*0.3)));
      if(good.length>=15){
        const src=[], dst=[];
        good.forEach(m=>{ const p=kp2.get(m.queryIdx).pt, q=kp1.get(m.trainIdx).pt; src.push(p.x,p.y); dst.push(q.x,q.y); });
        let srcM=cv.matFromArray(good.length,1,cv.CV_32FC2,src), dstM=cv.matFromArray(good.length,1,cv.CV_32FC2,dst);
        let Hm=cv.findHomography(srcM,dstM,cv.RANSAC,5);
        if(Hm && !Hm.empty()){ let out=new cv.Mat(); cv.warpPerspective(phM,out,Hm,new cv.Size(RW,RH));
          base=document.createElement("canvas"); base.width=RW; base.height=RH; cv.imshow(base,out); base._matches=good.length; out.delete(); }
        srcM.delete(); dstM.delete(); if(Hm) Hm.delete();
      }
      matches.delete(); bf.delete();
    }
  } finally {
    refM.delete();phM.delete();g1.delete();g2.delete();orb.delete();kp1.delete();kp2.delete();d1.delete();d2.delete();mask.delete();
  }
  return base; }
/* --- fase de ajuste de cantos (perspectiva) --- */
function cvEnterAdjust(){ if(!_rimg||!(window.cv&&cv.Mat)) return;
  const cvv=el("r-canvas"); const maxW=900, scale=Math.min(1,maxW/_rimg.width);
  _radjW=Math.round(_rimg.width*scale); _radjH=Math.round(_rimg.height*scale);
  cvv.width=_radjW; cvv.height=_radjH; cvv.getContext("2d").drawImage(_rimg,0,0,_radjW,_radjH);
  let q=null; try{ let src=cv.imread(cvv); q=cvDetectQuad(src,_radjW,_radjH); src.delete(); }catch(e){}
  _rcorners = q || [{x:_radjW*0.05,y:_radjH*0.05},{x:_radjW*0.95,y:_radjH*0.05},{x:_radjW*0.95,y:_radjH*0.95},{x:_radjW*0.05,y:_radjH*0.95}];
  _rphase="adjust"; el("r-out").innerHTML=""; cvControls(); cvDrawAdjust();
  el("r-status").innerHTML = q?'<span class="muted">Folha detectada. Ajuste os cantos se preciso e clique em <b>Ler cartão</b>.</span>'
    :'<span class="muted">Não detectei a folha — arraste os 4 cantos (laranja) para as bordas do cartão e clique em <b>Ler cartão</b>.</span>';
}
function cvDrawAdjust(){ const cvv=el("r-canvas"); const ctx=cvv.getContext("2d");
  ctx.drawImage(_rimg,0,0,_radjW,_radjH);
  ctx.strokeStyle="#22d3ee"; ctx.lineWidth=2; ctx.beginPath();
  _rcorners.forEach((p,i)=>{ i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y); }); ctx.closePath(); ctx.stroke();
  ctx.fillStyle="#f59e0b"; _rcorners.forEach(p=>{ ctx.beginPath(); ctx.arc(p.x,p.y,8,0,7); ctx.fill(); }); }
function rPt(ev){ const cv=el("r-canvas"), r=cv.getBoundingClientRect();
  return {x:(ev.clientX-r.left)*(cv.width/r.width), y:(ev.clientY-r.top)*(cv.height/r.height)}; }
function rDown(ev){ if(_rphase!=="adjust"||!_rcorners) return; const p=rPt(ev); ev.preventDefault();
  let best=-1,bd=1e9; _rcorners.forEach((c,i)=>{const d=Math.hypot(c.x-p.x,c.y-p.y); if(d<bd){bd=d;best=i;}});
  if(bd<=28) _rdragC=best; }
function rMove(ev){ if(_rdragC<0) return; const p=rPt(ev);
  _rcorners[_rdragC]={x:Math.max(0,Math.min(_radjW,p.x)),y:Math.max(0,Math.min(_radjH,p.y))}; cvDrawAdjust(); }
function rUp(ev){ _rdragC=-1; }
function cvOrder(pts){ const bySum=[...pts].sort((a,b)=>(a.x+a.y)-(b.x+b.y));
  const byDiff=[...pts].sort((a,b)=>(a.y-a.x)-(b.y-b.x));
  return [bySum[0], byDiff[0], bySum[3], byDiff[3]]; }  // tl,tr,br,bl
function cvDetectQuad(src,W,H){ let gray=new cv.Mat(),blur=new cv.Mat(),edg=new cv.Mat();
  cv.cvtColor(src,gray,cv.COLOR_RGBA2GRAY); cv.GaussianBlur(gray,blur,new cv.Size(5,5),0);
  cv.Canny(blur,edg,50,150); let k=cv.Mat.ones(5,5,cv.CV_8U); cv.dilate(edg,edg,k);
  let contours=new cv.MatVector(),hier=new cv.Mat();
  cv.findContours(edg,contours,hier,cv.RETR_EXTERNAL,cv.CHAIN_APPROX_SIMPLE);
  let best=null,bestArea=W*H*0.2;
  for(let i=0;i<contours.size();i++){ const c=contours.get(i); const area=cv.contourArea(c);
    if(area>bestArea){ const peri=cv.arcLength(c,true); let ap=new cv.Mat(); cv.approxPolyDP(c,ap,0.02*peri,true);
      if(ap.rows===4){ bestArea=area; if(best) best.delete(); best=ap; } else ap.delete(); }
    c.delete(); }
  gray.delete();blur.delete();edg.delete();k.delete();contours.delete();hier.delete();
  if(!best) return null;
  const pts=[]; for(let i=0;i<4;i++) pts.push({x:best.data32S[i*2],y:best.data32S[i*2+1]}); best.delete();
  return cvOrder(pts); }
function cvReadNow(){ if(!_rcorners||!(window.cv&&cv.Mat)) return;
  const tmp=document.createElement("canvas"); tmp.width=_radjW; tmp.height=_radjH;
  tmp.getContext("2d").drawImage(_rimg,0,0,_radjW,_radjH);
  let src=cv.imread(tmp); const [tl,tr,br,bl]=cvOrder(_rcorners);
  const W=Math.max(50,Math.round(Math.max(Math.hypot(br.x-bl.x,br.y-bl.y),Math.hypot(tr.x-tl.x,tr.y-tl.y))));
  const H=Math.max(50,Math.round(Math.max(Math.hypot(tr.x-br.x,tr.y-br.y),Math.hypot(tl.x-bl.x,tl.y-bl.y))));
  let s=cv.matFromArray(4,1,cv.CV_32FC2,[tl.x,tl.y,tr.x,tr.y,br.x,br.y,bl.x,bl.y]);
  let d=cv.matFromArray(4,1,cv.CV_32FC2,[0,0,W,0,W,H,0,H]);
  let M=cv.getPerspectiveTransform(s,d), dst=new cv.Mat();
  cv.warpPerspective(src,dst,M,new cv.Size(W,H));
  const base=document.createElement("canvas"); base.width=W; base.height=H; cv.imshow(base,dst);
  src.delete();s.delete();d.delete();M.delete();dst.delete();
  _rbase=base; _rphase="read"; cvControls(); cvOMR(); }
function cvReadRaw(){ if(!_rimg) return;
  const maxW=900, scale=Math.min(1,maxW/_rimg.width);
  const W=Math.round(_rimg.width*scale), H=Math.round(_rimg.height*scale);
  const base=document.createElement("canvas"); base.width=W; base.height=H;
  base.getContext("2d").drawImage(_rimg,0,0,W,H);
  _rbase=base; _rphase="read"; el("r-status").textContent=""; cvControls(); cvOMR(); }
function cvOMR(){ const tpl=cvTemplate(); if(!_rbase||!tpl||!(window.cv&&cv.Mat)) return;
  const W=_rbase.width, H=_rbase.height;
  let src=cv.imread(_rbase), gray=new cv.Mat(), bin=new cv.Mat();
  cv.cvtColor(src,gray,cv.COLOR_RGBA2GRAY);
  cv.adaptiveThreshold(gray,bin,255,cv.ADAPTIVE_THRESH_MEAN_C,cv.THRESH_BINARY_INV,25,10);
  const letters=tpl.letters||[], thr=(Number(el("thr").value)||50)/100;
  const results=[];
  (tpl.blocks||[]).forEach(b=>{ const alt=b.alternatives||tpl.alternatives||5;
    const bx=b.rect.x*W,by=b.rect.y*H,bw=b.rect.w*W,bh=b.rect.h*H;
    for(let r=0;r<b.questions;r++){ const fills=[];
      for(let c=0;c<alt;c++){ const cx=bx+bw*(c+0.5)/alt, cy=by+bh*(r+0.5)/b.questions;
        const rad=Math.max(4,Math.min(bw/alt,bh/b.questions)*0.32);
        const x0=Math.max(0,Math.round(cx-rad)),y0=Math.max(0,Math.round(cy-rad));
        const x1=Math.min(W,Math.round(cx+rad)),y1=Math.min(H,Math.round(cy+rad));
        let roi=bin.roi(new cv.Rect(x0,y0,Math.max(1,x1-x0),Math.max(1,y1-y0)));
        const filled=cv.countNonZero(roi)/((roi.rows*roi.cols)||1); roi.delete();
        fills.push({c,filled,cx,cy,rad}); }
      const marked=fills.filter(f=>f.filled>=thr).sort((a,b)=>a.c-b.c);
      let marcada="-", marcadas=[];
      if(marked.length===1){ marcada=letters[marked[0].c]||String.fromCharCode(65+marked[0].c); }
      else if(marked.length>=2){ marcada="*";
        marcadas=marked.map(f=>letters[f.c]||String.fromCharCode(65+f.c)); }
      results.push({questao:b.firstQuestion+r, marcada, marcadas, fills, alt}); } });
  src.delete(); gray.delete(); bin.delete();
  _rres={tpl,W,H,results}; cvDrawOverlay(); cvRenderTable(); }
function cvDrawOverlay(){ const {W,H,results,tpl}=_rres; const cvCanvas=el("r-canvas");
  cvCanvas.width=W; cvCanvas.height=H; const ctx=cvCanvas.getContext("2d");
  ctx.drawImage(_rbase,0,0); const letters=tpl.letters||[];
  results.forEach(q=>{ q.fills.forEach(f=>{ const L=letters[f.c]||String.fromCharCode(65+f.c);
    ctx.beginPath(); ctx.arc(f.cx,f.cy,f.rad,0,7);
    const thr=(Number(el("thr").value)||55)/100;
    if(q.marcada==="*" && f.filled>=thr){ ctx.strokeStyle="#eab308"; ctx.fillStyle="rgba(234,179,8,0.35)"; ctx.lineWidth=3; ctx.fill(); }
    else if(q.marcada===L && q.marcada!=="-" && q.marcada!=="*"){ ctx.strokeStyle="#22c55e"; ctx.lineWidth=3; }
    else if(q.marcada==="-"){ ctx.strokeStyle="rgba(220,38,38,0.75)"; ctx.lineWidth=2; }
    else { ctx.strokeStyle="rgba(148,163,184,0.3)"; ctx.lineWidth=1; }
    ctx.stroke(); }); }); }
function cvRenderTable(){ const {results,tpl}=_rres; const letters=tpl.letters||[];
  const marked=results.filter(r=>r.marcada!=="-"&&r.marcada!=="*").length;
  const blank=results.filter(r=>r.marcada==="-").length, multi=results.filter(r=>r.marcada==="*").length;
  el("r-out").innerHTML=`<div class="card"><h3>Leitura — ${results.length} questões · ${marked} marcadas · <span style="color:var(--bad)">${blank} em branco</span> · <span style="color:var(--warn)">${multi} múltiplas</span></h3>
    <p class="muted">ID_Exam (QR): <b>${_rIdExam?esc(_rIdExam):"não detectado"}</b></p>
    <p class="muted">Clique numa alternativa para corrigir manualmente. ∅ = em branco (vermelho). Amarelo = múltiplas marcações.</p>
    <div class="omr-grid">${results.map((q,i)=>`<div class="omr-q ${q.marcada==='*'?'multi':''} ${q.marcada==='-'?'blankq':''}" title="${q.marcada==='*'?'Múltiplas marcações':(q.marcada==='-'?'Nenhuma marcação':'')}"><span class="qn">${q.questao}</span>
      ${Array.from({length:q.alt||tpl.alternatives||5},(_,c)=>{const L=letters[c]||String.fromCharCode(65+c);
        return `<button class="omr-a ${q.marcada===L?'sel':''}" onclick="cvSet(${i},'${L}')">${L}</button>`;}).join("")}
      <button class="omr-a ${q.marcada==='-'?'sel blank':''}" onclick="cvSet(${i},'-')">∅</button>${q.marcada==='*'?`<span class="omr-multi">⚠ ${(q.marcadas||[]).join(",")}</span>`:''}</div>`).join("")}</div>
    <div style="margin-top:12px"><button id="cv-save" onclick="cvSave()">💾 Salvar no histórico</button></div></div>`; }
function cvSet(i,L){ _rres.results[i].marcada=L; _rres.results[i].marcadas=[]; cvDrawOverlay(); cvRenderTable(); }
async function cvSave(){
  if(!_rres || !_rfile){ alert("Faça a leitura de um cartão primeiro."); return; }
  const tpl=cvTemplate(); const btn=el("cv-save"); if(btn){ btn.disabled=true; btn.textContent="Salvando…"; }
  try{
    const ext=(_rfile.name.split('.').pop()||"png").toLowerCase();
    const s=await api("/submissions",{method:"POST",body:JSON.stringify({type:"answersheet",fileExt:ext,options:{templateId:tpl?tpl.templateId:""}})});
    await fetch(s.uploadUrl,{method:"PUT",headers:{"Content-Type":_rfile.type||"application/octet-stream"},body:_rfile});
    const answers=_rres.results.map(q=>({questao:q.questao,marcada:q.marcada,marcadas:q.marcadas||[]}));
    await api(`/submissions/${s.submissionId}/answersheet-result`,{method:"POST",
      body:JSON.stringify({answers,templateId:tpl?tpl.templateId:"",source:"OpenCV (navegador)",idExam:_rIdExam})});
    location.hash="cartao-hist";
  }catch(e){ alert(e.message); if(btn){ btn.disabled=false; btn.textContent="💾 Salvar no histórico"; } }
}

/* ---------------- Evaluation (model as a judge) ---------------- */
function cssId(s){ return (window.CSS&&CSS.escape)?CSS.escape(s):s; }
async function viewEvaluation(){
  h(`<div class="hdr"><h2>Evaluation — Model as a Judge</h2></div><div class="card muted">Carregando…</div>`);
  let c, ms;
  try{ [c, ms] = await Promise.all([api("/evaluations/candidates"), models()]); }
  catch(e){ return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const cands=c.candidates||[];
  const byType={essay:[],exam:[]}; cands.forEach(x=>(byType[x.type]=byType[x.type]||[]).push(x));
  const judgeSel=`<label>Modelo juiz (model as a judge)</label>
    <select id="judge">${ms.map(m=>`<option value="${m.id}">${esc(m.label)}${m.kind==="profile"?" ·perfil":""}</option>`).join("")}</select>`;
  const section=(type,label)=>{
    const list=byType[type]||[];
    if(!list.length) return `<h3>${label}</h3><div class="card muted">Nenhuma submissão com mais de um modelo.</div>`;
    return `<h3>${label}</h3><div class="card"><table>
      <tr><th>Protocolo</th><th>Data</th><th>Modelos usados</th><th>Avaliações</th><th></th></tr>
      ${list.map(x=>{
        const tr=x.multiTranscription?`<div class="muted">Transcrição: ${x.transcriptionModels.map(esc).join(", ")}</div>`:"";
        const co=`<div class="muted">Correção: ${x.correctionModels.map(esc).join(", ")}</div>`;
        // Avaliações já salvas (mais recentes primeiro), colapsáveis.
        const stored=(x.evaluations||[]).slice().reverse()
          .map(ev=>`<details class="evdet"><summary>Avaliação · juiz ${esc(ev.judgeModel)} · ${esc(ev.createdAt||"")}</summary>${renderEval(ev)}</details>`).join("");
        return `<tr><td>${x.submissionId.slice(0,8)}</td><td class="muted">${esc(x.createdAt||"")}</td>
          <td>${tr}${co}</td><td>${x.evaluationCount||0}</td>
          <td><button class="sec" onclick="runEval('${x.submissionId}')">⚖️ Avaliar</button></td></tr>
          <tr id="ev-${x.submissionId}"><td colspan="5" class="evcell">${stored}</td></tr>`;}).join("")}
      </table></div>`;
  };
  h(`<div class="hdr"><h2>Evaluation — Model as a Judge</h2>
       <button class="sec" onclick="viewEvaluation()">↻ Atualizar</button></div>
     <div class="card">${judgeSel}
       <p class="muted">Escolha o modelo juiz e clique em <b>Avaliar</b> numa submissão que usou mais de um modelo.
       O juiz compara as saídas (sem saber qual modelo gerou cada uma), dá notas por dimensão e indica a de
       maior qualidade. Cada avaliação fica <b>salva</b> no histórico da submissão.</p></div>
     ${section("essay","Redação")}${section("exam","Prova Discursiva")}`);
}
async function runEval(sid){
  const judge=el("judge").value;
  const cell=document.querySelector(`#ev-${cssId(sid)} .evcell`);
  if(!cell) return;
  const spin=document.createElement("div"); spin.className="muted";
  spin.textContent="⚖️ Avaliando com o juiz… pode levar alguns segundos.";
  cell.prepend(spin);
  try{
    const ev=await api("/evaluations/run",{method:"POST",body:JSON.stringify({submissionId:sid,judgeModel:judge})});
    spin.remove();
    const d=document.createElement("details"); d.className="evdet"; d.open=true;
    d.innerHTML=`<summary>Avaliação · juiz ${esc(ev.judgeModel)} · ${esc(ev.createdAt||"")}</summary>${renderEval(ev)}`;
    cell.prepend(d);
  }catch(e){ spin.className="danger"; spin.textContent=e.message; }
}
function sbar(v, win){ v=Math.max(0,Math.min(10,Number(v)||0));
  return `<span class="sbar"><span class="sfill${win?' win':''}" style="width:${(v/10*100).toFixed(0)}%"></span></span>`; }
function mtag(who, model, score, win){
  return `<span class="mtag${win?' win':''}"><span class="who">${who}</span>${esc(model)} · ${fmt(score)}/10${win?" 🏆":""}</span>`; }
function cmpCard(c){
  const aWin=c.winner==="A", bWin=c.winner==="B";
  const head=`<div class="cmphead">${mtag("A",c.modelA,c.scoreA,aWin)}<span class="vs">vs</span>${mtag("B",c.modelB,c.scoreB,bWin)}
    ${c.winner==="empate"?'<span class="vs">🤝 empate</span>':""}</div>`;
  const dims=(c.dimensions||[]).map(d=>`<div class="dimrow">
    <div class="dimname">${esc(d.name)}</div>
    <div class="dimcol"><span class="who">A</span>${sbar(d.scoreA,(Number(d.scoreA)||0)>=(Number(d.scoreB)||0))}<span class="sval">${fmt(d.scoreA)}</span></div>
    <div class="dimcol"><span class="who">B</span>${sbar(d.scoreB,(Number(d.scoreB)||0)>(Number(d.scoreA)||0))}<span class="sval">${fmt(d.scoreB)}</span></div>
    ${d.note?`<div class="dimnote">${esc(d.note)}</div>`:""}</div>`).join("");
  return `<div class="crit cmp">${head}
    ${dims?`<div class="dims">${dims}</div>`:""}
    <div class="muted" style="white-space:pre-wrap;margin-top:8px"><b>Resumo:</b> ${esc(c.rationale)}</div></div>`;
}
function renderEval(ev){
  const tr=ev.transcriptionComparisons||[], co=ev.correctionComparisons||[];
  if(!tr.length && !co.length) return '<span class="muted">Nada a comparar nesta submissão.</span>';
  return `<div class="evmeta">Juiz: <b>${esc(ev.judgeModel)}</b>${ev.createdAt?` · ${esc(ev.createdAt)}`:""}</div>
    ${tr.length?`<div class="ansl">Transcrições</div>${tr.map(cmpCard).join("")}`:""}
    ${co.length?`<div class="ansl">Correções</div>${co.map(cmpCard).join("")}`:""}`;
}

/* ---------------- Roteamento ---------------- */
const ROUTES = {
  "ex-corrige":()=>viewCorrecao("exam"), "ex-criar":viewCriar, "ex-hist":()=>viewHistorico("exam"),
  "red-rubrica":viewRubricas, "red-corrige":()=>viewCorrecao("essay"), "red-hist":()=>viewHistorico("essay"),
  "cartao-load":viewCartaoLoad, "cartao-read":viewCartaoRead, "cartao-tpl":viewCartaoTemplates,
  "cartao-hist":viewCartaoHist, "cartao":viewCartaoLoad,
  "modelos":viewModelos, "analytics":viewAnalytics, "evaluation":viewEvaluation,
};
function route(){ const k=location.hash.slice(1)||"ex-corrige"; renderNav(ROUTES[k]?k:"ex-corrige"); (ROUTES[k]||ROUTES["ex-corrige"])(); toggleSide(false); }
window.addEventListener("hashchange", route);

(async function(){
  const p=new URLSearchParams(location.search);
  if(p.get("code")){ try{ await exchangeCode(p.get("code")); }catch(e){ document.body.innerHTML="<p style='padding:24px'>Erro de login. <a href='/'>Tentar novamente</a></p>"; return; } }
  if(!ID_TOKEN){ return login(); }
  route();
})();
