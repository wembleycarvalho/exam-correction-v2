'use strict';

/** Helpers para respostas do API Gateway HTTP API (payload format 2.0). */

function json(statusCode, body, extra = {}) {
  return {
    statusCode,
    headers: { 'content-type': 'application/json', ...(extra.headers || {}) },
    body: JSON.stringify(body),
    ...(extra.cookies ? { cookies: extra.cookies } : {}),
  };
}

const ok = (body, extra) => json(200, body, extra);
const created = (body) => json(201, body);
const badRequest = (msg) => json(400, { error: msg });
const notFound = (msg = 'Não encontrado') => json(404, { error: msg });
const forbidden = (msg = 'Proibido') => json(403, { error: msg });
const serverError = (msg = 'Erro interno') => json(500, { error: msg });

function parseBody(event) {
  if (!event.body) return {};
  const raw = event.isBase64Encoded ? Buffer.from(event.body, 'base64').toString('utf8') : event.body;
  try {
    return JSON.parse(raw);
  } catch (_) {
    return {};
  }
}

/** Sub (id) do usuário autenticado via JWT do Cognito. */
function userSub(event) {
  return event.requestContext?.authorizer?.jwt?.claims?.sub || 'anon';
}

function pathParam(event, name) {
  return event.pathParameters?.[name];
}

function queryParam(event, name) {
  return event.queryStringParameters?.[name];
}

module.exports = {
  json,
  ok,
  created,
  badRequest,
  notFound,
  forbidden,
  serverError,
  parseBody,
  userSub,
  pathParam,
  queryParam,
};
