import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { parseVtt, secondsToTs, Cue } from '../vtt';
import { langLabel } from '../labels';

const label = (l: string) => langLabel(l);

/** Linha da timeline mesclada: tempo + texto de cada faixa (ou vazio). */
interface Row {
  t: number;
  a?: string;
  b?: string;
}

function mergeRows(a: Cue[], b: Cue[]): Row[] {
  // Pontos de início de ambas as faixas, ordenados.
  const points = Array.from(new Set([...a, ...b].map((c) => Math.round(c.start * 10) / 10))).sort(
    (x, y) => x - y
  );
  const at = (cues: Cue[], t: number) => {
    const matches = cues.filter((c) => t >= c.start - 0.05 && t < c.end + 0.05);
    if (matches.length === 0) return undefined;
    // Prefere o cue mais curto (a fala) sobre um evento longo que o cubra.
    matches.sort((x, y) => x.end - x.start - (y.end - y.start));
    return matches[0].text;
  };
  return points.map((t) => ({ t, a: at(a, t), b: at(b, t) }));
}

export default function SubtitleCompare({
  videoId,
  langs,
}: {
  videoId: string;
  langs: string[];
}) {
  const [langA, setLangA] = useState<string>(langs[0] || 'pt');
  const [langB, setLangB] = useState<string>(langs.find((l) => l !== (langs[0] || 'pt')) || langs[0] || 'pt');
  const [cuesA, setCuesA] = useState<Cue[]>([]);
  const [cuesB, setCuesB] = useState<Cue[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [wizLoading, setWizLoading] = useState(false);
  const [wiz, setWiz] = useState<{ analysis: string; usd: number; model: string; truncated: boolean } | null>(null);
  const [wizErr, setWizErr] = useState<string | null>(null);

  async function runWizard() {
    setWizErr(null);
    setWiz(null);
    setWizLoading(true);
    try {
      const r = await api.compareSubtitles(videoId, langA, langB, label(langA), label(langB));
      setWiz({ analysis: r.analysis, usd: r.usd, model: r.model, truncated: r.truncated });
    } catch (e: any) {
      setWizErr(e?.message || 'Falha na análise');
    } finally {
      setWizLoading(false);
    }
  }

  async function loadInto(lang: string, set: (c: Cue[]) => void) {
    try {
      const { content } = await api.getSubtitle(videoId, lang);
      set(parseVtt(content).cues);
    } catch {
      set([]);
    }
  }

  useEffect(() => {
    setLoading(true);
    setErr(null);
    Promise.all([loadInto(langA, setCuesA), loadInto(langB, setCuesB)]).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [langA, langB, videoId]);

  const rows = useMemo(() => mergeRows(cuesA, cuesB), [cuesA, cuesB]);

  return (
    <div className="compare">
      <div className="row">
        <label className="quality-select">
          Faixa A:
          <select value={langA} onChange={(e) => setLangA(e.target.value)}>
            {langs.map((l) => (
              <option key={l} value={l}>
                {label(l)}
              </option>
            ))}
          </select>
        </label>
        <label className="quality-select">
          Faixa B:
          <select value={langB} onChange={(e) => setLangB(e.target.value)}>
            {langs.map((l) => (
              <option key={l} value={l}>
                {label(l)}
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary"
          onClick={runWizard}
          disabled={wizLoading || langA === langB}
          title="Análise comparativa por IA"
        >
          {wizLoading ? 'Analisando…' : '✨ Wizard (análise por IA)'}
        </button>
      </div>
      {err && <p className="error">{err}</p>}

      {wizErr && <p className="error">{wizErr}</p>}
      {wiz && (
        <div className="wizard-panel">
          <div className="wizard-head">
            Análise comparativa — {label(langA)} × {label(langB)}
            <span className="muted">
              {' '}
              · {wiz.model.split('.').pop()} · US$ {wiz.usd.toFixed(4)}
              {wiz.truncated ? ' · amostra (faixa longa)' : ''}
            </span>
          </div>
          <div className="wizard-body">{wiz.analysis}</div>
        </div>
      )}
      {loading ? (
        <p className="muted">Carregando…</p>
      ) : (
        <div className="compare-grid">
          <div className="compare-head">Tempo</div>
          <div className="compare-head">{label(langA)}</div>
          <div className="compare-head">{label(langB)}</div>
          {rows.map((r, i) => (
            <div className="compare-rowgroup" key={i}>
              <div className="compare-time mono">{secondsToTs(r.t).slice(0, 8)}</div>
              <div className={`compare-cell ${r.a ? '' : 'empty'}`}>{r.a || '—'}</div>
              <div className={`compare-cell ${r.b ? '' : 'empty'}`}>{r.b || '—'}</div>
            </div>
          ))}
          {rows.length === 0 && <div className="muted">Sem conteúdo para comparar.</div>}
        </div>
      )}
    </div>
  );
}
