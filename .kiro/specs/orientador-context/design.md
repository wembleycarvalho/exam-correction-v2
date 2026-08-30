# Design — Orientador Context (backbone Moodle + AWS Context)

## Visão

Um **backbone de dados realista** (Moodle → data lake) como fundação independente, e o
**Orientador Context** como seu primeiro consumidor, usando **AWS Context** (grafo governado +
busca agêntica) e **AgentCore Memory**. Roda **em paralelo** ao Orientador atual; nada do que
existe é alterado.

## Arquitetura proposta

```mermaid
flowchart TB
  subgraph Backbone["Backbone de dados (fundação reutilizável)"]
    moodle["Moodle (ECS Fargate)\n+ Aurora Serverless v2 (privado)"]
    lake["Glue Data Catalog / Lake Formation\n(alunos, cursos, matrículas, notas, competências)"]
    moodle -->|export/replica DB| lake
  end
  lake --> ctx["AWS Context (preview)\nknowledge graph governado + busca agêntica\n(regras de negócio + permissões aluno×coordenador)"]

  subgraph Modulo["Módulo Orientador Context (novo, isolado)"]
    cf["CloudFront /orientador-context/*"]
    bridge["bridge Lambda"]
    subgraph RT["AgentCore Runtime (Strands)"]
      agent["Agente Orientador Context"]
      memory["AgentCore Memory/Harness"]
      calc["Lógica NOSSA: grade (grafo de conflito), what-if"]
    end
  end
  cf --> bridge --> agent
  agent -->|busca agêntica governada (MCP/API)| ctx
  agent --> memory
  agent --> calc
  calc -->|consome matrícula/currículo| ctx
```

> Coexiste com o Orientador atual (`/orientador/api` + Neptune), intocado.

## Componentes

- **Moodle** (imagem oficial/Bitnami) em **ECS Fargate**; banco em **Aurora Serverless v2**
  (subnet privada). Admin/DB em Secrets Manager. Acesso só via CloudFront.
- **Pipeline de dados**: export/replicação do banco do Moodle para **S3 + Glue Data Catalog**
  (ou Lake Formation). Tabelas-alvo derivadas de `mdl_user`, `mdl_course`, `mdl_enrol`/
  `mdl_user_enrolments`, `mdl_grade_*`, `mdl_course_modules`, framework de competências.
- **AWS Context**: mapeia relações num grafo governado; stewards curam relações inferidas,
  regras de negócio (currículo/pré-requisito/competência→carreira) e **permissões**.
- **Orientador Context (módulo)**: `bridge` Lambda → **AgentCore Runtime** (Strands) que
  consulta a busca agêntica do Context + **AgentCore Memory**. Rota `/orientador-context/*`.
- **Lógica própria** (não é recuperação de contexto): montar grade (coloração do grafo de
  conflito a partir da matrícula) e simulações what-if — reaproveitáveis do módulo atual.

## Fluxos de dados

1. **Seed** → Moodle populado sinteticamente (volume universidade).
2. **Ingestão** → Moodle DB → S3/Glue (batch/replica).
3. **Contexto** → Glue → AWS Context (inferência + curadoria + permissões).
4. **Runtime** → agente consulta busca agêntica; para grade/what-if, puxa matrícula/currículo do
   Context e roda o algoritmo próprio.

## RBAC / governança (ganho central sobre o atual)

O Orientador atual não tem RBAC (qualquer logado vira coordenador). Aqui, as **permissões do
AWS Context** impõem no dado: aluno acessa só o próprio; coordenador, o escopo do curso. O papel
vem do Cognito (grupos) propagado pelo bridge.

## O que fica NOSSO vs vai para o Context

| Responsabilidade | Onde |
|---|---|
| Relações de dados (aluno/curso/matrícula/nota/competência) + busca | **AWS Context** |
| Regras de negócio/curadoria + permissões | **AWS Context** |
| Memória de conversa | **AgentCore Memory** |
| Grade de horários (algoritmo de conflito) e what-if | **Código próprio** (tool) |
| UI/rotas do módulo | **Frontend + bridge** |

## Estratégia de seed sintético

- Volume alvo: ~milhares de alunos, dezenas de cursos, matrículas atuais, histórico de notas,
  competências. **Sem PII** (nomes/e-mails fictícios).
- Reprodutível: script versionado (gerador Moodle / import CSV / seed no banco). Idempotente.

