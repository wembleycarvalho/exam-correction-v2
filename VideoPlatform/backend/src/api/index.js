'use strict';

/**
 * Roteador único da API (API Gateway HTTP API, payload v2). Despacha por
 * routeKey. Todas as rotas são protegidas pelo JWT authorizer do Cognito.
 */

const uploads = require('./routes/uploads');
const videos = require('./routes/videos');
const subtitles = require('./routes/subtitles');
const translate = require('./routes/translate');
const compare = require('./routes/compare');
const evaluate = require('./routes/evaluate');
const describe = require('./routes/describe');
const progress = require('./routes/progress');
const jobs = require('./routes/jobs');
const settings = require('./routes/settings');
const play = require('./routes/play');
const analytics = require('./routes/analytics');
const { notFound, serverError } = require('./http');

const ROUTES = {
  'POST /api/uploads': uploads.create,
  'POST /api/uploads/{videoId}/part-url': uploads.partUrl,
  'POST /api/uploads/{videoId}/complete': uploads.complete,
  'POST /api/uploads/{videoId}/abort': uploads.abort,

  'GET /api/videos': videos.list,
  'GET /api/videos/{videoId}': videos.get,
  'GET /api/videos/{videoId}/progress': progress.get,
  'PATCH /api/videos/{videoId}': videos.update,
  'POST /api/videos/{videoId}/publish': videos.publish,
  'POST /api/videos/{videoId}/unpublish': videos.unpublish,
  'DELETE /api/videos/{videoId}': videos.remove,

  'GET /api/videos/{videoId}/subtitle': subtitles.get,
  'PUT /api/videos/{videoId}/subtitle': subtitles.put,

  'POST /api/videos/{videoId}/translate': translate.create,
  'POST /api/videos/{videoId}/compare-subtitles': compare.create,
  'POST /api/videos/{videoId}/evaluate-subtitle': evaluate.create,
  'POST /api/videos/{videoId}/sdh': jobs.startSdh,
  'POST /api/videos/{videoId}/describe': jobs.startDescribe,
  'GET /api/videos/{videoId}/description': describe.get,

  'POST /api/videos/{videoId}/play': play.authorize,

  'GET /api/analytics': analytics.get,

  'GET /api/settings': settings.list,
  'PUT /api/settings': settings.update,
};

exports.handler = async (event) => {
  const routeKey = event.routeKey || `${event.requestContext?.http?.method} ${event.rawPath}`;
  const fn = ROUTES[routeKey];
  console.log('API', routeKey);

  if (!fn) return notFound(`Rota não encontrada: ${routeKey}`);

  try {
    return await fn(event);
  } catch (err) {
    console.error('Erro na rota', routeKey, err);
    return serverError(err.message || 'Erro interno');
  }
};
