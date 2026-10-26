import { useEffect, useMemo, useState } from 'react';
import { api, Setting } from '../api';

export default function Settings() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const { settings } = await api.getSettings();
      setSettings(settings);
      setEdits({});
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  // Agrupa por categoria preservando a ordem.
  const groups = useMemo(() => {
    const map = new Map<string, Setting[]>();
    for (const s of settings) {
      if (!map.has(s.category)) map.set(s.category, []);
      map.get(s.category)!.push(s);
    }
    return Array.from(map.entries());
  }, [settings]);

  const valueOf = (s: Setting) => (s.settingKey in edits ? edits[s.settingKey] : s.value);
  const dirty = Object.keys(edits).length > 0;

  function onChange(key: string, v: string) {
    setEdits((e) => ({ ...e, [key]: v }));
  }

  async function save() {
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      await api.updateSettings(edits);
      setMsg('Configurações salvas. Novos processamentos já usam os novos valores (propaga em ~30s).');
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <h1>Configuração</h1>
      <p className="muted">
        Todos os parâmetros de comportamento (modelos, idiomas, tarifas, ajustes de legenda SDH,
        perfis de vídeo) ficam no DynamoDB e são editáveis aqui — sem alterar código nem redeploy.
      </p>

      {msg && <p className="success">{msg}</p>}
      {err && <p className="error">{err}</p>}

      {loading ? (
        <p className="muted">Carregando…</p>
      ) : (
        <>
          {groups.map(([category, items]) => (
            <div className="card" key={category}>
              <h2>{category}</h2>
              {items.map((s) => (
                <div className="setting" key={s.settingKey}>
                  <div className="setting-head">
                    <label>
                      {s.label} {s.unit ? <span className="muted">({s.unit})</span> : null}
                    </label>
                    <code className="mono setting-key">{s.settingKey}</code>
                  </div>
                  <p className="muted setting-desc">{s.description}</p>
                  {s.type === 'json' ? (
                    <textarea
                      rows={5}
                      className="mono"
                      value={valueOf(s)}
                      disabled={s.editable === false}
                      onChange={(e) => onChange(s.settingKey, e.target.value)}
                    />
                  ) : (
                    <input
                      type={s.type === 'number' ? 'number' : 'text'}
                      step="any"
                      value={valueOf(s)}
                      disabled={s.editable === false}
                      onChange={(e) => onChange(s.settingKey, e.target.value)}
                    />
                  )}
                </div>
              ))}
            </div>
          ))}

          <div className="save-bar">
            <button className="primary" onClick={save} disabled={!dirty || saving}>
              {saving ? 'Salvando…' : `Salvar${dirty ? ` (${Object.keys(edits).length})` : ''}`}
            </button>
            {dirty && (
              <button onClick={() => setEdits({})} disabled={saving}>
                Descartar alterações
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
