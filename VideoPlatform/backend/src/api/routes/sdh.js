'use strict';

/**
 * Legenda por IA a partir do ÁUDIO (Mistral Voxtral) — modo PROTÓTIPO com
 * múltiplas variantes para comparar qualidade × tempo × custo:
 *
 *   - mini1p : Voxtral Mini 3B, 1 passada (fala + marcadores)      → faixa pt-sdh-mini
 *   - v24b1p : Voxtral Small 24B, 1 passada (fala + marcadores)    → faixa pt-sdh
 *   - v24b2p : Voxtral Small 24B, 2 passadas (fala / sons)         → faixa pt-sdh-2p
 *
 * Em TODAS as variantes os marcadores de som ([música], [risos]...) são
 * colocados SÓ nas pausas da fala (com margem), nunca grudados no diálogo.
 * Cada variante grava métricas próprias em `sdhVariants.<método>` (tempo,
 * tokens, custo, nº de falas, nº de marcadores) para a tela de comparação.
 *
 * A DESCRIÇÃO do vídeo é outra feature (describe.js, modelo de vídeo).
 */

const { S3Client, GetObjectCommand, PutObjectCommand } = require('@aws-sdk/client-s3');
const { BedrockRuntimeClient, ConverseCommand } = require('@aws-sdk/client-bedrock-runtime');
const {
  REGION,
  MEDIA_BUCKET,
  keys,
  getVideo,
  updateVideo,
  patchVariant,
  recomputeCostTotal,
  getSettings,
  reqSetting,
  nowIso,
} = require('../../lib/common');
const { serializeVtt } = require('../../lib/vtt');
const { ok, badRequest, notFound, serverError, pathParam, parseBody } = require('../http');

const s3 = new S3Client({ region: REGION });
// Chunking faz muitas chamadas; retry adaptativo ajuda contra throttling do Bedrock.
const bedrock = new BedrockRuntimeClient({ region: REGION, maxAttempts: 6, retryMode: 'adaptive' });

// Prompt padrão da passada SDH (fala + marcadores). Editável em settings (sdh.prompt).
const DEFAULT_SDH_PROMPT = `Você é um legendador profissional de legendas SDH (closed caption) em português do Brasil.
Transcreva a FALA exatamente, com timestamps precisos (use frações de segundo, ex.: 0m2.4s).
Marque também os SONS não-falados RELEVANTES (música, aplausos, risos, trovão, passos, motor, explosão...), essenciais para surdos — mas sem exagerar.
Formato: uma linha por trecho: [INÍCIO - FIM] CONTEÚDO
- CONTEÚDO = a fala, quando houver voz; OU o som entre colchetes minúsculos, ex.: [música].
- AGRUPE um som contínuo em UMA linha cobrindo toda a sua duração. NUNCA repita o mesmo som em linhas seguidas.
- Priorize a fala; marque o ambiente só quando ele muda. Não marque respiração/ruído mínimo. Não invente nem traduza.
Exemplo:
[0m0s - 0m4.5s] [música de abertura]
[0m5s - 0m8s] Bom dia!
[0m8s - 0m25s] [risos]
Responda apenas as linhas.`;

// Passada "só fala" (variante de 2 passadas).
const PROMPT_SPEECH = `Transcreva a FALA deste áudio em português do Brasil, com timestamps precisos (frações de segundo).
Uma linha por trecho: [INÍCIO - FIM] texto, com tempos como 0m2.4s.
Transcreva SOMENTE a fala falada (inclua onomatopeias ditas pelo personagem, ex.: "Vrum!"). NÃO descreva sons de ambiente. Não traduza. Responda só as linhas.`;

// Passada "só sons não-falados" (variante de 2 passadas).
const PROMPT_EVENTS = `Liste SOMENTE os SONS NÃO-FALADOS audíveis deste áudio (música, aplausos, risos, trovão, passos, motor, explosão, telefone...).
Uma linha por som: [INÍCIO - FIM] [rótulo em minúsculas], com tempos como 0m8s.
AGRUPE um som contínuo em UMA linha cobrindo toda a sua duração. IGNORE completamente a fala. Não invente. Responda só as linhas.`;

/** Reexecuta `fn` com backoff exponencial em erros transitórios (throttling). */
async function withRetry(fn, { tries = 4, baseMs = 1500 } = {}) {
  let last;
  for (let i = 0; i < tries; i++) {
    try {
      return await fn();
    } catch (e) {
      last = e;
      const retriable = /throttl|too many|rate exceeded|ServiceUnavailable|Timeout|503|429/i.test(
        `${e.name} ${e.message}`
      );
      if (!retriable || i === tries - 1) throw e;
      await new Promise((r) => setTimeout(r, baseMs * 2 ** i + Math.random() * 500));
    }
  }
  throw last;
}

