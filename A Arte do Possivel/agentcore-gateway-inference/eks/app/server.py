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
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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
_agc = boto3.client("bedrock-agentcore-control", region_name=REGION)

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
    # Guardrail nativo do Bedrock (opcional). Vazio = desativado.
    "guardrail_id": os.environ.get("GUARDRAIL_ID") or _ssm_get("guardrail-id"),
    "guardrail_version": os.environ.get("GUARDRAIL_VERSION") or _ssm_get("guardrail-version", "DRAFT"),
    # Gateway id (control-plane) p/ o BYOK (menu Keys): (re)criar targets de provider.
    "gateway_id": os.environ.get("GATEWAY_ID") or _ssm_get("gateway-id"),
}

# Cliente do Bedrock só para o Guardrail (ApplyGuardrail). A inferência em si NÃO usa
# Bedrock direto — passa pelo AgentCore Gateway. O Guardrail é o serviço NATIVO do Bedrock,
# aplicado como uma verificação independente sobre o texto (entrada e saída).
_bedrock_rt = boto3.client("bedrock-runtime", region_name=REGION)
_bedrock = boto3.client("bedrock", region_name=REGION)  # control-plane (list guardrail versions)

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


# Resolucao dinamica da versao do Guardrail (cache curto p/ nao chamar a cada request).
# guardrail-version aceita: um numero ("2"), "DRAFT", ou "LATEST" (resolve a maior versao
# publicada automaticamente). Mudar no SSM entra em vigor em ~TTL, sem redeploy.
_GVER = {"resolved": None, "ts": 0.0}
_GVER_TTL = 120


def _latest_guardrail_version():
    try:
        vers = []
        for g in _bedrock.list_guardrails(guardrailIdentifier=_CFG["guardrail_id"]).get("guardrails", []):
            v = str(g.get("version") or "")
            if v.isdigit():
                vers.append(int(v))
        return str(max(vers)) if vers else "DRAFT"
    except Exception as e:  # noqa: BLE001
        print("latest guardrail version error:", repr(e))
        return "DRAFT"


def _guardrail_version():
    now = time.time()
    if _GVER["resolved"] and (now - _GVER["ts"]) < _GVER_TTL:
        return _GVER["resolved"]
    raw = (os.environ.get("GUARDRAIL_VERSION") or _ssm_get("guardrail-version", "DRAFT")).strip()
    resolved = _latest_guardrail_version() if raw.upper() == "LATEST" else raw
    _GVER.update(resolved=resolved, ts=now)
    return resolved


def _guardrail(text, source):
    """Aplica o Guardrail NATIVO do Bedrock (ApplyGuardrail) ao texto, independente do
    Gateway. `source` é "INPUT" (pergunta) ou "OUTPUT" (resposta). Retorna
    (blocked: bool, message: str) — message é o texto de bloqueio/mascarado do Guardrail.
    No-op se o Guardrail não estiver configurado."""
    gid = _CFG.get("guardrail_id")
    if not gid or not (text or "").strip():
        return (False, "")
    try:
        resp = _bedrock_rt.apply_guardrail(
            guardrailIdentifier=gid,
            guardrailVersion=_guardrail_version(),
            source=source,
            content=[{"text": {"text": text}}],
        )
        if resp.get("action") == "GUARDRAIL_INTERVENED":
            outs = resp.get("outputs") or []
            msg = (outs[0].get("text") if outs else "") or \
                "Não posso ajudar com esse conteúdo (bloqueado pela política de uso)."
            return (True, msg)
    except Exception as e:  # noqa: BLE001 — falha do guardrail não deve derrubar a inferência
        print("guardrail error:", repr(e))
    return (False, "")


