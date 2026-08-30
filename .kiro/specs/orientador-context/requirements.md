# Requisitos — Orientador Context (backbone Moodle + AWS Context)

## Objetivo

Provar, **em paralelo e sem tocar no que já existe**, um Orientador Acadêmico ancorado em
**dado realista de um LMS (Moodle)** e servido por um **grafo de conhecimento governado
gerenciado (AWS Context)** + **AgentCore Memory**, como um **novo módulo** (`Orientador Context`).
Depois de provado o conceito, aposentar o Orientador atual (Neptune + ingestão custom).

Alinhado à premissa **"A Arte do Possível"**: conceito ligado a problema real (orientação
acadêmica sobre dados operacionais de uma instituição), com valor mensurável.

## Não-objetivos (nesta fase)

- Não alterar/derrubar o Orientador atual, nem os módulos Avaliações/LMS/Entrevistador.
- Não integrar dado real de aluno (PII). Volume de universidade, porém **100% sintético**.
- Não construir um "matriculador"/SIS próprio — o Moodle É a fonte.

## Premissa de execução

- **Paralelo e não-invasivo:** novo diretório de módulo, nova stack/flag, nova rota
  (`/orientador-context/*`) e item de menu próprio. Ligar/desligar por feature flag.
- **Prova-antes-de-aposentar:** os dois orientadores coexistem para comparação lado a lado.

## Requisitos

### R1 — Backbone de dados realista (Moodle)
- R1.1 O sistema DEVE subir uma instância de **Moodle** gerenciada (container + banco) atrás do
  CloudFront, não exposta publicamente.
- R1.2 O Moodle DEVE ser **populado com dado sintético em volume próximo ao de uma universidade**
  (ordem de milhares de alunos, dezenas de cursos, matrículas, notas, competências), sem PII.
- R1.3 O seed DEVE ser **reproduzível** (script versionado) e idempotente.

### R2 — Data lake / catálogo
- R2.1 Os dados do Moodle DEVEM ser expostos a um **catálogo de dados** (AWS Glue Data
  Catalog / Lake Formation) — via export/replicação do banco do Moodle.
- R2.2 O catálogo DEVE conter, no mínimo: alunos, cursos, matrículas (enrollment atual),
  notas/conclusões, competências e a relação curso↔disciplina.

### R3 — Camada de contexto (AWS Context)
- R3.1 O sistema DEVE usar **AWS Context** para mapear as relações num knowledge graph
  governado e oferecer **busca agêntica** consumível pelo agente em runtime.
- R3.2 Regras de negócio (currículo, pré-requisitos, competências→carreira) DEVEM ser curadas/
  anexadas no Context.
- R3.3 **Governança/permissões** DEVEM impor a fronteira **aluno × coordenador** no nível do
  dado (um aluno não acessa dados de outro; coordenador acessa o escopo do seu curso).

### R4 — Agente Orientador Context
- R4.1 O agente (Strands no AgentCore Runtime) DEVE responder consultando a **busca agêntica do
  AWS Context** em vez de traversal em grafo em memória.
- R4.2 O agente DEVE usar **AgentCore Memory/Harness** para memória de conversa persistente
  (substitui o `history` manual e elimina o cache stale por container).
- R4.3 A **lógica de produto que é cálculo, não recuperação** — montar grade de horários
  (grafo de conflito) e simulações what-if — DEVE permanecer como código próprio, alimentado
  pelos dados do Context.
- R4.4 O agente DEVE **nunca alucinar**: responder só com base no Context; recusar e fundamentar
  o que não existir no dado (professores/salas/etc.), como no Orientador atual.

### R5 — Frontend / paridade
- R5.1 O novo módulo DEVE ter rota e item de menu próprios (`Orientador Context`), sem alterar
  o Orientador atual.
- R5.2 As telas DEVEM cobrir, no mínimo, chat aluno + modo coordenador (paridade funcional com
  o atual) para permitir comparação lado a lado.

### R6 — Segurança
- R6.1 Tudo público SOMENTE atrás do CloudFront; Moodle/DB isolados (subnet privada, Secrets
  Manager para credenciais de admin/DB).
- R6.2 IAM de privilégio mínimo; sem credenciais/segredos versionados.

### R7 — Custo e observabilidade
- R7.1 Custo fixo do backbone (Moodle: Fargate + Aurora Serverless v2) é aceitável, desde que o
  conceito se prove; DEVE ser possível **escalar para baixo** quando ocioso.
- R7.2 O sistema DEVE permitir **comparar** o Orientador Context vs atual (acurácia, custo,
  governança) para embasar a decisão de aposentadoria.

### R8 — Aposentadoria do atual (após prova)
- R8.1 Provado o conceito, o Orientador atual DEVE poder ser desligado por flag e o **Neptune +
  ingestão custom removidos**, sem impacto nos demais módulos.

## Riscos / dependências

- **AWS Context está em preview** — depende de estar **habilitado na conta/região**. Passo 0:
  verificar acesso. Se indisponível, ajustar o plano (backbone Moodle→data lake segue de pé;
  a camada de contexto aguarda liberação).
- Fidelidade do mapeamento schema Moodle → grafo (relações pedagógicas ricas: pré-requisito,
  competência→carreira) pode exigir curadoria manual no Context.
