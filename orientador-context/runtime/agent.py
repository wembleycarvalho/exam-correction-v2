"""Orientador Context — agente Strands hospedado no Amazon Bedrock AgentCore Runtime.

Responde QUALQUER pergunta:
- dados do Moodle -> ferramentas que consultam o data lake via Athena (com RBAC por sessao);
- eventos atuais / noticias -> ferramenta de web search (AgentCore, adicionada na fase 2);
- conhecimento geral -> o proprio modelo.

Memoria de conversa: gerenciada pelo AgentCore Memory (ligada por padrao no runtime).
RBAC: o bridge passa mode/student_id/groups no payload; as tools de aluno sao forcadas ao
aluno da sessao e as de coordenacao exigem grupo admin/professor.
"""
import os
import re
import time

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

app = BedrockAgentCoreApp()

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0")
GLUE_DB = os.environ.get("GLUE_DB", "moodle_datalake")
WORKGROUP = os.environ.get("WORKGROUP", "moodle-datalake")
# Memória gerenciada pelo AgentCore Memory (o Runtime injeta BEDROCK_AGENTCORE_MEMORY_ID).
# Usada via AgentCoreMemorySessionManager do Strands: persiste/recupera os turnos e gera
# os spans nativos (CreateEvent/ListEvents/RetrieveMemoryRecords) no AgentCore Observability.
MEMORY_ID = os.environ.get("BEDROCK_AGENTCORE_MEMORY_ID", "")

# Observabilidade NATIVA do AgentCore — sem métricas "na mão" e sem setup de telemetria no
# código. O pacote `aws-opentelemetry-distro` (ADOT) no requirements faz o Runtime
# auto-instrumentar o agente: cada chamada ao Bedrock (Converse) vira um span com
# gen_ai.usage.* (tokens in/out/total), modelo, latência e aws.genai.* — exportados para o
# CloudWatch GenAI Observability (seção de consumo de tokens/latência). Não inicializamos
# StrandsTelemetry aqui de propósito: isso duplicaria os spans de inferência (double count).

_athena = boto3.client("athena", region_name=REGION)

# Contexto da sessao (setado pelo entrypoint a cada invocacao) -> usado pelas tools p/ RBAC.
_CTX = {"is_coord": False, "student": None}

_USERNAME_RE = re.compile(r"^(aluno|prof)\d{1,6}$")


def _san_user(u):
    u = (u or "").strip()
    if not _USERNAME_RE.match(u):
        raise ValueError("username invalido")
    return u


def _san_text(s, n=80):
    return (s or "").strip()[:n].replace("'", "''")


def _q(sql, max_wait=25):
    qid = _athena.start_query_execution(
        QueryString=sql, QueryExecutionContext={"Database": GLUE_DB},
        WorkGroup=WORKGROUP)["QueryExecutionId"]
    deadline = time.time() + max_wait
    state = "QUEUED"
    while time.time() < deadline:
        state = _athena.get_query_execution(
            QueryExecutionId=qid)["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(0.6)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Athena {state}")
    rows = _athena.get_query_results(QueryExecutionId=qid, MaxResults=200)["ResultSet"]["Rows"]
    if not rows:
        return []
    hdr = [c.get("VarCharValue", "") for c in rows[0]["Data"]]
    return [dict(zip(hdr, [c.get("VarCharValue") for c in r["Data"]])) for r in rows[1:]]


def _fac(u):
    r = _q(f"SELECT faculdade FROM matriculas WHERE username='{u}' LIMIT 1")
    return r[0]["faculdade"] if r else ""


def _scoped_user(username):
    """Em modo aluno, ignora o que o modelo pediu e usa o aluno da sessao."""
    if not _CTX["is_coord"]:
        return _san_user(_CTX["student"])
    return _san_user(username or _CTX["student"])


# ------------------------------- tools de aluno -------------------------------
@tool
def perfil_aluno(username: str = "") -> dict:
    """Perfil e notas de um aluno (dados, notas por disciplina, nº de reprovacoes)."""
    u = _scoped_user(username)
    aluno = _q(f"SELECT username,nome,sobrenome,email,cidade FROM alunos WHERE username='{u}' LIMIT 1")
    notas = _q(f"SELECT faculdade,disciplina,nota,situacao FROM notas WHERE username='{u}' ORDER BY faculdade,disciplina")
    reprov = [n for n in notas if n.get("situacao") == "reprovado"]
    return {"aluno": aluno[0] if aluno else None, "faculdade": (notas[0]["faculdade"] if notas else _fac(u)),
            "notas": notas, "aprovadas": len(notas) - len(reprov), "reprovacoes": len(reprov)}


