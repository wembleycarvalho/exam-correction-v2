'use strict';

/**
 * Monta as settings de um job do MediaConvert: um grupo HLS com N renditions
 * (ABR). Áudio AAC muxado em cada rendition (simples e suficiente para protótipo).
 * A legenda NÃO vem daqui — é gerada pelo Transcribe como arquivo VTT à parte.
 */

/**
 * @param {object} p
 * @param {string} p.inputUri  s3://bucket/raw-videos/{id}/source.mp4
 * @param {string} p.destinationUri s3://bucket/video-profiles/{id}/hls/master
 * @param {string} [p.audioDestinationUri] s3://bucket/video-profiles/{id}/audio/track (WAV p/ Voxtral)
 * @param {Array<{name:string,width:number,height:number,bitrate:number}>} p.renditions
 */
function buildHlsJobSettings({ inputUri, destinationUri, audioDestinationUri, renditions, audioSampleRate = 16000 }) {
  const outputs = renditions.map((r) => ({
    NameModifier: `_${r.name}`,
    ContainerSettings: {
      Container: 'M3U8',
      M3u8Settings: {},
    },
    VideoDescription: {
      Width: r.width,
      Height: r.height,
      ScalingBehavior: 'DEFAULT',
      CodecSettings: {
        Codec: 'H_264',
        H264Settings: {
          RateControlMode: 'QVBR',
          QvbrSettings: { QvbrQualityLevel: 7 },
          MaxBitrate: r.bitrate,
          SceneChangeDetect: 'TRANSITION_DETECTION',
          GopSize: 90,
          GopSizeUnits: 'FRAMES',
          CodecProfile: 'MAIN',
          CodecLevel: 'AUTO',
        },
      },
    },
    AudioDescriptions: [
      {
        AudioSourceName: 'Audio Selector 1',
        CodecSettings: {
          Codec: 'AAC',
          AacSettings: {
            Bitrate: 96000,
            CodingMode: 'CODING_MODE_2_0',
            SampleRate: 48000,
          },
        },
      },
    ],
  }));

  const outputGroups = [
    {
      Name: 'HLS',
      OutputGroupSettings: {
        Type: 'HLS_GROUP_SETTINGS',
        HlsGroupSettings: {
          Destination: destinationUri,
          SegmentLength: 6,
          MinSegmentLength: 0,
          DirectoryStructure: 'SINGLE_DIRECTORY',
          ManifestDurationFormat: 'INTEGER',
          OutputSelection: 'MANIFESTS_AND_SEGMENTS',
          SegmentControl: 'SEGMENTED_FILES',
          CodecSpecification: 'RFC_4281',
        },
      },
      Outputs: outputs,
    },
  ];

  // Saída de ÁUDIO (WAV 16kHz mono) para a legenda SDH por IA (Voxtral).
  if (audioDestinationUri) {
    outputGroups.push({
      Name: 'Audio',
      OutputGroupSettings: {
        Type: 'FILE_GROUP_SETTINGS',
        FileGroupSettings: { Destination: audioDestinationUri },
      },
      Outputs: [
        {
          // Container RAW + codec WAV => arquivo .wav (RIFF) válido, aceito pelo Voxtral.
          ContainerSettings: { Container: 'RAW' },
          AudioDescriptions: [
            {
              AudioSourceName: 'Audio Selector 1',
              CodecSettings: {
                Codec: 'WAV',
                WavSettings: { BitDepth: 16, Channels: 1, SampleRate: audioSampleRate },
              },
            },
          ],
        },
      ],
    });
  }

  return {
    TimecodeConfig: { Source: 'ZEROBASED' },
    Inputs: [
      {
        FileInput: inputUri,
        TimecodeSource: 'ZEROBASED',
        VideoSelector: {},
        AudioSelectors: {
          'Audio Selector 1': { DefaultSelection: 'DEFAULT' },
        },
      },
    ],
    OutputGroups: outputGroups,
  };
}

module.exports = { buildHlsJobSettings };
