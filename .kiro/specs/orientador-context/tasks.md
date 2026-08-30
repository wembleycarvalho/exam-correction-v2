# Tarefas — Orientador Context (backbone Moodle + AWS Context)

> Em paralelo e **sem tocar** no Orientador atual nem nos demais módulos. Marcar `[x]` ao concluir.

## Fase 0 — De-risk (fazer ANTES de construir)
- [ ] 0.1 Confirmar que **AWS Context (preview)** está habilitado na conta/região (allowlist);
      documentar endpoints/APIs/quotas e forma de acesso do agente (MCP/API).
- [ ] 0.2 Escolher a imagem do **Moodle** (oficial/Bitnami) e validar boot em container ARM64.
- [ ] 0.3 Decidiar nome/rotas do módulo (`orientador-context`, `/orientador-context/*`) e item de menu.
- [ ] 0.4 Se Context indisponível: registrar plano alternativo (backbone segue; contexto aguarda).

## Fase 1 — Backbone Moodle
- [ ] 1.1 Infra do Moodle: **ECS Fargate** + **Aurora Serverless v2** (subnet privada), atrás do
      CloudFront; admin/DB em Secrets Manager; nada exposto publicamente.
- [ ] 1.2 Script de **seed sintético reproduzível** (volume universidade: milhares de alunos,
      dezenas de cursos, matrículas atuais, notas, competências) — sem PII.
- [ ] 1.3 Validar volume/coerência do dado no Moodle (relatórios/consultas de sanidade).

## Fase 2 — Dado → Contexto
- [ ] 2.1 Pipeline **Moodle DB → S3/Glue Data Catalog** (export/replica batch).
- [ ] 2.2 Modelar tabelas-alvo (alunos, cursos, matrículas, notas, competências, curso↔disciplina).
- [ ] 2.3 Habilitar **AWS Context** sobre o catálogo; revisar/curar relações inferidas.
- [ ] 2.4 Anexar regras de negócio (currículo, pré-requisito, competência→carreira).
- [ ] 2.5 Configurar **permissões (RBAC)**: aluno (só o próprio) × coordenador (escopo do curso).

## Fase 3 — Agente Orientador Context
- [ ] 3.1 Novo módulo (dir próprio) + `bridge` Lambda + rota `/orientador-context/*` + item de menu.
- [ ] 3.2 Agente Strands consumindo a **busca agêntica do AWS Context** (sem grafo em memória).
- [ ] 3.3 Integrar **AgentCore Memory/Harness** (memória de conversa; sem cache stale).
- [ ] 3.4 Portar a **lógica própria**: montar grade (grafo de conflito) e what-if, alimentadas
      pela matrícula/currículo vindos do Context.
- [ ] 3.5 Prompts anti-alucinação (só dado do Context; recusar+fundamentar o que não existir).
- [ ] 3.6 Frontend: chat aluno + modo coordenador (paridade para comparação).

## Fase 4 — Provar & comparar
- [ ] 4.1 Bateria de perguntas equivalentes nos dois orientadores (atual vs Context).
- [ ] 4.2 Comparar **acurácia, governança (RBAC), custo e latência**; registrar resultado.
- [ ] 4.3 Validar RBAC ao vivo (aluno não vê outro; coordenador vê só o curso).

## Fase 5 — Aposentar o atual (só após prova)
- [ ] 5.1 Desligar o Orientador atual por flag; migrar o menu para o novo.
- [ ] 5.2 Remover **Neptune + ingestão custom** (economia de custo fixo), sem impacto nos demais.
- [ ] 5.3 Atualizar docs (README do módulo + README raiz + diagramas).

## Verificação (transversal)
- [ ] Nada do Orientador atual / Avaliações / LMS / Entrevistador é alterado durante as Fases 0–4.
- [ ] Sem credenciais/segredos versionados; recursos isolados atrás do CloudFront.
- [ ] Custo do backbone monitorado e com opção de escalar para baixo quando ocioso.
