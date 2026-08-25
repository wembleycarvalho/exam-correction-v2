"""Graph-native analytics over the academic knowledge graph.

These are the "why a graph" insights: they combine PREREQUISITE_OF, OFFERED_IN,
DEVELOPS_COMPETENCY and REQUIRES_COMPETENCY edges to surface things a flat lookup
cannot — bottleneck disciplines, the critical (longest) prerequisite chain, competency
gaps between a student's program and a target career, cross-program (ES×CC) bridge
disciplines and strategic competencies (high career demand, low curriculum coverage).

Pure functions on a NetworkX DiGraph (no LLM, no I/O), deterministic and unit-testable,
mirroring the style of path_engine/queries so they map cleanly to openCypher later.
"""
from __future__ import annotations

import networkx as nx

from ..graph import queries as q
from ..graph.builder import nodes_by_type, prerequisite_subgraph

# Pesos para priorização (mesma convenção do path_engine).
IMPORTANCE_WEIGHT = {"critical": 1.0, "important": 0.6, "nice-to-have": 0.3}
DEMAND_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}


def _disc(g: nx.DiGraph, did: str) -> dict:
    d = g.nodes[did]
    return {
        "id": did, "name": d.get("name"), "code": d.get("code"),
        "area": d.get("area"), "credits": d.get("credits"),
        "difficulty": d.get("difficulty"),
        "suggested_semester": d.get("semester_suggested"),
        "kb_slug": d.get("kb_slug"),
    }


def _in_program(g: nx.DiGraph, did: str, program_id: str | None) -> bool:
    return (program_id is None) or (program_id in (g.nodes[did].get("programs") or []))


# --------------------------------------------------------------------------- #
# 1) Disciplinas-gargalo: quantas disciplinas dependem (in)diretamente de cada uma
# --------------------------------------------------------------------------- #
def prerequisite_bottlenecks(g: nx.DiGraph, program_id: str | None = None,
                             top: int | None = 10) -> list[dict]:
    """Ranqueia disciplinas por quantas outras elas destravam à frente.

    `unlocks_total` = fecho transitivo de dependentes; `unlocks_direct` = dependentes
    imediatos. Se `program_id` vier, restringe o universo às disciplinas do programa.
    """
    prereq = prerequisite_subgraph(g)
    discs = [d for d in prereq.nodes if _in_program(g, d, program_id)]
    rows = []
    for d in discs:
        deps = {x for x in q.all_dependents(g, d) if _in_program(g, x, program_id)}
        direct = [u for u in q.unlocks(g, d) if _in_program(g, u, program_id)]
        if not deps:
            continue
        rows.append({**_disc(g, d), "unlocks_total": len(deps),
                     "unlocks_direct": len(direct)})
    rows.sort(key=lambda r: (r["unlocks_total"], r["unlocks_direct"]), reverse=True)
    return rows[:top] if top else rows


# --------------------------------------------------------------------------- #
# 2) Caminho crítico: a maior cadeia de pré-requisitos (piso de semestres)
# --------------------------------------------------------------------------- #
def critical_path(g: nx.DiGraph, program_id: str | None = None) -> dict:
    """Maior cadeia de PREREQUISITE_OF. O tamanho é o mínimo de semestres se cursadas
    uma de cada vez em sequência — bom para detectar dependências longas demais."""
    prereq = prerequisite_subgraph(g)
    if program_id:
        keep = {d for d in prereq.nodes if _in_program(g, d, program_id)}
        prereq = prereq.subgraph(keep).copy()
    if prereq.number_of_edges() == 0:
        return {"length": 0, "path": []}
    path = nx.dag_longest_path(prereq)
    return {"length": len(path), "path": [_disc(g, d) for d in path]}