/** Converte um carimbo de tempo do Voxtral (0h0m0s0ms ou mm:ss) em segundos. */
function parseVoxTime(s) {
  const str = String(s).trim();
  if (str.includes(':')) {
    return str.split(':').reduce((acc, p) => acc * 60 + (parseFloat(p) || 0), 0);
  }
  const m = /(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?(?:(\d+)ms)?/.exec(str) || [];
  return +(m[1] || 0) * 3600 + +(m[2] || 0) * 60 + +(m[3] || 0) + +(m[4] || 0) / 1000;
}

/** Extrai cues "[ini - fim] conteúdo" (o conteúdo pode conter colchetes). */
function parseTranscription(text) {
  const TS = '\\[\\s*[0-9hms.: ]+?\\s*-\\s*[0-9hms.: ]+?\\s*\\]';
  const re = new RegExp(
    `\\[\\s*([0-9hms.: ]+?)\\s*-\\s*([0-9hms.: ]+?)\\s*\\]\\s*([\\s\\S]*?)(?=\\s*${TS}|\\s*$)`,
    'g'
  );
  const cues = [];
  let m;
  while ((m = re.exec(text)) !== null) {
    const t = (m[3] || '').trim();
    if (t) cues.push({ start: parseVoxTime(m[1]), end: parseVoxTime(m[2]), text: t });
  }
  return cues;
}

/** Normaliza um marcador de som: "[ Som De Motor ]" -> "[som de motor]". */
function normalizeMarker(text) {
  const m = /\[([^\]]*)\]/.exec(text);
  const inner = (m ? m[1] : text.replace(/[[\]]/g, ''))
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ');
  return `[${inner}]`;
}

/** Remove de um intervalo as partes cobertas por fala (retorna as lacunas). */
function subtractSpeech(ev, speech) {
  let parts = [{ start: ev.start, end: ev.end }];
  for (const s of speech) {
    const next = [];
    for (const p of parts) {
      if (s.end <= p.start || s.start >= p.end) {
        next.push(p);
        continue;
      }
      if (s.start > p.start) next.push({ start: p.start, end: Math.min(s.start, p.end) });
      if (s.end < p.end) next.push({ start: Math.max(s.end, p.start), end: p.end });
    }
    parts = next;
  }
  return parts;
}

/**
 * Coloca os marcadores de som SÓ nas pausas da fala, com margem de silêncio
 * antes/depois (não grudam no diálogo). Marcadores iguais e próximos são
 * fundidos. É o que dá o aspecto profissional à legenda SDH.
 */
function placeMarkersInGaps(speechCues, markers, { marginSec, minDurSec, maxDurSec }, mergeGapSec) {
  const speech = speechCues
    .map((c) => ({ start: c.start, end: c.end }))
    .sort((a, b) => a.start - b.start);
  const out = [];
  for (const e of markers) {
    for (const gap of subtractSpeech(e, speech)) {
      const prevEnds = speech.filter((s) => s.end <= gap.start + 0.001).map((s) => s.end);
      const nextStarts = speech.filter((s) => s.start >= gap.end - 0.001).map((s) => s.start);
      let start = gap.start;
      let end = gap.end;
      if (prevEnds.length) start = Math.max(start, Math.max(...prevEnds) + marginSec);
      if (nextStarts.length) end = Math.min(end, Math.min(...nextStarts) - marginSec);
      if (end - start < minDurSec) continue; // pausa curta demais
      if (end - start > maxDurSec) end = start + maxDurSec;
      out.push({ start, end, text: e.text });
    }
  }
  out.sort((a, b) => a.start - b.start);
  const merged = [];
  for (const c of out) {
    const last = merged[merged.length - 1];
    if (last && last.text === c.text && c.start <= last.end + mergeGapSec) {
      last.end = Math.max(last.end, c.end);
    } else {
      merged.push({ ...c });
    }
  }
  return merged;
}

async function voxtralCall(bytes, modelId, prompt, maxTokens) {
  const res = await bedrock.send(
    new ConverseCommand({
      modelId,
      messages: [
        { role: 'user', content: [{ audio: { format: 'wav', source: { bytes } } }, { text: prompt }] },
      ],
      inferenceConfig: { maxTokens, temperature: 0 },
    })
  );
  const text = res.output?.message?.content?.map((c) => c.text).join('') || '';
  const u = res.usage || {};
  return { cues: parseTranscription(text), inTok: u.inputTokens || 0, outTok: u.outputTokens || 0 };
}

