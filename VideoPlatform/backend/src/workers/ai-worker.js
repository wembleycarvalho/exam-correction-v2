'use strict';

/**
 * Worker assíncrono de IA. Executa a tarefa pesada fora do caminho síncrono da
 * API e grava o status final no item do vídeo. Timeout longo (ver infra).
 *
 * Evento:
 *   { task: 'sdh', videoId, method }   → variante de legenda (status em sdhVariants.<method>)
 *   { task: 'describe', videoId }      → descrição do vídeo (status em descriptionStatus)
 */

const sdh = require('../api/routes/sdh');
const describe = require('../api/routes/describe');
const evaluate = require('../api/routes/evaluate');
const { updateVideo, patchVariant, getSettings } = require('../lib/common');

function errMsg(res) {
  try {
    return JSON.parse(res.body).error;
  } catch (_) {
    return 'falha';
  }
}

/** SDH: status/erro ficam em sdhVariants.<method> (sucesso é gravado pelo create). */
async function runSdh(videoId, method) {
  try {
    const res = await sdh.create({ pathParameters: { videoId }, body: JSON.stringify({ method }) });
    if (res && res.statusCode >= 400) throw new Error(errMsg(res));
    // sucesso: sdh.create já gravou status 'pronto' + métricas na variante
    // Avaliação automática da qualidade do texto (consenso + LLM-juiz), se ligada.
    try {
      const cfg = await getSettings();
      if (cfg['eval.autoAfterSdh'] !== false) {
        await evaluate.evaluate(videoId, method);
      }
    } catch (ev) {
      console.error('Auto-avaliação falhou (não bloqueia o SDH)', method, ev);
    }
  } catch (e) {
    console.error('Worker SDH falhou', method, e);
    await patchVariant(videoId, method, {
      status: 'erro',
      error: String(e.message || e).slice(0, 500),
    });
  }
}

/** Descrição: status top-level descriptionStatus. */
async function runDescribe(videoId) {
  try {
    const res = await describe.create({ pathParameters: { videoId }, body: null });
    if (res && res.statusCode >= 400) throw new Error(errMsg(res));
    await updateVideo(videoId, { descriptionStatus: 'pronto' });
  } catch (e) {
    console.error('Worker describe falhou', e);
    await updateVideo(videoId, {
      descriptionStatus: 'erro',
      descriptionError: String(e.message || e).slice(0, 500),
    });
  }
}

/** Marca a tarefa como "erro" por tempo esgotado (antes do Lambda ser morto). */
async function markTimeout(task, videoId, method) {
  const msg =
    'Tempo de processamento esgotado (vídeo longo demais para esta variante no limite do worker). ' +
    'Tente um vídeo menor, a opção de 1 passada, ou aumente a concorrência em Config.';
  try {
    if (task === 'sdh') await patchVariant(videoId, method, { status: 'erro', error: msg });
    else if (task === 'describe')
      await updateVideo(videoId, { descriptionStatus: 'erro', descriptionError: msg });
  } catch (e) {
    console.error('Falha ao marcar timeout', e);
  }
}

exports.handler = async (event, context) => {
  const { task, videoId, method } = event || {};
  if (!videoId) return;
  const m = method || 'v24b1p';

  // Trava de timeout: grava "erro" ~15s antes do Lambda ser morto, para a
  // tarefa NUNCA ficar presa em "processando" se estourar o tempo.
  const remaining =
    (context && typeof context.getRemainingTimeInMillis === 'function'
      ? context.getRemainingTimeInMillis()
      : 900000) - 15000;
  let guardTimer;
  const guard = new Promise((resolve) => {
    guardTimer = setTimeout(async () => {
      await markTimeout(task, videoId, m);
      resolve();
    }, Math.max(5000, remaining));
  });

  const work = (async () => {
    if (task === 'sdh') await runSdh(videoId, m);
    else if (task === 'describe') await runDescribe(videoId);
  })();

  try {
    await Promise.race([work, guard]);
  } finally {
    clearTimeout(guardTimer);
  }
};
