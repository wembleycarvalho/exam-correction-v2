# Requisitos — Exam Correction v2

## Introdução

Este documento define os requisitos da segunda versão da plataforma de correção de
provas. A v1 (preservada em `OldVersion/`) fazia correção de redação (estilo ENEM),
correção de prova discursiva (via gabarito ou Knowledge Base) e transcrição de
gabaritos, usando chamadas diretas ao Amazon Bedrock, um frontend em Create React App
e métricas apenas simuladas.

A v2 reconstrói a plataforma em torno de **agentes especialistas Strands** hospedados no
**Amazon Bedrock AgentCore Runtime** e avaliados pelo **Amazon Bedrock AgentCore
Evaluations**, adiciona **rubricas editáveis e múltiplas por redação**, **identificação
do aluno/prova via QR/código de barras**, **criação de provas discursivas via tela de
admin**, **métricas reais** (consumo de tokens, custo, qualidade), **avaliação de
modelos/agentes e A/B testing em produção**, **autenticação Cognito** e um **novo
frontend** com menu lateral. Também inicia um módulo novo de **reconhecimento de cartão
resposta**. Os módulos de scanner e Alexa da v1 são removidos.

Toda a interface e todo o conteúdo de correção são em **português (PT-BR)**.

## Glossário

- **Rubrica**: conjunto de critérios e escalas de pontuação usado para corrigir uma redação.
- **Gabarito**: respostas de referência de uma prova discursiva.
- **KB (Knowledge Base)**: base de conhecimento vetorial usada para correção via RAG (removida do escopo).
- **AgentCore Runtime**: serviço gerenciado que hospeda e executa os agentes (deploy CodeZip, sem container local), com instrumentação de traces nativa.
- **AgentCore Evaluations**: serviço gerenciado que pontua a qualidade dos agentes (sessão, resposta, tool call) com avaliadores built-in e custom (LLM-as-judge/code-based), em modo online (produção/shadow) ou batch/A-B.
- **AgentCore Gateway**: proxy de inferência multi-modelo (OpenAI-compatível); usado apenas se/quando houver modelos no Mantle a rotear (fora do escopo da fase 1).
- **Submissão**: uma prova/redação enviada de um aluno para correção.
- **Cartão resposta**: folha de respostas de múltipla escolha lida opticamente.

---

## Requisito 1 — Plataforma de agentes no AgentCore Runtime

**User Story:** Como arquiteto da solução, quero que as capacidades de correção e
extração sejam agentes especialistas (Strands) hospedados no AgentCore Runtime e
invocados de forma gerenciada, para ter execução isolada, escalável, observável e
avaliável, sem servidores próprios.

#### Acceptance Criteria

1. THE SYSTEM SHALL implementar as capacidades de correção e extração como agentes especialistas (framework Strands) hospedados no Amazon Bedrock AgentCore Runtime.
2. THE SYSTEM SHALL implementar, no mínimo, agentes distintos para: transcrição/extração de conteúdo, correção de redação, correção de prova discursiva e criação de conteúdo de prova.
3. WHERE uma capacidade puder ser reutilizada por mais de um agente (ex.: leitura de QR/TestID, leitura de cartão resposta), THE SYSTEM SHALL implementá-la como uma tool compartilhada em vez de duplicá-la.
4. WHEN o Runtime é invocado (`InvokeAgentRuntime`) por um consumidor interno autenticado (o worker, via IAM), THE SYSTEM SHALL executar o agente adequado e retornar uma resposta estruturada (JSON) validada por schema.
5. THE SYSTEM SHALL manter os agentes acessíveis apenas por consumidores internos autenticados por IAM (o worker), nunca diretamente pelo usuário final/frontend.
6. IF um agente falhar ou exceder o tempo limite, THEN THE SYSTEM SHALL retornar um erro estruturado com código e mensagem em português, sem vazar detalhes internos sensíveis.
7. THE SYSTEM SHALL emitir traces de execução dos agentes (OpenTelemetry → AgentCore Observability) e registrar, por invocação, o agente, o modelo, a latência e o consumo de tokens (ver Requisito 8), de forma que as Evaluations (Requisito 9) possam pontuá-los.
8. THE SYSTEM SHALL acessar os modelos via Amazon Bedrock Converse API (parametrizados, sem hardcode); o AgentCore Gateway SHALL ser adotado apenas se/quando houver modelos no Mantle a rotear.

