#!/usr/bin/env python3
"""Gera 1 vídeo-aula por disciplina para a demo do módulo LMS (busca em vídeo).

Fonte da verdade: orientador-academico/data/disciplines.json (89 disciplinas, compartilhadas
entre os 6 cursos → 1 vídeo por disciplina).

Cada vídeo tem N capítulos em timestamps conhecidos. Por capítulo:
  - imagem de fundo temática gerada por IA (Bedrock Stability), com efeito Ken Burns (zoom/pan);
  - faixa escura (scrim) + tipografia: marca, disciplina, tema do capítulo, área/créditos/semestre;
  - narração do TEMA via Amazon Polly (voz pt-BR neural) — substitui o antigo beep.
Assim dá para demonstrar as buscas do Marengo: por texto (pular ao trecho), por cena/objeto
(imagens distintas) e por áudio (narração real por capítulo).

CONTEÚDO SINTÉTICO, sem valor pedagógico — só para demonstração.

Uso:
  python3 build_lms_videos.py --only disc_029     # gera só uma (avaliação)
  python3 build_lms_videos.py                      # gera o que falta (pula existentes)
  python3 build_lms_videos.py --force              # regenera tudo
  python3 build_lms_videos.py --limit 5 | --area Computação
  python3 build_lms_videos.py --no-images          # fundo gradiente (sem Bedrock imagem)
  python3 build_lms_videos.py --no-narration       # silêncio (sem Polly)
"""
import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent.parent / "orientador-academico" / "data"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
VIDEOS = HERE / "videos"
IMAGES = HERE / "images"
AUDIO = HERE / "audio"
CACHE = HERE / "chapters_cache.json"
MANIFEST = HERE / "manifest.json"

W, H, FPS = 1280, 720, 25
SEG = 15       # segundos por capítulo (padrão p/ ~2 min com 8 capítulos)
CHAPTERS = 8   # capítulos por vídeo (8 x 15s = 120s)
REGION = os.environ.get("AWS_REGION", "us-east-1")
CHAPTERS_MODEL = os.environ.get("LMS_CHAPTERS_MODEL", "amazon.nova-lite-v1:0")
IMAGE_MODEL = os.environ.get("LMS_IMAGE_MODEL", "stability.stable-image-ultra-v1:1")
IMAGE_REGION = os.environ.get("LMS_IMAGE_REGION", "us-west-2")
# Vozes pt-BR neural mescladas por capítulo (rotação).
VOICES = [v.strip() for v in os.environ.get("LMS_POLLY_VOICES", "Camila,Thiago,Vitoria").split(",") if v.strip()]

# Ritmo: duração de cada capítulo = LEAD (silêncio antes) + fala + TAIL (respiro depois),
# com um mínimo. Assim não há intervalos longos de silêncio entre os temas.
LEAD = 0.4
TAIL = 1.2
MIN_SEG = 3.0
FALLBACK_SEG = 5.0  # quando não há narração (--no-narration)

BRAND = "A Arte do Possível - LMS"
GENERIC = ["Introdução", "Conceitos Fundamentais", "Aplicações", "Estudo de Caso"]
# fundo gradiente por posição (fallback quando --no-images)
GRAD = [("0x1b2a4a", "0x2a4a7a"), ("0x0b6e4f", "0x12a06f"), ("0xb5651d", "0xe0872a"),
        ("0x5a2a83", "0x8a4bb0")]

_chapters_client = None
_image_client = None
_polly = None


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower() or "disc"


def sanitize(text: str) -> str:
    """Remove caracteres que quebram o parser de filtros do ffmpeg (drawtext)."""
    text = text.replace(":", " -").replace(",", " ").replace("%", " ")
    text = text.replace("'", "").replace("\\", "").replace("[", "(").replace("]", ")")
    return re.sub(r"\s+", " ", text).strip()[:52]


def seed_of(*parts) -> int:
    h = hashlib.md5("::".join(map(str, parts)).encode()).hexdigest()
    return int(h[:8], 16) % 4294967294


# ---------------- capítulos (Bedrock Nova Lite, cacheado) ----------------
def load_cache() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def save_cache(c: dict):
    CACHE.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")


