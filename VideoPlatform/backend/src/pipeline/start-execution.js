'use strict';

/**
 * Gatilho S3 (ObjectCreated em raw-videos/). Inicia a execução da Step Functions
 * para processar o vídeo recém-enviado.
 */

const { SFNClient, StartExecutionCommand } = require('@aws-sdk/client-sfn');
const { REGION, RAW_PREFIX, updateVideo, STATUS, nowIso } = require('../lib/common');

const sfn = new SFNClient({ region: REGION });
const STATE_MACHINE_ARN = process.env.STATE_MACHINE_ARN;

function parseKey(rawKey) {
  const key = decodeURIComponent(rawKey.replace(/\+/g, ' '));
  // raw-videos/{videoId}/source.ext
  const parts = key.split('/');
  if (parts.length < 3 || parts[0] !== RAW_PREFIX) return null;
  const videoId = parts[1];
  const ext = key.includes('.') ? key.slice(key.lastIndexOf('.')) : '.mp4';
  return { key, videoId, ext };
}

exports.handler = async (event) => {
  for (const record of event.Records || []) {
    const rawKey = record.s3?.object?.key;
    if (!rawKey) continue;
    const parsed = parseKey(rawKey);
    if (!parsed) {
      console.warn('Chave fora do padrão esperado, ignorando:', rawKey);
      continue;
    }
    const { key, videoId, ext } = parsed;
    console.log('Iniciando pipeline', { videoId, key });

    // Transição oficial "enviando" -> "processando": só aqui, quando a
    // pipeline realmente inicia (o upload cria o registro como "enviando").
    try {
      await updateVideo(videoId, {
        status: STATUS.PROCESSING,
        sourceKey: key,
        sourceExt: ext,
        pipelineStartedAt: nowIso(), // marca início p/ medir o tempo da pipeline
      });
    } catch (e) {
      console.warn('Falha ao atualizar status inicial (seguindo):', e.message);
    }

    await sfn.send(
      new StartExecutionCommand({
        stateMachineArn: STATE_MACHINE_ARN,
        name: `${videoId}-${Date.now()}`.slice(0, 80),
        input: JSON.stringify({ videoId, sourceKey: key, sourceExt: ext }),
      })
    );
  }
  return { ok: true };
};
