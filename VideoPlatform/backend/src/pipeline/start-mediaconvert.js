'use strict';

/**
 * Task da Step Functions (padrão waitForTaskToken): cria o job do MediaConvert
 * e guarda o task token no item do vídeo. A conclusão do job é tratada pelo
 * handler mediaconvert-callback (via EventBridge), que retoma a State Machine.
 */

const {
  MediaConvertClient,
  DescribeEndpointsCommand,
  CreateJobCommand,
} = require('@aws-sdk/client-mediaconvert');
const { REGION, MEDIA_BUCKET, keys, updateVideo, getSettings, reqSetting } = require('../lib/common');
const { buildHlsJobSettings } = require('../lib/mediaconvert-settings');

const MEDIACONVERT_ROLE_ARN = process.env.MEDIACONVERT_ROLE_ARN;

let cachedEndpoint = null;
async function getClient() {
  if (!cachedEndpoint) {
    const probe = new MediaConvertClient({ region: REGION });
    const res = await probe.send(new DescribeEndpointsCommand({}));
    cachedEndpoint = res.Endpoints?.[0]?.Url;
  }
  return new MediaConvertClient({ region: REGION, endpoint: cachedEndpoint });
}

exports.handler = async (event) => {
  const { videoId, sourceKey, taskToken } = event;
  console.log('Criando job MediaConvert', { videoId, sourceKey });

  const cfg = await getSettings();
  const renditions = reqSetting(cfg, 'transcode.renditions');
  const audioSampleRate = reqSetting(cfg, 'sdh.audioSampleRate');

  const inputUri = `s3://${MEDIA_BUCKET}/${sourceKey}`;
  const destinationUri = `s3://${MEDIA_BUCKET}/${keys.hlsDestinationBase(videoId)}`;
  const audioDestinationUri = `s3://${MEDIA_BUCKET}/${keys.audioDestinationBase(videoId)}`;

  const client = await getClient();

  const job = await client.send(
    new CreateJobCommand({
      Role: MEDIACONVERT_ROLE_ARN,
      Settings: buildHlsJobSettings({ inputUri, destinationUri, audioDestinationUri, renditions, audioSampleRate }),
      UserMetadata: { videoId },
      StatusUpdateInterval: 'SECONDS_60',
    })
  );

  const jobId = job.Job?.Id;
  console.log('Job MediaConvert criado', { jobId });

  // Guarda o token para o callback retomar a execução quando o job terminar.
  await updateVideo(videoId, { mcJobId: jobId, mcTaskToken: taskToken });

  // Não retorna: a task fica pendente até SendTaskSuccess no callback.
  return { jobId };
};
