# Requisitos — Módulo LMS de Vídeo (busca multimodal)

## Introdução

Este documento define os requisitos de um **novo módulo plugável** do portal "A Arte do
Possível": um **LMS (Learning Management System) de vídeo** cujo foco é **busca e interação
com o conteúdo dos vídeos** — não apenas por texto, mas por **cena/objeto** (o que aparece
na imagem) e por **voz/áudio** (o que é falado). O motor de entendimento de vídeo é o
**TwelveLabs Marengo Embed 3.0** no **Amazon Bedrock** (embeddings multimodais nativos de
vídeo), com índice vetorial em **Amazon S3 Vectors**.

O módulo segue o mesmo padrão dos módulos **Entrevistador** e **Orientador Acadêmico**:
100% desacoplado do módulo de correção, com recursos próprios (bucket, tabelas, índice),
servido pelo **mesmo CloudFront** sob `/lms/*` e protegido pela mesma autenticação
(Cognito). Prioridade de design: **simplicidade → serverless → segurança → custo**.

O acervo inicial é um conjunto de **vídeos-aula sintéticos** (um por disciplina), gerado
por `assets/lms-demo/build_lms_videos.py`, que produz também um `manifest.json` com a
estrutura de cada vídeo (disciplina, cursos, capítulos com timestamp, texto narrado, voz).
A taxonomia de cursos/disciplinas é reaproveitada do módulo Orientador (6 cursos, 89
disciplinas, muitas **compartilhadas** entre cursos).

Toda a interface e todo o conteúdo são em **português (PT-BR)**.

## Glossário

- **Marengo Embed 3.0**: modelo do TwelveLabs no Amazon Bedrock que gera embeddings
  multimodais (vídeo, texto, imagem, áudio) num **mesmo espaço vetorial**, permitindo busca
  *any-to-any*. Para vídeo, gera **embeddings por segmento** (cada um com janela de tempo).
- **S3 Vectors**: armazenamento/índice vetorial serverless da AWS; guarda os vetores dos
  segmentos + metadados e responde consultas por similaridade.
- **Segmento**: trecho contínuo de um vídeo (janela `start_sec`–`end_sec`) representado por
  um vetor de embedding.
- **Capítulo**: divisão didática do vídeo definida no `manifest.json` (título, `start_sec`,
  `dur_sec`, voz, texto narrado). Usado para navegação e como *ground-truth* de avaliação.
- **Manifesto**: `assets/lms-demo/manifest.json`, índice canônico do acervo (disciplinas,
  cursos, capítulos).
- **Ingestão**: processo assíncrono de embutir um vídeo (Marengo) e indexar seus segmentos.
- **Deep-link**: link/ação que abre o player já posicionado num timestamp.
- **Pegasus**: modelo video-language do TwelveLabs no Bedrock (resumo/Q&A sobre vídeo);
  usado apenas na fase 2.

---

## Requisito 1 — Módulo plugável e desacoplado

**User Story:** Como arquiteto da solução, quero que o LMS de vídeo seja um módulo próprio
e opcional, para poder instalá-lo/removê-lo sem afetar os demais módulos do portal.

#### Acceptance Criteria

1. THE SYSTEM SHALL implementar o módulo como um construct CDK próprio (`infra/modules/lms.py`) com seus próprios recursos (bucket S3, tabelas DynamoDB, índice S3 Vectors, Lambdas), sem alterar recursos dos módulos de correção, entrevistador ou orientador.
2. THE SYSTEM SHALL ser ativável por contexto do CDK (conjunto `modules`), do mesmo modo que `entrevistador` e `orientador`.
3. THE SYSTEM SHALL ser servido pelo **mesmo CloudFront** do portal sob o caminho `/lms/*` (API) e `/lms/media/*` (playback), sem distribuição adicional.
4. THE SYSTEM SHALL manter o código de backend em uma pasta raiz `lms/` e os assets de demonstração em `assets/lms-demo/`.
5. WHERE o módulo estiver desativado, THE SYSTEM SHALL continuar funcionando normalmente nos demais módulos.

---

## Requisito 2 — Acervo e catálogo a partir do manifesto

**User Story:** Como administrador, quero que o catálogo de vídeos (disciplinas, cursos,
capítulos) seja derivado do manifesto gerado, para não manter metadados duplicados à mão.

#### Acceptance Criteria

1. THE SYSTEM SHALL ler o `manifest.json` como fonte canônica do acervo (disciplina, área, semestre, créditos, cursos, e capítulos com `title`/`start_sec`/`dur_sec`/`voice`/`narration`).
2. THE SYSTEM SHALL persistir o catálogo em DynamoDB (disciplinas e capítulos), preservando o vínculo **disciplina → cursos** (uma disciplina pode pertencer a mais de um curso).
3. WHEN um vídeo for (re)ingerido, THE SYSTEM SHALL atualizar o catálogo de forma idempotente, sem duplicar disciplinas/capítulos.
4. THE SYSTEM SHALL expor o catálogo por API para o frontend listar cursos, disciplinas e capítulos.
5. THE SYSTEM SHALL tratar `kb_slug` como ponte opcional para o acervo textual do módulo Provas Online (quando existir), sem exigi-lo.

