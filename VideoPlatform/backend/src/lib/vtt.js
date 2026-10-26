'use strict';

/** Parser/serializer mínimo de WebVTT (suficiente para legendas do Transcribe). */

/**
 * @returns {{header:string, cues: Array<{id?:string,timing:string,start:number,end:number,text:string}>}}
 */
function parseVtt(content) {
  const normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const blocks = normalized.split(/\n\n+/);
  const cues = [];
  let header = 'WEBVTT';

  for (const block of blocks) {
    const lines = block.split('\n').filter((l) => l.length > 0);
    if (lines.length === 0) continue;
    if (lines[0].startsWith('WEBVTT')) {
      header = block.trim();
      continue;
    }
    // Acha a linha de timing (contém "-->").
    const timingIdx = lines.findIndex((l) => l.includes('-->'));
    if (timingIdx === -1) continue; // bloco NOTE/STYLE etc.
    const id = timingIdx > 0 ? lines[0] : undefined;
    const timing = lines[timingIdx];
    const text = lines.slice(timingIdx + 1).join('\n');
    const [startStr, endRest] = timing.split('-->');
    const endStr = (endRest || '').trim().split(' ')[0];
    cues.push({
      id,
      timing: timing.trim(),
      start: tsToSeconds(startStr.trim()),
      end: tsToSeconds(endStr.trim()),
      text,
    });
  }
  return { header, cues };
}

function serializeVtt({ header = 'WEBVTT', cues }) {
  const parts = [header];
  cues.forEach((c, i) => {
    const idLine = c.id || String(i + 1);
    const timing = c.timing || `${secondsToTs(c.start)} --> ${secondsToTs(c.end)}`;
    parts.push(`${idLine}\n${timing}\n${c.text}`);
  });
  return parts.join('\n\n') + '\n';
}

function tsToSeconds(ts) {
  // formatos: HH:MM:SS.mmm ou MM:SS.mmm
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

function secondsToTs(total) {
  const t = Math.max(0, total);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const ms = Math.round((t - Math.floor(t)) * 1000);
  const pad = (n, w = 2) => String(n).padStart(w, '0');
  return `${pad(h)}:${pad(m)}:${pad(s)}.${pad(ms, 3)}`;
}

/** Desloca todos os cues por offsetSec (positivo = adianta no tempo). */
function shiftVtt(parsed, offsetSec) {
  const cues = parsed.cues.map((c) => {
    const start = c.start + offsetSec;
    const end = c.end + offsetSec;
    return { ...c, start, end, timing: `${secondsToTs(start)} --> ${secondsToTs(end)}` };
  });
  return { ...parsed, cues };
}

module.exports = { parseVtt, serializeVtt, tsToSeconds, secondsToTs, shiftVtt };