# --------------------------------------------------------------------------- #
# 3) Lacunas de competência: programa do aluno x carreira-alvo
# --------------------------------------------------------------------------- #
def competency_gaps(g: nx.DiGraph, student_id: str, career_id: str | None = None) -> dict:
    """Para cada competência exigida pela carreira-alvo, classifica:
      - coberta  : aluno já concluiu disciplina do programa que a desenvolve
      - pendente : o programa oferece disciplina que a desenvolve, mas ainda não cursada
      - lacuna   : nenhuma disciplina do programa do aluno desenvolve a competência
    """
    student = q.get_node(g, student_id)
    program = student.get("program")
    career = career_id or student.get("target_career")
    completed = q.student_completed(g, student_id)
    program_discs = set(q.disciplines_in_program(g, program)) if program else set()

    gaps = []
    for r in q.career_competencies(g, career):
        comp = r["competency"]
        devs = q.disciplines_developing(g, comp)
        in_prog = [x["discipline"] for x in devs if x["discipline"] in program_discs]
        done = [d for d in in_prog if d in completed]
        options = q.order_by_prerequisites(g, [d for d in in_prog if d not in completed])
        if done:
            status = "coberta"
        elif in_prog:
            status = "pendente"
        else:
            status = "lacuna"
        gaps.append({
            "competency": comp,
            "competency_name": g.nodes[comp].get("name", comp),
            "importance": r["importance"],
            "status": status,
            "covered_by_student": bool(done),
            "close_with": [_disc(g, d) for d in options[:5]],
            "developed_elsewhere": status == "lacuna" and bool(devs),
        })

    st_order = {"lacuna": 0, "pendente": 1, "coberta": 2}
    imp_order = {"critical": 0, "important": 1, "nice-to-have": 2}
    gaps.sort(key=lambda x: (st_order.get(x["status"], 9), imp_order.get(x["importance"], 9)))
    return {
        "student_id": student_id, "name": student.get("name"),
        "program": program, "target_career": career,
        "career_name": g.nodes[career].get("name", career),
        "gaps": gaps,
        "summary": {
            "lacunas": sum(1 for x in gaps if x["status"] == "lacuna"),
            "pendentes": sum(1 for x in gaps if x["status"] == "pendente"),
            "cobertas": sum(1 for x in gaps if x["status"] == "coberta"),
        },
    }


# --------------------------------------------------------------------------- #
# 4) Disciplinas-ponte e mapa de currículo (ES × CC)
# --------------------------------------------------------------------------- #
def shared_disciplines(g: nx.DiGraph) -> list[dict]:
    """Disciplinas ofertadas em mais de um programa (pontes entre cursos)."""
    out = []
    for d in nodes_by_type(g, "Discipline"):
        progs = d.get("programs") or []
        if len(progs) > 1:
            out.append({**_disc(g, d["id"]), "programs": progs,
                        "program_names": [g.nodes[p].get("name", p) for p in progs]})
    out.sort(key=lambda r: (-len(r["programs"]), r.get("code") or ""))
    return out


def curriculum_overview(g: nx.DiGraph) -> dict:
    """Mapa dos programas: totais, exclusivas vs compartilhadas, pontes e sobreposição
    par a par entre os cursos."""
    programs = nodes_by_type(g, "Program")
    prog_ids = [p["id"] for p in programs]
    disc_by_prog = {p: set(q.disciplines_in_program(g, p)) for p in prog_ids}

    prog_rows = []
    for p in programs:
        pid = p["id"]
        discs = disc_by_prog[pid]
        exclusive = [d for d in discs if len(g.nodes[d].get("programs") or []) == 1]
        prog_rows.append({
            "id": pid, "name": p.get("name"),
            "total_disciplines": len(discs),
            "exclusive": len(exclusive),
            "shared": len(discs) - len(exclusive),
        })

    overlaps = []
    for i in range(len(prog_ids)):
        for j in range(i + 1, len(prog_ids)):
            a, b = prog_ids[i], prog_ids[j]
            inter = disc_by_prog[a] & disc_by_prog[b]
            overlaps.append({
                "a": a, "a_name": g.nodes[a].get("name"),
                "b": b, "b_name": g.nodes[b].get("name"),
                "shared": len(inter),
                "shared_disciplines": [_disc(g, d) for d in q.order_by_prerequisites(g, list(inter))],
            })

    return {"programs": prog_rows, "bridges": shared_disciplines(g), "overlaps": overlaps}


