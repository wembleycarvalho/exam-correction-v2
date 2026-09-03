"""AgentCore module — Gateway Inference (EKS Fargate + STREAMING SSE real).

Este é o backend do módulo "Gateway Inference" rodando no Amazon EKS Fargate (cluster
`strands-obs-demo`), atrás de um ALB + CloudFront (/agentcore/*). Diferente do caminho
Runtime+Lambda (que bufferiza a resposta em API Gateway), aqui o pod fica vivo e faz
STREAMING token-a-token via SSE — que é a razão de termos feito a PoC de EKS no Fargate.

Fluxo:
  browser (portal, JWT Cognito) -> CloudFront /agentcore/* -> ALB -> este pod
    -> Strands Agent (provider OpenAI/Anthropic) -> AgentCore Gateway (bedrock-mantle)
    -> stream_async -> SSE de volta ao browser.

O agente autentica no Gateway com token OAuth m2m (client_credentials) mintado a partir do
segredo no Secrets Manager. O browser NUNCA vê o segredo nem fala com o Gateway direto.

Observability NATIVA (mesma da PoC): o processo roda sob `opentelemetry-instrument`
(aws_distro), o Strands emite spans gen_ai.* que caem no CloudWatch GenAI Observability.

Rotas (montadas sob /agentcore/api/* pelo CloudFront):
  GET  /health              -> ok
  GET  /models              -> modelos do Gateway (agrupados por provider)
  POST /ask                 -> resposta COMPLETA em JSON (usado pela Evaluation, N modelos)
  POST /ask/stream          -> SSE token-a-token (usado pelo chat Inference)
  GET  /mantle/metrics      -> uso do Gateway (CloudWatch AWS/BedrockMantle)

Config (SSM /gateway-inference/*): base-url, token-endpoint, client-id, scope,
client-secret-arn. Auth do portal: POOL_ID (Cognito user pool do portal) via env.
"""
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import boto3
from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from opentelemetry import baggage, context
from pydantic import BaseModel

from strands import Agent

REGION = os.environ.get("AWS_REGION", "us-east-1")
DEFAULT_MODEL = os.environ.get("MODEL_ID", "bedrock-inference/anthropic.claude-haiku-4-5")
_SSM_PREFIX = os.environ.get("SSM_PREFIX", "/gateway-inference")

# Auth do portal (Cognito). Se REQUIRE_AUTH=false, pula validação (dev/port-forward).
POOL_ID = os.environ.get("POOL_ID", "")
REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "true").lower() != "false"

_MANTLE_NS = "AWS/BedrockMantle"

_ssm = boto3.client("ssm", region_name=REGION)
_secrets = boto3.client("secretsmanager", region_name=REGION)
_cw = boto3.client("cloudwatch", region_name=REGION)

_SYSTEM_DEFAULT = (
    "You are a helpful assistant. Reply clearly and naturally in the same language as the "
    "user's question."
)

app = FastAPI(title="AgentCore Gateway Inference (EKS + SSE)")
# As rotas são montadas 2x: na raiz (healthcheck do ALB, testes diretos) e sob
# /agentcore/api (o CloudFront encaminha o path completo /agentcore/* ao ALB).
router = APIRouter()


# --------------------------------------------------------------------------- config / token
def _ssm_get(name, default=""):
    try:
        return _ssm.get_parameter(Name=f"{_SSM_PREFIX}/{name}")["Parameter"]["Value"]
    except Exception:  # noqa: BLE001
        return default


_CFG = {
    "base_url": os.environ.get("GW_BASE_URL") or _ssm_get("base-url"),
    "token_endpoint": os.environ.get("COGNITO_TOKEN_ENDPOINT") or _ssm_get("token-endpoint"),
    "client_id": os.environ.get("COGNITO_CLIENT_ID") or _ssm_get("client-id"),
    "scope": os.environ.get("COGNITO_SCOPE") or _ssm_get("scope"),
    "secret_arn": os.environ.get("CLIENT_SECRET_ARN") or _ssm_get("client-secret-arn"),
}

_TOK = {"secret": None, "token": None, "ts": 0.0}
_TOKEN_TTL = 50 * 60


def _client_secret():
    if _TOK["secret"] is None:
        _TOK["secret"] = _secrets.get_secret_value(SecretId=_CFG["secret_arn"])["SecretString"]
    return _TOK["secret"]


