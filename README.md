# Exam Correction v2

Plataforma serverless de **leitura e correção de provas** assistida por IA, em **PT-BR**.
Cobre três materiais:

- **Redação** — correção por rubricas (padrão ENEM), nota por critério + feedback.
- **Prova discursiva** — correção por questão via **gabarito** ou conhecimento do modelo.
- **Cartão-resposta (múltipla escolha)** — leitura das marcações por **OMR determinístico
  (OpenCV)**, no navegador e no servidor, com detecção de **QR (ID_Exam)**.

Os agentes são **Strands** hospedados no **Amazon Bedrock AgentCore Runtime**; os modelos
são chamados via **Bedrock Converse**, parametrizados por capacidade. Tudo atrás do
**CloudFront**, autenticado por **Cognito**.

> A v1 original está preservada em `OldVersion/` (não modificar). Uma tentativa anterior em
> SAM/React foi descartada e mantida só como referência em `OldVersion-sam/`.

Ordem de prioridade do projeto: **simplicidade → serverless → segurança → custo**.

---

## Arquitetura

![Arquitetura](docs/architecture/exam-correction-v2.png)

```
Browser ─HTTPS─> CloudFront (+WAF)
                  ├── /            → S3 (frontend estático: index.html/app.js/styles.css
                  │                      + opencv.js p/ OMR e QR no navegador; OAC)
                  └── /api/*       → API Gateway HTTP (JWT Cognito + header secreto)
                                       └── Lambda API (CRUD + ciclo de vida + judge síncrono)
                                             ├── DynamoDB / S3 (uploads + referências, presigned)
                                             └── SQS ─> Lambda Worker (concorrência reservada)
                                                          ├── OpenCV (layer): OMR do cartão + QR
                                                          └── InvokeAgentRuntime (IAM)
                                                                └── AgentCore Runtime (agentes Strands)
                                                                      └── Bedrock Converse (modelos parametrizados)
```

- **Correção é assíncrona (job-based):** `upload → 202 + submissionId → polling`. Sem streaming.
- **O browser nunca chama o Runtime** — apenas o worker, via IAM. Fronteira de segurança limpa.
- **Modelos nunca são hardcoded** — escolhidos por capacidade na tela de Configuração de Modelos.