# --------------------------------------------------------------------------- #
# 5) Competências estratégicas: muita demanda de carreira, pouca oferta no currículo
# --------------------------------------------------------------------------- #
def strategic_competencies(g: nx.DiGraph, top: int | None = None) -> list[dict]:
    """`demand` pondera importância na carreira × nível de demanda da carreira;
    `coverage` é o nº de disciplinas que desenvolvem a competência. `strategic_score`
    alto = alta demanda com baixa cobertura (onde investir primeiro)."""
    careers = nodes_by_type(g, "Career")
    rows = []
    for c in nodes_by_type(g, "Competency"):
        cid = c["id"]
        demand = 0.0
        required_by = []
        for career in careers:
            reqs = {r["competency"]: r["importance"] for r in q.career_competencies(g, career["id"])}
            if cid in reqs:
                w = (IMPORTANCE_WEIGHT.get(reqs[cid], 0.6)
                     * DEMAND_WEIGHT.get(career.get("demand_level"), 0.6))
                demand += w
                required_by.append({
                    "career": career["id"], "name": career.get("name"),
                    "importance": reqs[cid], "demand_level": career.get("demand_level"),
                })
        coverage = len(q.disciplines_developing(g, cid))
        rows.append({
            "competency": cid, "name": c.get("name"),
            "demand": round(demand, 3), "coverage": coverage,
            "strategic_score": round(demand / (coverage + 1), 3),
            "required_by": required_by,
        })
    rows.sort(key=lambda r: (r["strategic_score"], r["demand"]), reverse=True)
    return rows[:top] if top else rows


# --------------------------------------------------------------------------- #
# 6) Relatório de competências de uma carreira, por programa
# --------------------------------------------------------------------------- #
def career_competency_report(g: nx.DiGraph, career_id: str) -> dict:
    """Para uma carreira, lista as competências exigidas e quais programas conseguem
    desenvolvê-las (com as disciplinas), evidenciando lacunas por currículo."""
    programs = [p["id"] for p in nodes_by_type(g, "Program")]
    rows = []
    for r in q.career_competencies(g, career_id):
        comp = r["competency"]
        devs = [x["discipline"] for x in q.disciplines_developing(g, comp)]
        by_program = {}
        for p in programs:
            pd = set(q.disciplines_in_program(g, p))
            covering = [d for d in devs if d in pd]
            by_program[p] = {
                "program_name": g.nodes[p].get("name", p),
                "count": len(covering),
                "disciplines": [_disc(g, d) for d in q.order_by_prerequisites(g, covering)],
            }
        rows.append({
            "competency": comp,
            "competency_name": g.nodes[comp].get("name", comp),
            "importance": r["importance"],
            "total_disciplines": len(devs),
            "by_program": by_program,
        })
    imp_order = {"critical": 0, "important": 1, "nice-to-have": 2}
    rows.sort(key=lambda x: (imp_order.get(x["importance"], 9), -x["total_disciplines"]))
    return {"career": career_id, "career_name": g.nodes[career_id].get("name", career_id),
            "programs": [{"id": p, "name": g.nodes[p].get("name", p)} for p in programs],
            "competencies": rows}


# --------------------------------------------------------------------------- #
# Bundles usados pelas actions do agente
# --------------------------------------------------------------------------- #
def _career_ref(g: nx.DiGraph, cid: str | None) -> dict:
    if not cid:
        return {"id": None, "name": None}
    nd = g.nodes[cid] if cid in g.nodes else {}
    return {"id": cid, "name": nd.get("name", cid), "area": nd.get("area"),
            "demand_level": nd.get("demand_level")}


def _program_ref(g: nx.DiGraph, pid: str | None) -> dict:
    if not pid:
        return {"id": None, "name": None}
    nd = g.nodes[pid] if pid in g.nodes else {}
    return {"id": pid, "name": nd.get("name", pid), "code": nd.get("code")}


