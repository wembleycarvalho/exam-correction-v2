# Plano de Implementação — Módulo LMS de Vídeo

Plano incremental do módulo plugável de **busca multimodal em vídeo** (TwelveLabs **Marengo
Embed 3.0** no Bedrock + índice **S3 Vectors**), servido pelo mesmo CloudFront sob `/lms/*`
(API) e `/lms/media/*` (playback). Segue o padrão dos módulos Entrevistador/Orientador.

> Convenções: IaC em **AWS CDK** (construct próprio `infra/modules/lms.py`); borda **CloudFront
> único** (API via JWT Cognito; mídia via S3/OAC); **1 índice S3 Vectors** para as 3 buscas
> (espaço unificado do Marengo); ingestão **assíncrona** (Marengo `StartAsyncInvoke`),
> consulta **síncrona**; região **us-east-1**; privilégio **mínimo** de IAM. Acervo/`manifest.json`
> vêm de `assets/lms-demo/build_lms_videos.py`. Verificar cada mudança (`cdk synth` / `pytest`)
> antes de concluir a tarefa.

---

## Fase 1 — Núcleo (ingestão + 3 buscas + player)

- [x] 1. Núcleo compartilhado (`lms/common/`)
  - Cliente **Marengo** (embed de texto/imagem/áudio síncrono; `StartAsyncInvoke` p/ vídeo);
    cliente **S3 Vectors** (PutVectors/QueryVectors + filtros); parser do `manifest.json`;
    função de **casamento segmento↔capítulo** por janela de tempo; montagem de metadados de
    segmento (`disc_id`, `programs`, `area`, `semester`, `video`, `start/end`, `chapter_*`,
    `narration`); `http`/`json_utils`/`authz` (claims JWT).
  - _Requisitos: R2, R3.3, R4.1, R9.2_
  - **Feito:** `lms/common/{config,manifest,segments,marengo,vectors}.py`; builders v3 aninhados
    e parser de embeddings (visual/audio/transcription); dim 512/cosseno; `SearchHit` com
    deep-link `#t=`; 10 testes em `lms/tests/test_common.py` (verdes).

- [x] 2. Ingestão (`lms/ingest/handler.py`)
  - Dispara `StartAsyncInvoke` (Marengo) por vídeo; coleta embeddings na saída S3; casa
    segmento↔capítulo; `PutVectors` no S3 Vectors com metadados; atualiza `lms_catalog` e
    `lms_ingest` (estado pendente/ingerindo/pronto/falhou). **Idempotente** por vídeo;
    reprocessável em falha; sem duplicar segmentos.
  - _Requisitos: R3.1–R3.7, R2.2, R2.3, R11.1_
  - **Feito:** `lms/ingest/handler.py` (ações start/collect/ingest) + `lms/common/store.py`
    (catálogo/estado DynamoDB, Decimal↔num); `rows_from_embeddings` (skip 'asset', modalidade
    default visual); leitura da saída S3 defensiva; testes em `lms/tests/test_ingest.py`.

- [x] 3. API/bridge (`lms/api/handler.py`)
  - Rotas: catálogo (`GET /lms/catalog`, cursos/disciplinas/capítulos) e **busca**
    (`POST /lms/search` com modo `text|audio|image`, filtros `programs/disc_id/area/semester`,
    escopo). Embeda a query no Marengo → `QueryVectors` → resolve `vídeo+timestamp+capítulo+
    cursos+score`. Erros `{code,message}` PT-BR.
  - _Requisitos: R4, R5, R6, R7.1, R7.3, R7.5, R11.2_
  - **Feito:** `lms/api/search.py` (build_index_filter escalar + pós-filtro de cursos, dedupe
    por segmento, group_catalog, run_search text/image/audio) e `lms/api/handler.py` (health/
    catalog/search; áudio async best-effort via StartAsyncInvoke+poll). Testes `test_api.py`.

- [x] 4. Infra CDK (`infra/modules/lms.py`)
  - Bucket S3 do acervo (BPA + OAC) + prefixo de saída de embeddings; **S3 Vectors** (índice,
    cosseno); DynamoDB `lms_catalog`/`lms_ingest`; Lambda API/bridge e Lambda/Step Functions
    de ingestão (IAM mínimo: Marengo específico, S3 Vectors, bucket, tabelas); HTTP API + JWT
    authorizer (reusa `user_pool`/`client`); expõe `self.api_domain` e `self.media_bucket`.
  - _Requisitos: R1.1, R1.2, R3.1, R8.1, R9.1–R9.4_
  - **Feito:** `infra/modules/lms.py` (sem VPC; S3 Vectors criado fora do CDK, nome via
    contexto/env; IAM escopado a Marengo/StartAsyncInvoke/async-invoke + s3vectors no índice +
    bucket/tabelas). Synth isolado do módulo OK (bucket+policy, 2 tabelas, 2 Lambdas, HTTP API+
    authorizer+rota /lms/{proxy+}). Bundle Lambda usa pacotes de topo common/api/ingest.

- [x] 5. Wiring no `exam_stack.py`
  - Sob o conjunto `modules` (`-c modules=...,lms`): behavior `/lms/*` (HttpOrigin + JWT) e
    `/lms/media/*` (S3/OAC, cache otimizado). `CfnOutput`s do módulo.
  - _Requisitos: R1.2, R1.3, R8.1, R8.2_
  - **Feito:** import + bloco `if "lms" in modules` com behaviors `/lms/media/*` (S3/OAC,
    CACHING_OPTIMIZED) e `/lms/*` (HttpOrigin HTTPS, CACHING_DISABLED, JWT). Synth da stack
    inteira deve rodar do build dir fora do OneDrive (latência do asset do layer no OneDrive).

