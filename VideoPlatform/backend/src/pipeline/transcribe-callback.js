'use strict';

/**
 * Acionado pelo EventBridge em "Transcribe Job State Change".
 * Copia o VTT gerado para o nome canônico ({videoId}.pt.vtt) e retoma a SFN.
 */

const { SFNClient, SendTaskSuccessCommand, SendTaskFailureCommand } = require('@aws-sdk/client-sfn');
const {
  TranscribeClient,
  GetTranscriptionJobCommand,
} = require('@aws-sdk/client-transcribe');
const { S3Client, CopyObjectCommand } = require('@aws-sdk/client-s3');
const { REGION, MEDIA_BUCKET, keys, getVideo } = require('../lib/common');

const sfn = new SFNClient({ region: REGION });
const transcribe = new TranscribeClient({ region: REGION });
const s3 = new S3Client({ region: REGION });

function videoIdFromJobName(name) {
  // prefix--videoId--timestamp
  const parts = (name || '').split('--');
  return parts.length >= 3 ? parts[1] : null;
}

/** Extrai a chave S3 (dentro do nosso bucket) a partir da URI de legenda. */
function keyFromSubtitleUri(uri) {
  if (!uri) return null;
  if (uri.startsWith('s3://')) {
    const rest = uri.slice('s3://'.length);
    const idx = rest.indexOf('/');
    return idx >= 0 ? rest.slice(idx + 1) : null;
  }
  const marker = `/${MEDIA_BUCKET}/`;
  const i = uri.indexOf(marker);
  if (i >= 0) return decodeURIComponent(uri.slice(i + marker.length).split('?')[0]);
  return null;
}

exports.handler = async (event) => {
  const detail = event.detail || {};
  const jobName = detail.TranscriptionJobName;
  const status = detail.TranscriptionJobStatus; // COMPLETED | FAILED
  const videoId = videoIdFromJobName(jobName);
  console.log('Transcribe callback', { status, jobName, videoId });

  if (!videoId) {
    console.warn('Não foi possível extrair videoId do job name:', jobName);
    return;
  }

  const video = await getVideo(videoId);
  const token = video?.trTaskToken;
  if (!token) {
    console.warn('Sem task token Transcribe para', videoId);
    return;
  }

  if (status !== 'COMPLETED') {
    await sfn.send(
      new SendTaskFailureCommand({
        taskToken: token,
        error: 'TranscribeFailed',
        cause: detail.FailureReason || `Status ${status}`,
      })
    );
    return;
  }

  // Descobre o VTT gerado e copia para o nome canônico.
  let sourceKey = `${keys.subtitlePrefix(videoId)}transcript.vtt`; // padrão esperado
  try {
    const job = await transcribe.send(
      new GetTranscriptionJobCommand({ TranscriptionJobName: jobName })
    );
    const uris = job.TranscriptionJob?.Subtitles?.SubtitleFileUris || [];
    const parsed = keyFromSubtitleUri(uris[0]);
    if (parsed) sourceKey = parsed;
  } catch (e) {
    console.warn('GetTranscriptionJob falhou, usando chave padrão:', e.message);
  }

  const destKey = keys.subtitle(videoId, 'pt');
  await s3.send(
    new CopyObjectCommand({
      Bucket: MEDIA_BUCKET,
      CopySource: `/${MEDIA_BUCKET}/${encodeURIComponent(sourceKey).replace(/%2F/g, '/')}`,
      Key: destKey,
      ContentType: 'text/vtt',
      MetadataDirective: 'REPLACE',
    })
  );

  await sfn.send(
    new SendTaskSuccessCommand({
      taskToken: token,
      output: JSON.stringify({ transcribe: { subtitleKey: destKey, lang: 'pt' } }),
    })
  );
};
