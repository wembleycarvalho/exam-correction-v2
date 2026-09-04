# Stack e Decisões Técnicas — A Arte do Possível WEB (portal de demos)

> Produto: **A Arte do Possível WEB**, um **portal de demos de IA** (cada demo = um capítulo
> do menu). O diretório/stack ainda se chama `exam-correction` por histórico. As demos de
> correção são serverless; demos que exigem outra arquitetura (ex.: **Entrevistador Virtual**,
> voz em tempo real → Fargate) são **exceções conscientes e documentadas**, na mesma stack.
>
> Princípio-guia: **simplicidade → serverless → segurança → custo**. A infra anterior
> (SAM com 7 nested stacks, React/MUI, 8 Lambdas) foi descartada por complexidade
> desnecessária e preservada em `OldVersion-sam/` apenas como referência.

## Stack

- **IaC:** AWS **CDK (Python)** — **1 stack única** em `infra/`. Recursos do AgentCore
  (Runtime, Evaluator) usam o construct **alpha** `aws_bedrock_agentcore_alpha` quando
  disponível; o que ainda não tiver cobertura em CloudFormation entra via **custom
  resource** ou via **AgentCore CLI/starter toolkit** no fluxo de deploy.
- **Compute:** **2 Lambdas** (Python 3.12):
  - `avaliacao/backend/api/handler.py` — **router único** de toda a API HTTP (submissions + admin).
  - `avaliacao/backend/worker/handler.py` — **worker SQS** fininho: faz a ponte `SQS → InvokeAgentRuntime`,
    persiste a correção, atualiza status e emite métricas. Não contém a lógica do agente.
  - **Exceção (Entrevistador Virtual):** serviço persistente **FastAPI + WebSocket** em
    **ECS Fargate** (código em `interviewer/`), para voz em tempo real (Nova Sonic, streaming
    bidirecional). Na mesma stack CDK, servido pelo mesmo CloudFront sob `/entrevistador/*`.
    Voz em tempo real não cabe no modelo Lambda/job-based — daí a exceção deliberada.
- **Agentes:** **Strands Agents** rodando no **Amazon Bedrock AgentCore Runtime**
  (deploy **CodeZip**, sem Docker local). Especialistas: `transcription`, `essay`,
  `exam`, `author`, `judge`, `examgen` (geração de Provas Online) e `answersheet`.
  Instrumentados com **OpenTelemetry** → **AgentCore Observability** (traces que alimentam
  as Evaluations).
- **Hospedagem de agentes e compute (preferência + exceções):**
  - **Padrão: AgentCore Runtime.** Todo agente nasce no **AgentCore Runtime** — é a regra.
    O Runtime tem **dois tipos de compute**:
    - **microVM (default, serverless):** Firecracker, isolamento por sessão, start rápido,
      pay-per-use, sessões **≤ 8h**. É o que usamos por padrão (simplicidade → serverless → custo).
    - **Instances (EC2 gerenciado):** roda o agente em **EC2** na nossa conta via um
      **capacity provider** (famílias GPU / memory / compute-optimized), sessões **≤ 14 dias**,
      com AgentCore cuidando de provisionamento/patching/scaling/lifecycle (drivers de GPU
      automáticos). Usar **só quando houver requisito explícito**: cargas sustentadas/
      resource-intensive, **GPU**, ou sessões longas (> 8h). Não é o default.
  - **Exceção — EKS Fargate:** quando houver **requisito explícito que o Runtime não atende
    bem** (ex.: **streaming SSE token-a-token** direto ao browser, como no módulo
    **Gateway Inference**), pode-se hospedar o agente em **EKS Fargate** (FastAPI + Strands),
    com observability nativa via ADOT. É **exceção consciente e documentada**, não o caminho
    padrão. Precedente: `agentcore-gateway-inference/eks/`.
  - Regra prática: **AgentCore Runtime (microVM) → Runtime Instances/EC2 (se sustentado/GPU/
    longo) → EKS Fargate (só se o Runtime não servir, ex. streaming ao browser).** Registrar
    a justificativa sempre que sair do default.
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
  `test_registry`, `online-exams`, `online-attempts`; `+ eval_*` na fase 2); S3
  (uploads/resultados). **A correção de material enviado (redação/discursiva/cartão) não usa
  KB** — gabarito + conhecimento do modelo cobrem o escopo (esse "sem KB" é **local** desse
  fluxo, não uma proibição global).
