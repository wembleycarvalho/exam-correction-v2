"""AgentCore Runtime entrypoint for the Orientador Acadêmico agent.

Hydrates the knowledge graph from Neptune (source of truth) on cold start, then serves:
  {"action":"ask","student_id":..,"question":..}  -> agente Strands + tools -> resposta PT-BR
  {"action":"recommend","student_id":..,"career_id"?}
  {"action":"progress","student_id":..}
  {"action":"stats"} / {"action":"bootstrap"}

The browser never calls this directly — a bridge Lambda invokes it via InvokeAgentRuntime.
"""
import os
import re
import sys
import time
import traceback
from contextlib import suppress

from bedrock_agentcore.runtime import BedrockAgentCoreApp


def log(*a):
    print("[orientador]", *a, file=sys.stderr, flush=True)


log("boot: entrypoint module importing")

from src.graph.neptune_client import NeptuneClient
from src.graph.neptune_store import build_graph_from_neptune
from src.graph.builder import nodes_by_type
from src.graph import queries as q
from src.recommender import path_engine as pe
from src.recommender import insights as ins
from src.llm.response_builder import answer_question  # fallback determinístico

from . import tools

MODEL_ID = os.environ.get("ORIENTADOR_MODEL_ID", "amazon.nova-pro-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")

SYSTEM = (
    "Você é o Orientador Acadêmico, um assistente que ajuda estudantes a planejar sua "
    "trilha de disciplinas com base em um grafo de conhecimento (disciplinas, pré-requisitos, "
    "competências e carreiras). Responda SEMPRE em português brasileiro, de forma clara e "
    "acolhedora. Use as ferramentas para obter os dados do grafo e NUNCA invente disciplinas, "
    "notas, pré-requisitos ou números que não venham das ferramentas. O grafo sabe o que o "
    "aluno JÁ CONCLUIU (progresso_aluno) e o que ele está CURSANDO neste semestre "
    "(minha_matricula) — use essas ferramentas em vez de supor. Quando recomendar uma trilha, "
    "apresente o plano por semestre.\n"
    "IMPORTANTE: nunca exponha identificadores internos do sistema (como 'disc_006', "
    "'prog_es', 'career_001', 'comp_007'). Refira-se a cursos, disciplinas, competências e "
    "carreiras SEMPRE pelo NOME legível; para disciplinas você pode incluir o código entre "
    "parênteses (ex.: 'Banco de Dados I (CC006)').\n"
    "FORMATO DA RESPOSTA: escreva SEMPRE em Markdown — títulos de seção com '## ', rótulos em "
    "**negrito** e itens em listas com '- '. Apresente planos por semestre, trilhas e "
    "quaisquer listas SEMPRE como listas Markdown, NUNCA como texto corrido."
)

COORD_SYSTEM = (
    "Você é o Orientador Acadêmico no modo COORDENAÇÃO. Ajuda o coordenador a analisar "
    "TODOS os alunos e cursos com base num grafo acadêmico. Responda SEMPRE em português "
    "brasileiro, de forma clara e objetiva, usando SOMENTE os dados retornados pelas "
    "ferramentas. Ao listar alunos, agrupe por curso e destaque quando houver alunos de "
    "CURSOS DIFERENTES.\n"
    "O QUE O GRAFO CONTÉM: cursos; disciplinas (com tipo obrigatória/eletiva e código); "
    "competências; carreiras; alunos; o que cada aluno JÁ CONCLUIU (com nota, semestre e ano); "
    "e em quais disciplinas cada aluno está MATRICULADO NESTE SEMESTRE (cursando agora). Para "
    "'quantos alunos por disciplina neste semestre', use disciplinas_do_curso (campo "
    "matriculados_agora) ou alunos_matriculados_por_disciplina — nunca chute.\n"
    "GRADE DE HORÁRIOS E SALAS: para 'montar grade de horários' ou 'quantas salas preciso' "
    "(inclusive turno noturno), use a ferramenta montar_grade_noturna — ela CALCULA uma grade "
    "conflito-consciente a partir da matrícula real (disciplinas com aluno em comum não "
    "coincidem) sob premissas EXPLÍCITAS (noites/semana, aulas/noite). Sempre apresente as "
    "premissas retornadas e o nº de salas. Se o usuário indicar noites/aulas por noite, passe "
    "como parâmetros. Para a agenda de UM aluno específico (ex.: 'quais dias e horários o aluno "
    "Fulano tem aula'), use grade_do_aluno com o NOME do aluno — ela cruza a matrícula dele com "
    "a mesma grade (use os mesmos parâmetros da grade que você acabou de montar).\n"
    "O QUE O GRAFO NÃO CONTÉM (NÃO invente sob nenhuma hipótese): nomes de professores, "
    "capacidade/tamanho de salas, custos ou projeções. Para 'quantos professores', use o nº de "
    "aulas simultâneas no pico (retornado pela grade) como mínimo e explique que o total "
    "depende da carga por professor — NUNCA invente nomes de professores nem lotação de sala.\n"
    "IMPORTANTE: nunca exponha identificadores internos (como 'disc_006', 'prog_es', "
    "'career_001', 'student_001', 'comp_007'). Use SEMPRE os nomes legíveis.\n"
    "FORMATO DA RESPOSTA: escreva SEMPRE em Markdown — títulos de seção com '## ' (e '### ' "
    "para subseções, ex.: dias da semana), rótulos em **negrito** (ex.: '**Salas "
    "necessárias:** 6') e itens em listas com '- '. Grades de horário, disciplinas por "
    "horário e QUALQUER lista devem sair como listas Markdown, NUNCA como texto corrido."
)