def get_chapters(disc: dict, cache: dict, use_bedrock: bool, n: int) -> list:
    did = disc["id"]
    cached = cache.get(did)
    if cached and len(cached.get("chapters", [])) >= n:
        return cached["chapters"][:n]
    chapters = None
    if use_bedrock:
        global _chapters_client
        try:
            if _chapters_client is None:
                import boto3
                _chapters_client = boto3.client("bedrock-runtime", region_name=REGION)
            prompt = (
                f"Liste exatamente {n} tópicos/capítulos, em ordem didática, de uma aula da "
                f"disciplina '{disc['name']}' (área de {disc['area']}). Responda apenas com os {n} "
                f"itens, um por linha, em português do Brasil, cada um com no máximo 4 palavras, sem "
                f"numeração, sem marcadores, sem pontuação final."
            )
            resp = _chapters_client.invoke_model(
                modelId=CHAPTERS_MODEL, contentType="application/json", accept="application/json",
                body=json.dumps({"messages": [{"role": "user", "content": [{"text": prompt}]}],
                                 "inferenceConfig": {"maxTokens": 60 + 20 * n, "temperature": 0.4}}))
            txt = json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"]
            lines = [re.sub(r"^[\-\d\.\)\s]+", "", ln).strip() for ln in txt.splitlines()]
            lines = [ln for ln in lines if ln]
            if len(lines) >= max(3, n - 2):
                chapters = lines[:n]
        except Exception as e:  # noqa: BLE001
            print(f"    [chapters] {did} falhou ({e}); genérico", file=sys.stderr)
    if not chapters:
        base = list(GENERIC)
        while len(base) < n:
            base.append(f"Tópico {len(base) + 1}")
        chapters = base[:n]
    chapters = [sanitize(c) for c in chapters][:n]
    cache[did] = {"name": disc["name"], "chapters": chapters}
    return chapters


