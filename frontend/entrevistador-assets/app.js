// Integração nativa no portal: tudo roda dentro de initInterviewer(), chamado pelo capítulo
// a cada render (o markup é re-injetado). Estáticos vêm do S3; WebSocket/API do Fargate.
window.initInterviewer = function () {
  const setupEl = document.getElementById("setup");
const interviewEl = document.getElementById("interview");
const startBtn = document.getElementById("start-btn");
const jobDescEl = document.getElementById("job-desc");
const jobCardsEl = document.getElementById("job-cards");
const generateBtn = document.getElementById("generate-btn");
const generateStatus = document.getElementById("generate-status");
const currentJobTag = document.getElementById("current-job-tag");
const micBtn = document.getElementById("mic-btn");
const stopIntBtn = document.getElementById("stop-interview");
const statusEl = document.getElementById("status");
const transcriptEl = document.getElementById("transcript");
const reportPanel = document.getElementById("report-panel");
const reportContent = document.getElementById("report-content");
const newIntBtn = document.getElementById("new-interview-btn");

// Avatar is managed by avatar.js
let avatarActive = false;

const ASSET_BASE = "/entrevistador-assets"; // estáticos (worklet, foto de fallback) no S3
const API_BASE = "/entrevistador";          // WebSocket + API no Fargate (via CloudFront)

const INPUT_SAMPLE_RATE = 16000;
const OUTPUT_SAMPLE_RATE = 24000;
const SEND_INTERVAL_MS = 32;

let ws = null;
let audioCtx = null;
let micStream = null;
let workletNode = null;
let isActive = false;
let isMicOn = false;
let currentRole = "";
let isSpeculative = false;
let jobDescription = "";
let selectedJobTitle = "";
let selectedJobDescription = "";
let jobsData = [];
let isEnding = false;
let hadFirstAudio = false;

// ---- Load jobs from JSON ----

async function loadJobs() {
  try {
    const res = await fetch(API_BASE + "/api/vagas");  // vagas da tabela (DynamoDB)
    const d = await res.json();
    jobsData = (d.vagas || []).map((v) => ({ id: v.id, title: v.title, description: v.description }));
    renderJobCards();
  } catch (e) {
    console.error("Failed to load vagas:", e);
  }
}

function renderJobCards() {
  jobCardsEl.innerHTML = "";
  jobsData.forEach((job) => {
    const card = document.createElement("div");
    card.className = "job-card";
    card.dataset.id = job.id;
    card.innerHTML = `<span class="card-title">${job.title}</span>`;
    card.addEventListener("click", () => selectJob(job, card));
    jobCardsEl.appendChild(card);
  });
}

function selectJob(job, card) {
  // Deselect all
  document.querySelectorAll(".job-card").forEach((c) => c.classList.remove("selected"));
  // Select this one
  card.classList.add("selected");
  selectedJobDescription = job.description;
  selectedJobTitle = job.title;
}

loadJobs();

// ---- Helpers ----

function setStatus(text) { statusEl.textContent = text; }

function addMessage(role, text) {
  const div = document.createElement("div");
  if (role === "USER") { div.className = "msg-user"; }
  else if (role === "error") { div.className = "msg-error"; }
  else if (role === "system") { div.className = "msg-system"; }
  else { div.className = "msg-assistant"; }
  const prefix = role === "USER" ? "🧑 Candidato" : role === "error" ? "⚠️" : role === "system" ? "ℹ️" : "🎙️ Entrevistador";
  div.textContent = `${prefix}: ${text}`;
  transcriptEl.appendChild(div);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64ToInt16Array(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Int16Array(bytes.buffer);
}

// ---- Downsampling ----

function downsample(buffer, fromRate, toRate) {
  if (fromRate === toRate) return buffer;
  const ratio = fromRate / toRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Int16Array(newLength);
  for (let i = 0; i < newLength; i++) {
    const idx = Math.round(i * ratio);
    result[i] = buffer[Math.min(idx, buffer.length - 1)];
  }
  return result;
}

// ---- Audio Capture ----

let pendingChunks = [];
let sendTimer = null;
let sessionReady = false; // true after session_started received

// 512 samples of silence at 16kHz = 32ms
const SILENCE_CHUNK = new Int16Array(512);

function startSendTimer() {
  sendTimer = setInterval(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN || !sessionReady) return;

    if (pendingChunks.length > 0) {
      let totalLen = 0;
      for (const c of pendingChunks) totalLen += c.length;
      const merged = new Int16Array(totalLen);
      let offset = 0;
      for (const c of pendingChunks) { merged.set(c, offset); offset += c.length; }
      pendingChunks = [];
      ws.send(JSON.stringify({ type: "audio", content: arrayBufferToBase64(merged.buffer) }));
    } else {
      // Send silence to keep the connection alive (Nova Sonic times out after 55s without audio)
      ws.send(JSON.stringify({ type: "audio", content: arrayBufferToBase64(SILENCE_CHUNK.buffer) }));
    }
  }, SEND_INTERVAL_MS);
}

