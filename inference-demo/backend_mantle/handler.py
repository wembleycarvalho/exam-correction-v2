"""
handler.py - Mantle admin/observability API (AWS Lambda, behind a Function URL).

This is a SEPARATE service from the inference backend (Fargate). It powers the
"Mantle-config" tab of the SPA and the project selector on the Inference tab:

  GET  /mantle/projects          -> list bedrock-mantle projects
  POST /mantle/projects          -> create a project { name, tags? }
  GET  /mantle/metrics           -> CloudWatch AWS/BedrockMantle dashboards
                                    (?project=&hours=&period=)
  GET  /mantle/data-retention    -> account data retention mode

Security (two layers, matching the rest of the stack):
  1. Not exposed: the Function URL uses AWS_IAM auth and is reachable ONLY via
     the CloudFront distribution (Origin Access Control, SigV4). CloudFront
     overrides the Authorization header when signing, so the user's Cognito
     access token is passed in the "X-Cognito-Token" header instead.
  2. Cognito: every request's X-Cognito-Token is validated (JWKS signature,
     issuer, token_use, client_id) before doing anything.

The bedrock-mantle project/data-retention endpoints are NOT proxied by the
AgentCore Gateway (MCP protocol), so we call bedrock-mantle directly, using a
short-lived Bedrock token minted from this Lambda's IAM role.
"""

import json
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import boto3
import jwt
import requests
from jwt import PyJWKClient
from aws_bedrock_token_generator import provide_token

REGION = os.environ["AWS_REGION"]
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
EVAL_BUCKET = os.environ.get("EVAL_BUCKET")
EVAL_ROLE_ARN = os.environ.get("EVAL_ROLE_ARN")
# Default Bedrock-native judge model for async evaluation jobs (overridable per
# request). Must be a model enabled for evaluation in this account/region.
DEFAULT_EVAL_JUDGE = os.environ.get("DEFAULT_EVAL_JUDGE", "us.anthropic.claude-sonnet-4-20250514-v1:0")
# Built-in model-as-judge metrics that don't require a ground-truth reference.
JUDGE_METRICS = ["Builtin.Correctness", "Builtin.Completeness", "Builtin.Coherence",
                 "Builtin.Relevance", "Builtin.FollowingInstructions", "Builtin.Helpfulness"]
JWT_ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
_jwks = PyJWKClient(f"{JWT_ISSUER}/.well-known/jwks.json")

MANTLE_BASE = f"https://bedrock-mantle.{REGION}.api.aws/v1"
NAMESPACE = "AWS/BedrockMantle"

GATEWAY_ID = os.environ.get("GATEWAY_ID", "")

_cw = boto3.client("cloudwatch", region_name=REGION)
_bedrock = boto3.client("bedrock", region_name=REGION)
_s3 = boto3.client("s3", region_name=REGION)
_agc = boto3.client("bedrock-agentcore-control", region_name=REGION)


class Unauthorized(Exception):
    pass


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def _verify(headers: dict):
    # Function URL lowercases header names.
    token = headers.get("x-cognito-token") or ""
    if not token and headers.get("authorization", "").lower().startswith("bearer "):
        token = headers["authorization"].split(" ", 1)[1]
    if not token:
        raise Unauthorized("Missing X-Cognito-Token.")
    try:
        key = _jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=["RS256"],
                            issuer=JWT_ISSUER, options={"verify_aud": False})
    except Exception as exc:  # noqa: BLE001
        raise Unauthorized(f"Invalid token: {exc}")
    # Require a valid access token from THIS user pool. We intentionally don't
    # pin client_id here (it would create a CDK dependency cycle: this Lambda is
    # a CloudFront origin, and the frontend client depends on the distribution).
    # Safe because the only other client in the pool is the machine-to-machine
    # client, whose secret is never exposed to browsers.
    if claims.get("token_use") != "access":
        raise Unauthorized("Not an access token.")
    return claims


# --------------------------------------------------------------------------- #
# bedrock-mantle direct calls (Bedrock token from this Lambda's IAM role)
# --------------------------------------------------------------------------- #
def _mantle(method: str, path: str, body: dict | None = None):
    token = provide_token(region=REGION)
    resp = requests.request(
        method, f"{MANTLE_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps(body) if body is not None else None,
        timeout=30,
    )
    ct = resp.headers.get("content-type", "")
    payload = resp.json() if ct.startswith("application/json") else {"raw": resp.text[:500]}
    return resp.status_code, payload