# ---------------- imagem de fundo (Bedrock Stability, cacheada) ----------------
def get_background(disc: dict, idx: int, chapter: str) -> Path | None:
    d = IMAGES / disc["id"]
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{idx}.png"
    if out.exists():
        return out
    global _image_client
    import base64
    import boto3
    if _image_client is None:
        _image_client = boto3.client("bedrock-runtime", region_name=IMAGE_REGION)
    negative = ("text, words, letters, typography, watermark, logo, ui, blurry, low quality, "
                "deformed, extra limbs")
    # Erros de credencial/permissão são "duros" (propaga → pula o vídeo p/ rerun); filtro de
    # conteúdo / falha transitória → tenta outra seed e, no fim, cai no gradiente daquele cap.
    AUTH = ("ExpiredToken", "UnrecognizedClient", "AccessDenied", "InvalidSignature")
    prompts = [
        f"Professional editorial illustration about {chapter} in the context of "
        f"{disc['name']} ({disc['area']}). Modern flat vector style, vibrant colors, clear "
        f"single subject, clean composition, no text, no words, 16:9.",
        f"Simple flat vector illustration representing {disc['area']}, abstract geometric shapes, "
        f"vibrant colors, clean composition, no text, 16:9.",  # fallback mais genérico/seguro
    ]
    for attempt in range(4):
        prompt = prompts[min(attempt // 2, len(prompts) - 1)]
        body = {"prompt": prompt[:1900], "negative_prompt": negative, "aspect_ratio": "16:9",
                "mode": "text-to-image", "output_format": "png",
                "seed": seed_of(disc["id"], idx, attempt)}
        try:
            resp = _image_client.invoke_model(modelId=IMAGE_MODEL, contentType="application/json",
                                              accept="application/json", body=json.dumps(body))
            payload = json.loads(resp["body"].read())
            imgs = payload.get("images")
            if imgs:
                out.write_bytes(base64.b64decode(imgs[0]))
                return out
            # sem imagens (provável filtro de conteúdo) — tenta outra seed/prompt
            print(f"    [image] {disc['id']}/{idx} sem imagens "
                  f"({payload.get('finish_reasons') or 'desconhecido'}); tentativa {attempt+1}",
                  file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            if any(a in type(e).__name__ or a in str(e) for a in AUTH):
                raise  # credencial/permissão -> falha dura
            print(f"    [image] {disc['id']}/{idx} erro ({e}); tentativa {attempt+1}",
                  file=sys.stderr)
    print(f"    [image] {disc['id']}/{idx} sem imagem após retries; usando gradiente",
          file=sys.stderr)
    return None


# ---------------- narração (Amazon Polly, cacheada) ----------------
def narration_text(disc: dict, idx: int, chapter: str) -> str:
    """Só o tema (não ensina conteúdo). 1º capítulo contextualiza com a disciplina."""
    if idx == 0:
        return f"{disc['name']}. Primeiro tema: {chapter}."
    return f"Tema: {chapter}."


def get_narration(disc: dict, idx: int, chapter: str, voice: str, use_polly: bool) -> Path | None:
    if not use_polly:
        return None
    d = AUDIO / disc["id"]
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{idx}_{voice}.mp3"
    if out.exists():
        return out
    text = narration_text(disc, idx, chapter)
    global _polly
    try:
        import boto3
        if _polly is None:
            _polly = boto3.client("polly", region_name=REGION)
        r = _polly.synthesize_speech(Text=text, VoiceId=voice, Engine="neural",
                                     LanguageCode="pt-BR", OutputFormat="mp3")
        out.write_bytes(r["AudioStream"].read())
        return out
    except Exception as e:  # noqa: BLE001
        print(f"    [polly] {disc['id']}/{idx} ({voice}) falhou ({e}); sem áudio", file=sys.stderr)
        return None


def ffprobe_duration(p: Path) -> float:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
        return float(out.stdout.strip())
    except Exception:  # noqa: BLE001
        return 0.0


# ---------------- render de 1 capítulo ----------------
def render_segment(path: Path, *, disc_name: str, chapter: str, subtitle: str, idx: int,
                   ntotal: int, bg_img: Path | None, narration: Path | None, dur: float):
    cap_tag = f"Cap {idx + 1}/{ntotal}"
    fout = min(0.35, dur / 4)
    # fontfile PRECISA vir entre aspas simples: no ffmpeg 8.0, path sem aspas quebra o
    # parse do 'text=' ("Either text ... must be provided").
    ff = f"fontfile='{FONT}'"
    overlays = (
        f"drawbox=x=0:y=0:w=iw:h=96:color=black@0.35:t=fill,"
        f"drawbox=x=0:y=ih-215:w=iw:h=215:color=black@0.55:t=fill,"
        f"drawtext={ff}:text='{BRAND}':fontcolor=white@0.85:fontsize=26:x=40:y=34,"
        f"drawtext={ff}:text='{cap_tag}':fontcolor=white@0.9:fontsize=26:x=w-text_w-40:y=34,"
        f"drawtext={ff}:text='{disc_name}':fontcolor=0xFFD166:fontsize=30:x=48:y=h-182,"
        f"drawtext={ff}:text='{chapter}':fontcolor=white:fontsize=56:x=48:y=h-142,"
        f"drawtext={ff}:text='{subtitle}':fontcolor=white@0.8:fontsize=26:x=48:y=h-62,"
        f"fade=t=in:st=0:d=0.3,fade=t=out:st={dur - fout}:d={fout}[v]"
    )
    zoom_frames = max(1, int(round(dur * FPS)))
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if bg_img:
        pan = "0.0016" if idx % 2 == 0 else "0.0013"
        cmd += ["-loop", "1", "-i", str(bg_img)]
        vf = (f"[0:v]scale=1600:900:force_original_aspect_ratio=increase,crop=1600:900,"
              f"zoompan=z='min(1.0+{pan}*in,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
              f"d={zoom_frames}:s={W}x{H}:fps={FPS},{overlays}")
    else:
        c0, c1 = GRAD[idx % len(GRAD)]
        cmd += ["-f", "lavfi", "-i", f"gradients=s={W}x{H}:c0={c0}:c1={c1}:d={dur}:r={FPS}"]
        vf = f"[0:v]{overlays}"

    if narration:
        cmd += ["-i", str(narration)]
        # pequeno lead de silêncio + fala + cauda curta, encaixado na duração do capítulo.
        af = f"[1:a]adelay={int(LEAD * 1000)}|{int(LEAD * 1000)},apad,atrim=0:{dur},asetpts=PTS-STARTPTS[a]"
        filt = f"{vf};{af}"
        maps = ["-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono:d={dur}"]
        filt = vf
        maps = ["-map", "[v]", "-map", "1:a"]

    cmd += ["-filter_complex", filt, *maps, "-t", str(dur), "-r", str(FPS),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
            "-c:a", "aac", "-b:a", "128k", str(path)]
    subprocess.run(cmd, check=True)


def add_music_bed(base: Path, out: Path, total: float):
    """Mixa uma trilha ambiente CONTÍNUA e suave (acorde grave fixo, sem beeps mudando)
    por baixo da narração. Acorde Am grave (110/164.81/220 Hz), lowpass e volume baixo."""
    expr = "0.10*sin(2*PI*110*t)+0.08*sin(2*PI*164.81*t)+0.05*sin(2*PI*220*t)"
    fin, fout = 2.0, 2.0
    af = (f"[1:a]lowpass=f=900,volume=0.16,afade=t=in:st=0:d={fin},"
          f"afade=t=out:st={max(0.0, total - fout)}:d={fout}[bed];"
          f"[0:a][bed]amix=inputs=2:duration=first:normalize=0[a]")
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(base),
        "-f", "lavfi", "-i", f"aevalsrc=exprs={expr}:s=24000:d={total}",
        "-filter_complex", af, "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", str(out),
    ], check=True)


def chapter_voices(disc_id: str, n: int) -> list:
    """Sorteia (determinístico por disciplina) QUANTOS narradores o vídeo usa — 1, 2 ou 3 —
    e distribui os capítulos entre esse subconjunto. Alguns vídeos ficam com 1 voz, outros
    com 2, outros com 3, de forma aleatória entre as disciplinas."""
    if not VOICES:
        return ["Camila"] * n
    rnd = random.Random(seed_of(disc_id, "voices"))
    k = min(rnd.choice([1, 2, 3]), len(VOICES))
    chosen = rnd.sample(VOICES, k)
    return [chosen[i % k] for i in range(n)]


def plan_chapters(disc: dict, chapters: list, *, use_polly: bool) -> list:
    """Garante narração (cacheada) e calcula a duração de cada capítulo a partir do áudio.
    Retorna lista de dicts: {index, title, voice, narration(Path|None), dur, start_sec}."""
    voices = chapter_voices(disc["id"], len(chapters))
    meta = []
    start = 0.0
    for i, ch in enumerate(chapters):
        voice = voices[i]
        narr = get_narration(disc, i, ch, voice, use_polly)
        if narr:
            dur = round(max(MIN_SEG, LEAD + ffprobe_duration(narr) + TAIL), 2)
        else:
            dur = FALLBACK_SEG
        meta.append({"index": i, "title": ch, "voice": voice, "narration": narr,
                     "dur": dur, "start_sec": round(start, 2)})
        start += dur
    return meta


def build_video(disc: dict, meta: list, out: Path, *, use_images: bool, use_music: bool):
    out.parent.mkdir(parents=True, exist_ok=True)
    disc_name = sanitize(disc["name"])
    subtitle = sanitize(f"{disc['area']} - {disc['credits']} creditos - semestre {disc['semester_suggested']}")
    n = len(meta)
    total = sum(m["dur"] for m in meta)
    with tempfile.TemporaryDirectory() as tmp:
        lines = []
        for m in meta:
            # get_background levanta erro em falha de credencial (pula o vídeo p/ rerun);
            # retorna None só após retries de filtro/transiente -> gradiente naquele capítulo.
            bg = get_background(disc, m["index"], m["title"]) if use_images else None
            seg = Path(tmp) / f"s{m['index']}.mp4"
            render_segment(seg, disc_name=disc_name, chapter=m["title"], subtitle=subtitle,
                           idx=m["index"], ntotal=n, bg_img=bg, narration=m["narration"],
                           dur=m["dur"])
            lines.append(f"file '{seg}'")
        listfile = Path(tmp) / "list.txt"
        listfile.write_text("\n".join(lines), encoding="utf-8")
        concat_out = (Path(tmp) / "concat.mp4") if use_music else out
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat",
                        "-safe", "0", "-i", str(listfile), "-c", "copy", str(concat_out)], check=True)
        if use_music:
            add_music_bed(concat_out, out, total=total)


