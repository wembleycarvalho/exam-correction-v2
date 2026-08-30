"""Tools do Orientador Context (consultas ao data lake via Athena).

Cada tool vira uma consulta SQL parametrizada e sanitizada sobre o catálogo `moodle_datalake`
(tabelas: alunos, cursos, matriculas, notas, competencias).

RBAC (ganho central sobre o Orientador atual): em modo aluno, as tools de aluno são
FORÇADAS ao `student_id` da sessão (o modelo não escolhe outro aluno) e as tools de
coordenação ficam indisponíveis. Modo coordenador exige grupo Cognito (admin/professor).
"""
import re

from athena import query

_USERNAME_RE = re.compile(r"^(aluno|prof)\d{1,6}$")


def _san_username(u: str) -> str:
    u = (u or "").strip()
    if not _USERNAME_RE.match(u):
        raise ValueError("username inválido (esperado alunoNNNN)")
    return u


def _san_text(s: str, maxlen: int = 80) -> str:
    # Athena roda 1 statement só; ainda assim escapamos aspas e cortamos comprimento.
    s = (s or "").strip()[:maxlen]
    return s.replace("'", "''")


# ---------------- Tools de aluno (auto-escopadas em modo aluno) ----------------
def perfil_aluno(username: str):
    u = _san_username(username)
    aluno = query(f"SELECT username, nome, sobrenome, email, cidade FROM alunos "
                  f"WHERE username = '{u}' LIMIT 1")
    notas = query(f"SELECT faculdade, disciplina, nota, situacao FROM notas "
                  f"WHERE username = '{u}' ORDER BY faculdade, disciplina")
    return {"aluno": aluno[0] if aluno else None, "notas": notas,
            "total_disciplinas": len(notas),
            "reprovacoes": sum(1 for n in notas if n.get("situacao") == "reprovado")}


def notas_aluno(username: str):
    u = _san_username(username)
    return {"notas": query(
        f"SELECT faculdade, disciplina, nota, situacao FROM notas "
        f"WHERE username = '{u}' ORDER BY nota")}


def query_alunos_min(limit: int = 500):
    """Lista mínima de alunos (username, nome) para popular selects da UI."""
    return query(
        f"SELECT username, nome, sobrenome FROM alunos ORDER BY username LIMIT {int(limit)}")


# ---------------- Tools de coordenação (exigem papel coordenador) ----------------
def alunos_em_risco(min_reprovacoes: int = 3, faculdade: str = ""):
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
        f"HAVING count(*) >= {mr} ORDER BY reprovacoes DESC LIMIT 50")}


def desempenho_faculdade():
    return {"faculdades": query(
        "SELECT faculdade, count(*) AS notas, round(avg(CAST(nota AS double)),2) AS media, "
        "round(100.0*sum(CASE WHEN situacao='reprovado' THEN 1 ELSE 0 END)/count(*),1) AS pct_reprovacao "
        "FROM notas GROUP BY faculdade ORDER BY media DESC")}


# ---------------- Tools de catálogo (disponíveis a todos) ----------------
def cursos_faculdade(faculdade: str):
    return {"cursos": query(
        f"SELECT disciplina, codigo FROM cursos WHERE faculdade = '{_san_text(faculdade)}' "
        f"ORDER BY disciplina")}


def competencias_curso(disciplina: str):
    return {"competencias": query(
        f"SELECT DISTINCT competencia, framework FROM competencias "
        f"WHERE disciplina = '{_san_text(disciplina)}' ORDER BY competencia")}


# ---------------- Especificações (Bedrock Converse toolConfig) ----------------
def _spec(name, desc, props, required):
    return {"toolSpec": {"name": name, "description": desc,
                         "inputSchema": {"json": {"type": "object", "properties": props,
                                                  "required": required}}}}

_STR = {"type": "string"}
_INT = {"type": "integer"}

ALUNO_TOOLS = [
    _spec("perfil_aluno", "Perfil do aluno da sessão: dados, notas por disciplina, nº de "
          "reprovações. Use para responder sobre o desempenho do próprio aluno.",
          {"username": _STR}, ["username"]),
    _spec("notas_aluno", "Lista as notas do aluno da sessão (menor para maior).",
          {"username": _STR}, ["username"]),
    _spec("cursos_faculdade", "Lista as disciplinas de uma faculdade.",
          {"faculdade": _STR}, ["faculdade"]),
    _spec("competencias_curso", "Competências associadas a uma disciplina.",
          {"disciplina": _STR}, ["disciplina"]),
]

COORD_TOOLS = ALUNO_TOOLS + [
    _spec("alunos_em_risco", "Alunos em risco de evasão (>= min_reprovacoes reprovações), "
          "opcionalmente filtrando por faculdade. Só para coordenação.",
          {"min_reprovacoes": _INT, "faculdade": _STR}, []),
    _spec("desempenho_faculdade", "Média de notas e % de reprovação por faculdade. "
          "Só para coordenação.", {}, []),
]

_EXECUTORS = {
    "perfil_aluno": perfil_aluno, "notas_aluno": notas_aluno,
    "cursos_faculdade": cursos_faculdade, "competencias_curso": competencias_curso,
    "alunos_em_risco": alunos_em_risco, "desempenho_faculdade": desempenho_faculdade,
}

_COORD_ONLY = {"alunos_em_risco", "desempenho_faculdade"}
_ALUNO_SCOPED = {"perfil_aluno", "notas_aluno"}


def execute(name: str, args: dict, *, is_coord: bool, student_id: str):
    """Executa a tool aplicando RBAC. Retorna dict (nunca levanta p/ o modelo)."""
    if name not in _EXECUTORS:
        return {"erro": f"tool desconhecida: {name}"}
    if name in _COORD_ONLY and not is_coord:
        return {"erro": "acesso negado: função restrita à coordenação"}
    args = dict(args or {})
    # Em modo aluno, força o escopo ao próprio aluno da sessão.
    if name in _ALUNO_SCOPED and not is_coord:
        args["username"] = student_id
    try:
        return _EXECUTORS[name](**args)
    except Exception as e:  # noqa: BLE001
        return {"erro": str(e)}