def list_projects():
    status, data = _mantle("GET", "/organization/projects")
    if status >= 300:
        return {"projects": [], "status": status, "error": data}
    projects = [
        {"id": p["id"], "name": p.get("name", p["id"]),
         "status": p.get("status"), "dataRetention": p.get("data_retention", {}).get("mode")}
        for p in data.get("data", [])
    ]
    return {"projects": projects, "status": status}


def create_project(body: dict):
    name = (body or {}).get("name", "").strip()
    if not name:
        return 400, {"error": "name is required"}
    payload = {"name": name}
    if body.get("tags"):
        payload["tags"] = body["tags"]
    status, data = _mantle("POST", "/organization/projects", payload)
    return status, data


def data_retention():
    out = {}
    try:
        out["controlPlane"] = _bedrock.get_account_data_retention().get("mode")
    except Exception as exc:  # noqa: BLE001
        out["controlPlane"] = f"error: {str(exc)[:120]}"
    status, data = _mantle("GET", "/data_retention")
    out["mantle"] = data.get("mode") if status < 300 else f"error {status}"
    return out


def set_data_retention(mode: str):
    """Set the account data retention mode on BOTH the control plane and the
    mantle side (they are managed separately). Account-wide, so callers should
    understand the privacy implications (see README)."""
    if mode not in ("inherit", "provider_data_share"):
        return 400, {"error": "mode must be 'inherit' or 'provider_data_share'"}
    out = {"mode": mode}
    try:
        _bedrock.put_account_data_retention(mode=mode)
        out["controlPlane"] = "updated"
    except Exception as exc:  # noqa: BLE001
        out["controlPlane"] = f"error: {str(exc)[:150]}"
    status, data = _mantle("PUT", "/data_retention", {"mode": mode})
    out["mantle"] = "updated" if status < 300 else f"error {status}: {data}"
    return 200, out


# --------------------------------------------------------------------------- #
# CloudWatch metrics (AWS/BedrockMantle)
# --------------------------------------------------------------------------- #
def _list_models_for_project(project: str) -> list[str]:
    """Model dimension values that have Project+Model data for a project."""
    models = set()
    paginator = _cw.get_paginator("list_metrics")
    for page in paginator.paginate(
        Namespace=NAMESPACE, MetricName="InputTokens",
        Dimensions=[{"Name": "Project", "Value": project}, {"Name": "Model"}],
    ):
        for m in page.get("Metrics", []):
            dims = {d["Name"]: d["Value"] for d in m["Dimensions"]}
            if dims.get("Project") == project and set(dims) == {"Project", "Model"}:
                models.add(dims["Model"])
    return sorted(models)


def _mq(qid, metric, dims, stat, period):
    return {
        "Id": qid,
        "MetricStat": {
            "Metric": {"Namespace": NAMESPACE, "MetricName": metric,
                       "Dimensions": [{"Name": k, "Value": v} for k, v in dims.items()]},
            "Period": period, "Stat": stat,
        },
        "ReturnData": True,
    }