def _m2m_token(force=False):
    now = time.time()
    if not force and _TOK["token"] and (now - _TOK["ts"]) < _TOKEN_TTL:
        return _TOK["token"]
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": _CFG["client_id"],
        "client_secret": _client_secret(),
        "scope": _CFG["scope"],
    }).encode()
    req = urllib.request.Request(_CFG["token_endpoint"], data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 — endpoint fixo (Cognito)
        tok = json.loads(r.read())["access_token"]
    _TOK["token"] = tok
    _TOK["ts"] = now
    return tok


def _clean(text):
    return re.sub(r"<thinking>.*?</thinking>", "", text or "",
                  flags=re.DOTALL | re.IGNORECASE).strip()


# --------------------------------------------------------------------------- model routing
# Mesmo roteamento determinístico do runtime agent.py: bedrock-mantle expõe cada modelo por
# UMA das 3 APIs OpenAI/Anthropic-compatíveis.
def _make_model(model_id, token):
    short = model_id.rsplit("/", 1)[-1]
    provider = short.split(".", 1)[0]
    base = _CFG["base_url"]
    if provider == "anthropic":
        from strands.models.anthropic import AnthropicModel
        anth_base = re.sub(r"/v1/?$", "", base)
        return AnthropicModel(client_args={"base_url": anth_base, "auth_token": token},
                              model_id=model_id, max_tokens=2048)
    if provider == "openai" and ("gpt-5" in short or "gpt-oss" in short) and "safeguard" not in short:
        from strands.models.openai_responses import OpenAIResponsesModel
        return OpenAIResponsesModel(client_args={"base_url": base, "api_key": token},
                                    model_id=model_id)
    from strands.models.openai import OpenAIModel
    return OpenAIModel(client_args={"base_url": base, "api_key": token}, model_id=model_id)


def _build_agent(model_id, system):
    token = _m2m_token()
    model = _make_model(model_id, token)
    return Agent(model=model, system_prompt=system or _SYSTEM_DEFAULT, callback_handler=None)


def _debug_from(result, model_id):
    m = getattr(result, "metrics", None)
    usage = dict(getattr(m, "accumulated_usage", {}) or {})
    latency = (getattr(m, "accumulated_metrics", {}) or {}).get("latencyMs", 0)
    return {
        "model": model_id,
        "gateway": (_CFG["base_url"] or "").split("//")[-1].split("/")[0],
        "tokens": {"input": int(usage.get("inputTokens", 0) or 0),
                   "output": int(usage.get("outputTokens", 0) or 0),
                   "total": int(usage.get("totalTokens", 0) or 0)},
        "latency_ms": round(float(latency or 0), 1),
    }


# --------------------------------------------------------------------------- auth (Cognito)
_JWK = {"client": None}


def _jwk_client():
    if _JWK["client"] is None:
        from jwt import PyJWKClient
        url = f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}/.well-known/jwks.json"
        _JWK["client"] = PyJWKClient(url)
    return _JWK["client"]


def _verify_jwt(authorization):
    """Valida o access/id token do Cognito do portal. Retorna o `sub` (ou '' se auth off)."""
    if not REQUIRE_AUTH:
        return ""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    tok = authorization.split(" ", 1)[1].strip()
    try:
        import jwt
        signing_key = _jwk_client().get_signing_key_from_jwt(tok)
        claims = jwt.decode(
            tok, signing_key.key, algorithms=["RS256"],
            issuer=f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}",
            options={"verify_aud": False},
        )
        if claims.get("token_use") not in ("access", "id"):
            raise HTTPException(status_code=401, detail="invalid token_use")
        return claims.get("sub", "")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="invalid token") from e


def _session_id(sub, conv):
    return hashlib.sha256(f"gwinf:{sub}:{conv or ''}".encode()).hexdigest()


