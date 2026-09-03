"""AgentCore module — Gateway Inference: agente Strands no AgentCore Runtime que faz
inferencia atraves do AgentCore Gateway (target bedrock-mantle) existente.

Reusa o InferenceDemoGateway (proxy unificado de LLMs, OpenAI/Anthropic-compativel). O
agente usa o provider OpenAI do Strands apontado para o base URL do Gateway, autenticando
com um token OAuth m2m (client_credentials) mintado a partir do segredo no Secrets Manager.
Rodando no Runtime, o Strands emite spans gen_ai.* nativos -> CloudWatch GenAI Observability.

Config (SSM /gateway-inference/*): base-url, token-endpoint, client-id, scope, client-secret-arn.
O browser NUNCA fala com o Gateway nem ve o segredo; so o Runtime (via bridge Lambda).
"""
import json
import os
import time

import re

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()

REGION = os.environ.get("AWS_REGION", "us-east-1")
DEFAULT_MODEL = os.environ.get("MODEL_ID", "bedrock-inference/anthropic.claude-haiku-4-5")
_SSM_PREFIX = os.environ.get("SSM_PREFIX", "/gateway-inference")

_ssm = boto3.client("ssm", region_name=REGION)
_secrets = boto3.client("secretsmanager", region_name=REGION)

_SYSTEM_DEFAULT = (
    "You are a helpful assistant. Reply clearly and naturally in the same language as the "
    "user's question."
)


def _ssm_get(name, default=""):
    try:
        return _ssm.get_parameter(Name=f"{_SSM_PREFIX}/{name}")["Parameter"]["Value"]
    except Exception:  # noqa: BLE001
        return default


# Config do Gateway (lida 1x no cold start).
_CFG = {
    "base_url": os.environ.get("GW_BASE_URL") or _ssm_get("base-url"),
    "token_endpoint": os.environ.get("COGNITO_TOKEN_ENDPOINT") or _ssm_get("token-endpoint"),
    "client_id": os.environ.get("COGNITO_CLIENT_ID") or _ssm_get("client-id"),
    "scope": os.environ.get("COGNITO_SCOPE") or _ssm_get("scope"),
    "secret_arn": os.environ.get("CLIENT_SECRET_ARN") or _ssm_get("client-secret-arn"),
}

# Cache do token m2m (~1h de validade; renova com margem) e do segredo.
_TOK = {"secret": None, "token": None, "ts": 0.0}
_TOKEN_TTL = 50 * 60


def _client_secret():
    if _TOK["secret"] is None:
        _TOK["secret"] = _secrets.get_secret_value(SecretId=_CFG["secret_arn"])["SecretString"]
    return _TOK["secret"]


def _m2m_token(force=False):
    import urllib.parse
    import urllib.request

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
    return re.sub(r"<thinking>.*?</thinking>", "", text or "", flags=re.DOTALL | re.IGNORECASE).strip()


# bedrock-mantle expõe modelos por 3 APIs OpenAI/Anthropic-compatíveis; cada modelo aceita
# só UMA. Roteamos deterministicamente pelo id (igual ao pick_api do inference-demo):
#   anthropic.*                      -> Messages   (/v1/messages)   -> AnthropicModel
#   openai.gpt-5* / openai.gpt-oss*  -> Responses  (/v1/responses)  -> OpenAIResponsesModel
#   (exceto *safeguard*, que é chat)
#   resto                            -> Chat       (/v1/chat/...)   -> OpenAIModel
def _make_model(model_id, token):
    short = model_id.rsplit("/", 1)[-1]
    provider = short.split(".", 1)[0]
    base = _CFG["base_url"]
    if provider == "anthropic":
        from strands.models.anthropic import AnthropicModel
        # o SDK Anthropic acrescenta /v1/messages; o base NÃO pode terminar em /v1.
        anth_base = re.sub(r"/v1/?$", "", base)
        return AnthropicModel(client_args={"base_url": anth_base, "auth_token": token},
                              model_id=model_id, max_tokens=2048)
    if provider == "openai" and ("gpt-5" in short or "gpt-oss" in short) and "safeguard" not in short:
        from strands.models.openai_responses import OpenAIResponsesModel
        return OpenAIResponsesModel(client_args={"base_url": base, "api_key": token}, model_id=model_id)
    from strands.models.openai import OpenAIModel
    return OpenAIModel(client_args={"base_url": base, "api_key": token}, model_id=model_id)


@app.entrypoint
def invoke(payload):
    question = (payload.get("question") or payload.get("prompt") or "").strip()
    model_id = (payload.get("model") or DEFAULT_MODEL).strip()
    system = (payload.get("system_prompt") or "").strip() or _SYSTEM_DEFAULT
    if not question:
        return {"result": {"answer": "Faca uma pergunta.", "model": model_id}}

    token = _m2m_token()
    model = _make_model(model_id, token)
    agent = Agent(model=model, system_prompt=system, callback_handler=None)
    result = agent(question)
    answer = _clean(str(result))

    m = getattr(result, "metrics", None)
    usage = dict(getattr(m, "accumulated_usage", {}) or {})
    latency = (getattr(m, "accumulated_metrics", {}) or {}).get("latencyMs", 0)
    debug = {
        "model": model_id,
        "gateway": (_CFG["base_url"] or "").split("//")[-1].split("/")[0],
        "tokens": {"input": int(usage.get("inputTokens", 0) or 0),
                   "output": int(usage.get("outputTokens", 0) or 0),
                   "total": int(usage.get("totalTokens", 0) or 0)},
        "latency_ms": round(float(latency or 0), 1),
    }
    return {"result": {"answer": answer, "model": model_id, "debug": debug}}


if __name__ == "__main__":
    app.run()
