"""
server.py - inference-demo backend: a thin proxy between the SPA and the
AgentCore Gateway inference target.

Why does a backend exist (instead of the SPA talking directly to the Gateway)?
  The Gateway uses OAuth client_credentials on Cognito, which requires a
  client_secret. A client_secret CANNOT be kept safe in an app that runs in the
  browser (a SPA) - anyone can read the JS and extract it. So the backend holds
  the secret (Secrets Manager) and the browser only talks to THIS backend, never
  directly to Cognito/Gateway. See the README for other alternatives considered
  (and why they were dropped).

Why Fargate (and not Lambda, like the websearch-demo)? This backend does
token-by-token STREAMING over Server-Sent Events (SSE) while the LLM generates
the response. Lambda with the Python runtime has no native response-streaming
support (only Node.js/other runtimes do); a long-lived process (Fargate) behind
an Application Load Balancer streams natively.

User authentication: the SPA signs users in through the Cognito Hosted UI
(Authorization Code + PKCE) and forwards the resulting access token as a
Bearer token. This backend validates that token (signature, issuer, token_use,
client_id) against the Cognito user pool before serving the protected
endpoints. The /api/health endpoint stays open so the ALB health check works.

Deliberate simplifications relative to the original demo (gateway_inference_demo):
  - A SINGLE call API: OpenAI Chat Completions (/v1/chat/completions), which is
    the most universally supported one across the bedrock-mantle models. The
    original demo tried messages/responses/chat in a fallback chain; we removed
    that complexity here.
  - No Nova bypass via direct Converse (that is not a Gateway "target" - it is
    out of scope for this demo, which is about the inference target).
  - No detailed debug panel - only the essentials (via SSE: text delta, TTFT,
    total time, tokens).
"""

import json
import logging
import os
import re
import time

import anthropic
import boto3
import jwt
from jwt import PyJWKClient
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI, APIError, APIConnectionError, APITimeoutError, BadRequestError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("inference-demo")

REGION = os.environ["AWS_REGION"]
INFERENCE_BASE_URL = os.environ["GATEWAY_INFERENCE_BASE_URL"]
TOKEN_ENDPOINT = os.environ["COGNITO_TOKEN_ENDPOINT"]
CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]
CLIENT_SECRET_ARN = os.environ["COGNITO_CLIENT_SECRET_ARN"]
SCOPE = os.environ["COGNITO_SCOPE"]

# Used to validate the interactive user's access token (see verify_user_token).
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
APP_CLIENT_ID = os.environ["COGNITO_APP_CLIENT_ID"]
JWT_ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
_jwks_client = PyJWKClient(f"{JWT_ISSUER}/.well-known/jwks.json")

TOKEN_TTL_SECONDS = 50 * 60  # the Cognito token lasts ~1h; renew with margin
_secrets = boto3.client("secretsmanager", region_name=REGION)
_token_cache = {"client_secret": None, "token": None, "ts": 0.0}

# System instruction: reply in the same language as the user's question.
SYSTEM_PROMPT = (
    "You are a helpful assistant. Reply clearly and naturally in the same "
    "language as the user's question."
)

# --------------------------------------------------------------------------- #
# Model -> API routing map
#
# bedrock-mantle exposes models through three different OpenAI-/Anthropic-
# compatible APIs, and each model only accepts ONE of them. Instead of probing
# at runtime, we route deterministically based on the model id (format
# "<target>/<provider>.<model>", e.g. "bedrock-inference/openai.gpt-5.4").
# The mapping below was derived from testing every model exposed by the Gateway
# (see the "Model API matrix" table in the README):
#
#   - "messages"  -> Anthropic Messages API      (/v1/messages)   : anthropic.*
#   - "responses" -> OpenAI Responses API        (/v1/responses)  : openai.gpt-5*, openai.gpt-oss*
#   - "chat"      -> OpenAI Chat Completions API  (/v1/chat/...)  : everyone else (default)
# --------------------------------------------------------------------------- #
API_MESSAGES = "messages"
API_RESPONSES = "responses"
API_CHAT = "chat"

# Default API per provider (segment after "<target>/" and before the first ".").
PROVIDER_API = {
    "anthropic": API_MESSAGES,
    "openai": API_RESPONSES,
}
DEFAULT_API = API_CHAT

# Per-model overrides, matched on the id after the "<target>/" prefix. These are
# models whose API differs from their provider's default (e.g. the gpt-oss
# safeguard models use Chat Completions, unlike the rest of openai.*).
MODEL_API_OVERRIDES = {
    "openai.gpt-oss-safeguard-120b": API_CHAT,
    "openai.gpt-oss-safeguard-20b": API_CHAT,
}


