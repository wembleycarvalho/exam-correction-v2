import { useEffect, useRef, useState } from 'react';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore - build compilado sem tipos
import shaka from 'shaka-player/dist/shaka-player.compiled.js';

import { langLabel } from '../labels';

export interface TextTrack {
  lang: string;
  url: string;
}

const subLabel = (l: string) => langLabel(l);

export interface DescSegment {
  start: number;
  end: number;
  text: string;
}

interface Props {
  hlsUrl: string;
  tracks?: TextTrack[];
  /** idioma de legenda ativo inicialmente */
  activeLang?: string;
  /** descrição do vídeo (Pegasus) para exibir sincronizada com o play */
  description?: DescSegment[];
}

/**
 * Player Shaka. ABR via HLS, legendas WebVTT selecionáveis. Envia credenciais
 * (cookies assinados) nas requisições de mídia. Mostra a resolução em reprodução
 * e permite fixar manualmente (Automático/1080p/720p/480p/360p).
 */
export default function VideoPlayer({ hlsUrl, tracks = [], activeLang, description = [] }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const playerRef = useRef<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [heights, setHeights] = useState<number[]>([]);
  const [currentHeight, setCurrentHeight] = useState<number | null>(null);
  const [mode, setMode] = useState<'auto' | number>('auto');
  const [subLang, setSubLang] = useState<string>('off');
  const [currentTime, setCurrentTime] = useState(0);
  // Mapa faixa(lang) -> id da text track no Shaka. Selecionamos pelo id exato,
  // porque vários langs começam com "pt" (pt-sdh, pt-sdh-mini...) e o Shaka
  // normaliza o idioma, confundindo a seleção por selectTextLanguage.
  const trackIdsRef = useRef<Record<string, number>>({});

  // Acompanha o tempo de reprodução (para a descrição sincronizada).
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const onTime = () => setCurrentTime(v.currentTime);
    v.addEventListener('timeupdate', onTime);
    return () => v.removeEventListener('timeupdate', onTime);
  }, []);

  const activeDescIdx = description.findIndex(
    (d) => currentTime >= d.start - 0.1 && currentTime < d.end + 0.1
  );
  const activeRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [activeDescIdx]);

  useEffect(() => {
    let destroyed = false;
    const video = videoRef.current;
    if (!video || !hlsUrl) return;

    async function init() {
      try {
        shaka.polyfill.installAll();
        if (!shaka.Player.isBrowserSupported()) {
          setError('Navegador não suportado pelo player.');
          return;
        }
        const player = new shaka.Player();
        await player.attach(video);
        playerRef.current = player;

        // Envia cookies (assinados) nas requisições de segmentos/manifesto.
        player.getNetworkingEngine().registerRequestFilter((_type: any, request: any) => {
          request.allowCrossSiteCredentials = true;
        });

        player.addEventListener('error', (e: any) => {
          setError(`Erro do player: ${e?.detail?.code ?? 'desconhecido'}`);
        });

        const refreshActive = () => {
          const vts = player.getVariantTracks();
          const uniq = Array.from(new Set(vts.map((t: any) => t.height).filter(Boolean))).sort(
            (a: any, b: any) => b - a
          );
          setHeights(uniq as number[]);
          const act = vts.find((t: any) => t.active);
          setCurrentHeight(act?.height ?? null);
        };
        player.addEventListener('adaptation', refreshActive);
        player.addEventListener('variantchanged', refreshActive);
        player.addEventListener('trackschanged', refreshActive);

        await player.load(hlsUrl);
        if (destroyed) return;
        refreshActive();

        trackIdsRef.current = {};
        for (const t of tracks) {
          try {
            const added = await player.addTextTrackAsync(t.url, t.lang, 'subtitles', 'text/vtt');
            if (added && added.id != null) trackIdsRef.current[t.lang] = added.id;
          } catch (err) {
            console.warn('Falha ao adicionar legenda', t.lang, err);
          }
        }
        if (tracks.length > 0) {
          const initial =
            activeLang && tracks.some((t) => t.lang === activeLang) ? activeLang : tracks[0].lang;
          player.setTextTrackVisibility(true);
          selectTrackByLang(player, initial);
          setSubLang(initial);
        } else {
          setSubLang('off');
        }
      } catch (e: any) {
        setError(e?.message || 'Falha ao carregar o vídeo');
      }
    }

    init();
    return () => {
      destroyed = true;
      if (playerRef.current) {
        playerRef.current.destroy();
        playerRef.current = null;
      }
    };
  }, [hlsUrl, JSON.stringify(tracks), activeLang]);

  // Seleciona a text track pelo ID exato mapeado (evita a confusão de idioma do Shaka).
  function selectTrackByLang(player: any, lang: string) {
    const id = trackIdsRef.current[lang];
    const track = player.getTextTracks().find((tt: any) => tt.id === id);
    if (track) {
      player.selectTextTrack(track);
      return true;
    }
    // Fallback: tenta por idioma (faixas padrão como 'pt', 'es', 'en').
    try {
      player.selectTextLanguage(lang);
    } catch (_) {
      /* ignora */
    }
    return false;
  }

  function selectSubtitle(value: string) {
    const player = playerRef.current;
    if (!player) return;
    setSubLang(value);
    if (value === 'off') {
      player.setTextTrackVisibility(false);
      return;
    }
    selectTrackByLang(player, value);
    player.setTextTrackVisibility(true);
  }

  function selectQuality(value: string) {
    const player = playerRef.current;
    if (!player) return;
    if (value === 'auto') {
      player.configure({ abr: { enabled: true } });
      setMode('auto');
      return;
    }
    const h = Number(value);
    const track = player.getVariantTracks().find((t: any) => t.height === h);
    if (track) {
      player.configure({ abr: { enabled: false } });
      player.selectVariantTrack(track, /* clearBuffer */ true);
      setMode(h);
      setCurrentHeight(h);
    }
  }

  return (
    <div className="player-wrap">
      <video
        ref={videoRef}
        controls
        playsInline
        style={{ width: '100%', background: '#000', borderRadius: 8 }}
      />
      {!error && (
        <div className="quality-bar">
          <span className="quality-badge">
            Assistindo: <strong>{currentHeight ? `${currentHeight}p` : '—'}</strong>
            {mode === 'auto' ? ' (automático)' : ' (fixo)'}
          </span>
          <div className="player-selects">
            {tracks.length > 0 && (
              <label className="quality-select">
                Legenda:
                <select value={subLang} onChange={(e) => selectSubtitle(e.target.value)}>
                  <option value="off">Desligada</option>
                  {tracks.map((t) => (
                    <option key={t.lang} value={t.lang}>
                      {subLabel(t.lang)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="quality-select">
              Qualidade:
              <select
                value={mode === 'auto' ? 'auto' : String(mode)}
                onChange={(e) => selectQuality(e.target.value)}
              >
                <option value="auto">Automático (ABR)</option>
                {heights.map((h) => (
                  <option key={h} value={h}>
                    {h}p
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      )}

      {description.length > 0 && (
        <div className="desc-panel">
          <div className="desc-title">Descrição do vídeo (acompanha o play)</div>
          <div className="desc-list">
            {description.map((d, i) => (
              <div
                key={i}
                ref={i === activeDescIdx ? activeRef : undefined}
                className={`desc-item ${i === activeDescIdx ? 'active' : ''}`}
                onClick={() => {
                  if (videoRef.current) videoRef.current.currentTime = d.start;
                }}
                title="Ir para este trecho"
              >
                <span className="desc-time mono">{fmt(d.start)}</span>
                <span className="desc-text">{d.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <p className="error">{error}</p>}
    </div>
  );
}

function fmt(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}
