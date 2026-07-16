"""Cliente do AgentCore Runtime (data plane).

O worker (e o wizard de resposta na API) invoca os agentes Strands hospedados no
AgentCore Runtime via `InvokeAgentRuntime` (resposta completa, SEM streaming). O browser
nunca chama o Runtime — apenas estes consumidores internos, autenticados por IAM.

Payload enviado ao agente (JSON):
    {"capability": "essay|exam|transcription|author", "modelId": "...", "input": {...}}
Resposta esperada do agente (JSON):
    {"ok": true, "result": {...}, "usage": {"tokensIn": int, "tokensOut": int}, "model": "..."}
"""
import json
import os
import uuid
from decimal import Decimal

import boto3


def _json_default(o):
    # DynamoDB devolve números como Decimal; o payload do agente precisa serializar.
    if isinstance(o, Decimal):
        return int(o) if o % 1 == 0 else float(o)
    if isinstance(o, set):
        return list(o)
    raise TypeError(f"Tipo não serializável: {type(o)}")

AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
AGENT_RUNTIME_PARAM = os.environ.get("AGENT_RUNTIME_PARAM", "")
AGENT_RUNTIME_QUALIFIER = os.environ.get("AGENT_RUNTIME_QUALIFIER", "DEFAULT")

_client = boto3.client("bedrock-agentcore")
_ssm = boto3.client("ssm")
_cached_arn = None


def _resolve_arn() -> str:
    """ARN do Runtime: env AGENT_RUNTIME_ARN tem prioridade; senão lê do SSM (cacheado).

    O `deploy-agents.sh` publica o ARN no parâmetro SSM após implantar o agente, sem
    exigir redeploy da stack.
    """
    global _cached_arn
    if AGENT_RUNTIME_ARN:
        return AGENT_RUNTIME_ARN
    if _cached_arn:
        return _cached_arn
    if AGENT_RUNTIME_PARAM:
        val = _ssm.get_parameter(Name=AGENT_RUNTIME_PARAM).get("Parameter", {}).get("Value", "")
        if val and val != "PENDING":
            _cached_arn = val
            return val
    return ""


def invoke_agent(capability: str, model_id: str, agent_input: dict, session_id: str = "") -> dict:
    """Invoca o agente no Runtime e retorna o dict JSON da resposta.

    Levanta RuntimeError se o Runtime não estiver configurado ou a resposta for inválida.
    """
    runtime_arn = _resolve_arn()
    if not runtime_arn:
        raise RuntimeError("Runtime dos agentes não configurado (rode deploy-agents.sh).")

    payload = json.dumps(
        {"capability": capability, "modelId": model_id, "input": agent_input},
        ensure_ascii=False, default=_json_default,
    ).encode("utf-8")

    # runtimeSessionId precisa ter comprimento mínimo (>= 33 chars).
    rsid = session_id or (uuid.uuid4().hex + uuid.uuid4().hex)

    resp = _client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        qualifier=AGENT_RUNTIME_QUALIFIER,
        runtimeSessionId=rsid,
        contentType="application/json",
        accept="application/json",
        payload=payload,
    )

    body = resp.get("response")
    raw = body.read() if hasattr(body, "read") else body
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    data = json.loads(raw) if raw else {}
    if not data.get("ok", False):
        raise RuntimeError(data.get("error", "Falha na execução do agente."))
    return data