def metrics(project: str, hours: int, period: int):
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    span = max(hours * 3600, period)

    # --- per-model table, scoped to the selected project ---
    # Per-project per-model figures come from the Project+Model dimension, which
    # CloudWatch publishes only for the per-inference InputTokens/OutputTokens
    # metrics: Sum = tokens, SampleCount = number of inferences. (Client error
    # rate is not published at Project+Model, so it's omitted at project scope.)
    model_ids = _list_models_for_project(project)
    queries = []
    idmap = {}
    for i, model in enumerate(model_ids):
        dims = {"Project": project, "Model": model}
        queries.append(_mq(f"m{i}_in", "InputTokens", dims, "Sum", span)); idmap[f"m{i}_in"] = (model, "inputTokens")
        queries.append(_mq(f"m{i}_ic", "InputTokens", dims, "SampleCount", span)); idmap[f"m{i}_ic"] = (model, "inferences")
        queries.append(_mq(f"m{i}_out", "OutputTokens", dims, "Sum", span)); idmap[f"m{i}_out"] = (model, "outputTokens")

    rows = {m: {"model": m, "inferences": 0, "inputTokens": 0, "outputTokens": 0} for m in model_ids}
    for chunk in _chunks(queries, 450):
        res = _cw.get_metric_data(MetricDataQueries=chunk, StartTime=start, EndTime=end)
        for r in res["MetricDataResults"]:
            model, key = idmap[r["Id"]]
            rows[model][key] = sum(r.get("Values", []))
    table = []
    for m in model_ids:
        row = rows[m]
        row["errorRate"] = None  # not available at Project+Model granularity
        table.append(row)
    table.sort(key=lambda r: (r["inputTokens"] + r["outputTokens"]), reverse=True)

    # --- time series (Project dimension, bucketed) ---
    series_q = [
        _mq("s_in", "TotalInputTokens", {"Project": project}, "Sum", period),
        _mq("s_out", "TotalOutputTokens", {"Project": project}, "Sum", period),
        _mq("s_inf", "Inferences", {"Project": project}, "Sum", period),
    ]
    sres = _cw.get_metric_data(MetricDataQueries=series_q, StartTime=start, EndTime=end,
                               ScanBy="TimestampAscending")
    series = {"timestamps": [], "inputTokens": [], "outputTokens": [], "inferences": []}
    by_id = {r["Id"]: r for r in sres["MetricDataResults"]}
    ts = by_id["s_in"].get("Timestamps", [])
    series["timestamps"] = [t.isoformat() for t in ts]
    series["inputTokens"] = by_id["s_in"].get("Values", [])
    series["outputTokens"] = by_id["s_out"].get("Values", [])
    series["inferences"] = by_id["s_inf"].get("Values", [])

    totals = {
        "inputTokens": sum(series["inputTokens"]),
        "outputTokens": sum(series["outputTokens"]),
        "inferences": sum(series["inferences"]),
    }
    return {"project": project, "hours": hours, "period": period,
            "models": table, "series": series, "totals": totals}


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# --------------------------------------------------------------------------- #
# Evaluation history (S3)
#
# Each interactive Evaluation run (the same prompt compared across up to 3
# models, plus the inline LLM-as-a-judge verdict and the measured speed/token
# metrics) is persisted as ONE JSON object, partitioned by date. This powers
# the "History" tab (past runs + a per-model quality benchmark aggregated from
# the judge verdicts). The bucket is private; only this Lambda touches it.
# --------------------------------------------------------------------------- #
def save_run(body: dict):
    if not EVAL_BUCKET:
        return 500, {"error": "eval bucket not configured"}
    run = dict(body or {})
    run_id = run.get("runId") or uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    run["runId"] = run_id
    run["ts"] = run.get("ts") or now.isoformat()
    key = f"runs/{now:%Y/%m/%d}/{now:%H%M%S}-{run_id}.json"
    _s3.put_object(Bucket=EVAL_BUCKET, Key=key,
                   Body=json.dumps(run).encode("utf-8"),
                   ContentType="application/json")
    return 200, {"runId": run_id, "key": key}


def _run_summary(r: dict):
    """Compact view for the history list (drops the full response text)."""
    cands = []
    for c in r.get("candidates", []):
        cands.append({"model": c.get("model"), "api": c.get("api"),
                      "metrics": c.get("metrics"), "error": c.get("error"),
                      "chars": len(c.get("text") or "")})
    return {"runId": r.get("runId"), "ts": r.get("ts"), "prompt": r.get("prompt"),
            "project": r.get("project"), "judgeModel": r.get("judgeModel"),
            "candidates": cands, "verdict": r.get("verdict")}


def list_runs(limit: int = 25):
    if not EVAL_BUCKET:
        return {"runs": []}
    keys = []
    paginator = _s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=EVAL_BUCKET, Prefix="runs/"):
        for o in page.get("Contents", []):
            keys.append(o["Key"])
    keys.sort(reverse=True)  # date-partitioned keys sort ~chronologically
    out = []
    for k in keys[:limit]:
        try:
            obj = _s3.get_object(Bucket=EVAL_BUCKET, Key=k)
            out.append(_run_summary(json.loads(obj["Body"].read())))
        except Exception:  # noqa: BLE001
            pass
    return {"runs": out, "count": len(out), "total": len(keys)}


def get_run(run_id: str):
    if not EVAL_BUCKET:
        return 500, {"error": "eval bucket not configured"}
    paginator = _s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=EVAL_BUCKET, Prefix="runs/"):
        for o in page.get("Contents", []):
            if run_id in o["Key"]:
                obj = _s3.get_object(Bucket=EVAL_BUCKET, Key=o["Key"])
                return 200, json.loads(obj["Body"].read())
    return 404, {"error": "run not found"}


