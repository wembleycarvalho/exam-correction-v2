# A Arte do Possível WEB — Documento Completo do Projeto

> Documento único e detalhado de **produto, arquitetura, módulos, segurança, observabilidade,
> deploy e custos**. Consolida e atualiza a documentação que estava fragmentada em
> `README.md`, `docs/ARCHITECTURE.md`, `docs/architecture/*` e nos READMEs por módulo.
>
> **Convenções deste documento**
> - Account ID e segredos **nunca** aparecem aqui. Onde um ID de conta seria necessário, use o
>   placeholder `123456789012`. Região padrão: `us-east-1`.
> - Princípio-guia de todo o projeto: **simplicidade → serverless → segurança → custo**.
> - Todo o conteúdo de interface e correção é **PT-BR**.

---

## 1. Visão do produto

**A Arte do Possível WEB** é um **portal de demonstrações** que prova conceitos de tecnologia
**sempre ligados a problemas reais** de instituições de ensino. Não é demo pela demo: cada
módulo mostra o que a tecnologia (principalmente IA generativa e agentes na AWS) permite fazer
para resolver — ou chegar perto de resolver — uma dor concreta de uma escola ou universidade.

Cada módulo carrega uma **narrativa de problema real**:

| Módulo | Problema real | O que a tecnologia prova |
|---|---|---|
| **Avaliações** | Corrigir redações/provas discursivas e cartões-resposta em escala, com nota e feedback justos | Correção assistida por IA (rubricas ENEM, gabarito, visão OMR determinística), modelo-como-juiz |
| **LMS (vídeo)** | Encontrar o momento certo dentro de horas de videoaula | Busca semântica em vídeo (embeddings multimodais) + sumarização |
| **Entrevistador** | Treinar alunos para entrevistas com prática real de conversa | Voz em tempo real (fala↔fala) com latência baixa |
| **Orientador Acadêmico** | Recomendar trilha/curso considerando o grafo de pré-requisitos e histórico | Agente sobre grafo (Neptune) com raciocínio sobre relações |
| **Orientador Context** | Orientar com base nos dados reais do LMS da instituição | Agente sobre data lake do Moodle (Athena/Glue) + memória + busca web |
| **Gateway Inference** | Servir inferência de múltiplos modelos (Bedrock + BYOK) com streaming e guarda | Gateway/streaming multi-provedor, Guardrails, chaves próprias (BYOK) |
| **Atendimento** | Atender aluno (financeiro, matrícula) por WhatsApp/chat e escalar para humano | Agente de atendimento com ferramentas, campanhas WhatsApp, integração Amazon Connect |

Perfis de acesso mínimos: **admin** e **professor** (grupos Cognito). Ações administrativas
(rubricas, provas, troca de modelos, criação de usuários) são restritas a admin.

---

## 2. Arquitetura macro

O portal é **serverless por padrão** e tem **um único ponto de entrada público: o CloudFront**.
Nada é acessível fora dele. O roteamento por caminho (`path-based routing`) direciona cada
módulo para seu backend:

```
                                 Internet
                                    │
                                    ▼
                       ┌────────────────────────┐
                       │       CloudFront        │  (única porta pública)
                       │   + WAF WebACL          │
                       └────────────┬───────────┘
                                    │  roteamento por caminho
        ┌───────────────┬──────────┼───────────┬───────────────┬────────────────┐
        ▼               ▼          ▼           ▼               ▼                ▼
   /  (SPA S3/OAC)  /api/*     /lms/*    /entrevistador/*  /orientador/*   /orientador-context/*
   frontend estát.  Avaliações  LMS       Entrevistador     Orient. Acad.   Orient. Context
                    HTTP API    HTTP API  ALB→Fargate       HTTP API        HTTP API
                                                                    │
                          ┌─────────────────────┬───────────────────┘
                          ▼                     ▼
                     /agentcore/*          /atendimento/*  +  /atendimento/api/ask
                     Gateway Inference     Atendimento API     Bridge (Lambda streaming)
```

**Componentes transversais:**

