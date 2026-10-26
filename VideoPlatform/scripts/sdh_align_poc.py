#!/usr/bin/env python3
"""
POC de ALINHAMENTO FORÇADO (torchaudio MMS_FA) para validar a sincronia da
legenda SDH sem usar o Amazon Transcribe.

Ideia: pegar o TEXTO bom do 24B (que tem tempos ruins) e usar o alinhador MMS
para descobrir QUANDO cada palavra acontece no áudio. Compara os tempos obtidos
com os tempos do Transcribe (verdade de tempo) para medir o erro de sincronia.

Entradas (arquivos locais já baixados):
  /tmp/sdh-poc/track.wav       áudio 16kHz mono 16-bit
  /tmp/sdh-poc/24b.vtt         legenda do 24B (usamos só o TEXTO das falas)
  /tmp/sdh-poc/transcribe.vtt  legenda do Transcribe (verdade de tempo)

Env:
  CLIP_SEC (90)   segundos de áudio a processar
  LINES    (24)   nº de linhas de fala do 24B a alinhar
"""
import os
import re
import sys
import time
import wave
import unicodedata

import numpy as np
import torch

POC = "/tmp/sdh-poc"
CLIP_SEC = float(os.environ.get("CLIP_SEC", "90"))
LINES = int(os.environ.get("LINES", "24"))


# ---------- util: WAV e VTT ----------
def load_wav(path):
    w = wave.open(path, "rb")
    sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
    want = min(n, int((CLIP_SEC + 1) * sr))
    raw = w.readframes(want)
    w.close()
    assert sw == 2, "esperado PCM 16-bit"
    data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return torch.from_numpy(data).unsqueeze(0), sr


def ts_to_sec(ts):
    p = ts.strip().split(":")
    p = [float(x) for x in p]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def parse_vtt(path):
    cues = []
    block = []
    for line in open(path, encoding="utf-8").read().replace("\r", "").split("\n"):
        if line.strip() == "":
            if block:
                cues.append(block)
                block = []
        else:
            block.append(line)
    if block:
        cues.append(block)
    out = []
    for b in cues:
        ti = next((i for i, l in enumerate(b) if "-->" in l), -1)
        if ti < 0:
            continue
        start = ts_to_sec(b[ti].split("-->")[0])
        text = " ".join(b[ti + 1:]).strip()
        if text:
            out.append((start, text))
    return out


def normalize(text):
    text = text.lower().replace("\u2019", "'")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")  # tira acentos
    text = re.sub(r"[^a-z' ]", " ", text)
    text = re.sub(r" +", " ", text)
    return text.strip()


# ---------- 1. carrega modelo MMS_FA ----------
print(f"CLIP_SEC={CLIP_SEC}  LINES={LINES}")
t0 = time.time()
from torchaudio.pipelines import MMS_FA as bundle

device = "cpu"
model = bundle.get_model()
model.to(device)
tokenizer = bundle.get_tokenizer()
aligner = bundle.get_aligner()
SR = bundle.sample_rate
torch.set_num_threads(os.cpu_count() or 4)
print(f"modelo carregado em {time.time() - t0:.1f}s  | threads={torch.get_num_threads()}  | SR={SR}")

# ---------- 2. áudio ----------
waveform, sr = load_wav(f"{POC}/track.wav")
assert sr == SR, f"esperado {SR}Hz, veio {sr}Hz"
clip_sec_real = waveform.size(1) / SR

# emission é a parte cara: computa UMA vez e reusa nos dois alinhamentos.
t0 = time.time()
with torch.inference_mode():
    emission, _ = model(waveform.to(device))
t_emit = time.time() - t0
num_frames = emission.size(1)
ratio = waveform.size(1) / num_frames / SR  # segundos por frame
print(f"áudio: {clip_sec_real:.1f}s")
print(f"emission (forward do modelo): {t_emit:.2f}s  => {t_emit / clip_sec_real:.3f}s CPU por 1s de áudio\n")


def align_lines(lines_raw):
    """Alinha uma lista de linhas (texto cru). Retorna [(inicio_s, fim_s, texto)]."""
    words, line_of_word, lines_norm = [], [], []
    for li, raw in enumerate(lines_raw):
        ws = normalize(raw).split()
        lines_norm.append(ws)
        for w in ws:
            words.append(w)
            line_of_word.append(li)
    t0 = time.time()
    spans = aligner(emission[0], tokenizer(words))
    dt = time.time() - t0
    ws_start = [sp[0].start * ratio for sp in spans]
    ws_end = [sp[-1].end * ratio for sp in spans]
    ls, le = {}, {}
    for i, li in enumerate(line_of_word):
        ls.setdefault(li, ws_start[i])
        le[li] = ws_end[i]
    out = []
    for li, raw in enumerate(lines_raw):
        if li in ls:
            out.append((ls[li], le[li], raw))
    return out, dt, len(words)


# ---------- 3A. VALIDAÇÃO RIGOROSA: alinhar o PRÓPRIO texto do Transcribe ----------
# Mesmo texto do Transcribe -> casamento 1:1 com os tempos dele. Mede o erro
# PURO do alinhador MMS contra a referência de tempo que confiamos.
gt = [(st, tx) for (st, tx) in parse_vtt(f"{POC}/transcribe.vtt") if st < clip_sec_real - 3]
gt_lines = [tx for (_, tx) in gt]
aligned_gt, t_align_gt, nw_gt = align_lines(gt_lines)

print(f"== 3A. Alinhador vs Transcribe (mesmo texto, {len(gt)} cues, {nw_gt} palavras, align {t_align_gt:.2f}s) ==")
print("  MMS(s)  Transcribe(s)   Δ(s)   texto")
deltas = []
for (ms, me, tx), (gts, _) in zip(aligned_gt, gt):
    d = ms - gts
    deltas.append(abs(d))
    flag = "" if abs(d) <= 0.5 else ("  <<" if abs(d) <= 1.5 else "  <<<<")
    print(f"  {ms:6.2f}   {gts:10.2f}   {d:+5.2f}   {tx[:40]}{flag}")
arr = np.array(deltas)
print(f"\n  ERRO DO ALINHADOR (|Δ| vs Transcribe): mediana={np.median(arr):.2f}s  "
      f"média={arr.mean():.2f}s  p90={np.percentile(arr, 90):.2f}s  máx={arr.max():.2f}s  (n={len(arr)})\n")

# ---------- 3B. PATH DE PRODUÇÃO: alinhar o TEXTO do 24B ----------
speech_24b = [t for (_, t) in parse_vtt(f"{POC}/24b.vtt") if not t.startswith("[")][:LINES]
aligned_24b, t_align_24b, nw_24b = align_lines(speech_24b)
print(f"== 3B. Texto do 24B alinhado pelo MMS ({len(speech_24b)} falas, {nw_24b} palavras, align {t_align_24b:.2f}s) ==")
print("  (compare visualmente com a coluna Transcribe acima)")
print("  MMS(s)   texto do 24B")
for (ms, me, tx) in aligned_24b:
    print(f"  {ms:6.2f}   {tx[:52]}")