---

## Requisito 2 — Correção de redação com rubricas editáveis e múltiplas

**User Story:** Como professor, quero corrigir uma redação usando uma ou mais rubricas
que eu mesmo possa editar, para adaptar a avaliação a diferentes contextos (ENEM,
vestibular próprio, critérios da escola).

#### Acceptance Criteria

1. THE SYSTEM SHALL permitir criar, editar, versionar e desativar rubricas de correção de redação.
2. THE SYSTEM SHALL representar uma rubrica como um conjunto de critérios, cada um com nome, descrição, pontuação máxima e (opcionalmente) descritores de níveis de desempenho.
3. THE SYSTEM SHALL disponibilizar uma rubrica padrão baseada nas 5 competências do ENEM (200 pontos cada, total 1000).
4. WHEN uma redação é enviada para correção, THE SYSTEM SHALL permitir selecionar uma ou mais rubricas a aplicar.
5. WHEN mais de uma rubrica é selecionada, THE SYSTEM SHALL produzir um resultado de correção independente por rubrica.
6. THE SYSTEM SHALL retornar, por rubrica, uma nota numérica por critério, a nota total e feedback textual justificando cada critério, em português.
7. THE SYSTEM SHALL transcrever o texto manuscrito/impresso da redação e armazenar a transcrição junto ao resultado.
8. IF a imagem não puder ser lida ou não contiver uma redação, THEN THE SYSTEM SHALL registrar o resultado como não-corrigível com o motivo.
9. THE SYSTEM SHALL persistir cada correção com referência à rubrica (e sua versão) utilizada.

---

## Requisito 3 — Correção de prova discursiva (gabarito ou conhecimento do modelo)

**User Story:** Como professor, quero corrigir provas discursivas escolhendo a
estratégia de correção (gabarito ou conhecimento do próprio modelo), para ter
flexibilidade conforme o tipo de prova.

> Nota: a estratégia por Knowledge Base (RAG) foi removida do escopo por não ser
> necessária ao núcleo (gabarito e modelo já cobrem os casos). Pode ser reintroduzida
> depois, com S3 Vectors, se surgir necessidade real.

#### Acceptance Criteria

1. THE SYSTEM SHALL suportar duas estratégias de correção de prova discursiva: (a) por gabarito de referência, (b) pelo conhecimento do próprio modelo (sem gabarito).
2. WHEN uma prova é enviada, THE SYSTEM SHALL transcrever os pares pergunta/resposta em uma estrutura JSON validada por schema.
3. THE SYSTEM SHALL corrigir cada questão individualmente e atribuir uma nota numérica por questão conforme uma escala configurável, substituindo a correção meramente binária da v1.
4. THE SYSTEM SHALL retornar, por questão, a nota e uma justificativa em português.
5. THE SYSTEM SHALL calcular e persistir a nota total da prova.
6. IF a estratégia escolhida for "gabarito" e não existir gabarito associado, THEN THE SYSTEM SHALL rejeitar a correção com mensagem explicativa.

---

## Requisito 4 — Criação de prova discursiva (tela de admin) com wizard de resposta

**User Story:** Como administrador/professor, quero criar uma prova discursiva
cadastrando as perguntas e as respostas de referência, com a opção de gerar a resposta
automaticamente a partir da pergunta, para montar gabaritos rapidamente.

#### Acceptance Criteria

