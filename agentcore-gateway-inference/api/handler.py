"""AgentCore — Gateway Inference: Router (Lambda) do módulo no portal.

Front door = portal, sob /agentcore/*. O browser nunca fala com o Gateway nem com o Runtime;
só esta Lambda (com IAM próprio).

Rotas (/agentcore/api/*):
  - health                         -> ok
  - models                         -> lista modelos do Gateway (agrupados por provider)
  - ask   {question,model,system_prompt} -> InvokeAgentRuntime (agente Strands) -> resposta

Config do Gateway e o ARN do Runtime vêm do SSM /gateway-inference/*. O token OAuth m2m
(client_credentials) é mintado a partir do segredo no Secrets Manager (só para /models; o
chat é feito pelo Runtime, que minta o próprio token).
"""
import json
import os
import time
import urllib.parse
import urllib.request

import boto3

_agentcore = boto3.client("bedrock-agentcore")
_ssm = boto3.client("ssm")
_secrets = boto3.client("secretsmanager")

_CFG = None
_TOK = {"secret": None, "token": None, "ts": 0.0}
_TOKEN_TTL = 50 * 60


def _cfg():
    global _CFG
    if _CFG is None:
        names = ["base-url", "token-endpoint", "client-id", "scope",
                 "client-secret-arn", "runtime-arn"]
        got = _ssm.get_parameters(Names=[f"/gateway-inference/{n}" for n in names])["Parameters"]
        m = {p["Name"].rsplit("/", 1)[-1]: p["Value"] for p in got}
        _CFG = m
    return _CFG


def _resp(status, body):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, ensure_ascii=False)}


def _subpath(event):
    raw = event.get("rawPath", "") or ""
    marker = "/agentcore/api/"
    if marker in raw:
        return raw.split(marker, 1)[1].strip("/")
    return raw.rsplit("/", 1)[-1].strip("/")


def _m2m_token(cfg, force=False):
    now = time.time()
    if not force and _TOK["token"] and (now - _TOK["ts"]) < _TOKEN_TTL:
        return _TOK["token"]
    if _TOK["secret"] is None:
        _TOK["secret"] = _secrets.get_secret_value(SecretId=cfg["client-secret-arn"])["SecretString"]
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": cfg["client-id"],
        "client_secret": _TOK["secret"], "scope": cfg["scope"],
    }).encode()
    req = urllib.request.Request(cfg["token-endpoint"], data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 — endpoint fixo (Cognito)
        _TOK["token"] = json.loads(r.read())["access_token"]
    _TOK["ts"] = now
    return _TOK["token"]


def _list_models(cfg):
    token = _m2m_token(cfg)
    req = urllib.request.Request(cfg["base-url"].rstrip("/") + "/models",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 — base URL do Gateway (SSM)
        data = json.loads(r.read())
    ids = sorted(m["id"] for m in data.get("data", []))
    grouped = {}
    for mid in ids:
        short = mid.rsplit("/", 1)[-1]
        prov = short.split(".", 1)[0]
        grouped.setdefault(prov, []).append(mid)
    return {"models": ids, "grouped": grouped, "count": len(ids)}


def _ask(cfg, *, question, model, system_prompt, session_id):
    payload = json.dumps({"question": question, "model": model,
                          "system_prompt": system_prompt or ""}).encode("utf-8")
    resp = _agentcore.invoke_agent_runtime(
        agentRuntimeArn=cfg["runtime-arn"], runtimeSessionId=session_id,
        contentType="application/json", accept="application/json", payload=payload)
    body = resp.get("response")
    raw = body.read() if hasattr(body, "read") else body
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    return data.get("result", data) if isinstance(data, dict) else {}


def _session_id(event, model):
    import hashlib
    try:
        sub = event["requestContext"]["authorizer"]["jwt"]["claims"].get("sub", "")
    except (KeyError, TypeError):
        sub = ""
    conv = ""
    if event.get("body"):
        try:
            conv = (json.loads(event["body"]) or {}).get("conv", "")
        except (ValueError, TypeError):
            conv = ""
    return hashlib.sha256(f"gwinf:{sub}:{conv}".encode()).hexdigest()


def handler(event, context):
    path = _subpath(event)
    if path == "health":
        return _resp(200, {"ok": True, "module": "agentcore-gateway-inference"})

    cfg = _cfg()
    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except (ValueError, TypeError):
            body = {}
    try:
        if path == "models":
            return _resp(200, _list_models(cfg))
        if path == "ask":
            q = (body.get("question") or "").strip()
            if not q:
                return _resp(400, {"error": "pergunta vazia"})
            model = (body.get("model") or "").strip()
            if not model:
                return _resp(400, {"error": "selecione um modelo"})
            res = _ask(cfg, question=q, model=model,
                       system_prompt=body.get("system_prompt"),
                       session_id=_session_id(event, model))
            return _resp(200, {"result": res})
        return _resp(404, {"error": f"rota nao encontrada: {path}"})
    except Exception as e:  # noqa: BLE001
        print("gateway-inference error:", repr(e))
        return _resp(502, {"error": "falha ao processar a requisicao"})
