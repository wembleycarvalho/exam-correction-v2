"""Strands tools that let the agent query the academic knowledge graph.

Each tool wraps a tested engine function (queries/path_engine) over the graph hydrated
from Neptune. Names in the student's question are resolved to graph ids by fuzzy match.
The current student is carried in a ContextVar set per request by the entrypoint.
"""
from __future__ import annotations

import difflib
import json
from contextvars import ContextVar

import networkx as nx
from strands import tool

from src.graph import queries as q
from src.recommender import path_engine as pe
from src.recommender import insights as ins

_GRAPH: nx.DiGraph | None = None
CURRENT_STUDENT: ContextVar[str] = ContextVar("current_student", default="")


def set_graph(g: nx.DiGraph) -> None:
    global _GRAPH
    _GRAPH = g


def _g() -> nx.DiGraph:
    if _GRAPH is None:
        raise RuntimeError("grafo não carregado")
    return _GRAPH


def _resolve(name: str, node_type: str) -> str | None:
    g = _g()
    name = (name or "").strip().lower()
    m = {d.get("name", "").lower(): n for n, d in g.nodes(data=True) if d.get("type") == node_type}
    if name in m:
        return m[name]
    match = difflib.get_close_matches(name, list(m), n=1, cutoff=0.6)
    if match:
        return m[match[0]]
    for nm, nid in m.items():
        if name and (name in nm or nm in name):
            return nid
    return None


def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


@tool
def progresso_aluno() -> str:
    """Progresso do aluno atual: disciplinas concluídas, pendentes e % do curso.
    Retorna os NOMES das disciplinas (nunca ids internos)."""
    g = _g()
    p = pe.student_progress(g, CURRENT_STUDENT.get())
    nm = lambda i: g.nodes[i].get("name", i) if i in g.nodes else i
    return _j({
        "aluno": p.get("name"),
        "curso": nm(p.get("program")),
        "percentual_concluido": p.get("completion_pct"),
        "concluidas": [nm(x) for x in p.get("completed", [])],
        "pendentes": [nm(x) for x in p.get("pending", [])],
    })


@tool
def minha_matricula() -> str:
    """Disciplinas que o aluno atual está cursando NESTE semestre (matrícula corrente).
    Retorna os NOMES das disciplinas (nunca ids internos)."""
    g = _g()
    enr = q.student_enrolled(g, CURRENT_STUDENT.get())
    nm = lambda i: g.nodes[i].get("name", i) if i in g.nodes else i
    return _j({"em_curso": sorted(nm(x) for x in enr), "total": len(enr)})


@tool
def recomendar_trilha(carreira: str = "") -> str:
    """Recomenda a trilha de disciplinas (plano por semestre) do aluno atual para uma
    carreira. Se `carreira` vier vazio, usa a carreira-alvo do aluno."""
    cid = _resolve(carreira, "Career") if carreira else None
    return _j(pe.recommend_path(_g(), CURRENT_STUDENT.get(), cid))


@tool
def checar_prerequisito(disciplina: str) -> str:
    """Pré-requisitos de uma disciplina (por nome) e o impacto de pulá-la."""
    g = _g()
    did = _resolve(disciplina, "Discipline")
    if not did:
        return _j({"erro": "disciplina não encontrada", "disciplina": disciplina})
    return _j({
        "disciplina": g.nodes[did].get("name"),
        "prerequisitos_diretos": [g.nodes[p].get("name") for p in q.direct_prerequisites(g, did)],
        "impacto_de_pular": pe.what_if_skip(g, did),
    })


@tool
def comparar_carreiras(carreira_a: str, carreira_b: str) -> str:
    """Compara as competências exigidas por duas carreiras (por nome)."""
    g = _g()
    a, b = _resolve(carreira_a, "Career"), _resolve(carreira_b, "Career")
    if not a or not b:
        return _j({"erro": "carreira não encontrada", "a": carreira_a, "b": carreira_b})
    return _j(pe.compare_careers(g, a, b))