Detalhes de subsistemas (cartão/OMR, model-as-judge, seleção de modelos): [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Fonte da verdade do spec: `.kiro/specs/exam-correction-v2/`.

---

## Funcionalidades

Menu lateral (responsivo; vira gaveta no celular):

- **Prova Discursiva**: Correção · Criação (com wizard de resposta) · Histórico.
- **Redação**: Rubricas (CRUD versionado) · Correção · Histórico.
- **Prova Objetiva (cartão-resposta)**:
  - **Carregar cartão** — leitura **no servidor** (OMR OpenCV), suporta **upload em massa**.
  - **Ler cartão (OpenCV)** — leitura **no navegador** (opencv.js): reconhece a folha
    (features + homografia → corrige posição/rotação/zoom/perspectiva), lê as marcações,
    permite correção manual e salva no histórico.
  - **Templates** — editor visual: sobe a imagem-demo, desenha/edita blocos (mover e
    redimensionar), define alternativas e sensibilidade por bloco; wizard de auto-detecção.
  - **Histórico**.
- **Configuração › Modelos**: primário/challenger por capacidade + modo (desligado / A-B por
  % / ambos) + preços por modelo.
- **Analytics**: Dados Analíticos (notas, tokens/custo por modelo) e **Evaluation**
  (model-as-judge — compara saídas de modelos diferentes e aponta a melhor, com notas por
  dimensão; avaliações ficam salvas).
- **QR / ID_Exam**: ao carregar qualquer imagem (redação/prova/cartão), um QR code é lido e
  seu conteúdo salvo em `ID_Exam`, exibido nas listas e detalhes do histórico.
- **👍/👎** por transcrição e por correção no histórico (insumo para a Evaluation/analytics).

---

## Pré-requisitos

- Conta AWS com acesso ao Amazon Bedrock e ao Bedrock AgentCore na região de deploy.
- **Credenciais via `aws configure` / AWS SSO** (nunca chaves estáticas no repositório).
- **Node 20+** (CDK CLI), **Python 3.12**, **AWS CLI v2**, **Graphviz** (só para regenerar o diagrama).
- Acesso aos modelos desejados habilitado no console do Bedrock (Model access).
- `pip install bedrock-agentcore-starter-toolkit strands-agents` (deploy dos agentes).

---

## Configuração (`.env`)

```bash
cp .env.example .env   # preencha; o .env real é ignorado pelo git
```

| Variável | Descrição |
|----------|-----------|
| `AWS_REGION` | Região de deploy (padrão `us-east-1`). |
| `STACK_NAME` | Nome da stack CDK. |
| `WORKER_CONCURRENCY` | Concorrência reservada do worker (limita chamadas simultâneas ao Bedrock). |
| `DEFAULT_MODEL_ID` | Opcional. Semeia todas as capacidades; vazio = configurar pela UI. |
| `BOOTSTRAP_ADMIN_EMAIL` | E-mail do 1º admin (opcional; pode passar no script). |

**Nunca** coloque `AWS_ACCESS_KEY_ID`/`SECRET` no `.env` versionado. Use profile/SSO.

---

## Deploy

```bash
./scripts/deploy.sh                 # infra (CDK) + Cognito + CORS + seed + frontend + agentes
./scripts/build-omr-layer.sh        # layer OpenCV (headless) + numpy p/ o OMR do cartão no worker
./scripts/create-admin-user.sh admin@suaescola.edu.br
```

`deploy.sh` executa, em ordem: CDK (stack única + `OriginSecret`), atualização das URLs do
Cognito, CORS do bucket de uploads, seed (rubrica ENEM), publicação do frontend
(`index.html`/`app.js`/`styles.css` + `opencv.js`) e deploy dos agentes (`deploy-agents.sh`,
CodeZip → Runtime, ARN no SSM).

`build-omr-layer.sh` empacota `opencv-python-headless` + `numpy` (wheels manylinux, sem
Docker), publica a layer e a anexa ao worker. Atualize o ARN em `infra/exam_stack.py`
(`OmrLayer`) se a versão mudar.

> Deploys incrementais de código usam `aws lambda update-function-code` + `aws s3 sync` +
> invalidação do CloudFront (evita rotacionar o `OriginSecret` a cada `cdk deploy`).

### Configurar modelos e templates (pós-deploy)

1. **Configuração › Modelos**: defina o modelo primário por capacidade (`transcription`,
   `essay`, `exam`, `author`, `answersheet`) e, opcionalmente, challenger + A/B %.
2. **Prova Objetiva › Templates**: crie um template do seu cartão (imagem de referência +
   blocos + alternativas + sensibilidade). Necessário para o OMR (cliente e servidor).

---

## API (resumo)

Todas as rotas sob `/api` (mesma origem do CloudFront; JWT Cognito obrigatório).

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/submissions` | Cria submissão + URL pré-assinada (essay/exam/answersheet) |
| POST | `/submissions/{id}/confirm` | Valida upload e enfileira (202) |
| GET | `/submissions[/{id}]` | Histórico / estado + resultado (inclui `idExam`) |
| GET | `/submissions/{id}/corrections` | Correções + transcrições da submissão |
| GET | `/submissions/{id}/image` | URL pré-assinada da imagem original |
| PUT | `/submissions/{id}/transcription-rating` | 👍/👎 de transcrição |
| POST | `/submissions/{id}/answersheet-result` | Salva leitura OMR feita no navegador (+`idExam`) |
| PUT | `/corrections/{id}/rating` | 👍/👎 de correção |
| GET/POST/PUT/DELETE | `/card-templates[/{id}]` | Templates de cartão |
| POST/GET | `/card-templates/{id}/reference` | Upload/leitura da imagem de referência (S3) |
| GET/POST | `/evaluations/candidates`, `/evaluations/run` | Model-as-judge |
| GET/POST/PUT | `/rubrics[/{id}]`, `/exams[/{id}]` | Versionados (escrita = admin) |
| POST | `/exams/{id}/suggest-answer` | Wizard de resposta (admin) |
| GET/PUT | `/model-config[/{capability}]`, `/pricing` | Seleção de modelos e preços |
| GET | `/models` | Modelos multimodais disponíveis (ativos, sem duplicatas) |
| POST/GET | `/test-registry[/{testId}]` | Vínculo TestID ↔ dono (QR sem PII) |
| GET | `/analytics` | Métricas reais (DynamoDB + CloudWatch) |
| POST | `/admin/users` | Criar usuário (admin) |
| GET | `/health` | Health check |

---

## Cartão-resposta (OMR)

Dois caminhos com o **mesmo algoritmo** (alinhamento por features + threshold + medição de
preenchimento por bolha), a partir de um **template**:

- **Ler cartão (navegador, opencv.js):** feedback imediato, correção manual, salva no
  histórico. Ideal para conferência unitária.
- **Carregar cartão (servidor, layer OpenCV no worker):** processa via fila; aceita **vários
  arquivos** (lote). Ideal para volume.

O template guarda a geometria (blocos: 1ª questão, nº de questões, alternativas, retângulo
normalizado), a **sensibilidade** e uma **imagem de referência** (no S3). O alinhamento por
homografia (ORB) torna a leitura robusta a foto torta/descentralizada/com zoom. Marcações:
letra (A–E), `-` (em branco, vermelho), `*` (múltiplas, amarelo, com as letras detectadas).
Um **QR** na imagem é lido e salvo em `ID_Exam`.

---

## Custos

O grande diferencial da correção de **cartão-resposta** é ser **determinística (OpenCV), sem
LLM**: não há custo de tokens/Bedrock — só serviços serverless por uso. O custo marginal é
dominado pelo tempo de CPU do worker.

### Corrigir 1.000 cartões (caminho "Carregar cartão", servidor)

Premissas: `us-east-1`, sob demanda, fora do free tier. Worker de **1 GB** por **~3 s** por
cartão (decodifica + alinha por features + lê bolhas + QR). Sem Bedrock, sem AgentCore.

| Serviço | Uso p/ 1.000 cartões | Custo aprox. |
|---|---|---|
| Lambda worker (OMR) | 1.000 × 3 GB-s = 3.000 GB-s | ~US$ 0,050 |
| Lambda API (create/confirm/polling) | ~4k invocações curtas | ~US$ 0,004 |
| API Gateway HTTP | ~4k requisições | ~US$ 0,004 |
| SQS | ~1k mensagens | ~US$ 0,001 |
| DynamoDB (on-demand) | ~4k escritas + leituras | ~US$ 0,006 |
| S3 (PUT/GET + ~200 MB/mês) | 1k upload + 1k leitura | ~US$ 0,010 |
| CloudFront (APIs pequenas) | ~4k req | ~US$ 0,005 |
| **Bedrock / LLM / AgentCore** | **não usado** | **US$ 0,00** |
| **Total marginal** | **1.000 cartões** | **≈ US$ 0,08–0,20** |

Ou seja, **~US$ 0,0001 por cartão** — praticamente desprezível, e escala linearmente.

- **Comparação com leitura por LLM (multimodal):** ler um cartão denso por LLM custaria da
  ordem de **~US$ 0,02–0,04 por cartão** (tokens de entrada+saída), ~**US$ 20–40 por 1.000**.
  O OMR determinístico é **~200–400× mais barato** — e mais confiável para grades.
- **"Ler cartão" (navegador):** o OMR roda no cliente (CPU do usuário, grátis); sobra só
  upload S3 + 1–2 chamadas de API + 1 escrita no Dynamo → **~US$ 0,02 por 1.000**.

### Custos fixos mensais (independentes de volume)

WAF WebACL (~US$ 5/mês + ~US$ 1/regra), armazenamento S3/DynamoDB (centavos no início),
CloudFront/Cognito (praticamente free tier em baixo volume) e a layer OpenCV (armazenamento
grátis). Em baixa escala, o **free tier** do Lambda (1M req + 400k GB-s/mês) tende a zerar o
custo variável de vários milhares de cartões.

> Preços de referência (`us-east-1`, sob demanda) e sujeitos a mudança — confira a
> [calculadora AWS](https://calculator.aws) para números oficiais. Correção de **redação** e
> **prova discursiva** usa LLM e tem custo por tokens (medido nas Analytics, por modelo).

---

## Licenças de terceiros

As dependências (OpenCV, NumPy, boto3, Pydantic, Strands, AgentCore, CDK etc.) e suas
licenças estão em [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md). Destaque: o
`opencv-python-headless` embarca componentes de terceiros, incluindo **FFmpeg (LGPL-2.1+)**;
o OpenCV.js é servido ao navegador sob **Apache-2.0**.

---

## Segurança (Well-Architected)

- **Ponto de entrada único no CloudFront**; S3 via **OAC** + Block Public Access; API só
  aceita tráfego com o **header secreto** injetado pelo CloudFront; **WAF**; HTTPS obrigatório.
- **Cognito** sem self-signup, senha forte, MFA opcional, grupos `admin`/`professor`.
- **IAM de privilégio mínimo** por Lambda; **Runtime só acessível via IAM** pelo worker.
- Criptografia em repouso (S3/DynamoDB/SQS) e em trânsito. Segredos no Secrets Manager/SSM.
- **PII fora do QR** (apenas `testId`/`ID_Exam` de vínculo).

---

## Testes

```bash
python3 -m pytest -q          # lógica portável (prompts, schemas, A/B, custo, rubrica)
cd infra && cdk synth         # valida a infraestrutura
python3 docs/architecture/exam-correction-v2.py   # regenera o diagrama (requer Graphviz)
```

---

## Fases

- **Fase 1 (implementada):** auth, dados, borda segura, fila assíncrona, agentes no Runtime
  (transcrição, redação, prova, autor), rubricas, criação de prova + wizard, TestID/QR,
  métricas + analytics, seleção de modelos + A/B, frontend com menu lateral.
- **Fase 2 (implementada nesta versão):** **cartão-resposta** (OMR OpenCV no cliente e no
  servidor, templates, QR/ID_Exam, upload em massa), **Evaluation (model-as-judge)** e
  **👍/👎** no histórico.
- **Futuro:** **AgentCore Evaluations** nativo (online/shadow + batch) e uso das marcas de
  âncora do cartão (fiducial) para robustez máxima de OMR.

---

## Estrutura

```
infra/            # CDK (stack única): Cognito, S3, DynamoDB, SQS+DLQ, 2 Lambdas, HTTP API, CloudFront, WAF, Runtime
backend/
  common/         # lógica compartilhada (gabarito, rubrica ENEM, metrics, http, model_config, ids)
  api/            # router único da API (submissions, rubrics, exams, templates, evaluations, model-config, analytics)
  worker/         # worker SQS (ponte → Runtime) + omr.py (OpenCV: leitura de cartão + QR)
agents/           # agentes Strands (transcription/essay/exam/author/answersheet/judge)
frontend/         # SPA vanilla: index.html + app.js + styles.css (+ opencv.js hospedado)
scripts/          # deploy.sh, deploy-agents.sh, build-omr-layer.sh, create-admin-user.sh, seed.py
docs/architecture # diagrama como código (diagrams) + PNG
tests/            # pytest
```
