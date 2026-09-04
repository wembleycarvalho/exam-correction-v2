# Arquitetura - Assistente Virtual Educacao e Saude

## Visao Geral

```
Cliente WhatsApp (+55 11 94574-6008)
        |
        v
AWS End User Messaging Social (WABA: Wembley AWS Test)
        |
        v (event destination direto, role: EndUserMessagingConnectRole)
Amazon Connect (instancia: connect-demo-ps)
        |
        v (fluxo: connect-whatsapp-interaction)
Connect AI Agent (triagem-educacao-saude) - tipo ORCHESTRATION
        |
        +---> MCP Tool: consultar_usuario (Gateway -> Lambda -> DynamoDB cadastro-usuarios)
        +---> MCP Tool: listar_cursos (Gateway -> Lambda -> DynamoDB catalogo-cursos)
        +---> MCP Tool: detalhe_curso (Gateway -> Lambda -> DynamoDB catalogo-cursos)
        +---> MCP Tool: consultar_academico (Gateway -> Lambda -> DynamoDB academico)
        +---> MCP Tool: gerar_boleto (Gateway -> Lambda -> S3 + WhatsApp Social Messaging)
        +---> MCP Tool: consultar_conteudo (Gateway -> Lambda -> DynamoDB + Bedrock KB)
        +---> Native Tool: connect_GetContactAttributes (le telefone do contato)
        +---> Return to Control: Escalate -> fila BasicQueue -> agente humano
        +---> Return to Control: Complete -> encerra conversa
```

## Componentes

### 1. WhatsApp (End User Messaging Social)
- WABA: waba-b7e8aaaa528c4a73a9dc4212f4323c79
- Phone: +55 11 94574-6008
- Event destination: direto pro Amazon Connect
- Role: EndUserMessagingConnectRole (trust: social-messaging.amazonaws.com, inline policy Action:*)
- IMPORTANTE: NUNCA re-setar event destination via API. Usar apenas console.

### 2. Amazon Connect
- Instancia: connect-demo-ps (82a1c25d-b923-4bd2-9c21-e7eba7f052ac)
- Fluxo: connect-whatsapp-interaction (acd511ac-afee-403b-9436-aa52f2f744cc)
- AI Agent: triagem-educacao-saude (criado pelo console, NAO via API)
- Prompt: connect-demo-ai-prompt (editavel pelo console)
- Lex Bot interno: connect-demo-conv-ai (KS8ONTST78) - gerenciado pelo Connect
- Integracao MCP: registrada no console (Integrations > MCP server)

### 3. AgentCore Gateway MCP (para Connect)
- Gateway: connect-jwt-gateway (connect-jwt-gateway-4njugyplcw)
- Auth: CUSTOM_JWT
- Discovery URL: https://connect-demo-ps.my.connect.aws/.well-known/openid-configuration
- allowedAudience: [gateway ID]
- Resource Policy: Principal: * com action bedrock-agentcore:InvokeGateway (OBRIGATORIO pra OAuth/JWT)
- Tags: AmazonConnectEnabled=true, owner=123456789012
- Role: AgentCoreGatewayRole
- Targets:
  - catalogo-cursos -> Lambda mcp-catalogo-cursos
  - user-lookup -> Lambda connect-user-lookup
  - academico -> Lambda mcp-academico
  - boleto -> Lambda mcp-boleto
  - conteudo -> Lambda mcp-vestibular

### 4. AgentCore Gateway MCP (para Harnesses)
- Gateway: harness-mcp-gateway (harness-mcp-gateway-tr8bba3cnq)
- Auth: AWS_IAM (harnesses nao suportam JWT)
- Mesmos targets Lambda

### 5. Bedrock AgentCore Harnesses
- harness_871f8 - Harness original (JWT auth via Cognito)
- harness_vendas - Consultor de vendas (com Gateway IAM)
- harness_alunos - Assistente academico
- harness_saude - Assistente de saude
- Memoria: Harness_memory_v1-RSSjzrBZAs