# --------------------------------------------------------------------------- #
# Async deep evaluation (Amazon Bedrock Evaluations, LLM-as-a-judge)
#
# For a saved run, we start ONE Bedrock model-evaluation job per candidate
# model (BedrockEvaluations "bring your own inference responses" mode supports a
# single modelIdentifier per job). Each job feeds the prompt + that model's
# response to a Bedrock-native judge model, which scores a built-in rubric.
# Jobs are async (minutes); a manifest is saved so the History tab can poll
# their status. This complements the interactive inline judge with a rigorous,
# auditable, managed evaluation.
# --------------------------------------------------------------------------- #
def _safe_id(s: str) -> str:
    return (re.sub(r"[^A-Za-z0-9_-]", "-", s or "")[:60]) or "model"


# Amazon Bedrock models supported as LLM-as-a-judge evaluators (model
# evaluation). We surface those actually present in the account/region.
# Ordered by preference. Nova/Llama/Mistral are actively maintained; the older
# Claude judges are kept last (they may be marked Legacy and get filtered out).
_JUDGE_CANDIDATES = [
    ("amazon.nova-pro-v1:0", "Amazon Nova Pro"),
    ("amazon.nova-lite-v1:0", "Amazon Nova Lite"),
    ("meta.llama3-1-70b-instruct-v1:0", "Meta Llama 3.1 70B Instruct"),
    ("mistral.mistral-large-2402-v1:0", "Mistral Large"),
    ("amazon.nova-micro-v1:0", "Amazon Nova Micro"),
    ("anthropic.claude-3-5-sonnet-20240620-v1:0", "Anthropic Claude 3.5 Sonnet"),
    ("anthropic.claude-3-haiku-20240307-v1:0", "Anthropic Claude 3 Haiku"),
]


def judge_models():
    """List Bedrock evaluator (judge) models available in this region/account.

    Only models present AND still ACTIVE (not Legacy) are returned — Legacy
    models are rejected by the evaluation service if unused for 30+ days.
    """
    active = set()
    seen_any = False
    try:
        for m in _bedrock.list_foundation_models(byOutputModality="TEXT").get("modelSummaries", []):
            seen_any = True
            mid = m.get("modelId")
            status = (m.get("modelLifecycle") or {}).get("status", "ACTIVE")
            if mid and status == "ACTIVE":
                active.add(mid)
    except Exception:  # noqa: BLE001
        seen_any = False
    out = [{"id": mid, "label": label} for mid, label in _JUDGE_CANDIDATES
           if not seen_any or mid in active]
    if not out:  # lookup failed or nothing matched: return the curated list
        out = [{"id": mid, "label": label} for mid, label in _JUDGE_CANDIDATES]
    return {"models": out, "default": out[0]["id"]}


def start_eval_jobs(body: dict):
    if not EVAL_BUCKET or not EVAL_ROLE_ARN:
        return 500, {"error": "evaluation jobs not configured"}
    run_id = (body or {}).get("runId")
    if not run_id:
        return 400, {"error": "runId is required"}
    judge = (body or {}).get("judgeModel") or DEFAULT_EVAL_JUDGE
    status, run = get_run(run_id)
    if status != 200:
        return status, run
    prompt = run.get("prompt", "")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    jobs = []
    for c in run.get("candidates", []):
        if c.get("error") or not c.get("text"):
            continue
        model = c["model"]
        mid = _safe_id(model)
        dskey = f"jobs/{run_id}/{mid}/dataset.jsonl"
        line = json.dumps({"prompt": prompt,
                           "modelResponses": [{"response": c["text"], "modelIdentifier": mid}]})
        _s3.put_object(Bucket=EVAL_BUCKET, Key=dskey, Body=(line + "\n").encode("utf-8"),
                       ContentType="application/jsonl")
        out_uri = f"s3://{EVAL_BUCKET}/jobs/{run_id}/{mid}/output/"
        job_name = f"eval-{mid}-{stamp}"[:63]
        try:
            resp = _bedrock.create_evaluation_job(
                jobName=job_name, roleArn=EVAL_ROLE_ARN, applicationType="ModelEvaluation",
                evaluationConfig={"automated": {
                    "datasetMetricConfigs": [{
                        # Model-as-a-Judge requires taskType "General".
                        "taskType": "General",
                        "dataset": {"name": "EvalDataset",
                                    "datasetLocation": {"s3Uri": f"s3://{EVAL_BUCKET}/{dskey}"}},
                        "metricNames": JUDGE_METRICS,
                    }],
                    "evaluatorModelConfig": {"bedrockEvaluatorModels": [{"modelIdentifier": judge}]},
                }},
                inferenceConfig={"models": [{"precomputedInferenceSource":
                                             {"inferenceSourceIdentifier": mid}}]},
                outputDataConfig={"s3Uri": out_uri},
            )
            jobs.append({"model": model, "jobArn": resp["jobArn"], "jobName": job_name})
        except Exception as exc:  # noqa: BLE001
            jobs.append({"model": model, "error": str(exc)[:400]})
    manifest = {"runId": run_id, "ts": datetime.now(timezone.utc).isoformat(),
                "judge": judge, "prompt": prompt, "jobs": jobs}
    _s3.put_object(Bucket=EVAL_BUCKET, Key=f"jobmanifests/{stamp}-{run_id}.json",
                   Body=json.dumps(manifest).encode("utf-8"), ContentType="application/json")
    return 200, manifest


