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
// Árvore do menu: um nó é [chave, rótulo] (folha, navega) OU [nome, filhos] (grupo).
// "Avaliações" agrupa as provas + Configuração + Evaluation; os demais módulos ficam no topo.
const MENU = [
  ["Avaliações", [
    ["Prova Discursiva", [["ex-corrige","Correção"],["ex-criar","Criação"],["ex-hist","Histórico"]]],
    ["Redação", [["red-rubrica","Rubricas"],["red-corrige","Correção"],["red-hist","Histórico"]]],
    ["Prova Objetiva", [["cartao-load","Carregar cartão"],["cartao-read","Ler cartão (OpenCV)"],["cartao-tpl","Templates"],["cartao-hist","Histórico"]]],
    ["Provas Online", [["po-criar","Provas"],["po-teste","Teste de prova"],["po-hist","Histórico"]]],
    ["Configuração", [["modelos","Modelos"]]],
    ["Evaluation", [["evaluation","Model-as-judge"]]],
  ]],
  ["LMS de Vídeo", [["lms-busca","Busca em Vídeo"],["lms-catalogo","Catálogo"],["lms-qualidade","Qualidade"]]],
  ["Entrevistador Virtual", [["ent-entrevista","Entrevista"],["ent-vagas","Vagas"],["ent-avatar","Avatar"],["ent-relatorio","Histórico"]]],
  ["Orientador Acadêmico", [["ori-alunos","Alunos"],["ori-cursos","Cursos"],["ori-carreiras","Carreiras"],["ori-chat","Chat"],["ori-trilha","Trilha"],["ori-grafo","Grafo"],["ori-insights","Insights"],["ori-curriculo","Currículo"],["ori-competencias","Competências"],["ori-coord","Coordenação"]]],
  ["Orientador Context", [["octx-alunos","Alunos"],["octx-cursos","Cursos"],["octx-chat","Chat"],["octx-trilha","Trilha"],["octx-grafo","Grafo"],["octx-insights","Insights"],["octx-curriculo","Currículo"],["octx-competencias","Competências"],["octx-coord","Coordenação"],["octx-risco","Risco de evasão"],["octx-desempenho","Desempenho"]]],
  ["AgentCore", [
    ["Gateway Inference", [
      ["gwinf-inference","Inference"],
      ["gwinf-eval","Evaluation"],
      ["gwinf-history","History"],
      ["gwinf-mantle","Mantle-config"],
      ["gwinf-keys","Keys"],
      ["gwinf-sysprompt","System-prompt"],
    ]],
  ]],
  ["Atendimento", [
    ["atend-chat","Chat (Connect)"],
    ["atend-templates","Templates WhatsApp"],
    ["atend-campanhas","Campanhas"],
  ]],
  ["Analytics", [["analytics","Dados Analíticos"]]],
];
// Grupos de topo que ficam SEMPRE por último (separados por uma linha).
const TRAILING_GROUPS = ["Analytics"];

// Um nó é grupo quando seu 2º elemento é lista (filhos); senão é folha [chave, rótulo].
function _isGroup(node){ return Array.isArray(node[1]); }
function _menuHasKey(children, active){
  return children.some(n => _isGroup(n) ? _menuHasKey(n[1], active) : n[0] === active);
}
function _renderNode(node, active, depth){
  if(!_isGroup(node)){
    const [k,t] = node;
    return `<a href="#${k}" class="${k===active?'active':''}">${t}</a>`;
  }
  const [name, children] = node;
  const open = _menuHasKey(children, active);
  const sub = depth > 0 ? " sub" : "";
  return `<div class="grp${sub}${open?" open":""}">`+
    `<div class="gh" onclick="toggleGrp(this)">${name}<span class="chev">▸</span></div>`+
    `<div class="grp-items">`+
    children.map(c => _renderNode(c, active, depth+1)).join("")+
    `</div></div>`;
}
function renderNav(active){
  // Acordeão: abre o caminho até o item ativo (guarda-chuva + subgrupo).
  const normal = MENU.filter(([g]) => !TRAILING_GROUPS.includes(g));
  const trailing = TRAILING_GROUPS.map(n => MENU.find(([g]) => g === n)).filter(Boolean);
  el("nav").innerHTML =
    normal.map(g => _renderNode(g, active, 0)).join("") +
    (trailing.length ? `<div class="nav-sep"></div>` : "") +
    trailing.map(g => _renderNode(g, active, 0)).join("");
  const c=claims(); el("who").textContent=(c.email||"")+(isAdmin()?" · admin":" · professor");
}
// Abre/fecha o grupo clicado; recolhe os irmãos do MESMO nível (accordion).
function toggleGrp(gh){
  const grp = gh.parentElement, container = grp.parentElement;
  const willOpen = !grp.classList.contains("open");
  Array.from(container.children).forEach(ch => {
    if(ch !== grp && ch.classList && ch.classList.contains("grp")) ch.classList.remove("open");
  });
  grp.classList.toggle("open", willOpen);
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
    // Só no cartão-resposta (com template): oferece sobrepor as marcações lidas.
    const overlay = (_cart && _cart.id===id && _cart.templateId)
      ? `<div style="margin-top:10px"><button class="sec" id="ovbtn" onclick="overlayCartao()">🎯 Sobrepor marcação</button>
         <div id="ov-box" style="margin-top:10px"></div></div>` : "";
    box.innerHTML=`<button class="sec" onclick="toggleImg('${id}')">Ocultar imagem</button><div id="img-media">${media}</div>${overlay}`;
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
  const nice={transcription:"Transcrição (leitura da imagem)",essay:"Correção de Redação",exam:"Correção de Prova Discursiva",author:"Wizard de Resposta",answersheet:"Leitura de Cartão Resposta",examgen:"Provas Online (geração de questões)"};
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
  try{
    await api("/model-config/"+cap,{method:"PUT",body:JSON.stringify({
      primaryModel:el("p-"+cap).value, challengerModel:(el("c-"+cap)||{}).value||"", mode,
      abPolicy:{percent:Number((el("ab-"+cap)||{}).value)||0}})});
    // Re-renderiza: o backend já preencheu o preço de lista do modelo escolhido, então
    // a tabela de Preços passa a mostrá-lo automaticamente.
    await viewModelos();
    el("out").innerHTML='<div class="card toast">Salvo. Preço do modelo atualizado abaixo.</div>';
  }catch(e){ el("out").innerHTML=`<div class="card danger">${esc(e.message)}</div>`; }
}
async function savePrices(){
  const prices={};
  _priceModels.forEach((m,i)=>{ const vi=el("pin-"+i).value, vo=el("pout-"+i).value;
    if(vi!==""||vo!==""){ prices[m]={in:Number(vi)||0, out:Number(vo)||0}; }});
  try{ await api("/pricing",{method:"PUT",body:JSON.stringify({prices})}); el("out").innerHTML='<div class="card toast">Preços salvos.</div>'; }
  catch(e){ el("out").innerHTML=`<div class="card danger">${esc(e.message)}</div>`; }
}

/* ---------------- Analytics (gráficos) ---------------- */
const TIPO_LABELS={essay:"Redação",exam:"Prova Discursiva",answersheet:"Cartão Resposta"};
function tipoLabel(t){ return TIPO_LABELS[t]||t; }
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
  const oe=a.onlineExams||{}; const oa=a.onlineAttempts||{};
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
    ${bars("Submissões por tipo", Object.entries(s.byType||{}).map(([k,v])=>[tipoLabel(k),v]))}
    ${bars("Distribuição de notas — Redação", Object.entries(g.essayHistogram||{}))}
    ${bars("Correções por modelo", Object.entries(a.byModel||{}))}
    ${modelTable("Tokens por modelo (entrada / saída / total)", a.tokensByModel, false)}
    <h2 style="margin-top:24px">Provas Online</h2>
    <div class="card"><div class="kpis">
      ${kpi("Provas criadas", oe.total||0)}
      ${kpi("Provas respondidas", oa.total||0)}
      ${kpi("Nota média", oa.scoreAvg!=null?(oa.scoreAvg+"%"):"—")}
    </div></div>
    ${bars("Provas criadas por formato", Object.entries(oe.byFormat||{}).map(([k,v])=>[fmtLabel(k),v]))}
    ${bars("Respostas por status", Object.entries(oa.byStatus||{}).map(([k,v])=>[statusLabel(k),v]))}
    ${bars("Respostas por formato", Object.entries(oa.byFormat||{}).map(([k,v])=>[fmtLabel(k),v]))}
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
    <div class="card"><table><tr><th>Protocolo</th><th>ID_Exam</th><th>Status</th><th>Questões lidas</th><th>Data</th><th></th></tr>
    ${items.length?items.map(s=>`<tr class="clk" onclick="viewCartaoDetail('${s.submissionId}')">
      <td>${s.submissionId.slice(0,8)}</td><td>${esc(s.idExam||"—")}</td><td><span class="pill ${s.status}">${s.status}</span></td>
      <td>${nmarks(s)}</td><td>${esc(s.createdAt||"")}</td>
      <td><button class="ghost" title="Excluir tudo" onclick="event.stopPropagation();deleteCartao('${s.submissionId}',false)">🗑</button></td></tr>`).join("")
      :'<tr><td colspan="6" class="muted">Nenhum cartão enviado ainda.</td></tr>'}</table>
    <p class="muted">Clique numa linha para ver as marcações e a imagem. 🗑 remove o cartão (banco + imagem no S3).</p></div>`);
}
// Exclui a submissão por completo (banco + imagem no S3). fromDetail=true volta ao histórico.
async function deleteCartao(id, fromDetail){
  if(!confirm("Excluir este cartão? Remove o registro e a imagem original (S3). Não pode ser desfeito.")) return;
  try{ await api(`/submissions/${id}`,{method:"DELETE"}); viewCartaoHist(); }
  catch(e){ alert(e.message); }
}
let _cart=null;
async function viewCartaoDetail(id){
  h('<div class="card muted">Carregando…</div>');
  let s; try{ s=await api(`/submissions/${id}`); }catch(e){ return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const back=`<button class="ghost" onclick="viewCartaoHist()">← Voltar</button>`;
  if(s.status!=="DONE"){ return h(`${back}<h2>Cartão Resposta</h2><div class="card"><span class="pill ${s.status}">${s.status}</span>
    ${s.status==="FAILED"?`<p class="danger">${esc(s.errorMessage||"Falha")}</p>`:'<p class="muted">Ainda processando. Use ↻ Atualizar em instantes.</p>'}</div>`); }
  _cart={id, readings:((s.result||{}).readings)||[], sel:0, idExam:s.idExam||"",
         templateId:((s.result||{}).templateId)||((s.options||{}).templateId)||""};
  renderCartao();
}
function markLabel(a){ const m=(typeof a==="string")?a:(a&&a.marcada);
  if(m==="-") return '<span style="color:var(--bad);font-weight:600">em branco</span>';
  if(m==="*"){ const ms=(a&&a.marcadas&&a.marcadas.length)?(": "+a.marcadas.map(esc).join(", ")):"";
    return `<span style="color:var(--warn);font-weight:600">⚠ múltiplas${ms}</span>`; }
  return `<b>${esc(m)}</b>`; }
function renderCartao(){
  const c=_cart; const rd=c.readings[c.sel]||c.readings[0]||{answers:[]};
  const back=`<div class="hdr" style="justify-content:space-between">
    <button class="ghost" onclick="viewCartaoHist()">← Voltar</button>
    <button class="ghost" title="Excluir tudo" onclick="deleteCartao('${c.id}',true)">🗑 Excluir cartão</button></div>`;
  const tabs=c.readings.length>1?`<div class="tabs">${c.readings.map((r,i)=>`<button class="tab ${i===c.sel?'on':''}" onclick="selCart(${i})">Leitura ${i+1} · ${esc(mlabel(r.model))}</button>`).join("")}</div>`:"";
  const ans=rd.answers||[];
  const cellCls=a=>{const m=(typeof a==="string")?a:(a&&a.marcada); return m==="*"?"multi":(m==="-"?"blankq":"");};
  const grid=ans.length?`<div class="omr-grid">${ans.map(a=>
      `<div class="omr-q ${cellCls(a)}"><span class="qn">${esc(a.questao)}</span><span class="oa">${markLabel(a)}</span></div>`).join("")}</div>`
    :'<p class="muted">Nenhuma marcação identificada.</p>';
  const foot=(rd.tokensIn||rd.tokensOut)?`<div class="foot">Modelo: ${esc(mlabel(rd.model))} · tokens: ${(rd.tokensIn||0)+(rd.tokensOut||0)}</div>`:"";
  const idline=c.idExam?`<p class="muted">ID_Exam: <b>${esc(c.idExam)}</b></p>`:"";
  h(`${back}<h2>Cartão Resposta</h2>
     <div class="card" id="imgbox">${idline}<button class="sec" onclick="toggleImg('${c.id}')">🖼️ Ver imagem original</button></div>
     ${c.readings.length>1?'<p class="muted">Leituras de modelos diferentes (modo Ambos). Escolha para comparar.</p>':""}
     ${tabs}
     <div class="card"><h3>Alternativas marcadas</h3>${grid}${foot}</div>`);
}
function selCart(i){ _cart.sel=i; renderCartao(); }

// Sobrepõe as marcações lidas no cartão em branco (imagem de referência do template),
// posicionando as bolhas pela mesma geometria do OMR: 🟢 marcada · 🟡 múltiplas · 🔴 em branco.
async function overlayCartao(){
  const box=el("ov-box"), btn=el("ovbtn"), media=el("img-media"); if(!box) return;
  // Toggle: mostra OU a original OU a sobreposta (nunca as duas).
  if(box.dataset.on==="1"){ box.dataset.on="0"; box.innerHTML=""; if(media) media.style.display=""; if(btn) btn.textContent="🎯 Sobrepor marcação"; return; }
  if(!_cart.templateId){ box.innerHTML='<p class="muted">Esta leitura não tem template associado — não há como posicionar as marcações.</p>'; return; }
  box.dataset.on="1"; if(media) media.style.display="none"; if(btn) btn.textContent="✖ Ver imagem original";
  box.innerHTML='<p class="muted">Preparando sobreposição na sua imagem…</p>';
  let t, im;
  try{ t=await api("/card-templates/"+_cart.templateId); }
  catch(e){ box.innerHTML=`<div class="danger">${esc(e.message)}</div>`; return; }
  try{ im=await api("/submissions/"+_cart.id+"/image"); }   // a imagem QUE VOCÊ ENVIOU
  catch(e){ box.innerHTML=`<div class="danger">${esc(e.message)}</div>`; return; }
  if(im.ext==="pdf"){ box.innerHTML='<p class="muted">Sobreposição indisponível para PDF.</p>'; return; }
  const rd=_cart.readings[_cart.sel]||{answers:[]};
  const byQ={}; (rd.answers||[]).forEach(a=>{ byQ[a.questao]=a; });
  const letters=(t.letters&&t.letters.length)?t.letters:null;
  const lidx=L=>{ if(letters){const i=letters.indexOf(L); if(i>=0) return i;} return (L||"").charCodeAt(0)-65; };
  const img=new Image();  // sem crossOrigin: só exibimos (não exportamos o canvas)
  img.onload=()=>{
    const maxW=Math.min(900,(box.clientWidth||900));
    const scale=Math.min(1, maxW/(img.naturalWidth||maxW));
    const W=Math.round((img.naturalWidth||maxW)*scale), H=Math.round((img.naturalHeight||maxW)*scale);
    const cv=document.createElement("canvas"); cv.width=W; cv.height=H;
    const ctx=cv.getContext("2d"); ctx.drawImage(img,0,0,W,H);
    (t.blocks||[]).forEach(b=>{
      const alt=Number(b.alternatives||t.alternatives||5), qs=Number(b.questions||0), first=Number(b.firstQuestion||1);
      const r=b.rect||{}; const bx=(r.x||0)*W, by=(r.y||0)*H, bw=(r.w||0)*W, bh=(r.h||0)*H;
      if(qs<=0||alt<=0||bw<=0||bh<=0) return;
      const rad=Math.max(6, Math.min(bw/alt, bh/qs)*0.42);
      for(let rr=0; rr<qs; rr++){
        const a=byQ[first+rr]; if(!a) continue;
        const cy=by+bh*(rr+0.5)/qs;
        const circle=(c,color)=>{ const cx=bx+bw*(c+0.5)/alt;
          ctx.beginPath(); ctx.arc(cx,cy,rad,0,Math.PI*2); ctx.lineWidth=3; ctx.strokeStyle=color; ctx.stroke(); };
        const m=a.marcada;
        if(m==="-"){ ctx.strokeStyle="#dc2626"; ctx.lineWidth=2; ctx.strokeRect(bx+1, by+bh*rr/qs+1, bw-2, bh/qs-2); }
        else if(m==="*"){ (a.marcadas||[]).forEach(L=>circle(lidx(L),"#d97706")); }
        else { circle(lidx(m),"#16a34a"); }
      }
    });
    cv.style.maxWidth="100%"; cv.style.borderRadius="8px"; cv.style.border="1px solid var(--line)";
    box.innerHTML=""; box.appendChild(cv);
    const leg=document.createElement("p"); leg.className="muted"; leg.style.marginTop="8px";
    leg.textContent="🟢 marcada · 🟡 múltiplas marcações · 🔴 em branco";
    box.appendChild(leg);
  };
  img.onerror=()=>{ box.innerHTML='<p class="danger">Não foi possível carregar a sua imagem enviada.</p>'; };
  img.src=im.url;
}

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
  const s=document.createElement("script"); s.src="/opencv.js?v=4.10.0"; s.async=true;
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

/* ---------------- Provas Online ---------------- */
/* Criação: gera uma prova de múltipla escolha ancorada na Knowledge Base (RAG). */
async function viewOnlineCreate(){
  h(`<h2>Provas Online — Provas</h2>
     <div class="card">
       <h3 style="margin-top:0">Criar nova prova</h3>
       <p class="muted">Informe um tema; a prova é gerada com base no conteúdo do Knowledge Base.</p>
       <label>Título (opcional)</label><input id="po-title" placeholder="Ex.: Arquitetura de Software — Prova 1">
       <label>Tema <span class="muted">(disciplina do KB — ou "Outro" para digitar)</span></label>
       <select id="po-theme-sel" onchange="onlineThemeChange()"><option value="">Carregando temas…</option></select>
       <input id="po-theme-custom" style="display:none;margin-top:8px" autocomplete="off" placeholder="Digite o tema…">
       ${isAdmin()?`<div style="margin-top:6px"><button class="sec" id="po-refresh" onclick="onlineRefreshThemes()">↻ Atualizar temas do KB</button> <span id="po-refmsg" class="muted"></span></div>`:""}
       <div class="row">
         <div><label>Formato</label><select id="po-format">
           <option value="mc">Múltipla escolha</option>
           <option value="discursive">Discursiva</option></select></div>
         <div><label>Nº de questões</label><input id="po-num" type="number" value="5" min="1" max="20"></div>
       </div>
       <div style="margin-top:14px"><button id="po-gen" onclick="onlineGenerate()">✨ Gerar prova</button></div>
     </div><div id="out"></div>
     <div class="hdr" style="justify-content:space-between">
       <h3 style="margin:0">Provas criadas</h3>
       <button class="sec" onclick="onlineLoadExams()">↻ Atualizar</button></div>
     <div id="po-exams" class="card muted">Carregando…</div>`);
  // Popula o seletor de temas do KB (disciplinas). Não bloqueia a tela.
  try{ const r=await api("/online-exams/themes"); _fillThemes(r.themes); }
  catch(e){ const s=el("po-theme-sel"); if(s) s.innerHTML='<option value="__custom__">Outro tema (digitar)…</option>'; onlineThemeChange(); }
  onlineLoadExams();
}
// Lista as provas já criadas (dono/admin), com ações de ver e excluir.
async function onlineLoadExams(){
  const box=el("po-exams"); if(!box) return;
  try{
    const r=await api("/online-exams"+(isAdmin()?"?all=true":""));
    const items=r.items||[];
    box.className="card";
    box.innerHTML = items.length
      ? `<table><tr><th>Título</th><th>Tema</th><th>Tipo</th><th>Questões</th><th>Criada</th><th></th></tr>`+
        items.map(x=>`<tr><td>${esc(x.title||"—")}</td><td>${esc(x.theme||"—")}</td><td>${fmtLabel(x.format)}</td>
          <td>${x.num}</td><td>${esc(x.createdAt||"")}</td>
          <td style="white-space:nowrap">
            <button class="ghost" title="Ver (com gabarito)" onclick="onlineExamView('${x.examId}')">👁</button>
            <button class="ghost" title="Excluir" onclick="onlineDeleteExam('${x.examId}')">🗑</button></td></tr>`).join("")+
        `</table><p class="muted">👁 ver questões e gabarito · 🗑 excluir a prova · para responder, use <a href="#po-teste">Teste de prova</a>.</p>`
      : '<p class="muted">Nenhuma prova criada ainda. Crie a primeira acima.</p>';
  }catch(e){ box.className="card danger"; box.textContent=e.message; }
}
async function onlineExamView(id){
  el("out").innerHTML='<div class="card muted">Carregando prova…</div>';
  try{ const ex=await api(`/online-exams/${id}?full=1`); el("out").innerHTML=onlineExamPreview(ex); window.scrollTo(0,0); }
  catch(e){ el("out").innerHTML=`<div class="card danger">${esc(e.message)}</div>`; }
}
async function onlineDeleteExam(id){
  if(!confirm("Excluir esta prova? As tentativas já respondidas no Histórico não são afetadas.")) return;
  try{ await api(`/online-exams/${id}`,{method:"DELETE"}); el("out").innerHTML=""; onlineLoadExams(); }
  catch(e){ alert(e.message); }
}
function _fillThemes(themes){
  const sel=el("po-theme-sel"); if(!sel) return;
  const groups={};
  (themes||[]).forEach(t=>{ const s=t.semestre||"?"; (groups[s]=groups[s]||[]).push(t); });
  const keys=Object.keys(groups).sort((a,b)=>(parseInt(a)||99)-(parseInt(b)||99));
  let html='<option value="">— selecione um tema —</option>';
  keys.forEach(s=>{ html+=`<optgroup label="Semestre ${esc(s)}">`+
    groups[s].map(t=>`<option value="${esc(t.name)}">${esc(t.name)}</option>`).join("")+`</optgroup>`; });
  html+='<option value="__custom__">Outro tema (digitar)…</option>';
  sel.innerHTML=html;
}
function onlineThemeChange(){
  const sel=el("po-theme-sel"), c=el("po-theme-custom"); if(!sel||!c) return;
  const custom = sel.value==="__custom__";
  c.style.display = custom?"block":"none";
  if(custom) c.focus();
}
// Admin: reindexa os temas lendo os metadados do KB (S3) e atualiza as sugestões.
async function onlineRefreshThemes(){
  const btn=el("po-refresh"), msg=el("po-refmsg");
  if(btn) btn.disabled=true; if(msg) msg.textContent="Reindexando o KB…";
  try{
    const r=await api("/online-exams/themes",{method:"POST"});
    _fillThemes(r.themes);
    if(msg) msg.textContent=`✅ ${r.count} temas atualizados.`;
  }catch(e){ if(msg) msg.textContent=e.message; }
  finally{ if(btn) btn.disabled=false; }
}
async function onlineGenerate(){
  const sel=el("po-theme-sel"); let theme=sel?sel.value:"";
  if(theme==="__custom__") theme=(el("po-theme-custom").value||"").trim();
  theme=(theme||"").trim();
  if(!theme) return alert('Selecione uma disciplina — ou escolha "Outro tema" e digite.');
  const num=Math.max(1,Math.min(20,Number(el("po-num").value)||5));
  const title=(el("po-title").value||"").trim();
  const format=(el("po-format")||{}).value||"mc";
  const btn=el("po-gen"); btn.disabled=true; btn.textContent="Gerando… (pode levar alguns segundos)";
  el("out").innerHTML='<div class="card muted">Consultando o Knowledge Base e gerando questões…</div>';
  try{
    const ex=await api("/online-exams",{method:"POST",body:JSON.stringify({theme,num,title,format})});
    el("out").innerHTML=`<div class="card toast">✅ Prova criada: <b>${esc(ex.title)}</b> (${ex.num} questões).
      Disponível em <a href="#po-teste">Teste de prova</a>.</div>`+onlineExamPreview(ex);
    onlineLoadExams();  // atualiza a lista de provas criadas
  }catch(e){ el("out").innerHTML=`<div class="card danger">${esc(e.message)}</div>`; }
  finally{ btn.disabled=false; btn.textContent="✨ Gerar prova"; }
}
function fmtLabel(f){ return f==="discursive"?"Discursiva":"Múltipla escolha"; }
function onlineExamPreview(ex){
  const disc=ex.format==="discursive";
  const qs=(ex.questoes||[]).map((q,i)=> disc
    ? `<div class="card"><b>Q${i+1}.</b> ${esc(q.enunciado)}
        <div class="fb" style="margin-top:8px"><p class="fb-ok"><b>Resposta de referência:</b> ${esc(q.respostaReferencia||"")}</p></div></div>`
    : `<div class="card"><b>Q${i+1}.</b> ${esc(q.enunciado)}
        <div style="margin-top:6px">${(q.alternativas||[]).map((a,j)=>{
          const L=String.fromCharCode(65+j); const ok=L===q.correta;
          return `<div style="${ok?'color:var(--ok);font-weight:600':''}">${L}) ${esc(a)}${ok?' ✓':''}</div>`;
        }).join("")}</div>
        ${q.explicacao?`<p class="muted" style="margin-top:6px">Explicação: ${esc(q.explicacao)}</p>`:""}</div>`).join("");
  const src=(ex.kbSources||[]).map(s=>`<li>${esc(s.title||s.uri)}${s.page?` — página ${s.page}`:""}</li>`).join("");
  return `<h3>${esc(ex.title||"Prova")}</h3>
    <p class="muted" style="margin-top:-6px">Prévia com gabarito · ${fmtLabel(ex.format)}${ex.theme?` · tema: ${esc(ex.theme)}`:""}</p>${qs}
    ${src?`<div class="card"><b>Fontes no Knowledge Base:</b><ul>${src}</ul></div>`:""}`;
}

/* Teste de prova: seleciona prova, responde (sem gabarito) e envia p/ correção server-side. */
let _po=null;
async function viewOnlineTest(){
  h(`<div class="hdr"><h2>Provas Online — Teste de prova</h2>
     <button class="sec" onclick="viewOnlineTest()">↻ Atualizar</button></div><div class="card muted">Carregando…</div>`);
  let r; try{ r=await api("/online-exams"+(isAdmin()?"?all=true":"")); }
  catch(e){ return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const items=(r.items||[]);
  h(`<div class="hdr"><h2>Provas Online — Teste de prova</h2>
     <button class="sec" onclick="viewOnlineTest()">↻ Atualizar</button></div>
     <div class="card"><label>Escolha a prova</label>
       <select id="po-sel">${items.length?items.map(x=>`<option value="${x.examId}">${esc(x.title||x.theme||x.examId)} · ${x.num} questões · ${fmtLabel(x.format)}</option>`).join(""):'<option value="">— nenhuma prova criada —</option>'}</select>
       <div style="margin-top:12px"><button ${items.length?"":"disabled"} onclick="onlineStart()">Iniciar prova</button></div>
     </div><div id="po-quiz"></div>`);
}
async function onlineStart(){
  const id=el("po-sel").value; if(!id) return;
  el("po-quiz").innerHTML='<div class="card muted">Carregando questões…</div>';
  let ex; try{ ex=await api(`/online-exams/${id}`); }
  catch(e){ return el("po-quiz").innerHTML=`<div class="card danger">${esc(e.message)}</div>`; }
  _po={examId:id, format:ex.format||"mc", questoes:ex.questoes||[]};
  const disc=_po.format==="discursive";
  const qs=_po.questoes.map(q=> disc
    ? `<div class="card"><b>Q${q.n}.</b> ${esc(q.enunciado)}
        <textarea id="qa-${q.n}" rows="5" style="margin-top:8px" placeholder="Escreva sua resposta…"></textarea></div>`
    : `<div class="card"><b>Q${q.n}.</b> ${esc(q.enunciado)}
        <div class="radios" style="margin-top:8px">${(q.alternativas||[]).map((a,j)=>{const L=String.fromCharCode(65+j);
          return `<label class="rb"><input type="radio" name="q${q.n}" value="${L}"><b>${L})</b> <span>${esc(a)}</span></label>`;}).join("")}</div></div>`).join("");
  el("po-quiz").innerHTML=`<h3>${esc(ex.title||"Prova")} <span class="muted">· ${fmtLabel(_po.format)}</span></h3>${qs}
    <div class="card"><button onclick="onlineSubmit()">Enviar respostas</button>
    <span class="muted">${disc?"A correção é feita por IA (nota e justificativa por questão).":"A correção é feita no servidor."}</span></div><div id="po-res"></div>`;
}
async function onlineSubmit(){
  if(!_po) return;
  const disc=_po.format==="discursive";
  const answers={};
  _po.questoes.forEach((q,i)=>{
    if(disc){ const t=el(`qa-${q.n}`); if(t && t.value.trim()) answers[i]=t.value.trim(); }
    else { const sel=document.querySelector(`input[name="q${q.n}"]:checked`); if(sel) answers[i]=sel.value; }
  });
  el("po-res").innerHTML='<div class="card muted">Enviando respostas…</div>';
  try{
    // A correção é assíncrona: recebe a tentativa em PROCESSING e acompanha o status.
    const r=await api(`/online-exams/${_po.examId}/attempts`,{method:"POST",body:JSON.stringify({answers})});
    await onlinePoll(r.attemptId, el("po-res"));
  }catch(e){ el("po-res").innerHTML=`<div class="card danger">${esc(e.message)}</div>`; }
}
// Acompanha a correção (PROCESSING→DONE/FAILED). Renderiza o resultado quando concluir.
async function onlinePoll(attemptId, box, tries){
  tries = tries||0;
  box.innerHTML=`<div class="card muted">⏳ Corrigindo… a tentativa está sendo processada.
    <span class="muted">Você também pode acompanhar em <a href="#po-hist">Histórico</a>.</span></div>`;
  let att; try{ att=await api(`/online-attempts/${attemptId}`); }
  catch(e){ box.innerHTML=`<div class="card danger">${esc(e.message)}</div>`; return; }
  const st=att.status||"DONE";
  if(st==="PROCESSING"){
    if(tries>=40){ box.innerHTML=`<div class="card muted">Ainda processando. Veja em <a href="#po-hist">Histórico</a> em instantes.</div>`; return; }
    setTimeout(()=>onlinePoll(attemptId, box, tries+1), 3000);
    return;
  }
  if(st==="FAILED"){ box.innerHTML=`<div class="card danger">A correção falhou: ${esc(att.errorMessage||"erro")}.</div>`; return; }
  const disc=att.format==="discursive";
  const head=disc?`Nota <b>${att.notaTotal}/${att.notaMaxima}</b> (${att.score}%)`:`<b>${att.acertos}/${att.total}</b> (${att.score}%)`;
  box.innerHTML=`<div class="card toast">✅ Correção concluída — ${head}.
    Veja também em <a href="#po-hist">Histórico</a>.</div>`+onlineResultDetail(att);
  window.scrollTo(0,document.body.scrollHeight);
}

// Abre/fecha a visualização do conteúdo da apostila e gera o link temporário (presigned).
async function kbView(btn, vid, encUri, page){
  const box=el(vid); if(!box) return;
  if(!box.hasAttribute("hidden")){ box.setAttribute("hidden",""); btn.textContent="👁️ Ver conteúdo"; return; }
  box.removeAttribute("hidden"); btn.textContent="Ocultar";
  const links=box.querySelector(".kblinks");
  if(links && !links.dataset.loaded){
    links.textContent="Gerando link temporário…";
    try{
      const r=await api("/online-exams/kb-doc?uri="+encUri);
      const base=r.url, atPage=page?`${base}#page=${page}`:base;
      links.innerHTML=`<a href="${atPage}" target="_blank" rel="noopener">📄 Abrir apostila${page?` na página ${page}`:""}</a>
        &nbsp;·&nbsp; <a href="${base}" target="_blank" rel="noopener" download>⬇ Baixar apostila (link temporário)</a>`;
      links.dataset.loaded="1";
    }catch(e){ links.innerHTML=`<span class="danger">${esc(e.message)}</span>`; }
  }
}