@tool
def explicar_conexao(item_a: str, item_b: str) -> str:
    """Explica a conexão acadêmica (pré-requisito/competência) entre duas
    disciplinas e/ou carreiras (por nome)."""
    g = _g()
    a = _resolve(item_a, "Discipline") or _resolve(item_a, "Career")
    b = _resolve(item_b, "Discipline") or _resolve(item_b, "Career")
    if not a or not b:
        return _j({"erro": "item não encontrado", "a": item_a, "b": item_b})
    return _j(pe.explain_connection(g, a, b))


@tool
def gargalos_do_curso() -> str:
    """Disciplinas-gargalo do curso do aluno atual: as que mais destravam outras
    disciplinas à frente (bom para priorizar). Inclui também o caminho crítico
    (maior cadeia de pré-requisitos) do curso."""
    g = _g()
    student = q.get_node(g, CURRENT_STUDENT.get())
    program = student.get("program")
    return _j({
        "bottlenecks": ins.prerequisite_bottlenecks(g, program_id=program, top=8),
        "critical_path": ins.critical_path(g, program_id=program),
    })


@tool
def lacunas_de_competencia(carreira: str = "") -> str:
    """Lacunas de competência entre o curso do aluno atual e a carreira-alvo: quais
    competências exigidas não são desenvolvidas por nenhuma disciplina do curso
    (lacuna), quais estão pendentes e quais já foram cobertas. `carreira` opcional
    (por nome); vazio usa a carreira-alvo do aluno."""
    cid = _resolve(carreira, "Career") if carreira else None
    return _j(ins.competency_gaps(_g(), CURRENT_STUDENT.get(), cid))


TOOLS = [progresso_aluno, minha_matricula, recomendar_trilha, checar_prerequisito,
         comparar_carreiras, explicar_conexao,
         gargalos_do_curso, lacunas_de_competencia]


# --------------------------- Ferramentas do COORDENADOR (cruzam TODOS os alunos) --------------------------- #
# Não usam CURRENT_STUDENT: operam sobre o conjunto de alunos do grafo. Só entram no
# toolset quando o chat está no modo coordenação (ver entrypoint._ask).
def _students(g):
    return [(n, d) for n, d in g.nodes(data=True) if d.get("type") == "Student"]


def _pname(g, pid):
    return g.nodes[pid].get("name", pid) if pid in g.nodes else pid


@tool
def alunos_do_curso(curso: str) -> str:
    """Lista os alunos matriculados em um CURSO (programa), pelo nome do curso
    (ex.: 'Banco de Dados', 'Engenharia de Software'). Uso do coordenador."""
    g = _g()
    pid = _resolve(curso, "Program")
    if not pid:
        return _j({"erro": "curso não encontrado", "curso": curso})
    alunos = sorted(d.get("name") for _, d in _students(g) if d.get("program") == pid)
    return _j({"curso": _pname(g, pid), "total": len(alunos), "alunos": alunos})


@tool
def alunos_por_disciplina(disciplina: str) -> str:
    """Lista os alunos que já cursaram (concluíram) uma DISCIPLINA (por nome), agrupados
    por curso — útil para ver alunos de cursos diferentes que estudaram a mesma
    disciplina. Uso do coordenador."""
    g = _g()
    did = _resolve(disciplina, "Discipline")
    if not did:
        return _j({"erro": "disciplina não encontrada", "disciplina": disciplina})
    por_curso: dict[str, list] = {}
    for n, d in _students(g):
        if did in q.student_completed(g, n):
            por_curso.setdefault(_pname(g, d.get("program")), []).append(d.get("name"))
    total = sum(len(v) for v in por_curso.values())
    return _j({"disciplina": g.nodes[did].get("name"), "total": total,
               "cursos_distintos": sorted(por_curso),
               "por_curso": {k: sorted(v) for k, v in sorted(por_curso.items())}})


@tool
def alunos_por_competencia(competencia: str) -> str:
    """Lista os alunos que desenvolveram uma COMPETÊNCIA (por terem concluído disciplinas
    que a desenvolvem), agrupados por curso. Ideal para achar alunos de CURSOS DIFERENTES
    estudando a mesma competência (`multiplos_cursos`). Uso do coordenador."""
    g = _g()
    cid = _resolve(competencia, "Competency")
    if not cid:
        return _j({"erro": "competência não encontrada", "competencia": competencia})
    discs = {r["discipline"] for r in q.disciplines_developing(g, cid)}
    por_curso: dict[str, list] = {}
    for n, d in _students(g):
        via = q.student_completed(g, n) & discs
        if via:
            por_curso.setdefault(_pname(g, d.get("program")), []).append({
                "aluno": d.get("name"),
                "via": sorted(g.nodes[x].get("name", x) for x in via)})
    total = sum(len(v) for v in por_curso.values())
    return _j({"competencia": g.nodes[cid].get("name"), "total": total,
               "cursos_distintos": sorted(por_curso), "multiplos_cursos": len(por_curso) > 1,
               "por_curso": {k: v for k, v in sorted(por_curso.items())}})


