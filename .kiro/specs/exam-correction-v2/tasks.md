# Plano de Implementação — Exam Correction v2

Plano incremental da arquitetura enxuta (CDK 1 stack; 2 Lambdas API+worker; agentes
**Strands no AgentCore Runtime**; qualidade via **AgentCore Evaluations**; 1 `index.html`).
Prompts de correção, rubrica ENEM e estrutura de gabarito são portados de `OldVersion-sam/`
(referência). `OldVersion/` permanece intocada (R13).

> Convenções: IaC em **AWS CDK** (1 stack); borda em **CloudFront único** com origem de API
> protegida por **header secreto** (Opção A; sem WAF neste projeto de teste); modelos parametrizados via
> `model_config` (sem hardcode), acessados por **Bedrock Converse direto**; correção
> **assíncrona/job-based** (SQS → worker → `InvokeAgentRuntime`, **sem streaming**).

---

## Fase 1 — Núcleo

- [ ] 1. Núcleo compartilhado (`backend/common/`)
  - Portar/limpar: `gabarito`, rubrica ENEM padrão (seed), `metrics` (EMF + custo),
    `http`, `json_utils`, `authz` (verify_origin + claims JWT), `model_config`
    (resolução primário/challenger por capacidade), `schemas` (contratos JSON dos agentes).
  - _Requisitos: R2, R3, R7.1, R8.1, R14.2_

- [ ] 2. Agentes Strands (`agents/`)
  - Implementar `transcription`, `essay` (multi-rubrica), `exam` (gabarito/modelo) e
    `author` (wizard) como agentes Strands; entrypoint compatível com AgentCore Runtime;
    `modelId` recebido no payload (nunca hardcoded); saída JSON validada por schema;
    Converse multimodal (bytes + media type detectado); instrumentação OpenTelemetry.
  - _Requisitos: R1.1, R1.2, R1.7, R1.8, R2, R3, R4.3, R7.4, R12.7_

- [ ] 3. API router único (`backend/api/handler.py`)
  - Roteamento por path para submissions (create/confirm/get/list), rubrics, exams
    (+suggest-answer → invoca agente `author`), model-config, test-registry, analytics,
    admin/users, health. JWT authorizer (Cognito) + header secreto de origem; erros
    `{code,message}` PT-BR.
  - _Requisitos: R2, R4, R5, R7, R8, R10, R11, R16.2, R16.6, R17.4_

- [ ] 4. Worker SQS (`backend/worker/handler.py`)
  - Claim idempotente `QUEUED→PROCESSING`; carrega arquivo (S3); resolve `model_config`;
    invoca o agente no **AgentCore Runtime** (`InvokeAgentRuntime`, não-streaming);
    challenger em shadow; grava `corrections`; atualiza submissão; emite EMF;
    `batchItemFailures` → DLQ.
  - _Requisitos: R1.4, R2.9, R3.5, R7.3, R8.1, R10.1, R16.3, R16.8_

- [ ] 5. Frontend (`frontend/index.html`)
  - SPA única vanilla + Cognito Hosted UI (PKCE, sem "criar conta"); menu lateral; upload
    (URL pré-assinada) → confirm → polling; correção de redação (multi-rubrica) e prova
    (estratégia); criação de prova (wizard); histórico; analytics; rubricas; config de
    modelos; QR (TestID) no cliente.
  - _Requisitos: R11.5, R12.1–R12.7_

- [ ] 6. Infra CDK (`infra/exam_stack.py` + `app.py`)
  - Cognito (sem self-signup, grupos, senha forte); S3 FE (OAC + BPA) e uploads (SSE);
    DynamoDB (submissions/corrections/rubrics/exams/model_config/test_registry); SQS+DLQ;
    2 Lambdas (IAM mínimo; worker com permissão `bedrock-agentcore:InvokeAgentRuntime`);
    HTTP API + authorizer + header secreto; CloudFront (sem WAF neste projeto de teste);
    Secrets Manager; recursos do AgentCore Runtime/Evaluator (construct alpha ou custom resource).
  - _Requisitos: R11, R14.1, R14.2, R16.1, R17.1–R17.13_

- [ ] 7. Deploy dos agentes no Runtime (`scripts/deploy-agents.sh`)
  - Empacotar (CodeZip, sem Docker) e implantar os agentes Strands no AgentCore Runtime via
    starter toolkit/CLI; emitir os ARNs/IDs consumidos pelo worker (via SSM/env).
  - _Requisitos: R1.1, R14.3_

- [ ] 8. Deploy e scripts
  - `scripts/deploy.sh` (cdk deploy → deploy dos agentes → build/sync FE → invalidação
    CloudFront), `scripts/create-admin-user.sh`; `.env`/`.env.example`; README de deploy.
  - _Requisitos: R11.8, R14.3, R14.5, R14.6, R14.7_

- [ ] 9. Verificação (fase 1)
  - `cdk synth` OK; `cfn-lint` no template sintetizado; `pytest` verde; revisão de
    segurança (CloudFront-only, sem self-signup, IAM mínimo, Runtime só via IAM). Validação
    ponta a ponta requer deploy com credenciais.
  - _Requisitos: R14, R17_

---

## Fase 2 — Cartão resposta e Evaluations

- [ ] 10. Cartão resposta (R6): tool `read_answer_sheet` (layer OpenCV) + agente
  `answersheet` (correção contra gabarito) + página no FE + processamento em lote via fila.
- [ ] 11. Evaluations/Harness (R9/R15): configurar avaliadores no **AgentCore Evaluations**
  (LLM-as-judge + code-based), avaliação online (shadow) e batch; datasets/golden sets
  (`eval_datasets`), runner de batch (`eval_runs`), leaderboard + `GET /evaluations`.

---

## Documentação (transversal)

- [ ] 12. README com deploy pelo usuário (pré-requisitos, `.env`, bootstrap/deploy CDK,
  deploy dos agentes no Runtime, 1º admin, configuração de modelos, segurança); referência
  da API; **diagrama "oficial AWS"** (skill `aws-architecture-diagram`); nota de migração
  v1→v2.
  - _Requisitos: R13, R14.3, R17_

---

## Cobertura de requisitos

Fase 1 cobre R1–R5, R7, R8, R10–R14, R16, R17. Fase 2 cobre R6, R9, R15. Documentação é
transversal. Todos os 17 requisitos têm ao menos uma tarefa associada.
