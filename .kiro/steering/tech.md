# Stack e Decisões Técnicas — Exam Correction v2

> Princípio-guia: **simplicidade → serverless → segurança → custo**. A infra anterior
> (SAM com 7 nested stacks, React/MUI, 8 Lambdas) foi descartada por complexidade
> desnecessária e preservada em `OldVersion-sam/` apenas como referência.

## Stack

- **IaC:** AWS **CDK (Python)** — **1 stack única** em `infra/`. Recursos do AgentCore
  (Runtime, Evaluator) usam o construct **alpha** `aws_bedrock_agentcore_alpha` quando
  disponível; o que ainda não tiver cobertura em CloudFormation entra via **custom
  resource** ou via **AgentCore CLI/starter toolkit** no fluxo de deploy.
- **Compute:** **2 Lambdas** (Python 3.12):
  - `backend/api/handler.py` — **router único** de toda a API HTTP (submissions + admin).
  - `backend/worker/handler.py` — **worker SQS** fininho: faz a ponte `SQS → InvokeAgentRuntime`,
    persiste a correção, atualiza status e emite métricas. Não contém a lógica do agente.
- **Agentes:** **Strands Agents** rodando no **Amazon Bedrock AgentCore Runtime**
  (deploy **CodeZip**, sem Docker local). Especialistas: `transcription`, `essay`,
  `exam`, `author` (e `answersheet` na fase 2). Instrumentados com **OpenTelemetry** →
  **AgentCore Observability** (traces que alimentam as Evaluations).
- **Modelos:** **Amazon Bedrock Converse API direto** (nativo do Strands). Escolha em
  runtime via `model_config` por capacidade (transcrição e correção independentes;
  challenger para A/B). Nunca hardcoded. O **AgentCore Gateway** só entra **se/quando**
  precisarmos de modelos no **Mantle** (futuro) — não é necessário agora.
- **Avaliação de qualidade:** **Amazon Bedrock AgentCore Evaluations** (GA) — modo
  **online** (amostra do tráfego de produção / shadow) e **on-demand/batch** + **A/B**.
  Avaliadores **built-in** e **custom** (LLM-as-judge e code-based/Lambda). Substitui
  harness/scorers próprios: o "harness" vira um **dataset** + um **runner** fino que
  dispara o batch evaluation contra o Runtime.
- **Tools (Lambda):** `read_test_id` (QR) e `read_answer_sheet` (fase 2, OpenCV em layer).
  Transcrição e correção são responsabilidade dos **agentes**, não de tools. Gabarito
  inline (`common.gabarito`) / DynamoDB.
- **API:** API Gateway **HTTP API** + **JWT authorizer (Cognito)** + validação de header
  secreto de origem (só aceita tráfego vindo do CloudFront).
- **Assíncrono:** **SQS + DLQ** + worker (concorrência reservada controlada,
  `ReportBatchItemFailures`, idempotência por `submissionId`, retry/backoff+jitter).
  Submissão é **job-based**: `POST /submissions` → `202 + submissionId` → polling.
  **Sem streaming.**
- **Dados:** DynamoDB (`submissions`, `corrections`, `rubrics`, `exams`, `model_config`,
  `test_registry`; `+ eval_*` na fase 2); S3 (uploads/resultados). **Sem KB, sem
  S3 Vectors, sem OpenSearch** — gabarito + conhecimento do modelo cobrem o escopo.
- **Borda:** **CloudFront único** (origem S3/OAC para o frontend estático; origem
  `/api/*` → HTTP API) + **WAF WebACL**. Nada acessível fora do CloudFront.
- **Auth:** Cognito User Pool **sem self-signup**, admin-create, senha forte, MFA opcional.
  Grupos `admin` e `professor`. Login pela **Hosted UI (PKCE)**.
- **Config/Segredos:** parâmetros via **SSM Parameter Store** e variáveis de ambiente via
  CDK; segredo de origem no **Secrets Manager**. Sem segredos no código ou no bundle do FE.
