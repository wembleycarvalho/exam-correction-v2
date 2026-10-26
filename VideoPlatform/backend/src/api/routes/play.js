'use strict';

/**
 * Autorização de reprodução. Só vídeos "pronto" podem tocar. Registra o play
 * (analytics) e emite cookies assinados do CloudFront com escopo e TTL curtos.
 * Como SPA, API e mídia estão no mesmo domínio CloudFront, os cookies são
 * first-party e o player os envia automaticamente nas requisições de mídia.
 */

const { SecretsManagerClient, GetSecretValueCommand } = require('@aws-sdk/client-secrets-manager');
const { getSignedCookies } = require('@aws-sdk/cloudfront-signer');
const { PutCommand } = require('@aws-sdk/lib-dynamodb');
const {
  REGION,
  PROFILES_PREFIX,
  PLAYS_TABLE,
  ddb,
  nowIso,
  getVideo,
  updateVideo,
  getSettings,
  STATUS,
} = require('../../lib/common');
const { ok, forbidden, notFound, parseBody, pathParam, userSub } = require('../http');

const sm = new SecretsManagerClient({ region: REGION });

const CF_DOMAIN = process.env.CF_DOMAIN;
const KEY_PAIR_ID = process.env.SIGNING_PUBLIC_KEY_ID;
const SECRET_ARN = process.env.SIGNING_PRIVATE_KEY_SECRET_ARN;

let cachedPrivateKey = null;
async function getPrivateKey() {
  if (!cachedPrivateKey) {
    const r = await sm.send(new GetSecretValueCommand({ SecretId: SECRET_ARN }));
    cachedPrivateKey = r.SecretString;
  }
  return cachedPrivateKey;
}

function cookieStrings(cookies, videoId, ttl) {
  const path = `/${PROFILES_PREFIX}/${videoId}/`;
  const attrs = `Path=${path}; Secure; HttpOnly; SameSite=Lax; Max-Age=${ttl}`;
  return Object.entries(cookies).map(([k, v]) => `${k}=${v}; ${attrs}`);
}

/** POST /api/videos/{videoId}/play */
async function authorize(event) {
  const videoId = pathParam(event, 'videoId');
  const body = parseBody(event);
  const preview = body?.preview === true; // só a tela de revisão envia preview=true

  const video = await getVideo(videoId);
  if (!video) return notFound('Vídeo não encontrado');

  // Player público: SÓ vídeos "pronto". Preview da revisão: também "revisar".
  const isReady = video.status === STATUS.READY;
  const isReviewPreview = video.status === STATUS.REVIEW && preview;
  if (!isReady && !isReviewPreview) {
    if (video.status === STATUS.REVIEW) {
      return forbidden('Vídeo não publicado (disponível apenas em preview na revisão).');
    }
    return forbidden('Vídeo ainda não está disponível para reprodução.');
  }

  // ---- Analytics: só conta play de vídeo publicado (não conta preview de revisão) ----
  if (isReady) {
    await updateVideo(videoId, {}, { add: { playCount: 1 } });
    try {
      await ddb.send(
        new PutCommand({
          TableName: PLAYS_TABLE,
          Item: { videoId, ts: nowIso(), user: userSub(event) },
        })
      );
    } catch (e) {
      console.warn('Falha ao gravar evento de play (seguindo):', e.message);
    }
  }

  // ---- Cookies assinados (escopo: só este vídeo; TTL vem das settings) ----
  const cfg = await getSettings();
  const TTL = cfg['delivery.signedCookieTtlSec'] || 7200;
  const privateKey = await getPrivateKey();
  const expires = Math.floor(Date.now() / 1000) + TTL;
  const resource = `https://${CF_DOMAIN}/${PROFILES_PREFIX}/${videoId}/*`;
  const policy = JSON.stringify({
    Statement: [{ Resource: resource, Condition: { DateLessThan: { 'AWS:EpochTime': expires } } }],
  });
  const signed = getSignedCookies({ keyPairId: KEY_PAIR_ID, privateKey, policy });

  const base = `https://${CF_DOMAIN}/${PROFILES_PREFIX}/${videoId}`;
  const subtitles = (video.subtitles || []).map((s) => ({
    lang: s.lang,
    offsetSec: s.offsetSec || 0,
    url: `${base}/legenda/${videoId}.${s.lang}.vtt`,
  }));

  return ok(
    {
      videoId,
      title: video.title,
      description: video.description,
      durationSec: video.durationSec || 0,
      hlsUrl: `${base}/hls/master.m3u8`,
      subtitles,
      expiresInSec: TTL,
    },
    { cookies: cookieStrings(signed, videoId, TTL) }
  );
}

module.exports = { authorize };