---

## Requisito 3 — Ingestão e embedding dos vídeos (Marengo → S3 Vectors)

**User Story:** Como sistema, quero embutir cada vídeo com o Marengo e indexar seus
segmentos, para permitir busca semântica por qualquer modalidade.

#### Acceptance Criteria

1. THE SYSTEM SHALL armazenar os vídeos em um bucket S3 privado (Block Public Access), acessível apenas via CloudFront (OAC) para playback e via IAM para a ingestão.
2. WHEN um vídeo é ingerido, THE SYSTEM SHALL invocar o **Marengo Embed 3.0** de forma **assíncrona** (`StartAsyncInvoke`) e obter os **embeddings por segmento** (cada um com janela de tempo), gravados em um prefixo S3 de saída.
3. THE SYSTEM SHALL indexar cada segmento no **S3 Vectors** com o vetor e os metadados: `disc_id`, `programs` (cursos), `area`, `semester`, `video`, `start_sec`, `end_sec`, `chapter_index`, `chapter_title` e `narration` (texto do capítulo correspondente pelo tempo).
4. THE SYSTEM SHALL processar a ingestão de forma **idempotente** por vídeo (reprocessar não duplica segmentos no índice).
5. THE SYSTEM SHALL controlar a ingestão de forma resiliente (reprocessável, com estado por vídeo: pendente/ingerindo/pronto/falhou), tolerando execução assíncrona longa do Marengo.
6. IF a ingestão de um vídeo falhar, THEN THE SYSTEM SHALL registrar o erro e permitir reprocessamento posterior sem intervenção manual no índice.
7. THE SYSTEM SHALL usar apenas a região suportada pelo Marengo Embed 3.0 (us-east-1) e credenciais com privilégio mínimo (apenas os modelos e recursos necessários).

---

## Requisito 4 — Busca por texto

**User Story:** Como usuário, quero buscar por texto e ser levado ao trecho exato do vídeo,
para encontrar rapidamente onde um assunto é tratado.

#### Acceptance Criteria

1. WHEN o usuário envia uma consulta em texto, THE SYSTEM SHALL gerar o embedding do texto com o Marengo e consultar o índice S3 Vectors por similaridade.
2. THE SYSTEM SHALL retornar os **top-k segmentos** rankeados, cada um resolvido para `vídeo + start_sec + end_sec + capítulo + disciplina + cursos + score`.
3. THE SYSTEM SHALL permitir que a busca por texto encontre tanto conteúdo **falado** (áudio) quanto **visual**, por o embedding do segmento ser multimodal.
4. WHEN um resultado é selecionado, THE SYSTEM SHALL abrir o player posicionado no `start_sec` do segmento (deep-link).

---

## Requisito 5 — Busca por voz/áudio

**User Story:** Como usuário, quero buscar usando um trecho de voz/áudio, para achar
momentos por conteúdo falado.

#### Acceptance Criteria

1. WHEN o usuário fornece um clipe de áudio (upload ou gravação curta), THE SYSTEM SHALL gerar o embedding de áudio com o Marengo e consultar o mesmo índice S3 Vectors.
2. THE SYSTEM SHALL retornar os segmentos rankeados com deep-link por timestamp, no mesmo formato da busca por texto.
3. THE SYSTEM SHALL permitir localizar conteúdo **falado** no acervo (a narração de cada capítulo faz parte do embedding do segmento).
4. WHERE o suporte do modelo à modalidade de consulta por áudio for assíncrono, THE SYSTEM SHALL tratar a consulta de forma compatível (ex.: aguardar o resultado), preservando a mesma resposta de saída.

---

## Requisito 6 — Busca por detalhes no vídeo (cena/objeto)

**User Story:** Como usuário, quero buscar por detalhes visuais (uma imagem de referência
ou uma descrição de cena/objeto), para achar onde algo **aparece** no vídeo.

#### Acceptance Criteria

1. WHEN o usuário fornece uma **imagem** de referência, THE SYSTEM SHALL gerar o embedding da imagem com o Marengo e consultar o índice, retornando os segmentos visualmente compatíveis.
2. WHEN o usuário descreve uma cena/objeto **em texto** (ex.: "diagrama de ciclo", "motor a vapor"), THE SYSTEM SHALL usar a busca por texto (Requisito 4) contra o mesmo índice.
3. THE SYSTEM SHALL retornar os segmentos rankeados com deep-link por timestamp.