def main():
    global SEG
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--area", default="")
    ap.add_argument("--only", default="", help="discipline_id específico (ex.: disc_029)")
    ap.add_argument("--chapters", type=int, default=CHAPTERS, help="capítulos por vídeo")
    ap.add_argument("--seg", type=int, default=SEG, help="segundos por capítulo")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--no-narration", action="store_true")
    ap.add_argument("--music", action="store_true", help="trilha ambiente (padrão: sem trilha)")
    args = ap.parse_args()

    SEG = args.seg
    n_chapters = args.chapters

    disciplines = json.loads((DATA / "disciplines.json").read_text(encoding="utf-8"))
    programs = {p["id"]: p for p in json.loads((DATA / "programs.json").read_text(encoding="utf-8"))}
    disciplines.sort(key=lambda d: d["id"])
    if args.only:
        disciplines = [d for d in disciplines if d["id"] == args.only]
    if args.area:
        disciplines = [d for d in disciplines if d["area"].lower() == args.area.lower()]
    if args.limit:
        disciplines = disciplines[: args.limit]
    if not disciplines:
        sys.exit("nenhuma disciplina após filtros")

    cache = load_cache()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []
    by_id = {m["discipline_id"]: m for m in manifest}
    total = len(disciplines)
    failures = []
    print(f"Gerando {total} disciplina(s) | imagens={not args.no_images} narração={not args.no_narration}")
    for n, disc in enumerate(disciplines, 1):
        slug = disc.get("kb_slug") or slugify(disc["name"])
        rel = f"{slugify(disc['area'])}/{disc['id']}_{slug}.mp4"
        out = VIDEOS / rel
        try:
            chapters = get_chapters(disc, cache, use_bedrock=True, n=n_chapters)
            save_cache(cache)
            meta = plan_chapters(disc, chapters, use_polly=not args.no_narration)
            # Fail-safe: se a narração era pra existir e falhou (ex.: credenciais), NÃO gera um
            # vídeo degradado — pula, deixando o vídeo ausente pra um rerun retentar.
            if not args.no_narration and any(m["narration"] is None for m in meta):
                raise RuntimeError("narração indisponível (credenciais/API?)")
            if out.exists() and not args.force:
                print(f"[{n}/{total}] skip {rel}")
            else:
                secs = round(sum(m["dur"] for m in meta))
                print(f"[{n}/{total}] {rel} ({secs}s)  <- {chapters}")
                build_video(disc, meta, out, use_images=not args.no_images, use_music=args.music)
        except Exception as e:  # noqa: BLE001
            # remove vídeo parcial/antigo pra forçar retentativa limpa no próximo run
            if out.exists() and args.force:
                out.unlink(missing_ok=True)
            print(f"[{n}/{total}] FALHOU {rel}: {e} — pulando (rerun retenta)", file=sys.stderr)
            failures.append(disc["id"])
            continue
        by_id[disc["id"]] = {
            "discipline_id": disc["id"], "name": disc["name"], "area": disc["area"],
            "semester": disc["semester_suggested"], "credits": disc["credits"],
            "kb_slug": disc.get("kb_slug"),
            "programs": [{"id": pid, "code": programs[pid]["code"], "name": programs[pid]["name"]}
                         for pid in disc.get("programs", []) if pid in programs],
            "video": rel, "duration_sec": round(sum(m["dur"] for m in meta), 2),
            "chapters": [{"index": m["index"], "title": m["title"],
                          "start_sec": m["start_sec"], "dur_sec": m["dur"], "voice": m["voice"],
                          "narration": narration_text(disc, m["index"], m["title"])}
                         for m in meta],
        }
        MANIFEST.write_text(json.dumps([by_id[d] for d in sorted(by_id)], ensure_ascii=False, indent=2),
                            encoding="utf-8")

    done = len([d for d in by_id])
    print(f"\nOK -> {MANIFEST} ({done} disciplinas no manifest)  |  vídeos em {VIDEOS}")
    if failures:
        print(f"FALHARAM {len(failures)} (rode de novo pra retentar): {', '.join(failures)}", file=sys.stderr)


if __name__ == "__main__":
    main()
