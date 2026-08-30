# Orientador Context (serverless)

Módulo **novo e isolado** do portal "A Arte do Possível". É a Fase 3 da spec
`.kiro/specs/orientador-context/`: um orientador acadêmico que consome o **data lake do
Moodle** (backbone em projeto apartado) em vez de um grafo Neptune próprio.

> **Coexiste** com o **Orientador Acadêmico** atual (Neptune, `/orientador/*`) — nada dele é
> alterado. Este módulo é **inerte por padrão**: só é provisionado quando ativado por
> `-c modules=...,orientador-context`. O objetivo é provar o conceito lado a lado e, depois,
> aposentar o atual (Fase 5).

## Arquitetura (opção B1 da spec — front door = portal)

```
Navegador (portal) ──/orientador-context/*──► CloudFront ──► HTTP API + JWT (Cognito)
                                                                     │
                                                          Lambda "agente" (serverless)
                                                          Bedrock Converse + tool-use
                                                                     │  Athena
                                                                     ▼
                                          Glue Data Catalog `moodle_datalake`  (S3)
                                          (alunos, cursos, matriculas, notas, competencias)
```

- **Sem VPC** (Athena/Glue/S3/Bedrock têm endpoints públicos) → mais simples que o Orientador
  atual (que precisa de VPC para o Neptune).
- **Agente em Lambda** (não AgentCore Runtime): a spec permite "agente **AgentCore/Lambda**"
  na opção B1. Usa **Bedrock Converse + tool-use** — o modelo pede ferramentas, a Lambda
  executa consultas Athena e devolve os dados; o modelo responde só com base neles
  (anti-alucinação). `MODEL_ID` configurável (default `amazon.nova-pro-v1:0`).
- Quando o **AWS Context** (preview) for habilitado sobre o mesmo catálogo, o agente troca a
  camada de consumo (busca agêntica governada) sem mudar o front door. **AgentCore Memory** e
  a lógica de grade/what-if do atual entram como evolução (ver spec).

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
por faculdade com matriculados/média), **Chat** (agente Converse + tools, RBAC), **Trilha**
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

- `agent/handler.py` — Lambda: rotas HTTP (`bootstrap`, `ask`, `perfil`, `risco`,
  `desempenho`, `health`) + laço Converse/tool-use + RBAC pelos grupos do Cognito.
- `agent/tools.py` — tools = consultas Athena sanitizadas (perfil/notas do aluno, alunos em
  risco, desempenho por faculdade, cursos e competências) + specs do Converse.
- `agent/athena.py` — helper de consulta ao workgroup/database do data lake.
- `agent/prompts.py` — prompts (modo aluno/coordenação) com regra anti-alucinação.
- `infra/modules/orientador_context.py` — construct CDK (Lambda + HTTP API + Cognito + IAM
  least-privilege: Athena/Glue/S3/Bedrock escopados). Exposto no CloudFront sob
  `/orientador-context/*` por bloco aditivo em `infra/exam_stack.py`.
- Frontend: itens de menu **Orientador Context (serverless)** e telas `octx-*` em
  `frontend/app.js` (helper `octxApi`) — puramente aditivo.

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

## Estado — DEPLOYADO (deploy cirúrgico)

O módulo está **no ar** no portal, sob `/orientador-context/*`. Verificado ponta a ponta:
`/orientador-context/health` → 200; `/ask` (aluno) responde com as notas reais do aluno via
Athena (sem alucinar); `/desempenho` e `/risco` funcionam para coordenação; aluno recebe 403
nas rotas de coordenação (RBAC); rota autenticada sem token → 401. Os módulos existentes
(`/api/*`, `/entrevistador/*`, `/orientador/*`, `/lms/*`) seguem **intactos**.

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

Comparação lado a lado com o Orientador atual (acurácia/custo/governança) e, quando o AWS
Context liberar, plugar a busca governada + AgentCore Memory sobre o mesmo data lake.
