'use strict';

/**
 * Avaliador de QUALIDADE DO TEXTO da legenda (não avalia tempo).
 *
 * Dá uma nota de confiança (0-100) à legenda do Voxtral/24B comparando-a com a
 * realidade (o áudio), via dois métodos complementares e ancorados no áudio:
 *   1) CONSENSO (Voxtral × Transcribe): concordância de palavras entre duas
 *      transcrições independentes do MESMO áudio (LCS normalizado). JS puro.
 *   2) LLM-JUIZ: um LLM recebe candidata + referência e devolve nota, comentário
 *      e trechos suspeitos (JSON). Reusa model.analysis (Claude).
 *
 * Resultado gravado em sdhVariants.<método>.eval. NÃO cria uma 3ª legenda.
 * Ver docs/09-evaluator-qualidade-texto.md.
 */

const { S3Client, GetObjectCommand } = require('@aws-sdk/client-s3');
const { BedrockRuntimeClient, ConverseCommand } = require('@aws-sdk/client-bedrock-runtime');
const {
  REGION,
  MEDIA_BUCKET,
  keys,
  getVideo,
  getSettings,
  reqSetting,
  patchVariant,
  nowIso,
} = require('../../lib/common');
const { parseVtt } = require('../../lib/vtt');
const { ok, badRequest, notFound, serverError, parseBody, pathParam } = require('../http');

const s3 = new S3Client({ region: REGION });
const bedrock = new BedrockRuntimeClient({ region: REGION, maxAttempts: 4, retryMode: 'adaptive' });

// Método da variante -> faixa (lang) da legenda. Igual ao mapa em sdh.js.
const METHOD_LANG = { mini1p: 'pt-sdh-mini', v24b1p: 'pt-sdh', v24b2p: 'pt-sdh-2p' };
const REFERENCE_LANG = 'pt'; // faixa do Transcribe (2ª opinião / referência de texto)

const DEFAULT_EVAL_PROMPT = `Você é um avaliador de qualidade de TRANSCRIÇÃO em português do Brasil.
Recebe a legenda CANDIDATA (gerada por uma IA que ouve o áudio) e uma legenda de REFERÊNCIA (Amazon Transcribe, que ouviu o MESMO áudio).
Avalie SOMENTE a qualidade do TEXTO da candidata — o acerto das PALAVRAS em relação ao que foi realmente dito. NÃO avalie o tempo/sincronismo.
Considere erros: palavra trocada, nome próprio errado, alucinação (texto inventado), repetição indevida, trecho sem sentido. Marcadores de som ([música], [risos]) são esperados na candidata e NÃO são erro.
Responda APENAS um JSON válido, sem texto fora dele, no formato:
{"score": <0-100>, "comment": "<1 a 3 frases em pt-BR>", "flags": [{"time":"mm:ss","issue":"<curto>"}]}
score = sua confiança de que o TEXTO da candidata está correto (100 = perfeito). flags = até 8 trechos mais suspeitos. Se não houver suspeitas, flags: [].`;

const mmss = (sec) => `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(Math.floor(sec % 60)).padStart(2, '0')}`;

/** Normaliza para comparação: minúsculas, sem acento, só letras/números/apóstrofo. */
function normWords(text) {
  return String(text)
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9' ]/g, ' ')
    .split(/\s+/)
    .filter(Boolean);
}

/** Comprimento da maior subsequência comum entre dois arrays (DP 1D, O(n*m)). */
function lcsLen(a, b) {
  if (!a.length || !b.length) return 0;
  const prev = new Array(b.length + 1).fill(0);
  const cur = new Array(b.length + 1).fill(0);
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      cur[j] = a[i - 1] === b[j - 1] ? prev[j - 1] + 1 : Math.max(prev[j], cur[j - 1]);
    }
    for (let j = 1; j <= b.length; j++) prev[j] = cur[j];
  }
  return prev[b.length];
}