def student_profile(g: nx.DiGraph, student_id: str) -> dict:
    """Perfil legível do aluno (nomes, não ids): curso, carreira-alvo, % de conclusão,
    disciplinas concluídas (com nota), pendentes ordenadas por pré-requisito, competências
    já desenvolvidas e próximos passos sugeridos."""
    from . import path_engine as pe  # import tardio evita qualquer ciclo

    student = q.get_node(g, student_id)
    program = student.get("program")
    career = student.get("target_career")
    prog = pe.student_progress(g, student_id)

    completed = []
    for did, d in q._out(g, student_id, "COMPLETED"):
        completed.append({**_disc(g, did),
                          "requirement": q.program_requirement(g, did, program) if program else "mandatory",
                          "grade": d.get("grade"),
                          "semester": d.get("semester"), "year": d.get("year")})
    completed.sort(key=lambda x: (x.get("year") or 0, x.get("semester") or 0, x.get("code") or ""))

    # Matrícula do semestre atual (cursando agora).
    enrolled_ids = q.student_enrolled(g, student_id)
    enrolled = [{**_disc(g, d),
                 "requirement": q.program_requirement(g, d, program) if program else "mandatory"}
                for d in q.order_by_prerequisites(g, list(enrolled_ids))]

    # Faltantes = pendentes que ainda NÃO estão em curso (buckets disjuntos).
    pending = [{**_disc(g, d),
                "requirement": q.program_requirement(g, d, program) if program else "mandatory"}
               for d in q.order_by_prerequisites(g, [p for p in prog["pending"] if p not in enrolled_ids])]

    comp_map: dict[str, set] = {}
    for c in completed:
        for cc in q.competencies_of_discipline(g, c["id"]):
            comp_map.setdefault(cc["competency"], set()).add(c["name"])
    competencies = [{"competency": cid, "name": g.nodes[cid].get("name", cid),
                     "from_disciplines": sorted(v)} for cid, v in comp_map.items()]
    competencies.sort(key=lambda x: x["name"])

    rec = pe.recommend_path(g, student_id, career)
    # Próximos passos = recomendadas que ainda não estão em curso (o que vem DEPOIS do semestre atual).
    next_steps = [d for d in rec.get("recommended_order", []) if d.get("id") not in enrolled_ids][:5]

    # Pedido de troca de curso pendente (se houver) — visível no perfil.
    cc_to = student.get("course_change_to")
    course_change = None
    if cc_to:
        cc_car = student.get("course_change_career")
        course_change = {
            "to_program": _program_ref(g, cc_to),
            "career": (_career_ref(g, cc_car) if cc_car else None),
            "at": student.get("course_change_at"),
            "status": student.get("course_change_status", "pending"),
        }

    return {
        "student_id": student_id,
        "name": student.get("name"),
        "email": student.get("email"),
        "program": _program_ref(g, program),
        "course_change_request": course_change,
        "target_career": _career_ref(g, career),
        "completion_pct": prog["completion_pct"],
        "mandatory": prog.get("mandatory"),
        "electives": prog.get("electives"),
        "counts": {"completed": len(completed), "enrolled": len(enrolled), "pending": len(pending)},
        "completed": completed,
        "enrolled": enrolled,
        "pending": pending,
        "competencies": competencies,
        "recommended_next": next_steps,
    }


# --------------------------------------------------------------------------- #
# Detalhe de Curso (Program) e de Carreira (Career) para as telas de navegação
# --------------------------------------------------------------------------- #
def requirement_of(g: nx.DiGraph, discipline_id: str, program_id: str) -> str:
    """Se a disciplina é obrigatória ('mandatory') ou eletiva ('elective') num curso."""
    return q.program_requirement(g, discipline_id, program_id)


def program_detail(g: nx.DiGraph, program_id: str) -> dict:
    """Visão de um curso: disciplinas (por semestre, com obrigatória/eletiva), distribuição
    por área/dificuldade, créditos, quantas são compartilhadas e alunos matriculados."""
    if program_id not in g.nodes:
        raise KeyError(program_id)
    nd = g.nodes[program_id]
    disc_ids = q.disciplines_in_program(g, program_id)

    by_area: dict[str, int] = {}
    by_diff: dict[str, int] = {}
    total_credits = 0
    mandatory = 0
    elective = 0
    sems: dict[int, list] = {}
    shared = 0
    for did in disc_ids:
        d = g.nodes[did]
        by_area[d.get("area", "?")] = by_area.get(d.get("area", "?"), 0) + 1
        by_diff[d.get("difficulty", "?")] = by_diff.get(d.get("difficulty", "?"), 0) + 1
        total_credits += d.get("credits") or 0
        if len(d.get("programs") or []) > 1:
            shared += 1
        req = requirement_of(g, did, program_id)
        if req == "elective":
            elective += 1
        else:
            mandatory += 1
        sems.setdefault(d.get("semester_suggested") or 0, []).append(
            {**_disc(g, did), "requirement": req})
    semesters = [{"semester": s, "disciplines": sorted(v, key=lambda x: x.get("code") or "")}
                 for s, v in sorted(sems.items())]

    students = [{"name": dd.get("name"),
                 "current_semester": dd.get("current_semester"),
                 "target_career_name": (g.nodes[dd.get("target_career")].get("name")
                                        if dd.get("target_career") in g.nodes else None)}
                for _, dd in g.nodes(data=True)
                if dd.get("type") == "Student" and dd.get("program") == program_id]

    return {
        "id": program_id, "name": nd.get("name"), "code": nd.get("code"),
        "counts": {"disciplines": len(disc_ids), "shared": shared,
                   "exclusive": len(disc_ids) - shared, "credits": total_credits,
                   "mandatory": mandatory, "elective": elective,
                   "elective_credits_required": q.elective_credits_required(g, program_id),
                   "students": len(students)},
        "by_area": by_area, "by_difficulty": by_diff,
        "semesters": semesters, "students": students,
    }


