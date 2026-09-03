# Princípios de Engenharia — Exam Correction v2

Estes princípios valem para todo design, código e decisão de infraestrutura da v2.
Na dúvida entre duas opções, escolha a que respeitar melhor esta ordem: **simplicidade →
serverless → segurança → custo**.

## 1. Simplicidade primeiro

- Não criar complexidade que não exista no problema. Resolver o requisito pedido, sem
  camadas, abstrações ou generalizações especulativas.
- Preferir a solução mais direta que atenda ao requisito e às restrições (segurança/custo).
- Não adicionar dependências, serviços ou componentes sem necessidade clara. Cada peça
  nova precisa se justificar por um requisito.
- Evitar orquestrações e infra "enterprise" quando um fluxo simples resolve.

## 2. Serverless por padrão + serviços novos, simples e seguros

- Preferir serviços serverless e gerenciados: Lambda, API Gateway HTTP, SQS, DynamoDB,
  S3, CloudFront, Cognito, Step Functions (só quando necessário).
- **Preferir serviços novos e gerenciados** quando eles simplificam a operação e aumentam
  a segurança (menos código próprio, credenciais gerenciadas, governança central). Ex.:
  usar o **AgentCore Runtime** para hospedar os agentes e o **AgentCore Evaluations** para
  medir qualidade, em vez de hand-rollar hospedagem e harness/scorers próprios.
- **AgentCore primeiro (regra travada):** para qualquer capacidade agêntica — hospedar
  agente, memória de conversa, busca na web, tools via MCP, avaliação/A-B, observabilidade
  de agente — **sempre dar preferência ao AgentCore** (Runtime, Memory, Gateway + conectores
  como `web-search`, Evaluations, Observability) em vez de reimplementar na mão ou colar
  serviço externo/API com chave. Só fugir do AgentCore com justificativa explícita de
  requisito (ex.: recurso indisponível na região) — e registrar o motivo. O fato de um
  recurso do AgentCore estar em preview **não** é impeditivo neste projeto (é demo).
- **Agentes**: implementados com **Strands** e hospedados no **AgentCore Runtime** (deploy
  CodeZip, sem Docker local), chamando modelos via **Bedrock Converse direto**. O
  **Correction Worker (Lambda)** apenas faz a ponte `SQS → InvokeAgentRuntime` (sem lógica
  de agente e sem streaming). O **AgentCore Gateway** só entra se/quando houver modelos no
  Mantle a rotear (futuro).
- **Qualidade e A/B** usam **AgentCore Evaluations** (online + batch), alimentado pelos
  traces do Runtime — não reimplementar avaliação na mão.
- Preferir o deploy **CodeZip** (Python puro, sem container). Dependências nativas (ex.:
  OpenCV para cartão resposta) ficam isoladas em layer/tool dedicada.
- Sem servidores para manter, sem escalonamento manual. Pagar pelo uso.

## 3. Segurança sempre

- Tudo público **somente atrás do CloudFront**; origens protegidas (S3 com OAC + Block
  Public Access; API só via header secreto — Opção A). Serviços internos nunca expostos à
  internet. (WAF removido neste projeto de teste; readicionar em produção.)
- **Cognito sem self-signup**; usuários criados apenas por admin; MFA e senha forte.
- **Privilégio mínimo de IAM** por função/tool/agente. Nunca políticas amplas como
  `AmazonBedrockFullAccess`/`AWSLambdaExecute` (erros da v1).
- Criptografia em repouso e em trânsito. Segredos em SSM/Secrets Manager, nunca em código
  ou no bundle do frontend.
- CORS restrito ao domínio do CloudFront. PII fora do QR (só `testId`).

## 4. Custo consciente

- Escolher o modelo certo para cada tarefa: modelo forte só onde precisa (visão/correção);
  modelo econômico para tarefas simples. Modelos sempre parametrizados (SSM), nunca fixos
  no código.
- Concorrência calibrada às quotas para evitar throttling e retrabalho.
- Preferir on-demand/pay-per-use; evitar capacidade provisionada sem necessidade.
- Medir custo por invocação (tokens/custo/latência) desde o início; otimizar com dado, não
  com achismo.

## 5. Mensurável e reproduzível

- **Observabilidade em TUDO (regra travada):** todo componente que executa (agentes no
  AgentCore Runtime, Lambdas, Gateway/web-search, Memory, workers) **deve** nascer com
  observabilidade **ligada**, não como afterthought. Concretamente:
  - **Traces:** habilitar **AgentCore Observability** (OpenTelemetry) em todo Runtime/Gateway
    — nunca desligar `--disable-otel`. Traces alimentam também as Evaluations.
  - **Métricas de negócio via CloudWatch EMF:** toda invocação de modelo emite **tokens
    (in/out/total), custo estimado, latência** e **uso de ferramentas** (ex.: chamadas ao
    Gateway/web-search, ao Athena, erros de tool). Emitir EMF como **linha JSON própria** no
    stdout do componente (o CloudWatch extrai a métrica); custo estimado a partir de tabela
    de preços **parametrizada por modelo** (env/SSM), nunca preço fixo escondido no código.
  - **Namespace por módulo** com dimensões úteis (Módulo, Modo, ModelId) para dá pra fatiar
    custo/consumo por perfil e por modelo (base para decisão de A/B e de troca de modelo).
  - **Logs estruturados** (JSON) com correlação por sessão/`submissionId`.
- Toda invocação de modelo registra tokens, custo e latência (ver acima) — desde o dia 1.
- Tudo como código (CDK, 1 stack), parametrizado por ambiente, deploy reproduzível.
- Verificar cada mudança (validate/build/test) antes de considerar concluída, incluindo
  **confirmar que as métricas/traces aparecem** no CloudWatch antes de dar a tarefa por feita.
