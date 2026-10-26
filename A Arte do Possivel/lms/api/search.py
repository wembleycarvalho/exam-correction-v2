"""Lógica de busca (pura/orquestração) do módulo LMS.

Um índice S3 Vectors só, três modos de consulta (espaço unificado do Marengo):
- text  -> embed de texto (sync); consulta todas as modalidades (casa falado E visual).
- image -> embed de imagem (sync); consulta modalidade 'visual'.
- audio -> embed de áudio (async); consulta modalidade 'audio'.

Filtros escalares (disc_id, area, semester, modality) vão como filtro do S3 Vectors.
`programs` (lista) é pós-filtrado em memória (o metadado do hit traz a lista de cursos).
"""
from __future__ import annotations

import time

from common import config
from common.segments import SearchHit, segment_key

MODALITY_FOR_MODE = {"text": None, "image": "visual", "audio": "audio"}


class Trace:
    """Trace de execução do backend: passos com descrição, duração (ms) e detalhes.
    Populado só quando o cliente pede debug — vira debug['trace'] na resposta."""
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.steps = []
        self._t = time.perf_counter()

    def step(self, acao: str, **detalhe):
        if not self.enabled:
            return
        now = time.perf_counter()
        ms = round((now - self._t) * 1000, 1)
        self._t = now
        item = {"passo": len(self.steps) + 1, "acao": acao, "ms": ms}
        if detalhe:
            item["detalhe"] = detalhe
        self.steps.append(item)


def build_index_filter(filters: dict | None, modality: str | None, scope: dict | None) -> dict | None:
    """Monta o filtro escalar do S3 Vectors (AND implícito entre chaves)."""
    f: dict = {}
    filters = filters or {}
    scope = scope or {}
    if filters.get("area"):
        f["area"] = filters["area"]
    if filters.get("semester") is not None and filters.get("semester") != "":
        f["semester"] = int(filters["semester"])
    # escopo por disciplina tem precedência sobre disc_id em filters
    disc_id = scope.get("disc_id") or filters.get("disc_id")
    if disc_id:
        f["disc_id"] = disc_id
    if modality:
        f["modality"] = modality
    return f or None


def _seg_key(hit: SearchHit) -> tuple:
    return (hit.disc_id, hit.video, round(hit.start_sec, 3))


def dedupe_by_segment(hits: list[SearchHit]) -> list[SearchHit]:
    """Um hit por segmento (disc/vídeo/início), mantendo o de maior score. Ordena desc."""
    best: dict[tuple, SearchHit] = {}
    for h in hits:
        k = _seg_key(h)
        cur = best.get(k)
        if cur is None or (h.score or 0) > (cur.score or 0):
            best[k] = h
    return sorted(best.values(), key=lambda h: (h.score or 0), reverse=True)


def apply_program_filter(hits: list[SearchHit], programs) -> list[SearchHit]:
    """Mantém hits cujos cursos interceptam os códigos pedidos (pós-filtro em memória)."""
    if not programs:
        return hits
    want = {programs} if isinstance(programs, str) else set(programs)
    return [h for h in hits if want.intersection(set(h.programs or []))]


def group_catalog(disciplines: list[dict]) -> dict:
    """Agrega o catálogo em cursos/áreas para a UI."""
    courses: dict[str, dict] = {}
    areas: set[str] = set()
    for d in disciplines:
        for p in d.get("programs", []):
            courses.setdefault(p["code"], {"code": p["code"], "name": p.get("name", "")})
        if d.get("area"):
            areas.add(d["area"])
    return {
        "courses": sorted(courses.values(), key=lambda c: c["name"]),
        "areas": sorted(areas),
        "disciplines": disciplines,
    }


def _raw_hit_debug(raw: list[dict]) -> list[dict]:
    out = []
    for v in raw:
        m = v.get("metadata", {}) or {}
        out.append({"key": v.get("key"), "distance": v.get("distance"),
                    "modality": m.get("modality"), "disc_id": m.get("disc_id"),
                    "chapter": m.get("chapter_title"), "start_sec": m.get("start_sec")})
    return out


def _query_input_summary(mode: str, text: str, image_b64: str) -> dict:
    if mode == "text":
        return {"inputType": "text", "text": {"inputText": text}}
    if mode == "image":
        return {"inputType": "image", "image": {"mediaSource":
                {"base64String": f"<imagem base64, {len(image_b64)} chars>"}}}
    return {"inputType": "audio", "audio": {"mediaSource": {"base64String": "<áudio (async)>"}}}


