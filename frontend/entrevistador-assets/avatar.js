// Photo-based avatar with animated mouth and eye blinks.
// Integrado nativamente no portal: refs do canvas são resolvidas em startAvatar()
// (o markup é re-injetado a cada navegação); dimensões fixas (canvas 400x400).
let avatarCanvas = null, avatarCtx = null, avatarContainer = null;
const W = 400, H = 400;

let avatarMouthOpen = 0, avatarTargetMouth = 0, avatarIsTalking = false;
let avatarBlinkProgress = 0; // 0 = open, 1 = fully closed
let avatarBlinkTarget = 0;
let avatarRunning = false;
let photoLoaded = false;

const AVATAR_API = "/entrevistador";
const FACE_DEFAULT = { leftEye:{x:146,y:192,w:16,h:6}, rightEye:{x:253,y:194,w:16,h:6},
                       mouth:{x:200,y:297,w:39,h:8}, mouthOpenMax:6, mouthSplitH:8 };
const photo = new Image();
// A imagem e a calibração (FACE) vêm do avatar PADRÃO (API); default abaixo até carregar.
let FACE = Object.assign({}, FACE_DEFAULT);

// Carrega o avatar padrão (imagem + calibração) da API. Rechamado a cada início de entrevista.
async function loadDefaultAvatar() {
  let url = "/entrevistador-assets/carolina_photo.jpg"; // fallback embutido
  try {
    const a = await (await fetch(AVATAR_API + "/api/avatars/default")).json();
    if (a && a.imageUrl) {
      url = a.imageUrl;
      if (a.calibration && a.calibration.leftEye) FACE = Object.assign({}, FACE_DEFAULT, a.calibration);
    }
  } catch (_) {}
  photoLoaded = false;
  photo.src = url + (url.indexOf("?") < 0 ? "?t=" + Date.now() : "");
}

// Pre-built eyelid strips (skin from above each eye)
let lidDataL = null, lidDataR = null;

photo.onload = () => {
  photoLoaded = true;
  buildLids();
};

function startAvatar() {
  // Carrega imagem + calibração do avatar padrão (assíncrono; o drawLoop aguarda photoLoaded).
  loadDefaultAvatar();
  // Resolve o canvas atual (re-injetado a cada render do capítulo).
  avatarCanvas = document.getElementById("avatar-canvas");
  avatarContainer = document.getElementById("avatar-container");
  if (!avatarCanvas) return;
  avatarCanvas.width = W; avatarCanvas.height = H;
  avatarCtx = avatarCanvas.getContext("2d");
  avatarRunning = true; scheduleNextBlink(); drawLoop();
}
function stopAvatar() { avatarRunning = false; }
function setAvatarTalking(t) {
  avatarIsTalking = t;
  if (avatarContainer) avatarContainer.className = t ? "talking" : "listening";
  if (!t) avatarTargetMouth = 0;
}
function setAvatarMouthFromAudio(a) {
  if (avatarIsTalking) avatarTargetMouth = Math.min(1, a * 2.5);
}

function scheduleNextBlink() {
  if (!avatarRunning) return;
  setTimeout(() => {
    if (!avatarRunning) return;
    avatarBlinkTarget = 1; // close
    setTimeout(() => {
      avatarBlinkTarget = 0; // open
      scheduleNextBlink();
    }, 150 + Math.random() * 80);
  }, 2500 + Math.random() * 4000);
}

// Build eyelid data: for each eye, capture a strip of skin from just above the eye
// that will slide down like a curtain
function buildLids() {
  const tmp = document.createElement("canvas");
  tmp.width = W; tmp.height = H;
  const tc = tmp.getContext("2d");
  tc.drawImage(photo, 0, 0, W, H);

  for (const [key, eye] of [["L", FACE.leftEye], ["R", FACE.rightEye]]) {
    const lidW = eye.w * 2 + 8;
    const lidH = eye.h * 2 + 4;
    const lidCanvas = document.createElement("canvas");
    lidCanvas.width = lidW;
    lidCanvas.height = lidH;
    const lc = lidCanvas.getContext("2d");

    // Copy skin from above the eye (the eyelid/brow area)
    const srcX = eye.x - lidW / 2;
    const srcY = eye.y - lidH - eye.h * 0.3; // above the eye
    lc.drawImage(tc.canvas, srcX, srcY, lidW, lidH, 0, 0, lidW, lidH);

    // Soft horizontal fade on left/right edges
    lc.globalCompositeOperation = "destination-in";
    const fadeGrad = lc.createLinearGradient(0, 0, lidW, 0);
    fadeGrad.addColorStop(0, "rgba(0,0,0,0)");
    fadeGrad.addColorStop(0.15, "rgba(0,0,0,1)");
    fadeGrad.addColorStop(0.85, "rgba(0,0,0,1)");
    fadeGrad.addColorStop(1, "rgba(0,0,0,0)");
    lc.fillStyle = fadeGrad;
    lc.fillRect(0, 0, lidW, lidH);
    lc.globalCompositeOperation = "source-over";

    if (key === "L") lidDataL = { canvas: lidCanvas, w: lidW, h: lidH };
    else lidDataR = { canvas: lidCanvas, w: lidW, h: lidH };
  }
}

