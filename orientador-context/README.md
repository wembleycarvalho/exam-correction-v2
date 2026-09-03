# Orientador Context

Módulo **novo e isolado** do portal "A Arte do Possível". É a Fase 3 da spec
`.kiro/specs/orientador-context/`: um orientador acadêmico que consome o **data lake do
Moodle** (backbone em projeto apartado) em vez de um grafo Neptune próprio.

> **Coexiste** com o **Orientador Acadêmico** atual (Neptune, `/orientador/*`) — nada dele é
> alterado. Este módulo é **inerte por padrão**: só é provisionado quando ativado por
> `-c modules=...,orientador-context`. O objetivo é provar o conceito lado a lado e, depois,
> aposentar o atual (Fase 5).

## Arquitetura (chat agêntico no AgentCore + telas determinísticas)

```
Navegador (portal) ──/orientador-context/*──► CloudFront ──► HTTP API + JWT (Cognito)
                                                                     │
                                                        Router (Lambda) — decide o caminho:
                                                                     │
        ┌────────────────────────────────────────────────────────────┴───────────────┐
        │ CHAT (/ask)                                       TELAS determinísticas       │
        ▼                                                   (perfil/grafo/coordenação)  │
  InvokeAgentRuntime (não-streaming)                                    │  Athena       │
        ▼                                                               ▼               │
  Amazon Bedrock AgentCore Runtime                    Glue Data Catalog `moodle_datalake` (S3)
  · agente Strands (CodeZip, sem VPC)                 (alunos, cursos, matriculas, notas, ...)
  · Bedrock Converse (Nova/Claude) + tool-use ──► SQL no Athena (mesmos dados do Moodle)
  · AgentCore Memory (curto prazo, por sessão)
  · AgentCore Gateway (web-search, MCP/SigV4) ──► índice web da AWS (notícias/fatos atuais)
```

O **chat** foi migrado para um **sistema agêntico de verdade**: um agente **Strands** hospedado
no **Amazon Bedrock AgentCore Runtime** (deploy **CodeZip**, sem Docker/VPC). O **Router
(Lambda)** apenas faz a **ponte** `HTTP → InvokeAgentRuntime` (não-streaming) — o browser
nunca fala com o Runtime; só a Lambda, com IAM próprio. As **telas determinísticas**
(perfil, trilha, grafo, coordenação, etc.) seguem consultando o data lake via **Athena direto**
na Lambda — mais simples e barato para dados tabulares fixos.

Capacidades do agente:
- **Dados do Moodle** — ferramentas que consultam o **data lake** via Athena (`moodle_datalake`),
  com RBAC por sessão. Responde só com base no retorno das ferramentas (anti-alucinação).
- **Notícias / eventos atuais** — **AgentCore Web Search** (conector gerenciado, MCP, servido
  dentro da AWS, sem chaves/egress) via **AgentCore Gateway** com auth **IAM/SigV4**. O agente
  cita as fontes (título, URL, data).
- **Conhecimento geral** — responde direto pelo modelo.
- **Memória de conversa** — **AgentCore Memory** (curto prazo, 30 dias) provisionada pelo
  runtime; a continuidade multi-turno também é reforçada pelo histórico enviado na ponte.

- **Sem VPC** (Athena/Glue/S3/Bedrock/AgentCore têm endpoints públicos) → mais simples que o
  Orientador atual (que precisa de VPC para o Neptune).
- **Modelos parametrizados** (`MODEL_ID`, default `amazon.nova-pro-v1:0`), nunca fixos no código.
- **Rollback seguro:** se o `InvokeAgentRuntime` falhar, o Router cai automaticamente no antigo
  agente-em-Lambda (Bedrock Converse local), sem derrubar o chat.

## Diagrama de arquitetura

![Orientador Context — arquitetura agêntica (AgentCore) e fluxo de dados](docs/architecture/orientador-context.png)

> Fonte versionada em `docs/architecture/orientador-context.py` (lib `diagrams` + Graphviz).
> Re-render: `python3 orientador-context/docs/architecture/orientador-context.py`.

## Fluxo de dados (do Moodle ao chat)

São **dois fluxos** independentes: a **ingestão** (leva o dado do Moodle até o data lake) e a
**pergunta** (o chat consome o data lake em tempo real).

