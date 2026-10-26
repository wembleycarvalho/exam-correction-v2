'use strict';

/**
 * Catch da Step Functions: marca o vídeo como "erro" e registra o motivo.
 */

const { STATUS, updateVideo } = require('../lib/common');

exports.handler = async (event) => {
  const videoId = event.videoId;
  const err = event.error || {};
  let reason = 'Falha no processamento';
  try {
    // O Catch injeta { Error, Cause } em $.error
    reason = err.Cause ? JSON.parse(err.Cause).errorMessage || err.Cause : err.Error || reason;
  } catch (_) {
    reason = err.Cause || err.Error || reason;
  }
  console.error('Pipeline falhou', { videoId, reason });

  if (videoId) {
    await updateVideo(videoId, { status: STATUS.ERROR, errorReason: String(reason).slice(0, 1024) });
  }
  return { videoId, status: STATUS.ERROR };
};