async function startCapture() {
  audioCtx = new AudioContext({ sampleRate: 48000 });
  micStream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, sampleRate: { ideal: 16000 }, echoCancellation: true, noiseSuppression: true },
  });
  const source = audioCtx.createMediaStreamSource(micStream);
  await audioCtx.audioWorklet.addModule(ASSET_BASE + "/audio-processor.js");
  workletNode = new AudioWorkletNode(audioCtx, "capture-processor");
  workletNode.port.onmessage = (e) => {
    if (!isMicOn) return;
    const int16 = new Int16Array(e.data);
    pendingChunks.push(downsample(int16, audioCtx.sampleRate, INPUT_SAMPLE_RATE));
  };
  source.connect(workletNode);
  workletNode.connect(audioCtx.destination);
}

function stopCapture() {
  if (sendTimer) { clearInterval(sendTimer); sendTimer = null; }
  pendingChunks = [];
  if (workletNode) { workletNode.disconnect(); workletNode = null; }
  if (micStream) { micStream.getTracks().forEach((t) => t.stop()); micStream = null; }
  if (audioCtx) { audioCtx.close(); audioCtx = null; }
}

// ---- Audio Playback ----

function initPlayback() {
  playbackCtx = new AudioContext({ sampleRate: OUTPUT_SAMPLE_RATE });
  playbackQueue = [];
  isPlaying = false;
}

function enqueueAudio(int16Array) {
  playbackQueue.push(int16Array);
  if (!isPlaying) drainPlaybackQueue();
}

function drainPlaybackQueue() {
  if (playbackQueue.length === 0 || !playbackCtx) {
    isPlaying = false;
    showAvatarListening();
    return;
  }
  isPlaying = true;
  const chunk = playbackQueue.shift();
  const float32 = new Float32Array(chunk.length);
  let rms = 0;
  for (let i = 0; i < chunk.length; i++) {
    float32[i] = chunk[i] / 32768;
    rms += float32[i] * float32[i];
  }
  rms = Math.sqrt(rms / chunk.length);
  setAvatarMouthFromAudio(Math.min(1, rms * 8));
  const buffer = playbackCtx.createBuffer(1, float32.length, OUTPUT_SAMPLE_RATE);
  buffer.getChannelData(0).set(float32);
  const src = playbackCtx.createBufferSource();
  src.buffer = buffer;
  src.connect(playbackCtx.destination);
  src.onended = () => drainPlaybackQueue();
  src.start();
}

function stopPlayback() {
  playbackQueue = []; isPlaying = false;
  if (playbackCtx) { playbackCtx.close(); playbackCtx = null; }
}

function clearPlaybackQueue() {
  playbackQueue = [];
  // Stop any currently playing source by closing and reinitializing
  if (playbackCtx) {
    playbackCtx.close();
    playbackCtx = new AudioContext({ sampleRate: OUTPUT_SAMPLE_RATE });
  }
  isPlaying = false;
}

// ---- Avatar Control ----

function showAvatarTalking() {
  setAvatarTalking(true);
}

function showAvatarListening() {
  setAvatarTalking(false);
}

function hideAvatar() {
  stopAvatar();
  avatarActive = false;
}

function initAvatar() {
  if (!avatarActive) {
    avatarActive = true;
    startAvatar();
  }
}

