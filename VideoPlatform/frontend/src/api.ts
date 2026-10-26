import { config } from './config';
import { getIdToken } from './auth';

/** Cliente HTTP: injeta o JWT do Cognito e usa same-origin em produção. */
async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = await getIdToken();
  const headers: Record<string, string> = {};
  if (token) headers['authorization'] = `Bearer ${token}`;
  if (body !== undefined) headers['content-type'] = 'application/json';

  const res = await fetch(`${config.apiBase}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    // same-origin em produção (CloudFront); 'include' permite cookies em qualquer caso.
    credentials: 'include',
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new Error(data?.error || `Erro ${res.status}`);
  }
  return data as T;
}

export interface Subtitle {
  lang: string;
  key?: string;
  offsetSec?: number;
  url?: string;
}
export interface TranscodeProfile {
  name: string;
  height: number;
  tier?: string;
  usd: number;
}
export interface Cost {
  transcodeUSD?: number;
  transcodeProfiles?: TranscodeProfile[];
  transcribeUSD?: number;
  translateUSD?: number;
  sdhUSD?: number;
  descriptionUSD?: number;
  orchestrationUSD?: number;
  totalUSD?: number;
}
export type JobStatus = 'processando' | 'pronto' | 'erro' | undefined;
export interface EvalFlag {
  time: string;
  issue: string;
}
export interface SubtitleEval {
  textConfidence: number | null;
  consensusPct: number | null;
  llmScore: number | null;
  comment: string;
  flags: EvalFlag[];
  methods: string[];
  costs: { transcribeUSD?: number | null; voxtralUSD?: number | null; judgeUSD?: number };
  model?: string;
  judgeTokens?: { input: number; output: number };
  truncated?: boolean;
  generatedAt?: string;
}
export interface SdhVariant {
  lang: string;
  key?: string;
  model?: string;
  passes?: number;
  timeMs?: number;
  inTok?: number;
  outTok?: number;
  usd?: number;
  cues?: number;
  markers?: number;
  speech?: number;
  status?: JobStatus;
  error?: string;
  generatedAt?: string;
  eval?: SubtitleEval;
}
export interface Video {
  videoId: string;
  status: 'enviando' | 'processando' | 'revisar' | 'pronto' | 'erro';
  title?: string;
  description?: string;
  originalFilename?: string;
  durationSec?: number;
  pipelineMs?: number;
  playCount?: number;
  subtitles?: Subtitle[];
  cost?: Cost;
  errorReason?: string;
  createdAt?: string;
  sdhStatus?: JobStatus;
  sdhError?: string;
  sdhVariants?: Record<string, SdhVariant>;
  descriptionStatus?: JobStatus;
  descriptionError?: string;
  hasDescription?: boolean;
}

export interface DescriptionSegment {
  start: number;
  end: number;
  text: string;
}
export interface VideoDescription {
  videoId: string;
  model: string;
  generatedAt: string;
  segments: DescriptionSegment[];
}

export interface Setting {
  settingKey: string;
  value: string;
  type: 'string' | 'number' | 'csv' | 'json' | 'bool';
  category: string;
  label: string;
  description: string;
  unit?: string;
  editable?: boolean;
  order?: number;
  updatedAt?: string;
}

export const api = {
  // uploads
  createUpload: (filename: string, contentType: string) =>
    request<{ videoId: string; key: string; uploadId: string }>('POST', '/api/uploads', {
      filename,
      contentType,
    }),
  partUrl: (videoId: string, uploadId: string, partNumber: number) =>
    request<{ url: string }>('POST', `/api/uploads/${videoId}/part-url`, { uploadId, partNumber }),
  completeUpload: (
    videoId: string,
    uploadId: string,
    parts: { ETag: string; PartNumber: number }[]
  ) => request('POST', `/api/uploads/${videoId}/complete`, { uploadId, parts }),

  // videos
  listVideos: () => request<{ videos: Video[] }>('GET', '/api/videos'),
  getVideo: (id: string) => request<Video>('GET', `/api/videos/${id}`),
  videoProgress: (id: string) =>
    request<{ videoId: string; status: string; transcodePercent: number | null }>(
      'GET',
      `/api/videos/${id}/progress`
    ),
  updateVideo: (id: string, patch: { title?: string; description?: string }) =>
    request<Video>('PATCH', `/api/videos/${id}`, patch),
  publishVideo: (id: string) => request<Video>('POST', `/api/videos/${id}/publish`),
  unpublishVideo: (id: string) => request<Video>('POST', `/api/videos/${id}/unpublish`),
  deleteVideo: (id: string) => request('DELETE', `/api/videos/${id}`),

  // subtitles
  getSubtitle: (id: string, lang: string) =>
    request<{ lang: string; content: string }>('GET', `/api/videos/${id}/subtitle?lang=${lang}`),
  putSubtitle: (id: string, lang: string, content: string, offsetSec: number) =>
    request('PUT', `/api/videos/${id}/subtitle`, { lang, content, offsetSec }),
  translate: (id: string, targetLang: string, sourceLang?: string) =>
    request<{ sourceLang: string; lang: string; subtitles: Subtitle[] }>(
      'POST',
      `/api/videos/${id}/translate`,
      { targetLang, sourceLang: sourceLang || 'pt' }
    ),

  // Wizard: análise comparativa de duas faixas de legenda por LLM.
  compareSubtitles: (
    id: string,
    langA: string,
    langB: string,
    labelA?: string,
    labelB?: string
  ) =>
    request<{
      langA: string;
      langB: string;
      model: string;
      truncated: boolean;
      analysis: string;
      tokens: { input: number; output: number };
      usd: number;
    }>('POST', `/api/videos/${id}/compare-subtitles`, { langA, langB, labelA, labelB }),

  // Legenda SDH por IA de áudio (Voxtral) — assíncrono. method seleciona a
  // variante (mini1p | v24b1p | v24b2p); status fica em sdhVariants[method].
  startSdh: (id: string, method?: string) =>
    request<{ videoId: string; method: string; status: string }>(
      'POST',
      `/api/videos/${id}/sdh`,
      method ? { method } : undefined
    ),
  // Avaliador de qualidade do TEXTO (consenso + LLM-juiz). Síncrono; grava o
  // resultado em sdhVariants[method].eval e também o retorna.
  evaluateSubtitle: (id: string, method: string) =>
    request<{ videoId: string; method: string; eval: SubtitleEval }>(
      'POST',
      `/api/videos/${id}/evaluate-subtitle`,
      { method }
    ),
  // Descrição de vídeo (Pegasus) — assíncrono (polling do descriptionStatus).
  startDescribe: (id: string) =>
    request<{ videoId: string; descriptionStatus: string }>('POST', `/api/videos/${id}/describe`),
  getDescription: (id: string) =>
    request<VideoDescription>('GET', `/api/videos/${id}/description`),

  // play (preview=true é usado só na tela de revisão, para vídeos em "revisar")
  play: (id: string, preview = false) =>
    request<{
      videoId: string;
      title?: string;
      description?: string;
      durationSec: number;
      hlsUrl: string;
      subtitles: Subtitle[];
      expiresInSec: number;
    }>('POST', `/api/videos/${id}/play`, preview ? { preview: true } : undefined),

  // settings (configuração)
  getSettings: () => request<{ settings: Setting[] }>('GET', '/api/settings'),
  updateSettings: (updates: Record<string, string>) =>
    request<{ updated: number }>('PUT', '/api/settings', { updates }),

  // analytics
  analytics: () =>
    request<{
      videos: {
        videoId: string;
        title: string;
        status: string;
        playCount: number;
        durationSec: number;
        cost: Cost | null;
      }[];
      totals: { totalPlays: number; estimatedCostUSD: number; videoCount: number };
    }>('GET', '/api/analytics'),
};

/** Faz o upload multipart de um arquivo, reportando progresso (0..1). */
export async function uploadFile(
  file: File,
  onProgress: (p: number) => void
): Promise<string> {
  const { videoId, uploadId } = await api.createUpload(file.name, file.type || 'video/mp4');

  const PART_SIZE = 10 * 1024 * 1024; // 10 MB
  const totalParts = Math.ceil(file.size / PART_SIZE);
  const parts: { ETag: string; PartNumber: number }[] = [];

  for (let i = 0; i < totalParts; i++) {
    const partNumber = i + 1;
    const blob = file.slice(i * PART_SIZE, Math.min((i + 1) * PART_SIZE, file.size));
    const { url } = await api.partUrl(videoId, uploadId, partNumber);

    const put = await fetch(url, { method: 'PUT', body: blob });
    if (!put.ok) throw new Error(`Falha no upload da parte ${partNumber}`);
    const etag = put.headers.get('ETag') || put.headers.get('etag');
    if (!etag) throw new Error('ETag ausente na resposta do S3 (verifique CORS do bucket)');
    parts.push({ ETag: etag, PartNumber: partNumber });

    onProgress((i + 1) / totalParts);
  }

  await api.completeUpload(videoId, uploadId, parts);
  return videoId;
}