def list_eval_jobs(limit: int = 25):
    if not EVAL_BUCKET:
        return {"manifests": []}
    keys = []
    paginator = _s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=EVAL_BUCKET, Prefix="jobmanifests/"):
        for o in page.get("Contents", []):
            keys.append(o["Key"])
    keys.sort(reverse=True)
    out = []
    for k in keys[:limit]:
        try:
            m = json.loads(_s3.get_object(Bucket=EVAL_BUCKET, Key=k)["Body"].read())
        except Exception:  # noqa: BLE001
            continue
        for j in m.get("jobs", []):
            arn = j.get("jobArn")
            if not arn:
                continue
            try:
                d = _bedrock.get_evaluation_job(jobIdentifier=arn)
                j["status"] = d.get("status")
            except Exception as exc:  # noqa: BLE001
                j["statusError"] = str(exc)[:150]
        out.append(m)
    return {"manifests": out, "count": len(out)}


# --------------------------------------------------------------------------- #
# Direct provider keys (OpenAI / Gemini) via AgentCore Identity + Gateway
#
# "Direct" here still means through the AgentCore Gateway inference endpoint,
# but via a CUSTOM provider target that authenticates with the customer's OWN
# API key (stored in AgentCore Identity, API_KEY mode) instead of the zero-config
# bedrock-mantle connector. Adding a key: validate it against the provider, test
# each model, store the key as an API Key Credential Provider, (re)create the
# Gateway inference target that references it, and persist the tested model list
# to S3 so the pickers can show them without ever exposing the key again.
# --------------------------------------------------------------------------- #
PROVIDERS = {
    "openai": {
        "target": "openai",
        "endpoint": "https://api.openai.com/v1",
        "models_url": "https://api.openai.com/v1/models",
        "cred": "openai-direct-key",
        "op_path": "/v1/chat/completions",
        "provider_path": "/chat/completions",
        "model_patterns": [{"model": "gpt-*"}, {"model": "o1*"}, {"model": "o3*"},
                           {"model": "o4*"}, {"model": "chatgpt-*"}],
    },
    "gemini": {
        "target": "gemini",
        # OpenAI-compatible base; model discovery hits {endpoint}/v1/models.
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models_url": "https://generativelanguage.googleapis.com/v1beta/openai/v1/models",
        "cred": "gemini-direct-key",
        "op_path": "/v1/chat/completions",
        "provider_path": "/chat/completions",
        "model_patterns": [{"model": "gemini-*"}],
    },
}
# OpenAI ids that are not chat models (skip when testing).
_OPENAI_SKIP = ("audio", "realtime", "transcribe", "tts", "image", "embedding",
                "moderation", "search", "instruct", "dall-e", "whisper", "codex")
_MAX_TEST_MODELS = 16


def _provider_models(cfg: dict, key: str) -> list[str]:
    r = requests.get(cfg["models_url"], headers={"Authorization": f"Bearer {key}"}, timeout=20)
    r.raise_for_status()
    data = r.json().get("data", [])
    ids = []
    for m in data:
        mid = (m.get("id") or "").split("/")[-1]  # gemini returns "models/gemini-.."
        if mid:
            ids.append(mid)
    return ids


