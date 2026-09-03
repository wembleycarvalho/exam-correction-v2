"""Orientador Context — agente serverless (Lambda) do portal "A Arte do Possivel".

Front door = portal, sob /orientador-context/*. Consome o data lake do Moodle (Athena sobre
`moodle_datalake`) via Bedrock Converse + tool-use (chat) e via consultas diretas (telas).
Coexiste com o Orientador Academico (Neptune), sem toca-lo.

RBAC: papel pelos grupos do Cognito (JWT). Coordenador (admin/professor) acessa visoes
agregadas/coordenacao; aluno e escopado ao proprio.
"""
import hashlib
import json
import os

import boto3

import tools

_agentcore = boto3.client("bedrock-agentcore")
_ssm = boto3.client("ssm")

# ARN do AgentCore Runtime (agente Strands). Env tem prioridade; senao lê do SSM (1x, cache).
_RUNTIME_ARN_ENV = os.environ.get("RUNTIME_ARN", "")
_RUNTIME_ARN_PARAM = os.environ.get("RUNTIME_ARN_PARAM", "/orientador-context/runtime-arn")
_RUNTIME_ARN_CACHE = None


def _runtime_arn():
    global _RUNTIME_ARN_CACHE
    if _RUNTIME_ARN_CACHE:
        return _RUNTIME_ARN_CACHE
    _RUNTIME_ARN_CACHE = _RUNTIME_ARN_ENV or _ssm.get_parameter(
        Name=_RUNTIME_ARN_PARAM)["Parameter"]["Value"]
    return _RUNTIME_ARN_CACHE


def _resp(status, body):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, ensure_ascii=False)}


def _ok(result):
    return _resp(200, {"result": result})


def _subpath(event):
    raw = event.get("rawPath", "") or ""
    marker = "/orientador-context/api/"
    if marker in raw:
        return raw.split(marker, 1)[1].strip("/")
    return raw.rsplit("/", 1)[-1].strip("/")


def _groups(event):
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        return set()
    g = claims.get("cognito:groups") or ""
    if isinstance(g, list):
        return set(g)
    return {x for x in str(g).replace("[", "").replace("]", "").replace(",", " ").split() if x}


def _has_priv(event):
    return bool(_groups(event) & {"admin", "professor"})


def _sub(event):
    try:
        return event["requestContext"]["authorizer"]["jwt"]["claims"].get("sub", "")
    except (KeyError, TypeError):
        return ""


def _session_id(event, mode, student_id):
    """Sessão estável por (usuário, modo, aluno) — chaveia a memória do AgentCore Runtime.
    O AgentCore exige runtimeSessionId com >= 33 chars; o hash SHA-256 (64 hex) atende."""
    seed = f"octx:{mode}:{student_id or ''}:{_sub(event)}"
    return hashlib.sha256(seed.encode()).hexdigest()


# ------------------------------------------------------------------ chat (AgentCore Runtime)
def _ask_runtime(question, *, is_coord, student_id, history, groups, session_id):
    """Ponte para o AgentCore Runtime (agente Strands: Athena + memória + web search).

    Chamada NÃO-streaming (resposta completa). O browser nunca fala com o Runtime; só esta
    Lambda, com IAM próprio. RBAC é reforçado tanto aqui quanto dentro do agente.
    """
    payload = json.dumps({
        "question": question,
        "mode": "coord" if is_coord else "aluno",
        "student_id": student_id,
        "groups": sorted(groups),
        "history": history or [],
    }).encode("utf-8")
    resp = _agentcore.invoke_agent_runtime(
        agentRuntimeArn=_runtime_arn(), runtimeSessionId=session_id,
        contentType="application/json", accept="application/json", payload=payload)
    body = resp.get("response")
    raw = body.read() if hasattr(body, "read") else body
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    res = data.get("result", data) if isinstance(data, dict) else {}
    return (res.get("answer") if isinstance(res, dict) else None) or \
        "Nao consegui elaborar uma resposta."


