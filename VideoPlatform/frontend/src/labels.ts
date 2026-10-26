// Rótulo amigável de uma faixa de legenda (lang), compondo idioma + variante.
// Ex.: pt -> "Português (Transcribe)"; pt-sdh -> "Português (SDH · 24B 1x)";
//      es -> "Espanhol"; es-sdh -> "Espanhol (SDH · 24B 1x)".

const BASE_NAME: Record<string, string> = {
  pt: 'Português',
  es: 'Espanhol',
  en: 'Inglês',
};

const SUFFIX_NAME: Record<string, string> = {
  '-sdh': 'SDH · 24B 1x',
  '-sdh-mini': 'SDH · Mini 1x',
  '-sdh-2p': 'SDH · 24B 2x',
};

export const TARGET_LANGS = ['es', 'en'];

/** Troca o prefixo "pt" da faixa de origem pelo idioma destino (pt-sdh -> es-sdh). */
export function translatedLang(sourceLang: string, target: string): string {
  return target + sourceLang.replace(/^pt/, '');
}

export function langLabel(lang: string): string {
  const m = /^(pt|es|en)(-.*)?$/.exec(lang);
  if (!m) return lang;
  const base = BASE_NAME[m[1]] || m[1];
  const suffix = m[2] || '';
  if (m[1] === 'pt' && suffix === '') return 'Português (Transcribe)';
  if (suffix === '') return base; // tradução a partir do Transcribe
  const sufName = SUFFIX_NAME[suffix] || suffix.slice(1);
  return `${base} (${sufName})`;
}
