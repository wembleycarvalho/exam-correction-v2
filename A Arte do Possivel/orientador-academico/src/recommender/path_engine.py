"""Core recommendation engine over the academic knowledge graph.

Pure functions on a NetworkX DiGraph (no LLM, no I/O) so they are fast (<2s), fully
deterministic and unit-testable. The LLM layer only orchestrates these calls.
"""
from __future__ import annotations

import networkx as nx

from ..graph import queries as q
from ..graph.builder import prerequisite_subgraph

# Peso relativo da importância da competência para a carreira.
IMPORTANCE_WEIGHT = {"critical": 1.0, "important": 0.6, "nice-to-have": 0.3}
DEFAULT_MAX_PER_SEMESTER = 5


# --------------------------------------------------------------------------- #
# Progresso do aluno
# --------------------------------------------------------------------------- #
def student_progress(g: nx.DiGraph, student_id: str) -> dict:
    """Progresso do aluno no curso, por CRÉDITOS e com cota de eletivas.

    O curso exige todas as obrigatórias + um mínimo de créditos eletivos (não todas as
    eletivas). O percentual considera obrigatórias concluídas + min(eletivas concluídas,
    exigidas), então não é preciso cursar todas as eletivas para chegar a 100%.
    """
    student = q.get_node(g, student_id)
    program = student.get("program")
    completed = q.student_completed(g, student_id)
    program_discs = set(q.disciplines_in_program(g, program)) if program else {
        n for n, d in g.nodes(data=True) if d.get("type") == "Discipline"}

    mand = {d for d in program_discs if q.program_requirement(g, d, program) == "mandatory"}
    elec = program_discs - mand
    req_elec = q.elective_credits_required(g, program) if program else 0

    done_mand = completed & mand
    done_elec = completed & elec
    mand_credits = sum(q.credits_of(g, d) for d in mand)
    done_mand_credits = sum(q.credits_of(g, d) for d in done_mand)
    done_elec_credits = sum(q.credits_of(g, d) for d in done_elec)
    eff_elec = min(done_elec_credits, req_elec)

    denom = mand_credits + req_elec
    pct = round(100.0 * (done_mand_credits + eff_elec) / denom, 1) if denom else 0.0

    # Pendências: obrigatórias que faltam + (se ainda não fechou a cota) as eletivas restantes.
    pending_mand = mand - completed
    pending = set(pending_mand)
    if done_elec_credits < req_elec:
        pending |= (elec - completed)

    return {
        "student_id": student_id,
        "name": student.get("name"),
        "program": program,
        "target_career": student.get("target_career"),
        "completed": sorted(completed),
        "pending": sorted(pending),
        "completion_pct": pct,
        "mandatory": {"done": len(done_mand), "total": len(mand),
                      "credits_done": done_mand_credits, "credits_total": mand_credits},
        "electives": {"credits_done": done_elec_credits, "credits_required": req_elec,
                      "credits_remaining": max(0, req_elec - done_elec_credits),
                      "quota_met": done_elec_credits >= req_elec},
    }


# --------------------------------------------------------------------------- #
# Relevância disciplina x carreira
# --------------------------------------------------------------------------- #
def discipline_relevance(g: nx.DiGraph, career_id: str) -> dict[str, float]:
    """Score each discipline by how much it develops the career's competencies.

    score(disc) = Σ over competencies of (develops_weight * importance_weight).
    """
    reqs = q.career_competencies(g, career_id)
    imp = {r["competency"]: IMPORTANCE_WEIGHT.get(r["importance"], 0.6) for r in reqs}
    scores: dict[str, float] = {}
    for comp_id, w_imp in imp.items():
        for dev in q.disciplines_developing(g, comp_id):
            scores[dev["discipline"]] = scores.get(dev["discipline"], 0.0) + dev["weight"] * w_imp
    return scores


