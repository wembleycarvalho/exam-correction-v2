'use strict';

/**
 * Task da Step Functions (padrão waitForTaskToken): inicia o job do Transcribe
 * (pt-BR) gerando legenda WebVTT. A conclusão é tratada por transcribe-callback.
 */

const {
  TranscribeClient,
  StartTranscriptionJobCommand,
} = require('@aws-sdk/client-transcribe');
const { REGION, MEDIA_BUCKET, keys, updateVideo, getSettings, reqSetting } = require('../lib/common');

const transcribe = new TranscribeClient({ region: REGION });
const APP_PREFIX = process.env.APP_PREFIX || 'videoplatform'; // identidade (infra), não é config

exports.handler = async (event) => {
  const { videoId, sourceKey, taskToken } = event;
  console.log('Iniciando Transcribe', { videoId, sourceKey });

  const cfg = await getSettings();
  const LANGUAGE_CODE = reqSetting(cfg, 'lang.transcribe');

  // Nome do job parseável no callback: prefix--videoId--timestamp (videoId é UUID, sem '--').
  const jobName = `${APP_PREFIX}--${videoId}--${Date.now()}`;
  const mediaUri = `s3://${MEDIA_BUCKET}/${sourceKey}`;
  // Transcribe grava o JSON e, com Subtitles, o(s) arquivo(s) VTT no bucket de saída.
  const outputKey = `${keys.subtitlePrefix(videoId)}transcript.json`;

  await transcribe.send(
    new StartTranscriptionJobCommand({
      TranscriptionJobName: jobName,
      LanguageCode: LANGUAGE_CODE,
      Media: { MediaFileUri: mediaUri },
      OutputBucketName: MEDIA_BUCKET,
      OutputKey: outputKey,
      Subtitles: { Formats: ['vtt'], OutputStartIndex: 1 },
    })
  );

  await updateVideo(videoId, { trJobName: jobName, trTaskToken: taskToken });

  return { jobName };
};
