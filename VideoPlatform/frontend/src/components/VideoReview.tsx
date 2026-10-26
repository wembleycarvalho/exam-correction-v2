import { useEffect, useMemo, useRef, useState } from 'react';
import { api, Video, SdhVariant } from '../api';
import { parseVtt, serializeVtt, shiftAll, secondsToTs, ParsedVtt } from '../vtt';
import { langLabel, translatedLang, TARGET_LANGS } from '../labels';
import StatusBadge from './StatusBadge';
import SubtitleCompare from './SubtitleCompare';

// Variantes de legenda por IA (protótipo) para comparar qualidade × tempo × custo.
const VARIANT_DEFS: { method: string; label: string; lang: string }[] = [
  { method: 'mini1p', label: 'Voxtral Mini (1 passada)', lang: 'pt-sdh-mini' },
  { method: 'v24b1p', label: 'Voxtral 24B (1 passada)', lang: 'pt-sdh' },
  { method: 'v24b2p', label: 'Voxtral 24B (2 passadas)', lang: 'pt-sdh-2p' },
];

const usdFmt = (n?: number | null) =>
  n == null
    ? '—'
    : n > 0 && n < 0.005
      ? '< US$ 0,01'
      : new Intl.NumberFormat('pt-BR', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }).format(n);

/** Rótulo + classe de cor para a nota de confiança do texto (0-100). */
function confInfo(score?: number | null): { label: string; cls: string } {
  if (score == null) return { label: '—', cls: 'muted' };
  if (score >= 85) return { label: `Alta (${score})`, cls: 'success' };
  if (score >= 65) return { label: `Média (${score})`, cls: '' };
  return { label: `Baixa (${score})`, cls: 'error' };
}