# --------------------------------------------------------------------------- #
# Recomendação de trilha
# --------------------------------------------------------------------------- #
def _recommend_core(g: nx.DiGraph, completed: set, program: str | None, career_id: str | None,
                    max_per_semester: int) -> dict:
    """Núcleo da recomendação para um par (curso, carreira) HIPOTÉTICO, reaproveitando um
    conjunto `completed` de disciplinas já concluídas. Base tanto da trilha do aluno quanto
    da simulação de troca de curso (plan_for_target)."""
    program_discs = set(q.disciplines_in_program(g, program)) if program else {
        n for n, d in g.nodes(data=True) if d.get("type") == "Discipline"}
    relevance = discipline_relevance(g, career_id) if career_id else {}

    mand = {d for d in program_discs if q.program_requirement(g, d, program) == "mandatory"}
    elec = program_discs - mand

    targets: set[str] = {d for d in mand if d not in completed}

    req_elec = q.elective_credits_required(g, program) if program else 0
    done_elec_credits = sum(q.credits_of(g, d) for d in completed if d in elec)
    remaining = max(0, req_elec - done_elec_credits)
    missing_elec = sorted(
        (d for d in elec if d not in completed),
        key=lambda d: (-relevance.get(d, 0.0), g.nodes[d].get("semester_suggested", 99),
                       g.nodes[d].get("code", d)))
    acc = 0
    for d in missing_elec:
        if acc >= remaining:
            break
        targets.add(d)
        acc += q.credits_of(g, d)

    needed: set[str] = set()
    for d in targets:
        needed.add(d)
        for pre in q.all_prerequisites(g, d):
            if pre not in completed and pre in program_discs:
                needed.add(pre)

    ordered = q.order_by_prerequisites(g, list(needed))
    plan = _pack_into_semesters(g, ordered, completed, max_per_semester)

    def brief(d):
        b = _disc_brief(g, d, relevance.get(d, 0.0))
        b["requirement"] = q.program_requirement(g, d, program) if program else "mandatory"
        return b

    return {
        "program": program,
        "target_career": career_id,
        "total_disciplines": len(ordered),
        "credits_remaining": sum(q.credits_of(g, d) for d in ordered),
        "elective_credits_required": req_elec,
        "elective_credits_remaining": max(0, remaining - acc),
        "recommended_order": [brief(d) for d in ordered],
        "semester_plan": plan,
    }


def recommend_path(g: nx.DiGraph, student_id: str, target_career_id: str | None = None,
                   max_per_semester: int = DEFAULT_MAX_PER_SEMESTER) -> dict:
    """Recommend a prioritized, prerequisite-respecting, semester-by-semester plan."""
    student = q.get_node(g, student_id)
    career_id = target_career_id or student.get("target_career")
    program = student.get("program")
    completed = q.student_completed(g, student_id)
    core = _recommend_core(g, completed, program, career_id, max_per_semester)
    return {"student_id": student_id, **core}


def plan_for_target(g: nx.DiGraph, completed: set, program: str, career_id: str,
                    max_per_semester: int = DEFAULT_MAX_PER_SEMESTER) -> dict:
    """Simula concluir um curso (talvez diferente do atual) mirando uma carreira,
    reaproveitando as disciplinas já concluídas. Devolve o que falta + o aproveitamento."""
    program_discs = set(q.disciplines_in_program(g, program))
    reused = [d for d in completed if d in program_discs]
    core = _recommend_core(g, set(completed), program, career_id, max_per_semester)
    return {
        **core,
        "reused_count": len(reused),
        "reused_credits": sum(q.credits_of(g, d) for d in reused),
        "semesters_remaining": len(core["semester_plan"]),
    }


def _pack_into_semesters(g, ordered, completed, max_per_semester):
    """Greedy scheduler: place a discipline in the earliest semester after all its
    (not-yet-completed) prerequisites, honoring the per-semester cap."""
    placed: dict[str, int] = {}
    semesters: list[list[str]] = []
    done = set(completed)
    remaining = list(ordered)

    sem_idx = 0
    while remaining:
        semesters.append([])
        progressed = False
        still = []
        for d in remaining:
            prereqs = [p for p in q.direct_prerequisites(g, d) if p in ordered or p not in done]
            unmet = [p for p in prereqs if p not in done and p not in placed]
            if not unmet and len(semesters[sem_idx]) < max_per_semester:
                semesters[sem_idx].append(d)
                placed[d] = sem_idx + 1
                progressed = True
            else:
                still.append(d)
        # Marca como concluídas as alocadas neste semestre (para liberar dependentes).
        for d in semesters[sem_idx]:
            done.add(d)
        remaining = still
        sem_idx += 1
        if not progressed:  # trava de segurança contra dependências impossíveis
            if remaining:
                semesters[sem_idx - 1].extend(remaining)
            break

    return [
        {"semester_offset": i + 1,
         "disciplines": [_disc_brief(g, d, 0.0) for d in block]}
        for i, block in enumerate(semesters) if block
    ]