### Ingestão — Moodle → data lake (diária / sob demanda)
- **A. Extração:** o Moodle grava tudo no **Aurora PostgreSQL** (privado, sem IP público). Uma
  **Lambda de export** lê visões curadas via **RDS Data API** (HTTPS, sem VPC/driver),
  disparada por **EventBridge (diário)** ou sob demanda (`invoke`).
- **B. Escrita:** a Lambda grava um **CSV por dataset** no **S3** em `s3://.../moodle/<dataset>/`
  (alunos, cursos, matriculas, notas, competencias).
- **C. Catalogação:** ao terminar, a Lambda **dispara o Glue Crawler**.
- **D. Catálogo:** o crawler infere o schema e cria/atualiza as tabelas no **Glue Data Catalog**
  (database `moodle_datalake`), deixando-as consultáveis por SQL.

> O dado do Moodle vira tabelas SQL no data lake — **derivado e reproduzível** (reexecutar a
> export regenera os CSVs).

### Pergunta — chat agêntico (tempo real)
1. **Pergunta:** você digita no chat do portal; o navegador chama
   `https://<portal>/orientador-context/api/ask` (HTTPS) via **CloudFront**.
2. **Auth/roteamento:** o CloudFront encaminha à **HTTP API**, que valida o **JWT do Cognito**
   (o grupo — admin/professor vs aluno — define o **RBAC**) e invoca o **Router (Lambda)**.
3. **Ponte para o Runtime:** o Router lê o ARN do runtime no **SSM** e chama
   **`InvokeAgentRuntime`** (não-streaming), passando `question`, `mode`, `student_id`,
   `groups` e o histórico. Uma sessão estável por (usuário, modo, aluno) chaveia a **memória**.
4. **Raciocínio (agente Strands):** o **AgentCore Runtime** roda o agente, que via **Bedrock
   Converse + tool-use** decide o que usar:
   - **SQL no Athena** (workgroup `moodle-datalake`, sobre o Glue Catalog → CSVs no S3) para
     dados do Moodle — responde **só com base neles** (anti-alucinação);
   - **AgentCore Web Search** (via Gateway/MCP) para notícias/fatos atuais, **citando fontes**;
   - conhecimento geral do modelo quando cabe.
5. **Resposta:** o agente devolve a resposta completa ao Router, que a entrega ao chat. O RBAC
   é reforçado nas duas pontas (Router + agente): aluno é escopado ao próprio `student_id`;
   visões de coordenação exigem grupo `admin`/`professor`.

**Em uma frase:** o Moodle abastece um data lake (Aurora → Lambda → S3 → Glue); quando você
pergunta no chat, o Router aciona um agente Strands no **AgentCore Runtime** que combina SQL no
Athena (dados do Moodle), **web search** (atualidades) e memória de conversa — com o papel
(aluno/coordenador) imposto pelo Cognito.

## Ganho central vs o Orientador atual: RBAC

O Orientador atual não tem RBAC (qualquer logado "vira coordenador"). Aqui o papel vem dos
**grupos do Cognito** (claims do JWT):
- **Coordenador** (`admin`/`professor`): visões agregadas (desempenho por faculdade) e alunos
  em risco de evasão.
- **Aluno**: escopado ao próprio; as tools de aluno são **forçadas** ao `student_id` da sessão
  e as tools de coordenação retornam "acesso negado". (Com o AWS Context, a permissão passa a
  ser imposta no próprio dado.)

## Features (paridade com o Orientador Acadêmico, adaptada ao data lake)

Telas/menu (todas sob "Orientador Context"): **Alunos** (perfil + notas), **Cursos** (disciplinas
por faculdade com matriculados/média), **Chat** (agente Strands no AgentCore Runtime: dados do
Moodle + web search + memória, RBAC), **Trilha**
(a refazer/pendentes/concluídas + % conclusão), **Grafo** (SVG força-dirigido reaproveitado:
`Tudo` = faculdades×disciplinas, `Aluno` = aluno→disciplinas→competências), **Insights**
(risco de evasão, pontos fortes/fracos, recomendações), **Currículo** (faculdades +
disciplinas-ponte), **Competências** (matriz competência×faculdade), **Coordenação**
(alunos por faculdade + **grade noturna conflito-consciente**), **Risco de evasão**,
**Desempenho por faculdade**.

