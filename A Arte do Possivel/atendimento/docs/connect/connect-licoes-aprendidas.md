---
inclusion: always
---

# Amazon Connect - Licoes Aprendidas (gotchas tecnicos)

Conhecimento adquirido resolvendo problemas reais. Consultar ANTES de mexer nesses temas.

## Painel de Briefing do Atendente (Screen Pop)
- O painel visual aparece via **UpdateContactEventHooks com DefaultAgentUI** apontando para um fluxo separado (agent-briefing-screen-pop) que contem o bloco ShowView. NAO e via 3P App nem workspace page.
- Fluxo: no caminho de Escalate -> invoke lambda briefing -> set contact attributes (briefing_*) -> UpdateContactEventHooks(DefaultAgentUI=fluxo screen pop) -> copiloto -> set-queue -> transfer.
- Quando o atendente ACEITA o contato, o fluxo screen pop dispara e renderiza a view.
- Resumo/sentimento/dicas: gerados pela **Lambda buscando o transcript** via `connect:ListRealtimeContactAnalysisSegmentsV2` (Contact Lens) + Bedrock. NAO depender de session attributes do Escalate tool (ver abaixo).

## ShowView via API
- O bloco ShowView **nao pode ser adicionado via `update_contact_flow_content`** no fluxo principal de forma confiavel (da InvalidContactFlowException).
- Funciona quando criado via `create_contact_flow` em um fluxo dedicado. Por isso o screen pop e um fluxo separado.
- Custom views NAO aparecem como aba (tab) ao lado de Customer Profile/Cases durante screen pop. Use card dentro da view do briefing.

## AI Agent (Q in Connect) - Escalate tool e session attributes
- Para o bot passar dados na escalacao (escalationSummary, sentiment, customerIntent, dicas), e preciso ADICIONAR essas propriedades ao **inputSchema do tool Escalate** (RETURN_TO_CONTROL). So instruir no prompt NAO basta.
- O Escalate tool deve ter `toolId: "Escalate"` e NAO ter campo `description` (apenas `instruction`) - igual a conta de referencia.
- PORÉM: na pratica os parametros do Escalate **nem sempre populam** `$.Lex.SessionAttributes.*` de forma confiavel (so o `Tool=Escalate` popula sempre). Por isso a abordagem robusta e gerar o resumo na Lambda a partir do transcript.
- O AI Agent usa uma VERSAO especifica do prompt (`promptId:N`). Editar o `$LATEST` NAO afeta o agente ate criar nova versao E apontar o agente para ela via `update-ai-agent`.

## update-ai-agent (orchestration) - boto3 vs CLI
- O boto3 instalado pode nao suportar `orchestrationAIAgentConfiguration` (da SDK_UNKNOWN_MEMBER / "Unknown parameter"). Usar **AWS CLI** (`aws qconnect update-ai-agent --configuration file://...`).
- Ao reenviar a config, tools **MCP** (Retrieve, QueryAssistant) NAO permitem override de `inputSchema`/`description`. Manter apenas: `toolName, toolType, toolId, overrideInputValues, userInteractionConfiguration`. Preservar `overrideInputValues` do Retrieve (binding da KB).

## Security Profile Applications - update bloqueado
- `update_security_profile` exige reenviar TODAS as applications. Se o namespace do gateway estiver stale, TODAS as permissoes dao "Invalid application permission" e o update fica bloqueado via API.
- Remover 3P app de Security Profile = fazer pelo console (Users > Security profiles > Agent Applications).

## Fluxo de VOZ (clonado do WhatsApp)
- O fluxo CONTACT_FLOW serve para voz E chat. `ConnectParticipantWithLexBot` funciona nos dois.
- Para voz, adaptar:
  1. **Ordem critica**: set-language(pt-BR) ANTES de set-tts-voice. Senao o 1o prompt sai em espanhol.
  2. Adicionar `UpdateContactTextToSpeechVoice` (Camila, Generative, pt-BR).
  3. Recording block: trocar ChatBehavior por **VoiceBehavior** com `AnalyticsModes: ["RealTime","AutomatedInteraction"]` e `IVRRecordingBehavior: Enabled`. Remover error types de chat (InFlightRedactionConfigurationFailed).
  4. Adicionar **Wait ~4s** antes do AI agent (senao o 1o input de audio chega vazio/ruido e o bot escala indevidamente).
  5. Para cair direto no fluxo sem saudacao fixa: o campo `Text` do bloco Lex e obrigatorio, mas pode ser `" "` (espaco) - o AI agent faz a propria saudacao.

