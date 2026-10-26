'use strict';

/**
 * Descrição de vídeo por IA (TwelveLabs Pegasus — modelo de VÍDEO no Bedrock).
 * Invocado via InvokeModel (não é Converse). O vídeo é lido direto do S3.
 * Produz segmentos cronológicos [{start,end,text}] (cena + ação + áudio) salvos
 * em description.json, exibidos sincronizados com o play. Custo em cost.descriptionUSD.
 */

const { S3Client, GetObjectCommand, PutObjectCommand } = require('@aws-sdk/client-s3');
const { BedrockRuntimeClient, InvokeModelCommand } = require('@aws-sdk/client-bedrock-runtime');
const { REGION, MEDIA_BUCKET, keys, getVideo, updateVideo, recomputeCostTotal, getSettings, reqSetting } = require('../../lib/common');
const { ok, notFound, serverError, parseBody, pathParam } = require('../http');

const s3 = new S3Client({ region: REGION });
const bedrock = new BedrockRuntimeClient({ region: REGION });

const ACCOUNT_ID = process.env.ACCOUNT_ID; // identidade (infra), não é config

// Formato de LINHA (não JSON): evita quebra de parsing com aspas/apóstrofos no
// texto em português (o Pegasus frequentemente gera JSON malformado nesses casos).
const PROMPT =
  'Descreva este vídeo em português do Brasil em segmentos cronológicos, cobrindo ' +
  'cena, ação e também o áudio (fala, música, sons). UMA LINHA por segmento, no ' +
  'formato: [INICIO-FIM] descrição — com INICIO e FIM em segundos inteiros. Exemplo:\n' +
  '[0-10] Abertura com o título sobre fundo azul; música animada.\n' +
  '[10-22] Personagem olha pela janela durante a chuva.\n' +
  'Não use JSON, não numere. Responda apenas as linhas.';

/** Parser tolerante: tenta o formato de linha "[ini-fim] texto"; se vazio, JSON. */
function parseSegments(text) {
  const out = [];
  for (const line of String(text).split('\n')) {
    const m = /^\s*\[\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*\]\s*(.+?)\s*$/.exec(line);
    if (m) out.push({ start: +m[1], end: +m[2], text: m[3].trim() });
  }
  if (out.length) return out;
  // Fallback: tenta JSON (caso o modelo ignore o formato de linha).
  const a = String(text).indexOf('[');
  const b = String(text).lastIndexOf(']');
  if (a >= 0 && b > a) {
    try {
      const arr = JSON.parse(text.slice(a, b + 1));
      return (Array.isArray(arr) ? arr : [])
        .filter((s) => typeof s.start === 'number' && typeof s.end === 'number' && s.text)
        .map((s) => ({ start: s.start, end: s.end, text: String(s.text) }));
    } catch (_) {
      /* ignora */
    }
  }
  return out;
}

/** POST /api/videos/{videoId}/describe */
async function create(event) {
  const videoId = pathParam(event, 'videoId');
  const video = await getVideo(videoId);
  if (!video) return notFound('Vídeo não encontrado');
  if (!video.sourceKey) return notFound('Fonte de vídeo não encontrada');

  const cfg = await getSettings();
  const MODEL = reqSetting(cfg, 'model.pegasus');
  const RATE_PER_MIN = cfg['cost.pegasusPerMin'] || 0;

  const uri = `s3://${MEDIA_BUCKET}/${video.sourceKey}`;
  const reqBody = {
    inputPrompt: PROMPT,
    mediaSource: { s3Location: { uri, bucketOwner: ACCOUNT_ID } },
  };

  // Pegasus é não-determinístico; às vezes não devolve o JSON. Tenta até 2x.
  let segments = [];
  let lastMessage = '';
  try {
    for (let attempt = 0; attempt < 2 && segments.length === 0; attempt++) {
      const res = await bedrock.send(
        new InvokeModelCommand({
          modelId: MODEL,
          contentType: 'application/json',
          accept: 'application/json',
          body: JSON.stringify(reqBody),
        })
      );
      const decoded = JSON.parse(new TextDecoder().decode(res.body));
      lastMessage = decoded.message || '';
      segments = parseSegments(lastMessage);
    }
  } catch (e) {
    console.error('Falha Pegasus', e);
    return serverError(`Falha ao gerar descrição: ${e.message}`);
  }

  // Sem segmentos utilizáveis: NÃO marca pronto e NÃO cobra (o worker seta "erro").
  if (segments.length === 0) {
    console.warn('Pegasus sem segmentos. message(início):', lastMessage.slice(0, 400));
    return serverError('O modelo não retornou segmentos de descrição utilizáveis. Tente novamente.');
  }

  const payload = { videoId, model: MODEL, generatedAt: new Date().toISOString(), segments };
  const descKey = keys.description(videoId);
  await s3.send(
    new PutObjectCommand({
      Bucket: MEDIA_BUCKET,
      Key: descKey,
      Body: JSON.stringify(payload),
      ContentType: 'application/json',
    })
  );

  // Custo estimado por duração (Pegasus não retorna tokens no corpo).
  // SUBSTITUI o custo anterior (a descrição é regerada por completo).
  const minutes = (video.durationSec || 0) / 60;
  const cost = { ...(video.cost || {}) };
  cost.descriptionUSD = +(minutes * RATE_PER_MIN).toFixed(4);
  cost.totalUSD = recomputeCostTotal(cost);
  await updateVideo(videoId, { cost, hasDescription: true });

  return ok({ videoId, segments: segments.length, descriptionUSD: cost.descriptionUSD });
}

/** GET /api/videos/{videoId}/description */
async function get(event) {
  const videoId = pathParam(event, 'videoId');
  try {
    const r = await s3.send(new GetObjectCommand({ Bucket: MEDIA_BUCKET, Key: keys.description(videoId) }));
    const text = await r.Body.transformToString('utf-8');
    return ok(JSON.parse(text));
  } catch (e) {
    return notFound('Descrição não gerada para este vídeo');
  }
}

module.exports = { create, get };