/** Concordância 0..1 entre as palavras de fala de duas legendas (via LCS). */
function consensusRatio(candCues, refCues, cap) {
  const candWords = candCues
    .filter((c) => !String(c.text).trim().startsWith('['))
    .flatMap((c) => normWords(c.text))
    .slice(0, cap);
  const refWords = refCues.flatMap((c) => normWords(c.text)).slice(0, cap);
  if (!candWords.length || !refWords.length) return { ratio: null, candWords: candWords.length, refWords: refWords.length };
  const l = lcsLen(candWords, refWords);
  // Normaliza pela média dos tamanhos (penaliza tanto faltar quanto sobrar palavra).
  const ratio = l / ((candWords.length + refWords.length) / 2);
  return { ratio: Math.max(0, Math.min(1, ratio)), candWords: candWords.length, refWords: refWords.length };
}

async function readCues(videoId, lang) {
  const r = await s3.send(new GetObjectCommand({ Bucket: MEDIA_BUCKET, Key: keys.subtitle(videoId, lang) }));
  const txt = await r.Body.transformToString('utf-8');
  return parseVtt(txt).cues;
}

function toLines(cues, max) {
  return cues.slice(0, max).map((c) => `[${mmss(c.start)}] ${c.text}`).join('\n');
}

/** Extrai o primeiro objeto JSON de um texto (tolerante a cercas ```json). */
function extractJson(text) {
  const i = text.indexOf('{');
  const j = text.lastIndexOf('}');
  if (i < 0 || j <= i) return null;
  try {
    return JSON.parse(text.slice(i, j + 1));
  } catch (_) {
    return null;
  }
}

/**
 * Executa a avaliação de uma variante e grava em sdhVariants.<method>.eval.
 * Reutilizável pela rota HTTP e pelo worker (auto-avaliação após o SDH).
 * @returns {object} o eval gravado.
 */