### 6. Lambda Functions
| Lambda | Funcao | DynamoDB |
|--------|--------|----------|
| mcp-catalogo-cursos | Lista/detalha cursos (graduacao + extensao) | catalogo-cursos |
| connect-user-lookup | Busca usuario por telefone (GSI) ou CPF (PK) | cadastro-usuarios |
| mcp-academico | Disciplinas, notas, provas, historico, financeiro por CPF | academico |
| mcp-boleto | Gera PDF de boleto fake e envia via WhatsApp | academico + cadastro-usuarios + S3 |
| mcp-vestibular | Consulta KB com filtro de metadata por perfil (aluno/nao-aluno) | cadastro-usuarios + academico + Bedrock KB |
| mcp-foto-cliente | Gera presigned URL para foto do cliente no S3 | cadastro-usuarios + S3 fotos-clientes |

### 7. DynamoDB
| Tabela | PK | GSI | Estrutura |
|--------|-----|-----|-----------|
| cadastro-usuarios | cpf (S) | telefone-index (telefone S) | Documento unico por usuario |
| catalogo-cursos | curso_id (S) | - | Graduacao (tipo ausente) e extensao (tipo=extensao) |
| academico | cpf (S) | - | Documento unico com disciplinas_atuais, provas, historico, financeiro |

### 8. IAM Roles
| Role | Funcao |
|------|--------|
| EndUserMessagingConnectRole | WhatsApp -> Connect (inline policy Action:*) |
| AgentCoreGatewayRole | Gateway -> Lambda |
| LambdaMCPCursosRole | Lambdas MCP -> DynamoDB |
| LambdaBoletoRole | Lambda boleto -> DynamoDB + S3 + Social Messaging |
| BedrockKBVestibularRole | Bedrock KB -> S3 Vectors + S3 Docs |
| ConnectHarnessLambdaRole | Lambdas harness |

### 9. Controle de Acesso por Metadata (KB)

A Knowledge Base (kb-vestibular, L2KOGGTB6K) armazena apostilas de disciplinas e conteudo publico.
O acesso e controlado via metadata filtering no Bedrock KB Retrieve.
Vector store: S3 Vectors (kb-vestibular-vectors-123456789012).

#### Como funciona

Cada documento no S3 tem um arquivo `.metadata.json` associado com atributos como `tipo`, `disciplina`, `modalidade`, `curso_id`.
Na hora do retrieve, a Lambda mcp-vestibular monta um filtro dinamico baseado no perfil do usuario.

#### Fluxo de controle de acesso

```
AI Agent chama consultar_conteudo(pergunta, cpf)
        |
        v
Lambda mcp-vestibular
        |
        +---> CPF informado?
        |       |
        |       +-- NAO --> filtro = {tipo: "publico"}
        |       |
        |       +-- SIM --> DynamoDB cadastro-usuarios (valida tipo=aluno)
        |                       |
        |                       +-- NAO e aluno --> filtro = {tipo: "publico"}
        |                       |
        |                       +-- SIM e aluno --> DynamoDB academico
        |                                               |
        |                                               v
        |                                   Coleta disciplinas_atuais[].nome
        |                                   + historico[].disciplinas[].nome
        |                                               |
        |                                               v
        |                                   filtro = orAll: [
        |                                       {tipo: "publico"},
        |                                       {disciplina IN [lista_permitidas]}
        |                                   ]
        |
        v
Bedrock KB Retrieve (com RetrievalFilter)
        |
        v
Retorna trechos relevantes pro AI Agent
```

#### Exemplos de filtro

Aluno (5o semestre, 25 disciplinas cursadas/cursando):
```python
filter = {
    "orAll": [
        {"equals": {"key": "tipo", "value": "publico"}},
        {"in": {"key": "disciplina", "value": [
            "Introducao a Programacao (Python)", "Logica Matematica",
            "Calculo I", "Comunicacao e Expressao",
            # ... todas as disciplinas cursadas + cursando
        ]}}
    ]
}
```

Nao-aluno (sem CPF ou tipo != aluno):
```python
filter = {"equals": {"key": "tipo", "value": "publico"}}
```

#### Estrutura no S3

