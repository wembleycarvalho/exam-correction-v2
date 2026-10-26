/** Parser/serializer de WebVTT no cliente (editor de sincronismo). */

export interface Cue {
  id?: string;
  start: number;
  end: number;
  text: string;
}
export interface ParsedVtt {
  header: string;
  cues: Cue[];
}

export function parseVtt(content: string): ParsedVtt {
  const norm = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const blocks = norm.split(/\n\n+/);
  const cues: Cue[] = [];
  let header = 'WEBVTT';

  for (const block of blocks) {
    const lines = block.split('\n').filter((l) => l.length > 0);
    if (lines.length === 0) continue;
    if (lines[0].startsWith('WEBVTT')) {
      header = block.trim();
      continue;
    }
    const timingIdx = lines.findIndex((l) => l.includes('-->'));
    if (timingIdx === -1) continue;
    const id = timingIdx > 0 ? lines[0] : undefined;
    const timing = lines[timingIdx];
    const text = lines.slice(timingIdx + 1).join('\n');
    const [startStr, endRest] = timing.split('-->');
    const endStr = (endRest || '').trim().split(' ')[0];
    cues.push({ id, start: tsToSeconds(startStr.trim()), end: tsToSeconds(endStr.trim()), text });
  }
  return { header, cues };
}

export function serializeVtt(parsed: ParsedVtt): string {
  const parts = [parsed.header || 'WEBVTT'];
  parsed.cues.forEach((c, i) => {
    const idLine = c.id || String(i + 1);
    parts.push(`${idLine}\n${secondsToTs(c.start)} --> ${secondsToTs(c.end)}\n${c.text}`);
  });
  return parts.join('\n\n') + '\n';
}

export function shiftAll(parsed: ParsedVtt, offsetSec: number): ParsedVtt {
  return {
    ...parsed,
    cues: parsed.cues.map((c) => ({
      ...c,
      start: Math.max(0, c.start + offsetSec),
      end: Math.max(0, c.end + offsetSec),
    })),
  };
}

export function tsToSeconds(ts: string): number {
  const parts = ts.split(':');
  let h = 0;
  let m = 0;
  let s = 0;
  if (parts.length === 3) {
    h = parseInt(parts[0], 10);
    m = parseInt(parts[1], 10);
    s = parseFloat(parts[2]);
  } else if (parts.length === 2) {
    m = parseInt(parts[0], 10);
    s = parseFloat(parts[1]);
  } else {
    s = parseFloat(parts[0]);
  }
  return h * 3600 + m * 60 + s;
}

export function secondsToTs(total: number): string {
  const t = Math.max(0, total);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const ms = Math.round((t - Math.floor(t)) * 1000);
  const pad = (n: number, w = 2) => String(n).padStart(w, '0');
  return `${pad(h)}:${pad(m)}:${pad(s)}.${pad(ms, 3)}`;
}
