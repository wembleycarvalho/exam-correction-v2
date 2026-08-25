"""Leitura do manifesto do acervo (assets/lms-demo/manifest.json).

O manifesto é a fonte canônica: disciplinas (com cursos) e capítulos (com timestamp, voz e
texto narrado). Estruturas puras — sem AWS — para facilitar teste.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chapter:
    index: int
    title: str
    start_sec: float
    dur_sec: float
    voice: str
    narration: str

    @property
    def end_sec(self) -> float:
        return round(self.start_sec + self.dur_sec, 3)


@dataclass
class Discipline:
    discipline_id: str
    name: str
    area: str
    semester: int
    credits: int
    kb_slug: str | None
    programs: list[dict]          # [{id, code, name}]
    video: str                    # caminho relativo do .mp4
    duration_sec: float
    chapters: list[Chapter] = field(default_factory=list)

    @property
    def program_codes(self) -> list[str]:
        return [p["code"] for p in self.programs if p.get("code")]

    @property
    def program_ids(self) -> list[str]:
        return [p["id"] for p in self.programs if p.get("id")]


def _chapter(d: dict) -> Chapter:
    return Chapter(
        index=int(d["index"]), title=d["title"], start_sec=float(d["start_sec"]),
        dur_sec=float(d["dur_sec"]), voice=d.get("voice", ""), narration=d.get("narration", ""),
    )


def parse_discipline(d: dict) -> Discipline:
    return Discipline(
        discipline_id=d["discipline_id"], name=d["name"], area=d["area"],
        semester=int(d.get("semester", 0)), credits=int(d.get("credits", 0)),
        kb_slug=d.get("kb_slug"), programs=list(d.get("programs", [])),
        video=d["video"], duration_sec=float(d.get("duration_sec", 0)),
        chapters=[_chapter(c) for c in d.get("chapters", [])],
    )


def load_manifest(path: str | Path) -> list[Discipline]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [parse_discipline(d) for d in data]
