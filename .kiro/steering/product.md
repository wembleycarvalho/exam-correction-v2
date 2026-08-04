# Produto — Exam Correction v2

## O que é

Plataforma de leitura e correção de provas, reconstruída (v2) a partir de um projeto
original preservado em `OldVersion/` (não modificar). O núcleo é a correção assistida por
IA de três tipos de material:

- **Redação** — correção por rubricas (padrão ENEM), com nota por critério e feedback.
- **Prova discursiva** — correção por questão via **gabarito** ou **conhecimento do
  modelo** (a correção de material enviado não usa RAG/KB).
- **Cartão resposta** (múltipla escolha) — reconhecimento de marcações + correção (fase 2).

Além da correção de material enviado, há um módulo de **estudo**:

- **Provas Online** — gera provas (múltipla escolha ou discursivas) ancoradas numa
  **Knowledge Base (RAG)**, o aluno responde no navegador, a correção é automática (MC
  determinística; discursiva por LLM) e, nas questões erradas, sugere trechos das apostilas
  do KB (com a página) para revisão. O projeto acompanha um **acervo sintético de
  demonstração** (`assets/kb-demo/`, 40 disciplinas fictícias) provisionável por
  `DEPLOY_KB=1 ./scripts/deploy.sh` — **conteúdo apenas para demonstração, sem compromisso
  com qualidade pedagógica**; em produção, aponte para um KB próprio.

## Capacidades de apoio

- Criação de prova discursiva (tela admin) com **wizard** de resposta automática.
- Identificação de aluno/prova por **QR contendo apenas um `testId`**, resolvido em uma
  base de vínculo (`test_registry`). PII nunca vai no QR.
- **Rubricas editáveis, versionadas e múltiplas** por redação.
- **Seleção de modelos** com primário + challenger e **A/B testing** em produção (shadow).
- **Métricas reais**: consumo de tokens, custo, latência e qualidade.
- **Avaliação de qualidade** de modelos/agentes via **AgentCore Evaluations** — online
  (shadow em produção) e on-demand/batch com A/B (fase 2).
- **Provas Online (estudo)**: geração de questões a partir da **Knowledge Base**, aplicação
  no navegador, correção automática e sugestão de material de estudo por questão errada.
- **Histórico** de correções com filtros e exportação.

## Idioma

Toda a interface e todo o conteúdo de correção são em **PT-BR**.

## Usuários e acesso

- Perfis mínimos: **admin** e **professor** (grupos Cognito).
- Ações administrativas (rubricas, provas, troca de modelos, criação de usuários) restritas
  a admin.

## Faseamento

- **Fase 1 (núcleo):** auth, dados, borda segura, fila assíncrona, agentes **Strands no
  AgentCore Runtime** (transcrição, redação, discursiva, autor), tool de TestID/QR,
  rubricas, criação de prova, métricas + analytics, seleção de modelos + A/B, frontend
  com menu lateral.
- **Fase 2:** cartão resposta e evaluations (**AgentCore Evaluations**).
- **Provas Online (estudo):** módulo com **Knowledge Base (RAG)** — geração de provas
  (múltipla escolha e discursivas), aplicação no navegador, correção assíncrona e sugestão
  de estudo por questão errada.

## O que foi descontinuado da v1

- Módulos **scanner** e **Alexa skill** (removidos).
- Disparo por prefixo S3 (substituído por API + fila assíncrona).
- Correção binária sem nota, prompts com JSON inválido, `media_type` fixo, API aberta e
  `student` fixo (todos corrigidos na v2).

Fonte da verdade detalhada: `.kiro/specs/exam-correction-v2/` (requirements, design, tasks).