@tool
def alunos_por_carreira(carreira: str) -> str:
    """Lista os alunos cuja carreira-alvo é a informada (por nome), agrupados por curso.
    Uso do coordenador."""
    g = _g()
    cid = _resolve(carreira, "Career")
    if not cid:
        return _j({"erro": "carreira não encontrada", "carreira": carreira})
    por_curso: dict[str, list] = {}
    for n, d in _students(g):
        if d.get("target_career") == cid:
            por_curso.setdefault(_pname(g, d.get("program")), []).append(d.get("name"))
    total = sum(len(v) for v in por_curso.values())
    return _j({"carreira": g.nodes[cid].get("name"), "total": total,
               "por_curso": {k: sorted(v) for k, v in sorted(por_curso.items())}})


@tool
def disciplinas_do_curso(curso: str) -> str:
    """Lista as DISCIPLINAS oferecidas em um curso (pelo nome do curso), com o tipo
    (obrigatória/eletiva) e quantos alunos DO CURSO já cursaram cada uma. Responde
    'quais as disciplinas do curso X e quantos alunos por disciplina'. Uso do coordenador."""
    g = _g()
    pid = _resolve(curso, "Program")
    if not pid:
        return _j({"erro": "curso não encontrado", "curso": curso})
    alunos = [n for n, d in _students(g) if d.get("program") == pid]
    cont: dict[str, int] = {}
    cont_enr: dict[str, int] = {}
    for sid in alunos:
        for did in q.student_completed(g, sid):
            cont[did] = cont.get(did, 0) + 1
        for did in q.student_enrolled(g, sid):
            cont_enr[did] = cont_enr.get(did, 0) + 1
    rows = []
    for did in q.disciplines_in_program(g, pid):
        nd = g.nodes[did]
        rows.append({"disciplina": nd.get("name"), "codigo": nd.get("code"),
                     "tipo": q.program_requirement(g, did, pid),
                     "matriculados_agora": cont_enr.get(did, 0),
                     "alunos_do_curso_que_cursaram": cont.get(did, 0)})
    rows.sort(key=lambda r: (r["tipo"] != "mandatory", r["disciplina"]))
    return _j({"curso": _pname(g, pid), "total_alunos_curso": len(alunos),
               "total_matriculas_no_semestre": sum(cont_enr.get(r_did, 0)
                                                    for r_did in q.disciplines_in_program(g, pid)),
               "total_disciplinas": len(rows), "disciplinas": rows,
               "observacao": "matriculados_agora = alunos do curso cursando a disciplina NESTE semestre; "
                             "alunos_do_curso_que_cursaram = já concluíram (histórico)."})


@tool
def alunos_matriculados_por_disciplina(disciplina: str) -> str:
    """Lista os alunos MATRICULADOS (cursando NESTE semestre) numa DISCIPLINA (por nome),
    agrupados por curso. Responde 'quantos/quais alunos estão cursando X agora'. Uso do coordenador."""
    g = _g()
    did = _resolve(disciplina, "Discipline")
    if not did:
        return _j({"erro": "disciplina não encontrada", "disciplina": disciplina})
    por_curso: dict[str, list] = {}
    for n, d in _students(g):
        if did in q.student_enrolled(g, n):
            por_curso.setdefault(_pname(g, d.get("program")), []).append(d.get("name"))
    total = sum(len(v) for v in por_curso.values())
    return _j({"disciplina": g.nodes[did].get("name"), "matriculados_neste_semestre": total,
               "cursos_distintos": sorted(por_curso),
               "por_curso": {k: sorted(v) for k, v in sorted(por_curso.items())}})


_DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _slot_labels(n: int) -> list[str]:
    """Horários noturnos a partir das 19:00: aulas de 100 min com 10 min de intervalo."""
    out = []
    for k in range(n):
        start = 19 * 60 + k * 110
        end = start + 100
        out.append(f"{start // 60:02d}:{start % 60:02d}-{(end // 60) % 24:02d}:{end % 60:02d}")
    return out


@tool
def _build_night_grid(g, pid, noites: int, aulas_por_noite: int) -> dict:
    """Núcleo determinístico da grade noturna (reutilizado pela grade geral e pela do aluno).
    Aloca cada disciplina com matrícula num horário, garantindo que disciplinas com aluno em
    comum não coincidam, equilibrando a carga. Retorna o slot de cada disciplina + labels."""
    alunos_por_disc: dict[str, set] = {}
    for n, _ in _students(g):
        for did in q.student_enrolled(g, n):
            alunos_por_disc.setdefault(did, set()).add(n)
    if pid:
        prog = set(q.disciplines_in_program(g, pid))
        alunos_por_disc = {k: v for k, v in alunos_por_disc.items() if k in prog}
    discs = list(alunos_por_disc)
    conflita = {d: set() for d in discs}
    for i in range(len(discs)):
        for j in range(i + 1, len(discs)):
            a, b = discs[i], discs[j]
            if alunos_por_disc[a] & alunos_por_disc[b]:
                conflita[a].add(b); conflita[b].add(a)
    noites = max(1, int(noites)); aulas_por_noite = max(1, int(aulas_por_noite))
    n_slots = noites * aulas_por_noite
    ordem = sorted(discs, key=lambda d: (-len(conflita[d]), -len(alunos_por_disc[d])))
    carga: list[list[str]] = [[] for _ in range(n_slots)]
    slot_de: dict[str, int] = {}
    sem_encaixe: list[str] = []
    for d in ordem:
        viaveis = [s for s in range(n_slots) if not any(x in conflita[d] for x in carga[s])]
        s = (min(viaveis, key=lambda s: len(carga[s])) if viaveis
             else min(range(n_slots), key=lambda s: len(carga[s])))
        if not viaveis:
            sem_encaixe.append(g.nodes[d].get("name", d))
        carga[s].append(d); slot_de[d] = s
    return {"alunos_por_disc": alunos_por_disc, "carga": carga, "slot_de": slot_de,
            "sem_encaixe": sem_encaixe, "n_slots": n_slots, "noites": noites,
            "aulas_por_noite": aulas_por_noite, "dias": _DIAS[:noites],
            "horarios": _slot_labels(aulas_por_noite)}