- **CloudFront** único (dist `E1LSW3Y6YHCU5D`, domínio `dmx5ebufo9tny.cloudfront.net`) — origem
  S3 via **OAC** (Origin Access Control) para o SPA estático + origens HTTP API / ALB / Function
  URL para cada módulo. **WAF WebACL** na borda.
- **Cognito** User Pool (`us-east-1_qbqZGnOPK`) **sem self-signup**, admin-create, senha forte,
  MFA opcional. Grupos `admin` e `professor`. Login pela **Hosted UI (PKCE)**. Autorização das
  APIs via **JWT authorizer**.
- **Frontend**: SPA estático (HTML/CSS/JS vanilla, sem React/Vite/MUI) servido do S3 via OAC,
  com menu lateral. Identidade visual única em todos os módulos.
- **Config/Segredos**: **SSM Parameter Store** (parâmetros por módulo, ex.: `/atendimento/*`,
  `/gateway-inference/*`) e **Secrets Manager** (segredo de origem, chaves BYOK). Nunca no
  código nem no bundle do frontend.
- **IaC**: cada módulo tem seu próprio deploy (CDK Python ou script), permitindo evolução
  independente. O núcleo (Avaliações + portal) é a stack `exam-correction-v2`.

**Roteamento por módulo (resumo):**

| Prefixo CloudFront | Backend | Módulo |
|---|---|---|
| `/` | S3 (OAC) | Frontend (SPA) |
| `/api/*` | HTTP API + JWT | Avaliações |
| `/lms/*` | HTTP API + JWT | LMS |
| `/entrevistador/*` | ALB → ECS Fargate (WebSocket) | Entrevistador |
| `/orientador/*` | HTTP API + JWT | Orientador Acadêmico |
| `/orientador-context/*` | HTTP API + JWT | Orientador Context |
| `/agentcore/*` | Gateway / streaming | Gateway Inference |
| `/atendimento/api/ask` | Function URL (Lambda streaming) | Atendimento (chat agente) |
| `/atendimento/*` | HTTP API + JWT | Atendimento (templates/campanhas) |

> Ordem importa: a behavior `/atendimento/api/ask` é avaliada **antes** de `/atendimento/*`.

---

## 3. Módulos em detalhe

### 3.1 Avaliações (`avaliacao/`) — núcleo

**Problema real.** Correção de redações, provas discursivas e cartões-resposta em escala, com
nota por critério e feedback, sem depender de correção manual lenta e inconsistente.

**Arquitetura.** Fluxo **assíncrono job-based** (sem streaming):

```
POST /api/submissions → 202 + submissionId → SQS → Worker Lambda → AgentCore Runtime (agentes)
                                                          │
                                        persiste correção + status → GET /api/submissions/{id} (polling)
```

- **API Lambda** (router único) — rotas de submissões + admin, sob `/api/*`.
- **Worker Lambda** (consumidor SQS) — ponte fina `SQS → InvokeAgentRuntime`; persiste correção,
  atualiza status, emite métricas (EMF). Não contém lógica de agente.
- **SQS + DLQ** — concorrência reservada, `ReportBatchItemFailures`, idempotência por
  `submissionId`, retry/backoff+jitter.
- **Agentes Strands no AgentCore Runtime** (deploy CodeZip, sem Docker): `transcription`,
  `essay`, `exam`, `author`, `answersheet`, `judge` (modelo-como-juiz), `examgen`.
- **OMR (cartão-resposta)**: reconhecimento **determinístico** com OpenCV
  (`avaliacao/backend/worker/omr.py`), isolado em **layer** (~189MB, `scripts/build-omr-layer.sh`).
  Transcrição/correção são responsabilidade dos agentes; visão determinística fica em código.
- **Provas Online**: **Bedrock Knowledge Base** (S3 Vectors + Titan Embeddings v2) para
  conhecimento de apoio.
- **Modelos**: **Bedrock Converse direto**, parametrizados por capacidade via `model_config`
  (nunca hardcoded). Primário gera nota oficial; challenger roda em **shadow** (A/B) sem afetar o
  aluno.