1. THE SYSTEM SHALL fornecer uma tela de administração para criar e editar provas discursivas.
2. THE SYSTEM SHALL permitir adicionar, editar, reordenar e remover questões, cada uma com enunciado e resposta de referência.
3. WHEN o usuário aciona o "wizard de resposta automática" de uma questão, THE SYSTEM SHALL gerar uma proposta de resposta de referência a partir do enunciado usando um agente/modelo.
4. THE SYSTEM SHALL permitir que o usuário edite ou substitua a resposta gerada antes de salvar.
5. THE SYSTEM SHALL permitir associar a cada questão uma pontuação máxima e (opcionalmente) uma escala/critério de correção.
6. THE SYSTEM SHALL persistir a prova criada de forma que possa ser usada como gabarito na correção (Requisito 3, estratégia "gabarito").
7. THE SYSTEM SHALL versionar provas para não invalidar correções já realizadas com versões anteriores.

---

## Requisito 5 — Identificação de aluno/prova via QR/código de barras (TestID)

**User Story:** Como operador da correção, quero que o sistema leia um QR/código de
barras na folha contendo um TestID para identificar automaticamente o dono da prova e
os demais metadados, para não precisar associar manualmente cada submissão.

#### Acceptance Criteria

1. THE SYSTEM SHALL detectar e decodificar um QR code (ou código de barras) presente na imagem enviada.
2. THE SYSTEM SHALL usar como payload do código um **TestID** compacto e único, sem embutir dados pessoais diretamente no código.
3. THE SYSTEM SHALL manter uma base de dados que relaciona o TestID ao "dono" da prova e aos metadados associados (aluno, disciplina, prova, turma, etc.).
4. WHEN o TestID é decodificado, THE SYSTEM SHALL resolver os metadados completos a partir dessa base de dados.
5. IF nenhum código for detectado ou o TestID não existir na base, THEN THE SYSTEM SHALL marcar a submissão como "não identificada" e permitir associação manual posteriormente.
6. THE SYSTEM SHALL associar o resultado da correção ao aluno/prova resolvidos a partir do TestID.
7. THE SYSTEM SHALL gerar o TestID e o respectivo QR/código no momento da criação/impressão da prova, registrando o vínculo na base de dados.
8. THE SYSTEM SHALL garantir que o TestID seja único e não reutilizável entre provas/submissões distintas.

> **Modelo de dados (a detalhar no design):** o QR carrega apenas o `testId`. A base de
> vínculo (`TestRegistry`) resolve, no mínimo: `testId` (chave), `ownerId` (dono/professor
> responsável), `examId`/versão da prova, `studentId` (matrícula/RA), `disciplineId`,
> `classId`/turma, `academicPeriod` (ano/semestre) e, opcionalmente, `institutionId`
> (multi-tenant) e `pageNumber`/`totalPages`. Manter PII fora do QR preserva privacidade e
> permite revogar/reatribuir o vínculo sem reimprimir a prova.

---

## Requisito 6 — Reconhecimento de cartão resposta (novo módulo)

**User Story:** Como professor, quero enviar cartões resposta de múltipla escolha e ter
as marcações reconhecidas e corrigidas automaticamente contra um gabarito, para
corrigir provas objetivas em escala.

#### Acceptance Criteria

1. THE SYSTEM SHALL reconhecer as marcações (bolhas preenchidas) de um cartão resposta de múltipla escolha a partir de uma imagem.
2. THE SYSTEM SHALL suportar a definição do layout do cartão (número de questões e alternativas por questão).
3. WHEN um cartão é processado, THE SYSTEM SHALL produzir a alternativa marcada por questão e sinalizar marcações ambíguas, múltiplas ou ausentes.
4. THE SYSTEM SHALL corrigir o cartão contra um gabarito de múltipla escolha e calcular a nota.
5. THE SYSTEM SHALL reaproveitar a identificação por QR/código de barras (Requisito 5) para associar o cartão ao aluno/prova.
6. THIS módulo SHALL ser entregue de forma incremental (iniciado como capítulo próprio), podendo começar por um MVP de reconhecimento antes da correção em escala.

---

## Requisito 7 — Seleção de modelos e A/B testing em produção

**User Story:** Como responsável técnico, quero selecionar/trocar os modelos usados na
correção e configurar um segundo modelo para avaliação ou teste A/B em produção, para
comparar qualidade e custo antes de promover uma troca de modelo.

