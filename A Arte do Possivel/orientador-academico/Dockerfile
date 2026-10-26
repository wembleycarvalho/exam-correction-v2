# Imagem do agente Orientador para o Amazon Bedrock AgentCore Runtime (linux/arm64).
# Buildada por scripts/deploy-orientador-agent.sh (finch/docker) — NÃO depende do
# agentcore starter toolkit (que, a partir da v0.1.x, não configura VPC).
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim
WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 UV_COMPILE_BYTECODE=1
COPY agent/requirements.txt agent/requirements.txt
RUN uv pip install -r agent/requirements.txt
RUN uv pip install aws-opentelemetry-distro>=0.10.1

ENV AWS_REGION=us-east-1
ENV AWS_DEFAULT_REGION=us-east-1
ENV DOCKER_CONTAINER=1

RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore
EXPOSE 8080
EXPOSE 8000

# Copia o projeto (respeitando .dockerignore) e sobe via OTel.
COPY . .
CMD ["opentelemetry-instrument", "python", "-m", "agent.entrypoint"]
