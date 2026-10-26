'use strict';

/**
 * Legendas: lê o VTT (para o editor de sincronismo) e grava o VTT ajustado.
 * O ajuste fino (offset global ou por cue) é feito no frontend, que envia o VTT
 * final; aqui apenas persistimos e registramos o offset aplicado.
 */

const { S3Client, GetObjectCommand, PutObjectCommand } = require('@aws-sdk/client-s3');
const { REGION, MEDIA_BUCKET, keys, getVideo, updateVideo } = require('../../lib/common');
const { ok, badRequest, notFound, parseBody, pathParam, queryParam } = require('../http');

const s3 = new S3Client({ region: REGION });

/** GET /api/videos/{videoId}/subtitle?lang=pt */
async function get(event) {
  const videoId = pathParam(event, 'videoId');
  const lang = queryParam(event, 'lang') || 'pt';
  const key = keys.subtitle(videoId, lang);
  try {
    const r = await s3.send(new GetObjectCommand({ Bucket: MEDIA_BUCKET, Key: key }));
    const content = await r.Body.transformToString('utf-8');
    return ok({ lang, content });
  } catch (e) {
    if (e.name === 'NoSuchKey' || e.$metadata?.httpStatusCode === 404) {
      return notFound('Legenda não encontrada para este idioma');
    }
    throw e;
  }
}

/** PUT /api/videos/{videoId}/subtitle  { lang, content, offsetSec } */
async function put(event) {
  const videoId = pathParam(event, 'videoId');
  const body = parseBody(event);
  const lang = body.lang || 'pt';
  const content = body.content;
  if (typeof content !== 'string' || !content.includes('WEBVTT')) {
    return badRequest('content deve ser um WebVTT válido');
  }

  const video = await getVideo(videoId);
  if (!video) return notFound('Vídeo não encontrado');

  const key = keys.subtitle(videoId, lang);
  await s3.send(
    new PutObjectCommand({
      Bucket: MEDIA_BUCKET,
      Key: key,
      Body: content,
      ContentType: 'text/vtt',
    })
  );

  // Atualiza o metadado de legendas (idioma + offset aplicado).
  const subtitles = Array.isArray(video.subtitles) ? [...video.subtitles] : [];
  const idx = subtitles.findIndex((s) => s.lang === lang);
  const entry = { lang, key, offsetSec: Number(body.offsetSec) || 0 };
  if (idx >= 0) subtitles[idx] = entry;
  else subtitles.push(entry);

  await updateVideo(videoId, { subtitles });
  return ok({ videoId, lang, offsetSec: entry.offsetSec });
}

module.exports = { get, put };