**Dados.** DynamoDB: `submissions`, `corrections`, `rubrics`, `exams`, `model_config`,
`test_registry` (+ `eval_*` na fase de evaluations). S3 para uploads/resultados.

**Identificação por QR.** O QR carrega **apenas `testId`** (PII fora do QR), resolvido em
`test_registry`.

**Deploy.** Stack `exam-correction-v2` (`infra/`, CDK Python — 1 stack única):
`cd infra && cdk synth` → `./scripts/deploy.sh`. Agentes: `./scripts/deploy-agents.sh`
(starter toolkit / CLI, CodeZip, sem Docker). Layer OMR: `scripts/build-omr-layer.sh`.

---

### 3.2 LMS de Vídeo (`lms/`)

**Problema real.** Achar o momento exato dentro de horas de videoaula ("onde o professor explica
integral por partes?") e resumir conteúdo.

**Stack.** **TwelveLabs Marengo Embed 3.0** (embeddings multimodais de vídeo) + **S3 Vectors**
(busca) + **Pegasus 1.2** (sumarização/QA sobre vídeo). **Sem Bedrock KB e sem AgentCore** — a
busca é direta sobre S3 Vectors, mantendo o módulo simples.

**Rotas.** `/lms/*` (HTTP API + JWT). **Deploy.** `scripts/deploy-lms.sh`. Spec em
`.kiro/specs/lms-video/`.

---

### 3.3 Entrevistador (`interviewer/`)

**Problema real.** Praticar entrevistas com uma conversa de voz realista, em tempo real.

**Stack.** **Amazon Nova Sonic** (voz fala↔fala, tempo real) via **FastAPI + WebSocket** rodando
em **ECS Fargate** atrás de **ALB**. Este é o **exceção consciente ao serverless**: voz em tempo
real com WebSocket persistente justifica um container de longa duração.

**Rotas.** `/entrevistador/*` (ALB). **Custo.** ~US$ 22–28/mês fixos (Fargate + ALB sempre
ligados) — o maior custo ocioso do portal, por design.

---

### 3.4 Orientador Acadêmico (`orientador-academico/`)

**Problema real.** Recomendar trilha/curso respeitando **pré-requisitos e histórico**, que são
naturalmente um **grafo**.

**Stack.** **Amazon Neptune** (grafo) + **agente Strands no AgentCore Runtime dentro de VPC**
(subnets com NAT, para o Runtime alcançar o Neptune). Uma **bridge Lambda** conecta a API ao
Runtime. Rotas `/orientador/*` (HTTP API + JWT).

**Gotchas registrados (importantes para manutenção):**
- O starter toolkit removeu suporte a VPC → o Runtime é atualizado via
  `bedrock-agentcore-control update-agent-runtime`.
- `requireServiceS3Endpoint` é **imutável** após criação.
- `runtimeSessionId` precisa ter **≥ 33 caracteres**.
- **Neptune é o principal custo ocioso** deste módulo.

**Deploy.** `scripts/deploy-orientador-agent.sh`. Spec em `.kiro/specs/orientador-context/`
(contém decisões relacionadas).

---

### 3.5 Orientador Context (`orientador-context/`) — novo

**Problema real.** Orientar o aluno com base nos **dados reais do LMS** da instituição (Moodle),
não em dados sintéticos.

**Stack.** **Data lake do Moodle** consultado via **Athena/Glue**; **agente Strands no AgentCore
Runtime** (CodeZip, **sem VPC**) + **AgentCore Memory** (memória de conversa) + **AgentCore
Gateway** para busca web. **RBAC por grupos Cognito** (o que cada perfil pode consultar). Rotas
`/orientador-context/*` (HTTP API + JWT).

**Aterramento em dado real.** Prefere um Moodle populado em volume próximo ao de uma universidade
a datasets sintéticos — é o que destrava o valor de analytics/governança sobre dado realista.

**Deploy.** `orientador-context/deploy/deploy.sh` (deploy cirúrgico).

---

### 3.6 Gateway Inference (`agentcore-gateway-inference/`)

**Problema real.** Servir inferência de **múltiplos provedores** (Bedrock + modelos externos via
BYOK) com **streaming**, **guardrails** e **chaves próprias**, mostrando o AgentCore Gateway como
ponto único de roteamento.

**Stack.**
- Módulo de **streaming em EKS Fargate** (cluster `strands-obs-demo`) e também versão em Runtime.
- **Guardrail** (Bedrock, `ArteDoPossivel`) — parâmetros em SSM `/gateway-inference/guardrail-*`.
- **Keys / BYOK** — Gemini e OpenAI via targets `gwinf-*` no `InferenceDemoGatewayV2`.
- Config em SSM `/gateway-inference/*`.

**Rotas.** `/agentcore/*` (CloudFront). Observação: PoC de observabilidade relacionada em
`eks-strands-observability/` (majoritariamente desmontada).

---

### 3.7 Atendimento (`atendimento/`) — importado do projeto Harness

**Problema real.** Atender o aluno (financeiro, matrícula, dúvidas) por **WhatsApp e chat**, com
**campanhas** de comunicação e **escalada para humano** via Amazon Connect.

Dividido em duas fases, **ambas implantadas e verificadas**.

#### Fase 1 — Templates e Campanhas (WhatsApp)
- **`atendimento/api/handler.py`** (Lambda, HTTP API `t5xxojb70d`) — rotas: `health`,
  `templates`, `template`, `campaign`, `format`, `send`, `campaign/send`.
- **`atendimento/api/campaign_lib.py`** — lógica de campanhas.
- **Deploy** (`atendimento/deploy/`): `standalone_stack.py` (CDK), `deploy.sh`,
  `cloudfront_behavior.py`.
- **CloudFront** `/atendimento/*` → HTTP API. Config em SSM `/atendimento/*`.

#### Fase 2 — Chat com agente + streaming
- **`atendimento/agent/agent.py`** — agente **Strands no AgentCore Runtime**
  (`atendimento_assistant-…`), modelo `us.anthropic.claude-sonnet-4-5-20250929-v1:0`, com **5
  tools** implementadas como Lambdas invocadas via `lambda:invoke` (as Lambdas leem eventos
  simples, sem MCP-over-IAM). ARN do Runtime em SSM `/atendimento/runtime-arn`.
- **`atendimento/bridge/index.mjs`** — **Lambda Node.js com response streaming** (Function URL),
  valida o **JWT do portal** e repassa o **SSE** do Runtime para o navegador. O browser **nunca**
  fala direto com o Runtime — só com a bridge, que tem IAM próprio.
  - Frames SSE: `data: "<delta>"` (incrementos) e `data: {"type":"done"}` (fim).
- **CloudFront** behavior `/atendimento/api/ask` → bridge, inserida **antes** de `/atendimento/*`.

**Integração Amazon Connect (WhatsApp/voz).**
- Instância Connect `connect-demo-ps`; entrada de WhatsApp passa por `wpp-gateway-inbound`
  (gateway SNS de voz/imagem).
- Escalada para humano exige (a) o agente marcar `Tool=Escalate` no fluxo e (b) um atendente
  logado na `BasicQueue`.
- **Gateways Connect** (estado saudável esperado `READY`): `connect-jwt-gateway`,
  `connect-mcp-gateway`. Um `UPDATE_UNSUCCESSFUL` no `connect-jwt-gateway` já causou "dificuldade
  técnica" no atendimento e foi corrigido via `update_gateway`.

**Navegação no portal.** Menu **Atendimento** → [Assistente (chat agente), Chat (Connect),
Templates WhatsApp, Campanhas].

**Docs relacionados.** `docs/modules/atendimento.md`.

---

## 4. Segurança (Well-Architected)

- **Borda Opção A**: tudo público **somente atrás do CloudFront**. Origens protegidas: S3 com
  **OAC + Block Public Access**; APIs só aceitam tráfego com **header secreto de origem**
  (Secrets Manager) + **WAF**. Sem VPC onde não é necessário.
- **Cognito sem self-signup**, admin-create, senha forte, MFA opcional; grupos `admin`/`professor`.
  APIs protegidas por **JWT authorizer**.
- **Privilégio mínimo de IAM** por Lambda/agente/tool. **Nunca** políticas amplas
  (`*FullAccess`).
- **Criptografia** em repouso e em trânsito. Segredos em **SSM/Secrets Manager**, jamais no código
  ou no bundle do frontend.
- **CORS** restrito ao domínio do CloudFront. **PII fora do QR** (só `testId`).
- **BYOK** (Gateway Inference) mantém chaves de terceiros em Secrets Manager, nunca no cliente.

---

## 5. Observabilidade

- **AgentCore Observability** — traces nativos dos agentes no Runtime (alimentam Evaluations e
  depuração de tool calls).
- **ADOT / OpenTelemetry** — instrumentação dos agentes; Transaction Search onde aplicável.
- **CloudWatch EMF** — o Worker de Avaliações emite métricas de **tokens, custo e latência** por
  invocação (medir custo desde o início).
- **Logs estruturados** em todas as Lambdas.
- **Qualidade / A-B** — via **AgentCore Evaluations** (online/shadow + batch), alimentado pelos
  traces do Runtime; não se reimplementa harness/scorers próprios.

---

## 6. Deploy — instruções por módulo

Pré-requisito comum: credenciais AWS válidas em `.env` na raiz (carregar com
`set -a; . ./.env; set +a`). Região `us-east-1`.

| Módulo | Comando |
|---|---|
| Núcleo (Avaliações + portal) | `cd infra && cdk synth` → `./scripts/deploy.sh` |
| Agentes de Avaliações | `./scripts/deploy-agents.sh` (CodeZip, sem Docker) |
| Layer OMR | `scripts/build-omr-layer.sh` |
| LMS | `scripts/deploy-lms.sh` |
| Orientador Acadêmico (agente) | `scripts/deploy-orientador-agent.sh` |
| Orientador Context | `orientador-context/deploy/deploy.sh` |
| Atendimento | `atendimento/deploy/deploy.sh` |
| Usuário admin | `scripts/create-admin-user.sh` |

**Validações antes de concluir qualquer tarefa:**
- Infra: `cd infra && cdk synth`; template AgentCore: `cfn-lint` (≥ 1.53).
- Testes: `pytest -q`.
- **Long-running** (dev server/watch): não rodar em terminal bloqueante — instruir o usuário.

---

## 7. Estrutura do repositório

```
README.md                     # visão geral (este documento é a fonte consolidada)
THIRD-PARTY-NOTICES.md
docs/
  PROJETO-COMPLETO.md          # ← este documento
  ARCHITECTURE.md              # deep-dive do núcleo (Avaliações)
  architecture/               # diagramas por módulo (.py + .png): portal, avaliacao, lms,
                              #   interviewer, orientador, atendimento
  modules/atendimento.md
infra/                        # CDK Python — stack única do núcleo (exam-correction-v2)
frontend/                     # SPA estática (vanilla) + Cognito Hosted UI (PKCE)
avaliacao/                    # núcleo: API Lambda, Worker SQS, agentes, OMR
lms/                          # LMS de vídeo (TwelveLabs + S3 Vectors + Pegasus)
interviewer/                  # Entrevistador (Nova Sonic, FastAPI/WebSocket, ECS Fargate)
orientador-academico/         # Orientador (Neptune + agente em VPC)
orientador-context/           # Orientador Context (Moodle data lake + agente + memory)
agentcore-gateway-inference/  # Gateway Inference (streaming multi-provedor, Guardrail, BYOK)
atendimento/                  # Atendimento (api/, agent/, bridge/, deploy/)
eks-strands-observability/    # PoC de observabilidade (majoritariamente desmontada)
scripts/                      # deploy.sh, deploy-agents.sh, deploy-lms.sh, ... build-omr-layer.sh
assets/                       # imagens/estáticos
.kiro/
  steering/                   # tech.md, product.md, principles.md, arte-do-possivel.md
  specs/                      # exam-correction-v2, orientador-context, lms-video
OldVersion/                   # v1 original (NUNCA modificar)
OldVersion-sam/               # tentativa SAM/React descartada (referência)
```

---

## 8. Custos (visão qualitativa)

O portal é **pay-per-use** por design; o custo ocioso concentra-se em poucos componentes.

| Item | Modelo de custo | Observação |
|---|---|---|
| Lambdas / HTTP API / SQS / DynamoDB / S3 / CloudFront | Sob demanda | Custo ~zero em ociosidade |
| AgentCore Runtime (agentes) | Por invocação/uso | Sem servidor ocioso |
| **Entrevistador** (Fargate + ALB) | **Fixo** | ~US$ 22–28/mês (WebSocket persistente) |
| **Orientador Acadêmico** (Neptune) | Instância | **Principal custo ocioso** do módulo |
| Modelos Bedrock (Converse) | Por token | Modelo forte só onde precisa; econômico no resto; medido via EMF |
| BYOK (Gemini/OpenAI) | Provedor externo | Chaves próprias, custo do provedor |

Estratégia: modelo certo por tarefa, concorrência calibrada às quotas (evita throttling/retrabalho),
on-demand por padrão, e **medição de custo por invocação** desde o início.

---

## 9. Decisões travadas (não reabrir sem motivo)

- **Correção é assíncrona/job-based** (`POST /submissions` → 202 → SQS → worker → polling). Sem
  streaming, sem Fargate, sem disparo por prefixo S3 no núcleo.
- **Agentes = Strands no AgentCore Runtime** (CodeZip). O worker Lambda só faz a ponte
  `SQS → InvokeAgentRuntime` (não-streaming). O browser nunca fala com o Runtime.
- **Streaming para o FE ≠ EKS.** Onde há streaming ao navegador (Atendimento Fase 2), usa-se
  **Lambda response streaming** (bridge Node.js) repassando SSE do Runtime. AgentCore Runtime é
  preferido a EKS; **EKS Fargate é exceção explícita** (Gateway Inference). **ECS Fargate** é a
  exceção do Entrevistador (voz em tempo real).
- **Modelos via Bedrock Converse direto**, parametrizados (`model_config`/SSM), nunca hardcoded.
  A/B: primário gera nota oficial, challenger em shadow.
- **Qualidade/A-B/Evaluations via AgentCore Evaluations nativo** (online + batch).
- **Borda Opção A** (header secreto + WAF + OAC/BPA). **PII fora do QR** (só `testId`).
- **KB permitida** quando útil (Avaliações usa Bedrock KB com S3 Vectors); preferir reuso e
  S3 Vectors; LMS não usa KB (busca direta em S3 Vectors).

---

## 10. Pendências e problemas conhecidos

- **Atendimento**: teste e2e no navegador do chat com streaming; hardening de OAC (follow-up);
  Guardrail opcional no agente; memória de conversa (opcional).
- **Connect**: escalada para humano só chega se houver **atendente logado na `BasicQueue`** e o
  agente marcar `Tool=Escalate` no fluxo. WhatsApp entra por `wpp-gateway-inbound` (SNS
  voz/imagem). Gateways devem estar `READY`.
- **eks-strands-observability**: PoC majoritariamente desmontada — não é caminho de produção.
- **OldVersion/** e **OldVersion-sam/**: apenas referência histórica — **nunca modificar**.

---

## 11. Referências internas

- Núcleo (deep-dive): `docs/ARCHITECTURE.md`
- Diagramas: `docs/architecture/*.png` (e os `.py` que os geram)
- Atendimento: `docs/modules/atendimento.md`
- Steering (fonte da verdade de decisões): `.kiro/steering/{tech,product,principles,arte-do-possivel}.md`
- Specs: `.kiro/specs/{exam-correction-v2,orientador-context,lms-video}/`