```
kb-vestibular-demo-{account}/
├── publico/
│   ├── edital_vestibular_2026_2.pdf                       # tipo=publico
│   ├── edital_vestibular_2026_2.pdf.metadata.json
│   ├── sobre_instituicao.pdf                              # tipo=publico
│   └── sobre_instituicao.pdf.metadata.json
└── privado/
    ├── graduacao/eng-software/
    │   ├── introducao_programacao_python.pdf               # tipo=disciplina
    │   ├── introducao_programacao_python.pdf.metadata.json
    │   └── ... (40 disciplinas, 8 semestres)
    └── extensao/
        ├── ext-ia-aplicada/
        │   ├── ia_aplicada.pdf                            # tipo=disciplina
        │   └── ia_aplicada.pdf.metadata.json
        └── ... (15 cursos de extensao)
```

#### Metadata JSON

Disciplina de graduacao:
```json
{"metadataAttributes": {"tipo": "disciplina", "modalidade": "graduacao", "curso_id": "eng-software", "disciplina": "Introducao a Programacao (Python)", "semestre": "1"}}
```

Conteudo publico:
```json
{"metadataAttributes": {"tipo": "publico", "categoria": "vestibular"}}
```

## Fluxo de Dados

1. Cliente envia mensagem no WhatsApp
2. End User Messaging Social envia pro Connect (via EndUserMessagingConnectRole)
3. Connect executa fluxo connect-whatsapp-interaction
4. Fluxo seta idioma pt-BR, salva telefone como atributo
5. Cria sessao Q Connect (CreateWisdomSession) com AI Agent triagem-educacao-saude
6. Conecta cliente ao Lex Bot (AI Agent self-service)
7. AI Agent usa connect_GetContactAttributes pra ler telefone
8. AI Agent usa consultar_usuario (telefone -> CPF + dados)
9. AI Agent identifica o usuario e chama pelo nome
10. AI Agent usa MCP tools conforme necessidade (cursos, academico, conteudo, boleto)
11. Escalate/transferir_atendente -> Connect assistant (copiloto-atendente) -> set-queue -> transfer
12. Atendente recebe contato no CCP com:
    - Customer Profile (nome, CPF, tipo, curso)
    - Q Connect Assistant (copiloto-atendente) com tools MCP para consultar DynamoDB e KB
    - Historico da conversa do AI Agent

### Fluxo detalhado (connect-whatsapp-interaction)

```
enable-logging -> set-language (pt-BR) -> set-phone-attr ($.CustomerEndpoint.Address)
    -> CreateWisdomSession (AI Agent: triagem-educacao-saude)
        -> SetContactData (WisdomSession)
            -> ConnectParticipantWithLexBot (Lex: connect-demo-conv-ai, AI Agent self-service)
                -> check-tool-result ($.Lex.SessionAttributes.Tool)
                    = Escalate -> Connect assistant (copiloto-atendente) -> set-queue -> transfer
                    = transferir_atendente -> Connect assistant (copiloto-atendente) -> set-queue -> transfer
                    No Match -> disconnect
```

### 10. Copiloto do Atendente (Agent Assistance)

Quando o contato e escalado para um atendente humano, o bloco Connect assistant
configura o Q Connect com o AI Agent `copiloto-atendente` (tipo ORCHESTRATION).

O atendente pode usar o Q Connect Assistant no CCP para:
- Consultar dados academicos do aluno (notas, disciplinas, provas, historico)
- Buscar informacoes de cursos (catalogo, grade curricular)
- Consultar conteudo da KB (apostilas, edital, informacoes institucionais)
- Buscar dados cadastrais de usuarios

AI Agents configurados:
| Agent | Tipo | Funcao |
|-------|------|--------|
| triagem-educacao-saude | ORCHESTRATION | Self-service (WhatsApp) - atende o cliente |
| copiloto-atendente | ORCHESTRATION | Agent Assistance - copiloto do atendente no CCP |
| assistente-portugues-ar | ANSWER_RECOMMENDATION | Recomendacoes automaticas em pt-BR |
| assistente-portugues-ms | MANUAL_SEARCH | Busca manual em pt-BR |

Tools do copiloto-atendente:
- consultar_usuario (DynamoDB cadastro-usuarios)
- consultar_academico (DynamoDB academico)
- consultar_conteudo (Bedrock KB com filtro de metadata)
- listar_cursos (DynamoDB catalogo-cursos)
- detalhe_curso (DynamoDB catalogo-cursos)
- consultar_vestibular (Bedrock KB)
- gerar_boleto (S3 + WhatsApp Social Messaging)
- Retrieve (KB do Q Connect)

