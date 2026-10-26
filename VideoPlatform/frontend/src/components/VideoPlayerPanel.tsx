import { useEffect, useRef, useState } from 'react';
import { api, Video } from '../api';
import VideoPlayer, { TextTrack, DescSegment } from './VideoPlayer';

/**
 * Coluna de player da Biblioteca. Se o vídeo já é reproduzível (revisar/pronto),
 * autoriza e carrega o player automaticamente. Enquanto está em "processando",
 * mostra o progresso do transcode (MediaConvert) e abre o player sozinho quando
 * fica pronto.
 */
export default function VideoPlayerPanel({
  video,
  onChanged,
}: {
  video: Video;
  onChanged?: () => void;
}) {
  const playable = video.status === 'revisar' || video.status === 'pronto';
  const [hlsUrl, setHlsUrl] = useState<string | null>(null);
  const [tracks, setTracks] = useState<TextTrack[]>([]);
  const [description, setDescription] = useState<DescSegment[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [percent, setPercent] = useState<number | null>(null);
  const timerRef = useRef<number | null>(null);

  const variantsKey = JSON.stringify(video.sdhVariants || {});

  // Carrega o player (só quando reproduzível).
  useEffect(() => {
    if (!playable) {
      setHlsUrl(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setErr(null);
    setHlsUrl(null);
    setTracks([]);
    (async () => {
      try {
        const data = await api.play(video.videoId, true);
        if (cancelled) return;
        const base = data.hlsUrl.replace(/\/hls\/master\.m3u8.*$/, '');
        const ts: TextTrack[] = (data.subtitles || [])
          .filter((s) => !!s.url)
          .map((s) => ({ lang: s.lang, url: s.url as string }));
        const have = new Set(ts.map((t) => t.lang));
        Object.values(video.sdhVariants || {}).forEach((v) => {
          if (v?.lang && v.status === 'pronto' && !have.has(v.lang)) {
            ts.push({ lang: v.lang, url: `${base}/legenda/${video.videoId}.${v.lang}.vtt` });
            have.add(v.lang);
          }
        });
        setHlsUrl(data.hlsUrl);
        setTracks(ts);
      } catch (e: any) {
        if (!cancelled) setErr(e?.message || 'Falha ao carregar o player');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video.videoId, variantsKey, playable]);

  // Descrição sincronizada (se já gerada).
  useEffect(() => {
    let cancelled = false;
    if (video.descriptionStatus !== 'pronto') {
      setDescription([]);
      return;
    }
    api
      .getDescription(video.videoId)
      .then((d) => {
        if (!cancelled) setDescription(d.segments || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [video.videoId, video.descriptionStatus]);

  // Progresso do transcode enquanto em "processando".
  useEffect(() => {
    if (video.status !== 'processando') {
      setPercent(null);
      return;
    }
    let cancelled = false;
    const tick = async () => {
      try {
        const p = await api.videoProgress(video.videoId);
        if (cancelled) return;
        setPercent(p.transcodePercent);
        if (p.status === 'revisar' || p.status === 'pronto') {
          onChanged?.(); // terminou → recarrega e troca para o player
          return;
        }
      } catch {
        /* ignora */
      }
      timerRef.current = window.setTimeout(tick, 8000);
    };
    tick();
    return () => {
      cancelled = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video.videoId, video.status]);

  // ---- Render ----
  if (playable) {
    return (
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Player</h3>
        {loading && <p className="muted">Carregando player…</p>}
        {!loading && err && (
          <>
            <p className="error">{err}</p>
            <p className="muted">O player exige o vídeo em "revisar" ou "pronto".</p>
          </>
        )}
        {!loading && !err && hlsUrl && (
          <VideoPlayer key={video.videoId} hlsUrl={hlsUrl} tracks={tracks} description={description} />
        )}
      </div>
    );
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Player</h3>
      {video.status === 'processando' && (
        <>
          <p className="muted">Vídeo em processamento…</p>
          <div className="progress">
            <div className="bar" style={{ width: `${percent ?? 0}%` }} />
          </div>
          <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
            Transcodificando (MediaConvert)
            {percent != null ? `: ${Math.round(percent)}%` : '…'} · a legenda base roda em
            paralelo. O player abre sozinho quando ficar "revisar".
          </p>
        </>
      )}
      {video.status === 'enviando' && (
        <p className="muted">Aguardando a conclusão do upload…</p>
      )}
      {video.status === 'erro' && (
        <p className="error">Falha no processamento: {video.errorReason || '—'}</p>
      )}
    </div>
  );
}