@tool
def progresso_aluno(username: str = "") -> dict:
    """Progresso do aluno: aprovadas, total do curso, % de conclusao, matriculas."""
    u = _scoped_user(username)
    fac = _fac(u)
    total = _q(f"SELECT count(*) n FROM cursos WHERE faculdade='{_san_text(fac)}'")
    aprov = _q(f"SELECT count(DISTINCT disciplina) n FROM notas WHERE username='{u}' AND situacao='aprovado'")
    t = int(total[0]["n"]) if total else 0
    a = int(aprov[0]["n"]) if aprov else 0
    return {"faculdade": fac, "aprovadas": a, "total_curso": t, "pendentes": max(0, t - a),
            "pct_conclusao": round(100.0 * a / t, 1) if t else 0.0}


@tool
def trilha_aluno(username: str = "") -> dict:
    """Trilha do aluno: disciplinas a refazer (reprovadas), nao cursadas e concluidas."""
    u = _scoped_user(username)
    fac = _fac(u)
    catalogo = _q(f"SELECT disciplina FROM cursos WHERE faculdade='{_san_text(fac)}' ORDER BY disciplina")
    notas = {n["disciplina"]: n for n in _q(f"SELECT disciplina,nota,situacao FROM notas WHERE username='{u}'")}
    aprov, refazer, falta = [], [], []
    for c in catalogo:
        d = c["disciplina"]
        if d in notas:
            (aprov if notas[d]["situacao"] == "aprovado" else refazer).append(
                {"disciplina": d, "nota": notas[d]["nota"]})
        else:
            falta.append(d)
    return {"faculdade": fac, "a_refazer": refazer, "nao_cursadas": falta, "aprovadas": aprov}


# ------------------------------- tools de coordenacao -------------------------------
@tool
def desempenho_faculdade() -> dict:
    """Media de notas e % de reprovacao por faculdade (coordenacao)."""
    if not _CTX["is_coord"]:
        return {"erro": "restrito a coordenacao"}
    return {"faculdades": _q(
        "SELECT faculdade,count(*) notas,round(avg(CAST(nota AS double)),2) media,"
        "round(100.0*sum(CASE WHEN situacao='reprovado' THEN 1 ELSE 0 END)/count(*),1) pct_reprovacao "
        "FROM notas GROUP BY faculdade ORDER BY media DESC")}


@tool
def alunos_em_risco(min_reprovacoes: int = 3, faculdade: str = "") -> dict:
    """Alunos em risco de evasao (>= min_reprovacoes reprovacoes), opcional por faculdade (coordenacao)."""
    if not _CTX["is_coord"]:
        return {"erro": "restrito a coordenacao"}
    mr = max(1, int(min_reprovacoes or 3))
    where = "WHERE n.situacao='reprovado'"
    if faculdade:
        where += f" AND n.faculdade='{_san_text(faculdade)}'"
    return {"alunos": _q(
        f"SELECT n.username,a.nome,a.sobrenome,n.faculdade,count(*) reprovacoes "
        f"FROM notas n JOIN alunos a ON a.username=n.username {where} "
        f"GROUP BY n.username,a.nome,a.sobrenome,n.faculdade HAVING count(*)>={mr} "
        f"ORDER BY reprovacoes DESC LIMIT 50")}


@tool
def cursos_faculdade(faculdade: str) -> dict:
    """Lista as disciplinas de uma faculdade."""
    return {"cursos": _q(f"SELECT disciplina,codigo FROM cursos WHERE faculdade='{_san_text(faculdade)}' ORDER BY disciplina")}


ALUNO_TOOLS = [perfil_aluno, progresso_aluno, trilha_aluno, cursos_faculdade]
COORD_TOOLS = ALUNO_TOOLS + [desempenho_faculdade, alunos_em_risco]


