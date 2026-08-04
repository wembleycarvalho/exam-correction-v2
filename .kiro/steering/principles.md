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

- Toda invocação de modelo registra tokens, custo e latência.
- Tudo como código (CDK, 1 stack), parametrizado por ambiente, deploy reproduzível.
- Verificar cada mudança (validate/build/test) antes de considerar concluída.