---

## Requisito 7 — Resultados, navegação e filtros

**User Story:** Como usuário, quero navegar pelos resultados e pelo vídeo com contexto,
para explorar o acervo com eficiência.

#### Acceptance Criteria

1. THE SYSTEM SHALL exibir cada resultado com miniatura do trecho, título do capítulo, disciplina, cursos e o instante (timestamp) do trecho.
2. THE SYSTEM SHALL oferecer navegação por **capítulos** (chips com os temas do manifesto) que posicionam o player no timestamp correspondente.
3. THE SYSTEM SHALL oferecer **filtros** por curso, disciplina, área e semestre sobre os resultados de busca.
4. WHERE uma disciplina for compartilhada por mais de um curso, THE SYSTEM SHALL indicar nos resultados **em quais cursos** aquele conteúdo aparece (descoberta cruzada entre cursos).
5. THE SYSTEM SHALL permitir busca com escopo (todo o acervo, um curso ou uma disciplina).

---

## Requisito 8 — Reprodução (playback) segura

**User Story:** Como usuário, quero assistir aos vídeos com segurança, para consumir o
conteúdo sem exposição pública do acervo.

#### Acceptance Criteria

1. THE SYSTEM SHALL servir os vídeos via CloudFront sob `/lms/media/*` com origem S3 protegida por **OAC** e **Block Public Access**.
2. THE SYSTEM SHALL NOT permitir acesso direto do browser ao bucket S3 do acervo.
3. THE SYSTEM SHALL suportar reprodução a partir de um timestamp arbitrário (seek), para viabilizar os deep-links de busca.
4. THE SYSTEM SHALL restringir o acesso ao portal (e ao módulo) a usuários autenticados via Cognito (mesma auth do portal).

---

## Requisito 9 — Segurança e privilégio mínimo

**User Story:** Como responsável pela segurança, quero que o módulo siga o mesmo padrão de
borda e privilégio mínimo dos demais, para não abrir superfícies novas.

#### Acceptance Criteria

1. THE SYSTEM SHALL expor a API do módulo apenas via CloudFront sob `/lms/*`, protegida por **JWT authorizer (Cognito)**.
2. THE SYSTEM SHALL conceder às Lambdas/roles apenas as permissões necessárias (Marengo/Bedrock específicos, S3 Vectors, o bucket do acervo, as tabelas do módulo), sem políticas amplas (`*FullAccess`).
3. THE SYSTEM SHALL manter segredos/config em SSM/Secrets Manager e variáveis de ambiente via CDK, nunca no código ou no bundle do frontend.
4. THE SYSTEM SHALL restringir CORS ao domínio do CloudFront.

---

## Requisito 10 — Qualidade mensurável (auto-avaliação)

**User Story:** Como avaliador, quero medir a qualidade da busca automaticamente, para
acompanhar a precisão sem curadoria manual.

#### Acceptance Criteria

1. THE SYSTEM SHALL oferecer uma rotina de avaliação que use cada capítulo como consulta (seu `chapter_title`/`narration`) e verifique se o segmento retornado cai dentro da **janela de tempo** daquele capítulo (acerto de timestamp).
2. THE SYSTEM SHALL reportar métricas agregadas de busca (ex.: precision@k, taxa de acerto de timestamp) por modalidade quando aplicável.
3. THE SYSTEM SHALL registrar, por consulta, latência e `top-k`/scores, para análise de custo e qualidade.

---

## Requisito 11 — Observabilidade e custo

**User Story:** Como operador, quero visibilidade de custo e desempenho da ingestão e da
busca, para otimizar com dado.

#### Acceptance Criteria

1. THE SYSTEM SHALL registrar, por vídeo ingerido, o número de segmentos e o tempo de ingestão.
2. THE SYSTEM SHALL registrar, por consulta, a modalidade, a latência e o número de resultados.
3. THE SYSTEM SHALL emitir logs estruturados e métricas (CloudWatch) para ingestão e busca.

---

## Requisito 12 — Faseamento

**User Story:** Como time, queremos entregar o núcleo primeiro, para validar a busca antes
de recursos avançados.

#### Acceptance Criteria

1. THE SYSTEM SHALL entregar na **Fase 1**: ingestão (Marengo → S3 Vectors), busca por **texto**, **voz/áudio** e **detalhes visuais**, playback com deep-link, navegação por capítulos e filtros, e a auto-avaliação de timestamp.
2. THE SYSTEM SHALL reservar para a **Fase 2**: "trechos parecidos" (segmento → segmentos similares no acervo), resumo/Q&A por vídeo via **Pegasus**, e um painel de qualidade/A-B.
3. WHERE um recurso for de Fase 2, THE SYSTEM SHALL NOT bloquear a entrega da Fase 1.
