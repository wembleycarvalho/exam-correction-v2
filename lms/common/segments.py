"""Casamento segmento↔capítulo e montagem de metadados/linhas de vetor p/ o S3 Vectors.

Um "segmento" é um clip do vídeo embutido pelo Marengo (janela start/end). Casamos cada
segmento com o capítulo do manifesto cuja janela de tempo contém o CENTRO do segmento —
assim o resultado de busca já sabe título/tema/narração e o timestamp para o deep-link.
"""
from __future__ import annotations

from dataclasses import dataclass

from .manifest import Chapter, Discipline


def chapter_for_time(chapters: list[Chapter], t: float) -> Chapter | None:
    """Capítulo cuja janela [start, start+dur) contém t; senão o mais próximo por início."""
    if not chapters:
        return None
    for ch in chapters:
        if ch.start_sec <= t < ch.end_sec:
            return ch
    # fora de qualquer janela (ex.: arredondamentos) -> capítulo de maior início <= t,
    # ou o primeiro se t for antes de tudo.
    before = [c for c in chapters if c.start_sec <= t]
    return before[-1] if before else chapters[0]


def segment_center(start_sec: float, end_sec: float) -> float:
    return round((float(start_sec) + float(end_sec)) / 2.0, 3)


def segment_key(disc_id: str, video: str, start_sec: float, modality: str) -> str:
    """Chave estável e idempotente do vetor (reprocessar sobrescreve, não duplica)."""
    return f"{disc_id}#{video}#{round(float(start_sec), 3)}#{modality}"


def segment_metadata(disc: Discipline, chapter: Chapter | None, *, start_sec: float,
                     end_sec: float, modality: str) -> dict:
    """Metadados anexados ao vetor. Chaves filtráveis (disc_id, programs, area, semester,
    modality, chapter_index, video, start/end) + não-filtráveis (narration, chapter_title,
    name) definidas em config.NON_FILTERABLE_KEYS."""
    meta = {
        "disc_id": disc.discipline_id,
        "name": disc.name,
        "area": disc.area,
        "semester": int(disc.semester),
        "programs": disc.program_codes,          # lista de strings (filtro por curso)
        "program_ids": disc.program_ids,
        "video": disc.video,
        "modality": modality,
        "start_sec": round(float(start_sec), 3),
        "end_sec": round(float(end_sec), 3),
    }
    if chapter is not None:
        meta["chapter_index"] = int(chapter.index)
        meta["chapter_title"] = chapter.title
        meta["narration"] = chapter.narration
    return meta


def rows_from_embeddings(disc: Discipline, items: list[dict]) -> list[dict]:
    """Converte a lista de embeddings do Marengo (um item por clip×modalidade) em linhas de
    vetor prontas para o `put_vectors`. Ignora embeddings de escopo 'asset' (queremos clips
    para o deep-link por timestamp). Modalidade ausente assume 'visual'."""
    rows = []
    for it in items:
        if it.get("scope") == "asset":
            continue
        emb = it.get("embedding")
        if not emb:
            continue
        modality = it.get("modality") or "visual"
        start = float(it.get("start_sec") or 0.0)
        end = float(it.get("end_sec") if it.get("end_sec") is not None else start)
        ch = chapter_for_time(disc.chapters, segment_center(start, end))
        rows.append(vector_row(disc, ch, embedding=emb, start_sec=start, end_sec=end,
                               modality=modality))
    return rows


def vector_row(disc: Discipline, chapter: Chapter | None, *, embedding: list[float],
               start_sec: float, end_sec: float, modality: str) -> dict:
    """Linha no formato do put_vectors do S3 Vectors."""
    return {
        "key": segment_key(disc.discipline_id, disc.video, start_sec, modality),
        "data": {"float32": [float(x) for x in embedding]},
        "metadata": segment_metadata(disc, chapter, start_sec=start_sec, end_sec=end_sec,
                                     modality=modality),
    }


@dataclass
class SearchHit:
    """Resultado normalizado de uma consulta, pronto para o frontend (deep-link)."""
    disc_id: str
    name: str
    area: str
    programs: list[str]
    video: str
    modality: str
    start_sec: float
    end_sec: float
    chapter_index: int | None
    chapter_title: str
    narration: str
    score: float

    @classmethod
    def from_vector(cls, v: dict, media_base_path: str = "/lms/media") -> "SearchHit":
        m = v.get("metadata", {}) or {}
        dist = v.get("distance")
        # distância cosseno -> score de similaridade (1 - dist), quando disponível.
        score = round(1.0 - float(dist), 4) if dist is not None else None
        return cls(
            disc_id=m.get("disc_id", ""), name=m.get("name", ""), area=m.get("area", ""),
            programs=list(m.get("programs", [])), video=m.get("video", ""),
            modality=m.get("modality", ""), start_sec=float(m.get("start_sec", 0)),
            end_sec=float(m.get("end_sec", 0)),
            chapter_index=m.get("chapter_index"), chapter_title=m.get("chapter_title", ""),
            narration=m.get("narration", ""), score=score,
        )

    def to_dict(self, media_base_path: str = "/lms/media") -> dict:
        return {
            "disc_id": self.disc_id, "name": self.name, "area": self.area,
            "programs": self.programs, "modality": self.modality, "video": self.video,
            "start_sec": self.start_sec, "end_sec": self.end_sec,
            "chapter_index": self.chapter_index, "chapter_title": self.chapter_title,
            "narration": self.narration, "score": self.score,
            "media_url": f"{media_base_path.rstrip('/')}/{self.video}",
            "deep_link": f"{media_base_path.rstrip('/')}/{self.video}#t={self.start_sec}",
        }