async function evaluate(videoId, method) {
  const spec = METHOD_LANG[method];
  if (!spec) throw new Error(`Método inválido para avaliação: ${method}`);

  const video = await getVideo(videoId);
  if (!video) throw new Error('Vídeo não encontrado');

  const cfg = await getSettings();
  const model = reqSetting(cfg, 'model.analysis');
  const maxCues = cfg['eval.maxCues'] ?? 150;
  const wC = cfg['eval.weightConsensus'] ?? 0.4;
  const wJ = cfg['eval.weightJudge'] ?? 0.6;
  const prompt = cfg['eval.prompt'] || DEFAULT_EVAL_PROMPT;
  const IN = cfg['cost.analysisInputPer1k'] || 0;
  const OUT = cfg['cost.analysisOutputPer1k'] || 0;
  const wordCap = cfg['eval.consensusWordCap'] ?? 4000;

  // Candidata (variante) é obrigatória; referência (Transcribe) é desejável.
  let candCues;
  try {
    candCues = await readCues(videoId, spec);
  } catch (e) {
    throw new Error(`Legenda da variante "${method}" (${spec}) não encontrada — gere-a antes de avaliar.`);
  }
  let refCues = null;
  try {
    refCues = await readCues(videoId, REFERENCE_LANG);
  } catch (_) {
    refCues = null; // sem Transcribe: consenso é pulado, segue só com o juiz
  }

  const methods = [];

  // ---- Método 1: consenso (LCS) ----
  let consensusPct = null;
  let consensusInfo = null;
  if (refCues) {
    const c = consensusRatio(candCues, refCues, wordCap);
    if (c.ratio != null) {
      consensusPct = Math.round(c.ratio * 100);
      consensusInfo = c;
      methods.push('consenso');
    }
  }

  // ---- Método 2: LLM-juiz ----
  let llmScore = null;
  let comment = '';
  let flags = [];
  let judgeUSD = 0;
  let judgeTokens = { input: 0, output: 0 };
  const truncated = candCues.length > maxCues || (refCues && refCues.length > maxCues);
  const userText =
    `LEGENDA CANDIDATA (faixa ${spec}, avaliada):\n${toLines(candCues, maxCues)}\n\n` +
    (refCues ? `LEGENDA REFERÊNCIA (Transcribe, faixa ${REFERENCE_LANG}):\n${toLines(refCues, maxCues)}\n\n` : '(Sem legenda de referência; avalie a candidata pela plausibilidade do texto.)\n\n') +
    (truncated ? `(Observação: analisando apenas os primeiros ${maxCues} trechos de cada faixa.)\n\n` : '') +
    prompt;

  try {
    const res = await bedrock.send(
      new ConverseCommand({
        modelId: model,
        messages: [{ role: 'user', content: [{ text: userText }] }],
        inferenceConfig: { maxTokens: 1200, temperature: 0 },
      })
    );
    const text = res.output?.message?.content?.map((c) => c.text).join('') || '';
    const u = res.usage || {};
    judgeTokens = { input: u.inputTokens || 0, output: u.outputTokens || 0 };
    judgeUSD = +((judgeTokens.input / 1000) * IN + (judgeTokens.output / 1000) * OUT).toFixed(4);
    const parsed = extractJson(text);
    if (parsed) {
      llmScore = Math.max(0, Math.min(100, Math.round(Number(parsed.score))));
      comment = String(parsed.comment || '').slice(0, 500);
      flags = Array.isArray(parsed.flags)
        ? parsed.flags.slice(0, 8).map((f) => ({ time: String(f.time || ''), issue: String(f.issue || '').slice(0, 160) }))
        : [];
    } else {
      comment = text.slice(0, 500); // fallback: não parseou JSON → guarda o texto
    }
    if (llmScore != null) methods.push('llm-juiz');
  } catch (e) {
    console.error('LLM-juiz falhou', e);
    comment = `Juiz indisponível: ${String(e.message || e).slice(0, 180)}`;
  }

  // ---- Nota final (reescala pesos pelos métodos disponíveis) ----
  let textConfidence = null;
  const parts = [];
  if (consensusPct != null) parts.push({ v: consensusPct, w: wC });
  if (llmScore != null) parts.push({ v: llmScore, w: wJ });
  if (parts.length) {
    const wsum = parts.reduce((a, p) => a + p.w, 0) || 1;
    textConfidence = Math.round(parts.reduce((a, p) => a + p.v * p.w, 0) / wsum);
  }

  // ---- Custos individualizados ----
  const variant = (video.sdhVariants || {})[method] || {};
  const costs = {
    transcribeUSD: refCues ? (video.cost?.transcribeUSD ?? null) : null,
    voxtralUSD: variant.usd ?? null,
    judgeUSD,
  };

  const evalResult = {
    textConfidence,
    consensusPct,
    llmScore,
    comment,
    flags,
    methods,
    costs,
    model,
    judgeTokens,
    consensusWords: consensusInfo ? { candidate: consensusInfo.candWords, reference: consensusInfo.refWords } : null,
    truncated: !!truncated,
    generatedAt: nowIso(),
  };

  await patchVariant(videoId, method, { eval: evalResult });
  return evalResult;
}

/** POST /api/videos/{videoId}/evaluate-subtitle  { method } */
async function create(event) {
  const videoId = pathParam(event, 'videoId');
  const method = (parseBody(event) || {}).method || 'v24b1p';
  if (!METHOD_LANG[method]) return badRequest(`Método inválido: ${method}`);
  try {
    const result = await evaluate(videoId, method);
    return ok({ videoId, method, eval: result });
  } catch (e) {
    if (/não encontrad/i.test(e.message)) return notFound(e.message);
    console.error('Falha na avaliação', method, e);
    return serverError(`Falha ao avaliar legenda (${method}): ${e.message}`);
  }
}

module.exports = { create, evaluate };
