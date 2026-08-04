# Arquitetura — detalhes por subsistema

Complementa o `README.md`. Diagrama: [`architecture/exam-correction-v2.png`](architecture/exam-correction-v2.png)
(fonte em `architecture/exam-correction-v2.py`).

## Visão geral do fluxo

1. O browser fala **apenas** com o CloudFront. `/` serve o frontend estático (S3/OAC);
   `/api/*` vai para a HTTP API (JWT Cognito + header secreto de origem).
2. A **API Lambda** faz CRUD e o ciclo de vida da submissão: cria o registro, devolve uma
   URL pré-assinada de upload (S3), e ao `confirm` enfileira na SQS (resposta `202`).
3. O **Worker Lambda** consome a fila (idempotente, concorrência reservada). As mensagens
   têm dois formatos: submissão de imagem (`{submissionId}`) ou tentativa de prova online
   (`{kind:"online-attempt", attemptId}`).
   - **redação/prova** → carrega a imagem do S3 e invoca os agentes no **AgentCore Runtime**
     (transcrição → correção), persiste `corrections` e a submissão;
   - **cartão-resposta** → roda **OMR determinístico (OpenCV)** localmente (sem agente);
   - **tentativa de Provas Online** → corrige a tentativa: múltipla escolha
     **determinística** (marcada × correta); discursiva pela capacidade **`exam`** (LLM).
     Grava nota/acertos e sugestões de estudo do KB na tabela `online-attempts`;
   - nos fluxos de imagem, tenta ler um **QR** e grava `ID_Exam` na submissão.
4. Métricas (tokens/custo/latência) via CloudWatch EMF; ARN do Runtime via SSM.

## Modelos por capacidade (`model_config`)

- Capacidades: `transcription`, `essay`, `exam`, `author`, `answersheet`, `examgen`
  (geração das Provas Online; a correção discursiva dessas provas reutiliza `exam`).
- Cada uma tem **primário**, **challenger** e **modo**: `single` (só primário), `ab` (um ou
  outro por %), `both` (roda os dois e permite comparar). Nunca hardcoded.
- `GET /api/models` lista só modelos **ACTIVE**, multimodais (aceitam imagem), **sem
  duplicatas** (um por modelo subjacente; prefere inference profile global > us; senão
  on-demand). Isso evita escolher modelos LEGACY/indisponíveis.
- Preços por modelo (`/api/pricing`) alimentam o cálculo de custo nas analytics; há fallback
  por família em `common/metrics.py`.

## Cartão-resposta / OMR

Mesmo algoritmo no cliente (opencv.js) e no servidor (`backend/worker/omr.py`), a partir de
um **template**:

1. **Alinhamento (opcional, recomendado):** detecta a folha e corrige perspectiva.
   - *Automático:* ORB (features) entre a foto e a **imagem de referência** do template +
     `findHomography` (RANSAC) → `warpPerspective`. Robusto a posição/rotação/zoom/perspectiva.
   - *Manual (fallback):* o usuário arrasta os 4 cantos (só no navegador).
2. **Binarização:** `adaptiveThreshold` (marcas → branco).
3. **Medição por bolha:** para cada bloco, as posições das bolhas são interpoladas a partir
   do retângulo normalizado (linhas = questões, colunas = alternativas). Mede-se a fração
   preenchida em cada bolha; `>= sensibilidade` conta como marcada.
4. **Decisão por questão:** 1 marcada → a letra; 0 → `-` (em branco); 2+ → `*` (múltiplas,
   guardando as letras). Correção manual disponível na leitura pelo navegador.

**Template** (`/api/card-templates`, guardado na tabela `model_config` com chave `tmpl#<id>`):
`{ name, alternatives, letters, sensitivity, blocks:[{firstQuestion, questions, alternatives,
rect:{x,y,w,h}}] }`. A **imagem de referência** vai para o S3 (`/reference`), não base64 no
DynamoDB (evita o limite de 400 KB por item).

**Caminhos:**
- *Ler cartão* (navegador): OMR + QR no cliente; salva via `POST /submissions/{id}/answersheet-result`.
- *Carregar cartão* (servidor): fila → worker → `omr.read_answersheet`; aceita **lote** (vários arquivos).