# --------------------------------------------------------------------------- models / mantle
def _list_models():
    token = _m2m_token()
    req = urllib.request.Request(_CFG["base_url"].rstrip("/") + "/models",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 — base URL do Gateway (SSM)
        data = json.loads(r.read())
    ids = sorted(m["id"] for m in data.get("data", []))
    grouped = {}
    for mid in ids:
        short = mid.rsplit("/", 1)[-1]
        grouped.setdefault(short.split(".", 1)[0], []).append(mid)
    return {"models": ids, "grouped": grouped, "count": len(ids)}


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _mantle_metrics(hours=24):
    models = set()
    pag = _cw.get_paginator("list_metrics")
    for page in pag.paginate(Namespace=_MANTLE_NS, MetricName="TotalInputTokens",
                             Dimensions=[{"Name": "Model"}]):
        for m in page.get("Metrics", []):
            if {d["Name"] for d in m["Dimensions"]} == {"Model"}:
                models.add(m["Dimensions"][0]["Value"])
    models = sorted(models)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    span = max(hours * 3600, 60)

    def mq(qid, metric, model, stat):
        return {"Id": qid, "ReturnData": True, "MetricStat": {
            "Metric": {"Namespace": _MANTLE_NS, "MetricName": metric,
                       "Dimensions": [{"Name": "Model", "Value": model}]},
            "Period": span, "Stat": stat}}

    queries, idmap = [], {}
    for i, model in enumerate(models):
        queries += [mq(f"m{i}i", "TotalInputTokens", model, "Sum"),
                    mq(f"m{i}o", "TotalOutputTokens", model, "Sum"),
                    mq(f"m{i}n", "Inferences", model, "Sum")]
        idmap[f"m{i}i"] = (model, "inputTokens")
        idmap[f"m{i}o"] = (model, "outputTokens")
        idmap[f"m{i}n"] = (model, "inferences")
    rows = {m: {"model": m, "inputTokens": 0, "outputTokens": 0, "inferences": 0} for m in models}
    for chunk in _chunks(queries, 450):
        res = _cw.get_metric_data(MetricDataQueries=chunk, StartTime=start, EndTime=end)
        for r in res["MetricDataResults"]:
            model, key = idmap[r["Id"]]
            rows[model][key] = int(sum(r.get("Values", [])))
    table = sorted(rows.values(), key=lambda r: r["inputTokens"] + r["outputTokens"], reverse=True)
    totals = {"inputTokens": sum(r["inputTokens"] for r in table),
              "outputTokens": sum(r["outputTokens"] for r in table),
              "inferences": sum(r["inferences"] for r in table)}
    return {"hours": hours, "namespace": _MANTLE_NS, "models": table, "totals": totals}


# --------------------------------------------------------------------------- request models
class AskReq(BaseModel):
    question: str = ""
    model: str = ""
    system_prompt: str | None = None
    conv: str | None = None


# --------------------------------------------------------------------------- routes
@router.get("/health")
def health():
    return {"ok": True, "module": "agentcore-gateway-inference", "host": "eks-fargate",
            "streaming": True}


@router.get("/models")
def models(authorization: str = Header(default="")):
    _verify_jwt(authorization)
    try:
        return _list_models()
    except Exception as e:  # noqa: BLE001
        print("models error:", repr(e))
        raise HTTPException(status_code=502, detail="falha ao listar modelos") from e


@router.get("/mantle/metrics")
def mantle_metrics(request: Request, authorization: str = Header(default="")):
    _verify_jwt(authorization)
    try:
        hours = int(request.query_params.get("hours", "24"))
    except (ValueError, TypeError):
        hours = 24
    try:
        return _mantle_metrics(max(1, min(hours, 168)))
    except Exception as e:  # noqa: BLE001
        print("mantle metrics error:", repr(e))
        raise HTTPException(status_code=502, detail="falha ao ler métricas") from e


@router.post("/ask")
def ask(req: AskReq, authorization: str = Header(default="")):
    """Resposta COMPLETA (JSON). Usada pela Evaluation (compara N modelos + judge)."""
    sub = _verify_jwt(authorization)
    q = (req.question or "").strip()
    if not q:
        return JSONResponse(status_code=400, content={"error": "pergunta vazia"})
    model_id = (req.model or DEFAULT_MODEL).strip()
    ctx_tok = context.attach(baggage.set_baggage("session.id", _session_id(sub, req.conv)))
    try:
        agent = _build_agent(model_id, (req.system_prompt or "").strip())
        result = agent(q)
        answer = _clean(str(result))
        return {"result": {"answer": answer, "model": model_id,
                           "debug": _debug_from(result, model_id)}}
    except Exception as e:  # noqa: BLE001
        print("ask error:", repr(e))
        return JSONResponse(status_code=502, content={"error": "falha ao processar"})
    finally:
        context.detach(ctx_tok)


@router.post("/ask/stream")
async def ask_stream(req: AskReq, authorization: str = Header(default="")):
    """STREAMING SSE token-a-token. Usado pelo chat Inference no portal.

    Emite linhas SSE:
      data: {"type":"delta","text":"..."}      (a cada chunk de texto)
      data: {"type":"done","model":..,"debug":..}
      data: {"type":"error","error":".."}
    """
    sub = _verify_jwt(authorization)
    q = (req.question or "").strip()
    model_id = (req.model or DEFAULT_MODEL).strip()
    system = (req.system_prompt or "").strip()
    session_id = _session_id(sub, req.conv)

    async def gen():
        if not q:
            yield _sse({"type": "error", "error": "pergunta vazia"})
            return
        ctx_tok = context.attach(baggage.set_baggage("session.id", session_id))
        final = None
        try:
            agent = _build_agent(model_id, system)
            async for event in agent.stream_async(q):
                if isinstance(event, dict):
                    if "data" in event and event["data"]:
                        yield _sse({"type": "delta", "text": event["data"]})
                    if "result" in event and event["result"] is not None:
                        final = event["result"]
            debug = _debug_from(final, model_id) if final is not None else {"model": model_id}
            yield _sse({"type": "done", "model": model_id, "debug": debug})
        except Exception as e:  # noqa: BLE001
            print("ask/stream error:", repr(e))
            yield _sse({"type": "error", "error": "falha ao processar"})
        finally:
            context.detach(ctx_tok)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


def _sse(obj):
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


# Monta as rotas na raiz e sob o prefixo que o CloudFront encaminha (/agentcore/api/*).
app.include_router(router)
app.include_router(router, prefix="/agentcore/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