def career_detail(g: nx.DiGraph, career_id: str) -> dict:
    """Visão de uma carreira: meta (área, demanda, ferramentas), competências
    exigidas (com quantas disciplinas as desenvolvem), alunos que a almejam e as
    disciplinas mais relevantes para ela."""
    from . import path_engine as pe  # relevância disciplina x carreira

    if career_id not in g.nodes:
        raise KeyError(career_id)
    nd = g.nodes[career_id]

    imp_order = {"critical": 0, "important": 1, "nice-to-have": 2}
    comps = []
    for r in q.career_competencies(g, career_id):
        comp = r["competency"]
        comps.append({"competency": comp, "name": g.nodes[comp].get("name", comp),
                      "importance": r["importance"],
                      "developed_by": len(q.disciplines_developing(g, comp))})
    comps.sort(key=lambda x: imp_order.get(x["importance"], 9))

    students = [{"name": dd.get("name"),
                 "program_name": (g.nodes[dd.get("program")].get("name")
                                  if dd.get("program") in g.nodes else None)}
                for _, dd in g.nodes(data=True)
                if dd.get("type") == "Student" and dd.get("target_career") == career_id]

    rel = pe.discipline_relevance(g, career_id)
    top = sorted(((did, s) for did, s in rel.items() if s > 0), key=lambda kv: -kv[1])[:8]
    top_disciplines = [{**_disc(g, did), "relevance": round(s, 3)} for did, s in top]

    return {
        "id": career_id, "name": nd.get("name"), "area": nd.get("area"),
        "demand_level": nd.get("demand_level"),
        "key_tools": nd.get("key_tools") or [],
        "competencies": comps, "students": students, "top_disciplines": top_disciplines,
    }


# --------------------------------------------------------------------------- #
# Direcionador de Carreira: questionário por competência -> fit por carreira ->
# alinhamento com o curso -> disciplinas extras / troca de curso
# --------------------------------------------------------------------------- #
# Uma pergunta por competência (mapeada pelo NOME, resolvido para id no grafo).
CAREER_QUESTIONS = [
    ("Gosto de modelar problemas com cálculo, álgebra e abstrações matemáticas.", "Pensamento Matemático"),
    ("Curto raciocínio lógico, provas e problemas de lógica.", "Raciocínio Lógico"),
    ("Gosto de programar: escrever, depurar e organizar código.", "Programação"),
    ("Tenho prazer em resolver problemas com estruturas de dados e algoritmos eficientes.", "Estruturas de Dados e Algoritmos"),
    ("Gosto de estatística, probabilidade e analisar dados sob incerteza.", "Estatística e Probabilidade"),
    ("Curto modelar e consultar bancos de dados (SQL, modelagem).", "Modelagem de Dados"),
    ("Tenho interesse em machine learning e treinar modelos.", "Machine Learning"),
    ("Gosto de projetar, testar e manter sistemas de software.", "Engenharia de Software"),
    ("Me interesso por redes, concorrência e sistemas distribuídos.", "Redes e Sistemas Distribuídos"),
    ("Gosto de infraestrutura, nuvem e automação (DevOps).", "Infraestrutura e Cloud"),
    ("Curto extrair insights e visualizar dados (analytics/BI).", "Análise de Dados"),
    ("Gosto de comunicação, entender o negócio e pensar o produto.", "Comunicação e Produto"),
    ("Tenho interesse em segurança da informação e proteção de sistemas.", "Segurança da Informação"),
    ("Curto entender por dentro o sistema operacional (processos, memória, kernel).", "Sistemas Operacionais"),
    ("Gosto de otimização e pesquisa operacional (modelos de decisão).", "Otimização e Pesquisa Operacional"),
    ("Me interesso por física, mecânica, forças e movimento.", "Física e Mecânica"),
    ("Gosto de termodinâmica, energia, calor e fluidos.", "Termodinâmica e Fluidos"),
    ("Tenho interesse em materiais: estrutura, propriedades e seleção.", "Ciência dos Materiais"),
    ("Curto processos de fabricação, automação e manutenção industrial.", "Manufatura e Processos"),
    ("Gosto de gestão da qualidade, melhoria contínua e controle estatístico.", "Gestão da Qualidade"),
    ("Me interesso por logística e cadeia de suprimentos.", "Logística e Cadeia de Suprimentos"),
    ("Gosto de mapear e melhorar processos e operações.", "Gestão de Processos e Operações"),
    ("Curto criar interfaces web e cuidar da experiência do usuário (front-end/UX).", "Desenvolvimento Front-end e UX"),
    ("Tenho interesse em administrar bancos de dados em produção (tuning, backup).", "Administração de Banco de Dados"),
    ("Me importo com governança, privacidade e ética de dados (LGPD).", "Governança e Ética de Dados"),
]