#### Acceptance Criteria

1. THE SYSTEM SHALL permitir configurar, sem alteração de código, qual modelo cada agente usa (via configuração/parametrização).
2. THE SYSTEM SHALL permitir definir um modelo primário e um modelo secundário (challenger) por capacidade de correção.
3. WHERE um modelo secundário estiver configurado para A/B testing, THE SYSTEM SHALL executar a correção também no challenger conforme uma política (ex.: percentual do tráfego) e registrar ambos os resultados para comparação.
4. THE SYSTEM SHALL registrar, por resultado, qual modelo/agente e qual versão produziram a correção.
5. THE SYSTEM SHALL permitir promover o modelo challenger a primário a partir da interface.
6. THE SYSTEM SHALL evitar que o resultado do challenger afete a nota oficial exibida ao aluno, salvo promoção explícita.

---

## Requisito 8 — Métricas, custo e qualidade (analytics reais)

**User Story:** Como gestor, quero ver dados analíticos reais de consumo de tokens,
custo, latência e qualidade das correções, para acompanhar o uso e a eficácia da
plataforma.

#### Acceptance Criteria

1. THE SYSTEM SHALL capturar, por invocação de agente/modelo, os tokens de entrada e saída, a latência e um custo estimado.
2. THE SYSTEM SHALL agregar métricas por período, por tipo de correção (redação, discursiva, cartão resposta), por modelo e por agente.
3. THE SYSTEM SHALL expor essas métricas por API para consumo do frontend, substituindo os dados simulados da v1.
4. THE SYSTEM SHALL registrar indicadores de qualidade da correção (ex.: taxa de sucesso, correções não-corrigíveis, divergência entre modelos primário/challenger).
5. THE SYSTEM SHALL emitir métricas operacionais para observabilidade (ex.: CloudWatch) além de persistir para análise histórica.

---

## Requisito 9 — Avaliação de modelos/agentes (AgentCore Evaluations)

**User Story:** Como responsável pela qualidade, quero avaliar a qualidade dos agentes e
modelos de forma gerenciada, tanto contra conjuntos de referência quanto sobre o tráfego
de produção, para medir objetivamente a qualidade da correção e comparar alternativas sem
manter um framework de avaliação próprio.

#### Acceptance Criteria

1. THE SYSTEM SHALL usar o **Amazon Bedrock AgentCore Evaluations** para pontuar a qualidade dos agentes a partir de seus traces (nível de sessão, resposta e/ou tool call).
2. THE SYSTEM SHALL suportar avaliação **online** (contínua, sobre amostra do tráfego de produção — incluindo o challenger em shadow) e **on-demand/batch** (contra um conjunto de referência).
3. THE SYSTEM SHALL definir avaliadores adequados à correção — no mínimo um avaliador **LLM-as-judge** (qualidade do feedback/aderência à rubrica) e, onde aplicável, um avaliador **code-based** (erro numérico da nota vs. referência) — usando avaliadores built-in e/ou custom.
4. THE SYSTEM SHALL cadastrar conjuntos de avaliação (ex.: redações/provas com nota e feedback de referência) e associá-los às execuções batch.
5. THE SYSTEM SHALL armazenar e exibir os resultados de avaliação por modelo/agente/versão e permitir comparação lado a lado (leaderboard), consumível pela tela de Avaliação de Modelos/Agentes.
6. WHERE existir A/B testing em produção (Requisito 7), THE SYSTEM SHALL alimentar as evaluations com os pares primário/challenger coletados via os traces do Runtime.

---

## Requisito 10 — Histórico de correções

**User Story:** Como professor, quero consultar o histórico de correções realizadas,
com filtros, para revisar e auditar resultados anteriores.

#### Acceptance Criteria

