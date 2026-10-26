'use strict';

/**
 * Configuração da plataforma (tela de Config). Todos os parâmetros de
 * comportamento ficam na tabela DynamoDB de settings — nada hardcoded.
 * GET  /api/settings  -> lista com metadados (label, descrição, tipo, categoria)
 * PUT  /api/settings  -> atualiza valores { updates: { chave: valor, ... } }
 */

const { SETTINGS_TABLE, ddb, ScanCommand, UpdateCommand, getSettings } = require('../../lib/common');
const { ok, badRequest, parseBody } = require('../http');

async function scanAll() {
  const items = [];
  let ExclusiveStartKey;
  do {
    const r = await ddb.send(new ScanCommand({ TableName: SETTINGS_TABLE, ExclusiveStartKey }));
    items.push(...(r.Items || []));
    ExclusiveStartKey = r.LastEvaluatedKey;
  } while (ExclusiveStartKey);
  return items;
}

function validateValue(type, value) {
  if (type === 'number') return isNaN(parseFloat(value)) ? 'valor numérico inválido' : null;
  if (type === 'json') {
    try {
      JSON.parse(value);
      return null;
    } catch (_) {
      return 'JSON inválido';
    }
  }
  return null;
}

/** GET /api/settings */
async function list() {
  const items = (await scanAll()).sort((a, b) => (a.order || 0) - (b.order || 0));
  return ok({ settings: items });
}

/** PUT /api/settings  { updates: { settingKey: value } } */
async function update(event) {
  const body = parseBody(event);
  const updates = body.updates || {};
  const keys = Object.keys(updates);
  if (keys.length === 0) return badRequest('Nada para atualizar');

  const meta = {};
  for (const it of await scanAll()) meta[it.settingKey] = it;

  // Valida tudo antes de gravar qualquer coisa.
  for (const k of keys) {
    const m = meta[k];
    if (!m) return badRequest(`Parâmetro desconhecido: ${k}`);
    if (m.editable === false) return badRequest(`Parâmetro não editável: ${k}`);
    const err = validateValue(m.type, String(updates[k]));
    if (err) return badRequest(`${k}: ${err}`);
  }

  for (const k of keys) {
    await ddb.send(
      new UpdateCommand({
        TableName: SETTINGS_TABLE,
        Key: { settingKey: k },
        UpdateExpression: 'SET #v = :v, updatedAt = :u',
        ExpressionAttributeNames: { '#v': 'value' },
        ExpressionAttributeValues: { ':v': String(updates[k]), ':u': new Date().toISOString() },
      })
    );
  }

  await getSettings(true); // invalida o cache desta instância
  return ok({ updated: keys.length });
}

module.exports = { list, update };
