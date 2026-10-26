"""Tools do Orientador Context — consultas ao data lake do Moodle via Athena.

Cada tool vira SQL parametrizado/sanitizado sobre o catálogo `moodle_datalake`
(alunos, cursos, matriculas, notas, competencias) + alguns algoritmos em Python
(ex.: grade noturna conflito-consciente).

Adaptação: o Moodle não tem grafo de pré-requisito nem carreiras. As features do
Orientador Acadêmico que dependiam disso foram adaptadas ao que o dado suporta
(progresso = concluídas/total do curso; trilha = a refazer/pendentes; etc.).

RBAC: em modo aluno, as tools de aluno são FORÇADAS ao `student_id` da sessão e as
tools de coordenação ficam indisponíveis (imposto no handler via `execute`).
"""
import re

from athena import query

_USERNAME_RE = re.compile(r"^(aluno|prof)\d{1,6}$")


def _san_username(u):
    u = (u or "").strip()
    if not _USERNAME_RE.match(u):
        raise ValueError("username invalido (esperado alunoNNNN)")
    return u


def _san_text(s, maxlen=80):
    return (s or "").strip()[:maxlen].replace("'", "''")


def _num(v, default=0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _faculdade_do_aluno(u):
    r = query(f"SELECT faculdade FROM matriculas WHERE username = '{u}' LIMIT 1")
    return r[0]["faculdade"] if r else ""


# ============================ TOOLS DE ALUNO ============================
def perfil_aluno(username):
    u = _san_username(username)
    aluno = query(f"SELECT username, nome, sobrenome, email, cidade FROM alunos "
                  f"WHERE username = '{u}' LIMIT 1")
    notas = query(f"SELECT faculdade, disciplina, nota, situacao FROM notas "
                  f"WHERE username = '{u}' ORDER BY faculdade, disciplina")
    fac = notas[0]["faculdade"] if notas else _faculdade_do_aluno(u)
    reprov = [n for n in notas if n.get("situacao") == "reprovado"]
    return {"aluno": aluno[0] if aluno else None, "faculdade": fac, "notas": notas,
            "total_disciplinas_cursadas": len(notas),
            "aprovadas": len(notas) - len(reprov), "reprovacoes": len(reprov)}


def notas_aluno(username):
    u = _san_username(username)
    return {"notas": query(f"SELECT faculdade, disciplina, nota, situacao FROM notas "
                           f"WHERE username = '{u}' ORDER BY nota")}


def progresso_aluno(username):
    u = _san_username(username)
    fac = _faculdade_do_aluno(u)
    total = query(f"SELECT count(*) AS n FROM cursos WHERE faculdade = '{_san_text(fac)}'")
    aprov = query(f"SELECT count(DISTINCT disciplina) AS n FROM notas "
                  f"WHERE username = '{u}' AND situacao = 'aprovado'")
    matric = query(f"SELECT count(*) AS n FROM matriculas WHERE username = '{u}'")
    t = int(_num(total[0]["n"])) if total else 0
    a = int(_num(aprov[0]["n"])) if aprov else 0
    return {"faculdade": fac, "aprovadas": a, "total_curso": t,
            "pendentes": max(0, t - a), "matriculas": int(_num(matric[0]["n"])) if matric else 0,
            "pct_conclusao": round(100.0 * a / t, 1) if t else 0.0}


def minha_matricula(username):
    u = _san_username(username)
    return {"matriculas": query(f"SELECT faculdade, disciplina, status FROM matriculas "
                                f"WHERE username = '{u}' ORDER BY disciplina")}


def competencias_aluno(username):
    u = _san_username(username)
    return {"competencias": query(
        f"SELECT DISTINCT c.competencia, c.framework FROM competencias c "
        f"JOIN notas n ON n.curso_id = c.curso_id "
        f"WHERE n.username = '{u}' AND n.situacao = 'aprovado' ORDER BY c.competencia")}


def trilha_aluno(username):
    """Adaptação da 'trilha': classifica as disciplinas do curso do aluno em
    aprovadas / a refazer (reprovadas) / não cursadas, com prioridade nas reprovadas."""
    u = _san_username(username)
    fac = _faculdade_do_aluno(u)
    catalogo = query(f"SELECT disciplina FROM cursos WHERE faculdade = '{_san_text(fac)}' "
                     f"ORDER BY disciplina")
    notas = query(f"SELECT disciplina, nota, situacao FROM notas WHERE username = '{u}'")
    by = {n["disciplina"]: n for n in notas}
    aprovadas, refazer, nao_cursadas = [], [], []
    for c in catalogo:
        d = c["disciplina"]
        if d in by:
            (aprovadas if by[d]["situacao"] == "aprovado" else refazer).append(
                {"disciplina": d, "nota": by[d]["nota"], "situacao": by[d]["situacao"]})
        else:
            nao_cursadas.append({"disciplina": d})
    total = len(catalogo)
    return {"faculdade": fac, "a_refazer": refazer, "nao_cursadas": nao_cursadas,
            "aprovadas": aprovadas, "total_curso": total,
            "pct_conclusao": round(100.0 * len(aprovadas) / total, 1) if total else 0.0}


# ============================ CATÁLOGO ============================
def cursos_faculdade(faculdade):
    return {"cursos": query(f"SELECT disciplina, codigo FROM cursos "
                            f"WHERE faculdade = '{_san_text(faculdade)}' ORDER BY disciplina")}


def competencias_curso(disciplina):
    return {"competencias": query(
        f"SELECT DISTINCT competencia, framework FROM competencias "
        f"WHERE disciplina = '{_san_text(disciplina)}' ORDER BY competencia")}


def faculdades():
    return {"faculdades": query(
        "SELECT faculdade, count(*) AS disciplinas FROM cursos GROUP BY faculdade ORDER BY faculdade")}


def programa(faculdade):
    """Detalhe do 'curso' (faculdade): disciplinas com matriculados, média e % reprovação."""
    f = _san_text(faculdade)
    disc = query(
        "SELECT c.disciplina, c.codigo, "
        "  (SELECT count(DISTINCT m.username) FROM matriculas m WHERE m.disciplina = c.disciplina AND m.faculdade = c.faculdade) AS matriculados, "
        "  (SELECT round(avg(CAST(n.nota AS double)),2) FROM notas n WHERE n.disciplina = c.disciplina AND n.faculdade = c.faculdade) AS media "
        f"FROM cursos c WHERE c.faculdade = '{f}' ORDER BY c.disciplina")
    alunos = query(f"SELECT count(DISTINCT username) AS n FROM matriculas WHERE faculdade = '{f}'")
    return {"faculdade": faculdade, "total_disciplinas": len(disc),
            "total_alunos": int(_num(alunos[0]["n"])) if alunos else 0, "disciplinas": disc}


def curriculo_overview():
    """Visão de currículo: faculdades com contagem de disciplinas e competências,
    + disciplinas-ponte (que aparecem em mais de uma faculdade)."""
    fac = query("SELECT c.faculdade, count(DISTINCT c.disciplina) AS disciplinas, "
                "  count(DISTINCT cp.competencia) AS competencias "
                "FROM cursos c LEFT JOIN competencias cp ON cp.faculdade = c.faculdade "
                "GROUP BY c.faculdade ORDER BY c.faculdade")
    ponte = query("SELECT disciplina, count(DISTINCT faculdade) AS n_faculdades "
                  "FROM cursos GROUP BY disciplina HAVING count(DISTINCT faculdade) > 1 "
                  "ORDER BY n_faculdades DESC")
    return {"faculdades": fac, "disciplinas_ponte": ponte}


def curriculo_faculdade(faculdade):
    f = _san_text(faculdade)
    return {"faculdade": faculdade, "disciplinas": query(
        "SELECT c.disciplina, c.codigo, "
        "  array_join(array_agg(DISTINCT cp.competencia), ', ') AS competencias "
        "FROM cursos c LEFT JOIN competencias cp ON cp.disciplina = c.disciplina AND cp.faculdade = c.faculdade "
        f"WHERE c.faculdade = '{f}' GROUP BY c.disciplina, c.codigo ORDER BY c.disciplina")}


def competencia_matriz():
    """Matriz competência × faculdade (nº de disciplinas que desenvolvem a competência)."""
    return {"celulas": query(
        "SELECT competencia, faculdade, count(DISTINCT disciplina) AS disciplinas "
        "FROM competencias GROUP BY competencia, faculdade ORDER BY competencia, faculdade")}


# ============================ COORDENAÇÃO ============================
def desempenho_faculdade():
    return {"faculdades": query(
        "SELECT faculdade, count(*) AS notas, round(avg(CAST(nota AS double)),2) AS media, "
        "round(100.0*sum(CASE WHEN situacao='reprovado' THEN 1 ELSE 0 END)/count(*),1) AS pct_reprovacao "
        "FROM notas GROUP BY faculdade ORDER BY media DESC")}


def alunos_em_risco(min_reprovacoes=3, faculdade=""):
    try:
        mr = max(1, int(min_reprovacoes))
    except (TypeError, ValueError):
        mr = 3
    where = "WHERE n.situacao = 'reprovado'"
    if faculdade:
        where += f" AND n.faculdade = '{_san_text(faculdade)}'"
    return {"alunos": query(
        f"SELECT n.username, a.nome, a.sobrenome, n.faculdade, count(*) AS reprovacoes "
        f"FROM notas n JOIN alunos a ON a.username = n.username {where} "
        f"GROUP BY n.username, a.nome, a.sobrenome, n.faculdade "
        f"HAVING count(*) >= {mr} ORDER BY reprovacoes DESC LIMIT 100")}


def visao_geral_cursos():
    return {"cursos": query(
        "SELECT faculdade, count(DISTINCT username) AS alunos FROM matriculas "
        "GROUP BY faculdade ORDER BY alunos DESC")}


def alunos_do_curso(faculdade):
    f = _san_text(faculdade)
    return {"alunos": query(
        f"SELECT DISTINCT m.username, a.nome, a.sobrenome FROM matriculas m "
        f"JOIN alunos a ON a.username = m.username WHERE m.faculdade = '{f}' "
        f"ORDER BY a.nome LIMIT 300")}


def matriculas_por_disciplina(faculdade=""):
    where = f"WHERE faculdade = '{_san_text(faculdade)}'" if faculdade else ""
    return {"disciplinas": query(
        f"SELECT disciplina, faculdade, count(DISTINCT username) AS matriculados "
        f"FROM matriculas {where} GROUP BY disciplina, faculdade "
        f"ORDER BY matriculados DESC LIMIT 100")}


def alunos_por_disciplina(disciplina):
    d = _san_text(disciplina)
    return {"alunos": query(
        f"SELECT DISTINCT n.username, a.nome, a.sobrenome, n.nota FROM notas n "
        f"JOIN alunos a ON a.username = n.username "
        f"WHERE n.disciplina = '{d}' AND n.situacao = 'aprovado' ORDER BY a.nome LIMIT 300")}


def alunos_por_competencia(competencia):
    c = _san_text(competencia)
    return {"alunos": query(
        f"SELECT DISTINCT n.username, a.nome, a.sobrenome, n.faculdade FROM notas n "
        f"JOIN competencias cp ON cp.curso_id = n.curso_id "
        f"JOIN alunos a ON a.username = n.username "
        f"WHERE cp.competencia = '{c}' AND n.situacao = 'aprovado' "
        f"ORDER BY a.nome LIMIT 300")}


def grade_noturna(faculdade, noites=5, aulas_por_noite=2):
    """Monta uma grade noturna conflito-consciente para uma faculdade: duas disciplinas
    com aluno em comum não podem cair no mesmo horário (coloração gulosa do grafo de
    conflito derivado da matrícula). Retorna a grade + estimativa de salas no pico."""
    f = _san_text(faculdade)
    try:
        noites = max(1, min(7, int(noites)))
        apn = max(1, min(6, int(aulas_por_noite)))
    except (TypeError, ValueError):
        noites, apn = 5, 2
    rows = query(f"SELECT disciplina, username FROM matriculas WHERE faculdade = '{f}'")
    alunos_por_disc = {}
    for r in rows:
        alunos_por_disc.setdefault(r["disciplina"], set()).add(r["username"])
    discs = sorted(alunos_por_disc, key=lambda d: len(alunos_por_disc[d]), reverse=True)
    # grafo de conflito: aresta se compartilham >= 1 aluno
    conflito = {d: set() for d in discs}
    for i in range(len(discs)):
        for j in range(i + 1, len(discs)):
            if alunos_por_disc[discs[i]] & alunos_por_disc[discs[j]]:
                conflito[discs[i]].add(discs[j])
                conflito[discs[j]].add(discs[i])
    n_slots = noites * apn
    slots = [[] for _ in range(n_slots)]
    slot_de = {}
    nao_alocadas = []
    for d in discs:
        for s in range(n_slots):
            if not any(viz in slot_de and slot_de[viz] == s for viz in conflito[d]):
                slots[s].append(d)
                slot_de[d] = s
                break
        else:
            nao_alocadas.append(d)
    grade = []
    for s in range(n_slots):
        noite = s // apn + 1
        horario = s % apn + 1
        grade.append({"noite": noite, "horario": horario,
                      "disciplinas": [{"disciplina": d, "matriculados": len(alunos_por_disc[d])}
                                      for d in slots[s]]})
    pico = max((len(s) for s in slots), default=0)
    return {"faculdade": faculdade, "noites": noites, "aulas_por_noite": apn,
            "grade": grade, "salas_no_pico": pico, "nao_alocadas": nao_alocadas,
            "total_disciplinas": len(discs)}


# ============================ Bedrock Converse toolConfig ============================
def _spec(name, desc, props, required):
    return {"toolSpec": {"name": name, "description": desc,
                         "inputSchema": {"json": {"type": "object", "properties": props,
                                                  "required": required}}}}

_STR = {"type": "string"}
_INT = {"type": "integer"}

ALUNO_TOOLS = [
    _spec("perfil_aluno", "Perfil e notas do aluno da sessao (dados, notas por disciplina, "
          "nº de reprovacoes).", {"username": _STR}, ["username"]),
    _spec("progresso_aluno", "Progresso do aluno: aprovadas, total do curso, % de conclusao, "
          "matriculas.", {"username": _STR}, ["username"]),
    _spec("trilha_aluno", "Trilha do aluno: disciplinas a refazer (reprovadas), nao cursadas e "
          "aprovadas.", {"username": _STR}, ["username"]),
    _spec("minha_matricula", "Disciplinas em que o aluno esta matriculado.", {"username": _STR}, ["username"]),
    _spec("competencias_aluno", "Competencias ja desenvolvidas pelo aluno (via disciplinas "
          "aprovadas).", {"username": _STR}, ["username"]),
    _spec("cursos_faculdade", "Lista as disciplinas de uma faculdade.", {"faculdade": _STR}, ["faculdade"]),
]

COORD_TOOLS = ALUNO_TOOLS + [
    _spec("desempenho_faculdade", "Media de notas e % de reprovacao por faculdade.", {}, []),
    _spec("alunos_em_risco", "Alunos em risco de evasao (>= min_reprovacoes reprovacoes), "
          "opcional por faculdade.", {"min_reprovacoes": _INT, "faculdade": _STR}, []),
    _spec("visao_geral_cursos", "Total de alunos por faculdade.", {}, []),
    _spec("alunos_do_curso", "Lista alunos de uma faculdade.", {"faculdade": _STR}, ["faculdade"]),
    _spec("matriculas_por_disciplina", "Matriculados por disciplina (opcional por faculdade), "
          "ranqueado.", {"faculdade": _STR}, []),
    _spec("alunos_por_disciplina", "Alunos que ja foram aprovados numa disciplina.",
          {"disciplina": _STR}, ["disciplina"]),
    _spec("alunos_por_competencia", "Alunos que desenvolveram uma competencia.",
          {"competencia": _STR}, ["competencia"]),
    _spec("grade_noturna", "Monta uma grade noturna conflito-consciente de uma faculdade "
          "(disciplinas com aluno em comum nao coincidem de horario).",
          {"faculdade": _STR, "noites": _INT, "aulas_por_noite": _INT}, ["faculdade"]),
]

_EXECUTORS = {
    "perfil_aluno": perfil_aluno, "notas_aluno": notas_aluno, "progresso_aluno": progresso_aluno,
    "minha_matricula": minha_matricula, "competencias_aluno": competencias_aluno,
    "trilha_aluno": trilha_aluno, "cursos_faculdade": cursos_faculdade,
    "competencias_curso": competencias_curso,
    "desempenho_faculdade": desempenho_faculdade, "alunos_em_risco": alunos_em_risco,
    "visao_geral_cursos": visao_geral_cursos, "alunos_do_curso": alunos_do_curso,
    "matriculas_por_disciplina": matriculas_por_disciplina,
    "alunos_por_disciplina": alunos_por_disciplina,
    "alunos_por_competencia": alunos_por_competencia, "grade_noturna": grade_noturna,
}

_COORD_ONLY = {"desempenho_faculdade", "alunos_em_risco", "visao_geral_cursos", "alunos_do_curso",
               "matriculas_por_disciplina", "alunos_por_disciplina", "alunos_por_competencia",
               "grade_noturna"}
_ALUNO_SCOPED = {"perfil_aluno", "notas_aluno", "progresso_aluno", "minha_matricula",
                 "competencias_aluno", "trilha_aluno"}


def query_alunos_min(limit=500):
    return query(f"SELECT username, nome, sobrenome FROM alunos ORDER BY username LIMIT {int(limit)}")


def execute(name, args, *, is_coord, student_id):
    if name not in _EXECUTORS:
        return {"erro": f"tool desconhecida: {name}"}
    if name in _COORD_ONLY and not is_coord:
        return {"erro": "acesso negado: funcao restrita a coordenacao"}
    args = dict(args or {})
    if name in _ALUNO_SCOPED and not is_coord:
        args["username"] = student_id
    try:
        return _EXECUTORS[name](**args)
    except Exception as e:  # noqa: BLE001
        return {"erro": str(e)}
