'use strict';

/**
 * Progresso de processamento de um vídeo. Para vídeos em "processando" com job
 * do MediaConvert, consulta o JobPercentComplete (transcode). Leve: o frontend
 * faz polling enquanto o player ainda não está disponível.
 */

const { MediaConvertClient, DescribeEndpointsCommand, GetJobCommand } = require('@aws-sdk/client-mediaconvert');
const { REGION, getVideo } = require('../../lib/common');
const { ok, notFound, pathParam } = require('../http');

let mcClient = null;
async function getMc() {
  if (mcClient) return mcClient;
  const base = new MediaConvertClient({ region: REGION });
  const ep = await base.send(new DescribeEndpointsCommand({}));
  const url = ep.Endpoints?.[0]?.Url;
  mcClient = new MediaConvertClient({ region: REGION, endpoint: url });
  return mcClient;
}

/** GET /api/videos/{videoId}/progress */
async function get(event) {
  const videoId = pathParam(event, 'videoId');
  const v = await getVideo(videoId);
  if (!v) return notFound('Vídeo não encontrado');

  let transcodePercent = null;
  if (v.status === 'processando' && v.mcJobId) {
    try {
      const mc = await getMc();
      const r = await mc.send(new GetJobCommand({ Id: v.mcJobId }));
      transcodePercent = r.Job?.JobPercentComplete ?? null;
    } catch (e) {
      console.warn('Falha ao ler progresso do MediaConvert (seguindo):', e.message);
    }
  }

  return ok({ videoId, status: v.status, transcodePercent });
}

module.exports = { get };