Comportamento proativo:
- Ao receber um contato transferido do bot, o copiloto analisa automaticamente o historico
  e gera um briefing com: resumo, dados do cliente, pontos de atencao, dicas e acoes sugeridas.
- O briefing aparece no painel Q Connect do Agent Workspace.
- Prompt: copiloto-atendente-prompt (Sonnet 4.5, editavel via API ou console)
- Docs: docs/PROMPT_COPILOTO_ATENDENTE.md

### 11. Customer Profiles

Dados dos usuarios sao sincronizados do DynamoDB (cadastro-usuarios) para o
Amazon Connect Customer Profiles. O atendente ve os dados no painel lateral do CCP.

- Domain: amazon-connect-connect-demo-ps
- Sync: scripts/sync_customer_profiles.py
- Campos mapeados: nome (FirstName/LastName), telefone, CPF (AccountNumber), tipo, curso, status
- Atributos customizados: cpf, tipo, status, curso, curso_id

### 12. Knowledge Base (Bedrock)

- KB ID: L2KOGGTB6K (recriada com S3 Vectors)
- Vector Store: S3 Vectors (bucket: kb-vestibular-vectors-123456789012, index: kb-vestibular-index)
- Docs Bucket: kb-vestibular-demo-123456789012
- Embedding Model: amazon.titan-embed-text-v2:0
- Conteudo: 168 PDFs (ementas + material didatico + newsletters + publico) com metadata filtering
- Q Connect KB: conteudo-institucional (f980bec2-5fab-4a67-b629-fbb5e22a6d3d) - 164 PDFs para o assistant do atendente

### 13. Fotos de Clientes

- Bucket: fotos-clientes-123456789012 (privado, public access bloqueado)
- CORS: permite GET de *.my.connect.aws e *.awsapps.com
- Lambda: mcp-foto-cliente (gera presigned URL valida por 1h)
- Role: LambdaFotoClienteRole (s3:GetObject + dynamodb:GetItem/Query)
- Estrutura: s3://fotos-clientes-123456789012/fotos/{cpf}.{jpg|png|webp}
- A Lambda tenta CPF formatado (123.456.789-00) e so-digitos (12345678900)
- Gerenciamento: scripts/upload_foto_cliente.py (upload, list, delete, bulk)

### 14. Painel de Briefing do Atendente (Screen Pop)

Quando um contato e escalado para atendente humano, um painel visual (Show View)
aparece no Agent Workspace com foto, resumo da conversa, sentimento, intencao e dicas.

Arquitetura (mesmo padrao da conta demo-gabinova):

```
Bot escala (Tool=Escalate)
  -> check-tool-result [Escalate/transferir_atendente]
  -> set-lex-attrs (captura $.Lex.SessionAttributes - opcional)
  -> invoke-briefing-lambda (connect-agent-briefing)
  -> set-briefing-attrs (salva briefing_* como contact attributes)
  -> set-agent-ui-hook (UpdateContactEventHooks: DefaultAgentUI = fluxo screen pop)
  -> copiloto-atendente -> set-queue -> transfer

Quando o atendente ACEITA o contato:
  -> fluxo agent-briefing-screen-pop dispara (via DefaultAgentUI event hook)
  -> Show View renderiza a view briefing-atendente com os contact attributes
```

Componentes:
- Lambda: connect-agent-briefing (Role: LambdaAgentBriefingRole)
  - Busca dados do cliente (DynamoDB), foto (presigned URL), situacao financeira
  - Busca o TRANSCRIPT da conversa via connect:ListRealtimeContactAnalysisSegmentsV2 (Contact Lens)
  - Gera resumo, sentimento, intencao e dicas com Bedrock (Claude Haiku 4.5)
  - IMPORTANTE: o resumo e gerado a partir do transcript real, NAO depende do bot
    preencher session attributes (que se mostraram nao confiaveis para parametros de tool)
- View: briefing-atendente (CUSTOMER_MANAGED) - layout com Image, AttributeSection,
  AttributeBar, Alert, TextArea (foto, dados, sentimento, intencao, resumo, dicas)