# ------------------------------------------------------------------ grafo (SVG force graph)
def _grafo(scope, entity_id, is_coord, student_id):
    nodes, edges, seen = [], [], set()

    def add_node(nid, label, ntype, **extra):
        if nid not in seen:
            seen.add(nid)
            nodes.append({"id": nid, "label": label, "type": ntype, **extra})

    if scope == "student":
        u = student_id if not is_coord else (entity_id or student_id)
        u = tools._san_username(u)
        perfil = tools.perfil_aluno(u)
        aluno = perfil.get("aluno") or {"nome": u}
        add_node("stu:" + u, (aluno.get("nome", "") + " " + aluno.get("sobrenome", "")).strip() or u,
                 "Student", status="student")
        for n in perfil.get("notas", []):
            d = n["disciplina"]
            did = "disc:" + d
            status = "done" if n.get("situacao") == "aprovado" else "todo"
            add_node(did, d, "Discipline", status=status, code=str(n.get("nota", "")))
            edges.append({"source": "stu:" + u, "target": did,
                          "relation": "COMPLETED", "label": str(n.get("nota", ""))})
        for c in tools.competencias_aluno(u).get("competencias", []):
            cid = "comp:" + c["competencia"]
            add_node(cid, c["competencia"], "Competency")
        focus = "stu:" + u
    else:  # full
        for c in tools.faculdades().get("faculdades", []):
            add_node("prog:" + c["faculdade"], c["faculdade"], "Program")
        # disciplinas + oferta
        rows = tools.query("SELECT faculdade, disciplina, codigo FROM cursos")
        for r in rows:
            did = "disc:" + r["disciplina"]
            add_node(did, r["disciplina"], "Discipline", code=r.get("codigo", ""))
            edges.append({"source": "prog:" + r["faculdade"], "target": did,
                          "relation": "OFFERED_IN", "label": ""})
        focus = "full"

    deg = {}
    for e in edges:
        deg[e["source"]] = deg.get(e["source"], 0) + 1
        deg[e["target"]] = deg.get(e["target"], 0) + 1
    for n in nodes:
        n["degree"] = deg.get(n["id"], 0)
    return {"scope": scope, "focus": focus, "nodes": nodes, "edges": edges,
            "counts": {"nodes": len(nodes), "edges": len(edges)}}


# ------------------------------------------------------------------ insights (computado)
def _insights(username):
    u = tools._san_username(username)
    perfil = tools.perfil_aluno(u)
    prog = tools.progresso_aluno(u)
    comps = tools.competencias_aluno(u).get("competencias", [])
    notas = sorted(perfil.get("notas", []), key=lambda n: tools._num(n.get("nota")))
    fracos = [n for n in notas if n.get("situacao") == "reprovado"] or notas[:3]
    fortes = sorted(perfil.get("notas", []), key=lambda n: tools._num(n.get("nota")),
                    reverse=True)[:3]
    reprov = perfil.get("reprovacoes", 0)
    risco = "alto" if reprov >= 3 else ("medio" if reprov >= 1 else "baixo")
    recs = []
    if fracos:
        recs.append("Priorizar refazer/reforcar: " + ", ".join(
            n["disciplina"] for n in fracos[:4]) + ".")
    if prog.get("pct_conclusao", 0) < 50:
        recs.append("Conclusao do curso em %.0f%%; planejar as pendentes." % prog.get("pct_conclusao", 0))
    if risco == "alto":
        recs.append("Risco de evasao alto: buscar tutoria/monitoria e acompanhamento.")
    if not recs:
        recs.append("Desempenho consistente; manter o ritmo e explorar disciplinas eletivas.")
    return {"aluno": perfil.get("aluno"), "faculdade": perfil.get("faculdade"),
            "risco_evasao": risco, "reprovacoes": reprov,
            "pct_conclusao": prog.get("pct_conclusao", 0),
            "pontos_fortes": fortes, "pontos_fracos": fracos[:5],
            "competencias_desenvolvidas": len(comps), "recomendacoes": recs}