# --------------------------------------------------------------------------- model routing
# Mesmo roteamento determinístico do runtime agent.py: bedrock-mantle expõe cada modelo por
# UMA das 3 APIs OpenAI/Anthropic-compatíveis.
def _make_model(model_id, token):
    """Retorna (model, route) — route descreve exatamente o que o EKS envia ao Gateway:
    qual API/path, endpoint, target e parametros."""
    short = model_id.rsplit("/", 1)[-1]
    provider = short.split(".", 1)[0]
    target = model_id.split("/", 1)[0] if "/" in model_id else ""
    base = _CFG["base_url"]
    if provider == "anthropic":
        from strands.models.anthropic import AnthropicModel
        anth_base = re.sub(r"/v1/?$", "", base)
        route = {"api": "messages", "provider_class": "AnthropicModel",
                 "base_url": anth_base, "path": "/v1/messages", "target": target,
                 "max_tokens": 2048, "auth": "Bearer ****(m2m)"}
        return AnthropicModel(client_args={"base_url": anth_base, "auth_token": token},
                              model_id=model_id, max_tokens=2048), route
    if provider == "openai" and ("gpt-5" in short or "gpt-oss" in short) and "safeguard" not in short:
        from strands.models.openai_responses import OpenAIResponsesModel
        route = {"api": "responses", "provider_class": "OpenAIResponsesModel",
                 "base_url": base, "path": "/v1/responses", "target": target,
                 "auth": "Bearer ****(m2m)"}
        return OpenAIResponsesModel(client_args={"base_url": base, "api_key": token},
                                    model_id=model_id), route
    from strands.models.openai import OpenAIModel
    route = {"api": "chat", "provider_class": "OpenAIModel",
             "base_url": base, "path": "/v1/chat/completions", "target": target,
             "auth": "Bearer ****(m2m)"}
    return OpenAIModel(client_args={"base_url": base, "api_key": token}, model_id=model_id), route


def _history_to_messages(history):
    """Converte o historico [{role,text}] do FE para o formato de mensagens do Strands
    (Bedrock Converse). Ignora entradas invalidas. É assim que o chat multi-turno tem
    MEMORIA: semeamos o Agent com os turnos anteriores da conversa."""
    msgs = []
    for h in (history or []):
        if not isinstance(h, dict):
            continue
        role = h.get("role")
        text = (h.get("text") or "").strip()
        if role in ("user", "assistant") and text:
            msgs.append({"role": role, "content": [{"text": text}]})
    return msgs


def _build_agent(model_id, system, history=None):
    token = _m2m_token()
    model, route = _make_model(model_id, token)
    seeded = _history_to_messages(history)
    agent = Agent(model=model, system_prompt=system or _SYSTEM_DEFAULT,
                  messages=seeded, callback_handler=None)
    return agent, route, seeded


def _trunc(s, n=600):
    s = s or ""
    return s if len(s) <= n else s[:n] + f"…(+{len(s) - n} chars)"


def _req_debug(route, system, seeded, question, model_id):
    """O que o EKS ENVIA ao Gateway: rota + payload de mensagens (conteudo real, truncado)."""
    msgs = []
    if (system or "").strip():
        msgs.append({"role": "system", "text": _trunc(system)})
    for m in (seeded or []):
        try:
            txt = m["content"][0].get("text", "")
        except Exception:  # noqa: BLE001
            txt = ""
        msgs.append({"role": m.get("role"), "text": _trunc(txt)})
    msgs.append({"role": "user", "text": _trunc(question)})
    return {
        "endpoint": f"{route.get('base_url', '')}{route.get('path', '')}",
        "api": route.get("api"),
        "provider_class": route.get("provider_class"),
        "target": route.get("target") or "(catálogo bedrock-mantle)",
        "model": model_id,
        "auth": route.get("auth"),
        "max_tokens": route.get("max_tokens"),
        "messages": msgs,
        "messages_count": len(msgs),
    }