function drawLoop() {
  if (!avatarRunning) return;
  requestAnimationFrame(drawLoop);
  if (!photoLoaded) return;

  // Smooth blink interpolation
  avatarBlinkProgress += (avatarBlinkTarget - avatarBlinkProgress) * 0.35;
  avatarMouthOpen += (avatarTargetMouth - avatarMouthOpen) * 0.3;

  // Draw photo base
  avatarCtx.drawImage(photo, 0, 0, W, H);

  // Blink
  if (avatarBlinkProgress > 0.02) drawBlink();

  // Mouth
  if (avatarMouthOpen > 0.05) drawMouth();
}

function drawBlink() {
  const progress = avatarBlinkProgress; // 0=open, 1=closed

  for (const [eye, lid] of [[FACE.leftEye, lidDataL], [FACE.rightEye, lidDataR]]) {
    if (!lid) continue;

    // The eyelid slides down from above the eye
    // At progress=0, it's fully above (hidden). At progress=1, it covers the eye.
    const eyeTop = eye.y - eye.h;
    const eyeBottom = eye.y + eye.h;
    const eyeHeight = eyeBottom - eyeTop;

    // Clip to the eye area (elliptical)
    avatarCtx.save();
    avatarCtx.beginPath();
    avatarCtx.ellipse(eye.x, eye.y, eye.w + 2, eye.h + 2, 0, 0, Math.PI * 2);
    avatarCtx.clip();

    // Draw the lid sliding down
    // yOffset: how far down the lid has come (0 = above eye, eyeHeight = fully covering)
    const yOffset = progress * eyeHeight;
    const drawY = eyeTop - lid.h + yOffset;

    avatarCtx.drawImage(lid.canvas, eye.x - lid.w / 2, drawY);

    // Eyelid crease line at the bottom edge of the lid
    if (progress > 0.1) {
      const lineY = eyeTop + yOffset;
      avatarCtx.strokeStyle = `rgba(100,70,50,${0.3 * progress})`;
      avatarCtx.lineWidth = 1.2;
      avatarCtx.beginPath();
      avatarCtx.moveTo(eye.x - eye.w * 0.8, lineY);
      avatarCtx.quadraticCurveTo(eye.x, lineY + 1.5, eye.x + eye.w * 0.8, lineY);
      avatarCtx.stroke();
    }

    avatarCtx.restore();
  }
}

function drawMouth() {
  const m = FACE.mouth;
  const open = avatarMouthOpen * (FACE.mouthOpenMax || 6);
  if (open < 0.3) return;

  const mw = m.w;
  const halfH = FACE.mouthSplitH || 8;
  const gap = open;

  // Dark mouth cavity
  avatarCtx.fillStyle = "#1A0808";
  avatarCtx.beginPath();
  avatarCtx.ellipse(m.x, m.y, mw * 0.55, gap * 0.5 + 0.5, 0, 0, Math.PI * 2);
  avatarCtx.fill();

  // Teeth
  if (gap > 1.5) {
    avatarCtx.fillStyle = "rgba(248,244,238,0.5)";
    avatarCtx.beginPath();
    avatarCtx.ellipse(m.x, m.y - gap * 0.15, mw * 0.38, Math.min(2.5, gap * 0.25), 0, 0, Math.PI * 2);
    avatarCtx.fill();
  }

  // Shift upper lip up
  const srcX = m.x - mw - 5, srcW = mw * 2 + 10;
  avatarCtx.drawImage(photo,
    (srcX / W) * photo.naturalWidth, ((m.y - halfH) / H) * photo.naturalHeight,
    (srcW / W) * photo.naturalWidth, (halfH / H) * photo.naturalHeight,
    srcX, m.y - halfH - gap * 0.4, srcW, halfH
  );

  // Shift lower lip down
  avatarCtx.drawImage(photo,
    (srcX / W) * photo.naturalWidth, (m.y / H) * photo.naturalHeight,
    (srcW / W) * photo.naturalWidth, ((halfH + 4) / H) * photo.naturalHeight,
    srcX, m.y + gap * 0.4, srcW, halfH + 4
  );
}
