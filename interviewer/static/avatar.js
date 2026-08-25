// Photo-based avatar with animated mouth and eye blinks
const avatarCanvas = document.getElementById("avatar-canvas");
const avatarCtx = avatarCanvas.getContext("2d");
const avatarContainer = document.getElementById("avatar-container");
const W = avatarCanvas.width, H = avatarCanvas.height;

let avatarMouthOpen = 0, avatarTargetMouth = 0, avatarIsTalking = false;
let avatarBlinkProgress = 0; // 0 = open, 1 = fully closed
let avatarBlinkTarget = 0;
let avatarRunning = false;
let photoLoaded = false;

const photo = new Image();
photo.src = "/static/carolina_photo.jpg";

let FACE = {
  leftEye:  { x: 146, y: 192, w: 16, h: 6 },
  rightEye: { x: 253, y: 194, w: 16, h: 6 },
  mouth:    { x: 200, y: 297, w: 39, h: 8 },
};

// Pre-built eyelid strips (skin from above each eye)
let lidDataL = null, lidDataR = null;

photo.onload = () => {
  photoLoaded = true;
  buildLids();
};

function startAvatar() { avatarRunning = true; scheduleNextBlink(); drawLoop(); }
function stopAvatar() { avatarRunning = false; }
function setAvatarTalking(t) {
  avatarIsTalking = t;
  avatarContainer.className = t ? "talking" : "listening";
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
  const open = avatarMouthOpen * 6;
  if (open < 0.3) return;

  const mw = m.w;
  const halfH = 8;
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
