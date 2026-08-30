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

## Estado

- Backend + infra (construct) + frontend: **prontos**, validados por `cdk synth` (recursos
  criados; **0 recursos sem a flag** — não afeta o portal atual) e `node --check`.
- **Não deployado** ainda (ative com o comando acima).
- Próximo (spec Fase 4/5): comparação lado a lado com o atual (acurácia/custo/governança) e,
  quando o AWS Context liberar, plugar a busca governada + AgentCore Memory.
