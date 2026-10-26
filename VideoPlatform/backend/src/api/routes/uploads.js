'use strict';

/**
 * Upload multipart direto do navegador para o S3 (sem limite de tamanho).
 * Fluxo: create -> (part-url * N) -> complete. O ObjectCreated dispara a pipeline.
 */

const { randomUUID } = require('crypto');
const {
  S3Client,
  CreateMultipartUploadCommand,
  UploadPartCommand,
  CompleteMultipartUploadCommand,
  AbortMultipartUploadCommand,
} = require('@aws-sdk/client-s3');
const { getSignedUrl } = require('@aws-sdk/s3-request-presigner');
const {
  REGION,
  MEDIA_BUCKET,
  STATUS,
  keys,
  nowIso,
  putVideo,
  getVideo,
} = require('../../lib/common');
const { ok, created, badRequest, notFound, parseBody, pathParam, userSub } = require('../http');

const s3 = new S3Client({ region: REGION });

function extFromName(name) {
  if (!name || !name.includes('.')) return '.mp4';
  return name.slice(name.lastIndexOf('.')).toLowerCase();
}

/** POST /api/uploads  { filename, contentType } */
async function create(event) {
  const body = parseBody(event);
  const filename = body.filename || 'video.mp4';
  const contentType = body.contentType || 'video/mp4';
  const ext = extFromName(filename);

  const videoId = randomUUID();
  const key = keys.source(videoId, ext);

  const mpu = await s3.send(
    new CreateMultipartUploadCommand({ Bucket: MEDIA_BUCKET, Key: key, ContentType: contentType })
  );

  // Nasce como "enviando": o objeto ainda não existe no S3. Só vira
  // "processando" quando a pipeline de fato inicia (start-execution, via
  // evento ObjectCreated após o complete). Assim um upload abandonado fica
  // honestamente marcado como "enviando", distinguível de quem está em pipeline.
  await putVideo({
    videoId,
    status: STATUS.UPLOADING,
    title: '',
    description: '',
    originalFilename: filename,
    sourceKey: key,
    sourceExt: ext,
    playCount: 0,
    subtitles: [],
    createdAt: nowIso(),
    updatedAt: nowIso(),
    createdBy: userSub(event),
  });

  return created({ videoId, key, uploadId: mpu.UploadId });
}

/** POST /api/uploads/{videoId}/part-url  { uploadId, partNumber } */
async function partUrl(event) {
  const videoId = pathParam(event, 'videoId');
  const body = parseBody(event);
  const { uploadId, partNumber } = body;
  if (!uploadId || !partNumber) return badRequest('uploadId e partNumber são obrigatórios');

  const video = await getVideo(videoId);
  if (!video) return notFound('Vídeo não encontrado');

  const url = await getSignedUrl(
    s3,
    new UploadPartCommand({
      Bucket: MEDIA_BUCKET,
      Key: video.sourceKey,
      UploadId: uploadId,
      PartNumber: Number(partNumber),
    }),
    { expiresIn: 3600 }
  );
  return ok({ url });
}

/** POST /api/uploads/{videoId}/complete  { uploadId, parts:[{ETag,PartNumber}] } */
async function complete(event) {
  const videoId = pathParam(event, 'videoId');
  const body = parseBody(event);
  const { uploadId, parts } = body;
  if (!uploadId || !Array.isArray(parts) || parts.length === 0) {
    return badRequest('uploadId e parts são obrigatórios');
  }

  const video = await getVideo(videoId);
  if (!video) return notFound('Vídeo não encontrado');

  const sorted = [...parts].sort((a, b) => a.PartNumber - b.PartNumber);
  await s3.send(
    new CompleteMultipartUploadCommand({
      Bucket: MEDIA_BUCKET,
      Key: video.sourceKey,
      UploadId: uploadId,
      MultipartUpload: { Parts: sorted },
    })
  );

  // O ObjectCreated em raw-videos/ dispara a Step Functions automaticamente,
  // e é o start-execution que muda o status "enviando" -> "processando".
  return ok({ videoId });
}

/** POST /api/uploads/{videoId}/abort  { uploadId } */
async function abort(event) {
  const videoId = pathParam(event, 'videoId');
  const body = parseBody(event);
  const { uploadId } = body;
  if (!uploadId) return badRequest('uploadId é obrigatório');

  const video = await getVideo(videoId);
  if (!video) return notFound('Vídeo não encontrado');

  await s3.send(
    new AbortMultipartUploadCommand({ Bucket: MEDIA_BUCKET, Key: video.sourceKey, UploadId: uploadId })
  );
  return ok({ videoId, aborted: true });
}

module.exports = { create, partUrl, complete, abort };