def pick_api(model: str) -> str:
    """Resolve which API a model speaks from its id (deterministic map)."""
    short = model.rsplit("/", 1)[-1]  # drop the "bedrock-inference/" target prefix
    if short in MODEL_API_OVERRIDES:
        return MODEL_API_OVERRIDES[short]
    provider = short.split(".", 1)[0]
    return PROVIDER_API.get(provider, DEFAULT_API)


# The Anthropic SDK appends "/v1/messages" itself, so its base URL must NOT
# already end in "/v1" (unlike the OpenAI base URL used for responses/chat).
ANTHROPIC_BASE_URL = re.sub(r"/v1/?$", "", INFERENCE_BASE_URL)


def _anthropic_client(token: str) -> anthropic.Anthropic:
    # auth_token makes the SDK send "Authorization: Bearer <token>" (the Gateway
    # uses OAuth), instead of the default x-api-key header.
    return anthropic.Anthropic(base_url=ANTHROPIC_BASE_URL, auth_token=token)


def verify_user_token(authorization: str | None) -> dict:
    """Validate the Cognito access token sent by the SPA as a Bearer token.

    Checks the signature (via the user pool JWKS), the issuer, that it is an
    access token, and that it was issued to our frontend app client. Raises
    HTTP 401 on any failure.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=JWT_ISSUER,
            options={"verify_aud": False},  # access tokens use client_id, not aud
        )
    except Exception as exc:  # noqa: BLE001 - any decode error means unauthorized
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
    if claims.get("token_use") != "access":
        raise HTTPException(status_code=401, detail="Not an access token.")
    if claims.get("client_id") != APP_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Token issued to a different client.")
    return claims


def _get_client_secret() -> str:
    if _token_cache["client_secret"] is None:
        resp = _secrets.get_secret_value(SecretId=CLIENT_SECRET_ARN)
        _token_cache["client_secret"] = resp["SecretString"]
    return _token_cache["client_secret"]


def _get_token(force: bool = False) -> str:
    import requests  # local import to make it clear only this function uses it

    now = time.time()
    if not force and _token_cache["token"] and (now - _token_cache["ts"]) < TOKEN_TTL_SECONDS:
        return _token_cache["token"]
    resp = requests.post(
        TOKEN_ENDPOINT,
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": _get_client_secret(),
            "scope": SCOPE,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"failed to obtain OAuth token ({resp.status_code}): {resp.text}")
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["ts"] = now
    return _token_cache["token"]


def _client(token: str) -> OpenAI:
    return OpenAI(base_url=INFERENCE_BASE_URL, api_key=token)


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


app = FastAPI(title="AgentCore Gateway Inference Demo")


class ChatRequest(BaseModel):
    model: str
    message: str
    # Optional: associate the inference with a bedrock-mantle project (for cost
    # attribution / observability). Sent via the "OpenAI-Project" header.
    project_id: str | None = None
    # Optional: override the default system prompt for this request.
    system_prompt: str | None = None


@app.get("/api/health")
def health():
    # Kept unauthenticated so the ALB target-group health check succeeds.
    return {"status": "ok"}


@app.get("/api/models")
def list_models(authorization: str | None = Header(default=None)):
    verify_user_token(authorization)
    try:
        token = _get_token()
        models = _client(token).models.list()
        ids = sorted(m.id for m in models.data)
        return {"models": ids}
    except (APIError, APIConnectionError, APITimeoutError) as exc:
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}")


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest, authorization: str | None = Header(default=None)):
    """Streaming over SSE.

    bedrock-mantle exposes models through different OpenAI-compatible APIs: most
    current models (e.g. the gpt-5 family) only speak the Responses API
    (/v1/responses), while others speak Chat Completions (/v1/chat/completions).
    So we try the Responses API first and fall back to Chat Completions when the
    model rejects it - covering both without the caller needing to know which.
    """
    verify_user_token(authorization)
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message.")

    token = _get_token()
    api = pick_api(req.model)
    # Per-request system prompt (falls back to the default) and optional project
    # association (OpenAI-Project header, forwarded to the inference call).
    prompt = req.system_prompt.strip() if (req.system_prompt and req.system_prompt.strip()) else SYSTEM_PROMPT
    extra_headers = {"OpenAI-Project": req.project_id} if req.project_id else None

    # Reconstruct the exact BE -> Gateway request for the debug panel. The real
    # bearer token is included so the frontend can build a runnable cURL; the UI
    # masks it on screen and only reveals it on "copy".
    if api == API_RESPONSES:
        gw_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        if extra_headers:
            gw_headers.update(extra_headers)
        gateway_request = {
            "method": "POST", "url": f"{INFERENCE_BASE_URL}/responses",
            "headers": gw_headers,
            "body": {"model": req.model, "instructions": prompt, "input": req.message, "stream": True},
        }
    elif api == API_CHAT:
        gw_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        if extra_headers:
            gw_headers.update(extra_headers)
        gateway_request = {
            "method": "POST", "url": f"{INFERENCE_BASE_URL}/chat/completions",
            "headers": gw_headers,
            "body": {"model": req.model,
                     "messages": [{"role": "system", "content": prompt},
                                  {"role": "user", "content": req.message}],
                     "stream": True, "stream_options": {"include_usage": True}},
        }
    else:  # API_MESSAGES
        gateway_request = {
            "method": "POST", "url": f"{ANTHROPIC_BASE_URL}/v1/messages",
            "headers": {"Authorization": f"Bearer {token}",
                        "anthropic-version": "2023-06-01", "content-type": "application/json"},
            "body": {"model": req.model, "max_tokens": 2048,
                     "system": prompt, "messages": [{"role": "user", "content": req.message}]},
        }

    def gen():
        t0 = time.time()
        counters = {"ttft_ms": None, "chunks": 0, "usage": {}, "text": ""}
        yield _sse({"type": "meta", "model": req.model, "api": api})
        yield _sse({"type": "debug", "gateway_request": gateway_request})

        def delta_event(text: str):
            if not text:
                return None
            if counters["ttft_ms"] is None:
                counters["ttft_ms"] = round((time.time() - t0) * 1000, 1)
            counters["chunks"] += 1
            counters["text"] += text
            return _sse({"type": "delta", "text": text})

        def iter_responses():
            """OpenAI Responses API (/v1/responses)."""
            stream = _client(token).responses.create(
                model=req.model, instructions=prompt,
                input=req.message, stream=True, extra_headers=extra_headers,
            )
            for event in stream:
                etype = getattr(event, "type", "")
                if etype == "response.output_text.delta":
                    ev = delta_event(getattr(event, "delta", "") or "")
                    if ev:
                        yield ev
                elif etype == "response.completed":
                    u = getattr(getattr(event, "response", None), "usage", None)
                    if u:
                        counters["usage"] = {
                            "input_tokens": getattr(u, "input_tokens", None),
                            "output_tokens": getattr(u, "output_tokens", None),
                        }

        def iter_chat():
            """OpenAI Chat Completions API (/v1/chat/completions)."""
            stream = _client(token).chat.completions.create(
                model=req.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": req.message},
                ],
                stream=True,
                stream_options={"include_usage": True},
                extra_headers=extra_headers,
            )
            for chunk in stream:
                if chunk.choices:
                    ev = delta_event(chunk.choices[0].delta.content or "")
                    if ev:
                        yield ev
                if getattr(chunk, "usage", None):
                    counters["usage"] = {
                        "input_tokens": chunk.usage.prompt_tokens,
                        "output_tokens": chunk.usage.completion_tokens,
                    }

        def iter_messages():
            """Anthropic Messages API (/v1/messages)."""
            # NOTE: the OpenAI-Project header is only accepted on the OpenAI-
            # compatible paths (responses/chat). The Anthropic Messages API
            # rejects it ("openai-project header is not supported"), so project
            # attribution is not applied for Claude models.
            with _anthropic_client(token).messages.stream(
                model=req.model,
                max_tokens=2048,
                system=prompt,
                messages=[{"role": "user", "content": req.message}],
            ) as stream:
                for text in stream.text_stream:
                    ev = delta_event(text)
                    if ev:
                        yield ev
                u = getattr(stream.get_final_message(), "usage", None)
                if u:
                    counters["usage"] = {
                        "input_tokens": getattr(u, "input_tokens", None),
                        "output_tokens": getattr(u, "output_tokens", None),
                    }

        runners = {API_RESPONSES: iter_responses, API_CHAT: iter_chat, API_MESSAGES: iter_messages}
        try:
            for ev in runners[api]():
                yield ev
            total_ms = round((time.time() - t0) * 1000, 1)
            yield _sse({"type": "done", "ttft_ms": counters["ttft_ms"],
                        "total_ms": total_ms, "chunks": counters["chunks"],
                        "usage": counters["usage"],
                        # Assembled Gateway -> Backend response (for the debug panel).
                        "gateway_response": {"model": req.model, "api": api,
                                             "usage": counters["usage"], "text": counters["text"]}})
        except BadRequestError as exc:
            yield _sse({"type": "error", "message": f"model rejected the call: {str(exc)[:200]}"})
        except (APIError, APIConnectionError, APITimeoutError) as exc:
            yield _sse({"type": "error", "message": f"{type(exc).__name__}: {str(exc)[:200]}"})
        except anthropic.APIError as exc:
            yield _sse({"type": "error", "message": f"{type(exc).__name__}: {str(exc)[:200]}"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
