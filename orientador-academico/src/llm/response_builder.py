"""Turn graph query results into natural Brazilian-Portuguese answers.

Templates are the source of truth (deterministic, no hallucination). If a Bedrock LLM
is provided, it only *rephrases* the factual summary in a friendlier tone — instructed
not to invent data. Also exposes answer_question(), the orchestrator used by the API.
"""
from __future__ import annotations

import networkx as nx

from ..graph import queries as q
from ..recommender import path_engine as pe
from .intent_parser import parse_intent

_POLISH_SYSTEM = (
    "Você é um orientador acadêmico amigável. Reescreva o resumo a seguir em português "
    "brasileiro, de forma clara e acolhedora, MANTENDO todos os fatos, nomes e números. "
    "NÃO invente disciplinas, notas ou dados que não estejam no resumo."
)


def _name(g, nid):
    return g.nodes[nid].get("name", nid) if nid in g.nodes else nid


def _fmt_plan(plan: list[dict]) -> str:
    lines = []
    for blk in plan:
        discs = ", ".join(d["name"] for d in blk["disciplines"])
        lines.append(f"• Semestre +{blk['semester_offset']}: {discs}")
    return "\n".join(lines)


def build_recommend(g, student_id, career_id) -> tuple[str, dict]:
    data = pe.recommend_path(g, student_id, career_id)
    career = _name(g, data["target_career"])
    if not data["recommended_order"]:
        return (f"Você já concluiu as disciplinas mais relevantes para {career}. Parabéns!", data)
    top = sorted(data["recommended_order"], key=lambda k: -k["relevance"])[:3]
    top_txt = ", ".join(t["name"] for t in top)
    txt = (f"Para seguir como **{career}**, o caminho recomendado tem "
           f"{data['total_disciplines']} disciplina(s), respeitando os pré-requisitos:\n"
           f"{_fmt_plan(data['semester_plan'])}\n\n"
           f"As mais decisivas para esse objetivo: {top_txt}.")
    return txt, data


def build_prerequisite(g, discipline_id) -> tuple[str, dict]:
    d = q.get_node(g, discipline_id)
    directs = pe.q.direct_prerequisites(g, discipline_id)
    impact = pe.what_if_skip(g, discipline_id)
    parts = [f"**{d['name']}** ({d.get('code')})."]
    if directs:
        parts.append("Pré-requisitos diretos: " + ", ".join(_name(g, p) for p in directs) + ".")
    else:
        parts.append("Não tem pré-requisitos diretos.")
    if impact["skippable_without_block"]:
        parts.append("Pular esta disciplina não bloqueia nenhuma outra do currículo.")
    else:
        n = len(impact["blocks_disciplines"])
        exemplos = ", ".join(x["name"] for x in impact["blocks_disciplines"][:4])
        parts.append(f"Atenção: pular travaria {n} disciplina(s) que dependem dela (ex.: {exemplos}).")
    # cobertura de competências
    losses = [c for cr in impact["affected_careers"] for c in cr["competencies"]
              if not c["has_alternative"]]
    if losses:
        parts.append("Algumas competências ficariam sem outra disciplina que as desenvolva — "
                     "evite pular se seu objetivo depende delas.")
    return " ".join(parts), impact


def build_compare(g, career_a, career_b) -> tuple[str, dict]:
    data = pe.compare_careers(g, career_a, career_b)
    shared = ", ".join(x["name"] for x in data["shared_competencies"]) or "—"
    only_a = ", ".join(x["name"] for x in data["only_a"]) or "—"
    only_b = ", ".join(x["name"] for x in data["only_b"]) or "—"
    txt = (f"Comparando **{data['career_a']['name']}** e **{data['career_b']['name']}**:\n"
           f"• Em comum: {shared}\n"
           f"• Só {data['career_a']['name']}: {only_a}\n"
           f"• Só {data['career_b']['name']}: {only_b}")
    return txt, data


def build_connection(g, a_id, b_id) -> tuple[str, dict]:
    data = pe.explain_connection(g, a_id, b_id)
    if not data["connected"]:
        return (f"Não encontrei uma conexão acadêmica direta entre {_name(g, a_id)} e {_name(g, b_id)}.", data)
    rel_pt = {"PREREQUISITE_OF": "é pré-requisito de", "DEVELOPS_COMPETENCY": "desenvolve a competência",
              "REQUIRES_COMPETENCY": "é exigida por", "COMPLEMENTS": "complementa"}
    facts = [f"{s['src_name']} {rel_pt.get(s['relation'], s['relation'])} {s['dst_name']}"
             for s in data["path"]]
    txt = (f"{_name(g, a_id)} e {_name(g, b_id)} se conectam assim: " + "; ".join(facts) + ".")
    return txt, data


def build_progress(g, student_id) -> tuple[str, dict]:
    p = pe.student_progress(g, student_id)
    txt = (f"{p['name']} concluiu {len(p['completed'])} disciplina(s) "
           f"({p['completion_pct']}% do curso) e tem {len(p['pending'])} pendente(s).")
    return txt, p


def answer_question(g: nx.DiGraph, student_id: str, question: str, llm=None,
                    polish: bool = False) -> dict:
    """Orchestrator: parse -> query graph -> compose PT-BR answer. Used by /ask."""
    parsed = parse_intent(question, g, llm=llm)
    intent = parsed["intent"]
    student = q.get_node(g, student_id)

    if intent == "recommend_path":
        answer, ctx = build_recommend(g, student_id, parsed["career_id"] or student.get("target_career"))
    elif intent == "check_prerequisite" and parsed["discipline_id"]:
        answer, ctx = build_prerequisite(g, parsed["discipline_id"])
    elif intent == "compare_careers":
        a = parsed["career_id"] or student.get("target_career")
        b = parsed["career_2_id"]
        if a and b and a != b:
            answer, ctx = build_compare(g, a, b)
        else:
            answer, ctx = ("Para comparar, me diga as duas carreiras (ex.: 'diferença entre "
                           "Cientista de Dados e Engenheiro de ML').", {})
    elif intent == "explain_connection":
        a = parsed["discipline_id"]
        b = parsed["discipline_2_id"] or parsed["career_id"]
        if a and b:
            answer, ctx = build_connection(g, a, b)
        else:
            answer, ctx = ("Diga os dois itens que quer conectar (ex.: 'o que Cálculo I tem a ver "
                           "com Machine Learning?').", {})
    elif intent == "progress":
        answer, ctx = build_progress(g, student_id)
    elif intent == "check_prerequisite":
        answer, ctx = ("Sobre qual disciplina você quer saber os pré-requisitos?", {})
    else:
        answer, ctx = ("Posso recomendar sua trilha, checar pré-requisitos, comparar carreiras "
                       "ou explicar conexões. Como posso ajudar?", {})

    if polish and llm is not None and answer:
        try:
            answer = llm.complete(answer, system=_POLISH_SYSTEM, max_tokens=600, temperature=0.3)
        except Exception:
            pass

    return {"answer": answer, "intent": intent, "entities": {
        "career_id": parsed["career_id"], "career_2_id": parsed["career_2_id"],
        "discipline_id": parsed["discipline_id"], "discipline_2_id": parsed["discipline_2_id"],
    }, "graph_context": ctx, "intent_source": parsed["source"]}
