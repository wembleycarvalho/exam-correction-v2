// Submenus do Entrevistador: Vagas, Avatar, Relatório.
// Vagas (DynamoDB via API) e Relatório usam a API do Fargate. Avatar persiste em localStorage.
(function () {
  const API_BASE = "/entrevistador";
  const ASSET_BASE = "/entrevistador-assets";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ---------------- Vagas (DynamoDB via API) ----------------
  window.initVagas = function () {
    const titleEl = $("v-title"), descEl = $("v-desc"), genBtn = $("v-generate"),
          genStatus = $("v-genstatus"), saveBtn = $("v-save"), cancelBtn = $("v-cancel"), listEl = $("v-list");
    let editingId = null;   // null = criando; id = editando vaga existente
    let current = [];       // cache das vagas para lookup no clique

    function resetForm() {
      editingId = null;
      titleEl.value = ""; descEl.value = "";
      saveBtn.textContent = "Salvar vaga";
      if (cancelBtn) cancelBtn.style.display = "none";
    }

    function loadForEdit(v) {
      editingId = v.id;
      titleEl.value = v.title || "";
      descEl.value = v.description || "";
      saveBtn.textContent = "Atualizar vaga";
      if (cancelBtn) cancelBtn.style.display = "";
      titleEl.focus();
      titleEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    async function render() {
      listEl.innerHTML = '<div class="muted" style="padding:0.6rem">Carregando…</div>';
      try {
        const d = await (await fetch(API_BASE + "/api/vagas")).json();
        current = d.vagas || [];
        listEl.innerHTML = current.length ? current.map((v) =>
          `<div class="report-item" data-id="${esc(v.id)}"><div class="report-info">
             <span class="report-date">${esc(v.title)}</span>
             <span class="report-job">${esc((v.description || "").slice(0, 130))}</span>
           </div><span class="report-open" data-del="${esc(v.id)}">🗑 excluir</span></div>`).join("")
          : '<div class="muted" style="padding:0.6rem">Nenhuma vaga cadastrada.</div>';
        // Clicar na vaga (fora do botão excluir) carrega no formulário para edição.
        listEl.querySelectorAll(".report-item").forEach((row) =>
          row.addEventListener("click", (e) => {
            if (e.target.closest("[data-del]")) return;
            const v = current.find((x) => x.id === row.dataset.id);
            if (v) loadForEdit(v);
          }));
        listEl.querySelectorAll("[data-del]").forEach((b) =>
          b.addEventListener("click", async (e) => {
            e.stopPropagation();
            if (!confirm("Excluir esta vaga?")) return;
            await fetch(API_BASE + "/api/vagas/" + encodeURIComponent(b.dataset.del), { method: "DELETE" });
            if (editingId === b.dataset.del) resetForm();
            render();
          }));
      } catch (e) { listEl.innerHTML = '<div class="danger" style="padding:0.6rem">Erro ao carregar vagas.</div>'; }
    }

    genBtn.addEventListener("click", async () => {
      const input = descEl.value.trim();
      if (!input) { alert("Digite ao menos o cargo ou uma breve descrição."); return; }
      genBtn.disabled = true; genStatus.textContent = "⏳ Gerando descrição...";
      try {
        const r = await fetch(API_BASE + "/api/generate-job", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ input }) });
        const d = await r.json();
        if (d.description) { descEl.value = d.description; genStatus.textContent = "✅ Descrição gerada"; setTimeout(() => genStatus.textContent = "", 3000); }
        else genStatus.textContent = "❌ Erro ao gerar";
      } catch (e) { genStatus.textContent = "❌ Erro de conexão"; }
      finally { genBtn.disabled = false; }
    });

    saveBtn.addEventListener("click", async () => {
      const title = (titleEl.value || "").trim(), description = (descEl.value || "").trim();
      if (!title || !description) { alert("Preencha título e descrição."); return; }
      saveBtn.disabled = true;
      const editing = editingId;
      try {
        const url = editing
          ? API_BASE + "/api/vagas/" + encodeURIComponent(editing)
          : API_BASE + "/api/vagas";
        await fetch(url, {
          method: editing ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, description }) });
        resetForm();
        genStatus.textContent = editing ? "✅ Vaga atualizada" : "✅ Vaga salva — já aparece em Entrevista";
        setTimeout(() => genStatus.textContent = "", 3500);
        render();
      } catch (e) { genStatus.textContent = "❌ Erro ao salvar"; }
      finally { saveBtn.disabled = false; }
    });

    if (cancelBtn) cancelBtn.addEventListener("click", resetForm);

    render();
  };

  // ---------------- Histórico de entrevistas (API Fargate + DynamoDB) ----------------
  function mdToHtml(s) {
    return (s || "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/^#{2,3} (.+)$/gm, "<h3>$1</h3>")
      .replace(/^- (.+)$/gm, "<li>$1</li>")
      .replace(/\n/g, "<br>");
  }

  function reportScoreMeta(score) {
    if (typeof score !== "number" || score < 0) return { color: "#888", label: "N/A", val: 0 };
    if (score >= 70) return { color: "#4caf50", label: "Alta aderência", val: score };
    if (score >= 40) return { color: "#ffc107", label: "Aderência parcial", val: score };
    return { color: "#f44336", label: "Baixa aderência", val: score };
  }

  function reportDetailHtml(rep) {
    const m = reportScoreMeta(rep.score);
    const tu = rep.tokenUsage || {};
    const total = tu.total || 0;
    let cost = "";
    if (total > 0) {
      const c = ((tu.input_speech || 0) + (tu.input_text || 0)) / 1000 * 0.0034 +
                ((tu.output_speech || 0) + (tu.output_text || 0)) / 1000 * 0.0136;
      const n = (x) => (x || 0).toLocaleString("pt-BR");
      cost = `<div class="rep-tokens"><div class="rep-tokens-title">💰 Consumo de Tokens & Custo</div>
        <table>
          <tr><td>🎤 Input Speech</td><td>${n(tu.input_speech)}</td></tr>
          <tr><td>📝 Input Text</td><td>${n(tu.input_text)}</td></tr>
          <tr><td>🔊 Output Speech</td><td>${n(tu.output_speech)}</td></tr>
          <tr><td>💬 Output Text</td><td>${n(tu.output_text)}</td></tr>
          <tr><td>📊 Total</td><td>${n(total)}</td></tr>
          <tr class="rep-cost"><td>💵 Custo estimado</td><td>US$ ${c.toFixed(4)}</td></tr>
        </table></div>`;
    }
    const tr = (rep.transcript || []).map((e) => {
      const role = e.role || "", text = esc(e.text || "");
      if (role === "Candidato") return `<div class="msg-user">🧑 ${role}: ${text}</div>`;
      if (role === "Entrevistador") return `<div class="msg-assistant">🎙️ ${role}: ${text}</div>`;
      return `<div class="msg-system">ℹ️ ${role}: ${text}</div>`;
    }).join("");
    const name = rep.candidateName && rep.candidateName !== "Não informado" ? rep.candidateName : "Candidato não identificado";
    const vaga = esc(rep.jobDescription || "");
    return `<div class="rep-detail">
      <div class="rep-head">
        <div class="rep-head-info">
          <div class="rep-name">${esc(name)}</div>
          <div class="rep-sub">${esc(rep.timestampDisplay || "")}</div>
          ${vaga ? `<div class="rep-vaga collapsed" data-vaga title="Clique para expandir/recolher">
            <div class="rep-vaga-label">Vaga <span class="rep-vaga-caret">▾</span></div>
            <div class="rep-vaga-text">${vaga}</div>
          </div>` : ""}
        </div>
        <button class="sec-btn rep-back" type="button">← Voltar</button>
      </div>
      <div class="rep-score" style="border-left:4px solid ${m.color}">
        <div class="rep-score-val" style="color:${m.color}">${m.val}%</div>
        <div class="rep-score-label">${m.label}</div>
      </div>
      <div class="rep-body">${mdToHtml(rep.reportBody || "")}</div>
      <div class="rep-section">💬 Transcrição</div>
      <div class="rep-transcript">${tr || '<div class="muted">Sem transcrição.</div>'}</div>
      ${cost}
      <div class="rep-foot"><button class="sec-btn rep-back" type="button">← Voltar ao histórico</button></div>
    </div>`;
  }

  window.initRelatorio = function () {
    const panel = $("reports-panel");
    if (!panel) return;

    async function showDetail(id) {
      panel.innerHTML = '<div class="muted" style="padding:0.6rem">Carregando relatório…</div>';
      try {
        const rep = await (await fetch(API_BASE + "/api/reports/" + encodeURIComponent(id))).json();
        if (rep.error) { panel.innerHTML = '<div class="danger" style="padding:0.6rem">Relatório não encontrado.</div>'; return; }
        panel.innerHTML = reportDetailHtml(rep);
        panel.querySelectorAll(".rep-back").forEach((b) => b.addEventListener("click", showList));
        const vagaEl = panel.querySelector("[data-vaga]");
        if (vagaEl) vagaEl.addEventListener("click", () => vagaEl.classList.toggle("collapsed"));
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (e) { panel.innerHTML = '<div class="danger" style="padding:0.6rem">Erro ao carregar o relatório.</div>'; }
    }

    async function showList() {
      panel.innerHTML = '<div id="r-list"><div class="muted" style="padding:0.6rem">Carregando…</div></div>';
      const listEl = $("r-list");
      try {
        const data = await (await fetch(API_BASE + "/api/reports")).json();
        if (!data.reports || !data.reports.length) {
          listEl.innerHTML = '<div class="muted" style="padding:0.6rem">Nenhuma entrevista registrada ainda.</div>'; return;
        }
        listEl.innerHTML = "";
        data.reports.forEach((r) => {
          const ts = r.timestamp;
          const d = ts && ts.length >= 13 ? `${ts.slice(6, 8)}/${ts.slice(4, 6)}/${ts.slice(0, 4)} ${ts.slice(9, 11)}:${ts.slice(11, 13)}` : "—";
          const score = (typeof r.score === "number" && r.score >= 0) ? `${r.score}%` : "—";
          const name = r.candidateName && r.candidateName !== "Não informado" ? r.candidateName : "Candidato não identificado";
          const it = document.createElement("div"); it.className = "report-item";
          it.innerHTML = `<div class="report-info">
              <span class="report-date">${esc(name)}</span>
              <span class="report-job">📋 ${d} · Aderência ${score} · ${esc(r.job_description || "—")}</span>
            </div>
            <div class="report-actions">
              <span class="report-open">Abrir →</span>
              <button class="rep-del" data-del="${r.id}" title="Excluir entrevista">🗑</button>
            </div>`;
          it.addEventListener("click", (e) => { if (e.target.closest("[data-del]")) return; showDetail(r.id); });
          const delBtn = it.querySelector("[data-del]");
          if (delBtn) delBtn.addEventListener("click", async (e) => {
            e.stopPropagation();
            if (!confirm("Excluir esta entrevista do histórico?")) return;
            await fetch(API_BASE + "/api/reports/" + encodeURIComponent(r.id), { method: "DELETE" });
            showList();
          });
          listEl.appendChild(it);
        });
      } catch (e) { listEl.innerHTML = '<div class="danger" style="padding:0.6rem">Erro ao carregar histórico.</div>'; }
    }

    showList();
  };

  // ---------------- Avatar (galeria + upload + geração + calibração via API) ----------------
  window.initAvatar = function () {
    const gallery = $("av-gallery"); if (!gallery) return;
    const editor = $("av-editor"), canvas = $("cal-canvas"), ctx = canvas ? canvas.getContext("2d") : null;
    const fileInput = $("av-file"), genPrompt = $("av-genprompt"), genBtn = $("av-generate"),
          avStatus = $("av-status"), editName = $("av-editing-name");

    let avatars = [], editingId = null, photoLoaded = false;
    const img = new Image();
    img.onload = () => { photoLoaded = true; };

    const ids = ["le-x","le-y","le-w","re-x","re-y","re-w","m-x","m-y","m-w","m-open","m-split"];
    const S = {}; ids.forEach((id) => { S[id] = { el: $(id), v: $(id + "-v") }; });
    ids.forEach((id) => { if (S[id].el) S[id].el.addEventListener("input", () => { if (S[id].v) S[id].v.textContent = S[id].el.value; }); });
    const v = (id) => parseInt(S[id].el.value);

    function setSlider(id, val) { if (S[id] && S[id].el && val != null) { S[id].el.value = val; if (S[id].v) S[id].v.textContent = val; } }
    function loadCalibration(cal) {
      cal = cal || {}; const le = cal.leftEye || {}, re = cal.rightEye || {}, m = cal.mouth || {};
      setSlider("le-x", le.x); setSlider("le-y", le.y); setSlider("le-w", le.w);
      setSlider("re-x", re.x); setSlider("re-y", re.y); setSlider("re-w", re.w);
      setSlider("m-x", m.x); setSlider("m-y", m.y); setSlider("m-w", m.w);
      setSlider("m-open", cal.mouthOpenMax); setSlider("m-split", cal.mouthSplitH);
      ids.forEach((id) => { if (S[id].v) S[id].v.textContent = S[id].el.value; });
    }
    function getFace() {
      return {
        leftEye:  { x: v("le-x"), y: v("le-y"), w: v("le-w"), h: Math.round(v("le-w") * 0.4) },
        rightEye: { x: v("re-x"), y: v("re-y"), w: v("re-w"), h: Math.round(v("re-w") * 0.4) },
        mouth:    { x: v("m-x"), y: v("m-y"), w: v("m-w"), h: Math.round(v("m-w") * 0.2) },
        mouthOpenMax: v("m-open"), mouthSplitH: v("m-split"),
      };
    }
    const chkTalk = $("cal-talk"), chkBlink = $("cal-blink");

    function openEditor(av) {
      editingId = av.id;
      if (editName) editName.textContent = av.name || "";
      if ($("av-name")) $("av-name").value = av.name || "";
      if ($("av-gender")) $("av-gender").value = (av.gender === "male") ? "male" : "female";
      photoLoaded = false;
      img.src = av.imageUrl + "?t=" + Date.now();
      loadCalibration(av.calibration);
      if (editor) editor.style.display = "";
      gallery.querySelectorAll(".av-card").forEach((c) => c.classList.toggle("selected", c.dataset.id === av.id));
    }

    async function loadGallery(selectId) {
      gallery.innerHTML = '<div class="muted" style="padding:0.4rem">Carregando…</div>';
      try {
        const data = await (await fetch(API_BASE + "/api/avatars")).json();
        avatars = data.avatars || [];
        if (!avatars.length) {
          gallery.innerHTML = '<div class="muted" style="padding:0.4rem">Nenhum avatar ainda. Envie ou gere um.</div>';
          if (editor) editor.style.display = "none"; return;
        }
        gallery.innerHTML = avatars.map((a) => `
          <div class="av-card${a.isDefault ? " is-default" : ""}" data-id="${a.id}">
            <img src="${a.imageUrl}" alt="${esc(a.name)}" loading="lazy" />
            ${a.isDefault ? '<div class="av-badge">★ padrão</div>' : ''}
            <div class="av-card-name">${esc(a.name)}</div>
            <div class="av-card-actions">
              ${a.isDefault ? '' : `<button class="av-mini" data-def="${a.id}" title="Definir como padrão">★ padrão</button>`}
              <button class="av-mini danger" data-del="${a.id}" title="Excluir">🗑</button>
            </div>
          </div>`).join("");
        gallery.querySelectorAll(".av-card").forEach((c) => c.addEventListener("click", (e) => {
          if (e.target.closest("[data-def]") || e.target.closest("[data-del]")) return;
          const a = avatars.find((x) => x.id === c.dataset.id); if (a) openEditor(a);
        }));
        gallery.querySelectorAll("[data-def]").forEach((b) => b.addEventListener("click", async (e) => {
          e.stopPropagation();
          await fetch(API_BASE + "/api/avatars/" + encodeURIComponent(b.dataset.def) + "/default", { method: "PUT" });
          loadGallery(editingId);
        }));
        gallery.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async (e) => {
          e.stopPropagation();
          if (!confirm("Excluir este avatar?")) return;
          await fetch(API_BASE + "/api/avatars/" + encodeURIComponent(b.dataset.del), { method: "DELETE" });
          if (editingId === b.dataset.del) { editingId = null; if (editor) editor.style.display = "none"; }
          loadGallery();
        }));
        const toOpen = avatars.find((a) => a.id === selectId) || avatars.find((a) => a.isDefault) || avatars[0];
        if (toOpen) openEditor(toOpen);
      } catch (e) { gallery.innerHTML = '<div class="danger" style="padding:0.4rem">Erro ao carregar avatares.</div>'; }
    }

    // Salvar calibração → PUT (por avatar)
    $("cal-save").addEventListener("click", async () => {
      if (!editingId) return;
      const st = $("cal-status"); st.textContent = "⏳ Salvando…";
      try {
        await fetch(API_BASE + "/api/avatars/" + encodeURIComponent(editingId), {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ calibration: getFace() }) });
        const a = avatars.find((x) => x.id === editingId); if (a) a.calibration = getFace();
        st.textContent = "✅ Calibração salva (aplicada nas próximas entrevistas)";
        setTimeout(() => st.textContent = "", 4000);
      } catch (e) { st.textContent = "❌ Erro ao salvar"; }
    });

    // Renomear avatar + definir sexo (nome e sexo do padrão viram nome/voz da entrevista)
    $("av-rename").addEventListener("click", async () => {
      if (!editingId) return;
      const name = ($("av-name").value || "").trim();
      const gender = ($("av-gender") && $("av-gender").value) || "female";
      if (!name) { return; }
      const st = $("av-rename-status"); st.textContent = "⏳";
      try {
        await fetch(API_BASE + "/api/avatars/" + encodeURIComponent(editingId), {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, gender }) });
        st.textContent = "✅ Salvo";
        setTimeout(() => st.textContent = "", 2500);
        loadGallery(editingId);
      } catch (e) { st.textContent = "❌ Erro"; }
    });

    // Upload de imagem
    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0]; if (!file) return;
      if (file.size > 6 * 1024 * 1024) { avStatus.textContent = "❌ Imagem muito grande (máx 6MB)"; return; }
      avStatus.textContent = "⏳ Enviando…";
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const name = (file.name || "Avatar").replace(/\.[^.]+$/, "");
          const r = await fetch(API_BASE + "/api/avatars", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, imageBase64: reader.result, contentType: file.type || "image/png" }) });
          const d = await r.json();
          if (d.error) { avStatus.textContent = "❌ " + d.error; return; }
          fileInput.value = ""; avStatus.textContent = "✅ Avatar enviado — ajuste a calibração";
          setTimeout(() => avStatus.textContent = "", 3500);
          loadGallery(d.id);
        } catch (e) { avStatus.textContent = "❌ Erro no upload"; }
      };
      reader.readAsDataURL(file);
    });

    // Gerar imagem (Stability, via API)
    genBtn.addEventListener("click", async () => {
      const prompt = (genPrompt.value || "").trim();
      const styleEl = $("av-style");
      const style = (styleEl && styleEl.value) || "desenho";
      genBtn.disabled = true; avStatus.textContent = "⏳ Gerando imagem (pode levar alguns segundos)…";
      try {
        const r = await fetch(API_BASE + "/api/avatars/generate", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: prompt ? prompt.slice(0, 40) : "Avatar gerado", prompt, style }) });
        const d = await r.json();
        if (d.error) { avStatus.textContent = "❌ " + d.error; return; }
        genPrompt.value = ""; avStatus.textContent = "✅ Avatar gerado — ajuste a calibração";
        setTimeout(() => avStatus.textContent = "", 4000);
        loadGallery(d.id);
      } catch (e) { avStatus.textContent = "❌ Erro na geração"; }
      finally { genBtn.disabled = false; }
    });

    // Pálpebra descendo (cortina) — replica a piscada da entrevista, para calibrar os olhos.
    function drawEyelid(eye, blink) {
      const eyeH = eye.h * 2;
      const lidW = eye.w * 2 + 8, lidH = eye.h * 2 + 4;
      const srcX = eye.x - lidW / 2, srcY = eye.y - lidH - eye.h * 0.3;
      const drawY = (eye.y - eye.h) - lidH + blink * eyeH;
      const nw = img.naturalWidth || 400, nh = img.naturalHeight || 400;
      ctx.save();
      ctx.beginPath(); ctx.ellipse(eye.x, eye.y, eye.w + 2, eye.h + 2, 0, 0, Math.PI * 2); ctx.clip();
      ctx.drawImage(img, (srcX / 400) * nw, (srcY / 400) * nh, (lidW / 400) * nw, (lidH / 400) * nh,
                    eye.x - lidW / 2, drawY, lidW, lidH);
      ctx.restore();
    }

    // Loop de preview da calibração
    function renderLoop() {
      if (!document.body.contains(canvas)) return; // saiu da tela → encerra
      requestAnimationFrame(renderLoop);
      if (!photoLoaded || !ctx || (editor && editor.style.display === "none")) return;
      const face = getFace(); const t = Date.now();
      let mouthOpen = 0;
      if (chkTalk && chkTalk.checked) { mouthOpen = 0.3 + Math.sin(t / 120) * 0.3 + Math.sin(t / 80) * 0.2; mouthOpen = Math.max(0, Math.min(1, mouthOpen)); }
      let blink = 0;
      if (chkBlink && chkBlink.checked) { const c = t % 3500; if (c > 3200) { const p = (c - 3200) / 300; blink = p < 0.5 ? p * 2 : 2 - p * 2; } }

      ctx.drawImage(img, 0, 0, 400, 400);
      // piscada (cortina de pálpebra) — feedback visual ao alinhar os olhos
      if (blink > 0.02) { drawEyelid(face.leftEye, blink); drawEyelid(face.rightEye, blink); }
      ctx.globalAlpha = 0.4;
      for (const eye of [face.leftEye, face.rightEye]) { ctx.strokeStyle = "#6ec6ff"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.ellipse(eye.x, eye.y, eye.w, eye.h, 0, 0, Math.PI * 2); ctx.stroke(); }
      ctx.strokeStyle = "#f44"; ctx.beginPath(); ctx.ellipse(face.mouth.x, face.mouth.y, face.mouth.w, face.mouth.h + 4, 0, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = 1;

      if (mouthOpen > 0.03) {
        const m = face.mouth, gap = mouthOpen * face.mouthOpenMax, halfH = face.mouthSplitH;
        ctx.fillStyle = "#1A0808"; ctx.beginPath(); ctx.ellipse(m.x, m.y, m.w * 0.55, gap * 0.5 + 0.5, 0, 0, Math.PI * 2); ctx.fill();
        if (gap > 1.5) { ctx.fillStyle = "rgba(248,244,238,0.5)"; ctx.beginPath(); ctx.ellipse(m.x, m.y - gap * 0.15, m.w * 0.38, Math.min(2.5, gap * 0.25), 0, 0, Math.PI * 2); ctx.fill(); }
        const sx = m.x - m.w - 5, sw = m.w * 2 + 10;
        ctx.drawImage(img, (sx/400)*img.naturalWidth, ((m.y-halfH)/400)*img.naturalHeight, (sw/400)*img.naturalWidth, (halfH/400)*img.naturalHeight, sx, m.y-halfH-gap*0.4, sw, halfH);
        ctx.drawImage(img, (sx/400)*img.naturalWidth, (m.y/400)*img.naturalHeight, (sw/400)*img.naturalWidth, ((halfH+4)/400)*img.naturalHeight, sx, m.y+gap*0.4, sw, halfH+4);
      }
    }
    renderLoop();

    loadGallery();
  };
})();