// ---------- Chunking de áudio WAV ----------
function parseWavHeader(buf) {
  if (
    buf.length < 44 ||
    buf.toString('ascii', 0, 4) !== 'RIFF' ||
    buf.toString('ascii', 8, 12) !== 'WAVE'
  ) {
    throw new Error('Áudio WAV inválido (cabeçalho RIFF/WAVE ausente).');
  }
  let off = 12;
  let fmt = null;
  let dataOffset = -1;
  let dataSize = 0;
  while (off + 8 <= buf.length) {
    const id = buf.toString('ascii', off, off + 4);
    const size = buf.readUInt32LE(off + 4);
    const body = off + 8;
    if (id === 'fmt ') {
      fmt = {
        channels: buf.readUInt16LE(body + 2),
        sampleRate: buf.readUInt32LE(body + 4),
        bitsPerSample: buf.readUInt16LE(body + 14),
      };
    } else if (id === 'data') {
      dataOffset = body;
      dataSize = Math.min(size, buf.length - body);
      break;
    }
    off = body + size + (size % 2);
  }
  if (!fmt || dataOffset < 0) throw new Error('Áudio WAV inválido (fmt/data ausente).');
  return { ...fmt, dataOffset, dataSize };
}

function buildWavHeader({ sampleRate, channels, bitsPerSample, dataSize }) {
  const blockAlign = channels * (bitsPerSample / 8);
  const byteRate = sampleRate * blockAlign;
  const h = Buffer.alloc(44);
  h.write('RIFF', 0, 'ascii');
  h.writeUInt32LE(36 + dataSize, 4);
  h.write('WAVE', 8, 'ascii');
  h.write('fmt ', 12, 'ascii');
  h.writeUInt32LE(16, 16);
  h.writeUInt16LE(1, 20);
  h.writeUInt16LE(channels, 22);
  h.writeUInt32LE(sampleRate, 24);
  h.writeUInt32LE(byteRate, 28);
  h.writeUInt16LE(blockAlign, 32);
  h.writeUInt16LE(bitsPerSample, 34);
  h.write('data', 36, 'ascii');
  h.writeUInt32LE(dataSize, 40);
  return h;
}

function planChunks(audioBuf, { chunkSec, overlapSec, maxChunks, maxChunkBytes }) {
  const { sampleRate, channels, bitsPerSample, dataOffset, dataSize } = parseWavHeader(audioBuf);
  const frame = channels * (bitsPerSample / 8);
  const bytesPerSec = sampleRate * frame;
  const headroom = 64;
  const byTime = Math.floor(chunkSec * bytesPerSec);
  const byCeil = Math.max(frame, Math.floor((maxChunkBytes - headroom) / frame) * frame);
  let chunkBytes = Math.min(byTime, byCeil);
  chunkBytes = Math.max(frame, Math.floor(chunkBytes / frame) * frame);
  const overlapBytes = Math.max(0, Math.floor((overlapSec * bytesPerSec) / frame) * frame);
  const stepBytes = Math.max(frame, chunkBytes - overlapBytes);

  const chunks = [];
  for (let pos = 0; pos < dataSize; pos += stepBytes) {
    const end = Math.min(dataSize, pos + chunkBytes);
    const pcm = audioBuf.subarray(dataOffset + pos, dataOffset + end);
    const header = buildWavHeader({ sampleRate, channels, bitsPerSample, dataSize: pcm.length });
    chunks.push({
      wav: Buffer.concat([header, pcm]),
      startSec: pos / bytesPerSec,
      endSec: end / bytesPerSec,
    });
    if (end >= dataSize || chunks.length >= maxChunks) break;
  }
  return chunks;
}

async function mapWithConcurrency(items, limit, fn) {
  const results = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, async () => {
    for (let idx = next++; idx < items.length; idx = next++) {
      results[idx] = await fn(items[idx], idx);
    }
  });
  await Promise.all(workers);
  return results;
}

