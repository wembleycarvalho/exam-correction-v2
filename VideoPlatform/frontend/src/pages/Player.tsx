import { useState } from 'react';
import { api, DescriptionSegment } from '../api';
import VideoPlayer, { TextTrack } from '../components/VideoPlayer';

export default function Player() {
  const [videoId, setVideoId] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState<{
    title?: string;
    summary?: string;
    hlsUrl: string;
    tracks: TextTrack[];
    description: DescriptionSegment[];
  } | null>(null);

  async function play() {
    setErr(null);
    setBusy(true);
    setData(null);
    try {
      const id = videoId.trim();
      const r = await api.play(id);
      const tracks = (r.subtitles || [])
        .filter((s) => s.url)
        .map((s) => ({ lang: s.lang, url: s.url as string }));
      // Descrição do vídeo (Pegasus), se existir.
      let description: DescriptionSegment[] = [];
      try {
        description = (await api.getDescription(id)).segments || [];
      } catch {
        /* sem descrição */
      }
      setData({ title: r.title, summary: r.description, hlsUrl: r.hlsUrl, tracks, description });
    } catch (e: any) {
      setErr(e?.message || 'Não foi possível reproduzir');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <h1>Player</h1>
      <p className="muted">
        Informe o ID do vídeo. O conteúdo é protegido: o backend valida o acesso e emite cookies
        assinados de curta duração. Vídeos só tocam quando estão "pronto" (ou em preview na revisão).
      </p>

      <div className="card row">
        <input
          placeholder="ID do vídeo (UUID)"
          value={videoId}
          onChange={(e) => setVideoId(e.target.value)}
          style={{ flex: 1 }}
        />
        <button className="primary" onClick={play} disabled={!videoId || busy}>
          {busy ? 'Carregando…' : 'Reproduzir'}
        </button>
      </div>
      {err && <p className="error">{err}</p>}

      {data && (
        <div className="card">
          {data.title && <h2>{data.title}</h2>}
          {data.summary && <p className="muted">{data.summary}</p>}
          <VideoPlayer
            hlsUrl={data.hlsUrl}
            tracks={data.tracks}
            activeLang="pt"
            description={data.description}
          />
        </div>
      )}
    </div>
  );
}
