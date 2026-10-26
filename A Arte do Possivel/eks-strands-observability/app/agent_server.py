"""PoC: agente Strands rodando FORA do AgentCore Runtime (no EKS Fargate), com
observabilidade NATIVA do AgentCore via ADOT SDK -> CloudWatch GenAI Observability.

O Strands emite spans OpenTelemetry (gen_ai.usage.* = tokens, execute_tool, invoke_agent).
Com o ADOT SDK (aws-opentelemetry-distro) instrumentando o processo e as variaveis de
ambiente do modo "non-runtime hosted agents", esses spans caem no MESMO painel
CloudWatch GenAI Observability usado pelos agentes do AgentCore Runtime.

Este servidor FastAPI so existe para conseguirmos INVOCAR o agente (via port-forward ou
Service). A telemetria nao depende dele — depende do Strands + ADOT.
"""
import os

import boto3
from fastapi import FastAPI
from pydantic import BaseModel
from opentelemetry import baggage, context

from strands import Agent, tool
from strands.models import BedrockModel

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0")

app = FastAPI(title="EKS Strands + AgentCore Observability (PoC)")


@tool
def horario_utc() -> dict:
    """Retorna a data/hora atual em UTC (ISO-8601). Ferramenta de exemplo p/ gerar
    um span execute_tool observavel."""
    import datetime
    return {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}


@tool
def somar(a: float, b: float) -> dict:
    """Soma dois numeros (ferramenta de exemplo)."""
    return {"resultado": a + b}


_SYSTEM = (
    "Voce e um assistente de demonstracao rodando no Amazon EKS Fargate. Responda em "
    "portugues do Brasil, de forma breve. Use as ferramentas quando fizer sentido."
)


class Ask(BaseModel):
    question: str
    session_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "host": "eks-fargate", "model": MODEL_ID}


@app.post("/invoke")
def invoke(req: Ask):
    # session.id via OpenTelemetry baggage: no Runtime isso e injetado automaticamente;
    # fora do Runtime (EKS) nos setamos p/ correlacionar a sessao no GenAI Observability.
    token = None
    if req.session_id:
        ctx = baggage.set_baggage("session.id", req.session_id)
        token = context.attach(ctx)
    try:
        agent = Agent(
            model=BedrockModel(model_id=MODEL_ID, region_name=REGION),
            system_prompt=_SYSTEM,
            tools=[horario_utc, somar],
            callback_handler=None,
        )
        result = agent(req.question)
        m = getattr(result, "metrics", None)
        usage = dict(getattr(m, "accumulated_usage", {}) or {})
        return {
            "answer": str(result),
            "model": MODEL_ID,
            "tokens": {"input": usage.get("inputTokens", 0),
                       "output": usage.get("outputTokens", 0),
                       "total": usage.get("totalTokens", 0)},
        }
    finally:
        if token is not None:
            context.detach(token)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
