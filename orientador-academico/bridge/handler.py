"""Bridge Lambda: ponte HTTP (via CloudFront + Cognito) -> AgentCore Runtime.

O browser nunca fala com o Runtime; este Lambda resolve o ARN do agente (SSM, publicado
pelo deploy do agente) e chama InvokeAgentRuntime de forma não-streaming. Mapeia as rotas
/orientador/api/* para as ações do agente (ask/recommend/progress/stats/bootstrap).
"""
import json
import os
import uuid

import boto3

_ssm = boto3.client("ssm")
_agent = boto3.client("bedrock-agentcore")


def _runtime_arn() -> str:
    # Lê o SSM a cada invocação: o ARN muda quando o agente é reimplantado (novo runtime),
    # e o volume aqui é baixo — cache em memória arriscaria apontar para um runtime deletado.
    return _ssm.get_parameter(Name=os.environ["AGENT_RUNTIME_PARAM"])["Parameter"]["Value"]


def _session_id(body: dict) -> str:
    # AgentCore exige runtimeSessionId com no mínimo 33 caracteres (uuid4().hex tem 32).
    sid = body.get("session_id") or ""
    if len(sid) >= 33:
        return sid
    return "orientador-" + uuid.uuid4().hex  # 11 + 32 = 43 chars


def _resp(status: int, body: dict):
    return {"statusCode": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, ensure_ascii=False)}


def _subpath(event: dict) -> str:
    raw = event.get("rawPath", "") or ""
    marker = "/orientador/api/"
    return raw.split(marker, 1)[1].strip("/") if marker in raw else raw.strip("/")


def handler(event, context):
    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except (ValueError, TypeError):
            body = {}

    path = _subpath(event)
    if path == "bootstrap":
        payload = {"action": "bootstrap"}
    elif path == "ask":
        payload = {"action": "ask", "student_id": body.get("student_id"),
                   "mode": body.get("mode"),
                   "question": body.get("question", ""), "history": body.get("history")}
    elif path == "recommend":
        payload = {"action": "recommend", "student_id": body.get("student_id"),
                   "career_id": body.get("career_id")}
    elif path == "progress":
        payload = {"action": "progress", "student_id": body.get("student_id")}
    elif path == "student":
        payload = {"action": "student", "student_id": body.get("student_id")}
    elif path == "graph":
        payload = {"action": "graph", "scope": body.get("scope", "full"), "id": body.get("id")}
    elif path == "program":
        payload = {"action": "program_detail", "program_id": body.get("program_id")}
    elif path == "career":
        payload = {"action": "career_detail", "career_id": body.get("career_id")}
    elif path in ("career-questions", "career_questions"):
        payload = {"action": "career_questions"}
    elif path in ("career-result", "career_result"):
        payload = {"action": "career_result", "student_id": body.get("student_id"),
                   "answers": body.get("answers"), "chosen_career_id": body.get("chosen_career_id")}
    elif path in ("set-target", "set_target"):
        payload = {"action": "set_target_career", "student_id": body.get("student_id"),
                   "career_id": body.get("career_id")}
    elif path in ("request-course-change", "request_course_change"):
        payload = {"action": "request_course_change", "student_id": body.get("student_id"),
                   "program_id": body.get("program_id"), "career_id": body.get("career_id")}
    elif path == "transfers":
        payload = {"action": "list_course_changes"}
    elif path in ("transfer-resolve", "transfer_resolve"):
        payload = {"action": "resolve_course_change", "student_id": body.get("student_id"),
                   "decision": body.get("decision")}
    elif path == "stats":
        payload = {"action": "stats"}
    elif path == "insights":
        payload = {"action": "insights", "student_id": body.get("student_id"),
                   "career_id": body.get("career_id")}
    elif path == "curriculum":
        payload = {"action": "curriculum"}
    elif path in ("competency-report", "competency_report"):
        payload = {"action": "competency_report", "career_id": body.get("career_id")}
    else:
        return _resp(404, {"error": f"rota não encontrada: {path}"})

    arn = _runtime_arn()
    if not arn or arn == "PENDING":
        return _resp(503, {"error": "Agente ainda não implantado (rode o deploy do agente)."})

    try:
        resp = _agent.invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=_session_id(body),
            contentType="application/json",
            accept="application/json",
            payload=json.dumps(payload).encode("utf-8"),
        )
        stream = resp.get("response")
        raw = stream.read() if hasattr(stream, "read") else stream
        data = json.loads(raw)
        return _resp(200, data)
    except Exception as e:  # noqa: BLE001
        return _resp(502, {"error": f"falha ao invocar o agente: {e}"})