1. THE SYSTEM SHALL persistir todas as correções (redação, discursiva, cartão resposta) com metadados (aluno, prova, disciplina, data/hora, modelo, rubrica/estratégia).
2. THE SYSTEM SHALL exibir o histórico com filtros por tipo, período, aluno, disciplina e prova.
3. THE SYSTEM SHALL permitir abrir uma correção específica e ver transcrição, notas, feedback e fontes/citações.
4. THE SYSTEM SHALL permitir baixar/exportar o resultado de uma correção.

---

## Requisito 11 — Autenticação e autorização (Cognito)

**User Story:** Como administrador, quero que o acesso à plataforma seja autenticado e
autorizado, para proteger dados de alunos e restringir ações administrativas.

#### Acceptance Criteria

1. THE SYSTEM SHALL exigir autenticação via Amazon Cognito para acessar o frontend e as APIs.
2. THE SYSTEM SHALL rejeitar requisições não autenticadas às APIs (substituindo o acesso aberto da v1).
3. THE SYSTEM SHALL associar cada submissão/correção ao usuário autenticado responsável, substituindo o `student` fixo da v1.
4. THE SYSTEM SHALL suportar, no mínimo, os papéis "administrador" e "professor", restringindo a criação de provas/rubricas e a troca de modelos a perfis autorizados.
5. THE SYSTEM SHALL desabilitar o auto-cadastro (self-signup) no Cognito; a tela de login SHALL NOT oferecer criação de conta.
6. THE SYSTEM SHALL permitir a criação de novos usuários somente por um administrador (ex.: via console/admin API do Cognito ou uma tela administrativa restrita), nunca por fluxo público.
7. THE SYSTEM SHALL aplicar política de senha forte, verificação de e-mail/entrega de credenciais de forma segura e suportar MFA para os usuários.
8. WHEN um usuário é criado por um administrador, THE SYSTEM SHALL exigir troca de senha no primeiro acesso.

---

## Requisito 12 — Frontend com menu lateral

**User Story:** Como usuário, quero navegar por um menu lateral entre as áreas da
plataforma, para acessar rapidamente correção, criação, histórico, analytics,
evaluations e configurações.

#### Acceptance Criteria

1. THE SYSTEM SHALL apresentar um menu lateral com, no mínimo, os itens: Correção de Redação, Correção de Prova Discursiva, Criação de Prova Discursiva, Reconhecimento de Cartão Resposta, Histórico de Correções, Dados Analíticos, Avaliação de Modelos/Agentes, Rubricas de Redação e Configuração de Modelos.
2. THE SYSTEM SHALL ser construído com uma stack de build mantida e atual (migrando do Create React App descontinuado da v1).
3. THE SYSTEM SHALL exibir, na correção de redação, a seleção de uma ou mais rubricas e o resultado por rubrica/critério.
4. THE SYSTEM SHALL exibir, na correção de prova discursiva, a seleção da estratégia (gabarito/KB/modelo) e o resultado por questão.
5. THE SYSTEM SHALL exibir os dados analíticos (consumo de tokens, custo, qualidade) a partir de dados reais da API.
6. THE SYSTEM SHALL permitir, na Configuração de Modelos, selecionar o modelo primário e o secundário/challenger por capacidade.
7. THE SYSTEM SHALL suportar upload de imagens em múltiplos formatos comuns (ex.: PNG, JPG, PDF), corrigindo a limitação de `media_type` fixo da v1.

---

## Requisito 13 — Remoção de módulos legados e preservação da v1

**User Story:** Como mantenedor, quero remover os módulos de scanner e Alexa e preservar
a v1 como referência, para reduzir escopo e manter um histórico limpo.

#### Acceptance Criteria

1. THE SYSTEM SHALL NOT incluir os módulos de scanner e de Alexa skill na v2.
2. THE SYSTEM SHALL preservar o conteúdo da v1 em `OldVersion/` sem modificá-lo.
3. THE SYSTEM SHALL entregar a v2 na raiz do repositório, isolada da v1.

---

## Requisito 14 — Infraestrutura e implantação

**User Story:** Como engenheiro de plataforma, quero infraestrutura como código
reproduzível para provisionar e implantar a v2, para ter ambientes consistentes.

