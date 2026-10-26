"""
handler.py - websearch-demo backend: ONE Lambda, no web framework, three
routes multiplexed by path:

  GET  /api/auth/config   Public. Returns the Hosted UI settings the SPA
                           needs to build the login redirect (client id,
                           authorize/logout endpoints, scope). No secrets.

  POST /api/auth/token    Public. Proxies the PKCE authorization-code/token
                           exchange to Cognito's /oauth2/token. Done here
                           (instead of directly from the browser) because
                           Cognito's token endpoint CORS behavior for
                           cross-origin fetch/XHR is undocumented/inconsistent
                           - routing it through this same-origin backend
                           avoids depending on that.

  POST /api/search        Requires the user's access token (issued by the
                           Hosted UI login above) in the "x-user-token"
                           header - NOT Authorization, which CloudFront OAC
                           overwrites with its own SigV4 signature.
                           The token is validated against Cognito
                           (cognito-idp:GetUser - no IAM permission needed,
                           see AWS docs). If valid, the Lambda then:
                             1. Fetches an M2M OAuth token from Cognito
                                (client_credentials, separate app client,
                                secret in Secrets Manager) - cached across
                                warm invocations.
                             2. Calls the "WebSearch" tool on the Gateway via
                                MCP (JSON-RPC tools/call).
                             3. Returns the results as JSON.

Why so ("BFF" - backend for frontend) instead of the browser talking to
Cognito/Gateway directly? The Gateway's client_credentials grant requires a
client_secret, which can never be safe in browser code. So the M2M client
stays server-side. The user-facing login is a separate, secret-less client
(public, PKCE) - but even its token exchange is proxied here to sidestep
Cognito's CORS limitations for browser-initiated calls.

Expected environment variables (set by the CDK from the infra stack's
outputs):
  GATEWAY_MCP_URL             AgentCore Gateway /mcp endpoint
  WEBSEARCH_TOOL_NAME         namespaced tool name (e.g. "websearch___WebSearch")
  COGNITO_TOKEN_ENDPOINT      Cognito OAuth token endpoint URL
  COGNITO_CLIENT_ID           M2M app client id (client_credentials)
  COGNITO_CLIENT_SECRET_ARN   Secrets Manager ARN holding the M2M client_secret
  COGNITO_SCOPE               M2M OAuth scope (e.g. "websearch-gateway/invoke")
  COGNITO_LOGIN_CLIENT_ID     public app client id for user login (PKCE)
  COGNITO_AUTHORIZE_ENDPOINT  Cognito /oauth2/authorize URL
  COGNITO_LOGOUT_ENDPOINT     Cognito /logout URL
"""

import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error

import boto3

GATEWAY_MCP_URL = os.environ["GATEWAY_MCP_URL"]
WEBSEARCH_TOOL_NAME = os.environ["WEBSEARCH_TOOL_NAME"]
TOKEN_ENDPOINT = os.environ["COGNITO_TOKEN_ENDPOINT"]
CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]
CLIENT_SECRET_ARN = os.environ["COGNITO_CLIENT_SECRET_ARN"]
SCOPE = os.environ["COGNITO_SCOPE"]
LOGIN_CLIENT_ID = os.environ["COGNITO_LOGIN_CLIENT_ID"]
AUTHORIZE_ENDPOINT = os.environ["COGNITO_AUTHORIZE_ENDPOINT"]
LOGOUT_ENDPOINT = os.environ["COGNITO_LOGOUT_ENDPOINT"]

MAX_RESULTS = 5
TOKEN_TTL_SECONDS = 50 * 60  # M2M Cognito token lasts ~1h; renew with margin

_secrets = boto3.client("secretsmanager")
_cognito_idp = boto3.client("cognito-idp")

# In-memory cache for the Lambda container (survives across "warm" invocations).
_cache = {"client_secret": None, "m2m_token": None, "m2m_token_ts": 0.0}


def _http_json(url, data=None, headers=None, form=None, timeout=20):
    """Simple POST with urllib (no dependency on 'requests')."""
    headers = dict(headers or {})
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    else:
        body = json.dumps(data or {}).encode()
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"error": raw.decode("utf-8", "ignore")}


def _get_client_secret():
    if _cache["client_secret"] is None:
        resp = _secrets.get_secret_value(SecretId=CLIENT_SECRET_ARN)
        _cache["client_secret"] = resp["SecretString"]
    return _cache["client_secret"]


def _get_m2m_token():
    """OAuth token for THIS Lambda to call the Gateway (client_credentials)."""
    now = time.time()
    if _cache["m2m_token"] and (now - _cache["m2m_token_ts"]) < TOKEN_TTL_SECONDS:
        return _cache["m2m_token"]
    status, data = _http_json(
        TOKEN_ENDPOINT,
        form={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": _get_client_secret(),
            "scope": SCOPE,
        },
    )
    if status >= 300:
        raise RuntimeError(f"failed to get M2M OAuth token ({status}): {data}")
    _cache["m2m_token"] = data["access_token"]
    _cache["m2m_token_ts"] = now
    return _cache["m2m_token"]