def career_questionnaire(g: nx.DiGraph) -> list[dict]:
    """Perguntas do direcionador, cada uma ligada a uma competência existente no grafo."""
    name2id = {d.get("name"): n for n, d in g.nodes(data=True) if d.get("type") == "Competency"}
    out = []
    for text, cname in CAREER_QUESTIONS:
        cid = name2id.get(cname)
        if cid:
            out.append({"competency": cid, "competency_name": cname, "question": text})
    return out


def score_careers(g: nx.DiGraph, interest: dict, top: int | None = None) -> list[dict]:
    """Pontua cada carreira pelo interesse do aluno nas competências que ela exige.
    `interest`: {competency_id: 0..1}. Competência não respondida = 0.5 (neutro).
    fit = média ponderada (por importância) do interesse nas competências exigidas."""
    rows = []
    for c in nodes_by_type(g, "Career"):
        cid = c["id"]
        num = den = 0.0
        for r in q.career_competencies(g, cid):
            w = IMPORTANCE_WEIGHT.get(r["importance"], 0.6)
            den += w
            num += w * float(interest.get(r["competency"], 0.5))
        fit = (num / den) if den else 0.0
        rows.append({"career": cid, "name": c.get("name"), "area": c.get("area"),
                     "demand_level": c.get("demand_level"),
                     "fit": round(fit, 4), "fit_pct": round(100 * fit, 1)})
    rows.sort(key=lambda x: (x["fit"], DEMAND_WEIGHT.get(x["demand_level"], 0.6)), reverse=True)
    return rows[:top] if top else rows


def program_coverage(g: nx.DiGraph, program_id: str, career_id: str) -> dict:
    """Quanto um curso cobre das competências exigidas por uma carreira (ponderado por
    importância). Retorna score 0..1 + competências cobertas e faltantes."""
    prog_discs = set(q.disciplines_in_program(g, program_id))
    total = cov = 0.0
    covered, missing = [], []
    for r in q.career_competencies(g, career_id):
        comp = r["competency"]
        w = IMPORTANCE_WEIGHT.get(r["importance"], 0.6)
        total += w
        devs = {x["discipline"] for x in q.disciplines_developing(g, comp)}
        entry = {"competency": comp, "name": g.nodes[comp].get("name", comp), "importance": r["importance"]}
        if devs & prog_discs:
            cov += w
            covered.append(entry)
        else:
            missing.append(entry)
    return {"score": round(cov / total, 4) if total else 0.0,
            "score_pct": round(100 * cov / total, 1) if total else 0.0,
            "covered": covered, "missing": missing}


def pending_course_changes(g: nx.DiGraph) -> list[dict]:
    """Pedidos de troca de curso pendentes (para a tela do coordenador)."""
    out = []
    for n, d in g.nodes(data=True):
        if d.get("type") == "Student" and d.get("course_change_to"):
            car = d.get("course_change_career")
            out.append({
                "student_id": n, "name": d.get("name"),
                "from_program": _program_ref(g, d.get("program")),
                "to_program": _program_ref(g, d.get("course_change_to")),
                "career": (_career_ref(g, car) if car else None),
                "at": d.get("course_change_at"),
                "status": d.get("course_change_status", "pending"),
            })
    out.sort(key=lambda x: x.get("at") or "")
    return out