def _slot_ref(grid: dict, s: int) -> tuple[str, str]:
    return grid["dias"][s // grid["aulas_por_noite"]], grid["horarios"][s % grid["aulas_por_noite"]]


@tool
def montar_grade_noturna(curso: str = "", noites: int = 5, aulas_por_noite: int = 2) -> str:
    """Monta uma GRADE de horários NOTURNA e estima o nº de SALAS a partir da MATRÍCULA real:
    duas disciplinas com pelo menos um aluno em comum NUNCA caem no mesmo horário (grafo de
    conflito). Modelo determinístico com premissas EXPLÍCITAS. Parâmetros: `curso` (opcional,
    restringe às disciplinas do curso), `noites` (noites/semana, padrão 5 = seg–sex),
    `aulas_por_noite` (padrão 2). Premissas: 1 turma por disciplina e 1 encontro semanal.
    Aloca balanceando a carga para minimizar salas. Uso do coordenador."""
    g = _g()
    pid = _resolve(curso, "Program") if curso else None
    grid = _build_night_grid(g, pid, noites, aulas_por_noite)
    if not grid["slot_de"]:
        return _j({"erro": "nenhuma disciplina com matrícula neste semestre"
                          + (f" no curso {curso}" if curso else "")})
    salas = max(len(c) for c in grid["carga"])
    grade = []
    for s in range(grid["n_slots"]):
        if not grid["carga"][s]:
            continue
        dia, hora = _slot_ref(grid, s)
        grade.append({"dia": dia, "horario": hora, "salas_no_horario": len(grid["carga"][s]),
                      "disciplinas": [{"disciplina": g.nodes[d].get("name", d),
                                       "alunos": len(grid["alunos_por_disc"][d])}
                                      for d in grid["carga"][s]]})
    return _j({
        "premissas": {"turno": "noturno", "noites_semana": grid["noites"],
                      "aulas_por_noite": grid["aulas_por_noite"], "horarios_semana": grid["n_slots"],
                      "modelo": "1 turma e 1 encontro semanal por disciplina; disciplinas com "
                                "aluno(s) em comum não coincidem no horário"},
        "curso": _pname(g, pid) if pid else "todos os cursos",
        "total_disciplinas": len(grid["slot_de"]),
        "salas_necessarias": salas,
        "professores_no_pico": salas,
        "observacao_professores": ("não há dado de PROFESSOR nem de capacidade de sala na base; "
                                   f"no horário de pico há {salas} aulas simultâneas (mínimo de salas e "
                                   "de professores atuando ao mesmo tempo). O total de professores "
                                   "depende da carga por professor."),
        "disciplinas_sem_encaixe": grid["sem_encaixe"],
        "grade": grade,
    })


@tool
def grade_do_aluno(aluno: str, noites: int = 5, aulas_por_noite: int = 2) -> str:
    """Agenda pessoal de um ALUNO (por nome): em quais DIAS e HORÁRIOS ele tem aula neste
    semestre, cruzando a matrícula dele com a MESMA grade noturna de montar_grade_noturna
    (mesmos parâmetros/premissas → os horários batem com a grade geral). Responde 'quais dias/
    horários o aluno X tem aula'. Uso do coordenador."""
    g = _g()
    sid = _resolve(aluno, "Student")
    if not sid:
        return _j({"erro": "aluno não encontrado", "aluno": aluno})
    grid = _build_night_grid(g, None, noites, aulas_por_noite)
    aulas = []
    for did in q.student_enrolled(g, sid):
        if did in grid["slot_de"]:
            dia, hora = _slot_ref(grid, grid["slot_de"][did])
            aulas.append({"dia": dia, "horario": hora, "disciplina": g.nodes[did].get("name", did),
                          "codigo": g.nodes[did].get("code")})
    ordem_dia = {d: i for i, d in enumerate(grid["dias"])}
    aulas.sort(key=lambda a: (ordem_dia.get(a["dia"], 9), a["horario"]))
    return _j({"aluno": g.nodes[sid].get("name"), "curso": _pname(g, g.nodes[sid].get("program")),
               "premissas": {"noites_semana": grid["noites"], "aulas_por_noite": grid["aulas_por_noite"]},
               "total_disciplinas": len(aulas), "aulas": aulas})


@tool
def matriculas_por_disciplina() -> str:
    """Total de alunos MATRICULADOS neste semestre em CADA disciplina, considerando TODOS os
    cursos, ordenado do maior para o menor. Responde 'quantos alunos tenho matriculado por
    disciplina' sem precisar informar um curso específico. Uso do coordenador."""
    g = _g()
    cont: dict[str, int] = {}
    for n, _ in _students(g):
        for did in q.student_enrolled(g, n):
            cont[did] = cont.get(did, 0) + 1
    rows = [{"disciplina": g.nodes[did].get("name", did), "codigo": g.nodes[did].get("code"),
             "matriculados": c} for did, c in cont.items()]
    rows.sort(key=lambda r: (-r["matriculados"], r["disciplina"]))
    return _j({"total_matriculas": sum(cont.values()),
               "disciplinas_com_matricula": len(rows), "por_disciplina": rows})


@tool
def visao_geral_cursos() -> str:
    """Visão geral para o coordenador: total de alunos por curso (todos os cursos)."""
    g = _g()
    counts: dict[str, int] = {}
    for _, d in _students(g):
        k = _pname(g, d.get("program"))
        counts[k] = counts.get(k, 0) + 1
    return _j({"total_alunos": sum(counts.values()), "por_curso": dict(sorted(counts.items()))})


COORD_TOOLS = [alunos_do_curso, disciplinas_do_curso, alunos_matriculados_por_disciplina,
               matriculas_por_disciplina, montar_grade_noturna, grade_do_aluno,
               alunos_por_disciplina, alunos_por_competencia, alunos_por_carreira,
               visao_geral_cursos]
