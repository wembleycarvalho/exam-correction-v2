"""Natural language -> structured intent + entities, grounded on the graph.

Primary path uses Bedrock to extract a small JSON. If Bedrock is unavailable (no
credentials / offline / tests), a deterministic keyword fallback keeps the demo working.
Entity names are resolved to graph node ids via fuzzy matching against real node names.
"""
from __future__ import annotations

import difflib
import json
import re

import networkx as nx

INTENTS = ["recommend_path", "check_prerequisite", "compare_careers",
           "explain_connection", "progress", "unknown"]

_SYSTEM = (
    "Você é um extrator de intenção para um orientador acadêmico. "
    "Dada a pergunta do aluno, responda APENAS um JSON válido, sem texto extra, no formato: "
    '{"intent": "<um de: recommend_path|check_prerequisite|compare_careers|explain_connection|progress>", '
    '"career": "<nome de carreira ou null>", "career_2": "<nome de carreira ou null>", '
    '"discipline": "<nome de disciplina ou null>", "discipline_2": "<nome de disciplina ou null>"}. '
    "recommend_path: quer saber quais disciplinas cursar / caminho para uma carreira. "
    "check_prerequisite: quer saber se pode pular/adiantar/pré-requisitos de uma disciplina. "
    "compare_careers: quer comparar duas carreiras. "
    "explain_connection: quer entender a relação entre duas coisas (disciplina/carreira). "
    "progress: quer saber seu progresso/quanto falta."
)


def _name_maps(g: nx.DiGraph):
    disc, career = {}, {}
    for n, d in g.nodes(data=True):
        t = d.get("type")
        if t == "Discipline":
            disc[d.get("name", "").lower()] = n
        elif t == "Career":
            career[d.get("name", "").lower()] = n
    return disc, career


def _resolve(name: str | None, name_map: dict[str, str]) -> str | None:
    if not name:
        return None
    key = name.strip().lower()
    if key in name_map:
        return name_map[key]
    match = difflib.get_close_matches(key, list(name_map.keys()), n=1, cutoff=0.6)
    if match:
        return name_map[match[0]]
    # tenta por substring (ex.: "cálculo" -> "cálculo i")
    for nm, nid in name_map.items():
        if key in nm or nm in key:
            return nid
    return None


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def _keyword_fallback(question: str) -> dict:
    q = question.lower()
    if any(w in q for w in ["pular", "posso pular", "adiantar", "pré-requisito", "pre-requisito", "prerequisito"]):
        intent = "check_prerequisite"
    elif any(w in q for w in ["diferença", "diferenca", "comparar", "versus", " vs ", "ou "]):
        intent = "compare_careers"
    elif any(w in q for w in ["relação", "relacao", "por que", "porque", "conexão", "conexao", "ligação", "tem a ver"]):
        intent = "explain_connection"
    elif any(w in q for w in ["progresso", "quanto falta", "quanto já", "quanto ja", "completei", "concluí"]):
        intent = "progress"
    else:
        intent = "recommend_path"
    return {"intent": intent}


def parse_intent(question: str, g: nx.DiGraph, llm=None) -> dict:
    """Return {intent, career_id, career_2_id, discipline_id, discipline_2_id, raw, source}."""
    disc_map, career_map = _name_maps(g)
    raw: dict = {}
    source = "fallback"

    if llm is not None:
        try:
            out = llm.complete(question, system=_SYSTEM, max_tokens=256, temperature=0.0)
            raw = _extract_json(out)
            if raw.get("intent") in INTENTS:
                source = "bedrock"
        except Exception:
            raw = {}

    if not raw or raw.get("intent") not in INTENTS:
        raw = {**_keyword_fallback(question), **raw}
        # extrai nomes por correspondência direta na pergunta quando o LLM não deu
        discs = _guess_all_names(question, disc_map)
        careers = _guess_all_names(question, career_map)
        raw.setdefault("discipline", discs[0] if discs else None)
        raw.setdefault("discipline_2", discs[1] if len(discs) > 1 else None)
        raw.setdefault("career", careers[0] if careers else None)
        raw.setdefault("career_2", careers[1] if len(careers) > 1 else None)

    intent = raw.get("intent", "unknown")
    if intent not in INTENTS:
        intent = "unknown"

    return {
        "intent": intent,
        "career_id": _resolve(raw.get("career"), career_map),
        "career_2_id": _resolve(raw.get("career_2"), career_map),
        "discipline_id": _resolve(raw.get("discipline"), disc_map),
        "discipline_2_id": _resolve(raw.get("discipline_2"), disc_map),
        "raw": raw,
        "source": source,
    }


def _guess_all_names(question: str, name_map: dict[str, str]) -> list[str]:
    """All node names present in the question, longest-first, dropping names that are
    substrings of an already-picked longer name (e.g. avoids 'machine learning' when
    'engenheiro de machine learning' já foi escolhido)."""
    q = question.lower()
    found = sorted([nm for nm in name_map if nm and nm in q], key=len, reverse=True)
    picked: list[str] = []
    for nm in found:
        if not any(nm in p for p in picked):
            picked.append(nm)
    return picked
