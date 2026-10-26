'use strict';

/**
 * Última task da pipeline (sucesso): consolida resultados do MediaConvert e do
 * Transcribe, calcula o custo estimado e move o vídeo para status "revisar".
 */

const { LambdaClient, InvokeCommand } = require('@aws-sdk/client-lambda');
const { STATUS, keys, updateVideo, getVideo, estimateCost, getSettings } = require('../lib/common');

const lambda = new LambdaClient({ region: process.env.AWS_REGION });

exports.handler = async (event) => {
  const videoId = event.videoId;
  const results = event.results || [];
  console.log('Finalizando', { videoId });

  // Tempo total da pipeline (transcode + Transcribe em paralelo + finalize).
  const video = await getVideo(videoId);
  const startedAt = video?.pipelineStartedAt ? Date.parse(video.pipelineStartedAt) : null;
  const pipelineMs = startedAt ? Date.now() - startedAt : undefined;

  // Os resultados vêm das duas branches do Parallel (ordem não garantida).
  let hlsKey = keys.hlsMaster(videoId);
  let durationSec = 0;
  let subtitleKey = keys.subtitle(videoId, 'pt');

  for (const r of results) {
    if (r?.mediaConvert) {
      hlsKey = r.mediaConvert.hlsKey || hlsKey;
      durationSec = r.mediaConvert.durationSec || durationSec;
    }
    if (r?.transcribe) {
      subtitleKey = r.transcribe.subtitleKey || subtitleKey;
    }
  }

  const cfg = await getSettings();
  const renditions = cfg['transcode.renditions'] || [];
  const cost = estimateCost({
    durationSec,
    renditions,
    rates: {
      mcSd: cfg['cost.mcSdPerMin'] || 0,
      mcHd: cfg['cost.mcHdPerMin'] || 0,
      mcUhd: cfg['cost.mcUhdPerMin'] || 0,
      trPerMin: cfg['cost.transcribePerAudioMin'] || 0,
      sfnPerTransition: cfg['cost.sfnPerTransition'] || 0,
      sfnTransitions: cfg['cost.estSfnTransitions'] || 0,
      pipelineLambdaGbSec: cfg['cost.estPipelineLambdaGbSec'] || 0,
      lambdaPerGbSecond: cfg['cost.lambdaPerGbSecond'] || 0,
    },
  });

  await updateVideo(videoId, {
    status: STATUS.REVIEW,
    hlsKey,
    durationSec,
    pipelineMs,
    cost,
    subtitles: [{ lang: 'pt', key: subtitleKey, offsetSec: 0 }],
  });

  // Opcional: gerar a legenda SDH (Voxtral) + avaliação automaticamente ao final
  // do pipeline. Desligado por padrão (pipeline.autoSdhMethod vazio) para não
  // adicionar custo de Voxtral a todo upload sem decisão explícita.
  const autoMethod = (cfg['pipeline.autoSdhMethod'] || '').trim();
  const worker = process.env.AI_WORKER_FN;
  if (autoMethod && worker) {
    try {
      await lambda.send(
        new InvokeCommand({
          FunctionName: worker,
          InvocationType: 'Event', // assíncrono: o worker gera SDH e depois avalia
          Payload: Buffer.from(JSON.stringify({ task: 'sdh', videoId, method: autoMethod })),
        })
      );
      console.log('Auto-SDH disparado', { videoId, method: autoMethod });
    } catch (e) {
      console.error('Falha ao disparar auto-SDH (não bloqueia o finalize)', e);
    }
  }

  return { videoId, status: STATUS.REVIEW };
};