#### Acceptance Criteria

1. THE SYSTEM SHALL definir toda a infraestrutura (agentes/Gateway, APIs, armazenamento, autenticação, hospedagem do frontend) como código.
2. THE SYSTEM SHALL parametrizar região, modelos e configurações sensíveis, sem valores fixos no código.
3. THE SYSTEM SHALL fornecer instruções/automação de build e deploy reproduzíveis.
4. THE SYSTEM SHALL isolar dados por ambiente e evitar credenciais embutidas no código.
5. THE SYSTEM SHALL fornecer um `.env.example` versionado (sem segredos) como modelo de configuração de deploy; o `.env` real SHALL ser ignorado pelo git.
6. THE SYSTEM SHALL documentar no README o processo de deploy pelo próprio usuário: pré-requisitos, credenciais via `aws configure`/SSO (não estáticas no repo), bootstrap e deploy da infra (AWS CDK), deploy dos agentes no AgentCore Runtime (CodeZip, sem Docker), provisionamento do 1º admin (Cognito) e configuração dos modelos por capacidade.
7. THE SYSTEM SHALL NOT armazenar credenciais AWS estáticas no repositório nem em arquivo versionado.

---

## Requisito 15 — Harness de avaliação (dataset + runner sobre AgentCore Evaluations)

**User Story:** Como responsável pela qualidade, quero disparar avaliações repetíveis de
um alvo de correção (agente + modelo + estratégia + rubrica/gabarito) contra um dataset de
referência, para comparar modelos/agentes de forma padronizada — apoiado no AgentCore
Evaluations, sem reimplementar a mecânica de pontuação.

#### Acceptance Criteria

1. THE SYSTEM SHALL manter datasets/golden sets versionados (redações/provas com nota e feedback de referência) reutilizáveis entre alvos, em armazenamento próprio (S3/DynamoDB).
2. THE SYSTEM SHALL fornecer um **runner** fino que executa um "alvo de correção" versionado (agente + modelo + estratégia + rubrica/gabarito) sobre um dataset, produzindo os traces/sessões que serão pontuados.
3. THE SYSTEM SHALL delegar a pontuação ao **AgentCore Evaluations** (batch/on-demand), reutilizando os mesmos avaliadores da avaliação online (Requisito 9) — LLM-as-judge para qualidade do feedback e code-based para erro numérico da nota.
4. THE SYSTEM SHALL produzir relatórios comparáveis e versionados entre alvos (leaderboard por modelo/agente/versão), consumíveis pela tela de Avaliação de Modelos/Agentes (Requisito 9) e pelos Dados Analíticos (Requisito 8).
5. THE SYSTEM SHALL operar em dois modos apoiados no mesmo serviço de avaliação: (a) **offline/batch**, contra um golden set; (b) **online/shadow**, pontuando o challenger executado junto do primário em produção (Requisito 7) sem afetar a nota oficial.
6. THE SYSTEM SHALL registrar, para cada execução, o alvo avaliado, o dataset, os scores e os metadados de custo/tokens/latência, de forma auditável e reproduzível.
7. WHERE novos agentes/estratégias forem adicionados, THE SYSTEM SHALL permitir avaliá-los pelo mesmo runner/serviço sem alteração da mecânica de execução/pontuação (extensibilidade).

---

## Requisito 16 — Processamento assíncrono, enfileiramento e controle de throttling

**User Story:** Como operador, quero que as correções sejam processadas de forma
assíncrona por meio de uma fila com concorrência controlada, para suportar picos de
requisições (ex.: turma inteira enviada de uma vez) sem sofrer throttling do Bedrock nem
perder submissões.

#### Acceptance Criteria

