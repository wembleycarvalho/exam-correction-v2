'use strict';

/**
 * Utilidades compartilhadas pelos handlers Lambda (pipeline + API).
 * JavaScript puro; o AWS SDK v3 é fornecido pelo runtime Node 20 do Lambda.
 */

const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const {
  DynamoDBDocumentClient,
  GetCommand,
  PutCommand,
  UpdateCommand,
  QueryCommand,
  ScanCommand,
} = require('@aws-sdk/lib-dynamodb');

const REGION = process.env.AWS_REGION || 'us-east-1';

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }), {
  marshallOptions: { removeUndefinedValues: true },
});

const VIDEOS_TABLE = process.env.VIDEOS_TABLE;
const PLAYS_TABLE = process.env.PLAYS_TABLE;
const MEDIA_BUCKET = process.env.MEDIA_BUCKET;
const SETTINGS_TABLE = process.env.SETTINGS_TABLE;
const RAW_PREFIX = process.env.RAW_PREFIX || 'raw-videos';
const PROFILES_PREFIX = process.env.PROFILES_PREFIX || 'video-profiles';

const STATUS = {
  UPLOADING: 'enviando', // upload em andamento (ainda não há objeto no S3)
  PROCESSING: 'processando', // pipeline iniciada (transcode/legenda)
  REVIEW: 'revisar',
  READY: 'pronto',
  ERROR: 'erro',
};

const nowIso = () => new Date().toISOString();

/** Caminhos canônicos no S3 para um vídeo. */
const keys = {
  rawPrefix: (videoId) => `${RAW_PREFIX}/${videoId}/`,
  source: (videoId, ext) => `${RAW_PREFIX}/${videoId}/source${ext || '.mp4'}`,
  profilesPrefix: (videoId) => `${PROFILES_PREFIX}/${videoId}/`,
  hlsDestinationBase: (videoId) => `${PROFILES_PREFIX}/${videoId}/hls/master`, // MediaConvert destino
  hlsMaster: (videoId) => `${PROFILES_PREFIX}/${videoId}/hls/master.m3u8`,
  subtitle: (videoId, lang) => `${PROFILES_PREFIX}/${videoId}/legenda/${videoId}.${lang}.vtt`,
  subtitlePrefix: (videoId) => `${PROFILES_PREFIX}/${videoId}/legenda/`,
  audioDestinationBase: (videoId) => `${PROFILES_PREFIX}/${videoId}/audio/track`, // MediaConvert destino
  audio: (videoId) => `${PROFILES_PREFIX}/${videoId}/audio/track.wav`,
  description: (videoId) => `${PROFILES_PREFIX}/${videoId}/description/description.json`,
};

async function getVideo(videoId) {
  const r = await ddb.send(new GetCommand({ TableName: VIDEOS_TABLE, Key: { videoId } }));
  return r.Item || null;
}

async function putVideo(item) {
  await ddb.send(new PutCommand({ TableName: VIDEOS_TABLE, Item: item }));
}

/**
 * UpdateItem genérico por atributos. `set` é um objeto nome->valor.
 */
async function updateVideo(videoId, set, opts = {}) {
  const names = {};
  const values = {};
  const sets = [];
  Object.entries(set).forEach(([k, v], i) => {
    names[`#k${i}`] = k;
    values[`:v${i}`] = v;
    sets.push(`#k${i} = :v${i}`);
  });
  names['#u'] = 'updatedAt';
  values[':u'] = nowIso();
  sets.push('#u = :u');

  let expr = `SET ${sets.join(', ')}`;
  if (opts.add) {
    const adds = [];
    Object.entries(opts.add).forEach(([k, v], i) => {
      names[`#a${i}`] = k;
      values[`:a${i}`] = v;
      adds.push(`#a${i} :a${i}`);
    });
    expr += ` ADD ${adds.join(', ')}`;
  }

  await ddb.send(
    new UpdateCommand({
      TableName: VIDEOS_TABLE,
      Key: { videoId },
      UpdateExpression: expr,
      ExpressionAttributeNames: names,
      ExpressionAttributeValues: values,
    })
  );
}

/**
 * Atualiza UM campo-mapa aninhado `sdhVariants.<method>` de forma atômica
 * (sem corrida entre jobs paralelos de variantes). Inicializa os mapas com
 * if_not_exists e então grava os campos passados.
 */
async function patchVariant(videoId, method, fields) {
  await ddb.send(
    new UpdateCommand({
      TableName: VIDEOS_TABLE,
      Key: { videoId },
      UpdateExpression: 'SET sdhVariants = if_not_exists(sdhVariants, :e)',
      ExpressionAttributeValues: { ':e': {} },
    })
  );
  await ddb.send(
    new UpdateCommand({
      TableName: VIDEOS_TABLE,
      Key: { videoId },
      UpdateExpression: 'SET sdhVariants.#m = if_not_exists(sdhVariants.#m, :e)',
      ExpressionAttributeNames: { '#m': method },
      ExpressionAttributeValues: { ':e': {} },
    })
  );
  const names = { '#m': method };
  const values = { ':u': nowIso() };
  const sets = ['updatedAt = :u'];
  Object.entries(fields).forEach(([k, v], i) => {
    names[`#f${i}`] = k;
    values[`:v${i}`] = v;
    sets.push(`sdhVariants.#m.#f${i} = :v${i}`);
  });
  await ddb.send(
    new UpdateCommand({
      TableName: VIDEOS_TABLE,
      Key: { videoId },
      UpdateExpression: `SET ${sets.join(', ')}`,
      ExpressionAttributeNames: names,
      ExpressionAttributeValues: values,
    })
  );
}