# ------------------------------- web search (AgentCore Gateway) -------------------------------
def _resolve_gateway_url():
    """URL do AgentCore Gateway (conector web-search). Env tem prioridade; senao SSM."""
    u = os.environ.get("AGENTCORE_GATEWAY_URL")
    if u:
        return u
    try:
        return boto3.client("ssm", region_name=REGION).get_parameter(
            Name="/orientador-context/gateway-url")["Parameter"]["Value"]
    except Exception:
        return ""


_GW_URL = _resolve_gateway_url()


def _run_async(make_coro):
    """Roda uma corrotina em um event loop proprio (evita conflito com loop do runtime)."""
    import asyncio
    import threading
    box = {}

    def runner():
        loop = asyncio.new_event_loop()
        try:
            box["v"] = loop.run_until_complete(make_coro())
        except Exception as e:  # noqa: BLE001
            box["e"] = e
        finally:
            loop.close()

    t = threading.Thread(target=runner)
    t.start()
    t.join()
    if "e" in box:
        raise box["e"]
    return box["v"]


async def _do_search(url, query, max_results):
    from mcp import ClientSession
    from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    async with aws_iam_streamablehttp_client(
        endpoint=url, aws_service="bedrock-agentcore",
        aws_region=REGION, credentials=creds,
    ) as (read, write, _sid):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = [t.name for t in listed.tools]
            name = next((n for n in names if n == "WebSearch" or n.endswith("___WebSearch")),
                        names[0] if names else None)
            if not name:
                raise RuntimeError("gateway sem tools")
            return await session.call_tool(name, {"query": query[:200], "maxResults": max_results})


def _extract_results(call_result):
    import json as _json
    payload = {}
    structured = getattr(call_result, "structuredContent", None)
    if isinstance(structured, dict) and "results" in structured:
        payload = structured
    else:
        for block in getattr(call_result, "content", []) or []:
            text = getattr(block, "text", None)
            if not text:
                continue
            try:
                parsed = _json.loads(text)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(parsed, dict) and "results" in parsed:
                payload = parsed
                break
    return [{"titulo": r.get("title"), "url": r.get("url"), "data": r.get("publishedDate"),
             "trecho": (r.get("text") or "")[:500]} for r in payload.get("results", [])]


@tool
def web_search(query: str, max_results: int = 6) -> dict:
    """Busca na web (AgentCore Web Search) para eventos atuais, noticias, precos e fatos
    recentes ou posteriores ao treino do modelo. Retorna titulo, url, data e trecho de
    cada fonte. Use sempre que a resposta depender de informacao atual e CITE as fontes.
    RESTRITA a coordenacao."""
    if not _CTX["is_coord"]:
        return {"erro": "restrito a coordenacao"}
    if not _GW_URL:
        return {"erro": "web search indisponivel"}
    mr = max(1, min(int(max_results or 6), 25))
    try:
        res = _run_async(lambda: _do_search(_GW_URL, query, mr))
    except Exception as e:  # noqa: BLE001
        return {"erro": f"falha na busca: {type(e).__name__}"}
    return {"resultados": _extract_results(res)}

_SYS_BASE = (
    "Voce e o Orientador Context, um assistente academico de uma universidade brasileira. "
    "Responda SEMPRE em portugues do Brasil, de forma clara e util."
)

# MODO ALUNO — escopo RESTRITO a vida academica na universidade. Sem web, sem conhecimento
# geral, sem assuntos fora do contexto academico.
_SYS_ALUNO = _SYS_BASE + (
    "\nMODO ALUNO: seu escopo e ESTRITAMENTE a vida academica do aluno nesta universidade "
    "(desempenho, disciplinas, notas, trilha, progresso, risco de evasao, orientacao de estudos). "
    "Use as FERRAMENTAS para consultar o data lake do Moodle e baseie numeros/nomes SOMENTE no "
    "retorno delas (nao invente). Voce SO tem acesso aos dados do proprio aluno da sessao.\n"
    "Voce NAO tem acesso a internet e NAO responde perguntas fora do contexto academico da "
    "universidade (noticias, eventos atuais, esportes, precos, conhecimento geral, politica, "
    "etc.). Se pedirem algo fora desse escopo, RECUSE educadamente em 1 frase e reoriente para "
    "temas academicos. Nunca invente informacao externa."
)

