#!/usr/bin/env python3
"""
POC do WhisperX (ASR Whisper + alinhamento wav2vec2) rodando em CPU, pra simular
o que aconteceria num ECS Fargate (que NÃO tem GPU).

Mede: qualidade do texto, precisão dos tempos (vs Transcribe) e VELOCIDADE por
etapa (carga, transcrição, alinhamento) pra extrapolar custo/tempo no Fargate.

Entradas locais:
  /tmp/sdh-poc/track.wav        áudio 16kHz mono 16-bit
  /tmp/sdh-poc/transcribe.vtt   verdade de tempo (Amazon Transcribe)

Env: CLIP_SEC (90), WX_MODEL (large-v3)
"""
import os
import re
import time
import wave
import unicodedata

import numpy as np

POC = "/tmp/sdh-poc"
CLIP_SEC = float(os.environ.get("CLIP_SEC", "90"))
WX_MODEL = os.environ.get("WX_MODEL", "large-v3")
DEVICE = "cpu"


def load_wav_np(path, clip_sec):
    w = wave.open(path, "rb")
    sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
    want = min(n, int(clip_sec * sr))
    raw = w.readframes(want)
    w.close()
    assert sw == 2 and sr == 16000, "esperado PCM 16-bit 16kHz"
    data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data, data.shape[0] / sr


def ts_to_sec(ts):
    p = [float(x) for x in ts.strip().split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def parse_vtt(path):
    cues, block = [], []
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


def norm(t):
    t = unicodedata.normalize("NFD", t.lower().replace("\u2019", "'"))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r" +", " ", re.sub(r"[^a-z' ]", " ", t)).strip()


print(f"WhisperX POC | modelo={WX_MODEL} | device={DEVICE} | CLIP_SEC={CLIP_SEC}")
import whisperx
import torch

torch.set_num_threads(os.cpu_count() or 8)

audio, clip_real = load_wav_np(f"{POC}/track.wav", CLIP_SEC)
print(f"áudio: {clip_real:.1f}s\n")

# 1. carga do modelo ASR
t0 = time.time()
model = whisperx.load_model(WX_MODEL, DEVICE, compute_type="int8", language="pt")
t_load = time.time() - t0

# 2. transcrição (ASR)
t0 = time.time()
result = model.transcribe(audio, batch_size=4)
t_tr = time.time() - t0
segs = result["segments"]

# 3. carga do modelo de alinhamento (wav2vec2 pt) + alinhamento
t0 = time.time()
amodel, meta = whisperx.load_align_model(language_code="pt", device=DEVICE)
t_load_a = time.time() - t0
t0 = time.time()
aligned = whisperx.align(segs, amodel, meta, audio, DEVICE, return_char_alignments=False)
t_align = time.time() - t0

print(f"== TEMPOS (CPU, {os.cpu_count()} threads) ==")
print(f"  carga ASR:        {t_load:6.1f}s")
print(f"  transcrição:      {t_tr:6.1f}s  => {t_tr / clip_real:.3f}x do tempo real")
print(f"  carga alinhador:  {t_load_a:6.1f}s")
print(f"  alinhamento:      {t_align:6.1f}s  => {t_align / clip_real:.3f}x do tempo real")
print(f"  TOTAL compute (tr+align): {t_tr + t_align:6.1f}s => {(t_tr + t_align) / clip_real:.3f}x realtime\n")

# ---------- qualidade do texto ----------
print("== TEXTO do WhisperX (início, tempo) ==")
for s in aligned["segments"][:24]:
    print(f"  {s['start']:6.2f}  {s['text'].strip()[:60]}")

# ---------- precisão de tempo vs Transcribe ----------
words = []
for s in aligned["segments"]:
    for w in s.get("words", []):
        if "start" in w:
            words.append((norm(w["word"]), w["start"]))
gt = [(st, norm(tx)) for (st, tx) in parse_vtt(f"{POC}/transcribe.vtt") if st < clip_real - 3]

deltas = []
for gts, gtx in gt:
    toks = set(gtx.split())
    if not toks:
        continue
    # casa qualquer palavra da cue com uma palavra do WhisperX DENTRO de ±5s
    cand = [t for (w, t) in words if w in toks and abs(t - gts) <= 5.0]
    if cand:
        deltas.append(min(abs(t - gts) for t in cand))
if deltas:
    a = np.array(deltas)
    print(f"\n== PRECISÃO vs Transcribe (|Δ|): mediana={np.median(a):.2f}s média={a.mean():.2f}s "
          f"p90={np.percentile(a,90):.2f}s (n={len(a)}) ==")
