# Entrevistador Virtual — servidor de voz em tempo real (FastAPI + WebSocket + Nova Sonic).
# Serviço próprio (streaming bidirecional), fora da stack serverless do exam-correction.
FROM python:3.12-slim

WORKDIR /app

# Dependências primeiro (cache de camadas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código + assets estáticos
COPY server.py .
COPY static ./static

# Porta HTTP/WebSocket (atrás de ALB/App Runner com upgrade WSS)
ENV PORT=8080
EXPOSE 8080

# Observação de credenciais: o cliente de streaming bidirecional usa
# EnvironmentCredentialsResolver — em produção (Fargate/App Runner) injete credenciais
# via variáveis de ambiente OU adapte para o resolver de credenciais de container/role.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