/* Histórico: lista tentativas; detalhe mostra acertos/erros + estudo no KB p/ as erradas. */
async function viewOnlineHist(){
  h(`<div class="hdr"><h2>Provas Online — Histórico</h2>
     <button class="sec" onclick="viewOnlineHist()">↻ Atualizar</button></div><div class="card muted">Carregando…</div>`);
  let r; try{ r=await api("/online-attempts"+(isAdmin()?"?all=true":"")); }
  catch(e){ return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const items=(r.items||[]);
  h(`<div class="hdr"><h2>Provas Online — Histórico</h2>
     <button class="sec" onclick="viewOnlineHist()">↻ Atualizar</button></div>
     <div class="card"><table><tr><th>Prova</th><th>Tema</th><th>Tipo</th><th>Status</th><th>Resultado</th><th>Nota</th><th>Data</th><th></th></tr>
     ${items.length?items.map(a=>{const st=a.status||"DONE"; const done=st==="DONE";
       return `<tr class="clk" onclick="viewOnlineAttempt('${a.attemptId}')">
       <td>${esc(a.title||"—")}</td><td>${esc(a.theme||"—")}</td><td>${fmtLabel(a.format)}</td>
       <td><span class="pill ${statusPill(st)}">${statusLabel(st)}</span></td>
       <td>${done?`${a.acertos}/${a.total}`:"—"}</td><td>${done?`<b>${a.score}%</b>`:"—"}</td>
       <td>${esc(a.createdAt||"")}</td>
       <td><button class="ghost" title="Excluir" onclick="event.stopPropagation();onlineDeleteAttempt('${a.attemptId}')">🗑</button></td></tr>`;}).join("")
       :'<tr><td colspan="8" class="muted">Nenhuma prova respondida ainda.</td></tr>'}</table>
     <p class="muted">Clique numa linha para ver acertos/notas e o que estudar. Provas em processamento aparecem como "Processando".</p></div>`);
}
// Exclui uma prova respondida do histórico (dono ou admin).
async function onlineDeleteAttempt(id, fromDetail){
  if(!confirm("Excluir esta prova respondida do histórico? Esta ação não pode ser desfeita.")) return;
  try{ await api(`/online-attempts/${id}`,{method:"DELETE"}); viewOnlineHist(); }
  catch(e){ alert(e.message); }
}
function statusLabel(s){ return s==="PROCESSING"?"Processando":(s==="FAILED"?"Falhou":"Concluída"); }
function statusPill(s){ return s==="PROCESSING"?"QUEUED":(s==="FAILED"?"bad":"ok"); }
async function viewOnlineAttempt(id){
  h('<div class="card muted">Carregando…</div>');
  _studyDebug=[];  // reinicia o log de debug ao abrir a tentativa
  let att; try{ att=await api(`/online-attempts/${id}`); }
  catch(e){ return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const back=`<div class="hdr" style="justify-content:space-between">
    <button class="ghost" onclick="viewOnlineHist()">← Voltar</button>
    <button class="ghost" title="Excluir" onclick="onlineDeleteAttempt('${id}')">🗑 Excluir</button></div>`;
  const st=att.status||"DONE";
  if(st==="PROCESSING"){
    return h(`${back}<h2>${esc(att.title||"Prova")} <span class="muted">· ${fmtLabel(att.format)}</span></h2>
      <div class="card"><span class="pill QUEUED">Processando</span>
      <p class="muted">A correção está sendo processada. Atualize em instantes.</p>
      <button class="sec" onclick="viewOnlineAttempt('${id}')">↻ Atualizar</button></div>`);
  }
  if(st==="FAILED"){
    return h(`${back}<h2>${esc(att.title||"Prova")}</h2>
      <div class="card danger">A correção falhou: ${esc(att.errorMessage||"erro")}.</div>`);
  }
  const disc=att.format==="discursive";
  const res=disc?`Nota <b>${att.notaTotal}/${att.notaMaxima}</b> (${att.score}%)`:`Acertos <b>${att.acertos}/${att.total}</b> (${att.score}%)`;
  h(`${back}
     <h2>${esc(att.title||"Prova")} <span class="muted">· ${fmtLabel(att.format)}</span></h2>
     <div class="card">${res} · Tema: ${esc(att.theme||"—")}</div>
     ${onlineResultDetail(att)}
     <details class="evdet" id="dbg" style="margin-top:16px">
       <summary>🐞 Debug — o que é enviado à API no "Sugerir material" (clique para expandir)</summary>
       <div id="dbg-body"></div>
     </details>`);
  _renderStudyDebug();
}
function _altText(q, letter){
  if(!letter) return "";
  const i=letter.charCodeAt(0)-65;
  return (q.alternativas||[])[i]||"";
}
// Bloco "Onde estudar": trechos da apostila + página + visualização com link temporário.
// Botão de sugestão sob demanda (só para questões erradas). A busca no KB é uma API à parte.
function _studyPlaceholder(aid, n){
  return `<div class="kbref-wrap">
    <button class="sec" id="sg-${n}" onclick="onlineSuggest(this,'${aid}',${n})">📚 Sugerir material de estudo</button>
    <div id="study-${n}" style="margin-top:8px"></div></div>`;
}
let _studyDebug=[];  // log das chamadas de "Sugerir material" (modo debug)
async function onlineSuggest(btn, aid, n){
  btn.disabled=true; const t=btn.textContent; btn.textContent="Buscando no KB…";
  const path=`/online-attempts/${aid}/study?debug=1`;
  const body={n};
  // Requisição HTTP real que o api() dispara (URL com base /api + headers).
  const clientReq={
    method:"POST",
    url:(API||"/api")+path,
    headers:{
      "Content-Type":"application/json",
      "Authorization":"Bearer "+(ID_TOKEN?(ID_TOKEN.slice(0,16)+"…(JWT Cognito, truncado)"):"—"),
    },
    body,
  };
  try{
    const r=await api(path,{method:"POST",body:JSON.stringify(body)});
    const box=el(`study-${n}`);
    if(box) box.innerHTML=(r.study&&r.study.length)
      ? `<div class="kbref-title">📚 Onde estudar o conteúdo correto:</div>`+_studySourcesHtml(r.study, n)
      : '<p class="muted">Nenhum material encontrado no Knowledge Base para esta questão.</p>';
    btn.style.display="none";
    // Modo debug: registra o que o front enviou e o que a API enviou ao KB.
    _studyDebug.push({n, at:new Date().toLocaleTimeString(),
      clientRequest:clientReq,
      apiToKb:(r.debug&&r.debug.kbRetrieve)||null,
      postProcessing:(r.debug&&r.debug.postProcessing)||"",
      resultado:(r.study||[]).map(s=>({titulo:s.title, arquivo:(s.uri||"").split("/").pop(), pagina:s.page}))});
    _renderStudyDebug(); const d=el("dbg"); if(d) d.open=true;
  }catch(e){ alert(e.message); btn.disabled=false; btn.textContent=t; }
}
function _renderStudyDebug(){
  const box=el("dbg-body"); if(!box) return;
  if(!_studyDebug.length){ box.innerHTML='<p class="muted">Clique em "Sugerir material" numa questão errada para ver o que é enviado à API.</p>'; return; }
  box.innerHTML=_studyDebug.map((d,i)=>`<div class="kbref">
    <div class="muted">#${i+1} · Questão ${d.n} · ${esc(d.at)}</div>
    <div class="ansl">1) Front-end → API</div>
    <pre class="dbgjson">${esc(JSON.stringify(d.clientRequest,null,2))}</pre>
    <div class="ansl">2) API → Knowledge Base (Bedrock Retrieve)</div>
    <pre class="dbgjson">${esc(JSON.stringify(d.apiToKb,null,2))}</pre>
    ${d.postProcessing?`<p class="muted">Pós-processamento: ${esc(d.postProcessing)}</p>`:""}
    <div class="ansl">3) Resultado retornado</div>
    <pre class="dbgjson">${esc(JSON.stringify(d.resultado,null,2))}</pre>
  </div>`).join("");
}
function _studySourcesHtml(sources, n){
  return (sources||[]).map((s,si)=>{const vid=`kbv-${n}-${si}`; const pg=s.page?` — página ${s.page}`:"";
    const file=(s.uri||"").split("/").pop();
    return `<div class="kbref">
      <div class="row" style="justify-content:space-between;align-items:center;gap:8px">
        <div>📖 <b>${esc(s.title||s.uri)}</b><span class="muted">${pg}</span>
          ${file?`<div class="muted" style="font-size:12px">📄 ${esc(file)}</div>`:""}</div>
        <button class="sec" onclick="kbView(this,'${vid}','${encodeURIComponent(s.uri||"")}',${s.page||0})">👁️ Ver conteúdo</button>
      </div>
      <div id="${vid}" class="kbviewer" hidden>
        ${s.snippet?`<div class="kbsnippet">${_fmtKb(s.snippet)}</div>`:""}
        <div class="kblinks muted"></div>
      </div>
    </div>`;}).join("");
}
// Formata o trecho cru do PDF: blocos (runs de 2+ espaços) viram parágrafos; títulos
// numerados / em caixa-alta viram cabeçalhos. Normaliza espaços repetidos.
function _fmtKb(text){
  const parts=String(text||"").replace(/\r/g,"").split(/\s{2,}/).map(s=>s.trim()).filter(Boolean);
  if(!parts.length) return "";
  return parts.map(p=>{
    const isHeading = /^\d+(\.\d+)*\.?\s+\S/.test(p) || /^[A-ZÀ-Ú][A-ZÀ-Ú0-9 ]{3,}$/.test(p);
    return isHeading ? `<div class="kbh">${esc(p)}</div>` : `<p>${esc(p)}</p>`;
  }).join("");
}
function _mcResultCard(q, aid){
  const cls=q.acertou?"ok":"bad";
  const alts=(q.alternativas||[]).map((a,j)=>{const L=String.fromCharCode(65+j);
    const isC=L===q.correta, isM=L===q.marcada;
    const style=isC?"color:var(--ok);font-weight:600":(isM&&!q.acertou?"color:var(--bad);font-weight:600":"");
    return `<div style="${style}">${L}) ${esc(a)}${isC?' ✓ (correta)':''}${isM&&!isC?' ✗ (sua resposta)':''}</div>`;
  }).join("");
  const feedback = q.acertou ? "" : `<div class="fb">
    <p class="fb-bad">❌ Sua resposta: ${q.marcada?`<b>${q.marcada})</b> ${esc(_altText(q,q.marcada))}`:"<b>não respondida</b>"} — incorreta.</p>
    <p class="fb-ok">✅ Resposta correta: <b>${q.correta})</b> ${esc(_altText(q,q.correta))}</p>
    ${q.explicacao?`<p><b>Justificativa:</b> ${esc(q.explicacao)}</p>`:""}</div>`;
  return `<div class="card"><div><span class="pill ${cls}">${q.acertou?"ACERTOU":"ERROU"}</span>
    <b> Q${q.n}.</b> ${esc(q.enunciado)}</div>
    <div style="margin-top:8px">${alts}</div>
    ${feedback}${q.acertou?"":_studyPlaceholder(aid, q.n)}</div>`;
}
function _discResultCard(q, aid){
  const nmax=Number(q.notaMaxima)||10, nota=Number(q.nota)||0;
  const good=nmax>0 && (nota/nmax)>=0.6;
  const cls=good?"ok":"bad";
  return `<div class="card"><div><span class="pill ${cls}">${nota}/${nmax}</span>
    <b> Q${q.n}.</b> ${esc(q.enunciado)}</div>
    <div class="fb" style="margin-top:8px">
      <p><b>Sua resposta:</b> ${q.respostaAluno?esc(q.respostaAluno):"<span class='fb-bad'>não respondida</span>"}</p>
      ${q.justificativa?`<hr class="sep"><p><b>Avaliação:</b> ${esc(q.justificativa)}</p>`:""}
      ${q.respostaReferencia?`<hr class="sep"><p class="fb-ok"><b>Resposta de referência:</b> ${esc(q.respostaReferencia)}</p>`:""}
    </div>
    ${good?"":_studyPlaceholder(aid, q.n)}</div>`;
}
function onlineResultDetail(att){
  const disc=att.format==="discursive"; const aid=att.attemptId;
  return (att.results||[]).map(q=> disc?_discResultCard(q, aid):_mcResultCard(q, aid)).join("");
}

/* ---------------- Entrevistador Virtual (4 submenus, nativo) ---------------- */
// UI servida do S3 (parte do portal); o Fargate atende só WebSocket/API. Cada submenu
// injeta seu fragmento + carrega scripts + chama a init correspondente.
const _EA = "/entrevistador-assets";
function _loadEntScript(src){
  return new Promise((res,rej)=>{
    if(document.querySelector(`script[data-ent="${src}"]`)) return res();
    const s=document.createElement("script"); s.src=src; s.dataset.ent=src;
    s.onload=()=>res(); s.onerror=()=>rej(new Error("Falha ao carregar "+src));
    document.head.appendChild(s);
  });
}
function _entCss(){
  if(!document.getElementById("ent-css")){
    const l=document.createElement("link"); l.id="ent-css"; l.rel="stylesheet"; l.href=`${_EA}/interview.css`;
    document.head.appendChild(l);
  }
}
async function _entRender(fragment, scripts, initFn){
  _entCss();
  h(`<div class="card muted">Carregando…</div>`);
  try{
    const html = await (await fetch(`${_EA}/${fragment}`)).text();
    el("view").innerHTML = html;
    for(const s of scripts) await _loadEntScript(`${_EA}/${s}`);
    if(initFn){ if(typeof window[initFn]==="function") window[initFn](); else throw new Error(initFn+" indisponível"); }
  }catch(e){ h(`<h2>Entrevistador Virtual</h2><div class="card danger">Falha ao carregar: ${esc(e.message)}</div>`); }
}
function viewEntEntrevista(){ return _entRender("interview.html", ["avatar.js","app.js"], "initInterviewer"); }
function viewEntVagas(){ return _entRender("vagas.html", ["ent-modules.js"], "initVagas"); }
function viewEntAvatar(){ return _entRender("avatar.html", ["avatar.js","ent-modules.js"], "initAvatar"); }
function viewEntRelatorio(){ return _entRender("relatorio.html", ["ent-modules.js"], "initRelatorio"); }

/* ---------------- Atendimento (Amazon Connect) ----------------
   O embed em iframe é bloqueado pela CSP (frame-ancestors) da instância my.connect.aws,
   mesmo com o domínio nos Approved Origins. Por isso abrimos o painel do Connect em janela
   dedicada (voz + WhatsApp + chat + tasks funcionam 100% lá). */
const CONNECT_INSTANCE_URL = "https://connect-demo-ps.my.connect.aws";
const CONNECT_WORKSPACE_URL = CONNECT_INSTANCE_URL + "/agent-app-v2/";

function viewAtendimentoChat(){
  h(`<div class="hdr"><h2>Atendimento — Chat</h2></div>
     <div class="card">
       <p>O painel de atendimento do <b>Amazon Connect</b> (voz, WhatsApp, chat e tasks) abre em uma janela dedicada.</p>
       <p class="muted">No 1º acesso, faça login no Connect e permita o microfone para atender chamadas de voz.</p>
       <div class="row" style="margin-top:1rem">
         <button onclick="window.open('${CONNECT_WORKSPACE_URL}','connectWorkspace','width=1280,height=880')">Abrir painel de atendimento ↗</button>
       </div>
     </div>`);
}

/* ---------------- Atendimento — Templates WhatsApp & Campanhas (via /atendimento/api) ----------------
   Backend serverless (Lambda) que porta o campaign_tester: End User Messaging Social +
   Customer Profiles + Connect Outbound Campaigns. O browser fala só com o Router (JWT do portal). */
const ATEND = "/atendimento/api";
async function atendApi(path, opts = {}, _retried) {
  const r = await fetch(ATEND + path, { ...opts, headers: {
    "Content-Type": "application/json", "Authorization": "Bearer " + ID_TOKEN, ...(opts.headers || {}) } });
  if (r.status === 401 && !_retried) {
    if (await refreshToken()) return atendApi(path, opts, true);
    login(); throw new Error("Sessão expirada. Redirecionando para o login…");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
  return data;
}
async function _atendTemplates(){
  if (!window._atendTpls) window._atendTpls = await atendApi("/templates");
  return window._atendTpls;
}
function _atendTplOptions(tpls){
  return (tpls.templates || []).map(t =>
    `<option value="${esc(t.metaTemplateId)}" data-name="${esc(t.name)}" data-lang="${esc(t.language)}" data-status="${esc(t.status)}">`
    + `${esc(t.name)} [${esc(t.status)}] (${esc(t.language)})</option>`).join("");
}

// ---- Testador de templates (preview + envio 1-a-1 transacional) ----
async function viewAtendTemplates(){
  h(`<div class="hdr"><h2>Atendimento — Templates WhatsApp</h2>
       <span class="muted">preview do template + envio 1-a-1 (transacional) via Amazon Connect / End User Messaging</span></div>
     <div class="card muted">Carregando templates…</div>`);
  let tpls;
  try { tpls = await _atendTemplates(); }
  catch(e){ return h(`<div class="card danger">${esc(e.message)}</div>`); }
  h(`<div class="hdr"><h2>Atendimento — Templates WhatsApp</h2>
       <span class="muted">${(tpls.templates||[]).length} templates na WABA · envio 1-a-1 transacional</span></div>
     <div class="card">
       <div class="row"><label>Template:</label>
         <select id="at-tpl" onchange="atTplLoad()" style="flex:1">${_atendTplOptions(tpls)}</select></div>
       <div id="at-detail" class="muted" style="margin-top:8px">Selecione um template.</div>
       <div class="row" style="margin-top:10px">
         <div style="flex:1"><label>Telefone (com DDI, ex: +5511985743177)</label>
           <input id="at-to" placeholder="+55..."></div>
         <div style="align-self:flex-end"><button class="btn" onclick="atSend()">Enviar</button></div>
       </div>
       <div id="at-sendout" style="margin-top:8px"></div>
     </div>`);
  atTplLoad();
}
async function atTplLoad(){
  const sel = el("at-tpl"); const id = sel && sel.value;
  const box = el("at-detail");
  if (!id){ box.innerHTML = "Selecione um template."; return; }
  box.classList.remove("muted"); box.innerHTML = "carregando definição…";
  let d;
  try { d = await atendApi("/template?metaTemplateId=" + encodeURIComponent(id)); }
  catch(e){ box.innerHTML = `<span class="danger">${esc(e.message)}</span>`; return; }
  let html = "";
  for (const p of (d.parts||[])){
    if (p.component === "body" || p.component === "header"){
      html += `<label>${p.component.toUpperCase()}</label><div class="preview">${esc(p.text||"")}</div>`;
      (p.indices||[]).forEach((idx,i)=>{
        const exv = (p.examples && p.examples[i]) ? p.examples[i] : "";
        html += `<div style="margin-top:6px"><label>Variável {{${idx}}} <span class="muted">(${p.component})</span></label>`
              + `<input data-comp="${p.component}" data-idx="${idx}" value="${esc(exv)}"></div>`;
      });
    } else if (p.component === "footer"){
      html += `<label>FOOTER</label><div class="preview">${esc(p.text||"")}</div>`;
    } else if (p.component === "buttons"){
      html += `<label>BOTÕES</label><div class="preview">${esc((p.buttons||[]).join(" | "))}</div>`;
    }
  }
  const nvars = (d.parts||[]).reduce((a,p)=>a+((p.indices||[]).length),0);
  if (!nvars) html += `<p class="muted">Este template não tem variáveis.</p>`;
  box.innerHTML = html;
}
async function atSend(){
  const sel = el("at-tpl"); if (!sel || !sel.value) return alert("selecione um template");
  const opt = sel.options[sel.selectedIndex];
  const to = (el("at-to").value||"").trim();
  if (!to) return alert("informe o telefone (com DDI)");
  const byComp = {};
  [...document.querySelectorAll('#at-detail input[data-comp]')].forEach(inp=>{
    const c = inp.getAttribute("data-comp"), idx = parseInt(inp.getAttribute("data-idx"));
    (byComp[c] = byComp[c] || []).push({idx, val: inp.value});
  });
  for (const c in byComp) byComp[c].sort((a,b)=>a.idx-b.idx);
  const out = el("at-sendout"); out.innerHTML = "enviando…";
  try {
    const d = await atendApi("/send", { method:"POST", body: JSON.stringify({
      to, metaTemplateId: sel.value, name: opt.dataset.name, language: opt.dataset.lang,
      header: (byComp.header||[]).map(x=>x.val), bodyVars: (byComp.body||[]).map(x=>x.val) }) });
    out.innerHTML = `<span style="color:green">enviado! messageId: <code>${esc(d.messageId||"?")}</code></span>`;
  } catch(e){ out.innerHTML = `<span class="danger">${esc(e.message)}</span>`; }
}

// ---- Campanhas (CSV -> Connect Outbound Campaigns) ----
function _atendParseCSV(text){
  const rows=[]; let i=0, field="", row=[], inq=false;
  while(i<text.length){ const c=text[i];
    if(inq){ if(c==='"'){ if(text[i+1]==='"'){field+='"';i++;} else inq=false; } else field+=c; }
    else { if(c==='"') inq=true;
      else if(c===',') { row.push(field); field=""; }
      else if(c==='\n'||c==='\r'){ if(c==='\r'&&text[i+1]==='\n')i++; row.push(field); rows.push(row); row=[]; field=""; }
      else field+=c; }
    i++; }
  if(field!==""||row.length){ row.push(field); rows.push(row); }
  return rows.map(r=>r.map(x=>x.trim())).filter(r=>r.some(x=>x!==""));
}
async function viewAtendCampanhas(){
  h(`<div class="hdr"><h2>Atendimento — Campanhas WhatsApp</h2>
       <span class="muted">disparo por CSV via Amazon Connect Outbound Campaigns (fiel ao arquivo)</span></div>
     <div class="card muted">Carregando templates…</div>`);
  let tpls;
  try { tpls = await _atendTemplates(); }
  catch(e){ return h(`<div class="card danger">${esc(e.message)}</div>`); }
  h(`<div class="hdr"><h2>Atendimento — Campanhas WhatsApp</h2>
       <span class="muted">cria uma campanha nova por disparo (segmento dedicado, fiel ao CSV)</span></div>
     <div class="card">
       <div class="row"><label>Template da campanha:</label>
         <select id="ac-tpl" onchange="acFmt()" style="flex:1">${_atendTplOptions(tpls)}</select></div>
       <div id="ac-fmt" class="muted" style="margin-top:8px"></div>
       <label style="margin-top:10px">Nome da campanha</label>
       <input id="ac-name" placeholder="ex: promo-vestibular (a data/hora é adicionada automaticamente)">
       <label style="margin-top:10px">Arquivo CSV</label>
       <input type="file" id="ac-file" accept=".csv,text/csv" onchange="acCsv()">
       <div id="ac-prev" style="margin-top:8px"></div>
       <button class="btn" id="ac-btn" onclick="acSend()" disabled style="margin-top:10px">Disparar campanha</button>
       <div id="ac-out" style="margin-top:8px"></div>
     </div>
     <div class="card"><p class="muted">⚠️ Disparar cria uma campanha real no Amazon Connect e envia WhatsApp
       aos contatos do CSV (só templates <b>APPROVED</b>). O envio sai ~5–6 min após a criação (mínimo do schedule da API).</p></div>`);
  acFmt();
}
let _acFmt = null, _acCsv = null;
async function acFmt(){
  const sel = el("ac-tpl"); const id = sel && sel.value;
  const box = el("ac-fmt");
  el("ac-btn").disabled = true; _acCsv = null; el("ac-prev").innerHTML = "";
  try { _acFmt = await atendApi("/campaign/format" + (id ? "?metaTemplateId=" + encodeURIComponent(id) : "")); }
  catch(e){ box.innerHTML = `<span class="danger">${esc(e.message)}</span>`; return; }
  box.classList.remove("muted");
  let h2 = `<p>Colunas esperadas no CSV (coluna <code>phone</code> obrigatória, com DDI):</p>`
         + `<div class="preview">${esc((_acFmt.columns||["phone"]).join(","))}</div>`;
  if ((_acFmt.legend||[]).length){
    h2 += `<table><thead><tr><th>coluna</th><th>variável</th><th>onde</th><th>exemplo</th></tr></thead><tbody>`
        + _acFmt.legend.map(l=>`<tr><td><code>${esc(l.column)}</code></td><td>${esc(l.placeholder)}</td><td>${esc(l.component)}</td><td>${esc(l.example||"")}</td></tr>`).join("")
        + `</tbody></table>`;
  } else { h2 += `<p class="muted">Este template não tem variáveis (basta a coluna <code>phone</code>).</p>`; }
  box.innerHTML = h2;
}
function acCsv(){
  const f = el("ac-file").files[0]; const box = el("ac-prev");
  el("ac-btn").disabled = true; _acCsv = null;
  if (!f){ box.innerHTML = ""; return; }
  const rd = new FileReader();
  rd.onload = () => {
    const grid = _atendParseCSV(rd.result);
    if (grid.length < 2){ box.innerHTML = `<span class="danger">CSV vazio ou sem linhas de dados</span>`; return; }
    const header = grid[0], rows = grid.slice(1);
    _acCsv = { header, rows, text: rd.result, filename: f.name };
    const phoneCol = (_acFmt && _acFmt.phone) || "phone";
    const pIdx = header.findIndex(x=>x.toLowerCase()===phoneCol.toLowerCase());
    const problemas = [];
    if (pIdx < 0) problemas.push(`falta a coluna obrigatória "${phoneCol}"`);
    let semTel = 0; rows.forEach(r=>{ if (pIdx>=0 && !((r[pIdx]||"").trim())) semTel++; });
    if (semTel) problemas.push(`${semTel} linha(s) sem telefone`);
    let t = `<table><thead><tr>${header.map(x=>`<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>`
          + rows.slice(0,20).map(r=>`<tr>${header.map((_,i)=>`<td>${esc(r[i]||"")}</td>`).join("")}</tr>`).join("")
          + `</tbody></table>`;
    if (rows.length>20) t += `<p class="muted">… +${rows.length-20} linha(s)</p>`;
    let msg = `<p>${rows.length} contato(s).</p>`;
    if (problemas.length) msg += `<p class="danger">${esc(problemas.join(" | "))}</p>`;
    else msg += `<p style="color:green">CSV válido</p>`;
    box.innerHTML = msg + t;
    el("ac-btn").disabled = problemas.length > 0;
  };
  rd.readAsText(f);
}
async function acSend(){
  if (!_acCsv) return alert("selecione um CSV");
  const sel = el("ac-tpl"); const nome = (el("ac-name").value||"").trim();
  if (!nome) return alert("informe o nome da campanha");
  if (!confirm(`Disparar a campanha "${nome}" para ${_acCsv.rows.length} contato(s)? Isso cria uma campanha real e envia WhatsApp.`)) return;
  const out = el("ac-out"); out.innerHTML = "disparando (criando campanha nova + enviando)…";
  try {
    const d = await atendApi("/campaign/send", { method:"POST", body: JSON.stringify({
      csv: _acCsv.text, filename: _acCsv.filename, metaTemplateId: sel.value, campaignName: nome }) });
    const c = d.campaign || {};
    let m = `<p style="color:green">${d.gravados}/${d.total} perfis · ${d.destinatarios||0} destinatário(s) único(s)</p>`;
    if (c.error) m += `<p class="danger">campanha: ${esc(c.error)}</p>`;
    else if (c.campaignId) m += `<p style="color:green">campanha criada: <code>${esc(c.campaignName||"")}</code> · id <code>${esc(c.campaignId)}</code></p>`;
    else if (c.pending) m += `<p class="muted">campanha NÃO criada — template ${esc(c.status||"PENDENTE")} na Meta.</p>`;
    m += `<p class="muted">CSV no S3: <code>${esc(d.s3||"")}</code>. Envio sai ~5–6 min após a criação.</p>`;
    if ((d.erros||[]).length) m += `<p class="danger">${esc(d.erros.join(" | "))}</p>`;
    out.innerHTML = m;
  } catch(e){ out.innerHTML = `<span class="danger">${esc(e.message)}</span>`; }
}

/* ---------------- Orientador Acadêmico (Neptune + AgentCore, via /orientador/api) ---------------- */
const ORI = "/orientador/api";
let _oriBoot = null;

async function oriApi(path, opts = {}, _retried) {
  const r = await fetch(ORI + path, { ...opts, headers: {
    "Content-Type": "application/json", "Authorization": "Bearer " + ID_TOKEN, ...(opts.headers || {}) } });
  if (r.status === 401 && !_retried) {
    // Mesmo comportamento do api(): token expirado -> renova em silêncio e repete; senão, login.
    if (await refreshToken()) return oriApi(path, opts, true);
    login(); throw new Error("Sessão expirada. Redirecionando para o login…");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
  return data;
}

async function oriBoot() {
  if (!_oriBoot) _oriBoot = await oriApi("/bootstrap");
  return _oriBoot.result || _oriBoot;
}

function _oriStudentSelect(boot, id, withCoord) {
  const pName = {}; (boot.programs || []).forEach(p => { pName[p.id] = p.name; });
  const byProg = {};
  (boot.students || []).forEach(s => { (byProg[s.program] = byProg[s.program] || []).push(s); });
  const groups = Object.keys(byProg)
    .sort((a, b) => (pName[a] || a).localeCompare(pName[b] || b))
    .map(pid => {
      const opts = byProg[pid].slice()
        .sort((a, b) => (a.name || "").localeCompare(b.name || ""))
        .map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join("");
      return `<optgroup label="${esc(pName[pid] || pid)}">${opts}</optgroup>`;
    }).join("");
  // Modo coordenação (só no chat): pergunta sobre TODOS os alunos/cursos.
  const coord = withCoord
    ? `<optgroup label="Coordenação"><option value="__coord__">👤 Coordenador do curso (todos os alunos)</option></optgroup>`
    : "";
  return `<select id="${id}">${coord}${groups}</select>`;
}

// Markdown leve e SEGURO p/ respostas do Orientador: escapa o HTML primeiro e só então
// converte um subconjunto (negrito, código, títulos #, listas - / 1.). Nada de HTML cru.
function _oriMd(raw) {
  const inline = s => esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+?)`/g, "<code>$1</code>");
  let html = "", ul = false, ol = false;
  const closeLists = () => { if (ul) { html += "</ul>"; ul = false; } if (ol) { html += "</ol>"; ol = false; } };
  for (const line of String(raw || "").split(/\r?\n/)) {
    const t = line.trim();
    if (!t) { closeLists(); continue; }
    let m;
    if ((m = t.match(/^#{1,6}\s+(.*)$/))) { closeLists(); html += `<div class="ori-md-h">${inline(m[1])}</div>`; }
    else if ((m = t.match(/^[-•*]\s+(.*)$/))) { if (ol) { html += "</ol>"; ol = false; } if (!ul) { html += "<ul class='ori-md-list'>"; ul = true; } html += `<li>${inline(m[1])}</li>`; }
    else if ((m = t.match(/^\d+\.\s+(.*)$/))) { if (ul) { html += "</ul>"; ul = false; } if (!ol) { html += "<ol class='ori-md-list'>"; ol = true; } html += `<li>${inline(m[1])}</li>`; }
    else { closeLists(); html += `<div>${inline(t)}</div>`; }
  }
  closeLists();
  return html;
}

async function viewOrientadorChat() {
  h(`<div class="hdr"><h2>Orientador Acadêmico — Chat</h2></div><div class="card muted">Carregando…</div>`);
  let boot;
  try { boot = await oriBoot(); } catch (e) { return h(`<div class="card danger">${esc(e.message)}</div>`); }
  h(`<div class="hdr"><h2>Orientador Acadêmico — Chat</h2></div>
     <div class="card">
       <div class="row"><label>Consultar:</label> ${_oriStudentSelect(boot, "ori-student", true)}</div>
       <div id="ori-chat" class="ori-chat"></div>
       <div class="ori-ask">
         <input id="ori-q" type="text" placeholder="Ex.: quero trabalhar com IA, o que curso agora?" />
         <button id="ori-send">Perguntar</button>
       </div>
       <div class="ori-chips" id="ori-chips"></div>
     </div>`);
  const chat = el("ori-chat"), input = el("ori-q");
  let history = [];  // memória da conversa: [{role:'user'|'assistant', content}]
  const CHIPS_ALUNO = ["Quero trabalhar com IA, o que curso agora?", "Posso pular Estrutura de Dados?",
    "Diferença entre Cientista de Dados e Engenheiro de Machine Learning?",
    "O que Cálculo I tem a ver com Machine Learning?"];
  const CHIPS_COORD = ["Quais alunos estão no curso de Banco de Dados?",
    "Quais alunos já cursaram Estrutura de Dados?",
    "Há alunos de cursos diferentes desenvolvendo a competência de Machine Learning?",
    "Quantos alunos há por curso?"];
  function add(role, text) {
    const d = document.createElement("div");
    d.className = "ori-msg ori-" + role;
    // Usuário: texto puro; bot: markdown leve (negrito, títulos, listas) bem formatado.
    d.innerHTML = role === "user"
      ? "🧑 " + esc(text).replace(/\n/g, "<br>")
      : `<div class="ori-md">${_oriMd(text)}</div>`;
    chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
  }
  const isCoord = () => el("ori-student").value === "__coord__";
  // Renderiza os chips de exemplo conforme o modo (aluno x coordenação) e religa o clique.
  function renderChips() {
    const box = el("ori-chips"); if (!box) return;
    box.innerHTML = (isCoord() ? CHIPS_COORD : CHIPS_ALUNO)
      .map(q => `<span class="ori-chip">${esc(q)}</span>`).join("");
    box.querySelectorAll(".ori-chip").forEach(c =>
      c.addEventListener("click", () => { input.value = c.textContent; send(); }));
  }
  // Trocar de aluno/modo reinicia a conversa (memória é por seleção).
  el("ori-student").addEventListener("change", () => { history = []; chat.innerHTML = ""; renderChips(); });
  async function send() {
    const q = (input.value || "").trim(); if (!q) return;
    const coord = isCoord();
    add("user", q); input.value = "";
    const wait = document.createElement("div"); wait.className = "ori-msg ori-bot muted"; wait.textContent = "🎓 pensando…";
    chat.appendChild(wait);
    try {
      const body = coord ? { mode: "coordinator", question: q, history }
                         : { student_id: el("ori-student").value, question: q, history };
      const d = await oriApi("/ask", { method: "POST", body: JSON.stringify(body) });
      const answer = d.answer || d.error || "(sem resposta)";
      wait.remove(); add("bot", answer);
      history.push({ role: "user", content: q }, { role: "assistant", content: answer });
      if (history.length > 16) history = history.slice(-16);
    } catch (e) { wait.remove(); add("bot", "Erro: " + e.message); }
  }
  el("ori-send").addEventListener("click", send);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
  renderChips();
}

async function viewOrientadorTrilha() {
  h(`<div class="hdr"><h2>Orientador Acadêmico — Trilha</h2></div><div class="card muted">Carregando…</div>`);
  let boot;
  try { boot = await oriBoot(); } catch (e) { return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const careers = (boot.careers || []).map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  h(`<div class="hdr"><h2>Orientador Acadêmico — Trilha</h2></div>
     <div class="card">
       <div class="row"><label>Aluno:</label> ${_oriStudentSelect(boot, "ori-student")}</div>
       <div class="row"><label>Carreira-alvo:</label>
         <select id="ori-career"><option value="">(usar a do aluno)</option>${careers}</select>
         <button id="ori-gen">Gerar trilha</button></div>
       <div id="ori-plan"></div>
     </div>`);
  async function gen() {
    const sid = el("ori-student").value, cid = el("ori-career").value || null;
    const out = el("ori-plan"); out.innerHTML = `<div class="muted">Calculando…</div>`;
    try {
      const [rec, prog] = await Promise.all([
        oriApi("/recommend", { method: "POST", body: JSON.stringify({ student_id: sid, career_id: cid }) }),
        oriApi("/progress", { method: "POST", body: JSON.stringify({ student_id: sid }) }),
      ]);
      const r = rec.result || {}, p = prog.result || {};
      const reqMap = {}; (r.recommended_order || []).forEach(d => { reqMap[d.id] = d.requirement; });
      const badge = id => reqMap[id] === "elective"
        ? '<span class="ori-pill ori-pend">eletiva</span>' : '<span class="ori-pill ori-ok">obrigatória</span>';
      const plan = (r.semester_plan || []).map(b =>
        `<div class="ori-sem"><b>Semestre +${b.semester_offset}</b><ul>${
          b.disciplines.map(d => `<li>${badge(d.id)} ${esc(d.name)} <span class="muted">(${esc(d.code || "")}, ${esc(d.area || "")}, ${d.credits ?? "?"} créd)</span></li>`).join("")
        }</ul></div>`).join("");
      const el2 = p.electives || {};
      const quota = el2.credits_required
        ? (el2.quota_met ? ' · cota eletiva concluída'
           : ` · faltam ${el2.credits_remaining} de ${el2.credits_required} créd eletivos`)
        : "";
      out.innerHTML = `
        <div class="ori-progress">Progresso: <b>${p.completion_pct ?? "—"}%</b>
          — ${(p.completed || []).length} concluídas, ${(p.pending || []).length} pendentes${quota}</div>
        <p class="muted">Trilha recomendada (${r.total_disciplines || 0} disciplinas: obrigatórias faltantes + eletivas para fechar a cota, respeitando pré-requisitos):</p>
        <div class="ori-plan-grid">${plan || '<div class="muted">Nada pendente para essa carreira. 🎉</div>'}</div>`;
    } catch (e) { out.innerHTML = `<div class="danger">${esc(e.message)}</div>`; }
  }
  el("ori-gen").addEventListener("click", gen);
  gen();
}

async function viewOrientadorAlunos() {
  h(`<div class="hdr"><h2>Orientador Acadêmico — Alunos</h2></div><div class="card muted">Carregando…</div>`);
  let boot;
  try { boot = await oriBoot(); } catch (e) { return h(`<div class="card danger">${esc(e.message)}</div>`); }
  h(`<div class="hdr"><h2>Orientador Acadêmico — Alunos</h2></div>
     <div class="card">
       <div class="row"><label>Aluno:</label> ${_oriStudentSelect(boot, "ori-student")}
         <button id="ori-dir">🎯 Direcionador de carreira</button></div>
       <div id="ori-prof"></div>
     </div>`);
  async function go() {
    const sid = el("ori-student").value;
    const out = el("ori-prof"); out.innerHTML = `<div class="muted">Carregando…</div>`;
    try {
      const p = (await oriApi("/student", { method: "POST", body: JSON.stringify({ student_id: sid }) })).result || {};
      const car = p.target_career || {}, prog = p.program || {};
      const demand = car.demand_level ? ` · demanda ${esc(car.demand_level)}` : "";
      const cr = d => `${d.credits ?? "?"} créd`;
      // Cor: eletiva=azul (sempre); senão concluída=verde, pendente=amarelo.
      const dotColor = (d, done) => d.requirement === "elective" ? "#3d8bfd" : (done ? "#2fbf71" : "#f5c518");
      const dot = c => `<span class="ori-dot" style="background:${c}"></span>`;
      const elecLabel = d => d.requirement === "elective" ? ' <span class="muted">· eletiva</span>' : "";
      const reqTag = d => d.requirement === "elective"
        ? '<span class="ori-pill ori-pend">eletiva</span>'
        : '<span class="ori-pill ori-ok">obrigatória</span>';
      const done = (p.completed || []).map(d =>
        `<li>${dot(dotColor(d, true))}${esc(d.name)} <span class="muted">(${esc(d.code || "")}, ${cr(d)})</span>${elecLabel(d)}${d.grade != null ? ` — nota <b>${esc(String(d.grade))}</b>` : ""}</li>`).join("");
      const pend = (p.pending || []).map(d =>
        `<span class="ori-tag">${dot(dotColor(d, false))}${esc(d.name)} <span class="muted">${esc(d.code || "")} · ${cr(d)}</span>${elecLabel(d)}</span>`).join("");
      const emcurso = (p.enrolled || []).map(d =>
        `<span class="ori-tag">${dot("#a855f7")}${esc(d.name)} <span class="muted">${esc(d.code || "")} · ${cr(d)}</span> ${reqTag(d)}</span>`).join("");
      const comps = (p.competencies || []).map(c =>
        `<span class="ori-tag" title="via: ${esc((c.from_disciplines || []).join(', '))}">${esc(c.name)}</span>`).join("");
      const next = (p.recommended_next || []).map(d =>
        `<li>${dot(dotColor(d, false))}${esc(d.name)} <span class="muted">(${esc(d.code || "")}, ${cr(d)})</span>${elecLabel(d)}</li>`).join("");
      const colorLegend = `<div class="ori-sub"><span class="ori-dot" style="background:#2fbf71"></span>concluída
        <span class="ori-dot" style="background:#a855f7"></span>em curso (semestre atual)
        <span class="ori-dot" style="background:#f5c518"></span>faltante obrigatória
        <span class="ori-dot" style="background:#3d8bfd"></span>eletiva</div>`;
      const mand = p.mandatory || {}, elec = p.electives || {};
      const quota = `<div class="ori-sub">Obrigatórias: <b>${mand.done ?? "—"}/${mand.total ?? "—"}</b>
        · Créditos eletivos: <b>${elec.credits_done ?? 0}/${elec.credits_required ?? 0}</b>
        ${elec.quota_met ? '<span class="ori-pill ori-ok">cota eletiva concluída</span>'
          : `<span class="ori-pill ori-pend">faltam ${elec.credits_remaining ?? 0} créd eletivos</span>`}</div>`;
      const cc = p.course_change_request;
      const ccBanner = cc ? `<div class="ori-rec ori-rec-course">
        📨 <b>Pedido de troca de curso</b> — para <b>${esc((cc.to_program||{}).name || "")}</b>
        <span class="ori-pill ori-pend">${esc(cc.status || "pendente")}</span>
        <div class="ori-sub muted">${cc.career && cc.career.name ? "Motivado pela carreira " + esc(cc.career.name) + ". " : ""}Solicitado em ${esc(cc.at || "—")} · aguardando análise do coordenador.</div>
      </div>` : "";
      out.innerHTML = `
        <div class="ori-prof-head">
          <div><div class="ori-prof-name">${esc(p.name || "")}</div>
            <div class="muted">${esc(prog.name || "")} · alvo: <b>${esc(car.name || "—")}</b>${demand}</div></div>
          <div class="ori-prof-pct"><b>${p.completion_pct ?? "—"}%</b><div class="muted">concluído</div></div>
        </div>
        ${ccBanner}
        ${quota}
        ${colorLegend}
        <div class="ori-grid2col">
          <div><h3>Concluídas <span class="muted">(${(p.completed || []).length})</span></h3>
            <ul class="ori-list">${done || '<li class="muted">Nenhuma.</li>'}</ul></div>
          <div><h3>Próximos passos <span class="muted">(sugeridos)</span></h3>
            <ol class="ori-list">${next || '<li class="muted">Nada pendente. 🎉</li>'}</ol></div>
        </div>
        <h3>Em curso <span class="muted">(${(p.enrolled || []).length}, neste semestre)</span></h3>
        <div class="ori-tags">${emcurso || '<span class="muted">—</span>'}</div>
        <h3>Competências já desenvolvidas</h3>
        <div class="ori-tags">${comps || '<span class="muted">—</span>'}</div>
        <h3>Faltantes <span class="muted">(${(p.pending || []).length}, em ordem de pré-requisito)</span></h3>
        <div class="ori-tags">${pend || '<span class="muted">—</span>'}</div>`;
    } catch (e) { out.innerHTML = `<div class="danger">${esc(e.message)}</div>`; }
  }
  el("ori-dir").addEventListener("click", () => oriDirecionador(el("ori-student").value, el("ori-prof"), go));
  // Trocar de aluno volta para o perfil (evita misturar respostas entre alunos).
  el("ori-student").addEventListener("change", go);
  go();
}

const ORI_IMP = { critical:["ori-gap","crítica"], important:["ori-pend","importante"], "nice-to-have":["ori-ok","desejável"] };

async function viewOrientadorCursos() {
  h(`<div class="hdr"><h2>Orientador Acadêmico — Cursos</h2></div><div class="card muted">Carregando…</div>`);
  let boot;
  try { boot = await oriBoot(); } catch (e) { return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const opts = (boot.programs || []).map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("");
  h(`<div class="hdr"><h2>Orientador Acadêmico — Cursos</h2></div>
     <div class="card">
       <div class="row"><label>Curso:</label> <select id="ori-prog">${opts}</select></div>
       <div id="ori-cd"></div>
     </div>`);
  async function go() {
    const out = el("ori-cd"); out.innerHTML = `<div class="muted">Carregando…</div>`;
    try {
      const p = (await oriApi("/program", { method: "POST", body: JSON.stringify({ program_id: el("ori-prog").value }) })).result || {};
      const c = p.counts || {};
      const areas = Object.entries(p.by_area || {}).sort((a,b)=>b[1]-a[1])
        .map(([a,n]) => `<span class="ori-tag">${esc(a)} <b>${n}</b></span>`).join("");
      const reqBadge = r => r === "elective"
        ? `<span class="ori-pill ori-pend">eletiva</span>` : `<span class="ori-pill ori-ok">obrigatória</span>`;
      const sems = (p.semesters || []).map(s =>
        `<div class="ori-sem"><b>${s.semester ? s.semester + "º semestre" : "Sem semestre definido"}</b>
          <ul>${s.disciplines.map(d => `<li>${reqBadge(d.requirement)} ${esc(d.name)} <span class="muted">(${esc(d.code||"")}, ${esc(d.area||"")}, ${d.credits ?? "?"} créd)</span></li>`).join("")}</ul></div>`).join("");
      const studs = (p.students || []).map(s =>
        `<li>${esc(s.name)} <span class="muted">— ${s.current_semester ? s.current_semester+"º sem" : "?"}${s.target_career_name ? ", alvo: "+esc(s.target_career_name) : ""}</span></li>`).join("");
      out.innerHTML = `
        <div class="ori-prof-head">
          <div><div class="ori-prof-name">${esc(p.name || "")}</div><div class="muted">${esc(p.code || "")}</div></div>
          <div class="ori-prof-pct"><b>${c.disciplines || 0}</b><div class="muted">disciplinas</div></div>
        </div>
        <div class="muted" style="margin:-.4rem 0 .8rem">${c.credits||0} créditos · ${c.mandatory||0} obrigatórias · ${c.elective||0} eletivas (exige ${c.elective_credits_required||0} créd eletivos) · ${c.shared||0} compartilhadas · ${c.students||0} aluno(s)</div>
        <h3>Disciplinas por área</h3><div class="ori-tags">${areas || '<span class="muted">—</span>'}</div>
        <h3>Alunos matriculados</h3><ul class="ori-list">${studs || '<li class="muted">Nenhum.</li>'}</ul>
        <h3>Grade por semestre</h3><div class="ori-plan-grid">${sems || '<span class="muted">—</span>'}</div>`;
    } catch (e) { out.innerHTML = `<div class="danger">${esc(e.message)}</div>`; }
  }
  el("ori-prog").addEventListener("change", go);
  go();
}

async function viewOrientadorCarreiras() {
  h(`<div class="hdr"><h2>Orientador Acadêmico — Carreiras</h2></div><div class="card muted">Carregando…</div>`);
  let boot;
  try { boot = await oriBoot(); } catch (e) { return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const opts = (boot.careers || []).map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  h(`<div class="hdr"><h2>Orientador Acadêmico — Carreiras</h2></div>
     <div class="card">
       <div class="row"><label>Carreira:</label> <select id="ori-career">${opts}</select></div>
       <div id="ori-cd"></div>
     </div>`);
  async function go() {
    const out = el("ori-cd"); out.innerHTML = `<div class="muted">Carregando…</div>`;
    try {
      const c = (await oriApi("/career", { method: "POST", body: JSON.stringify({ career_id: el("ori-career").value }) })).result || {};
      const toolsArr = Array.isArray(c.key_tools) ? c.key_tools
        : String(c.key_tools || "").split(/[;,]/).map(s => s.trim()).filter(Boolean);
      const tools = toolsArr.map(t => `<span class="ori-tag">${esc(t)}</span>`).join("");
      const comps = (c.competencies || []).map(x => {
        const [cls,lbl] = ORI_IMP[x.importance] || ["",""];
        return `<div class="ori-grow"><span class="ori-pill ${cls}">${lbl}</span> <b>${esc(x.name)}</b>
          <span class="muted">— ${x.developed_by} disciplina(s) desenvolvem</span></div>`;
      }).join("");
      const maxRel = Math.max(1e-6, ...(c.top_disciplines || []).map(d => d.relevance || 0));
      const top = (c.top_disciplines || []).map(d => {
        const w = Math.round(100 * (d.relevance||0) / maxRel);
        return `<div class="ori-brow"><div class="ori-bar"><span style="width:${w}%"></span></div>
          <b>${esc(d.name)}</b> <span class="muted">(${esc(d.code||"")})</span></div>`;
      }).join("");
      const studs = (c.students || []).map(s => `<li>${esc(s.name)} <span class="muted">— ${esc(s.program_name||"")}</span></li>`).join("");
      out.innerHTML = `
        <div class="ori-prof-head">
          <div><div class="ori-prof-name">${esc(c.name || "")}</div>
            <div class="muted">${esc(c.area || "")}</div></div>
          <div class="ori-prof-pct"><b>${esc(c.demand_level || "—")}</b><div class="muted">demanda</div></div>
        </div>
        <h3>Ferramentas-chave</h3><div class="ori-tags">${tools || '<span class="muted">—</span>'}</div>
        <h3>Competências exigidas</h3>${comps || '<span class="muted">—</span>'}
        <h3>Disciplinas mais relevantes</h3>${top || '<span class="muted">—</span>'}
        <h3>Alunos com esta carreira-alvo</h3><ul class="ori-list">${studs || '<li class="muted">Nenhum.</li>'}</ul>`;
    } catch (e) { out.innerHTML = `<div class="danger">${esc(e.message)}</div>`; }
  }
  el("ori-career").addEventListener("change", go);
  go();
}

let _oriQuestions = null;
const ORI_SCALE_LBL = ["Discordo totalmente", "Discordo", "Neutro", "Concordo", "Concordo totalmente"];

/* Direcionador de Carreira: wizard (1 pergunta por vez) dentro da tela de Alunos.
   host = elemento onde renderizar; back = callback para voltar ao perfil do aluno. */
async function oriDirecionador(sid, host, back) {
  host.innerHTML = `<div class="muted">Carregando questionário…</div>`;
  let qs;
  try {
    if (!_oriQuestions) _oriQuestions = ((await oriApi("/career-questions")).result || {}).questions || [];
    qs = _oriQuestions;
  } catch (e) { host.innerHTML = `<div class="danger">${esc(e.message)}</div>`; return; }

  const answers = {};
  let i = 0;

  function renderQ() {
    const q = qs[i];
    const pct = Math.round(100 * i / qs.length);
    host.innerHTML = `
      <div class="ori-wiz">
        <div class="ori-wiz-top"><span class="muted">Pergunta ${i + 1} de ${qs.length}</span>
          <div class="ori-wiz-bar"><span style="width:${pct}%"></span></div></div>
        <div class="ori-wiz-q">${esc(q.question)}</div>
        <div class="ori-wiz-opts">
          ${[0,1,2,3,4].map(v => `<button class="ori-wiz-opt" data-v="${v}"><b>${v}</b><span>${ORI_SCALE_LBL[v]}</span></button>`).join("")}
        </div>
        <div class="row" style="margin-top:.6rem">
          ${i > 0 ? `<button id="ori-wiz-back" class="ghost">← Voltar</button>` : ""}
          <button id="ori-wiz-cancel" class="ghost">Cancelar</button>
        </div>
      </div>`;
    host.querySelectorAll(".ori-wiz-opt").forEach(b => b.addEventListener("click", () => {
      answers[q.competency] = Number(b.getAttribute("data-v"));
      if (i < qs.length - 1) { i++; renderQ(); } else { finish(); }
    }));
    const bk = host.querySelector("#ori-wiz-back");
    if (bk) bk.addEventListener("click", () => { i = Math.max(0, i - 1); renderQ(); });
    host.querySelector("#ori-wiz-cancel").addEventListener("click", () => back && back());
  }

  async function finish() {
    host.innerHTML = `<div class="muted">Analisando suas respostas…</div>`;
    try {
      const d = (await oriApi("/career-result", { method: "POST", body: JSON.stringify({ student_id: sid, answers }) })).result || {};
      renderResult(d, (d.report || {}).career);
    } catch (e) { host.innerHTML = `<div class="danger">${esc(e.message)}</div>`; }
  }

  async function reRun(careerId) {
    host.innerHTML = `<div class="muted">Analisando…</div>`;
    try {
      const d = (await oriApi("/career-result", { method: "POST", body: JSON.stringify({ student_id: sid, answers, chosen_career_id: careerId }) })).result || {};
      renderResult(d, careerId);
    } catch (e) { host.innerHTML = `<div class="danger">${esc(e.message)}</div>`; }
  }

  function renderResult(d, chosenId) {
    const ranking = d.ranking || [], rep = d.report || {};
    chosenId = chosenId || rep.career;
    const ct = d.current_target;
    const curTxt = ct
      ? `Objetivo de carreira atual: <b>${esc(ct.name)}</b>`
      : `Este aluno <b>ainda não tem</b> um objetivo de carreira definido.`;

    const maxFit = Math.max(1e-6, ...ranking.map(r => r.fit || 0));
    const rank = ranking.map((r, k) => {
      const w = Math.round(100 * (r.fit || 0) / maxFit);
      const sel = r.career === chosenId ? " ori-rank-sel" : "";
      return `<div class="ori-brow ori-rank${sel}" data-career="${r.career}">
        <div class="ori-bar"><span style="width:${w}%"></span></div>
        <b>${k + 1}. ${esc(r.name)}</b> <span class="muted">— ${r.fit_pct}% de aderência${r.demand_level ? " · demanda " + esc(r.demand_level) : ""}</span></div>`;
    }).join("");

    const cur = rep.current || {}, best = rep.best_program || {};
    const missing = (cur.missing || []).map(m => `<span class="ori-tag">${esc(m.name)} <span class="muted">(${IMP_LABEL[m.importance] || m.importance})</span></span>`).join("") || '<span class="muted">nenhuma 🎉</span>';
    const extras = (cur.extras || []).map(x => {
      const inp = (x.in_program || []).map(dd => `${esc(dd.name)} <span class="muted">(${esc(dd.code || "")})</span>`).join(", ");
      const ext = (x.external || []).map(dd => `${esc(dd.name)} <span class="muted">(${(dd.programs || []).map(esc).join("/")})</span>`).join(", ");
      return `<div class="ori-sub"><b>${esc(x.competency_name)}</b>: ${inp ? "eletiva no seu curso — " + inp : (ext ? "em outro curso — " + ext : "sem oferta")}</div>`;
    }).join("");
    const isCurrent = ct && ct.id === chosenId;
    const chosenFit = (ranking.find(r => r.career === chosenId) || {}).fit_pct;

    // Bloco 1 — recomendação de CARREIRA (troca de alvo), com motivo e aceitar/não.
    let careerRec;
    if (isCurrent) {
      careerRec = `<div class="ori-rec"><div class="ori-sub">🎯 <b>Carreira:</b> <b>${esc(rep.career_name)}</b> já é o objetivo atual — nada a mudar.</div></div>`;
    } else {
      const motivo = `é a carreira que mais combina com as respostas${chosenFit != null ? ` (${chosenFit}% de aderência)` : ""}`
        + (rep.aligned ? `, e o curso atual já a atende bem (${cur.coverage_pct}%).`
                       : ` — porém o curso atual cobre só ${cur.coverage_pct}% do que ela exige.`);
      careerRec = `<div class="ori-rec">
        <div class="ori-sub">🎯 <b>Mudança de carreira recomendada:</b> ${ct ? `de <b>${esc(ct.name)}</b> para ` : "definir como "}<b>${esc(rep.career_name)}</b>.</div>
        <div class="ori-sub muted">Motivo: ${motivo}</div>
        <div class="row" style="margin-top:.5rem">
          <button id="ori-set">✔ Aceitar nova carreira</button>
          <button id="ori-decline" class="ghost">Manter atual</button>
          <span id="ori-set-msg" class="muted"></span>
        </div></div>`;
    }

    // Bloco 2 — recomendação de CURSO. Troca de curso passa pela instituição: botão de
    // "enviar sugestão ao coordenador" (simulado). Se não recomendada, apenas informa.
    const courseSug = rep.change_recommended
      ? `<div class="ori-rec ori-rec-course">
           <div class="ori-sub">📚 <b>Possível troca de curso:</b> <b>${esc(best.name)}</b> alinha melhor (${best.coverage_pct}% vs ${cur.coverage_pct}% no atual). Aproveitando <b>${best.aproveita_disciplinas}</b> disciplinas, faltariam ${best.faltam_disciplinas} disciplinas / ${best.faltam_creditos} créditos (~${best.semestres_restantes} sem).</div>
           <div class="ori-sub muted">Trocar de curso depende de análise da instituição.</div>
           <div class="row" style="margin-top:.5rem">
             <button id="ori-req">📨 Enviar sugestão ao coordenador</button>
             <span id="ori-req-msg" class="muted"></span>
           </div></div>`
      : `<div class="ori-sub" style="padding:.3rem 0">📚 <b>Curso:</b> manter em <b>${esc(cur.name)}</b> — atende bem esse objetivo (${cur.coverage_pct}%). Sem necessidade de troca.</div>`;
    host.innerHTML = `
      <div class="ori-sub" style="font-size:.95rem">${curTxt}</div>
      <h3>Carreiras que mais combinam com as respostas</h3>
      <p class="muted">Clique numa carreira para ver o relatório dela.</p>
      ${rank}
      <h3>Carreira indicada: ${esc(rep.career_name || "")}</h3>
      <div class="ori-sumline">Curso do aluno: <b>${esc(cur.name || "")}</b>
        <span class="ori-pill ${rep.aligned ? "ori-ok" : "ori-gap"}">${rep.aligned ? "condizente" : "pouco alinhado"} (${cur.coverage_pct ?? "—"}%)</span></div>
      <h4>Competências que faltam no curso</h4><div class="ori-tags">${missing}</div>
      ${extras ? `<h4>Como cobrir (disciplinas extras)</h4>${extras}` : ""}
      <h3>Recomendação</h3>
      ${careerRec}
      ${courseSug}
      <div class="row" style="margin-top:.8rem"><button id="ori-back" class="ghost">Voltar ao perfil</button></div>`;

    host.querySelectorAll(".ori-rank").forEach(elm =>
      elm.addEventListener("click", () => reRun(elm.getAttribute("data-career"))));
    const bkBtn = host.querySelector("#ori-back");
    if (bkBtn) bkBtn.addEventListener("click", () => back && back());
    const setBtn = host.querySelector("#ori-set");
    if (setBtn) setBtn.addEventListener("click", async () => {
      if (!confirm(`Definir "${rep.career_name}" como o objetivo de carreira deste aluno? Isso altera o cadastro.`)) return;
      const msg = host.querySelector("#ori-set-msg"); msg.textContent = "Salvando…";
      try {
        await oriApi("/set-target", { method: "POST", body: JSON.stringify({ student_id: sid, career_id: chosenId }) });
        _oriBoot = null;  // reflete o novo alvo nas outras telas
        setBtn.disabled = true;
        msg.innerHTML = `<span class="ori-pill ori-ok">nova carreira salva ✓</span>`;
      } catch (e) { msg.innerHTML = `<span class="ori-pill ori-gap">erro: ${esc(e.message)}</span>`; }
    });
    const decBtn = host.querySelector("#ori-decline");
    if (decBtn) decBtn.addEventListener("click", () => back && back());
    const reqBtn = host.querySelector("#ori-req");
    if (reqBtn) reqBtn.addEventListener("click", async () => {
      const rmsg = host.querySelector("#ori-req-msg"); rmsg.textContent = "Enviando…"; reqBtn.disabled = true;
      try {
        await oriApi("/request-course-change", { method: "POST", body: JSON.stringify({ student_id: sid, program_id: best.id, career_id: chosenId }) });
        _oriBoot = null;
        rmsg.innerHTML = `<span class="ori-pill ori-ok">pedido registrado no perfil do aluno ✓</span>`;
      } catch (e) { reqBtn.disabled = false; rmsg.innerHTML = `<span class="ori-pill ori-gap">erro: ${esc(e.message)}</span>`; }
    });
  }

  renderQ();
}

async function viewCoordTransfers() {
  h(`<div class="hdr"><h2>Coordenação — Pedidos de transferência</h2></div><div id="ori-coord-list" class="card muted">Carregando…</div>`);
  const host = el("ori-coord-list");
  async function load() {
    host.className = "card"; host.innerHTML = `<div class="muted">Carregando…</div>`;
    try {
      const reqs = ((await oriApi("/transfers")).result || {}).requests || [];
      if (!reqs.length) { host.innerHTML = `<div class="muted">Nenhum pedido de transferência pendente. 🎉</div>`; return; }
      host.innerHTML = reqs.map((r, i) => `
        <div class="ori-req-card" data-i="${i}">
          <div class="ori-req-head"><b>${esc(r.name)}</b>
            <span class="ori-pill ori-pend">${esc(r.status || "pendente")}</span></div>
          <div class="ori-sub">De <b>${esc((r.from_program||{}).name||"—")}</b> → para <b>${esc((r.to_program||{}).name||"—")}</b></div>
          <div class="ori-sub muted">${r.career && r.career.name ? "Motivado pela carreira " + esc(r.career.name) + " · " : ""}Solicitado em ${esc(r.at || "—")}</div>
          <div class="row" style="margin-top:.5rem">
            <button class="ori-accept" data-sid="${r.student_id}" data-name="${esc(r.name)}" data-to="${esc((r.to_program||{}).name||"")}">✔ Aceitar transferência</button>
            <button class="ghost ori-deny" data-sid="${r.student_id}" data-name="${esc(r.name)}">✖ Negar</button>
          </div>
        </div>`).join("");
      host.querySelectorAll(".ori-accept").forEach(b => b.addEventListener("click", () => decide(b.dataset.sid, "accept", b.dataset.name, b.dataset.to)));
      host.querySelectorAll(".ori-deny").forEach(b => b.addEventListener("click", () => decide(b.dataset.sid, "deny", b.dataset.name)));
    } catch (e) { host.innerHTML = `<div class="danger">${esc(e.message)}</div>`; }
  }
  async function decide(sid, decision, name, toName) {
    const q = decision === "accept"
      ? `Aceitar a transferência de ${name} para ${toName}? O curso do aluno será alterado.`
      : `Negar o pedido de transferência de ${name}?`;
    if (!confirm(q)) return;
    try {
      await oriApi("/transfer-resolve", { method: "POST", body: JSON.stringify({ student_id: sid, decision }) });
      _oriBoot = null;  // curso pode ter mudado
      load();
    } catch (e) { alert("Erro: " + e.message); }
  }
  load();
}

const ORI_STATUS = { lacuna: ["ori-gap", "Lacuna"], pendente: ["ori-pend", "Pendente"], coberta: ["ori-ok", "Coberta"] };
const IMP_LABEL = { critical: "crítica", important: "importante", "nice-to-have": "desejável" };

function _oriDiscList(discs) {
  if (!discs || !discs.length) return `<span class="muted">—</span>`;
  return discs.map(d => `${esc(d.name)} <span class="muted">(${esc(d.code || "")})</span>`).join(", ");
}

async function viewOrientadorInsights() {
  h(`<div class="hdr"><h2>Orientador Acadêmico — Insights</h2></div><div class="card muted">Carregando…</div>`);
  let boot;
  try { boot = await oriBoot(); } catch (e) { return h(`<div class="card danger">${esc(e.message)}</div>`); }
  h(`<div class="hdr"><h2>Orientador Acadêmico — Insights</h2></div>
     <div class="card">
       <div class="row"><label>Aluno:</label> ${_oriStudentSelect(boot, "ori-student")}</div>
       <p class="muted">Análises nativas do grafo: disciplinas-gargalo, caminho crítico de pré-requisitos e lacunas de competência para a carreira-alvo.</p>
       <div id="ori-ins"></div>
     </div>`);
  async function go() {
    const sid = el("ori-student").value;
    const out = el("ori-ins"); out.innerHTML = `<div class="muted">Calculando…</div>`;
    try {
      const d = (await oriApi("/insights", { method: "POST", body: JSON.stringify({ student_id: sid }) })).result || {};
      const b = (d.bottlenecks || []).map(x => {
        const ind = Math.max(0, (x.unlocks_total || 0) - (x.unlocks_direct || 0));
        return `<div class="ori-brow"><span class="ori-badge" title="total de disciplinas que dependem desta (diretas + indiretas)">${x.unlocks_total}</span>
          <b>${esc(x.name)}</b> <span class="muted">(${esc(x.code || "")}, ${esc(x.area || "")})</span>
          <span class="muted">— destrava <b>${x.unlocks_direct}</b> diretas + <b>${ind}</b> indiretas</span></div>`;
      }).join("") || `<span class="muted">—</span>`;
      const cp = d.critical_path || {};
      const chain = (cp.path || []).map(x => `<span class="ori-node" title="${esc(x.name)}">${esc(x.code || x.name)}</span>`).join('<span class="ori-arrow">→</span>');
      const g = d.competency_gaps || {}, sm = g.summary || {};
      const gaps = (g.gaps || []).map(x => {
        const [cls, lbl] = ORI_STATUS[x.status] || ["", x.status];
        let close = "";
        if (x.status === "lacuna")
          close = `<div class="ori-sub">Nenhuma disciplina do seu curso desenvolve esta competência — considere uma eletiva ou curso externo.</div>`;
        else if (x.status === "pendente")
          close = `<div class="ori-sub">Você fecha cursando: ${_oriDiscList(x.close_with)}</div>`;
        return `<div class="ori-grow"><span class="ori-pill ${cls}">${lbl}</span>
          <b>${esc(x.competency_name)}</b> <span class="muted">(${IMP_LABEL[x.importance] || x.importance})</span>${close}</div>`;
      }).join("");
      out.innerHTML = `
        <h3>Disciplinas-gargalo</h3>
        <p class="muted">São as disciplinas das quais mais outras dependem. O número em destaque é o <b>total</b> que ela destrava (diretas + indiretas). São prioridade: se você travar numa delas, trava muita coisa à frente.</p>
        ${b}
        <h3>Caminho crítico <span class="muted">(${cp.length || 0} disciplinas em cadeia)</span></h3>
        <p class="muted">A maior sequência de pré-requisitos encadeados do seu curso (cada uma exige a anterior). O tamanho é o <b>mínimo de semestres</b> se elas fossem cursadas uma após a outra.</p>
        <div class="ori-chain">${chain || '<span class="muted">—</span>'}</div>
        <h3>Lacunas de competência → ${esc(g.career_name || "")}</h3>
        <p class="muted">Compara as competências exigidas pela carreira-alvo com o que seu curso oferece: <b>lacuna</b> = nenhuma disciplina do curso desenvolve; <b>pendente</b> = existe disciplina, mas você ainda não cursou; <b>coberta</b> = você já desenvolveu.</p>
        <div class="ori-sumline"><span class="ori-pill ori-gap">${sm.lacunas || 0} lacunas</span>
          <span class="ori-pill ori-pend">${sm.pendentes || 0} pendentes</span>
          <span class="ori-pill ori-ok">${sm.cobertas || 0} cobertas</span></div>
        ${gaps}`;
    } catch (e) { out.innerHTML = `<div class="danger">${esc(e.message)}</div>`; }
  }
  el("ori-student").addEventListener("change", go);
  go();
}

async function viewOrientadorCurriculo() {
  h(`<div class="hdr"><h2>Orientador Acadêmico — Currículo</h2></div><div class="card muted">Carregando…</div>`);
  let d;
  try { d = (await oriApi("/curriculum")).result || {}; } catch (e) { return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const progs = (d.programs || []).map(p =>
    `<div class="ori-prog-card"><b>${esc(p.name)}</b>
       <div class="ori-prog-nums"><span>${p.total_disciplines} disciplinas</span>
       <span class="muted">${p.exclusive} exclusivas · ${p.shared} compartilhadas</span></div></div>`).join("");
  const overlaps = (d.overlaps || []).map(o =>
    `<div class="ori-sub"><b>${esc(o.a_name)} × ${esc(o.b_name)}</b>: ${o.shared} disciplinas em comum</div>
     <div class="ori-tags">${(o.shared_disciplines || []).map(x => `<span class="ori-tag">${esc(x.code || x.name)}</span>`).join("")}</div>`).join("");
  const maxScore = Math.max(1e-6, ...(d.strategic_competencies || []).map(s => s.strategic_score));
  const strat = (d.strategic_competencies || []).map(s => {
    const w = Math.round(100 * s.strategic_score / maxScore);
    return `<div class="ori-brow"><div class="ori-bar"><span style="width:${w}%"></span></div>
      <b>${esc(s.name)}</b> <span class="muted">— demanda ${s.demand}, ${s.coverage} disciplina(s)</span></div>`;
  }).join("");
  h(`<div class="hdr"><h2>Orientador Acadêmico — Currículo</h2></div>
     <div class="card">
       <h3>Programas</h3><div class="ori-grid2">${progs}</div>
       <h3>Sobreposição entre cursos <span class="muted">(disciplinas-ponte)</span></h3>${overlaps || '<span class="muted">—</span>'}
       <h3>Competências estratégicas <span class="muted">(muita demanda, pouca oferta)</span></h3>
       <p class="muted">Onde vale investir no currículo. <b>Demanda</b> = o quanto as carreiras pedem a competência (ponderado por importância na carreira e pela demanda de mercado dela). <b>N disciplina(s)</b> = quantas disciplinas do acervo a desenvolvem (a oferta). A <b>barra</b> combina os dois (demanda ÷ oferta): quanto maior, mais a competência é muito pedida e pouco ensinada — candidata a novas disciplinas/turmas.</p>
       ${strat || '<span class="muted">—</span>'}
     </div>`);
}

async function viewOrientadorCompetencias() {
  h(`<div class="hdr"><h2>Orientador Acadêmico — Competências</h2></div><div class="card muted">Carregando…</div>`);
  let boot;
  try { boot = await oriBoot(); } catch (e) { return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const careers = (boot.careers || []).map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  h(`<div class="hdr"><h2>Orientador Acadêmico — Competências</h2></div>
     <div class="card">
       <div class="row"><label>Carreira:</label><select id="ori-career">${careers}</select></div>
       <p class="muted">Competências exigidas pela carreira e quais cursos conseguem desenvolvê-las. Programa com 0 disciplinas = lacuna de currículo.</p>
       <div id="ori-rep"></div>
     </div>`);
  async function go() {
    const cid = el("ori-career").value;
    const out = el("ori-rep"); out.innerHTML = `<div class="muted">Carregando…</div>`;
    try {
      const d = (await oriApi("/competency-report", { method: "POST", body: JSON.stringify({ career_id: cid }) })).result || {};
      const progs = d.programs || [];
      const rows = (d.competencies || []).map(c => {
        const cells = progs.map(p => {
          const bp = (c.by_program || {})[p.id] || { count: 0, disciplines: [] };
          const cls = bp.count ? "ori-ok" : "ori-gap";
          return `<td class="${cls}" title="${esc((bp.disciplines || []).map(x => x.name).join(', '))}">${bp.count}</td>`;
        }).join("");
        return `<tr><td><b>${esc(c.competency_name)}</b><br><span class="muted">${IMP_LABEL[c.importance] || c.importance}</span></td>${cells}</tr>`;
      }).join("");
      const head = progs.map(p => `<th>${esc(p.name)}</th>`).join("");
      out.innerHTML = `<table class="ori-table"><thead><tr><th>Competência</th>${head}</tr></thead><tbody>${rows}</tbody></table>
        <p class="muted">Verde = o curso desenvolve a competência; vermelho = lacuna nesse currículo. Passe o mouse para ver as disciplinas.</p>`;
    } catch (e) { out.innerHTML = `<div class="danger">${esc(e.message)}</div>`; }
  }
  el("ori-career").addEventListener("change", go);
  go();
}

/* ---------------- Grafo visual (força dirigida, SVG puro, sem libs) ---------------- */
const ORI_COLORS = { Student:"#e0555b", Discipline:"#3d8bfd", Competency:"#f5a623", Career:"#17c3b2", Program:"#a259f7" };
const ORI_TYPE_PT = { Student:"Aluno", Discipline:"Disciplina", Competency:"Competência", Career:"Carreira", Program:"Curso" };
// Cores por status (usado no escopo Aluno): verde=concluída/alcançada, azul=falta, amarelo=carreira.
const ORI_STATUS_COLORS = { done:"#2fbf71", todo:"#3d8bfd", career:"#f5c518", student:"#e0555b" };
function _oriStar(r) {
  const pts = [];
  for (let i = 0; i < 10; i++) {
    const ang = -Math.PI / 2 + i * Math.PI / 5;
    const rad = (i % 2 === 0) ? r : r * 0.45;
    pts.push((Math.cos(ang) * rad).toFixed(1) + "," + (Math.sin(ang) * rad).toFixed(1));
  }
  return pts.join(" ");
}

function _oriForceGraph(container, data, onNodeClick) {
  const NS = "http://www.w3.org/2000/svg";
  const W = Math.max(320, container.clientWidth || 800);
  const H = Math.max(560, Math.round((window.innerHeight || 900) * 0.78));
  container.innerHTML = "";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "ori-graph"); svg.setAttribute("width", "100%");
  svg.setAttribute("height", H); svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const cam = document.createElementNS(NS, "g"); svg.appendChild(cam); container.appendChild(svg);

  const nodes = (data.nodes || []).map(n => ({ ...n,
    x: W/2 + (Math.random()-.5)*W*0.6, y: H/2 + (Math.random()-.5)*H*0.6, vx:0, vy:0 }));
  const idx = {}; nodes.forEach(n => idx[n.id] = n);
  const links = (data.edges || []).map(e => ({ source: idx[e.source], target: idx[e.target], label: e.label }))
    .filter(l => l.source && l.target);
  const N = nodes.length || 1;
  const bigGraph = N > 28;
  const k = Math.sqrt((W*H)/N) * 0.75;

  const lines = links.map(() => { const e = document.createElementNS(NS,"line"); e.setAttribute("class","ori-edge"); cam.appendChild(e); return e; });
  nodes.forEach(n => {
    const gg = document.createElementNS(NS,"g"); gg.setAttribute("class","ori-gnode");
    const r = 6 + Math.min(16, (n.degree||0)*1.1);
    // Cor: por status quando houver (escopo Aluno), senão por tipo.
    const fill = n.status ? (ORI_STATUS_COLORS[n.status] || ORI_COLORS[n.type] || "#999")
                          : (ORI_COLORS[n.type] || "#999");
    // Forma: estrela para Competência, bolinha para o resto.
    let c;
    if (n.type === "Competency") { c = document.createElementNS(NS,"polygon"); c.setAttribute("points", _oriStar(r+2)); }
    else { c = document.createElementNS(NS,"circle"); c.setAttribute("r", r); }
    c.setAttribute("fill", fill);
    const t = document.createElementNS(NS,"text"); t.setAttribute("class","ori-glabel");
    t.setAttribute("x", r+3); t.setAttribute("y", 4);
    t.textContent = n.label || "";
    const hide = bigGraph && (n.degree||0) < 4;
    if (hide) t.style.display = "none";
    gg.appendChild(c); gg.appendChild(t); cam.appendChild(gg);
    n._el = gg; n._c = c; n._r = r; n._t = t;
    c.addEventListener("mouseenter", () => { t.style.display = ""; });
    c.addEventListener("mouseleave", () => { if (hide && !n._pin) t.style.display = "none"; });
    const st = { done:" (concluída/alcançada)", todo:" (falta)", career:" (carreira-alvo)" }[n.status] || "";
    const title = document.createElementNS(NS,"title");
    title.textContent = `${n.label} — ${ORI_TYPE_PT[n.type] || n.type}${st}`; gg.appendChild(title);
  });

  function render() {
    for (let i=0;i<links.length;i++){ const l=links[i], e=lines[i];
      e.setAttribute("x1",l.source.x); e.setAttribute("y1",l.source.y);
      e.setAttribute("x2",l.target.x); e.setAttribute("y2",l.target.y); }
    for (const n of nodes) n._el.setAttribute("transform", `translate(${n.x},${n.y})`);
  }
  let alpha = 1, ticks = 0, raf = null;
  function step() {
    for (let i=0;i<N;i++){ const a=nodes[i];
      for (let j=i+1;j<N;j++){ const b=nodes[j];
        let dx=a.x-b.x, dy=a.y-b.y, d=Math.sqrt(dx*dx+dy*dy)||0.01;
        const f=(k*k)/d, fx=dx/d*f, fy=dy/d*f;
        a.vx+=fx; a.vy+=fy; b.vx-=fx; b.vy-=fy; } }
    for (const l of links){ const a=l.source, b=l.target;
      let dx=a.x-b.x, dy=a.y-b.y, d=Math.sqrt(dx*dx+dy*dy)||0.01;
      const f=(d*d)/k, fx=dx/d*f, fy=dy/d*f;
      a.vx-=fx; a.vy-=fy; b.vx+=fx; b.vy+=fy; }
    for (const n of nodes){
      n.vx += (W/2-n.x)*0.012; n.vy += (H/2-n.y)*0.012;
      if (n._pin){ n.vx=0; n.vy=0; }
      else { n.x += Math.max(-25,Math.min(25,n.vx*alpha*0.08)); n.y += Math.max(-25,Math.min(25,n.vy*alpha*0.08)); }
      n.vx*=0.86; n.vy*=0.86;
    }
    render();
    alpha *= 0.992; ticks++;
    raf = (ticks < 500 && alpha > 0.015) ? requestAnimationFrame(step) : null;
  }
  function kick(a){ alpha = Math.max(alpha, a||0.3); if (!raf) raf = requestAnimationFrame(step); }
  raf = requestAnimationFrame(step);

  // pan / zoom / drag
  let tx=0, ty=0, scale=1, drag=null;
  const applyCam = () => cam.setAttribute("transform", `translate(${tx},${ty}) scale(${scale})`);
  function worldXY(e){ const r=svg.getBoundingClientRect();
    const sx=(e.clientX-r.left)*(W/r.width), sy=(e.clientY-r.top)*(H/r.height);
    return { x:(sx-tx)/scale, y:(sy-ty)/scale }; }
  svg.addEventListener("wheel", (e) => { e.preventDefault();
    // Zoom suave: proporcional ao scroll (trackpad manda deltas pequenos) e com teto de
    // ±5% por evento, ancorado no ponto sob o cursor.
    const r = svg.getBoundingClientRect();
    const sx = (e.clientX-r.left)*(W/r.width), sy = (e.clientY-r.top)*(H/r.height);
    const wx = (sx-tx)/scale, wy = (sy-ty)/scale;
    const f = Math.min(1.05, Math.max(0.95, Math.exp(-e.deltaY * 0.0008)));
    const ns = Math.max(0.3, Math.min(3, scale * f));
    tx = sx - wx*ns; ty = sy - wy*ns; scale = ns; applyCam();
  }, { passive:false });
  nodes.forEach(n => n._c.addEventListener("pointerdown", (e) => {
    e.stopPropagation(); const w=worldXY(e); n._pin=true; n.x=w.x; n.y=w.y; n._t.style.display="";
    drag={node:n}; svg.setPointerCapture(e.pointerId); kick(0.4);
    n._moved=false; n._downX=e.clientX; n._downY=e.clientY;
  }));
  svg.addEventListener("pointerdown", (e) => { if (!drag){ drag={pan:true,x:e.clientX,y:e.clientY}; svg.setPointerCapture(e.pointerId); } });
  svg.addEventListener("pointermove", (e) => { if (!drag) return;
    if (drag.node){ const w=worldXY(e); drag.node.x=w.x; drag.node.y=w.y;
      if (Math.abs(e.clientX-drag.node._downX)+Math.abs(e.clientY-drag.node._downY)>4) drag.node._moved=true;
      if (!raf) render(); }
    else if (drag.pan){ tx+=e.clientX-drag.x; ty+=e.clientY-drag.y; drag.x=e.clientX; drag.y=e.clientY; applyCam(); }
  });
  svg.addEventListener("pointerup", (e) => {
    if (drag && drag.node){ const n=drag.node; n._pin=false; kick(0.2);
      if (!n._moved && onNodeClick) onNodeClick(n); }
    drag=null;
  });
  applyCam();
}

async function viewOrientadorGrafo() {
  h(`<div class="hdr"><h2>Orientador Acadêmico — Grafo</h2></div><div class="card muted">Carregando…</div>`);
  let boot;
  try { boot = await oriBoot(); } catch (e) { return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const typeLegend = Object.keys(ORI_COLORS).map(t =>
    `<span class="ori-leg"><i style="background:${ORI_COLORS[t]}"></i>${ORI_TYPE_PT[t]}</span>`).join("");
  const studentLegend =
    `<span class="ori-leg"><i style="background:${ORI_STATUS_COLORS.done}"></i>Concluída/alcançada</span>
     <span class="ori-leg"><i style="background:${ORI_STATUS_COLORS.todo}"></i>Falta</span>
     <span class="ori-leg"><i style="background:${ORI_STATUS_COLORS.career}"></i>Carreira-alvo</span>
     <span class="ori-leg">● disciplina</span><span class="ori-leg">★ competência</span>`;
  h(`<div class="hdr"><h2>Orientador Acadêmico — Grafo</h2></div>
     <div class="card">
       <div class="row">
         <label>Ver:</label>
         <select id="ori-scope">
           <option value="student">Aluno</option>
           <option value="discipline">Disciplina</option>
           <option value="career">Carreira</option>
           <option value="full">Tudo</option>
         </select>
         <select id="ori-ent"></select>
         <button id="ori-go">Montar grafo</button>
         <span id="ori-gcount" class="muted"></span>
       </div>
       <div class="ori-legend" id="ori-legend">${studentLegend}</div>
       <div id="ori-canvas" class="ori-canvas"></div>
       <p class="muted">Arraste os nós, use a roda para dar zoom e arraste o fundo para mover. Clique num nó (Aluno/Disciplina/Carreira) para recentralizar nele.</p>
     </div>`);

  const scopeSel = el("ori-scope"), entSel = el("ori-ent");
  function fillEntities() {
    const scope = scopeSel.value;
    let opts = "";
    if (scope === "student") opts = (boot.students||[]).map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join("");
    else if (scope === "discipline") opts = (boot.disciplines||[]).slice().sort((a,b)=>(a.name||"").localeCompare(b.name||"")).map(d => `<option value="${d.id}">${esc(d.name)} (${esc(d.code||"")})</option>`).join("");
    else if (scope === "career") opts = (boot.careers||[]).map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
    entSel.innerHTML = opts; entSel.style.display = scope === "full" ? "none" : "";
  }
  async function load() {
    const scope = scopeSel.value, id = scope === "full" ? null : entSel.value;
    el("ori-legend").innerHTML = (scope === "student") ? studentLegend : typeLegend;
    const cv = el("ori-canvas"); cv.innerHTML = `<div class="muted" style="padding:1rem">Montando…</div>`;
    el("ori-gcount").textContent = "";
    try {
      const d = (await oriApi("/graph", { method: "POST", body: JSON.stringify({ scope, id }) })).result || {};
      el("ori-gcount").textContent = `${d.counts?.nodes||0} nós · ${d.counts?.edges||0} ligações`;
      _oriForceGraph(cv, d, (n) => {
        const map = { Student:"student", Discipline:"discipline", Career:"career" };
        if (!map[n.type]) return;
        scopeSel.value = map[n.type]; fillEntities(); entSel.value = n.id; load();
      });
    } catch (e) { cv.innerHTML = `<div class="danger" style="padding:1rem">${esc(e.message)}</div>`; }
  }
  scopeSel.addEventListener("change", () => { fillEntities(); load(); });
  el("ori-go").addEventListener("click", load);
  fillEntities(); load();
}

/* ---------------- LMS de Vídeo (Marengo + S3 Vectors, via /lms) ---------------- */
const LMS = "/lms";
let _lmsCat = null;

let _lmsDebug = [];
// Trunca campos grandes (base64 de imagem/áudio/vídeo) para não poluir o painel de debug.
function _lmsSanitize(o) {
  if (typeof o === "string") return o.length > 160 ? `<${o.length} chars>` : o;
  if (Array.isArray(o)) return o.map(_lmsSanitize);
  if (o && typeof o === "object") { const r = {}; for (const k in o) r[k] = _lmsSanitize(o[k]); return r; }
  return o;
}
function _lmsRecord(method, path, reqBody, status, data) {
  let req = null; try { req = reqBody ? _lmsSanitize(JSON.parse(reqBody)) : null; } catch (e) { req = reqBody; }
  _lmsDebug.unshift({ ts: new Date().toLocaleTimeString(), method, path, status,
                      request: req, response: _lmsSanitize(data) });
  _lmsDebug = _lmsDebug.slice(0, 20);
  lmsRefreshDebug();
}
function _lmsBackendHtml(dbg) {
  if (!dbg || typeof dbg !== "object") return "";
  let h = '<div class="lms-be"><div class="lms-be-h">🔧 o que o backend fez por trás</div>';
  if (dbg.fluxo) h += `<div class="muted" style="font-size:12px;margin-bottom:6px">${esc(dbg.fluxo)}</div>`;
  if (Array.isArray(dbg.trace)) h += '<ol class="lms-trace">' + dbg.trace.map(s =>
    `<li><span class="lms-ms">${s.ms}ms</span> ${esc(s.acao)}` +
    (s.detalhe ? `<pre>${esc(JSON.stringify(s.detalhe, null, 2))}</pre>` : "") + `</li>`).join("") + '</ol>';
  if (Array.isArray(dbg.raw_hits)) h += `<div class="muted" style="font-size:12px;margin-top:6px">matches brutos do S3 Vectors (chave · distância · modalidade):</div>` +
    `<pre>${esc(JSON.stringify(dbg.raw_hits, null, 2))}</pre>`;
  if (dbg.erro) h += `<div class="danger">erro: ${esc(dbg.erro)}</div>`;
  return h + '</div>';
}

function lmsRefreshDebug() {
  const box = el("lmsDebug"); if (!box) return;
  if (!_lmsDebug.length) { box.innerHTML = ""; return; }
  box.innerHTML = `<details class="lms-debug"><summary>🐞 Debug — ${_lmsDebug.length} requisição(ões) ao backend (clique para expandir)</summary>`+
    _lmsDebug.map(e => {
      const resp = (e.response && typeof e.response === "object") ? { ...e.response } : e.response;
      const dbg = resp && resp.debug; if (resp && resp.debug) delete resp.debug;
      return `<div class="lms-dbg-item"><div class="muted" style="font-size:12px">${esc(e.ts)} · ${esc(e.method)} ${esc(e.path)} · HTTP ${e.status}</div>`+
        _lmsBackendHtml(dbg)+
        `<div class="lms-dbg-cols"><div><div class="muted">↑ enviado</div><pre>${esc(JSON.stringify(e.request, null, 2))}</pre></div>`+
        `<div><div class="muted">↓ recebido</div><pre>${esc(JSON.stringify(resp, null, 2))}</pre></div></div></div>`;
    }).join("")+
    `</details>`;
}

async function lmsApi(path, opts = {}, _retried) {
  const r = await fetch(LMS + path, { ...opts, headers: {
    "Content-Type": "application/json", "Authorization": "Bearer " + ID_TOKEN, ...(opts.headers || {}) } });
  if (r.status === 401 && !_retried) {
    if (await refreshToken()) return lmsApi(path, opts, true);
    login(); throw new Error("Sessão expirada. Redirecionando para o login…");
  }
  const data = await r.json().catch(() => ({}));
  _lmsRecord((opts.method || "GET").toUpperCase(), path, opts.body, r.status, data);
  if (!r.ok) throw new Error(data.message || data.error || ("HTTP " + r.status));
  return data;
}

async function lmsCatalog(force) { if (force || !_lmsCat) _lmsCat = await lmsApi("/catalog"); return _lmsCat; }

function _lmsFmt(s) { s = Math.max(0, Math.round(s || 0)); const m = Math.floor(s / 60); return (m > 0 ? m + "m" : "") + (s % 60) + "s"; }

function _lmsFileB64(input) {
  return new Promise((res, rej) => {
    const f = input && input.files && input.files[0];
    if (!f) return res("");
    const rd = new FileReader();
    rd.onload = () => res(String(rd.result).split(",").pop());
    rd.onerror = rej; rd.readAsDataURL(f);
  });
}

let _lmsNowPlaying = null;

function lmsPlay(url, t, disc_id, video) {
  const v = el("lmsPlayer"); if (!v) return;
  _lmsNowPlaying = (disc_id && video) ? { disc_id, video } : null;
  v.style.display = "block"; v.src = url;
  v.onloadedmetadata = () => { try { v.currentTime = t || 0; } catch (e) {} v.play().catch(() => {}); };
  v.load(); v.scrollIntoView({ behavior: "smooth", block: "center" });
  // barra do player: botão de cenas semelhantes ao INSTANTE ATUAL (só quando sabemos qual vídeo é)
  let bar = el("lmsPlayerBar");
  if (!bar) {
    v.insertAdjacentHTML("afterend", '<div id="lmsPlayerBar" style="display:none;margin:6px 0 10px"></div>');
    bar = el("lmsPlayerBar");
  }
  if (_lmsNowPlaying) {
    bar.style.display = "block";
    bar.innerHTML = `<button class="sec" onclick="lmsSimilarNow()" title="Busca cenas parecidas com o instante que está passando agora no vídeo (inclusive de outros cursos)">🔎 cenas semelhantes ao trecho atual</button> <span class="muted" style="font-size:12px">usa o instante atual do vídeo</span>`;
  } else {
    bar.style.display = "none"; bar.innerHTML = "";
  }
}

// Garante um container de resultados (a view de catálogo não tem #lmsResults nativo).
function _lmsEnsureResultsBox() {
  let box = el("lmsResults");
  if (!box) {
    const anchor = el("lmsPlayerBar") || el("lmsPlayer");
    if (anchor) { anchor.insertAdjacentHTML("afterend", '<div id="lmsResults" class="card muted"></div>'); box = el("lmsResults"); }
  }
  return box;
}

// Cenas semelhantes ao instante ATUAL do player (usa video.currentTime -> at_sec).
async function lmsSimilarNow() {
  if (!_lmsNowPlaying) return;
  const v = el("lmsPlayer");
  const at = v ? (v.currentTime || 0) : 0;
  const box = _lmsEnsureResultsBox();
  if (box) { box.className = "card muted"; box.textContent = "Buscando cenas semelhantes ao trecho atual…"; }
  try {
    const r = await lmsApi("/similar", { method: "POST", body: JSON.stringify({
      disc_id: _lmsNowPlaying.disc_id, video: _lmsNowPlaying.video,
      at_sec: at, modality: "visual", top_k: 12, debug: true }) });
    lmsRenderResults(r.results || []);
    if ((r.results || []).length && el("lmsResults"))
      el("lmsResults").insertAdjacentHTML("afterbegin",
        `<div class="muted" style="font-size:12px;margin-bottom:6px">Cenas semelhantes ao instante ${_lmsFmt(at)} do vídeo (inclusive de outros cursos):</div>`);
  } catch (e) { if (box) { box.className = "card danger"; box.textContent = e.message; } }
}

function lmsModeChange() {
  const m = el("lmsMode").value;
  if (m === "text")
    el("lmsInput").innerHTML = `<label>Consulta</label><input id="lmsQuery" placeholder="ex.: pilhas e filas, motor a vapor, normalização">`;
  else if (m === "image")
    el("lmsInput").innerHTML = `<label>Imagem de referência (cena/objeto)</label><input type="file" id="lmsFile" accept="image/*">`;
  else
    el("lmsInput").innerHTML = `<label>Clipe de áudio</label><input type="file" id="lmsFile" accept="audio/*">`+
      `<div class="muted" style="font-size:12px">Busca por voz é assíncrona (pode levar alguns segundos).</div>`;
}

async function viewLmsBusca() {
  h(`<div class="hdr"><h2>LMS de Vídeo — Busca</h2></div>
     <div class="card">
       <div class="row"><label>Modo</label>
         <select id="lmsMode" onchange="lmsModeChange()">
           <option value="text">Texto</option>
           <option value="image">Imagem (cena/objeto)</option>
           <option value="audio">Voz / Áudio</option>
         </select>
       </div>
       <div id="lmsInput"></div>
       <div class="row" style="margin-top:8px">
         <label>Curso</label><select id="lmsCurso"><option value="">Todos os cursos</option></select>
         <label>Área</label><select id="lmsArea"><option value="">Todas as áreas</option></select>
       </div>
       <div style="margin-top:10px"><button id="lmsGo" onclick="lmsSearch()">Buscar</button></div>
     </div>
     <video id="lmsPlayer" controls playsinline style="width:100%;max-width:820px;border-radius:10px;background:#000;display:none;margin:10px 0"></video>
     <div id="lmsPanel"></div>
     <div id="lmsResults" class="card muted">Faça uma busca para ver os trechos.</div>
     <div id="lmsDebug"></div>`);
  lmsModeChange(); lmsRefreshDebug();
  try {
    const cat = await lmsCatalog();
    el("lmsCurso").innerHTML = '<option value="">Todos os cursos</option>' +
      (cat.courses || []).map(c => `<option value="${esc(c.code)}">${esc(c.name)}</option>`).join("");
    el("lmsArea").innerHTML = '<option value="">Todas as áreas</option>' +
      (cat.areas || []).map(a => `<option value="${esc(a)}">${esc(a)}</option>`).join("");
  } catch (e) { /* catálogo pode estar vazio antes da ingestão */ }
}

async function lmsSearch() {
  const mode = el("lmsMode").value;
  const filters = {}; const curso = el("lmsCurso").value; const area = el("lmsArea").value;
  if (curso) filters.programs = [curso];
  if (area) filters.area = area;
  const body = { mode, filters, top_k: 12, debug: true };
  if (mode === "text") { body.query = (el("lmsQuery").value || "").trim(); if (!body.query) return; }
  else if (mode === "image") { const b = await _lmsFileB64(el("lmsFile")); if (!b) return alert("Selecione uma imagem."); body.image_b64 = b; }
  else { const b = await _lmsFileB64(el("lmsFile")); if (!b) return alert("Selecione um áudio."); body.audio_ref = { base64: b }; }
  el("lmsGo").disabled = true;
  el("lmsResults").className = "card muted"; el("lmsResults").textContent = "Buscando…";
  try {
    const r = await lmsApi("/search", { method: "POST", body: JSON.stringify(body) });
    lmsRenderResults(r.results || []);
  } catch (e) { el("lmsResults").className = "card danger"; el("lmsResults").textContent = e.message; }
  finally { el("lmsGo").disabled = false; }
}

function lmsRenderResults(items) {
  const box = el("lmsResults");
  if (!items.length) { box.className = "card muted"; box.textContent = "Nenhum trecho encontrado."; return; }
  box.className = "card";
  box.innerHTML = `<h3>${items.length} trecho(s)</h3>` + items.map(it => {
    const cursos = (it.programs || []).join(", ");
    const meta = `${esc(cursos)} · ${_lmsFmt(it.start_sec)} · ${esc(it.modality || "")}` +
      (it.score != null ? ` · score ${it.score}` : "");
    const vid = it.video || (it.media_url || '').replace('/lms/media/', '');
    const play = `lmsPlay(${JSON.stringify(it.media_url)}, ${it.start_sec || 0}, ${JSON.stringify(it.disc_id)}, ${JSON.stringify(vid)})`;
    const sum = `event.stopPropagation();lmsSummary(${JSON.stringify(it.disc_id)},${JSON.stringify(it.name || '')})`;
    return `<div class="lms-hit" onclick='${play}'>`+
      `<div><b>${esc(it.chapter_title || "—")}</b> — ${esc(it.name || "")}</div>`+
      `<div class="muted" style="font-size:12px">${meta}</div>`+
      `<div style="margin-top:4px">`+
      `<button class="sec" onclick='${sum}' title="Resumo e perguntas sobre o vídeo desta disciplina (Pegasus)">📝 resumo da aula</button>`+
      `<span class="muted" style="font-size:12px;margin-left:8px">▶ toque para tocar; use “cenas semelhantes ao trecho atual” no player</span></div></div>`;
  }).join("");
}

// media_url = /lms/media/<video>; deriva o path relativo do vídeo p/ o /lms/similar.
function _lmsVideoFromUrl(u) { return String(u || "").replace(/^.*\/lms\/media\//, ""); }

async function lmsSimilar(disc_id, video, start_sec) {
  const box = el("lmsResults");
  box.className = "card muted"; box.textContent = "Buscando trechos parecidos…";
  try {
    const r = await lmsApi("/similar", { method: "POST",
      body: JSON.stringify({ disc_id, video, start_sec, modality: "visual", top_k: 12, debug: true }) });
    lmsRenderResults(r.results || []);
    if ((r.results || []).length) el("lmsResults").insertAdjacentHTML("afterbegin",
      '<div class="muted" style="font-size:12px;margin-bottom:6px">Trechos visualmente parecidos (inclusive de outros cursos):</div>');
  } catch (e) { box.className = "card danger"; box.textContent = e.message; }
}

async function lmsSummary(disc_id, name) {
  const p = el("lmsPanel"); if (!p) return;
  p.innerHTML = `<div class="card muted">Gerando resumo de "${esc(name)}" (Pegasus)…</div>`;
  try {
    const r = await lmsApi("/summary", { method: "POST", body: JSON.stringify({ disc_id, debug: true }) });
    p.innerHTML = `<div class="card"><h3>📝 ${esc(name)}</h3>`+
      `<div style="white-space:pre-wrap;font-size:14px">${esc(r.summary || "")}</div>`+
      `<div class="row" style="margin-top:10px"><input id="lmsAskQ" placeholder="Pergunte sobre o vídeo…">`+
      `<button class="sec" onclick='lmsAsk(${JSON.stringify(disc_id)})'>Perguntar</button></div>`+
      `<div id="lmsAskA" class="muted" style="margin-top:8px"></div></div>`;
    p.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (e) { p.innerHTML = `<div class="card danger">${esc(e.message)}</div>`; }
}

async function lmsAsk(disc_id) {
  const q = (el("lmsAskQ").value || "").trim(); if (!q) return;
  const a = el("lmsAskA"); a.className = "muted"; a.textContent = "Consultando o vídeo (Pegasus)…";
  try {
    const r = await lmsApi("/ask", { method: "POST", body: JSON.stringify({ disc_id, question: q, debug: true }) });
    a.className = ""; a.style.whiteSpace = "pre-wrap"; a.textContent = r.answer || "";
  } catch (e) { a.className = "danger"; a.textContent = e.message; }
}

async function viewLmsQualidade() {
  h(`<div class="hdr"><h2>LMS de Vídeo — Qualidade da busca</h2></div>
     <div class="card">
       <p style="margin:0 0 6px">Mede, <b>sem curadoria manual</b>, se a busca em vídeo leva ao <b>momento certo</b> da aula.</p>
       <p class="muted" style="font-size:12.5px;margin:0">Para cada capítulo do acervo, usamos o texto falado nele como consulta e conferimos se o trecho devolvido cai justamente naquele ponto do vídeo. Quanto maior o acerto, melhor a busca encontra o instante certo.</p>
       <div class="row" style="margin-top:10px">
         <label>Disciplinas (amostra)</label><input id="lmsEvalLimit" type="number" value="8" min="1" max="89">
         <label>resultados por busca (k)</label><input id="lmsEvalK" type="number" value="5" min="1" max="20">
         <button id="lmsEvalGo" onclick="lmsRunEval()">Avaliar</button>
       </div>
     </div>
     <div id="lmsEvalOut" class="card muted">Clique em “Avaliar” para medir a qualidade da busca.</div>
     <div id="lmsDebug"></div>`);
  lmsRefreshDebug();
}

async function lmsRunEval() {
  const limit = parseInt(el("lmsEvalLimit").value || "8", 10);
  const k = parseInt(el("lmsEvalK").value || "5", 10);
  const out = el("lmsEvalOut"); out.className = "card muted";
  out.textContent = `Avaliando ${limit} disciplina(s)… (pode levar alguns segundos)`;
  el("lmsEvalGo").disabled = true;
  try {
    // Roda a avaliação e busca o catálogo em paralelo p/ traduzir ids -> nomes legíveis.
    const [r, cat] = await Promise.all([
      lmsApi("/eval", { method: "POST", body: JSON.stringify({ limit, k, verbose: true }) }),
      lmsCatalog().catch(() => ({ disciplines: [] })),
    ]);
    const map = {};
    (cat.disciplines || []).forEach(d => {
      map[d.disc_id] = { name: d.name, chaps: {} };
      (d.chapters || []).forEach(c => { map[d.disc_id].chaps[c.index] = c.title; });
    });
    const nm = id => (map[id] && map[id].name) || id;
    const chTitle = (id, idx) => (map[id] && map[id].chaps[idx]) || ("capítulo " + idx);
    const pc = x => (x != null ? (x * 100).toFixed(0) + "%" : "—");
    const cls = x => x >= 0.8 ? "good" : (x >= 0.5 ? "mid" : "bad");
    const metric = (v, label, desc) =>
      `<div class="lms-metric ${cls(v)}"><div class="v">${pc(v)}</div><div class="l">${label}</div><div class="d">${desc}</div></div>`;
    const snip = s => { s = (s || "").trim(); return esc(s.length > 70 ? s.slice(0, 70) + "…" : s); };
    const per = (r.per_query || []).map(q =>
      `<tr><td>${esc(nm(q.disc_id))}</td><td>${esc(chTitle(q.disc_id, q.chapter_index))}</td>`+
      `<td class="muted">${snip(q.query)}</td>`+
      `<td style="text-align:center">${q.hit1 ? "✅" : "❌"}</td>`+
      `<td style="text-align:center">${q.hitk ? "✅" : "❌"}</td></tr>`).join("");
    out.className = "card";
    out.innerHTML =
      `<div class="lms-verdict">A busca levou ao <b>momento exato</b> da aula em `+
        `<b>${pc(r.precision_at_1)}</b> das ${r.total} consultas (1º resultado). `+
        `Considerando os ${r.k} primeiros resultados, o acerto sobe para <b>${pc(r.hit_at_k)}</b>.</div>`+
      `<div class="lms-metrics">`+
        metric(r.precision_at_1, "Acerto no 1º resultado", "O topo da busca caiu no trecho certo do vídeo (o caso ideal).")+
        metric(r.hit_at_k, `Acerto entre os ${r.k} primeiros`, "O trecho certo apareceu na lista, mesmo que não no topo.")+
        metric(r.discipline_at_1, "Aula certa no 1º", "O 1º resultado veio da disciplina correta (ainda que em outro trecho).")+
      `</div>`+
      `<div class="muted" style="font-size:12px;margin:2px 0 6px">Amostra de ${r.total} consultas (um capítulo = uma consulta) · tolerância de ${r.tolerance_sec}s na janela do capítulo.</div>`+
      (per ? `<table style="margin-top:6px"><tr><th>Disciplina</th><th>Trecho (capítulo)</th><th>Consulta</th>`+
             `<th style="text-align:center">1º ✓</th><th style="text-align:center">top-${r.k} ✓</th></tr>${per}</table>` : "");
  } catch (e) { out.className = "card danger"; out.textContent = e.message; }
  finally { el("lmsEvalGo").disabled = false; }
}

async function viewLmsCatalogo() {
  h(`<div class="hdr"><h2>LMS de Vídeo — Catálogo</h2></div><div class="card muted">Carregando…</div>`);
  let cat; try { cat = await lmsCatalog(true); } catch (e) { return h(`<div class="hdr"><h2>LMS de Vídeo — Catálogo</h2></div><div class="card danger">${esc(e.message)}</div>`); }
  const disc = cat.disciplines || [];
  if (!disc.length) return h(`<div class="hdr"><h2>LMS de Vídeo — Catálogo</h2></div><div class="card muted">Catálogo vazio. Rode a ingestão (scripts/deploy-lms.sh).</div>`);
  const byArea = {}; disc.forEach(d => { (byArea[d.area] = byArea[d.area] || []).push(d); });
  const blocks = Object.keys(byArea).sort().map(a =>
    `<div class="card lms-cat-area"><h3>${esc(a)} <span class="muted" style="font-size:12px">(${byArea[a].length})</span></h3>` +
    byArea[a].map(d => {
      const cursos = (d.programs || []).map(p => `<span class="lms-course">${esc(p.code)}</span>`).join("");
      const chaps = (d.chapters || []).map(c =>
        `<a class="lms-chap" onclick='lmsPlay(${JSON.stringify("/lms/media/" + d.video)}, ${c.start_sec || 0}, ${JSON.stringify(d.disc_id)}, ${JSON.stringify(d.video)})'>`
        + `<span class="lms-chap-ic">▶</span> ${esc(c.title)} <span class="lms-chap-t">${_lmsFmt(c.start_sec)}</span></a>`).join("");
      return `<div class="lms-disc"><div class="lms-disc-head"><b>${esc(d.name)}</b>${cursos}</div>`
        + `<div class="lms-chaps">${chaps || '<span class="muted" style="font-size:12px">sem capítulos</span>'}</div></div>`;
    }).join("") + `</div>`).join("");
  h(`<div class="hdr"><h2>LMS de Vídeo — Catálogo</h2></div>
     <video id="lmsPlayer" controls playsinline style="width:100%;max-width:820px;border-radius:10px;background:#000;display:none;margin:10px 0"></video>${blocks}
     <div id="lmsDebug"></div>`);
  lmsRefreshDebug();
}

/* ---------------- Roteamento ---------------- */
/* ---------------- Orientador Context (serverless, data lake do Moodle) ----------------
   Módulo NOVO e isolado — coexiste com o Orientador Acadêmico (Neptune) sem alterá-lo.
   Consome o data lake (Athena) via agente serverless; RBAC por perfil Cognito. */
const OCTX = "/orientador-context/api";
let _octxBoot = null;

async function octxApi(path, opts = {}, _retried) {
  const r = await fetch(OCTX + path, { ...opts, headers: {
    "Content-Type": "application/json", "Authorization": "Bearer " + ID_TOKEN, ...(opts.headers || {}) } });
  if (r.status === 401 && !_retried) {
    if (await refreshToken()) return octxApi(path, opts, true);
    login(); throw new Error("Sessão expirada. Redirecionando para o login…");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
  return data;
}
async function octxBoot() {
  if (!_octxBoot) _octxBoot = (await octxApi("/bootstrap", { method: "POST", body: "{}" })).result;
  return _octxBoot;
}

async function viewOrientadorContextChat() {
  h(`<div class="hdr"><h2>Orientador Context — Chat</h2></div><div class="card muted">Carregando…</div>`);
  let boot;
  try { boot = await octxBoot(); } catch (e) { return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const students = (boot.students || []).map(s =>
    `<option value="${esc(s.username)}">${esc((s.nome || "") + " " + (s.sobrenome || "") + " (" + s.username + ")")}</option>`).join("");
  const coordOpt = boot.is_coord_capable
    ? `<option value="__coord__">👤 Coordenação (visão do curso)</option>` : "";
  h(`<div class="hdr"><h2>Orientador Context — Chat</h2>
       <span class="muted">dados do Moodle via data lake (Athena) · RBAC por perfil</span></div>
     <div class="card octx-chat-card">
       <div class="row"><label>Atuar como:</label> <select id="octx-who" onchange="octxNova()">${coordOpt}${students}</select></div>
       <div id="octx-chat" class="ori-chat"></div>
       <div class="ori-ask">
         <input id="octx-q" placeholder="Pergunte sobre desempenho, disciplinas, risco de evasão…"
                onkeydown="if(event.key==='Enter')octxSend()">
         <button class="btn" onclick="octxSend()">Enviar</button>
         <button class="btn sec" onclick="octxNova()" title="Inicia uma nova conversa (limpa a memória da sessão)">Nova conversa</button>
       </div>
       <details class="octx-debug" id="octx-debug">
         <summary>🔎 Debug — o que o agente consumiu (requisição, tools, serviços, memória)</summary>
         <div id="octx-debug-body" class="octx-debug-body muted">Envie uma pergunta para ver os detalhes desta resposta.</div>
       </details>
     </div>`);
  window._octxHist = [];
  // Nonce de conversa por carregamento de página: garante uma sessão do AgentCore Runtime
  // com o código atual (evita afinidade a instância antiga) e habilita "Nova conversa".
  if (!window._octxConv) window._octxConv = Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
}
function octxNova() {
  window._octxConv = Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  window._octxHist = [];
  const box = el("octx-chat"); if (box) box.innerHTML = "";
  const dbg = el("octx-debug-body");
  if (dbg) { dbg.classList.add("muted"); dbg.innerHTML = "Envie uma pergunta para ver os detalhes desta resposta."; }
}
async function octxSend() {
  const who = el("octx-who").value, q = (el("octx-q").value || "").trim();
  if (!q) return;
  const mode = who === "__coord__" ? "coord" : "aluno";
  const student_id = who === "__coord__" ? null : who;
  const box = el("octx-chat");
  box.innerHTML += `<div class="octx-turn user"><span class="octx-who">Você</span><div class="msg user">${esc(q)}</div></div>`;
  el("octx-q").value = "";
  box.innerHTML += `<div class="octx-turn bot" id="octx-wait"><span class="octx-who">Orientador Context</span><div class="msg bot">…</div></div>`;
  box.scrollTop = box.scrollHeight;
  const feReq = { question: q, mode, student_id, conv: window._octxConv, history: window._octxHist.slice() };
  try {
    const d = await octxApi("/ask", { method: "POST", body: JSON.stringify(feReq) });
    const a = (d.result && d.result.answer) || "(sem resposta)";
    el("octx-wait").outerHTML = `<div class="octx-turn bot"><span class="octx-who">Orientador Context</span><div class="msg bot">${_oriMd(a)}</div></div>`;
    window._octxHist.push({ role: "user", text: q }, { role: "assistant", text: a });
    if (window._octxHist.length > 16) window._octxHist = window._octxHist.slice(-16);
    _octxDebug(feReq, (d.result && d.result.debug) || null, null);
  } catch (e) {
    el("octx-wait").outerHTML = `<div class="octx-turn bot"><span class="octx-who">Orientador Context</span><div class="msg bot danger">${esc(e.message)}</div></div>`;
    _octxDebug(feReq, null, e.message);
  }
  box.scrollTop = box.scrollHeight;
}
function _octxDebug(feReq, dbg, err) {
  const body = el("octx-debug-body");
  if (!body) return;
  body.classList.remove("muted");
  dbg = dbg || {};
  const ag = dbg.agent || {};
  const req = dbg.request || {};
  const tok = ag.tokens || {};
  const mem = ag.memory || {};
  const li = (arr, f) => (arr && arr.length ? arr.map(f).join("") : '<li class="muted">—</li>');
  const tools = li(ag.tools, t => `<li><b>${esc(t.name)}</b> ×${t.calls}`
    + (t.errors ? ` <span class="danger">(${t.errors} erro)</span>` : "")
    + ` · ${t.time_s}s`
    + (t.input && Object.keys(t.input).length ? ` · input <code>${esc(JSON.stringify(t.input))}</code>` : "")
    + `</li>`);
  const svcs = li(ag.services, s => `<li><b>${esc(s.service)}</b> — ${esc(s.detail)}</li>`);
  const errBlock = err ? `<div class="octx-dbg-sec danger">Erro: ${esc(err)}</div>` : "";
  body.innerHTML = errBlock + `
    <div class="octx-dbg-sec"><h4>1) FE → BE (o que o front enviou)</h4><ul>
      <li>pergunta: <code>${esc(feReq.question || "")}</code></li>
      <li>modo: <b>${esc(req.mode || feReq.mode || "")}</b> · aluno: <b>${esc(req.student_id || feReq.student_id || "—")}</b></li>
      <li>turnos de histórico enviados: <b>${req.history_turns != null ? req.history_turns : (feReq.history || []).length}</b></li>
      <li>sessão de memória: <code>${esc((req.session_id || "").slice(0, 16))}${req.session_id ? "…" : ""}</code> · actor: <code>${esc(req.actor_id || "—")}</code></li>
    </ul></div>
    <div class="octx-dbg-sec"><h4>2) Modelo &amp; consumo</h4><ul>
      <li>modelo: <b>${esc(ag.model || "—")}</b></li>
      <li>tokens: entrada <b>${tok.input || 0}</b> · saída <b>${tok.output || 0}</b> · total <b>${tok.total || 0}</b></li>
      <li>latência: <b>${ag.latency_ms || 0} ms</b> · ciclos do agente: <b>${ag.cycles || 0}</b></li>
    </ul></div>
    <div class="octx-dbg-sec"><h4>3) Tools usadas</h4><ul>${tools}</ul></div>
    <div class="octx-dbg-sec"><h4>4) Serviços / AWS consumidos</h4><ul>${svcs}</ul></div>
    <div class="octx-dbg-sec"><h4>5) Memória (AgentCore Memory)</h4><ul>
      <li>${mem.enabled ? "ativa" : "inativa"} — ${esc(mem.backend || "—")}</li>
    </ul></div>
    <details class="octx-dbg-raw"><summary>JSON bruto</summary><pre>${esc(JSON.stringify(dbg, null, 2))}</pre></details>`;
}

async function viewOrientadorContextRisco() {
  h(`<div class="hdr"><h2>Orientador Context — Risco de evasão</h2></div><div class="card muted">Carregando…</div>`);
  try {
    const d = await octxApi("/risco", { method: "POST", body: JSON.stringify({ min_reprovacoes: 3 }) });
    const rows = (d.result && d.result.alunos) || [];
    const trs = rows.map(a => `<tr><td>${esc(a.username)}</td><td>${esc((a.nome || "") + " " + (a.sobrenome || ""))}</td>`
      + `<td>${esc(a.faculdade || "")}</td><td>${esc(a.reprovacoes || "")}</td></tr>`).join("");
    h(`<div class="hdr"><h2>Orientador Context — Risco de evasão</h2>
         <span class="muted">≥ 3 reprovações · restrito à coordenação (RBAC)</span></div>
       <div class="card"><table class="tbl"><thead><tr><th>Usuário</th><th>Nome</th><th>Faculdade</th>
         <th>Reprovações</th></tr></thead><tbody>${trs
         || `<tr><td colspan="4" class="muted">Sem alunos nesse critério (ou perfil sem permissão).</td></tr>`}
       </tbody></table></div>`);
  } catch (e) { h(`<div class="card danger">${esc(e.message)}</div>`); }
}

async function viewOrientadorContextDesempenho() {
  h(`<div class="hdr"><h2>Orientador Context — Desempenho</h2></div><div class="card muted">Carregando…</div>`);
  try {
    const d = await octxApi("/desempenho", { method: "POST", body: "{}" });
    const rows = (d.result && d.result.faculdades) || [];
    const trs = rows.map(f => `<tr><td>${esc(f.faculdade)}</td><td>${esc(f.notas)}</td>`
      + `<td>${esc(f.media)}</td><td>${esc(f.pct_reprovacao)}%</td></tr>`).join("");
    h(`<div class="hdr"><h2>Orientador Context — Desempenho por faculdade</h2></div>
       <div class="card"><table class="tbl"><thead><tr><th>Faculdade</th><th>Notas</th><th>Média</th>
         <th>% Reprovação</th></tr></thead><tbody>${trs
         || `<tr><td colspan="4" class="muted">Sem dados (perfil sem permissão).</td></tr>`}</tbody></table></div>`);
  } catch (e) { h(`<div class="card danger">${esc(e.message)}</div>`); }
}

// ---- Orientador Context: telas com paridade ao Acadêmico (adaptadas ao data lake) ----
function _octxStudents(boot) {
  return (boot.students || []).map(s =>
    `<option value="${esc(s.username)}">${esc((s.nome||"")+" "+(s.sobrenome||"")+" ("+s.username+")")}</option>`).join("");
}
function _octxNota(n) {
  const cls = n.situacao === "reprovado" ? "danger" : "";
  return `<span class="${cls}">${esc(n.nota)} · ${esc(n.situacao||"")}</span>`;
}
async function _octxBootOrErr() {
  try { return await octxBoot(); } catch (e) { h(`<div class="card danger">${esc(e.message)}</div>`); return null; }
}

async function viewOrientadorContextAlunos() {
  h(`<div class="hdr"><h2>Orientador Context — Alunos</h2></div><div class="card muted">Carregando…</div>`);
  const boot = await _octxBootOrErr(); if (!boot) return;
  h(`<div class="hdr"><h2>Orientador Context — Alunos</h2></div>
     <div class="card"><div class="row"><label>Aluno:</label> <select id="octx-al">${_octxStudents(boot)}</select></div></div>
     <div id="octx-al-body"></div>`);
  async function load() {
    const sid = el("octx-al").value; const host = el("octx-al-body");
    host.innerHTML = `<div class="card muted">Carregando perfil…</div>`;
    try {
      const p = (await octxApi("/perfil", { method:"POST", body: JSON.stringify({ student_id: sid }) })).result;
      const a = p.aluno || {};
      const rows = (p.notas||[]).map(n => `<tr><td>${esc(n.faculdade)}</td><td>${esc(n.disciplina)}</td><td>${_octxNota(n)}</td></tr>`).join("");
      host.innerHTML = `<div class="card">
        <h3>${esc((a.nome||"")+" "+(a.sobrenome||""))} <span class="muted">· ${esc(p.faculdade||"")}</span></h3>
        <p class="muted">${esc(a.email||"")} — aprovadas: ${p.aprovadas} · reprovações: ${p.reprovacoes}</p>
        <table class="tbl"><thead><tr><th>Faculdade</th><th>Disciplina</th><th>Nota</th></tr></thead><tbody>${rows||`<tr><td colspan=3 class=muted>Sem notas.</td></tr>`}</tbody></table></div>`;
    } catch (e) { host.innerHTML = `<div class="card danger">${esc(e.message)}</div>`; }
  }
  el("octx-al").addEventListener("change", load); load();
}

async function viewOrientadorContextTrilha() {
  h(`<div class="hdr"><h2>Orientador Context — Trilha</h2></div><div class="card muted">Carregando…</div>`);
  const boot = await _octxBootOrErr(); if (!boot) return;
  h(`<div class="hdr"><h2>Orientador Context — Trilha</h2><span class="muted">disciplinas a refazer, pendentes e concluídas</span></div>
     <div class="card"><div class="row"><label>Aluno:</label> <select id="octx-tr">${_octxStudents(boot)}</select></div></div>
     <div id="octx-tr-body"></div>`);
  async function load() {
    const sid = el("octx-tr").value; const host = el("octx-tr-body");
    host.innerHTML = `<div class="card muted">Carregando…</div>`;
    try {
      const t = (await octxApi("/trilha", { method:"POST", body: JSON.stringify({ student_id: sid }) })).result;
      const lst = (arr,f) => arr.length ? arr.map(f).join("") : `<li class="muted">—</li>`;
      host.innerHTML = `<div class="card">
        <div class="row"><b>Conclusão do curso:</b> ${t.pct_conclusao}% (${t.aprovadas.length}/${t.total_curso})</div>
        <h3 class="danger">A refazer (reprovadas)</h3><ul>${lst(t.a_refazer, d=>`<li>${esc(d.disciplina)} — nota ${esc(d.nota)}</li>`)}</ul>
        <h3>Ainda não cursadas</h3><ul>${lst(t.nao_cursadas, d=>`<li>${esc(d.disciplina)}</li>`)}</ul>
        <h3>Concluídas</h3><ul>${lst(t.aprovadas, d=>`<li>${esc(d.disciplina)} — nota ${esc(d.nota)}</li>`)}</ul></div>`;
    } catch (e) { host.innerHTML = `<div class="card danger">${esc(e.message)}</div>`; }
  }
  el("octx-tr").addEventListener("change", load); load();
}

async function viewOrientadorContextInsights() {
  h(`<div class="hdr"><h2>Orientador Context — Insights</h2></div><div class="card muted">Carregando…</div>`);
  const boot = await _octxBootOrErr(); if (!boot) return;
  h(`<div class="hdr"><h2>Orientador Context — Insights</h2></div>
     <div class="card"><div class="row"><label>Aluno:</label> <select id="octx-in">${_octxStudents(boot)}</select></div></div>
     <div id="octx-in-body"></div>`);
  async function load() {
    const sid = el("octx-in").value; const host = el("octx-in-body");
    host.innerHTML = `<div class="card muted">Analisando…</div>`;
    try {
      const i = (await octxApi("/insights", { method:"POST", body: JSON.stringify({ student_id: sid }) })).result;
      const cor = { alto:"danger", medio:"", baixo:"" }[i.risco_evasao] || "";
      host.innerHTML = `<div class="card">
        <p><b>Risco de evasão:</b> <span class="${cor}">${esc(i.risco_evasao)}</span> · <b>Conclusão:</b> ${i.pct_conclusao}% · <b>Competências:</b> ${i.competencias_desenvolvidas}</p>
        <h3>Pontos fortes</h3><ul>${(i.pontos_fortes||[]).map(n=>`<li>${esc(n.disciplina)} — ${esc(n.nota)}</li>`).join("")||"<li class=muted>—</li>"}</ul>
        <h3 class="danger">Pontos fracos</h3><ul>${(i.pontos_fracos||[]).map(n=>`<li>${esc(n.disciplina)} — ${esc(n.nota)} (${esc(n.situacao||"")})</li>`).join("")||"<li class=muted>—</li>"}</ul>
        <h3>Recomendações</h3><ul>${(i.recomendacoes||[]).map(r=>`<li>${esc(r)}</li>`).join("")}</ul></div>`;
    } catch (e) { host.innerHTML = `<div class="card danger">${esc(e.message)}</div>`; }
  }
  el("octx-in").addEventListener("change", load); load();
}

async function viewOrientadorContextCursos() {
  h(`<div class="hdr"><h2>Orientador Context — Cursos</h2></div><div class="card muted">Carregando…</div>`);
  const boot = await _octxBootOrErr(); if (!boot) return;
  const facs = (boot.faculdades||[]).map(f=>`<option value="${esc(f)}">${esc(f)}</option>`).join("");
  h(`<div class="hdr"><h2>Orientador Context — Cursos</h2></div>
     <div class="card"><div class="row"><label>Faculdade:</label> <select id="octx-cs">${facs}</select></div></div>
     <div id="octx-cs-body"></div>`);
  async function load() {
    const f = el("octx-cs").value; const host = el("octx-cs-body");
    host.innerHTML = `<div class="card muted">Carregando…</div>`;
    try {
      const p = (await octxApi("/programa", { method:"POST", body: JSON.stringify({ faculdade: f }) })).result;
      const rows = (p.disciplinas||[]).map(d=>`<tr><td>${esc(d.disciplina)}</td><td>${esc(d.matriculados||0)}</td><td>${esc(d.media||"—")}</td></tr>`).join("");
      host.innerHTML = `<div class="card"><p class="muted">${esc(p.faculdade)} — ${p.total_disciplinas} disciplinas · ${p.total_alunos} alunos</p>
        <table class="tbl"><thead><tr><th>Disciplina</th><th>Matriculados</th><th>Média</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    } catch (e) { host.innerHTML = `<div class="card danger">${esc(e.message)}</div>`; }
  }
  el("octx-cs").addEventListener("change", load); load();
}

async function viewOrientadorContextCurriculo() {
  h(`<div class="hdr"><h2>Orientador Context — Currículo</h2></div><div class="card muted">Carregando…</div>`);
  try {
    const c = (await octxApi("/curriculo", { method:"POST", body:"{}" })).result;
    const facs = (c.faculdades||[]).map(f=>`<tr><td>${esc(f.faculdade)}</td><td>${esc(f.disciplinas)}</td><td>${esc(f.competencias)}</td></tr>`).join("");
    const ponte = (c.disciplinas_ponte||[]).map(d=>`<li>${esc(d.disciplina)} (${esc(d.n_faculdades)} faculdades)</li>`).join("") || `<li class="muted">Nenhuma disciplina compartilhada entre faculdades.</li>`;
    h(`<div class="hdr"><h2>Orientador Context — Currículo</h2></div>
       <div class="card"><h3>Faculdades</h3>
         <table class="tbl"><thead><tr><th>Faculdade</th><th>Disciplinas</th><th>Competências</th></tr></thead><tbody>${facs}</tbody></table></div>
       <div class="card"><h3>Disciplinas-ponte</h3><ul>${ponte}</ul></div>`);
  } catch (e) { h(`<div class="card danger">${esc(e.message)}</div>`); }
}

async function viewOrientadorContextCompetencias() {
  h(`<div class="hdr"><h2>Orientador Context — Competências</h2></div><div class="card muted">Carregando…</div>`);
  try {
    const m = (await octxApi("/competencias-matriz", { method:"POST", body:"{}" })).result;
    const cells = m.celulas || [];
    const comps = [...new Set(cells.map(c=>c.competencia))].sort();
    const facs = [...new Set(cells.map(c=>c.faculdade))].sort();
    const val = {}; cells.forEach(c => { val[c.competencia+"|"+c.faculdade] = c.disciplinas; });
    const head = `<tr><th>Competência ⧵ Faculdade</th>${facs.map(f=>`<th>${esc(f)}</th>`).join("")}</tr>`;
    const body = comps.map(cp => `<tr><td>${esc(cp)}</td>${facs.map(f=>{
      const v = val[cp+"|"+f]; return v ? `<td style="background:#e6f4ea;text-align:center">${esc(v)}</td>` : `<td style="text-align:center" class="muted">—</td>`;
    }).join("")}</tr>`).join("");
    h(`<div class="hdr"><h2>Orientador Context — Competências × Faculdade</h2><span class="muted">nº de disciplinas que desenvolvem cada competência</span></div>
       <div class="card"><table class="tbl">${head}${body}</table></div>`);
  } catch (e) { h(`<div class="card danger">${esc(e.message)}</div>`); }
}

async function viewOrientadorContextGrafo() {
  h(`<div class="hdr"><h2>Orientador Context — Grafo</h2></div><div class="card muted">Carregando…</div>`);
  const boot = await _octxBootOrErr(); if (!boot) return;
  const typeLegend = Object.keys(ORI_COLORS).map(t => `<span class="ori-leg"><i style="background:${ORI_COLORS[t]}"></i>${ORI_TYPE_PT[t]}</span>`).join("");
  const studentLegend = `<span class="ori-leg"><i style="background:${ORI_STATUS_COLORS.done}"></i>Concluída</span><span class="ori-leg"><i style="background:${ORI_STATUS_COLORS.todo}"></i>Reprovada/pendente</span><span class="ori-leg">● disciplina</span><span class="ori-leg">★ competência</span>`;
  h(`<div class="hdr"><h2>Orientador Context — Grafo</h2></div>
     <div class="card">
       <div class="row"><label>Ver:</label>
         <select id="octx-scope"><option value="student">Aluno</option><option value="full">Tudo (faculdades × disciplinas)</option></select>
         <select id="octx-ent">${_octxStudents(boot)}</select>
         <button class="btn" id="octx-gg">Montar grafo</button><span id="octx-gc" class="muted"></span></div>
       <div class="ori-legend" id="octx-leg">${studentLegend}</div>
       <div id="octx-canvas" class="ori-canvas"></div>
       <p class="muted">Arraste os nós, use a roda para zoom. No modo Aluno, clique num nó Aluno para recentralizar.</p>
     </div>`);
  const scopeSel = el("octx-scope"), entSel = el("octx-ent");
  function sync(){ entSel.style.display = scopeSel.value === "full" ? "none" : ""; el("octx-leg").innerHTML = scopeSel.value==="student"?studentLegend:typeLegend; }
  async function load() {
    const scope = scopeSel.value, id = scope==="full"?null:entSel.value;
    const cv = el("octx-canvas"); cv.innerHTML = `<div class="muted" style="padding:1rem">Montando…</div>`; el("octx-gc").textContent="";
    try {
      const d = (await octxApi("/grafo", { method:"POST", body: JSON.stringify({ scope, id, mode:"coord" }) })).result || {};
      el("octx-gc").textContent = `${d.counts?.nodes||0} nós · ${d.counts?.edges||0} ligações`;
      _oriForceGraph(cv, d, (n)=>{ if(n.type==="Student"){ scopeSel.value="student"; sync(); load(); } });
    } catch (e) { cv.innerHTML = `<div class="danger" style="padding:1rem">${esc(e.message)}</div>`; }
  }
  scopeSel.addEventListener("change", ()=>{ sync(); load(); });
  el("octx-gg").addEventListener("click", load);
  sync(); load();
}

async function viewOrientadorContextCoord() {
  h(`<div class="hdr"><h2>Orientador Context — Coordenação</h2></div><div class="card muted">Carregando…</div>`);
  const boot = await _octxBootOrErr(); if (!boot) return;
  if (!boot.is_coord_capable) return h(`<div class="hdr"><h2>Orientador Context — Coordenação</h2></div><div class="card muted">Restrito à coordenação (perfil admin/professor).</div>`);
  const facs = (boot.faculdades||[]).map(f=>`<option value="${esc(f)}">${esc(f)}</option>`).join("");
  h(`<div class="hdr"><h2>Orientador Context — Coordenação</h2></div>
     <div class="card"><h3>Alunos por faculdade</h3><div id="octx-vg" class="muted">Carregando…</div></div>
     <div class="card"><h3>Grade noturna (conflito-consciente)</h3>
       <div class="row"><label>Faculdade:</label> <select id="octx-gf">${facs}</select>
         <button class="btn" id="octx-gb">Montar grade</button></div>
       <div id="octx-grade"></div></div>`);
  try {
    const vg = (await octxApi("/visao-geral", { method:"POST", body: JSON.stringify({ mode:"coord" }) })).result;
    el("octx-vg").innerHTML = `<table class="tbl"><thead><tr><th>Faculdade</th><th>Alunos</th></tr></thead><tbody>${(vg.cursos||[]).map(c=>`<tr><td>${esc(c.faculdade)}</td><td>${esc(c.alunos)}</td></tr>`).join("")}</tbody></table>`;
  } catch (e) { el("octx-vg").innerHTML = `<span class="danger">${esc(e.message)}</span>`; }
  async function grade() {
    const f = el("octx-gf").value; const host = el("octx-grade");
    host.innerHTML = `<div class="muted">Montando grade…</div>`;
    try {
      const g = (await octxApi("/grade-noturna", { method:"POST", body: JSON.stringify({ mode:"coord", faculdade: f }) })).result;
      const byNoite = {}; (g.grade||[]).forEach(s => { (byNoite[s.noite]=byNoite[s.noite]||[]).push(s); });
      const blocks = Object.keys(byNoite).sort().map(nt => `<div class="card" style="margin:.4rem 0"><b>Noite ${nt}</b>${byNoite[nt].map(s=>`<div>Horário ${s.horario}: ${s.disciplinas.map(d=>esc(d.disciplina)+" ("+d.matriculados+")").join(", ")||"<span class=muted>—</span>"}</div>`).join("")}</div>`).join("");
      host.innerHTML = `<p class="muted">${esc(g.faculdade)} — ${g.total_disciplinas} disciplinas · salas no pico: ${g.salas_no_pico}${(g.nao_alocadas||[]).length?` · não alocadas: ${g.nao_alocadas.length}`:""}</p>${blocks}`;
    } catch (e) { host.innerHTML = `<div class="danger">${esc(e.message)}</div>`; }
  }
  el("octx-gb").addEventListener("click", grade); grade();
}

/* ---------------- AgentCore — Gateway Inference ----------------
   Chat via o AgentCore Gateway (target bedrock-mantle) atraves de um agente Strands no
   AgentCore Runtime (observability nativa). O browser fala so com o Router (/agentcore/api). */
const GWINF = "/agentcore/api";
async function gwinfApi(path, opts = {}, _retried) {
  const r = await fetch(GWINF + path, { ...opts, headers: {
    "Content-Type": "application/json", "Authorization": "Bearer " + ID_TOKEN, ...(opts.headers || {}) } });
  if (r.status === 401 && !_retried) {
    if (await refreshToken()) return gwinfApi(path, opts, true);
    login(); throw new Error("Sessão expirada. Redirecionando para o login…");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
  return data;
}
async function viewGwInference() {
  h(`<div class="hdr"><h2>Gateway Inference — Inference</h2>
       <span class="muted">chat via AgentCore Gateway (bedrock-mantle) · agente Strands no EKS Fargate · streaming</span></div>
     <div class="card muted">Carregando modelos…</div>`);
  let mods;
  try { mods = await gwinfApi("/models"); }
  catch (e) { return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const groups = mods.grouped || {};
  const opts = Object.keys(groups).sort().map(g =>
    `<optgroup label="${esc(g)}">` +
    groups[g].map(m => `<option value="${esc(m)}">${esc(m.split("/").pop())}</option>`).join("") +
    `</optgroup>`).join("");
  h(`<div class="hdr"><h2>Gateway Inference — Inference</h2>
       <span class="muted">${mods.count} modelos · AgentCore Gateway · agente Strands no EKS Fargate · streaming SSE</span></div>
     <div class="card octx-chat-card">
       <div class="row"><label>Modelo:</label> <select id="gw-model">${opts}</select>
         <button class="btn sec" onclick="gwNova()" title="Nova conversa">Nova conversa</button></div>
       <div id="gw-chat" class="ori-chat" style="max-height:none;flex:1 1 auto;min-height:0"></div>
       <div class="ori-ask">
         <input id="gw-q" placeholder="Pergunte qualquer coisa ao modelo selecionado…"
                onkeydown="if(event.key==='Enter')gwSend()">
         <button class="btn" onclick="gwSend()">Enviar</button>
       </div>
       <details class="octx-debug" id="gw-debug"><summary>🔎 Debug — modelo, tokens, latência, gateway</summary>
         <div id="gw-debug-body" class="octx-debug-body muted">Envie uma pergunta para ver os detalhes.</div></details>
     </div>`);
  if (!window._gwConv) window._gwConv = Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
}
function gwNova(){ window._gwConv = Date.now().toString(36)+Math.random().toString(36).slice(2,10);
  window._gwHist = []; window._gwTurn = 0;   // limpa a memoria da conversa
  const b=el("gw-chat"); if(b) b.innerHTML=""; const d=el("gw-debug-body");
  if(d){ d.classList.add("muted"); d.innerHTML="Envie uma pergunta para ver os detalhes."; } }
/* Streaming SSE: o backend roda no EKS Fargate (pod atrás do ALB) e emite deltas
   token-a-token via /agentcore/api/ask/stream. Consumimos com fetch + ReadableStream. */
async function gwStream(body, onDelta, _retried) {
  const r = await fetch(GWINF + "/ask/stream", {
    method: "POST", headers: {
      "Content-Type": "application/json", "Authorization": "Bearer " + ID_TOKEN },
    body: JSON.stringify(body) });
  if (r.status === 401 && !_retried) {
    if (await refreshToken()) return gwStream(body, onDelta, true);
    login(); throw new Error("Sessão expirada. Redirecionando para o login…");
  }
  if (!r.ok || !r.body) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || ("HTTP " + r.status));
  }
  const reader = r.body.getReader(), dec = new TextDecoder();
  let buf = "", debug = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, i); buf = buf.slice(i + 2);
      const line = frame.split("\n").find(l => l.startsWith("data:"));
      if (!line) continue;
      let ev; try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
      if (ev.type === "delta") onDelta(ev.text || "");
      else if (ev.type === "done") debug = ev.debug || {};
      else if (ev.type === "error") throw new Error(ev.error || "falha no streaming");
    }
  }
  return debug || {};
}
function _gwExchangeHtml(dbg){
  const rq=dbg.request, rp=dbg.response, rt=dbg.route||{};
  if(!rq && !rp) return "";
  const msgs=(rq&&rq.messages||[]).map(m=>
    `<div class="octx-turn"><span class="octx-who">${esc(m.role)}</span>`+
    `<div class="msg ${m.role==='user'?'user':'bot'}" style="white-space:pre-wrap">${esc(m.text||"")}</div></div>`).join("");
  const reqHtml = rq ? `<details open class="octx-dbg-raw"><summary>➡️ Requisição — EKS → Gateway</summary>
      <ul>
        <li>endpoint: <code>${esc(rq.endpoint||"")}</code></li>
        <li>API: <b>${esc(rq.api||"")}</b> · classe: <code>${esc(rq.provider_class||"")}</code></li>
        <li>target: <code>${esc(rq.target||"")}</code> · model: <code>${esc(rq.model||"")}</code></li>
        <li>auth: <code>${esc(rq.auth||"")}</code>${rq.max_tokens?` · max_tokens: <b>${rq.max_tokens}</b>`:""}</li>
        <li>mensagens enviadas (${rq.messages_count||0}):</li>
      </ul>${msgs}</details>` : "";
  const respHtml = rp ? `<details open class="octx-dbg-raw"><summary>⬅️ Resposta — Gateway → EKS</summary>
      <ul>
        <li>status: <b>${esc(rp.status||"")}</b> · stop: <code>${esc(rp.stop_reason||"—")}</code></li>
        <li>tokens: entrada <b>${(rp.tokens||{}).input||0}</b> · saída <b>${(rp.tokens||{}).output||0}</b> · total <b>${(rp.tokens||{}).total||0}</b></li>
        <li>chars da resposta: <b>${rp.output_chars||0}</b> · latência: <b>${rp.latency_ms||0} ms</b></li>
      </ul></details>` : "";
  return reqHtml + respHtml;
}
async function gwSend() {
  const model = el("gw-model").value, q = (el("gw-q").value || "").trim();
  if (!q) return;
  const who = esc(model.split("/").pop());
  const box = el("gw-chat");
  box.innerHTML += `<div class="octx-turn user"><span class="octx-who">Você</span><div class="msg user">${esc(q)}</div></div>`;
  el("gw-q").value = "";
  // id ÚNICO por turno (evita colisao de id quando ha varias respostas na conversa).
  const tid = "gw-live-" + (window._gwTurn = (window._gwTurn || 0) + 1);
  box.innerHTML += `<div class="octx-turn bot"><span class="octx-who">${who}</span><div class="msg bot" id="${tid}"><span class="muted">gerando resposta…</span></div></div>`;
  box.scrollTop = box.scrollHeight;
  const live = el(tid);
  if (!window._gwHist) window._gwHist = [];
  const history = window._gwHist.slice(-20);   // memoria da conversa (turnos anteriores)
  let acc = "";
  try {
    // Inference NAO exibe streaming: acumulamos em silencio e so mostramos a resposta
    // FINAL, ja verificada pelo guardrail de saida (evita exibir texto cru que seria
    // bloqueado). O backend continua streamando; o buffering e so no FE.
    const dbg = await gwStream(
      { question: q, model, system_prompt: window._gwSys || "", conv: window._gwConv, history },
      (t) => { acc += t; });
    const g = dbg.guardrail || {};
    // Guardrail de saída bloqueou: usa a mensagem do guardrail no lugar do texto gerado.
    if (g.blocked && g.stage === "output" && g.message) acc = g.message;
    const finalText = acc || "(sem resposta)";
    live.innerHTML = _oriMd(finalText);
    if (g.blocked) live.classList.add("danger");
    // memoria: registra o turno (pergunta + resposta final) para o proximo envio.
    window._gwHist.push({ role: "user", text: q }, { role: "assistant", text: finalText });
    const tok = dbg.tokens || {};
    const gbadge = g.blocked
      ? `<span class="danger">bloqueado (${g.stage === "input" ? "entrada" : "saída"})</span>`
      : `<b>OK</b>`;
    const body = el("gw-debug-body"); body.classList.remove("muted");
    body.innerHTML = `<div class="octx-dbg-sec"><ul>
      <li>host: <b>EKS Fargate (streaming SSE)</b></li>
      <li>modelo: <b>${esc(dbg.model || model)}</b></li>
      <li>guardrail (Bedrock): ${gbadge}</li>
      <li>tokens: entrada <b>${tok.input||0}</b> · saída <b>${tok.output||0}</b> · total <b>${tok.total||0}</b></li>
      <li>gateway: <code>${esc(dbg.gateway||"")}</code></li>
    </ul></div>${_gwExchangeHtml(dbg)}
    <details class="octx-dbg-raw"><summary>JSON bruto</summary><pre>${esc(JSON.stringify(dbg,null,2))}</pre></details>`;
  } catch (e) {
    live.innerHTML = (acc ? _oriMd(acc) + "<br>" : "") + `<span class="danger">${esc(e.message)}</span>`;
  }
  box.scrollTop = box.scrollHeight;
}
function viewGwSysprompt() {
  const cur = window._gwSys || "";
  h(`<div class="hdr"><h2>Gateway Inference — System-prompt</h2>
       <span class="muted">guardado na sessão do navegador; enviado em toda inferência</span></div>
     <div class="card">
       <label>System prompt</label>
       <textarea id="gw-sys" style="min-height:160px">${esc(cur)}</textarea>
       <div style="margin-top:8px"><button class="btn" onclick="window._gwSys=el('gw-sys').value; alert('System-prompt salvo para esta sessão.')">Salvar</button>
       <button class="btn sec" onclick="window._gwSys='';el('gw-sys').value=''">Limpar</button></div>
     </div>`);
}
function _gwSoon(title, desc){ h(`<div class="hdr"><h2>Gateway Inference — ${title}</h2></div>
  <div class="card"><p>${desc}</p><p class="muted">Em construção — próxima fase do módulo.</p></div>`); }
async function _gwLoadModels(){
  if(!window._gwModels){ window._gwModels = await gwinfApi("/models"); }
  return window._gwModels;
}
function _gwModelOpts(sel){
  const g=(window._gwModels&&window._gwModels.grouped)||{};
  return Object.keys(g).sort().map(p=>`<optgroup label="${esc(p)}">`+
    g[p].map(m=>`<option value="${esc(m)}"${m===sel?" selected":""}>${esc(m.split("/").pop())}</option>`).join("")+
    `</optgroup>`).join("");
}
async function viewGwEval(){
  h(`<div class="hdr"><h2>Gateway Inference — Evaluation</h2></div><div class="card muted">Carregando modelos…</div>`);
  try{ await _gwLoadModels(); }catch(e){ return h(`<div class="card danger">${esc(e.message)}</div>`); }
  const g=(window._gwModels.grouped)||{}; const flat=window._gwModels.models||[];
  const dflt=[flat.find(m=>/claude/.test(m)),flat.find(m=>/deepseek/.test(m)),flat.find(m=>/qwen|gemma|mistral/.test(m))];
  const judge=flat.find(m=>/claude-sonnet|claude-opus/.test(m))||dflt[0];
  h(`<div class="hdr"><h2>Gateway Inference — Evaluation</h2>
       <span class="muted">mesmo prompt em até 3 modelos + LLM-as-a-judge</span></div>
     <div class="card">
       <label>Prompt</label><textarea id="ev-prompt" style="min-height:80px">Explique o que é o Amazon Bedrock AgentCore em 3 frases.</textarea>
       <div class="row" style="margin-top:8px">
         <div style="flex:1"><label>Modelo A</label><select id="ev-a">${_gwModelOpts(dflt[0])}</select></div>
         <div style="flex:1"><label>Modelo B</label><select id="ev-b">${_gwModelOpts(dflt[1])}</select></div>
         <div style="flex:1"><label>Modelo C (opcional)</label><select id="ev-c"><option value="">—</option>${_gwModelOpts(dflt[2])}</select></div>
       </div>
       <div class="row"><div style="flex:1"><label>Juiz (LLM-as-a-judge)</label><select id="ev-judge">${_gwModelOpts(judge)}</select></div>
         <div style="align-self:flex-end"><button class="btn" onclick="gwEvalRun()">Avaliar</button></div></div>
       <p class="muted">Dica: escolha um juiz que NÃO seja candidato (evita viés).</p>
     </div>
     <div id="ev-out"></div>`);
}
async function _gwAsk(model, question, system){
  const t0=performance.now();
  const d=await gwinfApi("/ask",{method:"POST",body:JSON.stringify({question,model,system_prompt:system||"",conv:"eval-"+Math.random().toString(36).slice(2)})});
  const ms=Math.round(performance.now()-t0); const r=d.result||{};
  return {model, answer:r.answer||"", tokens:(r.debug&&r.debug.tokens)||{}, ms};
}
async function gwEvalRun(){
  const prompt=(el("ev-prompt").value||"").trim(); if(!prompt) return;
  const cands=[el("ev-a").value, el("ev-b").value, el("ev-c").value].filter((v,i,a)=>v&&a.indexOf(v)===i);
  const judge=el("ev-judge").value;
  const labels="ABCDE".split("");
  const out=el("ev-out");
  // 1) Cada modelo streama a resposta AO VIVO no seu proprio card (juiz vem depois).
  out.innerHTML=`<div class="card"><h3>Respostas (streaming)</h3>
     <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px">
     ${cands.map((m,i)=>`<div class="card" style="margin:0">
        <div class="row" style="justify-content:space-between"><b>[${labels[i]}] ${esc(m.split("/").pop())}</b>
          <span id="ev-badge-${i}" class="muted">…</span></div>
        <div id="ev-live-${i}" class="msg bot" style="min-height:40px">…</div>
        <div id="ev-meta-${i}" class="muted" style="font-size:12px"></div>
      </div>`).join("")}
     </div></div>
     <div id="ev-verdict"></div>`;
  const runs=new Array(cands.length);
  const texts={};
  await Promise.all(cands.map((m,i)=>{
    texts[i]=""; const t0=performance.now();
    return gwStream({question:prompt,model:m,system_prompt:window._gwSys||"",conv:"eval-"+Math.random().toString(36).slice(2)},
        (t)=>{ texts[i]+=t; const e=el("ev-live-"+i); if(e) e.innerHTML=_oriMd(texts[i]); })
      .then(dbg=>{ const ms=Math.round(performance.now()-t0); const g=dbg.guardrail||{};
        if(g.blocked&&g.stage==="output"&&g.message){ texts[i]=g.message; }
        const e=el("ev-live-"+i); if(e){ e.innerHTML=_oriMd(texts[i]||"(sem resposta)"); if(g.blocked) e.classList.add("danger"); }
        const b=el("ev-badge-"+i); if(b) b.innerHTML=g.blocked?`<span class="danger">🛡️ bloqueado (${g.stage==="input"?"entrada":"saída"})</span>`:`🛡️ OK`;
        const tok=dbg.tokens||{}; const mt=el("ev-meta-"+i);
        if(mt) mt.textContent=`tokens ${tok.total||0} · ${ms} ms`;
        runs[i]={model:m, answer:texts[i], tokens:tok, ms, blocked:!!g.blocked};
      })
      .catch(e=>{ const el2=el("ev-live-"+i); if(el2) el2.innerHTML=`<span class="danger">${esc(e.message)}</span>`;
        runs[i]={model:m, answer:"", tokens:{}, ms:0, error:e.message}; });
  }));
  // 2) Juiz roda DEPOIS, sobre as respostas ja recebidas.
  const jout=el("ev-verdict");
  jout.innerHTML=`<div class="card muted">Consultando o juiz (${esc(judge.split("/").pop())})…</div>`;
  const jprompt="Voce e um juiz imparcial de respostas de LLMs. Prompt do usuario:\n\""+prompt+"\"\n\n"+
    runs.map((r,i)=>`[${labels[i]}] modelo=${r.model}\nResposta:\n${r.answer}`).join("\n\n---\n\n")+
    "\n\nAvalie CADA resposta de 0 a 10 em accuracy, completeness, relevance, clarity e calcule overall (media). "+
    "Responda SOMENTE com JSON valido, sem markdown: "+
    '{"scores":[{"label":"A","accuracy":n,"completeness":n,"relevance":n,"clarity":n,"overall":n}],"winner":"A","rationale":"1 frase"}';
  let verdict={};
  try{
    const jr=await _gwAsk(judge, jprompt, "Responda apenas com JSON valido.");
    const mtxt=(jr.answer||"").replace(/```json|```/g,"").trim();
    verdict=JSON.parse(mtxt.slice(mtxt.indexOf("{"), mtxt.lastIndexOf("}")+1));
  }catch(e){ verdict={error:String(e)}; }
  const smap={}; (verdict.scores||[]).forEach(s=>smap[s.label]=s);
  const rows=runs.map((r,i)=>{ const L=labels[i]; const s=smap[L]||{}; const tps=r.tokens.output&&r.ms?((r.tokens.output/(r.ms/1000)).toFixed(1)):"—";
    const win=verdict.winner===L; const gr=r.blocked?'<span class="danger">bloqueado</span>':'OK';
    return `<tr><td><b>${L}</b>${win?' 🏆':''}</td><td>${esc(r.model.split("/").pop())}</td>
      <td>${s.overall!=null?'<b>'+s.overall+'</b>':'—'}</td>
      <td>${gr}</td>
      <td>${r.tokens.total||0}</td><td>${r.ms} ms</td><td>${tps} tok/s</td></tr>`;}).join("");
  try{
    const saveRows=runs.map((r,i)=>{const L=labels[i];const s=smap[L]||{};
      return {model:r.model, overall:(s.overall!=null?s.overall:null), win:verdict.winner===L};});
    const all=_gwEvalRuns(); all.push({ts:Date.now(), prompt, winner:verdict.winner||"", rows:saveRows});
    localStorage.setItem("gwEvalRuns", JSON.stringify(all.slice(-50)));
  }catch(e){}
  jout.innerHTML=`<div class="card"><h3>Veredito do juiz</h3>
     <table><thead><tr><th>#</th><th>Modelo</th><th>Nota (juiz)</th><th>Guardrail</th><th>Tokens</th><th>Latência</th><th>Vazão</th></tr></thead>
     <tbody>${rows}</tbody></table>
     <p style="margin-top:8px">Vencedor: <b>${esc(verdict.winner||"—")}</b>${verdict.rationale?` — ${esc(verdict.rationale)}`:""}</p>
     ${verdict.error?`<p class="danger">Juiz nao retornou JSON valido: ${esc(verdict.error)}</p>`:""}
     <p class="muted">Juiz: ${esc(judge.split("/").pop())}. Notas 0–10 por accuracy/completeness/relevance/clarity (overall = média). As respostas aparecem acima, em streaming.</p></div>`;
}
async function viewGwMantle(){
  const hrs = window._gwMetHours || 24;
  h(`<div class="hdr"><h2>Gateway Inference — Mantle-config</h2>
       <span class="muted">observability do Gateway (CloudWatch AWS/BedrockMantle)</span></div>
     <div class="card">
       <div class="row"><label>Janela:</label>
         <select id="gw-hrs" onchange="window._gwMetHours=+this.value;viewGwMantle()">
           ${[["1","1h"],["24","24h"],["168","7 dias"]].map(([v,t])=>`<option value="${v}"${+v===hrs?" selected":""}>${t}</option>`).join("")}</select></div>
       <div id="gw-met" class="muted">Carregando métricas…</div>
     </div>`);
  try{
    const m = await gwinfApi("/mantle/metrics?hours="+hrs);
    const t = m.totals||{};
    const rows = (m.models||[]).map(r=>`<tr><td>${esc(r.model.split("/").pop())}</td>
      <td>${r.inferences}</td><td>${r.inputTokens}</td><td>${r.outputTokens}</td>
      <td>${r.inputTokens+r.outputTokens}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">sem dados na janela</td></tr>`;
    el("gw-met").classList.remove("muted");
    el("gw-met").innerHTML = `<div class="kpis" style="margin-bottom:10px">
        <div class="kpi"><b>${t.inferences||0}</b>inferências</div>
        <div class="kpi"><b>${t.inputTokens||0}</b>tokens entrada</div>
        <div class="kpi"><b>${t.outputTokens||0}</b>tokens saída</div></div>
      <table><thead><tr><th>Modelo</th><th>Inferências</th><th>Tokens in</th><th>Tokens out</th><th>Total</th></tr></thead>
      <tbody>${rows}</tbody></table>
      <p class="muted">Uso agregado por modelo no Gateway (namespace ${esc(m.namespace)}). Inclui todo o tráfego do Gateway na conta.</p>`;
  }catch(e){ el("gw-met").innerHTML=`<span class="danger">${esc(e.message)}</span>`; }
}
function _gwEvalRuns(){ try{ return JSON.parse(localStorage.getItem("gwEvalRuns")||"[]"); }catch(e){ return []; } }
function viewGwHistory(){
  const runs=_gwEvalRuns();
  const bench={};
  runs.forEach(run=>(run.rows||[]).forEach(r=>{ const b=bench[r.model]=bench[r.model]||{model:r.model,runs:0,sum:0,wins:0};
    b.runs++; if(r.overall!=null) b.sum+=r.overall; if(r.win) b.wins++; }));
  const brows=Object.values(bench).sort((a,b)=>(b.sum/b.runs)-(a.sum/a.runs)).map(b=>
    `<tr><td>${esc(b.model.split("/").pop())}</td><td>${(b.sum/b.runs).toFixed(1)}</td><td>${b.wins}</td><td>${b.runs}</td></tr>`).join("")
    || `<tr><td colspan="4" class="muted">sem avaliações ainda — rode uma na aba Evaluation</td></tr>`;
  const hist=runs.slice(-15).reverse().map(run=>`<tr><td>${esc(new Date(run.ts).toLocaleString())}</td>
    <td style="max-width:320px">${esc((run.prompt||"").slice(0,80))}</td><td>${esc((run.winner||"—"))}</td>
    <td>${(run.rows||[]).map(r=>esc(r.model.split("/").pop())).join(", ")}</td></tr>`).join("")
    || `<tr><td colspan="4" class="muted">—</td></tr>`;
  h(`<div class="hdr"><h2>Gateway Inference — History</h2>
       <span class="muted">avaliações salvas neste navegador · benchmark por modelo</span></div>
     <div class="card"><h3>Benchmark por modelo</h3>
       <table><thead><tr><th>Modelo</th><th>Nota média (juiz)</th><th>Vitórias</th><th>Avaliações</th></tr></thead><tbody>${brows}</tbody></table>
       <div style="margin-top:8px"><button class="btn sec" onclick="localStorage.removeItem('gwEvalRuns');viewGwHistory()">Limpar histórico</button></div></div>
     <div class="card"><h3>Últimas avaliações</h3>
       <table><thead><tr><th>Quando</th><th>Prompt</th><th>Vencedor</th><th>Modelos</th></tr></thead><tbody>${hist}</tbody></table></div>`);
}
async function viewGwKeys(){
  h(`<div class="hdr"><h2>Gateway Inference — Keys (BYOK)</h2>
       <span class="muted">sua chave OpenAI/Gemini via AgentCore Identity → mesmo Gateway</span></div>
     <div class="card">
       <p class="muted">Traga sua própria chave: ela é validada, guardada no <b>AgentCore Identity</b>
       (nunca no navegador), e um <b>target</b> do Gateway é criado para ela. Os modelos que
       funcionarem passam a aparecer no seletor de Inference/Evaluation (ex.: <code>gemini/*</code>).</p>
       <div class="row" style="gap:8px;align-items:flex-end;flex-wrap:wrap">
         <div><label>Provider</label><select id="k-prov"><option value="gemini">gemini</option><option value="openai">openai</option></select></div>
         <div style="flex:1;min-width:280px"><label>API key</label>
           <input id="k-key" type="password" placeholder="cole a chave do provider" autocomplete="off"></div>
         <button class="btn" onclick="gwKeySave()">Validar e salvar</button>
       </div>
       <div id="k-msg" class="muted" style="margin-top:8px"></div>
     </div>
     <div id="k-list" class="card muted">Carregando chaves…</div>`);
  gwKeysRefresh();
}
async function gwKeysRefresh(){
  const box=el("k-list");
  try{
    const d=await gwinfApi("/keys");
    const rows=(d.providers||[]).map(p=>{
      const st=p.configured?`<span style="color:green">configurado</span>`:`<span class="muted">não configurado</span>`;
      const models=(p.models||[]).map(m=>`<code>${esc(m.split("/").pop())}</code>`).join(" ")||"—";
      const del=p.configured?`<button class="btn sec" onclick="gwKeyDelete('${esc(p.provider)}')">Remover</button>`:"";
      return `<tr><td><b>${esc(p.provider)}</b></td><td>${st}</td>
        <td>${p.updatedAt?esc(new Date(p.updatedAt).toLocaleString()):"—"}</td>
        <td style="max-width:420px">${models}</td><td>${del}</td></tr>`;}).join("");
    box.classList.remove("muted");
    box.innerHTML=`<h3>Chaves / providers</h3>
      <table><thead><tr><th>Provider</th><th>Status</th><th>Atualizado</th><th>Modelos testados</th><th></th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  }catch(e){ box.classList.remove("muted"); box.innerHTML=`<div class="danger">${esc(e.message)}</div>`; }
}
async function gwKeySave(){
  const provider=el("k-prov").value, apiKey=(el("k-key").value||"").trim();
  const msg=el("k-msg");
  if(!apiKey){ msg.innerHTML=`<span class="danger">Informe a chave.</span>`; return; }
  msg.classList.remove("muted"); msg.innerHTML=`Validando e testando modelos… (pode levar alguns segundos)`;
  try{
    const d=await gwinfApi("/keys",{method:"POST",body:JSON.stringify({provider,apiKey})});
    const okN=(d.models||[]).length; const failed=(d.tested||[]).filter(t=>!t.ok).length;
    msg.innerHTML=`<span style="color:green">OK</span> — ${okN} modelo(s) disponíveis${failed?`, ${failed} falharam`:""}. `
      + `Status do target: <b>${esc(d.targetStatus||"?")}</b>. Já aparecem no seletor.`;
    el("k-key").value=""; window._gwModels=null;   // invalida cache do picker
    gwKeysRefresh();
  }catch(e){ msg.innerHTML=`<span class="danger">${esc(e.message)}</span>`; }
}
async function gwKeyDelete(provider){
  if(!confirm(`Remover a chave e o target de "${provider}"? Os modelos desse provider deixam de aparecer.`)) return;
  try{ await gwinfApi("/keys/"+encodeURIComponent(provider),{method:"DELETE"}); window._gwModels=null; gwKeysRefresh(); }
  catch(e){ alert(e.message); }
}

const ROUTES = {
  "ex-corrige":()=>viewCorrecao("exam"), "ex-criar":viewCriar, "ex-hist":()=>viewHistorico("exam"),
  "red-rubrica":viewRubricas, "red-corrige":()=>viewCorrecao("essay"), "red-hist":()=>viewHistorico("essay"),
  "cartao-load":viewCartaoLoad, "cartao-read":viewCartaoRead, "cartao-tpl":viewCartaoTemplates,
  "cartao-hist":viewCartaoHist, "cartao":viewCartaoLoad,
  "modelos":viewModelos, "analytics":viewAnalytics, "evaluation":viewEvaluation,
  "po-criar":viewOnlineCreate, "po-teste":viewOnlineTest, "po-hist":viewOnlineHist,
  "ent-entrevista":viewEntEntrevista, "ent-vagas":viewEntVagas,
  "ent-avatar":viewEntAvatar, "ent-relatorio":viewEntRelatorio,
  "atend-chat":viewAtendimentoChat, "atend-templates":viewAtendTemplates, "atend-campanhas":viewAtendCampanhas,
  "ori-alunos":viewOrientadorAlunos, "ori-cursos":viewOrientadorCursos, "ori-carreiras":viewOrientadorCarreiras,
  "ori-coord":viewCoordTransfers,
  "ori-grafo":viewOrientadorGrafo,
  "ori-chat":viewOrientadorChat, "ori-trilha":viewOrientadorTrilha,
  "ori-insights":viewOrientadorInsights, "ori-curriculo":viewOrientadorCurriculo, "ori-competencias":viewOrientadorCompetencias,
  "lms-busca":viewLmsBusca, "lms-catalogo":viewLmsCatalogo, "lms-qualidade":viewLmsQualidade,
  "octx-chat":viewOrientadorContextChat, "octx-risco":viewOrientadorContextRisco,
  "octx-desempenho":viewOrientadorContextDesempenho,
  "octx-alunos":viewOrientadorContextAlunos, "octx-cursos":viewOrientadorContextCursos,
  "octx-trilha":viewOrientadorContextTrilha, "octx-grafo":viewOrientadorContextGrafo,
  "octx-insights":viewOrientadorContextInsights, "octx-curriculo":viewOrientadorContextCurriculo,
  "octx-competencias":viewOrientadorContextCompetencias, "octx-coord":viewOrientadorContextCoord,
  "gwinf-inference":viewGwInference, "gwinf-eval":viewGwEval, "gwinf-history":viewGwHistory,
  "gwinf-mantle":viewGwMantle, "gwinf-keys":viewGwKeys, "gwinf-sysprompt":viewGwSysprompt,
};
function route(){ const k=location.hash.slice(1)||"ex-corrige"; renderNav(ROUTES[k]?k:"ex-corrige"); (ROUTES[k]||ROUTES["ex-corrige"])(); toggleSide(false); }
window.addEventListener("hashchange", route);

(async function(){
  const p=new URLSearchParams(location.search);
  if(p.get("code")){ try{ await exchangeCode(p.get("code")); }catch(e){ document.body.innerHTML="<p style='padding:24px'>Erro de login. <a href='/'>Tentar novamente</a></p>"; return; } }
  if(!ID_TOKEN){ return login(); }
  route();
})();
