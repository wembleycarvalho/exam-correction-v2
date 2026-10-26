import { useEffect, useState } from 'react';
import { api, Video } from '../api';
import StatusBadge from '../components/StatusBadge';

type AnalyticsData = Awaited<ReturnType<typeof api.analytics>>;

// Formatação pt-BR: vírgula decimal, sem separador de milhar ambíguo.
const nf = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const usd = (n?: number | null) =>
  n == null ? '—' : n > 0 && n < 0.005 ? '< US$ 0,01' : nf.format(n);
const fmtTime = (ms?: number | null) =>
  ms == null ? '—' : ms < 90000 ? `${Math.round(ms / 1000)}s` : `${(ms / 60000).toFixed(1)} min`;

const VARIANT_ROWS: { method: string; label: string }[] = [
  { method: 'mini1p', label: 'Voxtral Mini (1 passada)' },
  { method: 'v24b1p', label: 'Voxtral 24B (1 passada)' },
  { method: 'v24b2p', label: 'Voxtral 24B (2 passadas)' },
];

function VideoDetail({ videoId }: { videoId: string }) {
  const [v, setV] = useState<Video | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setV(null);
    setErr(null);
    api
      .getVideo(videoId)
      .then((data) => {
        if (!cancelled) setV(data);
      })
      .catch((e) => {
        if (!cancelled) setErr(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  if (err) return <p className="error">{err}</p>;
  if (!v) return <p className="muted">Carregando detalhes…</p>;

  const c = v.cost || {};
  const variants = v.sdhVariants || {};

  return (
    <div className="card">
      <div className="review-head">
        <h2 style={{ margin: 0 }}>
          {v.title || '(sem título)'} <StatusBadge status={v.status} />
        </h2>
      </div>
      <p className="mono muted">{v.videoId}</p>

      <section>
        <h3>Geral</h3>
        <div className="row">
          <span className="muted">Duração: {v.durationSec ? `${Math.round(v.durationSec)}s` : '—'}</span>
          <span className="muted">· Plays: {v.playCount ?? 0}</span>
        </div>
      </section>

      <section>
        <h3>Custo estimado (por técnica)</h3>
        <table className="table">
          <tbody>
            {c.transcodeProfiles && c.transcodeProfiles.length > 0 ? (
              <>
                {c.transcodeProfiles.map((p) => (
                  <tr key={p.name}>
                    <td style={{ paddingLeft: 28 }} className="muted">
                      Transcode · {p.name} ({p.tier?.toUpperCase()})
                    </td>
                    <td>{usd(p.usd)}</td>
                  </tr>
                ))}
                <tr><td>Transcode (MediaConvert) — subtotal</td><td>{usd(c.transcodeUSD)}</td></tr>
              </>
            ) : (
              <tr><td>Transcode (MediaConvert)</td><td>{usd(c.transcodeUSD)}</td></tr>
            )}
            <tr><td>Legenda base (Transcribe)</td><td>{usd(c.transcribeUSD)}</td></tr>
            <tr><td>Legenda SDH · Voxtral Mini (1 passada)</td><td>{usd(variants.mini1p?.usd)}</td></tr>
            <tr><td>Legenda SDH · Voxtral 24B (1 passada)</td><td>{usd(variants.v24b1p?.usd)}</td></tr>
            <tr><td>Legenda SDH · Voxtral 24B (2 passadas)</td><td>{usd(variants.v24b2p?.usd)}</td></tr>
            <tr><td>Tradução (Translate)</td><td>{usd(c.translateUSD)}</td></tr>
            <tr><td>Descrição (Pegasus)</td><td>{usd(c.descriptionUSD)}</td></tr>
            <tr><td>Orquestração (Lambda + Step Functions)</td><td>{usd(c.orchestrationUSD)}</td></tr>
            <tr><td><strong>Total*</strong></td><td><strong>{usd(c.totalUSD)}</strong></td></tr>
          </tbody>
        </table>
        <p className="muted">
          * As variantes de legenda SDH são alternativas de comparação; o Total considera apenas
          uma faixa SDH (a última gerada).
        </p>
      </section>

      <section>
        <h3>Tempos</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Etapa</th>
              <th>Tempo</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Pipeline de transcoding (transcode + Transcribe)</td>
              <td>{fmtTime(v.pipelineMs)}</td>
            </tr>
            {VARIANT_ROWS.map((d) => {
              const x = variants[d.method];
              return (
                <tr key={d.method}>
                  <td>Legenda SDH — {d.label}</td>
                  <td>{fmtTime(x?.timeMs)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section>
        <h3>Avaliação de qualidade do texto</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Variante</th>
              <th>Nota (0-100)</th>
              <th>Consenso</th>
              <th>Juiz</th>
              <th>Custo do juiz</th>
            </tr>
          </thead>
          <tbody>
            {VARIANT_ROWS.map((d) => {
              const e = variants[d.method]?.eval;
              return (
                <tr key={d.method}>
                  <td>{d.label}</td>
                  <td>{e?.textConfidence ?? '—'}</td>
                  <td>{e?.consensusPct != null ? `${e.consensusPct}%` : '—'}</td>
                  <td>{e?.llmScore ?? '—'}</td>
                  <td>{usd(e?.costs?.judgeUSD)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="muted">
          Nota de confiança da qualidade do TEXTO (consenso Voxtral×Transcribe + LLM-juiz). Não
          avalia tempo/sincronismo.
        </p>
      </section>
    </div>
  );
}

export default function Analytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    api
      .analytics()
      .then(setData)
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="page">
      <h1>Analytics</h1>
      <p className="muted">
        Plays por vídeo e custo estimado de processamento. Clique numa linha para ver todos os
        dados do vídeo.
      </p>
      {err && <p className="error">{err}</p>}

      {data && (
        <>
          <div className="cards">
            <div className="metric">
              <div className="metric-value">{data.totals.totalPlays}</div>
              <div className="metric-label">Plays totais</div>
            </div>
            <div className="metric">
              <div className="metric-value">{data.totals.videoCount}</div>
              <div className="metric-label">Vídeos</div>
            </div>
            <div className="metric">
              <div className="metric-value">{usd(data.totals.estimatedCostUSD)}</div>
              <div className="metric-label">Custo estimado total</div>
            </div>
          </div>

          <table className="table">
            <thead>
              <tr>
                <th>Título</th>
                <th>Status</th>
                <th>Plays</th>
                <th>Custo total</th>
              </tr>
            </thead>
            <tbody>
              {data.videos.map((v) => (
                <tr
                  key={v.videoId}
                  className={v.videoId === selected ? 'sel' : ''}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelected(v.videoId === selected ? null : v.videoId)}
                >
                  <td>{v.title}</td>
                  <td>
                    <StatusBadge status={v.status} />
                  </td>
                  <td>{v.playCount}</td>
                  <td>{usd(v.cost?.totalUSD)}</td>
                </tr>
              ))}
              {data.videos.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    Nenhum dado ainda.
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {selected && (
            <div style={{ marginTop: 16 }}>
              <VideoDetail videoId={selected} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