def _debug_from(result, model_id, route=None, req=None, wall_ms=None):
    m = getattr(result, "metrics", None)
    usage = dict(getattr(m, "accumulated_usage", {}) or {})
    latency = (getattr(m, "accumulated_metrics", {}) or {}).get("latencyMs", 0)
    if not latency and wall_ms:
        latency = wall_ms
    answer = ""
    try:
        answer = str(result)
    except Exception:  # noqa: BLE001
        pass
    dbg = {
        "model": model_id,
        "gateway": (_CFG["base_url"] or "").split("//")[-1].split("/")[0],
        "tokens": {"input": int(usage.get("inputTokens", 0) or 0),
                   "output": int(usage.get("outputTokens", 0) or 0),
                   "total": int(usage.get("totalTokens", 0) or 0)},
        "latency_ms": round(float(latency or 0), 1),
    }
    if route is not None:
        dbg["route"] = route
    if req is not None:
        dbg["request"] = req
    # O que o Gateway RESPONDE ao EKS (metadados da resposta).
    dbg["response"] = {
        "status": "200 OK",
        "model": model_id,
        "stop_reason": getattr(result, "stop_reason", None),
        "output_chars": len(answer or ""),
        "tokens": dbg["tokens"],
        "latency_ms": dbg["latency_ms"],
    }
    return dbg


# --------------------------------------------------------------------------- auth (Cognito)
_JWK = {"client": None}


def _jwk_client():
    if _JWK["client"] is None:
        from jwt import PyJWKClient
        url = f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}/.well-known/jwks.json"
        _JWK["client"] = PyJWKClient(url)
    return _JWK["client"]


def _decode(authorization):
    """Valida o access/id token do Cognito do portal e retorna os claims ({} se auth off)."""
    if not REQUIRE_AUTH:
        return {}
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
        return claims
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="invalid token") from e


def _verify_jwt(authorization):
    """Valida o token e retorna o `sub` (ou '' se auth off)."""
    return _decode(authorization).get("sub", "")


def _require_admin(authorization):
    """Exige o grupo Cognito 'admin' para acoes administrativas (ex.: Keys). Se o token
    nao trouxer 'cognito:groups' (pools que nao anexam grupos), falha-aberto — o menu ja e
    admin-only no frontend e o JWT e validado."""
    claims = _decode(authorization)
    if not REQUIRE_AUTH:
        return
    groups = claims.get("cognito:groups") or []
    if isinstance(groups, str):
        groups = [groups]
    if groups and "admin" not in groups:
        raise HTTPException(status_code=403, detail="admin only")


def _session_id(sub, conv):
    return hashlib.sha256(f"gwinf:{sub}:{conv or ''}".encode()).hexdigest()