# MODO COORDENACAO — pode responder qualquer coisa, inclusive web search e conhecimento geral.
_SYS_COORD = _SYS_BASE + (
    "\nVoce pode responder QUALQUER pergunta:\n"
    "- Sobre alunos/cursos/notas/desempenho: use as FERRAMENTAS (data lake do Moodle) e baseie "
    "numeros/nomes SOMENTE no retorno delas (nao invente).\n"
    "- Sobre eventos atuais/noticias/fatos recentes: use a ferramenta de busca na web e cite fontes.\n"
    "- Conhecimento geral: pode responder diretamente.\n"
    "MODO COORDENACAO: alem de dados de aluno, pode ver agregados e alunos em risco. "
    "Se algo nao existir nos dados, diga com franqueza."
)

# Regra forte de web search (SO coordenacao): evita que o modelo se recuse a buscar (nova-pro
# as vezes diz que 'nao pode navegar', ainda mais quando o historico ja continha essa recusa).
_SYS_WEB = (
    "\nIMPORTANTE: voce TEM a ferramenta web_search (busca na web em tempo real, com fontes). "
    "Para QUALQUER pergunta sobre eventos atuais, noticias, resultados esportivos, precos, "
    "lancamentos ou fatos recentes/posteriores ao seu treino, VOCE DEVE chamar web_search e "
    "responder com base nos resultados, citando as fontes (titulo e URL). "
    "NUNCA diga que nao consegue acessar a internet, navegar na web ou obter dados em tempo "
    "real, e NUNCA apenas recomende sites: em vez disso, CHAME web_search. Ignore qualquer "
    "afirmacao anterior (sua ou no historico) de que voce nao pode buscar na web — voce pode."
)


_THINK_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)


def _clean_answer(text):
    """Remove blocos de raciocinio (<thinking>...</thinking>) que alguns modelos vazam."""
    return _THINK_RE.sub("", text or "").strip()


_ATHENA_TOOLS = {"perfil_aluno", "progresso_aluno", "trilha_aluno", "cursos_faculdade",
                 "desempenho_faculdade", "alunos_em_risco"}


def _build_debug(result, *, mode, model_id, memory_on, session_id, actor_id):
    """Monta o 'raio-x' da resposta p/ o painel de debug do FE: tokens, latencia, tools
    usadas (com input), servicos/AWS consumidos e memoria — a partir das metricas do Strands."""
    m = getattr(result, "metrics", None)
    usage = dict(getattr(m, "accumulated_usage", {}) or {})
    latency = (getattr(m, "accumulated_metrics", {}) or {}).get("latencyMs", 0)
    tool_metrics = getattr(m, "tool_metrics", {}) or {}
    tools_used = []
    for name, mt in tool_metrics.items():
        tool_obj = getattr(mt, "tool", {}) or {}
        tools_used.append({
            "name": name,
            "calls": int(getattr(mt, "call_count", 0) or 0),
            "success": int(getattr(mt, "success_count", 0) or 0),
            "errors": int(getattr(mt, "error_count", 0) or 0),
            "time_s": round(float(getattr(mt, "total_time", 0.0) or 0.0), 3),
            "input": tool_obj.get("input", {}),
        })
    names = {t["name"] for t in tools_used}
    services = [{"service": "Amazon Bedrock (Converse)", "detail": model_id}]
    if names & _ATHENA_TOOLS:
        services.append({"service": "Amazon Athena", "detail": f"data lake {GLUE_DB} (SQL)"})
    if "web_search" in names:
        services.append({"service": "AgentCore Gateway", "detail": "conector web-search (MCP/SigV4)"})
    if memory_on:
        services.append({"service": "AgentCore Memory", "detail": "curto prazo (STM) — CreateEvent/ListEvents"})
    return {
        "model": model_id,
        "mode": mode,
        "tokens": {"input": int(usage.get("inputTokens", 0) or 0),
                   "output": int(usage.get("outputTokens", 0) or 0),
                   "total": int(usage.get("totalTokens", 0) or 0)},
        "latency_ms": round(float(latency or 0), 1),
        "cycles": int(getattr(m, "cycle_count", 0) or 0),
        "tools": tools_used,
        "services": services,
        "memory": {"enabled": bool(memory_on), "backend": "AgentCore Memory (STM)",
                   "session_id": session_id, "actor_id": actor_id},
    }