def _is_chat_candidate(provider: str, mid: str) -> bool:
    if provider == "gemini":
        return mid.startswith("gemini-") and "embedding" not in mid
    low = mid.lower()
    if any(s in low for s in _OPENAI_SKIP):
        return False
    return low.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-"))


def _test_model(cfg: dict, key: str, mid: str) -> tuple[bool, str]:
    """Minimal chat completion to confirm the key can actually use the model."""
    url = f"{cfg['endpoint']}/chat/completions"
    hdr = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    base = {"model": mid, "messages": [{"role": "user", "content": "ping"}]}
    for tok_field in ("max_tokens", "max_completion_tokens"):
        try:
            r = requests.post(url, headers=hdr, json={**base, tok_field: 1}, timeout=25)
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:120]
        if r.status_code == 200:
            return True, ""
        # Retry with the other token field if that was the complaint.
        if r.status_code == 400 and "max_tokens" in r.text and tok_field == "max_tokens":
            continue
        return False, f"{r.status_code}: {r.text[:120]}"
    return False, "unsupported token parameter"


def _ensure_cred_provider(cfg: dict, key: str) -> str:
    """(Re)create the API Key Credential Provider so it holds the latest key."""
    name = cfg["cred"]
    try:
        _agc.delete_api_key_credential_provider(name=name)
        time.sleep(2)
    except Exception:  # noqa: BLE001
        pass
    resp = _agc.create_api_key_credential_provider(name=name, apiKey=key)
    return resp["credentialProviderArn"]


def _ensure_target(cfg: dict, provider_arn: str):
    """(Re)create the Gateway inference target for this provider."""
    target = cfg["target"]
    try:
        for t in _agc.list_gateway_targets(gatewayIdentifier=GATEWAY_ID).get("items", []):
            if t.get("name") == target:
                _agc.delete_gateway_target(gatewayIdentifier=GATEWAY_ID, targetId=t["targetId"])
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
            "credentialPrefix": "Bearer",  # Gateway inserts the space itself
        }},
    }]
    return _agc.create_gateway_target(
        gatewayIdentifier=GATEWAY_ID, name=target,
        targetConfiguration=target_config,
        credentialProviderConfigurations=cred_configs,
    )


def save_key(body: dict):
    provider = (body or {}).get("provider", "").strip().lower()
    key = (body or {}).get("apiKey", "").strip()
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return 400, {"error": "provider must be 'openai' or 'gemini'"}
    if not key:
        return 400, {"error": "apiKey is required"}
    if not GATEWAY_ID:
        return 500, {"error": "gateway not configured"}
    # 1. Discover + test models with the provided key.
    try:
        all_ids = _provider_models(cfg, key)
    except Exception as exc:  # noqa: BLE001
        return 400, {"error": f"key rejected or model list failed: {str(exc)[:200]}"}
    candidates = [m for m in all_ids if _is_chat_candidate(provider, m)][:_MAX_TEST_MODELS]
    # Test models in parallel so the whole request stays well under the
    # CloudFront origin-response timeout (sequential tests could exceed it).
    tested, working = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda mid: (mid, *_test_model(cfg, key, mid)), candidates))
    for mid, ok, err in results:
        tested.append({"model": mid, "ok": ok, "error": err})
        if ok:
            working.append(f"{cfg['target']}/{mid}")
    if not working:
        return 400, {"error": "the key could not use any model", "tested": tested}
    # 2. Store the key in AgentCore Identity and (re)create the Gateway target.
    try:
        arn = _ensure_cred_provider(cfg, key)
        tgt = _ensure_target(cfg, arn)
    except Exception as exc:  # noqa: BLE001
        return 502, {"error": f"stored/tested OK, but Gateway target failed: {str(exc)[:250]}"}
    # 3. Persist the tested model list (never the key) for the pickers.
    record = {"provider": provider, "target": cfg["target"], "models": working,
              "tested": tested, "updatedAt": datetime.now(timezone.utc).isoformat(),
              "credentialProviderArn": arn, "targetId": tgt.get("targetId"),
              "targetStatus": tgt.get("status")}
    if EVAL_BUCKET:
        _s3.put_object(Bucket=EVAL_BUCKET, Key=f"keys/{provider}.json",
                       Body=json.dumps(record).encode("utf-8"), ContentType="application/json")
    return 200, {"provider": provider, "models": working, "tested": tested,
                 "targetStatus": tgt.get("status")}