/** Transcreve/legenda o áudio inteiro com um prompt, fatiando e costurando. */
async function transcribeAudio(audioBuf, modelId, opts) {
  const { prompt, maxTokens } = opts;
  const chunks = planChunks(audioBuf, opts);
  const perChunk = await mapWithConcurrency(chunks, opts.concurrency, async (c) => {
    const r = await withRetry(() => voxtralCall(c.wav, modelId, prompt, maxTokens));
    const dur = c.endSec - c.startSec;
    // Descarta/clampa timestamps ALUCINADOS fora da janela da fatia (o modelo
    // às vezes entra em loop e gera tempos além do áudio enviado).
    const cues = r.cues
      .filter((q) => q.start >= -0.5 && q.start <= dur + 1.5)
      .map((q) => {
        const start = Math.max(0, q.start);
        let end = Math.min(q.end, dur);
        if (end <= start) end = Math.min(dur, start + 0.5);
        return { start: start + c.startSec, end: end + c.startSec, text: q.text };
      });
    return { cues, inTok: r.inTok, outTok: r.outTok };
  });
  const all = [];
  let inTok = 0;
  let outTok = 0;
  for (let k = 0; k < chunks.length; k++) {
    inTok += perChunk[k].inTok;
    outTok += perChunk[k].outTok;
    const lower = k === 0 ? -Infinity : (chunks[k].startSec + chunks[k - 1].endSec) / 2;
    const upper =
      k === chunks.length - 1 ? Infinity : (chunks[k + 1].startSec + chunks[k].endSec) / 2;
    for (const q of perChunk[k].cues) {
      if (q.start >= lower && q.start < upper) all.push(q);
    }
  }
  all.sort((a, b) => a.start - b.start);
  return { cues: all, inTok, outTok, chunks: chunks.length };
}

const VARIANTS = {
  mini1p: { lang: 'pt-sdh-mini', passes: 1, modelKey: 'mini', rateKey: 'mini' },
  v24b1p: { lang: 'pt-sdh', passes: 1, modelKey: 'small', rateKey: 'small' },
  v24b2p: { lang: 'pt-sdh-2p', passes: 2, modelKey: 'small', rateKey: 'small' },
};