- **Knowledge Base (RAG) — política geral:** **KB é permitido e incentivado quando há
  necessidade real** (ex.: RAG sobre acervo institucional, geração de questões, atendimento
  com base de conhecimento). Ordem de preferência:
  1. **Reutilizar um KB já existente no projeto** antes de criar outro (evita duplicar
     ingestão/custo). Ex.: o acervo de **Provas Online** e o **conteúdo institucional** do
     módulo de Atendimento.
  2. **Amazon Bedrock Knowledge Base** gerenciada (não hand-rollar RAG), com vector store
     **Amazon S3 Vectors por padrão** (serverless, ~90% mais barato, escala massiva,
     sub-segundo) — **prioridade por custo/simplicidade**.
  3. **GraphRAG (Bedrock KB + Amazon Neptune Analytics)** **quando o problema for
     relacional/multi-hop** (perguntas que cruzam várias entidades/relações, não lookup de
     entidade única) — o KB extrai entidades/relações automaticamente e combina busca
     vetorial + travessia de grafo. **Investigar necessidade/custo antes de adotar**; Neptune
     Analytics não é serverless-barato como S3 Vectors, então só quando o ganho de grafo se
     justificar. (OpenSearch/Aurora pgvector só se um requisito específico pedir.)
  - **Acesso:** só o backend (API/agente) acessa o KB (`bedrock:Retrieve`/`RetrieveAndGenerate`
    no ARN do KB + `s3:GetObject`/`s3:ListBucket` no acervo, com **metadata filtering** para
    controle de acesso quando aplicável). `kbId`/`kbBucket` por contexto do CDK/SSM, nunca no
    bundle do frontend. Nada de KB/bucket de conta específica hardcoded.
- **Borda:** **CloudFront único** (origem S3/OAC para o frontend estático; origem
  `/api/*` → HTTP API). Nada acessível fora do CloudFront. **Sem WAF** (projeto de teste;
  em produção, adicione um WAF WebACL com regras gerenciadas + rate limiting).
- **Auth:** Cognito User Pool **sem self-signup**, admin-create, senha forte, MFA opcional.
  Grupos `admin` e `professor`. Login pela **Hosted UI (PKCE)**.
- **Config/Segredos:** parâmetros via **SSM Parameter Store** e variáveis de ambiente via
  CDK; segredo de origem no **Secrets Manager**. Sem segredos no código ou no bundle do FE.
- **Observabilidade (LIGADA em tudo, NATIVA primeiro):** usar a **AgentCore Observability
  nativa** (OpenTelemetry/ADOT). Para agentes no Runtime deployados via AgentCore CLI a
  instrumentação é **automática** — basta **`aws-opentelemetry-distro`** no `requirements.txt`
  do agente + **Transaction Search habilitado** na conta (1x). Isso alimenta o painel
  **CloudWatch GenAI Observability** com **consumo de tokens (gen_ai.usage.*), latência,
  modelo, tool-use e chamadas downstream (Athena/SSM/Gateway)** por sessão/trace (os spans
  detalhados chegam no stream **`spans`** do log group do runtime). Nunca desligar OTel;
  **não** inicializar `StrandsTelemetry` na mão no Runtime (duplica spans e double-conta
  tokens). Métricas de **Memory/Gateway** também aparecem no painel. **EMF próprio só para
  lacunas** do nativo (ex.: **custo em USD**): linha JSON isolada, tabela de preços
  parametrizada por modelo (env `MODEL_PRICES`/SSM), namespace por módulo — exceção, não
  regra. + logs estruturados (JSON) correlacionados por sessão/`submissionId`. Verificar que
  tokens/traces aparecem no GenAI Observability antes de dar a tarefa por feita.
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
- **Borda Opção A:** API protegida por header secreto (Secrets Manager); S3 via OAC
  com Block Public Access. Sem VPC. **Sem WAF** neste projeto de teste (readicionar em produção).
