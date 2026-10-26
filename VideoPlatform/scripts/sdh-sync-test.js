'use strict';

/**
 * Harness de VALIDAÇÃO de sincronia do SDH (24B) — não faz parte do deploy.
 *
 * Objetivo: isolar a variável "tamanho do chunk" e medir, em evidência, se
 * diminuir o chunk melhora a sincronia dos timestamps do Voxtral 24B.
 *
 * Como: baixa (via S3 Range GET) só os primeiros ~CLIP_SEC segundos do áudio
 * REAL de um vídeo já processado, roda o MESMO código de produção
 * (sdh.transcribeAudio) com chunk grande vs pequeno, e imprime lado a lado
 * contra a legenda-verdade do Transcribe (faixa pt), cujos tempos são corretos.
 *
 * Uso:
 *   set -a; source .env; set +a
 *   VIDEOS_TABLE=videoplatform-videos SETTINGS_TABLE=videoplatform-settings \
 *   MEDIA_BUCKET=<bucket> node scripts/sdh-sync-test.js
 *
 * Env opcionais: TEST_VIDEO_ID, CLIP_SEC (120), CHUNK_SECS ("60,20").
 */

const path = require('path');
const { S3Client, GetObjectCommand } = require('@aws-sdk/client-s3');

const BACKEND = path.resolve(__dirname, '../backend/src');
const { __internals } = require(path.join(BACKEND, 'api/routes/sdh.js'));
const { getSettings, reqSetting, REGION, MEDIA_BUCKET, keys } = require(
  path.join(BACKEND, 'lib/common.js')
);
const { parseVtt } = require(path.join(BACKEND, 'lib/vtt.js'));

const { transcribeAudio, parseWavHeader, buildWavHeader, DEFAULT_SDH_PROMPT } = __internals;

const VIDEO_ID = process.env.TEST_VIDEO_ID || 'a9b8f137-047b-4f85-9685-bce9130d1f58';
const CLIP_SEC = Number(process.env.CLIP_SEC || 120);
const CHUNK_SECS = (process.env.CHUNK_SECS || '60,20').split(',').map(Number);
const N = Number(process.env.SHOW || 16);

const s3 = new S3Client({ region: REGION });

async function getRange(key, maxBytes) {
  const r = await s3.send(
    new GetObjectCommand({ Bucket: MEDIA_BUCKET, Key: key, Range: `bytes=0-${maxBytes}` })
  );
  return Buffer.from(await r.Body.transformToByteArray());
}
async function getText(key) {
  const r = await s3.send(new GetObjectCommand({ Bucket: MEDIA_BUCKET, Key: key }));
  return r.Body.transformToString('utf-8');
}

/** Recorta os primeiros `seconds` do WAV (buffer pode ser parcial do Range GET). */
function sliceWav(buf, seconds) {
  const h = parseWavHeader(buf);
  const frame = h.channels * (h.bitsPerSample / 8);
  const bytesPerSec = h.sampleRate * frame;
  let want = Math.floor((seconds * bytesPerSec) / frame) * frame;
  want = Math.min(want, h.dataSize);
  const pcm = buf.subarray(h.dataOffset, h.dataOffset + want);
  const header = buildWavHeader({
    sampleRate: h.sampleRate,
    channels: h.channels,
    bitsPerSample: h.bitsPerSample,
    dataSize: pcm.length,
  });
  return { wav: Buffer.concat([header, pcm]), sampleRate: h.sampleRate, bytesPerSec };
}

const fmt = (t) => {
  const m = Math.floor(t / 60);
  const s = t % 60;
  return `${String(m).padStart(2, '0')}:${s.toFixed(1).padStart(4, '0')}`;
};
const clean = (s) => s.replace(/\s+/g, ' ').trim().slice(0, 58);

(async () => {
  const cfg = await getSettings();
  const modelId = reqSetting(cfg, 'model.voxtral');
  const base = {
    prompt: cfg['sdh.prompt'] || DEFAULT_SDH_PROMPT,
    maxTokens: cfg['sdh.voxtralMaxTokens'] ?? 4000,
    overlapSec: cfg['sdh.chunkOverlapSec'] ?? 3,
    concurrency: cfg['sdh.chunkConcurrency'] ?? 5,
    maxChunks: cfg['sdh.maxChunks'] ?? 240,
    maxChunkBytes: (cfg['sdh.maxAudioMB'] || 2) * 1024 * 1024,
  };

  // ~CLIP_SEC s de áudio 16kHz mono 16-bit ≈ CLIP_SEC*32000 bytes (+ header + folga).
  const rangeBytes = Math.ceil((CLIP_SEC + 15) * 16000 * 2) + 2000;
  console.log(
    `Vídeo ${VIDEO_ID}\nBaixando ~${(rangeBytes / 1e6).toFixed(1)}MB (primeiros ~${CLIP_SEC}s)...`
  );
  const full = await getRange(keys.audio(VIDEO_ID), rangeBytes);
  const { wav } = sliceWav(full, CLIP_SEC);
  console.log(`Clipe: ${(wav.length / 1e6).toFixed(2)}MB | modelo ${modelId}\n`);

  const gt = parseVtt(await getText(keys.subtitle(VIDEO_ID, 'pt'))).cues.filter(
    (c) => c.start < CLIP_SEC
  );

  const results = {};
  for (const chunkSec of CHUNK_SECS) {
    const t0 = Date.now();
    const r = await transcribeAudio(wav, modelId, { ...base, chunkSec });
    const speech = r.cues
      .filter((c) => !c.text.startsWith('['))
      .sort((a, b) => a.start - b.start);
    results[chunkSec] = { speech, ms: Date.now() - t0, chunks: r.chunks, inTok: r.inTok, outTok: r.outTok };
    console.log(
      `chunk=${chunkSec}s → ${r.chunks} fatias | ${speech.length} falas | ${(
        (Date.now() - t0) /
        1000
      ).toFixed(1)}s | tokens ${r.inTok}/${r.outTok}`
    );
  }

  console.log('\n================ TRANSCRIBE (tempos corretos) ================');
  gt.slice(0, N).forEach((c) => console.log(`${fmt(c.start)}  ${clean(c.text)}`));
  for (const chunkSec of CHUNK_SECS) {
    console.log(`\n================ 24B chunk=${chunkSec}s ================`);
    results[chunkSec].speech.slice(0, N).forEach((c) => console.log(`${fmt(c.start)}  ${clean(c.text)}`));
  }
})().catch((e) => {
  console.error('ERRO:', e.message || e);
  process.exit(1);
});