**Layer OpenCV:** `opencv-python-headless` + `numpy` (~189 MB descompactada) publicada por
`scripts/build-omr-layer.sh` e anexada ao worker (junto do layer boto3, dentro do limite de
250 MB). Import de `cv2` é **tardio** (só no caminho de cartão), sem afetar redação/prova.

## QR / ID_Exam

- Detecção com `cv2.QRCodeDetector` no servidor (redação/prova/cartão) e `cv.QRCodeDetector`
  no navegador (Ler cartão). Testa a imagem original **e versões ampliadas** (upscale) +
  `detectAndDecodeMulti` — QR pequeno em foto de baixa resolução falha sem upscale.
- O conteúdo (ex.: `id001...`) é salvo no campo `idExam` da submissão e exibido nas listas e
  detalhes do histórico (redação, prova e cartão). PDF ainda não suportado para QR.

## Evaluation (model-as-judge)

- `GET /api/evaluations/candidates`: submissões que usaram **mais de um modelo** (transcrição
  ou correção), por tipo.
- `POST /api/evaluations/run { submissionId, judgeModel }`: a API invoca o agente **judge**
  (síncrono, `InvokeAgentRuntime`) para comparar pares de saídas (transcrições entre si;
  correções do mesmo grupo). Retorna vencedor, notas **por dimensão** e justificativa.
- Cada avaliação é **persistida** em `submission.result.evaluations` (histórico).

## Avaliação humana (👍/👎)

- `PUT /api/corrections/{id}/rating` e `PUT /api/submissions/{id}/transcription-rating`
  gravam `rating` (`up`/`down`/`""`). Insumo para analytics/Evaluation.

## Provas Online / Knowledge Base (RAG)

Módulo de estudo ancorado numa **Amazon Bedrock Knowledge Base** (conteúdo já indexado).
Helpers compartilhados em `backend/common/online_grading.py`; provas e tentativas em tabelas
próprias (`online-exams`, `online-attempts`).

- **Temas:** `GET /api/online-exams/themes` lê a lista salva; `POST` (admin) reindexa lendo
  os `*.pdf.metadata.json` sob `KB_THEMES_PREFIX` no bucket do KB (campo `disciplina`,
  ordenado por `semestre`).
- **Geração** (`POST /api/online-exams`): a **API** recupera passagens por tema
  (`bedrock:Retrieve`, `KB_ID`) e invoca o agente **`examgen`** (síncrono) para criar as
  questões ancoradas nos trechos — `mc` (múltipla escolha, com gabarito + explicação) ou
  `discursive` (com resposta de referência). A prova guarda `kbSources` (com página).
- **Aplicação/correção:** `POST /api/online-exams/{id}/attempts` cria a tentativa
  (`PROCESSING`) e enfileira; o **worker** corrige (MC determinística; discursiva via `exam`)
  e grava nota/acertos. `GET /api/online-attempts/{id}` faz o polling.
- **Estudo:** por questão errada, `study_sources` busca no KB os melhores trechos das
  **apostilas** (com página). `GET /api/online-exams/kb-doc?uri=` devolve URL pré-assinada do
  documento, restrita ao acervo (exclui `*_email.pdf`; prioriza `*_material.pdf`).
- **Fronteira:** só a **API** acessa o KB (`bedrock:Retrieve` no ARN do KB; `s3:GetObject`/
  `s3:ListBucket` no bucket do KB). O worker apenas corrige. KB configurado por contexto do
  CDK (`kbId`/`kbBucket`), nunca no bundle do frontend.

## Deploy incremental (por que não `cdk deploy` sempre)

O `cdk deploy` rotaciona o `OriginSecret` (header CloudFront→API), o que causaria
invalidações/rechurn. Por isso, mudanças de código usam `update-function-code` + `s3 sync` +
invalidação; a stack (`infra/exam_stack.py`) é mantida como fonte da verdade para um deploy
limpo futuro (inclui IAM e a referência da layer OpenCV).