Ações do agente (rotas `/orientador-context/api/*`): `bootstrap, ask, perfil, progresso,
trilha, matricula, competencias-aluno, insights, grafo, programa, faculdades, curriculo,
curriculo-faculdade, competencias-matriz, risco, desempenho, visao-geral, alunos-curso,
matriculas-disciplina, alunos-disciplina, alunos-competencia, grade-noturna, grade-aluno`.

**Fora de escopo (sem dado no Moodle):** Carreiras / Direcionador de carreira, trilha por
pré-requisito / what-if e Insights de caminho-crítico (não há grafo de pré-requisito), e o
fluxo de transferência de curso (exigiria escrita/DynamoDB). Documentado como enriquecimento
futuro (a lógica de grade noturna, essa sim, foi portada por só depender da matrícula).

## Componentes

- `agent/handler.py` — **Router (Lambda)**: rotas HTTP + RBAC pelos grupos do Cognito. O
  `/ask` faz a **ponte** para o AgentCore Runtime (`InvokeAgentRuntime`, lendo o ARN no SSM),
  com **fallback** ao Converse local. As telas determinísticas seguem em Athena direto.
- `agent/tools.py` — consultas Athena sanitizadas usadas pelas telas determinísticas (e pelo
  fallback local) + specs do Converse.
- `agent/athena.py` — helper de consulta ao workgroup/database do data lake.
- `agent/prompts.py` — prompts (modo aluno/coordenação) com regra anti-alucinação.
- `runtime/agent.py` — **agente Strands** do AgentCore Runtime: `@app.entrypoint` +
  ferramentas Athena (perfil/progresso/trilha/cursos/desempenho/risco) com RBAC por sessão +
  `web_search` (AgentCore Gateway) + limpeza de saída. Modelo por `MODEL_ID`.
- `runtime/gateway-websearch.yaml` — CloudFormation do **AgentCore Gateway** (IAM/SigV4 +
  conector `web-search`). Sem account-id hardcoded (usa pseudo-parâmetros).
- `runtime/deploy-runtime.sh` — deploy reproduzível do runtime (CodeZip, sem Docker): gateway +
  `agentcore launch` + IAM least-privilege na execution role + SSM (`runtime-arn`, `gateway-url`).
- `infra/modules/orientador_context.py` — construct CDK (Lambda + HTTP API + Cognito + IAM
  least-privilege: Athena/Glue/S3/Bedrock/AgentCore/SSM escopados). Exposto no CloudFront sob
  `/orientador-context/*` por bloco aditivo em `infra/exam_stack.py`.
- Frontend: itens de menu **Orientador Context** e telas `octx-*` em `frontend/app.js`
  (helper `octxApi`) — puramente aditivo.

## Deploy (opt-in — não altera o deploy padrão)

O módulo consome o **DataLakeBucket** do stack do backbone (`moodle-backbone`, projeto
apartado). O `deploy.sh` resolve o bucket automaticamente quando o módulo é ativado:

```bash
# Ativa o módulo junto do conjunto atual (preserva os módulos que você já usa!):
MODULES="correcao,entrevistador,orientador-context" ./scripts/deploy.sh
```

> ⚠️ **Importante:** o CloudFormation reflete o ÚLTIMO conjunto de `modules` deployado. Informe
> em `MODULES` **todos** os módulos que devem seguir ativos (ex.: inclua `orientador,lms` se
> estiverem no ar) — omitir um o remove. Sem `MODULES`, o deploy segue idêntico ao atual.

Variáveis: `MOODLE_STACK` (default `moodle-backbone`) e `ORIENTADOR_CONTEXT_LAKE_BUCKET`
(override manual do bucket) e `orientadorContextModelId` (via `-c`).

## Verificação rápida (pós-deploy)

```bash
curl -s https://<cloudfront>/orientador-context/health          # {"ok":true,...}
# Chat (aluno):  POST /orientador-context/api/ask {question, mode:"aluno", student_id:"aluno0001"}
# Coordenação:   POST /orientador-context/api/desempenho   (exige grupo admin/professor)
```

## Observabilidade (ligada em tudo)

- **Traces / sessions:** **AgentCore Observability** (OpenTelemetry) habilitada no runtime —
  aparece no painel **CloudWatch → GenAI Observability** (sessões, spans, ferramentas, erros).