## Outbound (ligacoes de saida)
- Erro "Invalid outbound configuration": a fila de saida (default outbound queue do routing profile) precisa de caller ID. Setar via `update_queue_outbound_caller_config`.
- Numeros "555" (+1555...) sao FICTICIOS e a API rejeita como caller ID.
- Toll-free geralmente NAO faz outbound internacional.
- Erro "Invalid number / unable to complete": destino fora da **allow-list de paises** (console: AWS Console > Connect > instancia > Telephony, NAO tem API) e/ou caller ID incompativel.
- Inbound toll-free NAO precisa de allow-list (so outbound precisa).

## Phone number -> Flow
- `associate_phone_number_contact_flow` (boto3 connect) associa o numero a um contact flow inbound. O `TargetArn` do describe-phone-number mostra a INSTANCIA, nao o fluxo (normal).

## Contact Lens / transcript
- Transcript em tempo real (durante a conversa): `connect:ListRealtimeContactAnalysisSegmentsV2` com `OutputType=Raw, SegmentTypes=["Transcript"]`.
- Chamadas muito curtas podem nao ter analise ("Real-time contact analysis not found").

## Teste de chat via API (sem WhatsApp real)
- `scripts/test_chat_escalate.py` inicia chat e conversa com o bot. PRECISA de **websocket** (create_participant_connection com Type WEBSOCKET) - so REST nao engaja o Lex.
- Limitacao: chat via API nao tem `CustomerEndpoint.Address`, entao `set-phone-attr` zera o phone -> campos que dependem de telefone (nome/foto/timeline) ficam vazios no teste. No WhatsApp real funcionam.
- MCP gateway tools podem falhar no chat via API (auth JWT diferente) -> escalacoes degradadas.

## AI Agent perdeu as tools do gateway ("dificuldades tecnicas")
- Sintoma: no WhatsApp (+5511945746008) o bot responde "Estou tendo dificuldades tecnicas para
  acessar suas informacoes financeiras" e oferece atendente. Nos logs do gateway
  (`/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/connect-jwt-gateway-4njugyplcw`)
  NAO ha nenhuma entrada na hora da conversa, e as Lambdas de tool (mcp-academico etc.) nao sao
  invocadas -> a chamada nem chega ao gateway.
- Causa raiz: o AI Agent de orquestracao **agent-nova** (`9fe5ed34...`, assistant `4c588966...`)
  ficou so com `Complete, Escalate, Retrieve, QueryAssistant`. As 6 tools do gateway
  (`academico___consultar_academico`, `boleto___gerar_boleto`, `user_lookup___consultar_usuario`,
  `catalogo_cursos___listar_cursos`, `catalogo_cursos___detalhe_curso`,
  `conteudo___consultar_conteudo`) + `connect_GetContactAttributes` sumiram da config (um
  update/publish anterior reenviou a config sem elas). O gateway e a integracao MCP continuavam
  saudaveis (o **copiloto-atendente** `69d86b4f...` ainda tinha as tools -> serviu de fonte).
- Diagnostico rapido:
  `aws qconnect get-ai-agent --assistant-id <A> --ai-agent-id 9fe5ed34-... --query 'aiAgent.configuration.orchestrationAIAgentConfiguration.toolConfigurations[].toolName'`
  Se faltarem as `*___*` do namespace `gateway_connect-jwt-gateway-...`, e isso.
- Fix: reenviar a config do agent-nova incluindo as tools do gateway (copiar as entradas exatas do
  copiloto). toolId no formato `gateway_connect-jwt-gateway-4njugyplcw__<target>___<tool>`,
  toolName `<target>___<tool>`. Regras de limpeza MCP valem (so toolName/toolType/toolId/
  overrideInputValues/userInteractionConfiguration). Preservar o `overrideInputValues` do Retrieve.
  Aplicar via `aws qconnect update-ai-agent ... --visibility-status PUBLISHED --configuration file://...`.
- Validacao: chat de teste com CPF conhecido (`123.456.789-00`, Wembley Carvalho) pedindo
  "situacao financeira" -> o bot retorna as mensalidades (Junho/2026 em aberto) e o gateway
  registra `tools/call academico___consultar_academico`.
- Observacao lateral: ha webhooks de status `failed`/"phone number malformed" para
  `recipient +000000000000` chegando no `wpp-gateway-inbound` (callbacks de delivery de um envio
  de campanha/template quebrado). Sao ruido, nao afetam o chat; investigar separadamente se o
  envio de campanha estiver falhando.