# --------------------------------------------------------------------------- models / mantle
def _list_models():
    token = _m2m_token()
    req = urllib.request.Request(_CFG["base_url"].rstrip("/") + "/models",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 — base URL do Gateway (SSM)
        data = json.loads(r.read())
    ids = [m["id"] for m in data.get("data", [])]
    grouped = {}
    for mid in ids:
        short = mid.rsplit("/", 1)[-1]
        grouped.setdefault(short.split(".", 1)[0], []).append(mid)
    # BYOK (menu Keys): mescla os modelos dos providers configurados (ex.: gemini/*), que
    # NAO aparecem no /models do Gateway (catalogo bedrock-mantle) mas existem via target.
    for prov, rec in _all_key_records().items():
        for mid in (rec.get("models") or []):
            grouped.setdefault(prov, [])
            if mid not in grouped[prov]:
                grouped[prov].append(mid)
            if mid not in ids:
                ids.append(mid)
    ids = sorted(set(ids))
    for k in grouped:
        grouped[k] = sorted(set(grouped[k]))
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


# --------------------------------------------------------------------------- Keys (BYOK)
# Chaves diretas de provider (OpenAI/Gemini) via AgentCore Identity + Gateway. "Direto" =
# ainda passa pelo Gateway, mas por um target CUSTOM que autentica com a chave do cliente
# (guardada no AgentCore Identity, modo API_KEY) em vez do conector zero-config bedrock-mantle.
# Fluxo ao salvar: valida a chave no provider, testa os modelos, guarda a chave como API Key
# Credential Provider, (re)cria o target do Gateway e persiste a lista de modelos que
# funcionaram (no SSM, SEM a chave) para os pickers mostrarem — ex.: Gemini.
PROVIDERS = {
    # Nomes de target/cred proprios do modulo (gwinf-*) para NAO colidir nem clobberar os
    # recursos compartilhados do inference-demo (gemini-direct-key / target "gemini").
    "openai": {
        "target": "gwinf-openai",
        "endpoint": "https://api.openai.com/v1",
        "models_url": "https://api.openai.com/v1/models",
        "cred": "gwinf-openai-key",
        "op_path": "/v1/chat/completions",
        "provider_path": "/chat/completions",
        "model_patterns": [{"model": "gpt-*"}, {"model": "o1*"}, {"model": "o3*"},
                           {"model": "o4*"}, {"model": "chatgpt-*"}],
    },
    "gemini": {
        "target": "gwinf-gemini",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models_url": "https://generativelanguage.googleapis.com/v1beta/openai/models",
        "cred": "gwinf-gemini-key",
        "op_path": "/v1/chat/completions",
        "provider_path": "/chat/completions",
        "model_patterns": [{"model": "gemini-*"}],
    },
}
_OPENAI_SKIP = ("audio", "realtime", "transcribe", "tts", "image", "embedding",
                "moderation", "search", "instruct", "dall-e", "whisper", "codex")
_MAX_TEST_MODELS = 16


def _key_param(provider):
    return f"{_SSM_PREFIX}/keys-{provider}"


def _get_key_record(provider):
    try:
        v = _ssm.get_parameter(Name=_key_param(provider))["Parameter"]["Value"]
        return json.loads(v)
    except Exception:  # noqa: BLE001
        return None


def _all_key_records():
    out = {}
    for p in PROVIDERS:
        rec = _get_key_record(p)
        if rec:
            out[p] = rec
    return out


def _http_json(method, url, key=None, body=None, timeout=25):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — endpoint de provider fixo
        return r.status, json.loads(r.read() or b"{}")


def _provider_models(cfg, key):
    try:
        _, data = _http_json("GET", cfg["models_url"], key=key, timeout=20)
    except urllib.error.HTTPError as e:  # inclui o corpo do erro p/ diagnostico
        detail = (e.read() or b"")[:300].decode("utf-8", "ignore")
        raise RuntimeError(f"{e.code}: {detail}") from e
    ids = []
    for m in data.get("data", []):
        mid = (m.get("id") or "").split("/")[-1]  # gemini retorna "models/gemini-.."
        if mid:
            ids.append(mid)
    return ids


def _is_chat_candidate(provider, mid):
    if provider == "gemini":
        return mid.startswith("gemini-") and "embedding" not in mid
    low = mid.lower()
    if any(s in low for s in _OPENAI_SKIP):
        return False
    return low.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-"))


def _test_model(cfg, key, mid):
    """Chat completion minimo p/ confirmar que a chave usa o modelo."""
    url = f"{cfg['endpoint']}/chat/completions"
    base = {"model": mid, "messages": [{"role": "user", "content": "ping"}]}
    for tok_field in ("max_tokens", "max_completion_tokens"):
        try:
            st, _ = _http_json("POST", url, key=key, body={**base, tok_field: 1}, timeout=25)
            if st == 200:
                return (mid, True, "")
        except urllib.error.HTTPError as e:  # noqa: PERF203
            txt = (e.read() or b"").decode(errors="ignore")[:120]
            if e.code == 400 and "max_tokens" in txt and tok_field == "max_tokens":
                continue
            return (mid, False, f"{e.code}: {txt}")
        except Exception as e:  # noqa: BLE001
            return (mid, False, str(e)[:120])
    return (mid, False, "unsupported token parameter")


def _ensure_cred_provider(cfg, key):
    name = cfg["cred"]
    try:
        _agc.delete_api_key_credential_provider(name=name)
        time.sleep(2)
    except Exception:  # noqa: BLE001
        pass
    return _agc.create_api_key_credential_provider(name=name, apiKey=key)["credentialProviderArn"]


def _ensure_target(cfg, provider_arn):
    gid = _CFG["gateway_id"]
    target = cfg["target"]
    try:
        for t in _agc.list_gateway_targets(gatewayIdentifier=gid).get("items", []):
            if t.get("name") == target:
                _agc.delete_gateway_target(gatewayIdentifier=gid, targetId=t["targetId"])
                time.sleep(4)
    except Exception:  # noqa: BLE001
        pass
    target_config = {"inference": {"provider": {
        "endpoint": cfg["endpoint"],
        "operations": [{"path": cfg["op_path"], "providerPath": cfg["provider_path"],
                        "models": cfg["model_patterns"]}],
    }}}
    cred_configs = [{
        "credentialProviderType": "API_KEY",
        "credentialProvider": {"apiKeyCredentialProvider": {
            "providerArn": provider_arn,
            "credentialLocation": "HEADER",
            "credentialParameterName": "Authorization",
            "credentialPrefix": "Bearer",
        }},
    }]
    return _agc.create_gateway_target(gatewayIdentifier=gid, name=target,
                                      targetConfiguration=target_config,
                                      credentialProviderConfigurations=cred_configs)


def _save_key(provider, key):
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return 400, {"error": "provider deve ser 'openai' ou 'gemini'"}
    if not key:
        return 400, {"error": "apiKey obrigatoria"}
    if not _CFG.get("gateway_id"):
        return 500, {"error": "gateway nao configurado (SSM gateway-id)"}
    try:
        all_ids = _provider_models(cfg, key)
    except Exception as exc:  # noqa: BLE001
        return 400, {"error": f"chave rejeitada ou listagem falhou: {str(exc)[:200]}"}
    candidates = [m for m in all_ids if _is_chat_candidate(provider, m)][:_MAX_TEST_MODELS]
    tested, working = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for mid, ok, err in ex.map(lambda m: _test_model(cfg, key, m), candidates):
            tested.append({"model": mid, "ok": ok, "error": err})
            if ok:
                working.append(f"{cfg['target']}/{mid}")
    if not working:
        return 400, {"error": "a chave nao conseguiu usar nenhum modelo", "tested": tested}
    try:
        arn = _ensure_cred_provider(cfg, key)
        tgt = _ensure_target(cfg, arn)
    except Exception as exc:  # noqa: BLE001
        return 502, {"error": f"testou OK, mas o target do Gateway falhou: {str(exc)[:250]}"}
    rec = {"provider": provider, "target": cfg["target"], "models": working,
           "updatedAt": datetime.now(timezone.utc).isoformat(),
           "targetStatus": tgt.get("status")}
    try:
        _ssm.put_parameter(Name=_key_param(provider), Type="String", Overwrite=True,
                           Value=json.dumps(rec))
    except Exception as exc:  # noqa: BLE001
        print("save key record error:", repr(exc))
    return 200, {"provider": provider, "models": working, "tested": tested,
                 "targetStatus": tgt.get("status")}


def _list_keys():
    out = []
    for provider in PROVIDERS:
        rec = _get_key_record(provider)
        if rec:
            out.append({"provider": provider, "configured": True,
                        "models": rec.get("models", []), "updatedAt": rec.get("updatedAt"),
                        "targetStatus": rec.get("targetStatus")})
        else:
            out.append({"provider": provider, "configured": False, "models": []})
    return {"providers": out}


def _delete_key(provider):
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return 400, {"error": "provider desconhecido"}
    gid = _CFG.get("gateway_id")
    try:
        for t in _agc.list_gateway_targets(gatewayIdentifier=gid).get("items", []):
            if t.get("name") == cfg["target"]:
                _agc.delete_gateway_target(gatewayIdentifier=gid, targetId=t["targetId"])
    except Exception:  # noqa: BLE001
        pass
    try:
        _agc.delete_api_key_credential_provider(name=cfg["cred"])
    except Exception:  # noqa: BLE001
        pass
    try:
        _ssm.delete_parameter(Name=_key_param(provider))
    except Exception:  # noqa: BLE001
        pass
    return 200, {"provider": provider, "removed": True}


# --------------------------------------------------------------------------- request models
class AskReq(BaseModel):
    question: str = ""
    model: str = ""
    system_prompt: str | None = None
    conv: str | None = None
    history: list | None = None


class KeyReq(BaseModel):
    provider: str = ""
    apiKey: str = ""


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


@router.get("/keys")
def keys_list(authorization: str = Header(default="")):
    _verify_jwt(authorization)
    return _list_keys()


@router.post("/keys")
def keys_save(req: KeyReq, authorization: str = Header(default="")):
    """BYOK: registra a chave do provider (openai/gemini), (re)cria o target no Gateway e
    persiste os modelos testados. Restrito ao grupo admin."""
    _require_admin(authorization)
    status, body = _save_key((req.provider or "").strip().lower(), (req.apiKey or "").strip())
    return JSONResponse(status_code=status, content=body)


@router.delete("/keys/{provider}")
def keys_delete(provider: str, authorization: str = Header(default="")):
    _require_admin(authorization)
    status, body = _delete_key(provider.strip().lower())
    return JSONResponse(status_code=status, content=body)


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
        blocked, gmsg = _guardrail(q, "INPUT")
        if blocked:
            return {"result": {"answer": gmsg, "model": model_id,
                               "debug": {"model": model_id,
                                         "guardrail": {"blocked": True, "stage": "input"}}}}
        system = (req.system_prompt or "").strip()
        agent, route, seeded = _build_agent(model_id, system, req.history)
        _t0 = time.time()
        result = agent(q)
        _wall = round((time.time() - _t0) * 1000, 1)
        answer = _clean(str(result))
        debug = _debug_from(result, model_id, route,
                            _req_debug(route, system, seeded, q, model_id), _wall)
        oblocked, omsg = _guardrail(answer, "OUTPUT")
        if oblocked:
            answer = omsg
        debug["guardrail"] = {"blocked": oblocked, "stage": "output" if oblocked else "pass"}
        return {"result": {"answer": answer, "model": model_id, "debug": debug}}
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
        acc = []
        try:
            # Guardrail de ENTRADA: bloqueia antes de gastar qualquer token do modelo.
            blocked, gmsg = _guardrail(q, "INPUT")
            if blocked:
                yield _sse({"type": "delta", "text": gmsg})
                yield _sse({"type": "done", "model": model_id,
                            "debug": {"model": model_id,
                                      "guardrail": {"blocked": True, "stage": "input"}}})
                return
            agent, route, seeded = _build_agent(model_id, system, req.history)
            req_dbg = _req_debug(route, system, seeded, q, model_id)
            _t0 = time.time()
            async for event in agent.stream_async(q):
                if isinstance(event, dict):
                    if "data" in event and event["data"]:
                        acc.append(event["data"])
                        yield _sse({"type": "delta", "text": event["data"]})
                    if "result" in event and event["result"] is not None:
                        final = event["result"]
            _wall = round((time.time() - _t0) * 1000, 1)
            debug = (_debug_from(final, model_id, route, req_dbg, _wall) if final is not None
                     else {"model": model_id, "route": route, "request": req_dbg})
            # Guardrail de SAÍDA: avalia o texto acumulado; se intervir, o FE substitui.
            oblocked, omsg = _guardrail("".join(acc), "OUTPUT")
            debug["guardrail"] = {"blocked": oblocked, "stage": "output" if oblocked else "pass"}
            if oblocked:
                debug["guardrail"]["message"] = omsg
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