// ---- WebSocket ----

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}${API_BASE}/ws`);

  ws.onopen = () => {
    setStatus("Conectado — iniciando entrevista...");
    ws.send(JSON.stringify({ type: "start", job_description: jobDescription }));
  };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    switch (msg.type) {
      case "session_started":
        setStatus("⏳ Aguardando a entrevistadora...");
        sessionReady = true;
        isMicOn = true;
        micBtn.classList.add("active");
        micBtn.textContent = "🔇";
        initAvatar();
        showAvatarListening();
        break;
      case "audio":
        if (!hadFirstAudio) {
          hadFirstAudio = true;
          setStatus("🔴 Entrevista em andamento — fale quando estiver pronto");
        }
        showAvatarTalking();
        enqueueAudio(base64ToInt16Array(msg.content));
        break;
      case "barge_in":
        // Candidate interrupted — clear playback queue immediately
        clearPlaybackQueue();
        showAvatarListening();
        break;
      case "text":
        if (msg.role === "USER") addMessage("USER", msg.content);
        else if (msg.role === "ASSISTANT" && isSpeculative) {
          addMessage("ASSISTANT", msg.content);
          // Auto-end ONLY when the interviewer (ASSISTANT speculative) signals end
          if (msg.content && msg.content.includes("[ENTREVISTA FINALIZADA]")) {
            console.log("Interview end marker detected, ending in 5s...");
            setTimeout(() => { if (isActive) endInterview(); }, 5000);
          }
        }
        break;
      case "content_start":
        currentRole = msg.role || "";
        isSpeculative = msg.speculative || false;
        break;
      case "session_stopped":
        setStatus("Entrevista encerrada — gerando relatório...");
        break;
      case "report_generating":
        addMessage("system", "⏳ Gerando relatório de avaliação...");
        break;
      case "report":
        showReport(msg.content, msg.token_usage);
        break;
      case "error":
        addMessage("error", msg.message);
        setStatus("Erro — tente novamente");
        break;
    }
  };

  ws.onerror = (e) => { console.error("WS error:", e); setStatus("Erro de conexão"); };
  ws.onclose = (e) => {
    console.log("WS closed, code:", e.code, "reason:", e.reason, "isActive:", isActive, "isEnding:", isEnding);
    if (isActive && !isEnding) {
      setStatus("Conexão perdida — reconectando não suportado. Tente novamente.");
      // Don't auto-end, let user decide
    }
  };
}

// ---- Interview lifecycle ----

async function startInterview() {
  jobDescription = (selectedJobDescription || "").trim();
  if (!jobDescription) { alert("Selecione uma vaga."); return; }

  const label = selectedJobTitle || "Vaga personalizada";
  currentJobTag.textContent = `📋 ${label}`;

  setupEl.style.display = "none";
  interviewEl.style.display = "flex";
  transcriptEl.innerHTML = "";
  addMessage("system", `Entrevista para "${label}" iniciada. Conectando...`);

  isActive = true;
  hadFirstAudio = false;
  sessionReady = false;
  initPlayback();

  // Start send timer immediately (sends silence until session is ready + mic is on)
  startSendTimer();

  // Connect WebSocket FIRST (doesn't depend on mic)
  connectWS();

  // Start mic capture in background (non-blocking)
  startCapture().catch((e) => {
    console.error("Mic error:", e);
    addMessage("error", "Não foi possível acessar o microfone: " + e.message);
  });
}

function endInterview() {
  if (isEnding) return;
  isEnding = true;
  isActive = false;
  isMicOn = false;
  micBtn.classList.remove("active");
  micBtn.textContent = "🎤";
  stopCapture();
  stopPlayback();
  hideAvatar();
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "stop" }));
    // Don't close WS yet — wait for report
  }
  setStatus("Entrevista encerrada — aguarde o relatório...");
  addMessage("system", "Entrevista finalizada. Gerando avaliação...");
  interviewEl.style.display = "none";
}

function showReport(markdown, tokenUsage) {
  // Parse score from first line (SCORE:75)
  let score = null;
  let reportText = markdown;
  // Parse score - try multiple patterns
  const patterns = [
    /SCORE:\s*(\d+)/im,
    /Score de Aderência[:\s]*(\d+)/im,
    /Aderência[:\s]*(\d+)/im,
    /(\d+)\s*%/m,
  ];
  for (const pat of patterns) {
    const m = markdown.match(pat);
    if (m) {
      score = parseInt(m[1], 10);
      if (score >= 0 && score <= 100) break;
      score = null;
    }
  }
  reportText = markdown.replace(/^SCORE:\s*\d+%?\s*/im, "");

  // Render semáforo
  const scorePanel = document.getElementById("score-panel");
  const lightGreen = document.getElementById("light-green");
  const lightYellow = document.getElementById("light-yellow");
  const lightRed = document.getElementById("light-red");
  const scoreValue = document.getElementById("score-value");
  const scoreBar = document.getElementById("score-bar");

  lightGreen.className = "light";
  lightYellow.className = "light";
  lightRed.className = "light";

  if (score !== null) {
    scoreValue.textContent = `${score}%`;
    scoreBar.style.width = `${score}%`;

    if (score >= 70) {
      lightGreen.classList.add("green-on");
      scoreBar.style.background = "#4caf50";
      scoreValue.style.color = "#4caf50";
    } else if (score >= 40) {
      lightYellow.classList.add("yellow-on");
      scoreBar.style.background = "#ffc107";
      scoreValue.style.color = "#ffc107";
    } else {
      lightRed.classList.add("red-on");
      scoreBar.style.background = "#f44336";
      scoreValue.style.color = "#f44336";
    }
  }

  // Render report markdown
  const html = reportText
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^### (.+)$/gm, "<h3 style='color:#8b9cf7;margin-top:1rem;'>$1</h3>")
    .replace(/^## (.+)$/gm, "<h3 style='color:#8b9cf7;margin-top:1rem;'>$1</h3>")
    .replace(/^- (.+)$/gm, "• $1")
    .replace(/\n/g, "<br>");
  reportContent.innerHTML = html;

  // Render token usage & cost
  if (tokenUsage && tokenUsage.total > 0) {
    const tokenPanel = document.getElementById("token-panel");
    const tokenTable = document.getElementById("token-table");

    // Nova Sonic 2 pricing (per 1K tokens)
    const SONIC_INPUT_SPEECH = 0.0034;
    const SONIC_OUTPUT_SPEECH = 0.0136;
    const SONIC_INPUT_TEXT = 0.0034;
    const SONIC_OUTPUT_TEXT = 0.0136;

    const inSpeech = tokenUsage.input_speech || 0;
    const inText = tokenUsage.input_text || 0;
    const outSpeech = tokenUsage.output_speech || 0;
    const outText = tokenUsage.output_text || 0;
    const totalIn = tokenUsage.total_input || 0;
    const totalOut = tokenUsage.total_output || 0;
    const total = tokenUsage.total || 0;

    const costInSpeech = (inSpeech / 1000) * SONIC_INPUT_SPEECH;
    const costInText = (inText / 1000) * SONIC_INPUT_TEXT;
    const costOutSpeech = (outSpeech / 1000) * SONIC_OUTPUT_SPEECH;
    const costOutText = (outText / 1000) * SONIC_OUTPUT_TEXT;
    const totalCost = costInSpeech + costInText + costOutSpeech + costOutText;

    tokenTable.innerHTML = `
      <tr><td>🎤 Input Speech Tokens</td><td>${inSpeech.toLocaleString()}</td></tr>
      <tr><td>📝 Input Text Tokens</td><td>${inText.toLocaleString()}</td></tr>
      <tr><td>🔊 Output Speech Tokens</td><td>${outSpeech.toLocaleString()}</td></tr>
      <tr><td>💬 Output Text Tokens</td><td>${outText.toLocaleString()}</td></tr>
      <tr><td>📥 Total Input</td><td>${totalIn.toLocaleString()}</td></tr>
      <tr><td>📤 Total Output</td><td>${totalOut.toLocaleString()}</td></tr>
      <tr><td>📊 Total Tokens</td><td>${total.toLocaleString()}</td></tr>
      <tr class="cost-row"><td>💵 Custo estimado</td><td>US$ ${totalCost.toFixed(4)}</td></tr>
    `;
    tokenPanel.style.display = "block";
  }

  reportPanel.style.display = "block";
  setStatus("Relatório pronto");
  if (ws) { ws.close(); ws = null; }
}

function resetToSetup() {
  reportPanel.style.display = "none";
  transcriptEl.innerHTML = "";
  selectedJobDescription = "";
  selectedJobTitle = "";
  isEnding = false;
  hadFirstAudio = false;
  sessionReady = false;
  document.querySelectorAll(".job-card").forEach((c) => c.classList.remove("selected"));
  setupEl.style.display = "flex";
  setStatus("");
}

// Mic toggle (mute/unmute during interview)
micBtn.addEventListener("click", () => {
  if (!isActive) return;
  isMicOn = !isMicOn;
  micBtn.classList.toggle("active", isMicOn);
  micBtn.textContent = isMicOn ? "🔇" : "🎤";
  setStatus(isMicOn ? "🔴 Microfone ligado" : "Microfone desligado (mudo)");
});

startBtn.addEventListener("click", startInterview);
stopIntBtn.addEventListener("click", endInterview);
newIntBtn.addEventListener("click", resetToSetup);

// Geração de vaga (submenu Vagas) e histórico (submenu Relatório) foram movidos p/ ent-modules.js.

}; // fim de window.initInterviewer