/** POST /api/videos/{videoId}/sdh  { method?: 'mini1p'|'v24b1p'|'v24b2p' } */
async function create(event) {
  const videoId = pathParam(event, 'videoId');
  const method = (parseBody(event) || {}).method || 'v24b1p';
  const spec = VARIANTS[method];
  if (!spec) return badRequest(`Método SDH inválido: ${method}`);

  const video = await getVideo(videoId);
  if (!video) return notFound('Vídeo não encontrado');

  const cfg = await getSettings();
  const modelId =
    spec.modelKey === 'mini'
      ? cfg['model.voxtralMini'] || 'mistral.voxtral-mini-3b-2507'
      : reqSetting(cfg, 'model.voxtral');
  const rateIn =
    spec.rateKey === 'mini'
      ? cfg['cost.voxtralMiniInputPer1k'] ?? cfg['cost.voxtralInputPer1k'] ?? 0
      : cfg['cost.voxtralInputPer1k'] ?? 0;
  const rateOut =
    spec.rateKey === 'mini'
      ? cfg['cost.voxtralMiniOutputPer1k'] ?? cfg['cost.voxtralOutputPer1k'] ?? 0
      : cfg['cost.voxtralOutputPer1k'] ?? 0;

  const chunkOpts = {
    maxTokens: cfg['sdh.voxtralMaxTokens'] ?? 4000,
    chunkSec: cfg['sdh.chunkSec'] ?? 60,
    overlapSec: cfg['sdh.chunkOverlapSec'] ?? 3,
    concurrency: cfg['sdh.chunkConcurrency'] ?? 5,
    maxChunks: cfg['sdh.maxChunks'] ?? 240,
    maxChunkBytes: (cfg['sdh.maxAudioMB'] || 2) * 1024 * 1024,
  };
  const gapOpts = {
    marginSec: cfg['sdh.speechMarginSec'] ?? 2,
    minDurSec: cfg['sdh.minMarkerSec'] ?? 0.8,
    maxDurSec: cfg['sdh.maxMarkerSec'] ?? 6,
  };
  const minCueSec = cfg['sdh.minCueSec'] ?? 0.8;
  const mergeGapSec = cfg['sdh.mergeMarkerGapSec'] ?? 2.5;
  const sdhPrompt = cfg['sdh.prompt'] || DEFAULT_SDH_PROMPT;

  const audioKey = keys.audio(videoId);
  let audioBuf;
  try {
    const r = await s3.send(new GetObjectCommand({ Bucket: MEDIA_BUCKET, Key: audioKey }));
    audioBuf = Buffer.from(await r.Body.transformToByteArray());
  } catch (e) {
    return notFound('Áudio do vídeo não encontrado (reprocessar o vídeo para gerar o áudio).');
  }

  try {
    const t0 = Date.now();
    let speechRaw;
    let markerRaw;
    let inTok = 0;
    let outTok = 0;

    if (spec.passes === 1) {
      const r = await transcribeAudio(audioBuf, modelId, { ...chunkOpts, prompt: sdhPrompt });
      inTok = r.inTok;
      outTok = r.outTok;
      speechRaw = r.cues.filter((c) => !c.text.startsWith('['));
      markerRaw = r.cues.filter((c) => c.text.startsWith('['));
    } else {
      // 2 passadas em PARALELO (fala / sons) para caber no timeout do worker.
      const [a, b] = await Promise.all([
        transcribeAudio(audioBuf, modelId, { ...chunkOpts, prompt: PROMPT_SPEECH }),
        transcribeAudio(audioBuf, modelId, { ...chunkOpts, prompt: PROMPT_EVENTS }),
      ]);
      inTok = a.inTok + b.inTok;
      outTok = a.outTok + b.outTok;
      speechRaw = a.cues.filter((c) => !c.text.startsWith('['));
      // Garante que todo item do passe de eventos seja um marcador entre colchetes.
      markerRaw = b.cues.map((c) => ({
        ...c,
        text: c.text.startsWith('[') ? c.text : `[${c.text}]`,
      }));
    }
    const timeMs = Date.now() - t0;

    // Fala: duração mínima (corrige cues degeneradas).
    const speech = speechRaw.map((c) => ({ start: c.start, end: c.end, text: c.text }));
    for (const c of speech) if (c.end - c.start < minCueSec) c.end = c.start + minCueSec;
    speech.sort((a, b) => a.start - b.start);

    // Marcadores SÓ nas pausas (não grudam na fala).
    const placed = placeMarkersInGaps(
      speech,
      markerRaw.map((m) => ({ ...m, text: normalizeMarker(m.text) })),
      gapOpts,
      mergeGapSec
    );

    const cues = [...speech, ...placed].sort(
      (a, b) => a.start - b.start || (a.text.startsWith('[') ? 1 : -1)
    );
    if (cues.length === 0) return serverError('Nenhum conteúdo utilizável do áudio.');

    const vtt = serializeVtt({ header: 'WEBVTT', cues });
    const destKey = keys.subtitle(videoId, spec.lang);
    await s3.send(
      new PutObjectCommand({ Bucket: MEDIA_BUCKET, Key: destKey, Body: vtt, ContentType: 'text/vtt' })
    );

    // Custo = modelo (tokens Voxtral) + compute (Lambda GB-s do worker).
    const voxUSD = (inTok / 1000) * rateIn + (outTok / 1000) * rateOut;
    const memGB = (Number(process.env.AWS_LAMBDA_FUNCTION_MEMORY_SIZE) || 2048) / 1024;
    const lambdaUSD = (timeMs / 1000) * memGB * (cfg['cost.lambdaPerGbSecond'] || 0);
    const usd = +(voxUSD + lambdaUSD).toFixed(5);

    // Métricas da variante (atômico, sem corrida entre jobs paralelos).
    await patchVariant(videoId, method, {
      lang: spec.lang,
      key: destKey,
      model: modelId,
      passes: spec.passes,
      timeMs,
      inTok,
      outTok,
      voxUSD: +voxUSD.toFixed(5),
      lambdaUSD: +lambdaUSD.toFixed(5),
      usd,
      cues: cues.length,
      markers: placed.length,
      speech: speech.length,
      status: 'pronto',
      error: '',
      generatedAt: nowIso(),
    });

    // Reflete o custo da ÚLTIMA variante gerada em cost.sdhUSD (representativo).
    const cost = { ...(video.cost || {}) };
    cost.sdhUSD = usd;
    cost.totalUSD = recomputeCostTotal(cost);
    await updateVideo(videoId, { cost });

    return ok({
      videoId,
      method,
      lang: spec.lang,
      model: modelId,
      timeMs,
      inTok,
      outTok,
      usd,
      cues: cues.length,
      markers: placed.length,
    });
  } catch (e) {
    console.error('Falha SDH', method, e);
    return serverError(`Falha ao gerar legenda SDH (${method}): ${e.message}`);
  }
}

module.exports = { create };
// Exposto apenas para o harness de validação (scripts/sdh-sync-test.js).
// Não é usado pelo worker/produção; exportar funções puras é inócuo em runtime.
module.exports.__internals = { transcribeAudio, parseWavHeader, buildWavHeader, DEFAULT_SDH_PROMPT };