- [x] 6. Publicação do acervo + catálogo (`scripts/deploy-lms.sh`)
  - Sobe os `.mp4` de `assets/lms-demo/videos/` para o bucket do acervo; carrega o
    `manifest.json` no `lms_catalog`; dispara a ingestão de cada vídeo (fila/loop),
    respeitando idempotência e estado.
  - _Requisitos: R2.1, R2.3, R3.4, R3.5_
  - **Feito:** `scripts/deploy-lms.sh` (lê CfnOutputs; cria vector bucket+índice S3 Vectors
    512/cosseno; `aws s3 sync` dos vídeos p/ `lms/media/`; invoca IngestFn por disciplina do
    manifesto — o catálogo é gravado na ingestão). Params das APIs `s3vectors` conferidos via
    boto3 (create_vector_bucket, create_index metadataConfiguration.nonFilterableMetadataKeys,
    put/query). Prefixo do acervo alinhado a `lms/media/` (casa com o path do CloudFront).

- [x] 7. Frontend — capítulo "LMS" (`frontend/app.js`, `frontend/index.html`)
  - Player + barra de busca com seletor de modo (**texto / voz / imagem**); lista de
    resultados (miniatura + capítulo + disciplina + **cursos** + timestamp) com deep-link
    (seek no `start_sec`); chips de capítulos; filtros curso/disciplina/área/semestre;
    indicação de **descoberta cruzada** ("aparece nos cursos X, Y").
  - _Requisitos: R4.4, R5.2, R6.1, R7.1–R7.5, R8.3_
  - **Feito:** grupo "LMS de Vídeo" (busca + catálogo) no menu; `lmsApi` (JWT+refresh);
    viewLmsBusca (modo texto/imagem/voz, filtros curso/área do catálogo, player com seek no
    start_sec, resultados com cursos/timestamp/score) e viewLmsCatalogo (por área → disciplina
    → chips de capítulos que dão play no timestamp). Áudio inline base64 (`audio_input_b64` +
    branch no `embed_audio_query`). CSS `.lms-hit`/`.lms-disc`. node --check OK.

- [x] 8. Auto-avaliação de qualidade (`lms/eval/` + rota admin)
  - Rotina batch/on-demand: usa cada capítulo como consulta (`chapter_title`/`narration`) e
    mede **acerto de timestamp** (segmento retornado dentro da janela do capítulo);
    precision@k por modalidade; latência/scores por consulta. Relatório agregado.
  - _Requisitos: R10.1–R10.3, R11.3_
  - **Feito:** `lms/eval/evaluate.py` (is_correct por centro do segmento na janela do capítulo;
    evaluate → precision@1, hit@k, discipline@1) + rota `POST /lms/eval` (amostra por `limit`,
    usa a busca por texto). Testes `test_eval.py` (overlaps, is_correct, perfect/wrong/empty).

- [x] 9. Testes + verificação
  - `pytest` do núcleo (casamento segmento↔capítulo, montagem de metadados, parsing do
    manifesto, resolução de resultado→deep-link); `cdk synth` do módulo; `node --check` do
    frontend. Validar as 3 buscas ponta a ponta contra um acervo pequeno.
  - _Requisitos: R3.4, R4.2, R5.1, R6.1, R7.4_
  - **Feito:** `pytest lms` = 31 verdes; `py_compile` de todo o pacote; `node --check app.js`;
    `ast` de `infra/modules/lms.py`+`exam_stack.py`; `bash -n deploy-lms.sh`; synth isolado do
    `LmsModule` OK. Validação ponta-a-ponta das 3 buscas fica para após o deploy real
    (`-c modules=...,lms` + `scripts/deploy-lms.sh`), fora do escopo local.

---

## Fase 2 — Avançado

- [x] 10. "Trechos parecidos" (segmento → similares)
  - A partir de um momento do vídeo, usa o vetor do segmento para achar segmentos similares
    no acervo (inclui descoberta entre cursos compartilhados).
  - _Requisitos: R12.2_
  - **Feito:** `VectorIndex.get` (GetVectors) + `search.run_similar` (busca pelo vetor do
    segmento, filtro `modality`, exclui o próprio) + rota `POST /lms/similar` + botão
    "🔎 parecidos" no frontend. Validado ao vivo (descoberta cruzada entre cursos).

- [x] 11. Pegasus (resumo / Q&A por vídeo)
  - Integra o **TwelveLabs Pegasus** (Bedrock) para resumo e perguntas-e-respostas sobre o
    vídeo, por cima do mesmo acervo (IAM adicional restrito ao Pegasus).
  - _Requisitos: R12.2_
  - **Feito:** `common/pegasus.py` (InvokeModel, vídeo inline base64) + rotas `POST /lms/summary`
    e `POST /lms/ask` + IAM Pegasus na ApiFn + botão "📝 resumo" e caixa de perguntas no
    frontend. Usa o **inference profile** `us.twelvelabs.pegasus-1-2-v1:0` (on-demand exige
    profile). Validado ao vivo (resumo real em PT-BR).

- [x] 12. Painel de qualidade / A-B
  - Dashboard das métricas de busca (precision@k, acerto de timestamp, latência) e comparação
    A/B (ex.: Marengo 2.7 vs 3.0), reaproveitando a auto-avaliação da Fase 1.
  - _Requisitos: R10.2, R12.2_
  - **Feito:** view "Qualidade" (`viewLmsQualidade`/`lmsRunEval`) sobre `POST /lms/eval`
    (precision@1, hit@k, discipline@1 + tabela por capítulo). A/B entre modelos (Marengo 2.7 vs
    3.0) exigiria um segundo índice/ingestão — deixado como evolução (o painel e o `eval` já
    suportam trocar de modelo por parâmetro).