- **Métricas de negócio (custo/consumo):** o agente emite **CloudWatch EMF** a cada invocação,
  no namespace **`OrientadorContext/Agent`** com dimensões `Module` / `Mode` / `ModelId`:
  - `InputTokens`, `OutputTokens`, `TotalTokens` — consumo de tokens;
  - `EstimatedCostUSD` — custo estimado (tabela de preços por modelo, override via env
    `MODEL_PRICES`; rótulo "estimado", nunca preço fixo escondido);
  - `LatencyMs` — latência do laço do agente;
  - `ToolCalls`, `ToolErrors`, `WebSearchCalls` (uso do Gateway), `AthenaToolCalls`, `Invocations`.
- **Como emite:** uma **linha JSON EMF isolada** no stdout do runtime → CloudWatch extrai a
  métrica (o streaming da resposta é desligado no agente para não "colar" no JSON).
- **Ver rápido:**
  ```bash
  aws cloudwatch list-metrics --namespace OrientadorContext/Agent
  aws cloudwatch get-metric-statistics --namespace OrientadorContext/Agent \
    --metric-name TotalTokens --dimensions Name=Module,Value=orientador-context \
    --start-time $(date -u -v-1H +%FT%TZ) --end-time $(date -u +%FT%TZ) \
    --period 3600 --statistics Sum
  ```
- **Gateway/Memory:** métricas gerenciadas do AgentCore (invocações, latência, erros) também
  aparecem no painel GenAI Observability; o consumo do web-search é rastreado por `WebSearchCalls`.

## Estado — DEPLOYADO (deploy cirúrgico)

O módulo está **no ar** no portal, sob `/orientador-context/*`, com o chat já **agêntico**
(AgentCore Runtime). Verificado ponta a ponta: `/orientador-context/health` → 200; o **runtime**
responde com as notas/progresso reais do aluno via Athena (sem alucinar), com **web search**
citando fontes para notícias e **memória** multi-turno; `/desempenho` e `/risco` (telas) seguem
para coordenação; aluno recebe 403 nas rotas de coordenação (RBAC); rota autenticada sem token
→ 401. Os módulos existentes (`/api/*`, `/entrevistador/*`, `/orientador/*`, `/lms/*`) seguem
**intactos**. Se o runtime ficar indisponível, o Router cai no Converse local (rollback).

**Deploy do agente (AgentCore Runtime):** `cd orientador-context/runtime && ./deploy-runtime.sh`
— provisiona o Gateway (web search), faz `agentcore launch` (CodeZip, **sem Docker**), aplica
IAM least-privilege na execution role e publica os SSM params (`runtime-arn`, `gateway-url`)
que o Router consome. Reproduzível, sem account-id/bucket hardcoded (resolve dos stacks).

**Como foi deployado (e por que não pelo `deploy.sh`):** o `deploy.sh` faz `cdk deploy` do
portal inteiro, inviável neste ambiente — o módulo Entrevistador usa **imagem Docker**
(`ContainerImage.from_asset`) e o fingerprint de assets do CDK falha lendo o repositório no
OneDrive. Para não redeployar (nem arriscar) o portal, o deploy é **cirúrgico e reproduzível**,
versionado em **`orientador-context/deploy/`**: stack CDK standalone (Lambda + HTTP API +
Cognito importado + IAM least-privilege) + behavior `/orientador-context/*` ligado à
distribution existente de forma aditiva/idempotente + publicação do `app.js`. Um comando:

```bash
cd orientador-context/deploy && ./deploy.sh     # resolve IDs/bucket sozinho; NÃO requer Docker
```

> **Reconciliar para o CDK do portal (quando houver Docker):**
> `cd orientador-context/deploy && ./teardown.sh` (remove behavior + stack standalone) e depois
> `MODULES="correcao,entrevistador,orientador,lms,orientador-context" ./scripts/deploy.sh`
> (o `deploy.sh` já resolve o `DataLakeBucket`). Enquanto o portal não é redeployado com a flag,
> o módulo vive pelo caminho cirúrgico acima.

## Próximo (spec Fase 4/5)

Comparação lado a lado com o Orientador atual (acurácia/custo/governança); **AgentCore
Observability** para traces do agente (tokens/custo/latência) e **AgentCore Evaluations**
(online/batch + A/B) alimentadas por esses traces; e, quando o AWS Context liberar, plugar a
busca governada sobre o mesmo data lake. Memória de longo prazo (LTM) é evolução natural da
STM já provisionada.