app = BedrockAgentCoreApp()
_GRAPH = None


def graph():
    global _GRAPH
    if _GRAPH is None:
        ep = os.environ.get("NEPTUNE_ENDPOINT", "<unset>")
        log(f"hydrating graph from Neptune endpoint={ep}")
        t0 = time.time()
        _GRAPH = build_graph_from_neptune(NeptuneClient())
        tools.set_graph(_GRAPH)
        log(f"graph hydrated in {time.time() - t0:.1f}s "
            f"nodes={_GRAPH.number_of_nodes()} edges={_GRAPH.number_of_edges()}")
    return _GRAPH


def _extract_text(result) -> str:
    with suppress(Exception):
        msg = getattr(result, "message", None)
        if isinstance(msg, dict):
            txt = "".join(c.get("text", "") for c in msg.get("content", []) if isinstance(c, dict))
            if txt.strip():
                return txt
    return str(result)


# Remove blocos de raciocínio do modelo e qualquer id interno que escape para a resposta.
_THINK_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)
_ID_RE = re.compile(r"\b(?:disc|comp|career|student)_\d+\b|\bprog_[a-z0-9]+\b")


def _sanitize(g, text: str) -> str:
    if not text:
        return text
    text = _THINK_RE.sub("", text)
    text = re.sub(r"</?thinking>", "", text, flags=re.IGNORECASE)

    def repl(m):
        tok = m.group(0)
        return g.nodes[tok].get("name", tok) if tok in g.nodes else tok

    return _ID_RE.sub(repl, text).strip()


def _history_messages(history) -> list:
    """Converte o histórico do chat (lista {role, content}) para o formato do Strands."""
    msgs = []
    for turn in (history or [])[-8:]:  # limita a memória recente
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": [{"text": content}]})
    return msgs


def _ask(student_id: str, question: str, history=None, mode: str | None = None) -> dict:
    g = graph()
    tools.set_graph(g)
    # Modo coordenação: cruza TODOS os alunos (sem escopo de aluno único).
    coordinator = (mode == "coordinator") or (student_id in (None, "", "__coord__"))
    if coordinator:
        system, toolset = COORD_SYSTEM, tools.COORD_TOOLS
    else:
        tools.CURRENT_STUDENT.set(student_id)
        student = q.get_node(g, student_id)
        prog_id, career_id = student.get("program"), student.get("target_career")
        prog_name = g.nodes[prog_id].get("name", prog_id) if prog_id in g.nodes else prog_id
        career_name = g.nodes[career_id].get("name", career_id) if career_id in g.nodes else career_id
        system = (SYSTEM + f"\nAluno atual: {student.get('name')} "
                  f"(curso {prog_name}, carreira-alvo {career_name}).")
        toolset = tools.TOOLS
    try:
        from strands import Agent
        from strands.models import BedrockModel
        # Memória da conversa: injeta os turnos anteriores para dar continuidade
        # (ex.: 'quais faltam?' entende que se refere à resposta anterior).
        agent = Agent(model=BedrockModel(model_id=MODEL_ID, region_name=REGION),
                      system_prompt=system, tools=toolset,
                      messages=_history_messages(history))
        return {"answer": _sanitize(g, _extract_text(agent(question))), "engine": "strands",
                "mode": "coordinator" if coordinator else "student"}
    except Exception as e:  # noqa: BLE001 — fallback determinístico mantém a demo de pé
        if coordinator:
            return {"answer": "Não consegui processar a pergunta de coordenação agora. "
                    "Tente reformular (ex.: 'quais alunos estão no curso de Banco de Dados?').",
                    "engine": "fallback", "mode": "coordinator", "note": str(e)}
        out = answer_question(g, student_id, question)
        return {"answer": _sanitize(g, out["answer"]), "engine": "fallback", "note": str(e)}