- **PII fora do QR:** o QR carrega apenas `testId`, resolvido em `test_registry`.
- **KB permitido quando há necessidade (política geral acima):** o "sem KB" vale **só** para a
  **correção de material enviado** (gabarito + modelo cobrem). Onde RAG agrega — **Provas
  Online** (gerar questões/material) e **Atendimento** (base institucional/vestibular) — usa-se
  **Bedrock KB**. **Reutilizar KB existente** antes de criar; **S3 Vectors por padrão**;
  **GraphRAG/Neptune só se o caso for relacional/multi-hop** (investigar necessidade+custo).
  Só o backend acessa o KB.
- **KB demo integrado ao projeto:** o repo inclui um **acervo sintético** em `assets/kb-demo/`
  (só para demonstração, **sem compromisso pedagógico**) e o `scripts/deploy-kb.sh`, que
  provisiona o KB com **Amazon S3 Vectors** (vector store serverless, custo/simplicidade) +
  embeddings Titan v2. `kbId`/`kbBucket` vazios = módulo desabilitado; produção aponta para um
  KB próprio via `KB_ID`/`KB_BUCKET`. Nada de bucket/KB hardcoded de conta específica no stack.

## Estrutura do repositório

```
infra/
  app.py                 # CDK app
  exam_stack.py          # stack única (Cognito, S3, DynamoDB, SQS+DLQ, 2 Lambdas, HTTP API, CloudFront, AgentCore Runtime/Evaluator)
  cdk.json, requirements.txt
avaliacao/               # módulo Avaliações (provas: discursiva, redação, objetiva, online)
  backend/
    common/              # lógica compartilhada (gabarito, rubrica ENEM, metrics, http, json_utils, authz, model_config)
    api/                 # router único + rotas (submissions + admin)
    worker/              # worker SQS (ponte SQS → InvokeAgentRuntime) + omr.py
  agents/                # agentes Strands (deploy no AgentCore Runtime via CodeZip)
  tests/                 # pytest do módulo (+ pytest.ini)
lms/                     # módulo LMS de Vídeo (lms/tests/)
interviewer/             # módulo Entrevistador Virtual (FastAPI + WebSocket, Fargate) (interviewer/tests/)
orientador-academico/    # módulo Orientador Acadêmico (Neptune + AgentCore) (tests/, venv próprio)
tools/                   # Lambdas expostas como tools (read_test_id; read_answer_sheet fase 2)
frontend/
  index.html             # SPA única (vanilla) + Cognito Hosted UI (PKCE)
assets/kb-demo/          # acervo SINTÉTICO do KB (Provas Online) — só para demonstração
scripts/
  deploy.sh, deploy-agents.sh, deploy-kb.sh, build-omr-layer.sh, create-admin-user.sh,
  test-all.sh (regressão por módulo), smoke-test.sh (e2e ao vivo)
OldVersion/              # v1 original (NUNCA modificar)
OldVersion-sam/          # tentativa SAM/React descartada (referência, não usar)
.kiro/specs/exam-correction-v2/
```

## Comandos

- Sintetizar/validar infra: `cd infra && cdk synth`
- Validar template sintetizado (AgentCore): `cfn-lint` (>= 1.53; conhece `AWS::BedrockAgentCore::*`).
- Deploy infra: `./scripts/deploy.sh` (usa `.env`: `AWS_REGION`, `STACK_NAME`, etc.)
- Deploy do KB de demonstração (Provas Online): `DEPLOY_KB=1 ./scripts/deploy.sh` ou
  `./scripts/deploy-kb.sh` avulso (acervo sintético + S3 Vectors + ingestion; grava
  `infra/kb-config.json`). Produção: `KB_ID`/`KB_BUCKET` de um KB próprio.
- Deploy dos agentes no Runtime: `./scripts/deploy-agents.sh` (AgentCore starter toolkit / CLI, CodeZip — **sem Docker**).
- Testes: por módulo (`cd avaliacao && pytest -q`; `cd lms && pytest -q`; orientador usa venv próprio).
  Regressão de todos os módulos: `./scripts/test-all.sh`. E2e ao vivo: `./scripts/smoke-test.sh`.
- Long-running (dev server/watch): **não** rodar via terminal bloqueante — instruir o usuário.

## Regras de execução

- Verificar cada mudança (`cdk synth` / `pytest`) antes de marcar tarefa como concluída.
- Seguir o `tasks.md` do spec, uma tarefa por vez, marcando `[x]` ao concluir.
- Privilégio mínimo de IAM por Lambda/agente. Nunca políticas amplas (`*FullAccess`).