def career_fit_report(g: nx.DiGraph, student_id: str, career_id: str) -> dict:
    """Relatório de aderência do aluno a uma carreira: alinhamento do curso ATUAL,
    competências faltantes + disciplinas extras (eletivas do curso ou externas), melhor
    curso alternativo e o que faltaria em cada um reaproveitando as concluídas."""
    from . import path_engine as pe

    student = q.get_node(g, student_id)
    program = student.get("program")
    completed = q.student_completed(g, student_id)

    cur_cov = program_coverage(g, program, career_id)
    cur_disc = set(q.disciplines_in_program(g, program))

    # Disciplinas extras para cobrir as competências faltantes.
    extras = []
    for m in cur_cov["missing"]:
        devs = [x["discipline"] for x in q.disciplines_developing(g, m["competency"])]
        in_prog = [d for d in devs if d in cur_disc]   # eletivas do próprio curso
        external = [d for d in devs if d not in cur_disc]
        extras.append({
            "competency_name": m["name"], "importance": m["importance"],
            "in_program": [_disc(g, d) for d in q.order_by_prerequisites(g, in_prog)][:4],
            "external": [{**_disc(g, d),
                          "programs": [g.nodes[p].get("name", p) for p in (g.nodes[d].get("programs") or [])]}
                         for d in external][:4],
        })

    # Melhor curso alternativo para essa carreira.
    programs = nodes_by_type(g, "Program")
    cov_by_prog = {p["id"]: program_coverage(g, p["id"], career_id)["score"] for p in programs}
    best_pid = max(cov_by_prog, key=lambda p: cov_by_prog[p])

    def prog_ref(pid):
        return {"id": pid, "name": g.nodes[pid].get("name", pid),
                "coverage_pct": round(100 * cov_by_prog[pid], 1)}

    current_plan = pe.plan_for_target(g, completed, program, career_id)
    best_plan = pe.plan_for_target(g, completed, best_pid, career_id) if best_pid != program else current_plan

    change = (best_pid != program) and (cov_by_prog[best_pid] - cov_by_prog[program] >= 0.15)
    return {
        "career": career_id, "career_name": g.nodes[career_id].get("name", career_id),
        "student_program": prog_ref(program),
        "aligned": cur_cov["score"] >= 0.7,
        "current": {**prog_ref(program), "missing": cur_cov["missing"], "extras": extras,
                    "faltam_disciplinas": current_plan["total_disciplines"],
                    "faltam_creditos": current_plan["credits_remaining"],
                    "semestres_restantes": current_plan["semesters_remaining"]},
        "best_program": {**prog_ref(best_pid),
                         "faltam_disciplinas": best_plan["total_disciplines"],
                         "faltam_creditos": best_plan["credits_remaining"],
                         "semestres_restantes": best_plan["semesters_remaining"],
                         "aproveita_disciplinas": best_plan["reused_count"],
                         "aproveita_creditos": best_plan["reused_credits"]},
        "change_recommended": change,
    }


# --------------------------------------------------------------------------- #
# Subgrafo para visualização (força dirigida no frontend)
# --------------------------------------------------------------------------- #
REL_PT = {
    "PREREQUISITE_OF": "pré-requisito de",
    "DEVELOPS_COMPETENCY": "desenvolve",
    "REQUIRES_COMPETENCY": "exige",
    "COMPLEMENTS": "complementa",
    "OFFERED_IN": "ofertada em",
    "COMPLETED": "concluiu",
    "TARGETS": "almeja",
}


def _viz_node(g: nx.DiGraph, nid: str) -> dict:
    d = g.nodes[nid]
    return {"id": nid, "label": d.get("name", nid), "type": d.get("type", "?"),
            "code": d.get("code"), "area": d.get("area")}