@app.entrypoint
def invoke(payload: dict) -> dict:
    action = (payload or {}).get("action", "ask")
    log(f"invoke action={action!r}")
    try:
        g = graph()
        if action == "ask":
            return {"ok": True, **_ask(payload.get("student_id"), payload.get("question", ""),
                                       payload.get("history"), mode=payload.get("mode"))}
        if action == "recommend":
            return {"ok": True, "result": pe.recommend_path(g, payload["student_id"], payload.get("career_id"))}
        if action == "progress":
            return {"ok": True, "result": pe.student_progress(g, payload["student_id"])}
        if action == "student":
            # Perfil legível do aluno (nomes, sem ids internos) para a tela de Alunos.
            return {"ok": True, "result": ins.student_profile(g, payload["student_id"])}
        if action == "graph":
            # Subgrafo para visualização (força dirigida no frontend).
            return {"ok": True, "result": ins.subgraph(
                g, (payload or {}).get("scope", "full"), (payload or {}).get("id"))}
        if action == "stats":
            return {"ok": True, "result": q.graph_stats(g)}
        if action == "insights":
            # Insights nativos de grafo centrados no aluno (gargalos, caminho crítico, gaps).
            return {"ok": True, "result": ins.student_insights(
                g, payload["student_id"], payload.get("career_id"))}
        if action == "curriculum":
            # Mapa de currículo ES×CC (pontes/sobreposição) + competências estratégicas.
            return {"ok": True, "result": {
                **ins.curriculum_overview(g),
                "strategic_competencies": ins.strategic_competencies(g, top=12),
            }}
        if action == "competency_report":
            # Relatório de competências por carreira (cobertura por programa).
            career = payload.get("career_id")
            if not career:
                return {"ok": False, "error": "career_id é obrigatório"}
            return {"ok": True, "result": ins.career_competency_report(g, career)}
        if action == "program_detail":
            pid = payload.get("program_id")
            if not pid:
                return {"ok": False, "error": "program_id é obrigatório"}
            return {"ok": True, "result": ins.program_detail(g, pid)}
        if action == "career_detail":
            career = payload.get("career_id")
            if not career:
                return {"ok": False, "error": "career_id é obrigatório"}
            return {"ok": True, "result": ins.career_detail(g, career)}
        if action == "career_questions":
            # Direcionador de carreira: questionário (perguntas por competência).
            return {"ok": True, "result": {"questions": ins.career_questionnaire(g)}}
        if action == "career_result":
            # Respostas (0..4 por competência) -> ranking de carreiras + relatório de aderência.
            answers = (payload or {}).get("answers") or {}
            interest = {cid: max(0.0, min(1.0, float(v) / 4.0)) for cid, v in answers.items()}
            ranking = ins.score_careers(g, interest, top=5)
            chosen = payload.get("chosen_career_id") or (ranking[0]["career"] if ranking else None)
            report = ins.career_fit_report(g, payload["student_id"], chosen) if chosen else None
            student = q.get_node(g, payload["student_id"])
            ct = student.get("target_career")
            current_target = ({"id": ct, "name": g.nodes[ct].get("name", ct)}
                              if ct and ct in g.nodes else None)
            return {"ok": True, "result": {"ranking": ranking, "report": report,
                                           "current_target": current_target}}
        if action == "set_target_career":
            # Grava o novo objetivo de carreira no Neptune (escrita) e atualiza o grafo em memória.
            from src.graph import neptune_store as store
            sid, career = payload.get("student_id"), payload.get("career_id")
            if not sid or not career:
                return {"ok": False, "error": "student_id e career_id são obrigatórios"}
            store.set_student_target(NeptuneClient(), sid, career)
            if sid in g.nodes:
                g.nodes[sid]["target_career"] = career
            return {"ok": True, "result": {"student_id": sid, "target_career": career,
                                           "target_career_name": g.nodes[career].get("name", career)
                                           if career in g.nodes else career}}
        if action == "request_course_change":
            # Registra um pedido de troca de curso (pendente) no perfil do aluno. NÃO troca.
            from src.graph import neptune_store as store
            from datetime import datetime, timezone
            sid, pid = payload.get("student_id"), payload.get("program_id")
            career = payload.get("career_id") or ""
            if not sid or not pid:
                return {"ok": False, "error": "student_id e program_id são obrigatórios"}
            when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            store.request_course_change(NeptuneClient(), sid, pid, career, when)
            if sid in g.nodes:
                g.nodes[sid].update({"course_change_to": pid, "course_change_career": career,
                                     "course_change_at": when, "course_change_status": "pending"})
            return {"ok": True, "result": {"student_id": sid, "program_id": pid,
                                           "program_name": g.nodes[pid].get("name", pid) if pid in g.nodes else pid,
                                           "at": when}}
        if action == "list_course_changes":
            # Coordenador: lista de pedidos pendentes lida AO VIVO do Neptune (não do cache).
            from src.graph import neptune_store as store
            rows = store.list_pending_course_changes(NeptuneClient())

            def pref(pid):
                return {"id": pid, "name": g.nodes[pid].get("name", pid) if pid in g.nodes else pid}

            def cref(cid):
                return ({"id": cid, "name": g.nodes[cid].get("name", cid)}
                        if cid and cid in g.nodes else None)

            requests = [{"student_id": r.get("id"), "name": r.get("name"),
                         "from_program": pref(r.get("program")),
                         "to_program": pref(r.get("to_program")),
                         "career": cref(r.get("career")),
                         "at": r.get("at"), "status": r.get("status") or "pending"}
                        for r in rows]
            requests.sort(key=lambda x: x.get("at") or "")
            return {"ok": True, "result": {"requests": requests}}
        if action == "resolve_course_change":
            # Coordenador aceita/nega um pedido. accept efetiva a troca de curso.
            from src.graph import neptune_store as store
            sid = payload.get("student_id")
            decision = payload.get("decision")
            if not sid or decision not in ("accept", "deny"):
                return {"ok": False, "error": "student_id e decision (accept|deny) são obrigatórios"}
            to = g.nodes[sid].get("course_change_to") if sid in g.nodes else None
            store.resolve_course_change(NeptuneClient(), sid, decision, to)
            if sid in g.nodes:
                nd = g.nodes[sid]
                if decision == "accept" and to:
                    nd["program"] = to
                nd["course_change_status"] = "accepted" if decision == "accept" else "denied"
                for k in ("course_change_to", "course_change_career", "course_change_at"):
                    nd.pop(k, None)
            return {"ok": True, "result": {"student_id": sid, "decision": decision,
                                           "new_program": to if decision == "accept" else None}}
        if action == "load":
            # Carga do dataset (JSON embutido no container) no Neptune — roda de dentro
            # da VPC. Usado uma vez após o deploy (ou para recarregar).
            from src.graph import neptune_store as store
            client = NeptuneClient()
            if (payload or {}).get("clear"):
                store.clear_graph(client)
            counts = store.load_json_to_neptune(client)
            global _GRAPH
            _GRAPH = None  # força re-hidratar no próximo uso
            return {"ok": True, "result": counts}
        if action == "bootstrap":
            return {"ok": True, "result": {
                "programs": nodes_by_type(g, "Program"),
                "careers": nodes_by_type(g, "Career"),
                "students": [{"id": s["id"], "name": s.get("name"), "program": s.get("program"),
                              "target_career": s.get("target_career")}
                             for s in nodes_by_type(g, "Student")],
                "disciplines": [{"id": d["id"], "name": d.get("name"), "code": d.get("code"),
                                 "area": d.get("area"), "programs": d.get("programs", [])}
                                for d in nodes_by_type(g, "Discipline")],
                "stats": q.graph_stats(g),
            }}
        return {"ok": False, "error": f"ação desconhecida: {action!r}"}
    except Exception as exc:  # noqa: BLE001 — contrato de erro estruturado
        log(f"invoke action={action!r} FAILED: {exc}\n{traceback.format_exc()}")
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    app.run()