1. THE SYSTEM SHALL processar correções de forma assíncrona, desacoplando a ingestão (upload/registro da submissão) da execução da correção por meio de uma fila.
2. WHEN uma submissão é registrada, THE SYSTEM SHALL responder imediatamente com um identificador e um estado inicial (ex.: "enfileirada"), sem bloquear até o fim da correção.
3. THE SYSTEM SHALL processar as mensagens com concorrência controlada, respeitando as quotas de invocação de modelo do Bedrock (TPM/RPM) para evitar `ThrottlingException`.
4. WHEN ocorrer throttling ou erro transitório, THE SYSTEM SHALL aplicar retry com backoff exponencial e jitter.
5. IF uma mensagem falhar após o número máximo de tentativas, THEN THE SYSTEM SHALL encaminhá-la para uma Dead Letter Queue (DLQ) com visibilidade do erro, sem perder a submissão.
6. THE SYSTEM SHALL expor o ciclo de vida de cada submissão (ex.: enfileirada, processando, concluída, falha) de forma consultável pelo frontend (polling ou notificação).
7. THE SYSTEM SHALL suportar envio em lote (múltiplas submissões/cartões de uma turma) com throughput previsível e sem perda de itens.
8. THE SYSTEM SHALL garantir idempotência: reprocessar a mesma submissão não SHALL gerar correção duplicada.
9. THE SYSTEM SHALL expor métricas de fila (profundidade, idade da mensagem mais antiga, contagem de throttling, throughput) para os Dados Analíticos (Requisito 8) e observabilidade.
10. WHERE houver A/B testing ou execução do harness (Requisitos 7 e 15), THE SYSTEM SHALL usar o mesmo mecanismo de fila/concorrência para suavizar os picos de invocação adicionais.

---

## Requisito 17 — Segurança de borda/rede e postura Well-Architected

**User Story:** Como responsável de segurança, quero que toda a superfície pública fique
exclusivamente atrás do Amazon CloudFront, com as origens protegidas e as boas práticas
do AWS Well-Architected aplicadas, para minimizar a superfície de ataque e proteger dados
de alunos.

#### Acceptance Criteria

1. THE SYSTEM SHALL servir o frontend e as APIs públicas exclusivamente através do Amazon CloudFront (ponto de entrada único).
2. THE SYSTEM SHALL impedir o acesso direto às origens (bucket do frontend e endpoint da API) por fora do CloudFront.
3. THE SYSTEM SHALL usar Origin Access Control (OAC) para o bucket S3 do frontend e bloquear todo acesso público ao bucket.
4. THE SYSTEM SHALL garantir que o endpoint da API só aceite requisições provenientes do CloudFront (ex.: validação de um segredo de origem injetado pelo CloudFront e/ou restrição por WAF/prefix list gerenciada do CloudFront).
5. THE SYSTEM SHALL associar um AWS WAF WebACL ao CloudFront com, no mínimo, regras gerenciadas contra ameaças comuns e limitação de taxa (rate limiting).
6. THE SYSTEM SHALL exigir HTTPS/TLS em todo o tráfego, redirecionando HTTP para HTTPS, com versões de TLS seguras.
7. THE SYSTEM SHALL restringir o CORS a origens conhecidas (o domínio do CloudFront), substituindo o `AllowOrigin: "*"` da v1.
8. THE SYSTEM SHALL manter os serviços internos (AgentCore Gateway, workers, filas, bancos) fora da internet pública, acessíveis apenas via IAM/autenticação interna, nunca diretamente pelo usuário final.
9. THE SYSTEM SHALL cifrar dados em repouso (S3, DynamoDB, SQS) e em trânsito (TLS).
10. THE SYSTEM SHALL aplicar privilégio mínimo de IAM por função/tool/agente (sem políticas excessivamente amplas como `AmazonBedrockFullAccess` usada na v1).
11. THE SYSTEM SHALL registrar logs de acesso e auditoria (ex.: logs do CloudFront, WAF e CloudTrail) para rastreabilidade.
12. THE SYSTEM SHALL manter segredos e parâmetros sensíveis em serviço apropriado (SSM Parameter Store/Secrets Manager), nunca no código ou no bundle do frontend.
13. THE SYSTEM SHALL definir cabeçalhos de segurança de resposta no CloudFront (ex.: HSTS, X-Content-Type-Options, política de segurança de conteúdo adequada ao app).