def _seed_messages(history):
    """Reconstroi o contexto da conversa (turnos anteriores) no formato do Strands."""
    msgs = []
    for h in (history or [])[-8:]:
        role = "assistant" if h.get("role") == "assistant" else "user"
        text = (h.get("text") or h.get("content") or "").strip()
        if text:
            msgs.append({"role": role, "content": [{"text": text}]})
    return msgs


_MEM_ID_RE = re.compile(r"[^a-zA-Z0-9-_]")


def _san_id(v, fallback):
    """Sanitiza actor_id/session_id p/ o padrao aceito pelo AgentCore Memory."""
    v = _MEM_ID_RE.sub("-", (v or "").strip())[:200]
    return v or fallback


def _session_manager(session_id, actor_id):
    """Cria o AgentCoreMemorySessionManager (STM) — persiste/recupera turnos no AgentCore
    Memory e emite os spans nativos de memória. Retorna None se memória indisponivel."""
    if not (MEMORY_ID and session_id):
        return None
    try:
        from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
        from bedrock_agentcore.memory.integrations.strands.session_manager import (
            AgentCoreMemorySessionManager,
        )
        cfg = AgentCoreMemoryConfig(memory_id=MEMORY_ID,
                                    session_id=_san_id(session_id, "session"),
                                    actor_id=_san_id(actor_id, "user"))
        return AgentCoreMemorySessionManager(cfg, region_name=REGION)
    except Exception as e:  # noqa: BLE001 — memória nunca derruba o chat
        print("memory session manager init failed:", repr(e))
        return None


@app.entrypoint
def invoke(payload):
    q = (payload.get("question") or payload.get("prompt") or "").strip()
    mode = payload.get("mode", "aluno")
    student_id = payload.get("student_id")
    groups = set(payload.get("groups") or [])
    is_coord = bool(groups & {"admin", "professor"}) and mode == "coord"
    _CTX["is_coord"] = is_coord
    _CTX["student"] = student_id
    if not q:
        return {"result": {"answer": "Faca uma pergunta.", "mode": "coord" if is_coord else "aluno"}}
    if not is_coord and not student_id:
        return {"result": {"answer": "Selecione um aluno para o modo aluno.", "mode": "aluno"}}

    mode = "coord" if is_coord else "aluno"
    system = _SYS_COORD if is_coord else _SYS_ALUNO
    tools = list(COORD_TOOLS if is_coord else ALUNO_TOOLS)
    # Web search e conhecimento externo SO para coordenacao; aluno fica restrito ao escopo
    # academico da universidade (sem web, sem off-topic).
    if is_coord:
        tools += _WEB_TOOLS  # web search (AgentCore Gateway); vazio se o gateway nao estiver configurado
        if _WEB_TOOLS:
            system += _SYS_WEB  # reforca o uso da web_search quando disponivel

    # Memória: AgentCore Memory (nativo) via session manager. actor = aluno (modo aluno) ou
    # o usuário coordenador; session = a sessão estável enviada pela ponte.
    session_id = payload.get("session_id")
    actor_id = payload.get("actor_id") or (student_id if not is_coord else "coord")
    sm = _session_manager(session_id, actor_id)

    # callback_handler=None: nao streamar a resposta pro stdout (mantem os logs limpos; os
    # traces/tokens vao via OpenTelemetry -> AgentCore Observability, nao via stdout).
    kwargs = dict(model=BedrockModel(model_id=MODEL_ID, region_name=REGION),
                  system_prompt=system, tools=tools, callback_handler=None)
    if sm is not None:
        kwargs["session_manager"] = sm  # memória nativa cuida do histórico
    else:
        kwargs["messages"] = _seed_messages(payload.get("history"))  # fallback sem memória

    result = None
    try:
        agent = Agent(**kwargs)
        result = agent(q)
        answer = _clean_answer(str(result))
    finally:
        if sm is not None:
            try:
                sm.close()  # garante o flush dos eventos de memória (spans CreateEvent)
            except Exception as e:  # noqa: BLE001
                print("memory session manager close failed:", repr(e))
    debug = _build_debug(result, mode=mode, model_id=MODEL_ID, memory_on=sm is not None,
                         session_id=session_id, actor_id=actor_id)
    return {"result": {"answer": answer, "mode": mode, "debug": debug}}


# Web search: ativa quando o Gateway do AgentCore Web Search estiver configurado (SSM/env).
_WEB_TOOLS = [web_search] if _GW_URL else []

if __name__ == "__main__":
    app.run()
