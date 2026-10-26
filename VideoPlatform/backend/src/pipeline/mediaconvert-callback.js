'use strict';

/**
 * Acionado pelo EventBridge em "MediaConvert Job State Change".
 * Lê o task token guardado no vídeo e retoma a Step Functions (sucesso/falha).
 */

const { SFNClient, SendTaskSuccessCommand, SendTaskFailureCommand } = require('@aws-sdk/client-sfn');
const { REGION, keys, getVideo } = require('../lib/common');

const sfn = new SFNClient({ region: REGION });

function extractDurationSec(detail) {
  try {
    const groups = detail.outputGroupDetails || [];
    for (const g of groups) {
      for (const o of g.outputDetails || []) {
        if (o.durationInMs) return Math.round(o.durationInMs / 1000);
      }
    }
  } catch (_) {}
  return 0;
}

exports.handler = async (event) => {
  const detail = event.detail || {};
  const status = detail.status; // COMPLETE | ERROR | CANCELED
  const videoId = detail.userMetadata?.videoId;
  console.log('MediaConvert callback', { status, videoId, jobId: detail.jobId });

  if (!videoId) {
    console.warn('Evento sem videoId em userMetadata, ignorando.');
    return;
  }

  const video = await getVideo(videoId);
  const token = video?.mcTaskToken;
  if (!token) {
    console.warn('Sem task token para', videoId, '(execução já retomada?)');
    return;
  }

  if (status === 'COMPLETE') {
    const durationSec = extractDurationSec(detail);
    await sfn.send(
      new SendTaskSuccessCommand({
        taskToken: token,
        output: JSON.stringify({
          mediaConvert: { hlsKey: keys.hlsMaster(videoId), durationSec },
        }),
      })
    );
  } else {
    await sfn.send(
      new SendTaskFailureCommand({
        taskToken: token,
        error: 'MediaConvertFailed',
        cause: detail.errorMessage || `Status ${status}`,
      })
    );
  }
};
