'use strict';

/**
 * "Wizard" de comparação de legendas. Lê DUAS faixas (langA, langB) do mesmo
 * vídeo e pede a um LLM (model.analysis) uma análise comparativa em pt-BR:
 * diferenças, qual versão parece correta e um veredito. Síncrono (entrada
 * limitada a analysis.maxCues trechos por faixa para caber no tempo da API).
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
} = require('../../lib/common');
const { parseVtt } = require('../../lib/vtt');
const { ok, badRequest, notFound, serverError, parseBody, pathParam } = require('../http');

const s3 = new S3Client({ region: REGION });
const bedrock = new BedrockRuntimeClient({ region: REGION });

const DEFAULT_PROMPT = `Você é um especialista em legendagem em português do Brasil. Vou te dar DUAS legendas do MESMO vídeo (A e B), com marcação de tempo. Compare-as e produza uma análise objetiva, em português, em tópicos:
1) Principais DIFERENÇAS (transcrição da fala, pontuação, onomatopeias, marcadores de som como [música]/[risos], sincronismo). Dê 3 a 6 exemplos citando o tempo.
2) Em cada exemplo, diga qual versão parece CORRETA e por quê.
3) VEREDITO: qual legenda é melhor no geral e o que faltaria para ficar ideal.
Seja conciso.`;

function mmss(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

async function readCues(videoId, lang) {
  const r = await s3.send(
    new GetObjectCommand({ Bucket: MEDIA_BUCKET, Key: keys.subtitle(videoId, lang) })
  );
  const txt = await r.Body.transformToString('utf-8');
  return parseVtt(txt).cues;
}

function toLines(cues, max) {
  return cues
    .slice(0, max)
    .map((c) => `[${mmss(c.start)}] ${c.text}`)
    .join('\n');
}

/** POST /api/videos/{videoId}/compare-subtitles  { langA, langB, labelA?, labelB? } */
async function create(event) {
  const videoId = pathParam(event, 'videoId');
  const body = parseBody(event) || {};
  const { langA, langB } = body;
  if (!langA || !langB || langA === langB) {
    return badRequest('Selecione duas faixas DIFERENTES para comparar.');
  }

  const video = await getVideo(videoId);
  if (!video) return notFound('Vídeo não encontrado');

  const cfg = await getSettings();
  const model = reqSetting(cfg, 'model.analysis');
  const maxCues = cfg['analysis.maxCues'] ?? 150;
  const prompt = cfg['analysis.prompt'] || DEFAULT_PROMPT;
  const IN = cfg['cost.analysisInputPer1k'] || 0;
  const OUT = cfg['cost.analysisOutputPer1k'] || 0;

  let a;
  let b;
  try {
    a = await readCues(videoId, langA);
  } catch (e) {
    return notFound(`Legenda "${langA}" não encontrada`);
  }
  try {
    b = await readCues(videoId, langB);
  } catch (e) {
    return notFound(`Legenda "${langB}" não encontrada`);
  }

  const labelA = body.labelA || langA;
  const labelB = body.labelB || langB;
  const truncated = a.length > maxCues || b.length > maxCues;
  const userText =
    `LEGENDA A = "${labelA}" (faixa ${langA}):\n${toLines(a, maxCues)}\n\n` +
    `LEGENDA B = "${labelB}" (faixa ${langB}):\n${toLines(b, maxCues)}\n\n` +
    (truncated ? `(Observação: analisando apenas os primeiros ${maxCues} trechos de cada faixa.)\n\n` : '') +
    prompt;

  try {
    const res = await bedrock.send(
      new ConverseCommand({
        modelId: model,
        messages: [{ role: 'user', content: [{ text: userText }] }],
        inferenceConfig: { maxTokens: 1500, temperature: 0.2 },
      })
    );
    const text = res.output?.message?.content?.map((c) => c.text).join('') || '';
    const u = res.usage || {};
    const usd = +(((u.inputTokens || 0) / 1000) * IN + ((u.outputTokens || 0) / 1000) * OUT).toFixed(4);
    return ok({
      videoId,
      langA,
      langB,
      model,
      truncated,
      analysis: text,
      tokens: { input: u.inputTokens || 0, output: u.outputTokens || 0 },
      usd,
    });
  } catch (e) {
    console.error('Falha na análise comparativa', e);
    return serverError(`Falha na análise: ${e.message}`);
  }
}

module.exports = { create };