- Fluxo: agent-briefing-screen-pop (CONTACT_FLOW) - contem o bloco Show View
- Event hook: DefaultAgentUI no fluxo principal aponta para o screen pop flow
- Teste: scripts/test_chat_escalate.py (chat via websocket que dispara escalate)

Contact attributes populados (briefing_*):
- briefing_nome, briefing_telefone, briefing_tipo, briefing_curso, briefing_financeiro, briefing_foto_url (da Lambda)
- briefing_resumo, briefing_sentimento, briefing_intencao, briefing_dicas (Bedrock sobre o transcript)

### 15. Aba Historico do Cliente (Timeline)

Aba adicional no Agent Workspace (ao lado de Customer Profile e Cases) com a linha do
tempo de TODAS as interacoes anteriores do cliente, organizadas por data.

```
Escalate -> ... -> set-briefing-attrs
  -> invoke-timeline-lambda (connect-customer-timeline)
  -> set-timeline-attr (briefing_timeline)
  -> set-agent-ui-hook -> copiloto -> queue -> transfer
```

Componentes:
- Lambda: connect-customer-timeline (Role: LambdaCustomerTimelineRole)
  - search_contacts (ultimos 55 dias) + get_contact_attributes para casar pelo telefone
  - Reutiliza briefing_resumo armazenado; quando ausente, gera resumo do transcript com Bedrock
  - Retorna timeline_markdown (texto formatado por data) + timeline_count
  - Permissoes: connect:SearchContacts, DescribeContact, GetContactAttributes, ListRealtimeContactAnalysisSegmentsV2, bedrock:InvokeModel
- View: historico-cliente (CUSTOMER_MANAGED) - TextArea read-only com a timeline
- Contact attribute: briefing_timeline (setado no caminho de escalate)
- Workspace Page (config manual no console):
  - UI Management > Workspaces > workspace-atendente > Add page
  - Slug: historico | View: historico-cliente
  - Input data: {"timeline_text":{"DefaultValue":"$.#briefing_timeline"}}

## Configuracoes Criticas

### Gateway JWT + Connect
- allowedAudience DEVE ser o Gateway ID
- Resource policy DEVE usar Principal: * (wildcard) pra OAuth/JWT
- Registrar como integracao MCP pelo console do Connect
- AI Agent criado pelo console (NAO via API)
- Prompt editado pelo console (prompts via API dao erro Unauthorized)
- Habilitar "Agente de IA" no bloco Get Customer Input do fluxo

### Sessoes de Chat
- Sessoes ficam ativas mesmo apos encerrar no CCP
- Usar scripts/manage_sessions.py kill antes de testar
- Novas mensagens vao pra sessao ativa existente

### 16. Canal de Voz (Voice Inbound) e Outbound

#### Voz Inbound (toll-free)
- Numero: +18667787229 (toll-free US) associado ao fluxo `connect-voice-inbound`
- Fluxo `connect-voice-inbound` (a915ca30-...): clone do connect-whatsapp-interaction adaptado para voz.
- Reaproveita os MESMOS recursos: AI agent self-service (bot-nova pt_BR), Lambdas
  connect-agent-briefing e connect-customer-timeline, fila BasicQueue, painel screen pop.
- Adaptacoes de voz (ver .kiro/steering/connect-licoes-aprendidas.md):
  - Ordem: enable-logging -> set-language(pt-BR) -> set-tts-voice(Camila) -> recording(Voice) -> set-phone-attr -> Wait 4s -> ai-agent
  - Recording em VoiceBehavior (RealTime + AutomatedInteraction, IVRRecordingBehavior Enabled)
  - Wait 4s antes do AI agent (evita escalacao indevida por audio inicial vazio)
  - Bloco Lex com Text=" " (espaco) para o AI agent fazer a propria saudacao
- Script: scripts/create_voice_inbound_flow.py

#### Outbound (ligacoes de saida)
- A fila BasicQueue tem caller ID configurado (OutboundCallerConfig) com +18667787229.
- Script: scripts/set_outbound_caller_id.py
- Para ligar para o exterior (ex: Brasil): adicionar o pais na allow-list (console:
  AWS Console > Connect > instancia > Telephony - sem API) e usar um caller ID DID real
  (toll-free nao faz outbound internacional; numeros "555" sao ficticios).
