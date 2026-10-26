import { useEffect, useRef, useState } from 'react';
import { api, uploadFile, Video } from '../api';
import StatusBadge from '../components/StatusBadge';
import VideoReview from '../components/VideoReview';
import VideoPlayerPanel from '../components/VideoPlayerPanel';

export default function Library() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    try {
      const { videos } = await api.listVideos();
      setVideos(videos);
    } catch (err: any) {
      setError(err?.message || 'Falha ao carregar');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (inputRef.current) inputRef.current.value = ''; // permite reenviar o mesmo arquivo
    if (!file) return;
    setUploadErr(null);
    setUploading(true);
    setProgress(0);
    try {
      const videoId = await uploadFile(file, setProgress);
      await load();
      setSelected(videoId);
    } catch (err: any) {
      setUploadErr(err?.message || 'Falha no upload');
    } finally {
      setUploading(false);
    }
  }

  const selectedVideo = videos.find((v) => v.videoId === selected) || null;

  return (
    <div className="page lib3-wide">
      <div className="lib-head">
        <h1>Biblioteca de vídeos</h1>
        <label className={`filepick ${uploading ? 'disabled' : ''}`} style={{ margin: 0 }}>
          <input
            ref={inputRef}
            type="file"
            accept="video/*"
            className="filepick-input"
            disabled={uploading}
            onChange={onPickFile}
          />
          <span className="filepick-btn">
            {uploading ? `Enviando… ${(progress * 100).toFixed(0)}%` : '⬆ Enviar vídeo'}
          </span>
        </label>
      </div>
      <p className="muted">
        Selecione um vídeo na lista; as configurações abrem no centro e o player à direita.
      </p>
      {uploading && (
        <>
          <div className="progress">
            <div className="bar" style={{ width: `${progress * 100}%` }} />
          </div>
          <p className="error" style={{ fontSize: 12, marginTop: 6 }}>
            Não saia desta página enquanto o upload estiver em andamento.
          </p>
        </>
      )}
      {uploadErr && <p className="error">{uploadErr}</p>}
      {error && <p className="error">{error}</p>}

      <div className="lib3">
        {/* Coluna 1: lista */}
        <div className="lib3-list">
          {loading ? (
            <p className="muted">Carregando…</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Título</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {videos.map((v) => (
                  <tr
                    key={v.videoId}
                    className={v.videoId === selected ? 'sel' : ''}
                    onClick={() => setSelected(v.videoId)}
                  >
                    <td>
                      {v.title || (
                        <span className="muted">(sem título) {v.videoId.slice(0, 8)}…</span>
                      )}
                    </td>
                    <td>
                      <StatusBadge status={v.status} />
                    </td>
                  </tr>
                ))}
                {videos.length === 0 && (
                  <tr>
                    <td colSpan={2} className="muted">
                      Nenhum vídeo ainda. Use "Enviar vídeo".
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        {/* Coluna 2: configurações (revisão) */}
        <div className="lib3-config">
          {selectedVideo ? (
            <VideoReview
              key={selectedVideo.videoId}
              video={selectedVideo}
              onClose={() => setSelected(null)}
              onChanged={load}
            />
          ) : (
            <div className="card detail-empty">
              Selecione um vídeo à esquerda para abrir as configurações (metadados, legendas,
              comparação de modelos).
            </div>
          )}
        </div>

        {/* Coluna 3: player */}
        <div className="lib3-player">
          {selectedVideo ? (
            <VideoPlayerPanel key={selectedVideo.videoId} video={selectedVideo} onChanged={load} />
          ) : (
            <div className="card detail-empty">O player do vídeo selecionado aparece aqui.</div>
          )}
        </div>
      </div>
    </div>
  );
}