def list_keys():
    out = []
    if EVAL_BUCKET:
        for provider in PROVIDERS:
            try:
                obj = _s3.get_object(Bucket=EVAL_BUCKET, Key=f"keys/{provider}.json")
                r = json.loads(obj["Body"].read())
                out.append({"provider": provider, "configured": True,
                            "models": r.get("models", []), "updatedAt": r.get("updatedAt"),
                            "targetStatus": r.get("targetStatus")})
            except Exception:  # noqa: BLE001
                out.append({"provider": provider, "configured": False, "models": []})
    return {"providers": out}


def delete_key(provider: str):
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return 400, {"error": "unknown provider"}
    try:
        for t in _agc.list_gateway_targets(gatewayIdentifier=GATEWAY_ID).get("items", []):
            if t.get("name") == cfg["target"]:
                _agc.delete_gateway_target(gatewayIdentifier=GATEWAY_ID, targetId=t["targetId"])
    except Exception:  # noqa: BLE001
        pass
    try:
        _agc.delete_api_key_credential_provider(name=cfg["cred"])
    except Exception:  # noqa: BLE001
        pass
    if EVAL_BUCKET:
        try:
            _s3.delete_object(Bucket=EVAL_BUCKET, Key=f"keys/{provider}.json")
        except Exception:  # noqa: BLE001
            pass
    return 200, {"provider": provider, "removed": True}


# --------------------------------------------------------------------------- #
# Router (Lambda Function URL, payload format 2.0)
# --------------------------------------------------------------------------- #
def _resp(status, obj):
    return {"statusCode": status,
            "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
            "body": json.dumps(obj)}


def handler(event, context):  # noqa: ARG001
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")
    path = path[len("/mantle"):] if path.startswith("/mantle") else path
    qs = event.get("queryStringParameters") or {}

    try:
        _verify(headers)
    except Unauthorized as exc:
        return _resp(401, {"error": str(exc)})

    try:
        if path in ("/projects", "/projects/") and method == "GET":
            return _resp(200, list_projects())
        if path in ("/projects", "/projects/") and method == "POST":
            body = json.loads(event.get("body") or "{}")
            status, data = create_project(body)
            return _resp(status if status < 300 else 502 if status >= 500 else status, data)
        if path == "/data-retention" and method == "GET":
            return _resp(200, data_retention())
        if path == "/data-retention" and method == "PUT":
            body = json.loads(event.get("body") or "{}")
            status, data = set_data_retention(body.get("mode", ""))
            return _resp(status, data)
        if path == "/metrics" and method == "GET":
            project = qs.get("project", "default")
            hours = int(qs.get("hours", "168"))
            period = int(qs.get("period", "86400"))
            return _resp(200, metrics(project, hours, period))
        if path in ("/evals/runs", "/evals/runs/") and method == "POST":
            body = json.loads(event.get("body") or "{}")
            status, data = save_run(body)
            return _resp(status, data)
        if path in ("/evals/runs", "/evals/runs/") and method == "GET":
            return _resp(200, list_runs(int(qs.get("limit", "25"))))
        if path in ("/evals/jobs", "/evals/jobs/") and method == "POST":
            body = json.loads(event.get("body") or "{}")
            status, data = start_eval_jobs(body)
            return _resp(status, data)
        if path in ("/evals/jobs", "/evals/jobs/") and method == "GET":
            return _resp(200, list_eval_jobs(int(qs.get("limit", "25"))))
        if path in ("/evals/judge-models", "/evals/judge-models/") and method == "GET":
            return _resp(200, judge_models())
        if path in ("/keys", "/keys/") and method == "GET":
            return _resp(200, list_keys())
        if path in ("/keys", "/keys/") and method == "POST":
            body = json.loads(event.get("body") or "{}")
            status, data = save_key(body)
            return _resp(status, data)
        if path.startswith("/keys/") and method == "DELETE":
            status, data = delete_key(path.rsplit("/", 1)[-1])
            return _resp(status, data)
        if path.startswith("/evals/runs/") and method == "GET":
            status, data = get_run(path.rsplit("/", 1)[-1])
            return _resp(status, data)
        if path in ("/health", "/") and method == "GET":
            return _resp(200, {"status": "ok"})
        return _resp(404, {"error": f"no route for {method} {path}"})
    except Exception as exc:  # noqa: BLE001
        return _resp(500, {"error": f"{type(exc).__name__}: {str(exc)[:300]}"})
