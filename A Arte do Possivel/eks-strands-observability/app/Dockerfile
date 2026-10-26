# Imagem do agente Strands p/ EKS Fargate (linux/amd64).
# Observability nativa via ADOT SDK: rodamos sob `opentelemetry-instrument`, que
# auto-instrumenta Strands + botocore/Bedrock e exporta os spans (gen_ai.usage.* etc.)
# para o CloudWatch GenAI Observability, configurado pelas env vars do Deployment.
FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent_server.py .

EXPOSE 8080
# opentelemetry-instrument carrega o ADOT (via OTEL_PYTHON_DISTRO/CONFIGURATOR nas env vars)
# e instrumenta o processo antes de subir o uvicorn.
CMD ["opentelemetry-instrument", "uvicorn", "agent_server:app", "--host", "0.0.0.0", "--port", "8080"]
