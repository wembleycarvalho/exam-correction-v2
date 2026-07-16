"""Métricas via CloudWatch EMF + estimativa de custo.

Helper usado pelo worker para emitir tokens/custo/latência/outcome de forma padronizada.
O formato EMF permite que o CloudWatch extraia métricas automaticamente dos logs, sem
chamadas de API adicionais (custo baixo). Complementa os traces do AgentCore Observability.
"""
import json
import os
import time
from typing import Optional

NAMESPACE = os.environ.get("METRICS_NAMESPACE", "ExamCorrection")

# Preço de REFERÊNCIA (USD por 1k tokens). Estimativa por família de modelo, baseada nas
# faixas públicas do Bedrock/Anthropic. Ajustável por env MODEL_PRICING (JSON por modelId
# exato), que tem prioridade:  MODEL_PRICING='{"<modelId>":{"in":0.003,"out":0.015}}'
_DEFAULT_PRICING: dict = {}

# Correspondência por substring do modelId (ordem importa: mais específico primeiro).
_FAMILY_PRICING = [
    ("opus", {"in": 0.015, "out": 0.075}),
    ("sonnet", {"in": 0.003, "out": 0.015}),
    ("haiku", {"in": 0.0008, "out": 0.004}),
    ("nova-premier", {"in": 0.0025, "out": 0.0125}),
    ("nova-pro", {"in": 0.0008, "out": 0.0032}),
    ("nova-lite", {"in": 0.00006, "out": 0.00024}),
    ("nova-micro", {"in": 0.000035, "out": 0.00014}),
    ("nova", {"in": 0.0008, "out": 0.0032}),
    ("mistral", {"in": 0.002, "out": 0.006}),
    ("llama", {"in": 0.0006, "out": 0.0008}),
]


def _pricing() -> dict:
    override = os.environ.get("MODEL_PRICING")
    if override:
        try:
            return {**_DEFAULT_PRICING, **json.loads(override)}
        except json.JSONDecodeError:
            pass
    return _DEFAULT_PRICING


def price_for(model: str) -> Optional[dict]:
    """Preço {in,out} por 1k tokens: env exato tem prioridade; senão, por família."""
    exact = _pricing().get(model)
    if exact:
        return exact
    m = (model or "").lower()
    for key, p in _FAMILY_PRICING:
        if key in m:
            return p
    return None


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> Optional[float]:
    """Custo estimado em USD. None se o preço do modelo for desconhecido."""
    price = price_for(model)
    if not price:
        return None
    return round((tokens_in / 1000.0) * price["in"] + (tokens_out / 1000.0) * price["out"], 6)


def cost_breakdown(model: str, tokens_in: int, tokens_out: int) -> Optional[dict]:
    """Custo estimado {in, out, total} em USD, ou None se preço desconhecido."""
    price = price_for(model)
    if not price:
        return None
    ci = round((tokens_in / 1000.0) * price["in"], 6)
    co = round((tokens_out / 1000.0) * price["out"], 6)
    return {"in": ci, "out": co, "total": round(ci + co, 6)}


def emit(dimensions: dict, metrics: dict, properties: Optional[dict] = None) -> None:
    """Emite um documento EMF no stdout (capturado pelo CloudWatch Logs)."""
    doc = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": NAMESPACE,
                    "Dimensions": [list(dimensions.keys())] if dimensions else [[]],
                    "Metrics": [{"Name": name} for name in metrics],
                }
            ],
        },
    }
    doc.update({k: str(v) for k, v in dimensions.items()})
    doc.update(metrics)
    if properties:
        doc.update(properties)
    print(json.dumps(doc, ensure_ascii=False))


def emit_model_usage(
    capability: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: float,
    outcome: str = "success",
    submission_id: Optional[str] = None,
    is_challenger: bool = False,
) -> None:
    """Atalho para registrar uso de modelo (tokens/custo/latência/outcome)."""
    cost = estimate_cost(model, tokens_in, tokens_out)
    metrics = {
        "tokensIn": tokens_in,
        "tokensOut": tokens_out,
        "latencyMs": latency_ms,
        "invocations": 1,
    }
    if cost is not None:
        metrics["costUsd"] = cost
    props = {}
    if submission_id:
        props["submissionId"] = submission_id
    emit(
        {
            "capability": capability,
            "model": model,
            "outcome": outcome,
            "role": "challenger" if is_challenger else "primary",
        },
        metrics,
        props or None,
    )
