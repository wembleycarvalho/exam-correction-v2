'use strict';

/**
 * Analytics: contagem de plays por vídeo e custo estimado de processamento,
 * mais totais agregados. Não é monitoramento de tráfego de rede.
 */

const { VIDEOS_TABLE, ddb, ScanCommand } = require('../../lib/common');
const { ok } = require('../http');

/** GET /api/analytics */
async function get() {
  const r = await ddb.send(new ScanCommand({ TableName: VIDEOS_TABLE }));
  const items = r.Items || [];

  const videos = items
    .map((v) => ({
      videoId: v.videoId,
      title: v.title || '(sem título)',
      status: v.status,
      playCount: v.playCount || 0,
      durationSec: v.durationSec || 0,
      cost: v.cost || null,
    }))
    .sort((a, b) => b.playCount - a.playCount);

  const totals = videos.reduce(
    (acc, v) => {
      acc.totalPlays += v.playCount;
      acc.estimatedCostUSD += v.cost?.totalUSD || 0;
      acc.videoCount += 1;
      return acc;
    },
    { totalPlays: 0, estimatedCostUSD: 0, videoCount: 0 }
  );
  totals.estimatedCostUSD = +totals.estimatedCostUSD.toFixed(4);

  return ok({ videos, totals });
}

module.exports = { get };