def _require_user_token(event):
    """Validates the end user's access token (from the Hosted UI login).

    Uses cognito-idp:GetUser, which Cognito authorizes with the bearer
    access token itself - no IAM permission is evaluated for this call, so
    the Lambda's execution role needs nothing extra. Raises ValueError (be
    treated as 401 by the caller) if the token is missing or invalid.
    """
    headers = event.get("headers") or {}
    # Primary: custom header. CloudFront OAC (SIGV4_ALWAYS) overwrites the
    # Authorization header with its own signature, so the browser sends the
    # user's access token in x-user-token instead. (Lambda Function URL
    # lowercases header names.)
    token = (headers.get("x-user-token") or "").strip()
    if not token:
        # Fallback for direct invocation/testing (not via CloudFront).
        auth_header = headers.get("authorization") or headers.get("Authorization") or ""
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
    if not token:
        raise ValueError("missing user token")
    try:
        _cognito_idp.get_user(AccessToken=token)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid or expired token: {exc}") from exc


def _websearch(m2m_token, query):
    """Calls the WebSearch tool via /mcp (JSON-RPC tools/call)."""
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": WEBSEARCH_TOOL_NAME,
            "arguments": {"query": query[:200], "maxResults": MAX_RESULTS},
        },
    }
    status, data = _http_json(
        GATEWAY_MCP_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {m2m_token}",
            "Accept": "application/json, text/event-stream",
        },
    )
    if status >= 300:
        raise RuntimeError(f"MCP tools/call failed ({status}): {data}")
    result = data.get("result") or {}
    if result.get("isError"):
        raise RuntimeError(f"WebSearch returned an error: {result}")
    results = []
    for block in result.get("content", []):
        if block.get("type") == "text":
            parsed = json.loads(block.get("text", "{}"))
            results = parsed.get("results", []) or results
    return results


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def _handle_auth_config():
    return _response(200, {
        "clientId": LOGIN_CLIENT_ID,
        "authorizeEndpoint": AUTHORIZE_ENDPOINT,
        "logoutEndpoint": LOGOUT_ENDPOINT,
        # aws.cognito.signin.user.admin lets the backend validate the access
        # token via the Cognito GetUser API.
        "scope": "openid email aws.cognito.signin.user.admin",
    })


def _handle_auth_token(payload):
    """Exchanges an authorization code (+ PKCE verifier) for tokens.

    Proxied server-side so the browser never talks cross-origin to Cognito's
    /oauth2/token endpoint directly (see module docstring).
    """
    code = (payload.get("code") or "").strip()
    code_verifier = (payload.get("code_verifier") or "").strip()
    redirect_uri = (payload.get("redirect_uri") or "").strip()
    if not code or not code_verifier or not redirect_uri:
        return _response(400, {"error": "'code', 'code_verifier' and 'redirect_uri' are required"})

    status, data = _http_json(
        TOKEN_ENDPOINT,
        form={
            "grant_type": "authorization_code",
            "client_id": LOGIN_CLIENT_ID,
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        },
    )
    if status >= 300:
        return _response(status if status >= 400 else 502, {"error": data})

    return _response(200, {
        "access_token": data.get("access_token"),
        "id_token": data.get("id_token"),
        "expires_in": data.get("expires_in"),
        "token_type": data.get("token_type"),
    })


def _handle_search(event, payload):
    try:
        _require_user_token(event)
    except ValueError as exc:
        return _response(401, {"error": str(exc)})

    query = (payload.get("query") or "").strip()
    if not query:
        return _response(400, {"error": "'query' field is required"})

    try:
        m2m_token = _get_m2m_token()
        results = _websearch(m2m_token, query)
    except Exception as exc:  # noqa: BLE001
        return _response(502, {"error": str(exc)[:400]})

    return _response(200, {"query": query, "results": results})


def handler(event, context):  # noqa: ARG001 (context required by Lambda)
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method") or event.get("httpMethod") or "POST"
    path = http.get("path") or event.get("rawPath") or "/api/search"

    if method == "OPTIONS":
        return _response(204, {})

    if method == "GET" and path.rstrip("/") == "/api/auth/config":
        return _handle_auth_config()

    try:
        payload = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid body; expected JSON"})

    if method == "POST" and path.rstrip("/") == "/api/auth/token":
        return _handle_auth_token(payload)

    if method == "POST" and path.rstrip("/") == "/api/search":
        return _handle_search(event, payload)

    return _response(404, {"error": f"no route for {method} {path}"})