def run_search(mode: str, *, marengo, vectors, video_embed_fn=None, text: str = "",
               image_b64: str = "", audio_ref: dict | None = None, filters: dict | None = None,
               scope: dict | None = None, top_k: int | None = None,
               media_base: str = None, debug: dict | None = None) -> list[dict]:
    media_base = media_base or config.MEDIA_BASE_PATH
    top_k = top_k or config.DEFAULT_TOP_K
    if mode not in MODALITY_FOR_MODE:
        raise ValueError(f"modo inválido: {mode}")
    tr = Trace(debug is not None)

    flt = build_index_filter(filters, MODALITY_FOR_MODE[mode], scope)
    tr.step("montar filtro de metadados", modalidade_alvo=MODALITY_FOR_MODE[mode], filter=flt)

    if mode == "text":
        qv = marengo.embed_text(text)
    elif mode == "image":
        qv = marengo.embed_image_b64(image_b64)
    else:  # audio (assíncrono) — via função injetada (start+poll+read)
        if video_embed_fn is None:
            raise RuntimeError("busca por áudio requer video_embed_fn (async)")
        qv = video_embed_fn(audio_ref or {})
    tr.step("embutir a QUERY no Marengo (InvokeModel)", model_id=marengo.model_id,
            request=_query_input_summary(mode, text, image_b64),
            embedding_dim=len(qv) if qv else 0)
    if not qv:
        if debug is not None:
            debug["erro"] = "embedding da query vazio"
            debug["trace"] = tr.steps
        return []

    raw = vectors.query(qv, top_k=top_k * 3, flt=flt)
    tr.step("consultar S3 Vectors (QueryVectors, similaridade cosseno)",
            vectorBucket=vectors.bucket, index=vectors.index, topK=top_k * 3,
            filter=flt, n_resultados=len(raw))
    hits = [SearchHit.from_vector(v, media_base) for v in raw]
    n_raw = len(hits)
    hits = apply_program_filter(hits, (filters or {}).get("programs"))
    hits = dedupe_by_segment(hits)[:top_k]
    tr.step("pós-filtro de curso + dedupe por segmento", entrada=n_raw, saida=len(hits))
    if debug is not None:
        debug.update({
            "fluxo": ("O vídeo NÃO é reprocessado na busca: os embeddings dos trechos foram "
                      "gerados na ingestão (Marengo → S3 Vectors). Aqui embutimos apenas a "
                      "QUERY com o Marengo e fazemos busca por similaridade vetorial."),
            "trace": tr.steps,
            "raw_hits": _raw_hit_debug(raw),
        })
    return [h.to_dict(media_base) for h in hits]


def _vector_data(v: dict) -> list[float]:
    d = v.get("data", {}) or {}
    return d.get("float32") or d.get("vector") or []


def resolve_segment_start(vectors, disc_id: str, video: str, at_sec: float,
                          modality: str = "visual") -> float | None:
    """Descobre qual segmento (start) cobre o instante `at_sec` de um vídeo. Usa as chaves
    do índice (que codificam disc#video#start#modality), sem precisar de metadados: pega o
    maior start <= at_sec (o segmento em que o instante cai); se nenhum, o primeiro."""
    prefix = f"{disc_id}#{video}#"
    suffix = f"#{modality}"
    starts: list[float] = []
    for k in vectors.list_keys():
        if k.startswith(prefix) and k.endswith(suffix):
            try:
                starts.append(float(k[len(prefix):].split("#")[0]))
            except (ValueError, IndexError):
                continue
    if not starts:
        return None
    starts.sort()
    at = float(at_sec)
    covering = [s for s in starts if s <= at]
    return covering[-1] if covering else starts[0]


def run_similar(*, disc_id: str, video: str, start_sec: float | None = None, vectors,
                modality: str = "visual", at_sec: float | None = None,
                top_k: int | None = None, media_base: str = None,
                debug: dict | None = None) -> list[dict]:
    """'Trechos parecidos': pega o vetor do segmento (por chave) e busca os mais próximos,
    excluindo o próprio segmento. Descoberta cruzada entre cursos (sem filtro de curso).

    Se `at_sec` for informado (instante atual do player), resolve o segmento que cobre esse
    instante e usa o start dele; caso contrário usa `start_sec` diretamente."""
    media_base = media_base or config.MEDIA_BASE_PATH
    top_k = top_k or config.DEFAULT_TOP_K
    tr = Trace(debug is not None)
    if at_sec is not None:
        resolved = resolve_segment_start(vectors, disc_id, video, at_sec, modality)
        tr.step("resolver segmento no instante do player (ListVectors)",
                at_sec=round(float(at_sec), 2), modality=modality, start_resolvido=resolved)
        if resolved is not None:
            start_sec = resolved
    if start_sec is None:
        if debug is not None:
            debug["erro"] = "sem start_sec (nem at_sec resolvível) para o vídeo"
            debug["trace"] = tr.steps
        return []
    key = segment_key(disc_id, video, start_sec, modality)
    got = vectors.get([key], return_data=True, return_metadata=False)
    tr.step("buscar o vetor do segmento de origem (GetVectors por chave)", key=key,
            encontrado=bool(got))
    if not got:
        if debug is not None:
            debug["erro"] = f"segmento {key} não encontrado no índice"
            debug["trace"] = tr.steps
        return []
    qv = _vector_data(got[0])
    if not qv:
        return []
    raw = vectors.query(qv, top_k=top_k * 3 + 3, flt={"modality": modality})
    tr.step("consultar S3 Vectors com o vetor do segmento (vizinhos)", index=vectors.index,
            topK=top_k * 3 + 3, filter={"modality": modality}, n_resultados=len(raw))
    hits = [SearchHit.from_vector(v, media_base) for v in raw]
    n_raw = len(hits)
    # exclui o próprio segmento de origem
    hits = [h for h in hits if not (h.disc_id == disc_id and h.video == video
                                    and round(h.start_sec, 3) == round(float(start_sec), 3))]
    hits = dedupe_by_segment(hits)[:top_k]
    tr.step("excluir o próprio segmento + dedupe", entrada=n_raw, saida=len(hits))
    if debug is not None:
        debug.update({
            "fluxo": ("Reusa o vetor já indexado do segmento de origem (GetVectors por chave) "
                      "e busca vizinhos no S3 Vectors, excluindo o próprio segmento."),
            "trace": tr.steps,
            "raw_hits": _raw_hit_debug(raw),
        })
    return [h.to_dict(media_base) for h in hits]