export default function VideoReview({
  video,
  onClose,
  onChanged,
}: {
  video: Video;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [title, setTitle] = useState(video.title || '');
  const [description, setDescription] = useState(video.description || '');
  const [editLang, setEditLang] = useState('pt');
  const [translateSource, setTranslateSource] = useState('pt');
  const [parsed, setParsed] = useState<ParsedVtt | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [job, setJob] = useState<null | 'sdh' | 'describe'>(null);
  const pollRef = useRef<number | null>(null);
  const [variants, setVariants] = useState<Record<string, SdhVariant>>(video.sdhVariants || {});
  const varPollRef = useRef<number | null>(null);
  const [evaluating, setEvaluating] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      if (varPollRef.current) window.clearInterval(varPollRef.current);
    };
  }, []);

  useEffect(() => {
    setVariants(video.sdhVariants || {});
  }, [video.videoId, video.sdhVariants]);

  // Retoma o acompanhamento da descrição se já estiver em andamento (reabriu a tela).
  useEffect(() => {
    if (video.descriptionStatus === 'processando') {
      setJob('describe');
      pollJob('descriptionStatus', 'descriptionError', 'Descrição');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video.videoId]);

  // "Gerando" vale tanto para o disparo local quanto para o status persistido.
  const describing = job === 'describe' || video.descriptionStatus === 'processando';

  const availableLangs = useMemo(() => {
    const set = new Set<string>(['pt']);
    (video.subtitles || []).forEach((s) => set.add(s.lang));
    Object.values(variants).forEach((v) => {
      if (v?.lang && v.status === 'pronto') set.add(v.lang);
    });
    return [...set];
  }, [video, variants]);

  function ensureVariantPoll() {
    if (varPollRef.current) return;
    varPollRef.current = window.setInterval(async () => {
      try {
        const v = await api.getVideo(video.videoId);
        setVariants(v.sdhVariants || {});
        const running = Object.values(v.sdhVariants || {}).some((x) => x?.status === 'processando');
        if (!running && varPollRef.current) {
          window.clearInterval(varPollRef.current);
          varPollRef.current = null;
          onChanged();
        }
      } catch {
        /* ignore transient */
      }
    }, 5000);
  }

  async function startVariant(method: string) {
    setErr(null);
    try {
      await api.startSdh(video.videoId, method);
      setVariants((prev) => ({
        ...prev,
        [method]: { ...(prev[method] || { lang: '' }), status: 'processando', error: '' },
      }));
      note('Variante de legenda em processamento (IA de áudio)…');
      ensureVariantPoll();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function evaluateVariant(method: string) {
    setErr(null);
    setEvaluating(method);
    try {
      const r = await api.evaluateSubtitle(video.videoId, method);
      setVariants((prev) => ({
        ...prev,
        [method]: { ...(prev[method] || { lang: '' }), eval: r.eval },
      }));
      note('Avaliação de qualidade concluída.');
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setEvaluating(null);
    }
  }

  async function loadSubtitle(lang: string) {
    setErr(null);
    try {
      const { content } = await api.getSubtitle(video.videoId, lang);
      setParsed(parseVtt(content));
    } catch (e: any) {
      setParsed(null);
      setErr(`Sem legenda em ${langLabel(lang)}`);
    }
  }

  useEffect(() => {
    loadSubtitle(editLang);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editLang, video.videoId]);

  function note(m: string) {
    setMsg(m);
    setErr(null);
    window.setTimeout(() => setMsg(null), 3000);
  }

  function applyShift(delta: number) {
    if (!parsed) return;
    setParsed(shiftAll(parsed, delta));
  }

  function updateCue(i: number, field: 'start' | 'end' | 'text', value: string) {
    if (!parsed) return;
    const cues = parsed.cues.map((c, idx) => {
      if (idx !== i) return c;
      if (field === 'text') return { ...c, text: value };
      const num = parseFloat(value);
      return { ...c, [field]: isNaN(num) ? c[field] : num };
    });
    setParsed({ ...parsed, cues });
  }

  async function saveMeta() {
    setBusy(true);
    try {
      await api.updateVideo(video.videoId, { title, description });
      note('Metadados salvos');
      onChanged();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveSubtitle() {
    if (!parsed) return;
    setBusy(true);
    try {
      await api.putSubtitle(video.videoId, editLang, serializeVtt(parsed), 0);
      note('Legenda salva');
      onChanged();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function translateTo(target: string) {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.translate(video.videoId, target, translateSource);
      note(`Tradução gerada: ${langLabel(r.lang)}`);
      onChanged();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  function pollJob(field: 'sdhStatus' | 'descriptionStatus', errorField: 'sdhError' | 'descriptionError', label: string, onReady?: () => void) {
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        const v = await api.getVideo(video.videoId);
        if (v[field] === 'pronto') {
          if (pollRef.current) window.clearInterval(pollRef.current);
          setJob(null);
          note(`${label} pronta!`);
          onChanged();
          onReady?.();
        } else if (v[field] === 'erro') {
          if (pollRef.current) window.clearInterval(pollRef.current);
          setJob(null);
          setErr(`${label} falhou: ${v[errorField] || ''}`);
          onChanged();
        }
      } catch {
        /* ignore transient */
      }
    }, 5000);
  }

  async function genDescription() {
    setErr(null);
    setJob('describe');
    try {
      await api.startDescribe(video.videoId);
      note('Descrição do vídeo em processamento (Pegasus)…');
      pollJob('descriptionStatus', 'descriptionError', 'Descrição');
    } catch (e: any) {
      setErr(e.message);
      setJob(null);
    }
  }

  async function publish() {
    setBusy(true);
    setErr(null);
    try {
      await api.publishVideo(video.videoId);
      note('Publicado! Status: pronto');
      onChanged();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function unpublish() {
    setBusy(true);
    setErr(null);
    try {
      await api.unpublishVideo(video.videoId);
      note('Despublicado. Status: revisar (não aparece mais no Player).');
      onChanged();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm('Excluir este vídeo e todos os arquivos? Esta ação é irreversível.')) return;
    setBusy(true);
    try {
      await api.deleteVideo(video.videoId);
      onChanged();
      onClose();
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  }

  return (
    <div className="review card">
      <div className="review-head">
        <h2>
          Revisão <StatusBadge status={video.status} />
        </h2>
        <button className="link" onClick={onClose}>
          Fechar
        </button>
      </div>
      <p className="mono muted">{video.videoId}</p>
      {msg && <p className="success">{msg}</p>}
      {err && <p className="error">{err}</p>}

      {/* Metadados */}
      <section>
        <h3>Informações</h3>
        <label>Título</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
        <label>Descrição</label>
        <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
        <button className="primary" onClick={saveMeta} disabled={busy}>
          Salvar informações
        </button>
      </section>

      {/* Legenda + sincronismo */}
      <section>
        <h3>Legenda e sincronismo</h3>
        <div className="row">
          <label>Idioma:</label>
          <select value={editLang} onChange={(e) => setEditLang(e.target.value)}>
            {availableLangs.map((l) => (
              <option key={l} value={l}>
                {langLabel(l)}
              </option>
            ))}
          </select>
        </div>

        {parsed ? (
          <>
            <div className="row">
              <span className="muted">Ajuste global (todos os cues):</span>
              <button onClick={() => applyShift(-1)}>-1s</button>
              <button onClick={() => applyShift(-0.5)}>-0,5s</button>
              <button onClick={() => applyShift(0.5)}>+0,5s</button>
              <button onClick={() => applyShift(1)}>+1s</button>
            </div>

            <div className="cues">
              {parsed.cues.map((c, i) => (
                <div className="cue" key={i}>
                  <div className="cue-times">
                    <input
                      type="number"
                      step="0.1"
                      value={c.start.toFixed(3)}
                      onChange={(e) => updateCue(i, 'start', e.target.value)}
                      title={secondsToTs(c.start)}
                    />
                    <span>→</span>
                    <input
                      type="number"
                      step="0.1"
                      value={c.end.toFixed(3)}
                      onChange={(e) => updateCue(i, 'end', e.target.value)}
                      title={secondsToTs(c.end)}
                    />
                  </div>
                  <input
                    className="cue-text"
                    value={c.text}
                    onChange={(e) => updateCue(i, 'text', e.target.value)}
                  />
                </div>
              ))}
            </div>

            <div className="row">
              <button className="primary" onClick={saveSubtitle} disabled={busy}>
                Salvar legenda ({langLabel(editLang)})
              </button>
            </div>
          </>
        ) : (
          <p className="muted">Nenhuma legenda carregada para este idioma.</p>
        )}
      </section>

      {/* Idiomas / tradução */}
      <section>
        <h3>Tradução de legendas</h3>
        <p className="muted">
          Escolha a legenda de <strong>origem</strong> (qualquer uma em português) e o idioma de
          <strong> destino</strong>. A tradução preserva a variante (ex.: <code>pt-sdh</code> →{' '}
          <code>es-sdh</code>).
        </p>
        <div className="row">
          <label>Origem:</label>
          <select value={translateSource} onChange={(e) => setTranslateSource(e.target.value)}>
            {availableLangs
              .filter((l) => l.startsWith('pt'))
              .map((l) => (
                <option key={l} value={l}>
                  {langLabel(l)}
                </option>
              ))}
          </select>
        </div>
        <div className="row">
          {TARGET_LANGS.map((t) => {
            const out = translatedLang(translateSource, t);
            const exists = availableLangs.includes(out);
            return (
              <button key={t} onClick={() => translateTo(t)} disabled={busy || exists}>
                {exists ? `${langLabel(out)} ✓` : `Traduzir p/ ${langLabel(t)}`}
              </button>
            );
          })}
        </div>
      </section>

      {/* Legenda por IA de áudio (Voxtral) — comparação de variantes (protótipo) */}
      <section>
        <h3>Legenda por IA (áudio) — comparação de modelos</h3>
        <p className="muted">
          O modelo de áudio <strong>Voxtral</strong> (Bedrock) ouve o áudio e gera a legenda com a
          fala <em>e</em> os marcadores de som (<code>[música]</code>, <code>[risos]</code>,{' '}
          <code>[suspiro]</code>) posicionados <strong>só nas pausas</strong> da fala. Gere por
          diferentes variantes e compare <strong>tempo × custo × qualidade</strong>. A faixa{' '}
          <strong>Português (Transcribe)</strong> já existe como referência (sem marcadores).
        </p>
        <div className="row">
          {VARIANT_DEFS.map((d) => {
            const st = variants[d.method]?.status;
            const done = st === 'pronto';
            return (
              <button key={d.method} onClick={() => startVariant(d.method)} disabled={busy || st === 'processando'}>
                {st === 'processando' ? `${d.label}…` : done ? `Regerar ${d.label}` : d.label}
              </button>
            );
          })}
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Opção</th>
              <th>Faixa (legenda)</th>
              <th>Status</th>
              <th>Tempo</th>
              <th>Qualidade do texto</th>
            </tr>
          </thead>
          <tbody>
            {VARIANT_DEFS.map((d) => {
              const v = variants[d.method];
              const ev = v?.eval;
              const ci = confInfo(ev?.textConfidence);
              return (
                <tr key={d.method}>
                  <td>{d.label}</td>
                  <td className="mono">{d.lang}</td>
                  <td>
                    {v?.status ? <StatusBadge status={v.status} /> : '—'}
                    {v?.status === 'erro' && v.error && <span className="muted"> {v.error}</span>}
                  </td>
                  <td>{v?.timeMs != null ? `${(v.timeMs / 1000).toFixed(0)}s` : '—'}</td>
                  <td>
                    {ev?.textConfidence != null ? (
                      <span className={ci.cls}>{ci.label}</span>
                    ) : (
                      <span className="muted">—</span>
                    )}{' '}
                    {v?.status === 'pronto' && (
                      <button
                        className="link"
                        onClick={() => evaluateVariant(d.method)}
                        disabled={evaluating === d.method}
                      >
                        {evaluating === d.method ? 'avaliando…' : ev ? 'reavaliar' : 'avaliar'}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Avaliação de qualidade do TEXTO (nota do juiz + comentário + métodos + custos + flags) */}
        {VARIANT_DEFS.map((d) => {
          const ev = variants[d.method]?.eval;
          if (!ev) return null;
          const ci = confInfo(ev.textConfidence);
          return (
            <div className="wizard-panel" key={`ev-${d.method}`}>
              <div className="wizard-head">
                Avaliação de texto — {d.label}{' '}
                <span className="muted">
                  · nota <strong className={ci.cls}>{ev.textConfidence ?? '—'}</strong>/100
                  {ev.consensusPct != null ? ` · consenso ${ev.consensusPct}%` : ''}
                  {ev.llmScore != null ? ` · juiz ${ev.llmScore}` : ''}
                </span>
              </div>
              <div className="wizard-body">
                {ev.comment && <p>{ev.comment}</p>}
                <p className="muted">
                  Métodos: {ev.methods?.join(', ') || '—'} · Custos — Transcribe{' '}
                  {usdFmt(ev.costs?.transcribeUSD)} · Voxtral {usdFmt(ev.costs?.voxtralUSD)} · Juiz{' '}
                  {usdFmt(ev.costs?.judgeUSD)}
                </p>
                {ev.flags && ev.flags.length > 0 && (
                  <ul className="eval-flags">
                    {ev.flags.map((f, i) => (
                      <li key={i}>
                        <span className="mono">{f.time}</span> — {f.issue}
                      </li>
                    ))}
                  </ul>
                )}
                {ev.truncated && <p className="muted">(análise por amostra — faixa longa)</p>}
              </div>
            </div>
          );
        })}

        <p className="muted">
          <strong>Faixa</strong> = identificador da legenda (selecionável no player); arquivo no S3:{' '}
          <code>{video.videoId}.&lt;faixa&gt;.vtt</code>. A nota avalia só o <strong>texto</strong>{' '}
          (acerto das palavras vs. o áudio). Modelo, tokens, nº de falas e marcadores ficam no{' '}
          <strong>Analytics</strong>.
        </p>
      </section>

      {/* Assets gerados para o vídeo */}
      <section>
        <h3>Assets gerados</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Asset</th>
              <th>Tipo</th>
              <th>Arquivo (S3)</th>
            </tr>
          </thead>
          <tbody>
            {availableLangs.map((l) => (
              <tr key={l}>
                <td>{langLabel(l)}</td>
                <td>Legenda (VTT)</td>
                <td className="mono">legenda/{video.videoId}.{l}.vtt</td>
              </tr>
            ))}
            {video.descriptionStatus === 'pronto' && (
              <tr>
                <td>Descrição do vídeo (Pegasus)</td>
                <td>JSON</td>
                <td className="mono">description/description.json</td>
              </tr>
            )}
            <tr>
              <td>Vídeo adaptativo (ABR)</td>
              <td>HLS</td>
              <td className="mono">hls/master.m3u8</td>
            </tr>
          </tbody>
        </table>
        <p className="muted">
          Caminhos relativos ao prefixo do vídeo no S3. O avaliador <strong>não</strong> cria uma
          legenda nova — ele dá a nota de qualidade da legenda do Voxtral.
        </p>
      </section>

      {/* Descrição do vídeo (Pegasus) */}
      <section>
        <h3>Descrição do vídeo (IA)</h3>
        <p className="muted">
          O modelo de vídeo <strong>Pegasus</strong> (TwelveLabs/Bedrock) descreve o conteúdo em
          segmentos cronológicos (cena, ação, áudio), exibidos acompanhando o vídeo no player.
        </p>
        <div className="row">
          <button className="primary" onClick={genDescription} disabled={busy || describing}>
            {describing
              ? '⏳ Gerando descrição…'
              : video.descriptionStatus === 'pronto'
                ? 'Regerar descrição'
                : 'Gerar descrição'}
          </button>
          {describing && <span className="muted">em andamento (pode sair da tela)</span>}
          {!describing && video.descriptionStatus === 'pronto' && (
            <span className="success">descrição ✓</span>
          )}
          {!describing && video.descriptionStatus === 'erro' && (
            <span className="error">falhou — {video.descriptionError || 'tente de novo'}</span>
          )}
        </div>
      </section>

      {/* Comparar duas legendas lado a lado */}
      {availableLangs.length >= 2 && (
        <section>
          <h3>Comparar legendas (lado a lado)</h3>
          <SubtitleCompare videoId={video.videoId} langs={availableLangs} />
        </section>
      )}

      {/* Ações de status */}
      <section className="actions">
        {video.status === 'revisar' && (
          <button className="primary" onClick={publish} disabled={busy || !title}>
            Publicar (marcar como pronto)
          </button>
        )}
        {video.status === 'pronto' && (
          <button onClick={unpublish} disabled={busy}>
            Despublicar (voltar para revisar)
          </button>
        )}
        <button className="danger" onClick={remove} disabled={busy}>
          Excluir vídeo
        </button>
      </section>
    </div>
  );
}
