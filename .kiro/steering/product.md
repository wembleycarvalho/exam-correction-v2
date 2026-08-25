# Produto — A Arte do Possível WEB (portal de demos)

## O que é

**A Arte do Possível WEB** é um **portal de demonstrações de IA** — uma vitrine onde cada
demo é um **capítulo** do menu lateral, sob um portal comum (auth Cognito, borda CloudFront,
mesma UI). Não é mais "apenas" uma ferramenta de correção de provas: correção é o primeiro
conjunto de demos, e novas demos entram como novos capítulos.

> O código nasceu do projeto de correção de provas (original preservado em `OldVersion/`,
> não modificar). O diretório/stack ainda se chama `exam-correction` por histórico, mas o
> **produto** é o portal "A Arte do Possível WEB".

### Demos atuais

**Correção assistida por IA (serverless):**
- **Redação** — correção por rubricas (padrão ENEM), com nota por critério e feedback.
- **Prova discursiva** — correção por questão via **gabarito** ou **conhecimento do
  modelo** (a correção de material enviado não usa RAG/KB).
- **Cartão resposta** (múltipla escolha) — reconhecimento de marcações + correção.
- **Provas Online** — módulo de estudo: gera provas (MC ou discursivas) ancoradas numa
  **Knowledge Base (RAG)**, o aluno responde no navegador, a correção é automática (MC
  determinística; discursiva por LLM) e sugere trechos das apostilas do KB para revisão.
  Acompanha um **acervo sintético de demonstração** (`assets/kb-demo/`, 40 disciplinas
  fictícias), provisionável por `DEPLOY_KB=1 ./scripts/deploy.sh` — **conteúdo só para
  demonstração**; em produção, aponte para um KB próprio.

**Voz em tempo real:**
- **Entrevistador Virtual** — simulador de entrevista por **voz em tempo real** com
  **Amazon Nova Sonic** (streaming bidirecional) e relatório de avaliação de RH ao final.
  É a primeira demo que **foge da arquitetura serverless**: exige servidor persistente
  (FastAPI + WebSocket), rodando em **ECS Fargate** dentro da mesma stack, servido pelo
  **mesmo CloudFront** sob `/entrevistador/*` e embutido no portal. Código em `interviewer/`.

Cada nova demo deve entrar como um novo capítulo do menu, reaproveitando auth/borda comuns;
a arquitetura de cada uma pode variar (serverless por padrão; exceções, como voz em tempo
real, são conscientes e documentadas).

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
- **Entrevistador Virtual**: entrevista por voz em tempo real (Nova Sonic) + relatório de
  avaliação de RH (score/semáforo, competências, comportamento) ao final.
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
- **Entrevistador Virtual:** demo de **voz em tempo real** (Nova Sonic) em **ECS Fargate**
  (exceção consciente ao serverless), servida pelo mesmo CloudFront sob `/entrevistador/*`.

## O que foi descontinuado da v1

- Módulos **scanner** e **Alexa skill** (removidos).
- Disparo por prefixo S3 (substituído por API + fila assíncrona).
- Correção binária sem nota, prompts com JSON inválido, `media_type` fixo, API aberta e
  `student` fixo (todos corrigidos na v2).

Fonte da verdade detalhada: `.kiro/specs/exam-correction-v2/` (requirements, design, tasks).