# ------------------------------------------------------------------ dispatch
def handler(event, context):
    path = _subpath(event)
    if path == "health":
        return _resp(200, {"ok": True, "module": "orientador-context"})

    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except (ValueError, TypeError):
            body = {}

    has_priv = _has_priv(event)
    mode = body.get("mode", "aluno")
    student_id = body.get("student_id")
    is_coord = has_priv and mode == "coord"

    def need_student():
        if not student_id:
            return _resp(400, {"error": "selecione um aluno"})
        return None

    def need_coord():
        if not has_priv:
            return _resp(403, {"error": "restrito a coordenacao"})
        return None

    try:
        # ---- comum ----
        if path == "bootstrap":
            return _ok({"is_coord_capable": has_priv,
                        "faculdades": [f["faculdade"] for f in tools.faculdades()["faculdades"]],
                        "students": tools.query_alunos_min() if has_priv else []})

        if path == "ask":
            q = (body.get("question") or "").strip()
            if not q:
                return _resp(400, {"error": "pergunta vazia"})
            if not is_coord and not student_id:
                return _resp(400, {"error": "selecione um aluno (modo aluno)"})
            history = body.get("history")
            session_id = _session_id(event, "coord" if is_coord else "aluno", student_id)
            # Chat 100% no AgentCore Runtime (agente Strands: Athena + memória + web search).
            # Sem fallback local: se o Runtime falhar, devolvemos erro claro (não degradamos
            # para um agente sem ferramentas).
            try:
                answer = _ask_runtime(q, is_coord=is_coord, student_id=student_id,
                                      history=history, groups=_groups(event),
                                      session_id=session_id)
            except Exception as e:  # noqa: BLE001
                print("AgentCore Runtime invoke failed:", repr(e))
                return _resp(502, {"error": "o assistente esta temporariamente indisponivel, "
                                            "tente novamente em instantes"})
            return _ok({"answer": answer, "mode": "coord" if is_coord else "aluno"})

        # ---- aluno (escopado) ----
        if path in ("perfil", "progresso", "trilha", "matricula", "competencias-aluno", "insights"):
            r = need_student()
            if r:
                return r
            if path == "perfil":
                return _ok(tools.perfil_aluno(student_id))
            if path == "progresso":
                return _ok(tools.progresso_aluno(student_id))
            if path == "trilha":
                return _ok(tools.trilha_aluno(student_id))
            if path == "matricula":
                return _ok(tools.minha_matricula(student_id))
            if path == "competencias-aluno":
                return _ok(tools.competencias_aluno(student_id))
            if path == "insights":
                return _ok(_insights(student_id))

        if path == "grafo":
            scope = body.get("scope", "full")
            if scope == "student" and not is_coord and not student_id:
                return _resp(400, {"error": "selecione um aluno"})
            return _ok(_grafo(scope, body.get("id"), is_coord, student_id))

        # ---- catalogo (publico p/ autenticado) ----
        if path == "faculdades":
            return _ok(tools.faculdades())
        if path == "programa":
            if not body.get("faculdade"):
                return _resp(400, {"error": "faculdade obrigatoria"})
            return _ok(tools.programa(body["faculdade"]))
        if path == "curriculo":
            return _ok(tools.curriculo_overview())
        if path == "curriculo-faculdade":
            if not body.get("faculdade"):
                return _resp(400, {"error": "faculdade obrigatoria"})
            return _ok(tools.curriculo_faculdade(body["faculdade"]))
        if path == "competencias-matriz":
            return _ok(tools.competencia_matriz())

        # ---- coordenacao (exige grupo) ----
        if path in ("risco", "desempenho", "visao-geral", "alunos-curso", "matriculas-disciplina",
                    "alunos-disciplina", "alunos-competencia", "grade-noturna", "grade-aluno"):
            r = need_coord()
            if r:
                return r
            if path == "risco":
                return _ok(tools.alunos_em_risco(int(body.get("min_reprovacoes", 3) or 3),
                                                 body.get("faculdade", "")))
            if path == "desempenho":
                return _ok(tools.desempenho_faculdade())
            if path == "visao-geral":
                return _ok(tools.visao_geral_cursos())
            if path == "alunos-curso":
                return _ok(tools.alunos_do_curso(body.get("faculdade", "")))
            if path == "matriculas-disciplina":
                return _ok(tools.matriculas_por_disciplina(body.get("faculdade", "")))
            if path == "alunos-disciplina":
                return _ok(tools.alunos_por_disciplina(body.get("disciplina", "")))
            if path == "alunos-competencia":
                return _ok(tools.alunos_por_competencia(body.get("competencia", "")))
            if path == "grade-noturna":
                return _ok(tools.grade_noturna(body.get("faculdade", ""),
                                               body.get("noites", 5), body.get("aulas_por_noite", 2)))
            if path == "grade-aluno":
                grade = tools.grade_noturna(body.get("faculdade", ""))
                u = body.get("student_id") or ""
                minhas = set()
                if u:
                    minhas = {m["disciplina"] for m in tools.minha_matricula(u).get("matriculas", [])}
                for slot in grade["grade"]:
                    slot["disciplinas"] = [d for d in slot["disciplinas"] if d["disciplina"] in minhas]
                return _ok(grade)

        return _resp(404, {"error": f"rota nao encontrada: {path}"})
    except Exception as e:  # noqa: BLE001
        return _resp(502, {"error": str(e)})