- **Observabilidade:** **AgentCore Observability** (traces dos agentes) + CloudWatch
  **EMF** (tokens/custo/latência) emitido pelo worker + logs estruturados.
- **Frontend:** **1 `index.html` estático** (HTML/CSS/JS vanilla) + Cognito Hosted UI
  (PKCE), com menu lateral. **Sem React/Vite/MUI/Router.**

## Decisões travadas (não reabrir sem motivo)

- Correção é **assíncrona/job-based**: `POST /submissions` → `202 + submissionId` → SQS →
  worker → `GET /submissions/{id}` (polling). **Sem streaming, sem Fargate, sem disparo
  por prefixo S3.**
- **Agentes = Strands no AgentCore Runtime** (não código solto no worker; não Fargate/
  FastAPI). O worker Lambda apenas faz a ponte `SQS → InvokeAgentRuntime` e chama o Runtime
  de forma **não-streaming** (resposta completa). O **browser nunca fala com o Runtime** —
  só o worker, com IAM próprio.
- **Qualidade / A-B / evaluations via AgentCore Evaluations nativo** (online + batch),
  alimentado pelos traces do Runtime. Não hand-rollar harness/scorers.
- **Modelos via Bedrock Converse direto**, parametrizados (`model_config`), nunca
  hardcoded. `DEFAULT_MODEL_ID` do `.env` é opcional (semeia todas as capacidades); vazio =
  configurar pela UI. **Gateway só para Mantle no futuro.**
- **A/B:** primário gera a nota oficial; challenger roda em **shadow** e não afeta o aluno.
- **Borda Opção A:** API protegida por header secreto (Secrets Manager) + WAF; S3 via OAC
  com Block Public Access. Sem VPC.
- **PII fora do QR:** o QR carrega apenas `testId`, resolvido em `test_registry`.

## Estrutura do repositório

```
infra/
  app.py                 # CDK app
  exam_stack.py          # stack única (Cognito, S3, DynamoDB, SQS+DLQ, 2 Lambdas, HTTP API, CloudFront, WAF, AgentCore Runtime/Evaluator)
  cdk.json, requirements.txt
backend/
  common/                # lógica compartilhada (gabarito, rubrica ENEM, metrics, http, json_utils, authz, model_config)
  api/                   # router único + rotas (submissions + admin)
  worker/                # worker SQS (ponte SQS → InvokeAgentRuntime)
agents/                  # agentes Strands (deploy no AgentCore Runtime via CodeZip)
tools/                   # Lambdas expostas como tools (read_test_id; read_answer_sheet fase 2)
frontend/
  index.html             # SPA única (vanilla) + Cognito Hosted UI (PKCE)
scripts/
  deploy.sh, deploy-agents.sh, create-admin-user.sh
tests/                   # pytest
OldVersion/              # v1 original (NUNCA modificar)
OldVersion-sam/          # tentativa SAM/React descartada (referência, não usar)
.kiro/specs/exam-correction-v2/
```

## Comandos

- Sintetizar/validar infra: `cd infra && cdk synth`
- Validar template sintetizado (AgentCore): `cfn-lint` (>= 1.53; conhece `AWS::BedrockAgentCore::*`).
- Deploy infra: `./scripts/deploy.sh` (usa `.env`: `AWS_REGION`, `STACK_NAME`, etc.)
- Deploy dos agentes no Runtime: `./scripts/deploy-agents.sh` (AgentCore starter toolkit / CLI, CodeZip — **sem Docker**).
- Testes: `pytest -q`
- Long-running (dev server/watch): **não** rodar via terminal bloqueante — instruir o usuário.

## Regras de execução

- Verificar cada mudança (`cdk synth` / `pytest`) antes de marcar tarefa como concluída.
- Seguir o `tasks.md` do spec, uma tarefa por vez, marcando `[x]` ao concluir.
- Privilégio mínimo de IAM por Lambda/agente. Nunca políticas amplas (`*FullAccess`).
