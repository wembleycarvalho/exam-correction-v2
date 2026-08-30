"""Orientador Context — agente serverless (Lambda) do portal "A Arte do Possível".

Padrão da opção B1 da spec: o agente (aqui em Lambda, não AgentCore Runtime) consome o
data lake (Athena sobre `moodle_datalake`) via Bedrock Converse + tool-use. Front door é o
portal, sob /orientador-context/*. Coexiste com o Orientador atual (Neptune), sem tocá-lo.

RBAC (ganho central): o papel vem dos grupos do Cognito (claims do JWT). Coordenador
(admin/professor) acessa visões agregadas e alunos em risco; aluno é escopado ao próprio.
"""
import json
import os

import boto3

import tools
import prompts

_bedrock = boto3.client("bedrock-runtime")
MODEL_ID = os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0")


def _resp(status, body):
    return {"statusCode": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, ensure_ascii=False)}


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


def _messages(history, question):
    msgs = []
    for h in (history or [])[-8:]:
        role = "assistant" if h.get("role") == "assistant" else "user"
        text = (h.get("text") or h.get("content") or "").strip()
        if text:
            msgs.append({"role": role, "content": [{"text": text}]})
    msgs.append({"role": "user", "content": [{"text": question}]})
    return msgs


def _ask(question, *, is_coord, student_id, history):
    system = prompts.COORD if is_coord else prompts.ALUNO
    toolset = tools.COORD_TOOLS if is_coord else tools.ALUNO_TOOLS
    messages = _messages(history, question)

    for _ in range(6):
        resp = _bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": system}],
            messages=messages,
            toolConfig={"tools": toolset},
            inferenceConfig={"maxTokens": 1200, "temperature": 0.2},
        )
        out = resp["output"]["message"]
        messages.append(out)
        if resp.get("stopReason") == "tool_use":
            results = []
            for block in out.get("content", []):
                tu = block.get("toolUse")
                if not tu:
                    continue
                result = tools.execute(tu["name"], tu.get("input", {}),
                                       is_coord=is_coord, student_id=student_id)
                results.append({"toolResult": {
                    "toolUseId": tu["toolUseId"], "content": [{"json": result}]}})
            messages.append({"role": "user", "content": results})
            continue
        text = "".join(b.get("text", "") for b in out.get("content", []))
        return text.strip() or "Não consegui elaborar uma resposta."
    return "Não consegui concluir a análise com os dados disponíveis."


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

    try:
        if path == "bootstrap":
            faculdades = tools.desempenho_faculdade()["faculdades"] if has_priv else []
            alunos = tools.query_alunos_min() if has_priv else []
            return _resp(200, {"result": {
                "is_coord_capable": has_priv,
                "faculdades": [f["faculdade"] for f in faculdades],
                "students": alunos}})

        if path == "ask":
            q = (body.get("question") or "").strip()
            if not q:
                return _resp(400, {"error": "pergunta vazia"})
            if not is_coord and not student_id:
                return _resp(400, {"error": "selecione um aluno (modo aluno)"})
            answer = _ask(q, is_coord=is_coord, student_id=student_id,
                          history=body.get("history"))
            return _resp(200, {"result": {"answer": answer, "mode": "coord" if is_coord else "aluno"}})

        if path == "perfil":
            if not student_id:
                return _resp(400, {"error": "student_id obrigatório"})
            return _resp(200, {"result": tools.perfil_aluno(student_id)})

        if path == "risco":
            if not has_priv:
                return _resp(403, {"error": "restrito à coordenação"})
            return _resp(200, {"result": tools.alunos_em_risco(
                int(body.get("min_reprovacoes", 3) or 3), body.get("faculdade", ""))})

        if path == "desempenho":
            if not has_priv:
                return _resp(403, {"error": "restrito à coordenação"})
            return _resp(200, {"result": tools.desempenho_faculdade()})

        return _resp(404, {"error": f"rota não encontrada: {path}"})
    except Exception as e:  # noqa: BLE001
        return _resp(502, {"error": str(e)})