def subgraph(g: nx.DiGraph, scope: str = "full", node_id: str | None = None) -> dict:
    """Monta um subgrafo (nós + arestas) amigável para visualização em força dirigida.

    scope:
      full       -> grafo inteiro
      student    -> aluno + disciplinas concluídas + competências delas + carreira-alvo
      discipline -> disciplina + pré-requisitos + o que destrava + competências + cursos + alunos
      career     -> carreira + competências exigidas + disciplinas que as desenvolvem + alunos
    Labels usam o NOME (nunca ids internos).
    """
    keep: list[tuple[str, str, str]] = []
    nodes: set[str] = set()
    status: dict[str, str] = {}  # nó -> done|todo|career|student (usado no escopo student)

    def add(u: str, v: str, rel: str):
        if u in g.nodes and v in g.nodes:
            nodes.add(u); nodes.add(v); keep.append((u, v, rel))

    if scope == "full":
        nodes.update(g.nodes)
        keep = [(u, v, d.get("relation", "?")) for u, v, d in g.edges(data=True)]
    elif scope == "student":
        # Mapa "aluno -> carreira": competências exigidas pela carreira-alvo e as
        # disciplinas do curso que as desenvolvem, marcadas por status (concluída/alcançada
        # em verde; falta em azul). A carreira aparece em destaque.
        if node_id not in g.nodes:
            raise KeyError(node_id)
        nodes.add(node_id)
        completed = q.student_completed(g, node_id)
        program = g.nodes[node_id].get("program")
        program_discs = set(q.disciplines_in_program(g, program)) if program else set()
        career = g.nodes[node_id].get("target_career")
        req_comps = ([c for c, _ in q._out(g, career, "REQUIRES_COMPETENCY")]
                     if career and career in g.nodes else [])
        req_set = set(req_comps)
        if career and career in g.nodes:
            add(node_id, career, "TARGETS")
            for comp in req_comps:
                add(career, comp, "REQUIRES_COMPETENCY")
        # disciplinas relevantes: do curso e que desenvolvem alguma competência exigida
        relevant = set()
        for comp in req_comps:
            for disc in q.disciplines_developing(g, comp):
                d = disc["discipline"]
                if not program_discs or d in program_discs:
                    relevant.add(d)
        for d in relevant:
            for comp, _ in q._out(g, d, "DEVELOPS_COMPETENCY"):
                if comp in req_set:
                    add(d, comp, "DEVELOPS_COMPETENCY")
            if d in completed:
                add(node_id, d, "COMPLETED")
        # status por nó
        achieved = {c for c in req_set
                    if {x["discipline"] for x in q.disciplines_developing(g, c)} & completed}
        for n in nodes:
            t = g.nodes[n].get("type")
            if n == node_id:
                status[n] = "student"
            elif n == career:
                status[n] = "career"
            elif t == "Competency":
                status[n] = "done" if n in achieved else "todo"
            elif t == "Discipline":
                status[n] = "done" if n in completed else "todo"
    elif scope == "discipline":
        if node_id not in g.nodes:
            raise KeyError(node_id)
        nodes.add(node_id)
        for p in q.direct_prerequisites(g, node_id):
            add(p, node_id, "PREREQUISITE_OF")
        for v in q.unlocks(g, node_id):
            add(node_id, v, "PREREQUISITE_OF")
        for cc in q.competencies_of_discipline(g, node_id):
            add(node_id, cc["competency"], "DEVELOPS_COMPETENCY")
        for prog in (g.nodes[node_id].get("programs") or []):
            add(node_id, prog, "OFFERED_IN")
        for u, _, d in g.in_edges(node_id, data=True):
            if d.get("relation") == "COMPLETED":
                add(u, node_id, "COMPLETED")
    elif scope == "career":
        if node_id not in g.nodes:
            raise KeyError(node_id)
        nodes.add(node_id)
        for comp, _ in q._out(g, node_id, "REQUIRES_COMPETENCY"):
            add(node_id, comp, "REQUIRES_COMPETENCY")
            for disc in q.disciplines_developing(g, comp):
                add(disc["discipline"], comp, "DEVELOPS_COMPETENCY")
        for n, d in g.nodes(data=True):
            if d.get("type") == "Student" and d.get("target_career") == node_id:
                add(n, node_id, "TARGETS")
    else:
        raise ValueError(f"escopo inválido: {scope!r}")

    deg: dict[str, int] = {}
    for u, v, _ in keep:
        deg[u] = deg.get(u, 0) + 1
        deg[v] = deg.get(v, 0) + 1

    node_list = []
    for n in nodes:
        nd = _viz_node(g, n)
        nd["degree"] = deg.get(n, 0)
        nd["status"] = status.get(n)
        node_list.append(nd)
    node_list.sort(key=lambda x: (-x["degree"], x["label"] or ""))
    edge_list = [{"source": u, "target": v, "relation": r, "label": REL_PT.get(r, r)}
                 for u, v, r in keep]

    focus = _viz_node(g, node_id) if (node_id and node_id in g.nodes) else None
    return {"scope": scope, "focus": focus,
            "nodes": node_list, "edges": edge_list,
            "counts": {"nodes": len(node_list), "edges": len(edge_list)}}


def student_insights(g: nx.DiGraph, student_id: str, career_id: str | None = None) -> dict:
    """Pacote centrado no aluno: gargalos do seu programa, caminho crítico do programa
    e lacunas de competência para a carreira-alvo."""
    student = q.get_node(g, student_id)
    program = student.get("program")
    return {
        "student_id": student_id, "name": student.get("name"), "program": program,
        "bottlenecks": prerequisite_bottlenecks(g, program_id=program, top=8),
        "critical_path": critical_path(g, program_id=program),
        "competency_gaps": competency_gaps(g, student_id, career_id),
    }