/** Classifica um perfil pelo height em tier de preço do MediaConvert. */
function mcTier(height) {
  if (height > 1080) return 'uhd';
  if (height >= 720) return 'hd';
  return 'sd';
}

/**
 * Estima o custo de processamento inicial (USD) a partir das tarifas recebidas
 * (lidas das settings pelo chamador). Sem defaults de comportamento aqui.
 * - MediaConvert: custo POR PERFIL (tier SD/HD/UHD × minutos de saída).
 * - Orquestração: estimativa de Lambda (pipeline) + transições do Step Functions.
 */
function estimateCost({ durationSec = 0, renditions = [], rates = {} } = {}) {
  const minutes = durationSec / 60;
  const {
    mcSd = 0,
    mcHd = 0,
    mcUhd = 0,
    trPerMin = 0,
    sfnPerTransition = 0,
    sfnTransitions = 0,
    pipelineLambdaGbSec = 0,
    lambdaPerGbSecond = 0,
  } = rates;
  const rateFor = (h) => (mcTier(h) === 'uhd' ? mcUhd : mcTier(h) === 'hd' ? mcHd : mcSd);

  const list = Array.isArray(renditions) ? renditions : [];
  const transcodeProfiles = list.map((r) => {
    const height = r.height || 0;
    return {
      name: r.name || `${height}p`,
      height,
      tier: mcTier(height),
      usd: +(minutes * rateFor(height)).toFixed(5),
    };
  });
  const transcodeUSD = +transcodeProfiles.reduce((a, p) => a + p.usd, 0).toFixed(4);
  const transcribeUSD = +(minutes * trPerMin).toFixed(4);
  const orchestrationUSD = +(
    sfnTransitions * sfnPerTransition +
    pipelineLambdaGbSec * lambdaPerGbSecond
  ).toFixed(5);

  const cost = {
    transcodeUSD,
    transcodeProfiles,
    transcribeUSD,
    translateUSD: 0,
    sdhUSD: 0,
    descriptionUSD: 0,
    orchestrationUSD,
    estimatedAt: nowIso(),
  };
  cost.totalUSD = recomputeCostTotal(cost);
  return cost;
}

/** Parcelas de custo somadas no total (cada técnica isolada). */
const COST_PARTS = [
  'transcodeUSD', // MediaConvert
  'transcribeUSD', // Amazon Transcribe (legenda)
  'translateUSD', // Amazon Translate (traduções)
  'sdhUSD', // legenda SDH por IA de áudio (Voxtral)
  'descriptionUSD', // descrição de vídeo (Pegasus)
  'orchestrationUSD', // Lambda (pipeline) + Step Functions
];

/** Recalcula o total somando todas as parcelas de custo. */
function recomputeCostTotal(cost = {}) {
  const t = COST_PARTS.reduce((acc, k) => acc + (cost[k] || 0), 0);
  return +t.toFixed(4);
}

// ---------- Configuração (settings) lida da tabela DynamoDB ----------
function parseSettingValue(value, type) {
  switch (type) {
    case 'number':
      return parseFloat(value);
    case 'bool':
      return value === 'true' || value === true;
    case 'csv':
      return String(value)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
    case 'json':
      try {
        return JSON.parse(value);
      } catch (_) {
        return null;
      }
    default:
      return value;
  }
}

let _settingsCache = null;
let _settingsAt = 0;
const SETTINGS_TTL_MS = 30 * 1000;

/**
 * Retorna { 'chave': valorJaConvertido } a partir da tabela de settings.
 * Cache de 30s por instância da Lambda (mudanças na tela de Config propagam
 * em até ~30s, sem redeploy).
 */
async function getSettings(force = false) {
  const now = Date.now();
  if (!force && _settingsCache && now - _settingsAt < SETTINGS_TTL_MS) return _settingsCache;
  const items = [];
  let ExclusiveStartKey;
  do {
    const r = await ddb.send(new ScanCommand({ TableName: SETTINGS_TABLE, ExclusiveStartKey }));
    items.push(...(r.Items || []));
    ExclusiveStartKey = r.LastEvaluatedKey;
  } while (ExclusiveStartKey);
  const out = {};
  for (const it of items) out[it.settingKey] = parseSettingValue(it.value, it.type);
  _settingsCache = out;
  _settingsAt = now;
  return out;
}

/** Lê uma chave de settings garantindo presença (erro claro se faltar seed). */
function reqSetting(cfg, key) {
  if (cfg[key] === undefined || cfg[key] === null) {
    throw new Error(`Configuração ausente: "${key}" (verifique a tabela de settings/seed).`);
  }
  return cfg[key];
}

module.exports = {
  REGION,
  ddb,
  VIDEOS_TABLE,
  PLAYS_TABLE,
  MEDIA_BUCKET,
  RAW_PREFIX,
  PROFILES_PREFIX,
  STATUS,
  keys,
  nowIso,
  SETTINGS_TABLE,
  getSettings,
  reqSetting,
  getVideo,
  putVideo,
  updateVideo,
  patchVariant,
  estimateCost,
  recomputeCostTotal,
  // reexport dynamo commands para handlers
  GetCommand,
  PutCommand,
  UpdateCommand,
  QueryCommand,
  ScanCommand,
};
