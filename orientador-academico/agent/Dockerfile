# AgentCore Runtime exige ARM64. Contexto de build = a pasta orientador-academico/
# (para reaproveitar o pacote `src` já testado, sem duplicar código).
FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

COPY agent/requirements.txt /app/agent/requirements.txt
RUN pip install --no-cache-dir -r /app/agent/requirements.txt

COPY src /app/src
COPY data /app/data
COPY agent /app/agent

ENV PYTHONPATH=/app
# Sem buffering de stdout/stderr para que os logs cheguem ao CloudWatch em tempo real.
ENV PYTHONUNBUFFERED=1
# O BedrockAgentCoreApp expõe /invocations e /ping na porta 8080.
EXPOSE 8080
CMD ["python", "-m", "agent.entrypoint"]
