'use strict';

/** CRUD de vídeos: listar, obter, editar metadados (revisão), publicar, excluir. */

const {
  S3Client,
  ListObjectsV2Command,
  DeleteObjectsCommand,
} = require('@aws-sdk/client-s3');
const {
  REGION,
  MEDIA_BUCKET,
  VIDEOS_TABLE,
  STATUS,
  ddb,
  ScanCommand,
  UpdateCommand,
  keys,
  getVideo,
  updateVideo,
  nowIso,
} = require('../../lib/common');
const { ok, badRequest, notFound } = require('../http');
const { DeleteCommand } = require('@aws-sdk/lib-dynamodb');
const { parseBody, pathParam } = require('../http');

const s3 = new S3Client({ region: REGION });

/** Remove atributos internos (tokens) antes de devolver ao cliente. */
function sanitize(v) {
  if (!v) return v;
  const { mcTaskToken, trTaskToken, ...rest } = v;
  return rest;
}

/** GET /api/videos */
async function list() {
  const r = await ddb.send(new ScanCommand({ TableName: VIDEOS_TABLE }));
  const items = (r.Items || [])
    .map(sanitize)
    .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
  return ok({ videos: items });
}

/** GET /api/videos/{videoId} */
async function get(event) {
  const videoId = pathParam(event, 'videoId');
  const v = await getVideo(videoId);
  if (!v) return notFound('Vídeo não encontrado');
  return ok(sanitize(v));
}

/** PATCH /api/videos/{videoId}  { title, description } */
async function update(event) {
  const videoId = pathParam(event, 'videoId');
  const body = parseBody(event);
  const v = await getVideo(videoId);
  if (!v) return notFound('Vídeo não encontrado');

  const set = {};
  if (typeof body.title === 'string') set.title = body.title.slice(0, 200);
  if (typeof body.description === 'string') set.description = body.description.slice(0, 5000);
  if (Object.keys(set).length === 0) return badRequest('Nada para atualizar');

  await updateVideo(videoId, set);
  const updated = await getVideo(videoId);
  return ok(sanitize(updated));
}

/** POST /api/videos/{videoId}/publish  (revisar -> pronto) */
async function publish(event) {
  const videoId = pathParam(event, 'videoId');
  const v = await getVideo(videoId);
  if (!v) return notFound('Vídeo não encontrado');
  if (v.status !== STATUS.REVIEW) {
    return badRequest(`Só é possível publicar a partir de "revisar" (atual: ${v.status})`);
  }
  if (!v.title) return badRequest('Informe um título antes de publicar');

  await ddb.send(
    new UpdateCommand({
      TableName: VIDEOS_TABLE,
      Key: { videoId },
      UpdateExpression: 'SET #s = :ready, publishedAt = :p, updatedAt = :u',
      ExpressionAttributeNames: { '#s': 'status' },
      ExpressionAttributeValues: { ':ready': STATUS.READY, ':p': nowIso(), ':u': nowIso() },
    })
  );
  const updated = await getVideo(videoId);
  return ok(sanitize(updated));
}

/** POST /api/videos/{videoId}/unpublish  (pronto -> revisar) */
async function unpublish(event) {
  const videoId = pathParam(event, 'videoId');
  const v = await getVideo(videoId);
  if (!v) return notFound('Vídeo não encontrado');
  if (v.status !== STATUS.READY) {
    return badRequest(`Só é possível despublicar um vídeo "pronto" (atual: ${v.status})`);
  }
  await ddb.send(
    new UpdateCommand({
      TableName: VIDEOS_TABLE,
      Key: { videoId },
      UpdateExpression: 'SET #s = :review, updatedAt = :u REMOVE publishedAt',
      ExpressionAttributeNames: { '#s': 'status' },
      ExpressionAttributeValues: { ':review': STATUS.REVIEW, ':u': nowIso() },
    })
  );
  const updated = await getVideo(videoId);
  return ok(sanitize(updated));
}

/** DELETE /api/videos/{videoId}  (remove objetos do S3 + registro) */
async function remove(event) {
  const videoId = pathParam(event, 'videoId');
  const v = await getVideo(videoId);
  if (!v) return notFound('Vídeo não encontrado');

  for (const prefix of [keys.rawPrefix(videoId), keys.profilesPrefix(videoId)]) {
    let token;
    do {
      const listed = await s3.send(
        new ListObjectsV2Command({ Bucket: MEDIA_BUCKET, Prefix: prefix, ContinuationToken: token })
      );
      const objects = (listed.Contents || []).map((o) => ({ Key: o.Key }));
      if (objects.length > 0) {
        await s3.send(
          new DeleteObjectsCommand({ Bucket: MEDIA_BUCKET, Delete: { Objects: objects } })
        );
      }
      token = listed.IsTruncated ? listed.NextContinuationToken : undefined;
    } while (token);
  }

  await ddb.send(new DeleteCommand({ TableName: VIDEOS_TABLE, Key: { videoId } }));
  return ok({ videoId, deleted: true });
}

module.exports = { list, get, update, publish, unpublish, remove };