def _disc_brief(g: nx.DiGraph, disc_id: str, score: float) -> dict:
    d = g.nodes[disc_id]
    return {
        "id": disc_id, "name": d.get("name"), "code": d.get("code"),
        "credits": d.get("credits"), "area": d.get("area"),
        "difficulty": d.get("difficulty"),
        "suggested_semester": d.get("semester_suggested"),
        "relevance": round(score, 3),
        "kb_slug": d.get("kb_slug"),
    }


# --------------------------------------------------------------------------- #
# What-if: impacto de pular uma disciplina
# --------------------------------------------------------------------------- #
def what_if_skip(g: nx.DiGraph, discipline_id: str, career_id: str | None = None) -> dict:
    """Impact of skipping a discipline: which disciplines get blocked and which
    careers lose competency coverage."""
    d = q.get_node(g, discipline_id)
    blocked = q.all_dependents(g, discipline_id)  # dependem (in)diretamente desta

    developed = {c["competency"]: c["weight"] for c in q.competencies_of_discipline(g, discipline_id)}

    affected_careers = []
    for career in [n for n, nd in g.nodes(data=True) if nd.get("type") == "Career"]:
        if career_id and career != career_id:
            continue
        reqs = q.career_competencies(g, career)
        hit = []
        for r in reqs:
            comp = r["competency"]
            if comp not in developed:
                continue
            # Existe outra disciplina (fora esta) que desenvolve a competência?
            alts = [x["discipline"] for x in q.disciplines_developing(g, comp)
                    if x["discipline"] != discipline_id]
            hit.append({
                "competency": comp,
                "importance": r["importance"],
                "weight_lost": round(developed[comp], 3),
                "has_alternative": bool(alts),
                "alternatives": alts,
            })
        if hit:
            affected_careers.append({"career": career, "competencies": hit})

    return {
        "discipline": {"id": discipline_id, "name": d.get("name"), "code": d.get("code")},
        "blocks_disciplines": [_disc_brief(g, x, 0.0) for x in sorted(blocked)],
        "affected_careers": affected_careers,
        "skippable_without_block": len(blocked) == 0,
    }


# --------------------------------------------------------------------------- #
# Comparação de carreiras
# --------------------------------------------------------------------------- #
def compare_careers(g: nx.DiGraph, career_a: str, career_b: str) -> dict:
    a = {r["competency"] for r in q.career_competencies(g, career_a)}
    b = {r["competency"] for r in q.career_competencies(g, career_b)}

    def label(cid):
        return g.nodes[cid].get("name", cid)

    return {
        "career_a": {"id": career_a, "name": g.nodes[career_a].get("name")},
        "career_b": {"id": career_b, "name": g.nodes[career_b].get("name")},
        "shared_competencies": [{"id": c, "name": label(c)} for c in sorted(a & b)],
        "only_a": [{"id": c, "name": label(c)} for c in sorted(a - b)],
        "only_b": [{"id": c, "name": label(c)} for c in sorted(b - a)],
    }


# Relações que carregam sentido acadêmico numa explicação de conexão
# (exclui OFFERED_IN/COMPLETED, que ligam quase tudo trivialmente).
MEANINGFUL_RELATIONS = {"PREREQUISITE_OF", "DEVELOPS_COMPETENCY", "REQUIRES_COMPETENCY", "COMPLEMENTS"}


def explain_connection(g: nx.DiGraph, source_id: str, target_id: str) -> dict:
    """Shortest *meaningful* relationship path between two nodes (why connected?)."""
    sub = nx.DiGraph()
    sub.add_nodes_from(g.nodes(data=True))
    for u, v, d in g.edges(data=True):
        if d.get("relation") in MEANINGFUL_RELATIONS:
            sub.add_edge(u, v, **d)
    und = sub.to_undirected(as_view=True)
    try:
        path = nx.shortest_path(und, source_id, target_id)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return {"connected": False, "path": []}
    steps = []
    for u, v in zip(path, path[1:]):
        # Orienta o passo conforme a aresta real (o grafo é dirigido).
        if sub.has_edge(u, v):
            src, dst = u, v
        else:
            src, dst = v, u
        rel = sub.edges[src, dst]["relation"]
        steps.append({
            "from": u, "from_name": g.nodes[u].get("name", u),
            "to": v, "to_name": g.nodes[v].get("name", v),
            "relation": rel,
            "src": src, "src_name": g.nodes[src].get("name", src),
            "dst": dst, "dst_name": g.nodes[dst].get("name", dst),
        })
    return {"connected": True, "path": steps}
