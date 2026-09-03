# EKS Strands + Observability nativa do AgentCore (PoC)

Prova de conceito: um **agente Strands** rodando **fora do AgentCore Runtime**, no
**Amazon EKS Fargate**, com **observabilidade nativa do AgentCore** — os traces/tokens/
tool-use caem no **mesmo painel CloudWatch → GenAI Observability** usado pelos agentes do
Runtime. Demonstra o modo "non-runtime hosted agents": Strands emite spans OpenTelemetry e o
**ADOT SDK** (em processo) os exporta para o CloudWatch.

> Contexto: no portal "A Arte do Possível", o padrão é AgentCore **Runtime** (observability
> automática). Este módulo existe para **provar que dá para observar um agente em EKS** de
> forma equivalente — útil para times que já têm plataforma Kubernetes.

## Arquitetura

```
kubectl/port-forward ─► Service ─► Pod (EKS Fargate, namespace `strands`)
                                     └─ FastAPI + agente Strands (BedrockModel/Converse)
                                        rodando sob `opentelemetry-instrument` (ADOT SDK)
                                        │                         │
                                        ▼ Bedrock (InvokeModel)   ▼ OTLP -> CloudWatch
                                     Amazon Bedrock            GenAI Observability
                                                               (traces/tokens/tool-use)
```

- **Cluster:** EKS 1.32, **100% Fargate** (sem nodegroup EC2), OIDC habilitado (IRSA).
  Reutiliza uma **VPC existente** (a conta está no limite de VPCs/EIPs) com subnets privadas
  + NAT em 2 AZs.
- **Imagem:** construída na nuvem via **CodeBuild** (sem Docker/finch local) e publicada no
  **ECR** (`eks-strands-observability`).
- **IRSA:** a service account `strands-agent` assume uma role IAM com `bedrock:InvokeModel`
  + entrega de telemetria (`logs:PutLogEvents`, `xray:PutTraceSegments`, `cloudwatch:PutMetricData`).
- **Observability (non-runtime):** o pod roda sob `opentelemetry-instrument` com
  `aws-opentelemetry-distro` e as env vars do modo non-runtime
  (`AGENT_OBSERVABILITY_ENABLED`, `OTEL_PYTHON_DISTRO=aws_distro`,
  `OTEL_PYTHON_CONFIGURATOR=aws_configurator`, headers de log group). Os spans do agente vão
  para o log group `/aws/eks-strands-observability/agent` e ao Transaction Search (o
  `TransactionSearchXRayAccess` foi estendido para incluir esse log group). `session.id` é
  setado via OpenTelemetry **baggage** (no Runtime isso é automático).

## Estrutura

```
app/            agent_server.py (FastAPI + Strands + baggage), requirements.txt, Dockerfile, buildspec.yml
eksctl-cluster.yaml   cluster Fargate reutilizando a VPC (subnets privadas + NAT)
iam/agent-irsa-policy.json   permissões da service account (Bedrock + telemetria)
k8s/deployment.yaml   Namespace + Deployment (env vars ADOT) + Service
deploy-eks.sh         IRSA + deploy do agente (idempotente)
teardown-eks.sh       destrói o cluster p/ parar custos (PURGE_BUILD=yes remove ECR/CodeBuild)
```

## Como subir (resumo)

```bash
# 1) imagem -> ECR (CodeBuild) — feito uma vez; rebuild = start-build no projeto eks-strands-image
# 2) cluster (uma vez, ~15 min):
eksctl create cluster -f eksctl-cluster.yaml
# 3) IRSA + deploy do agente:
./deploy-eks.sh
# 4) testar:
kubectl -n strands port-forward svc/strands-agent 8080:80 &
curl -s localhost:8080/health
curl -s -XPOST localhost:8080/invoke -H 'content-type: application/json' \
  -d '{"question":"que horas sao em UTC? e some 2+3","session_id":"demo-eks-1"}'
```

Depois, veja no **CloudWatch → GenAI Observability** (aba *Bedrock AgentCore* / Traces) o
agente `eks-strands-agent`: spans `invoke_agent`, `chat` (tokens `gen_ai.usage.*`),
`execute_tool` (`horario_utc`/`somar`) — igual a um agente do Runtime.

## Custo & teardown

O **EKS control plane** cobra ~**US$0.10/h (~US$73/mês)** mesmo ocioso; Fargate cobra por
pod/hora. **Destrua após a demo:**

```bash
./teardown-eks.sh                 # apaga cluster + IRSA
PURGE_BUILD=yes ./teardown-eks.sh # também remove ECR + CodeBuild
```

A VPC reutilizada e o log group de observability não são removidos pelo teardown.
