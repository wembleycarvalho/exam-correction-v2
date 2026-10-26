'use strict';

/**
 * Dispara jobs de IA pesados (SDH/Voxtral e Descrição/Pegasus) de forma
 * ASSÍNCRONA, para não esbarrar no limite de 30s do API Gateway HTTP.
 * Invoca o worker Lambda (Event) e retorna 202 imediatamente; o status fica no
 * item do vídeo e o frontend faz polling.
 *
 * SDH é por VARIANTE (mini1p/v24b1p/v24b2p): cada uma roda como job próprio e
 * grava status/métricas em sdhVariants.<método> (jobs paralelos sem corrida).
 */

const { LambdaClient, InvokeCommand } = require('@aws-sdk/client-lambda');
const { REGION, getVideo, updateVideo, patchVariant } = require('../../lib/common');
const { ok, badRequest, notFound, serverError, pathParam, parseBody } = require('../http');

const lambda = new LambdaClient({ region: REGION });
const WORKER = process.env.AI_WORKER_FN;

async function invokeWorker(payload) {
  await lambda.send(
    new InvokeCommand({
      FunctionName: WORKER,
      InvocationType: 'Event', // assíncrono
      Payload: Buffer.from(JSON.stringify(payload)),
    })
  );
}

/** POST /api/videos/{videoId}/sdh  { method? } */
async function startSdh(event) {
  const videoId = pathParam(event, 'videoId');
  const v = await getVideo(videoId);
  if (!v) return notFound('Vídeo não encontrado');
  if (!WORKER) return serverError('Worker de IA não configurado');

  const method = (parseBody(event) || {}).method || 'v24b1p';
  if (v.sdhVariants?.[method]?.status === 'processando') {
    return badRequest(`A variante "${method}" já está sendo gerada para este vídeo.`);
  }
  await patchVariant(videoId, method, { status: 'processando', error: '' });
  await invokeWorker({ task: 'sdh', videoId, method });
  return ok({ videoId, method, status: 'processando' });
}

/** POST /api/videos/{videoId}/describe */
async function startDescribe(event) {
  const videoId = pathParam(event, 'videoId');
  const v = await getVideo(videoId);
  if (!v) return notFound('Vídeo não encontrado');
  if (!WORKER) return serverError('Worker de IA não configurado');
  if (v.descriptionStatus === 'processando') {
    return badRequest('A descrição já está sendo gerada para este vídeo.');
  }

  await updateVideo(videoId, { descriptionStatus: 'processando' });
  await invokeWorker({ task: 'describe', videoId });
  return ok({ videoId, descriptionStatus: 'processando' });
}

module.exports = { startSdh, startDescribe };