## Faseamento

- **Fase 0 — de-risk:** confirmar AWS Context (preview) na conta/região; validar imagem Moodle.
- **Fase 1 — backbone:** stack Moodle (Fargate + Aurora) + seed sintético em volume.
- **Fase 2 — dado→contexto:** pipeline Moodle→Glue/Lake Formation→AWS Context (+ permissões).
- **Fase 3 — agente:** módulo Orientador Context (rota/menu próprios) sobre busca agêntica +
  AgentCore Memory; portar a lógica de grade/what-if.
- **Fase 4 — provar & comparar:** lado a lado com o atual (acurácia/custo/governança).
- **Fase 5 — aposentar:** desligar Orientador atual + remover Neptune/ingestão custom.

## Riscos e mitigação

- **AWS Context preview / disponibilidade:** verificar no passo 0. Se indisponível, o backbone
  (Moodle→data lake) segue; a camada de contexto aguarda liberação (fallback temporário:
  hidratar um grafo a partir do data lake, sem perder o backbone).
- **Mapeamento pedagógico rico** (pré-requisito, competência→carreira): pode exigir curadoria
  manual no Context, além da inferência automática.
- **Custo fixo do backbone:** Aurora Serverless v2 (min ACU) + Fargate; escalar para baixo/parar
  quando ocioso. Aceito, pois destrava o conceito e serve vários módulos.

## Reuso futuro (fora do escopo desta prova)

O backbone (Moodle + data lake + Context) é fundação: depois pode alimentar Provas Online
(cursos/materiais reais), LMS de Vídeo (vincular vídeos a cursos) e Avaliações (sincronizar
notas) — unificando alunos/cursos/matrículas no portal.

---

## Decisões travadas (Fase 0)

- **AWS Context não tem client boto3/CLI** (verificado em botocore 1.43.78). É capability em
  **preview dentro do Amazon Quick Suite**, consumida por agentes do Quick (integração via MCP)
  e que **publica o contexto governado em S3/Apache Iceberg** (padrão aberto).
- **Opção A (Orientador como agente NATIVO do Amazon Quick) — DESCARTADA.** A interface é
  **sempre o portal de demos "A Arte do Possível"**, nunca a UI do Amazon Quick.
- **Arquitetura escolhida = Opção B:** o **front door é o portal** (capítulo próprio, como o
  Orientador atual). O **motor** consome o AWS Context como camada de contexto governado:
  - **B1 (preferida):** nosso agente (AgentCore/Lambda) lê o contexto governado publicado em
    **S3/Iceberg** (via Athena/Glue) + regras/permissões, e responde no portal.
  - **B2 (alternativa):** o backend do portal chama o **Amazon Quick como motor** por trás
    (se/quando houver caminho programático), renderizando o resultado no portal. "Consumo via
    Quick" é aceitável **desde que a interface seja o portal**.
- **Fallback (C):** enquanto o AWS Context (preview) não estiver habilitado na conta, o backbone
  **Moodle → data lake** segue de pé e o agente consulta o **data lake diretamente** (Athena/
  Glue); troca-se para B1/B2 quando o Context liberar. Assim a Fase 1 não fica bloqueada.
- **Backbone Moodle → data lake é pré-requisito comum** e independente do preview do Context —
  é por onde começamos.

---

## Fronteira de projetos (decisão: Moodle TOTALMENTE apartado)

- O **backbone (Moodle + data lake + habilitação do AWS Context)** é um **projeto separado**,
  com repo/stack próprios — **não** é módulo/flag do `exam-correction`. A infra do Moodle
  criada aqui foi **removida** do `exam-correction` (revertido `infra/exam_stack.py`; excluído
  `infra/modules/moodle.py`).
- O **portal `exam-correction`** só recebe, mais tarde, o módulo **Orientador Context**
  (Fase 3), que **consome os outputs** do backbone (data lake / contexto governado em
  Iceberg) — sem nunca embutir a UI do Moodle nem acoplar a infra do Moodle à stack do portal.
- Divisão de escopo:
  - **Projeto apartado (backbone):** Fases 1–2 (Moodle em Fargate+Aurora+EFS, seed sintético,
    pipeline → Glue/Lake Formation, AWS Context + permissões).
  - **Este repo (portal):** Fases 3–4 (módulo Orientador Context consumindo o backbone;
    comparação lado a lado com o Orientador atual).
