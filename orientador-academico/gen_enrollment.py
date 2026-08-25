#!/usr/bin/env python3
"""Gera a matrícula do semestre atual ("enrolled") para cada aluno, de forma
determinística e coerente com o currículo — SEM inventar nada.

Regra: "cursando agora" = o 1º bloco do plano recomendado (recommend_path), ou seja, as
próximas disciplinas que o aluno deve cursar respeitando pré-requisitos e a cota de
eletivas (obrigatórias faltantes priorizadas), limitado à carga por semestre do motor
(máx. 5). Alunos sem pendências ficam com matrícula vazia (formandos).

Grava o campo `enrolled` (lista de ids de disciplina) em data/students.json. Idempotente:
recalcula sempre a partir das CONCLUÍDAS, não da matrícula anterior.

Uso: python gen_enrollment.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.graph.builder import build_graph, DATA_DIR  # noqa: E402
from src.recommender import path_engine as pe  # noqa: E402

STUDENTS = os.path.join(DATA_DIR, "students.json")


def main() -> None:
    g = build_graph()
    students = json.load(open(STUDENTS, encoding="utf-8"))
    total = 0
    for s in students:
        plan = pe.recommend_path(g, s["id"]).get("semester_plan") or []
        enrolled = [d["id"] for d in plan[0]["disciplines"]] if plan else []
        s["enrolled"] = enrolled
        total += len(enrolled)
    json.dump(students, open(STUDENTS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(students)} alunos · {total} matrículas geradas · média "
          f"{total / max(1, len(students)):.1f}/aluno")


if __name__ == "__main__":
    main()
