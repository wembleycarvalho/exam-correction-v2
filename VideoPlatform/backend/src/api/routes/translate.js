'use strict';

/**
 * Tradução de legenda sob demanda (seção "Idiomas" da revisão).
 * Lê o VTT pt-BR, traduz os textos dos cues (preservando timestamps) via Amazon
 * Translate, grava {videoId}.{lang}.vtt e atualiza metadados + custo.
 */

const { S3Client, GetObjectCommand, PutObjectCommand } = require('@aws-sdk/client-s3');
const { TranslateClient, TranslateTextCommand } = require('@aws-sdk/client-translate');
const { REGION, MEDIA_BUCKET, keys, getVideo, updateVideo, recomputeCostTotal, getSettings } = require('../../lib/common');
const { parseVtt, serializeVtt } = require('../../lib/vtt');
const { ok, badRequest, notFound, parseBody, pathParam } = require('../http');

const s3 = new S3Client({ region: REGION });
const translate = new TranslateClient({ region: REGION });

const SOURCE_LANG = 'pt'; // faixa de origem (estrutural)

async function translateText(text, target) {
  if (!text || !text.trim()) return text;
  const r = await translate.send(
    new TranslateTextCommand({
      Text: text,
      SourceLanguageCode: SOURCE_LANG,
      TargetLanguageCode: target,
    })
  );
  return r.TranslatedText ?? text;
}

/** Traduz cues com concorrência limitada. */
async function translateCues(cues, target) {
  const out = new Array(cues.length);
  let chars = 0;
  const CONCURRENCY = 5;
  for (let i = 0; i < cues.length; i += CONCURRENCY) {
    const slice = cues.slice(i, i + CONCURRENCY);
    const results = await Promise.all(
      slice.map(async (c) => {
        chars += (c.text || '').length;
        const text = await translateText(c.text, target);
        return { ...c, text };
      })
    );
    results.forEach((c, j) => (out[i + j] = c));
  }
  return { cues: out, chars };
}

/**
 * POST /api/videos/{videoId}/translate  { targetLang, sourceLang? }
 * sourceLang: faixa de origem (qualquer legenda em português: pt, pt-sdh,
 * pt-sdh-mini, pt-sdh-2p). O destino preserva a variante trocando o prefixo
 * "pt" pelo idioma alvo (ex.: pt-sdh -> es-sdh).
 */
async function create(event) {
  const videoId = pathParam(event, 'videoId');
  const body = parseBody(event);
  const cfg = await getSettings();
  const SUPPORTED = new Set(cfg['lang.translations'] || []);
  const TRANSLATE_RATE = cfg['cost.translatePerChar'] || 0;
  const target = (body.targetLang || '').toLowerCase();
  if (!SUPPORTED.has(target)) {
    return badRequest(`Idioma não suportado. Use: ${[...SUPPORTED].join(', ')}`);
  }

  // Origem: qualquer faixa em português (padrão: pt/Transcribe).
  const sourceLang = (body.sourceLang || SOURCE_LANG).toLowerCase();
  if (!/^pt(-|$)/.test(sourceLang)) {
    return badRequest('A legenda de origem precisa ser em português (pt, pt-sdh, ...).');
  }
  // Destino preserva a variante: pt -> target; pt-sdh -> target-sdh; etc.
  const outLang = target + sourceLang.replace(/^pt/, '');

  const video = await getVideo(videoId);
  if (!video) return notFound('Vídeo não encontrado');

  // Lê a legenda de origem escolhida.
  const srcKey = keys.subtitle(videoId, sourceLang);
  let srcContent;
  try {
    const r = await s3.send(new GetObjectCommand({ Bucket: MEDIA_BUCKET, Key: srcKey }));
    srcContent = await r.Body.transformToString('utf-8');
  } catch (e) {
    return notFound(`Legenda de origem "${sourceLang}" não encontrada`);
  }

  const parsed = parseVtt(srcContent);
  const { cues, chars } = await translateCues(parsed.cues, target);
  const outVtt = serializeVtt({ header: parsed.header, cues });

  const destKey = keys.subtitle(videoId, outLang);
  await s3.send(
    new PutObjectCommand({
      Bucket: MEDIA_BUCKET,
      Key: destKey,
      Body: outVtt,
      ContentType: 'text/vtt',
    })
  );

  // Atualiza metadados de legenda + custo de tradução acumulado.
  const subtitles = Array.isArray(video.subtitles) ? [...video.subtitles] : [];
  const idx = subtitles.findIndex((s) => s.lang === outLang);
  const entry = { lang: outLang, key: destKey, offsetSec: 0, source: `translate:${sourceLang}` };
  if (idx >= 0) subtitles[idx] = entry;
  else subtitles.push(entry);

  const cost = { ...(video.cost || {}) };
  const addTranslate = +(chars * TRANSLATE_RATE).toFixed(4);
  cost.translateUSD = +(((cost.translateUSD || 0) + addTranslate)).toFixed(4);
  cost.totalUSD = recomputeCostTotal(cost);

  await updateVideo(videoId, { subtitles, cost });
  return ok({ videoId, sourceLang, lang: outLang, charsTranslated: chars, subtitles });
}

module.exports = { create };
