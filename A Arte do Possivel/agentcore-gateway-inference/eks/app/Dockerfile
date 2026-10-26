# Imagem do backend "Gateway Inference" p/ EKS Fargate (linux/amd64) — STREAMING SSE.
# Observability nativa via ADOT SDK: rodamos sob `opentelemetry-instrument`, que
# auto-instrumenta Strands + botocore e exporta spans gen_ai.* -> CloudWatch GenAI
# Observability (configurado pelas env vars do Deployment, modo non-runtime hosted agent).
FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8080
# --http h11 garante streaming incremental (sem buffering). 1 worker: o Fargate escala por réplica.
CMD ["opentelemetry-instrument", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--http", "h11", "--no-access-log"]
