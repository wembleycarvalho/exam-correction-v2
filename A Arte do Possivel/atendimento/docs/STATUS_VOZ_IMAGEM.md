# Status - Voz e Imagem no WhatsApp (Amazon Connect)

Data: 2026-08-27. Conta 123456789012, us-east-1. Instancia Connect `82a1c25d-b923-4bd2-9c21-e7eba7f052ac`.

## Objetivo
Cliente envia **voz** ou **imagem** no WhatsApp; o bot interpreta e responde **no mesmo formato**
(voz->voz, texto->texto), com troca sob demanda ("responde por texto/audio"). Imagem: modelo de
visao interpreta e o agente responde (ex: corrigir prova a partir de prints).

## Arquitetura implementada (gateway de voz/midia)
Substituimos o event destination nativo (WhatsApp -> Connect direto) por um gateway:

```
WhatsApp -> End User Messaging Social -> SNS (whatsapp-inbound) -> Lambda wpp-gateway-inbound
   - audio: get_whatsapp_message_media (OGG) -> Amazon Transcribe Streaming (pt-BR) -> texto
   - imagem: get_whatsapp_message_media (JPEG) -> Bedrock Claude (visao) -> transcricao/descricao
   - texto: direto
   -> StartChatContact no MESMO flow (acd511ac) + StartContactStreaming + participant connection
   -> injeta a mensagem (texto/transcricao/descricao) no chat
   -> grava sessao (DynamoDB whatsapp-connect-sessions) com last_modality

Amazon Connect (flow + AI agent orchestration 69d86b4f / prompt 3d787af2)
   -> responde -> contact streaming -> SNS (whatsapp-connect-streaming) -> Lambda wpp-gateway-outbound
   -> se last_modality=voice: Bedrock Polly (Camila generative) -> ffmpeg OGG/Opus -> nota de voz (voice:true)
   -> senao: texto
   -> send_whatsapp_message
```

### Recursos criados (scripts/setup_voice_infra.py)
- DynamoDB `whatsapp-connect-sessions` (PK contactId, GSI customerId-index; guarda connectionToken,
  participantToken, systemNumber, last_modality)
- S3 `whatsapp-media-123456789012` (privado, lifecycle 1 dia)
- SNS `whatsapp-inbound` (policy: EUM Social publica) e `whatsapp-connect-streaming` (policy: Connect publica)
- IAM role `LambdaWppGatewayRole` (dynamodb, s3 get/put/list, socialmessaging get/post/send,
  connect StartChatContact/StartContactStreaming/DescribeContact, transcribe streaming, polly, bedrock invoke)
- Layers: `ffmpeg-layer` (x86, /opt/bin/ffmpeg) e `wpp-voice-deps` (amazon-transcribe + awscrt linux + requests)
- Lambdas: `wpp-gateway-inbound`, `wpp-gateway-outbound` (x86_64, python3.12)

### Lambdas
- `lambdas/wpp_gateway_inbound.py` - entrada (parse SNS, audio/imagem/texto, StartChatContact, sessao,
  override de modalidade por pedido do usuario). Autoteste `_selftest` (transcribe).
- `lambdas/wpp_gateway_outbound.py` - saida (streaming -> WhatsApp; voz via Polly+ffmpeg; anexos do
  atendente via signed url). Autoteste `_selftest` (synth).

## O que FUNCIONA (validado)
- Transcricao de voz (Transcribe Streaming, pt-BR) - fiel, ~2-4s.
- Sintese de voz de saida (Polly Camila generative -> OGG/Opus -> nota de voz) - chega no WhatsApp.
- Regra "mesmo formato": voz->voz, texto->texto.
- Override de formato: "responde por texto/audio/email" (deteccao por palavra-chave no gateway).
- Interpretacao de imagem (Bedrock Claude visao) - transcreve o conteudo (ex: prova) e injeta no chat.
- StartChatContact -> flow -> AI agent (com tools consultar_academico, gerar_boleto, consultar_conteudo etc.)
  -> streaming -> outbound. Preserva o fluxo/tools existentes.
- Prompt `:4` do agente com regras ENTREGA (entregar em vez de prometer) e CONTINUIDADE.

## CAUSA RAIZ DA DESCONEXAO (medido) + FIX ATUAL
Medicao: um contato ocioso desconecta em **~300s (5 min)**, mesmo com o idle timer do participante
desativado (update_participant_role_config Unset). Ou seja, o timeout e a **sessao do bot Lex/AI
agent (~5 min esperando input)**, nao o idle do chat. Nao da pra manter um contato "aguardando" a
proxima mensagem alem de ~5 min. Por isso, apos uma pausa >5min, a mensagem seguinte cai num contato
morto e nao e respondida (afetava voz, texto e imagem).

Fato importante: o AI agent NAO responde a InitialMessage (turno 1 = so saudacao); ele responde a
partir do turno 2. Dentro de um contato vivo, turnos 2+ sao respondidos normalmente (com tools).

FIX IMPLEMENTADO (contato novo por mensagem + turno-2):
- Cada mensagem abre um contato NOVO (elimina a corrida dos 5 min).
- StartChatContact com saudacao vazia (Text do bloco Lex = " ", InitialMessage = " ") = turno 1.
- Apos ~5s, envia a mensagem real do cliente como TURNO 2 (que o agente responde).
- Contexto entre mensagens nao persiste (cada msg = contato novo) - aceitavel dado o limite de 5 min.
- Custo: +~5s de latencia por mensagem. A validar com teste real (usuario registrado responde de
  verdade; testes com numero fake sao enganosos porque consultar_usuario nao encontra e o bot
  degrada).

Tentativas ja feitas (cada uma com efeito colateral):
1. Reuso de contato + checar `DisconnectTimestamp` (contact_is_live): reduz, mas ha janela de corrida
   (~1-2s) em que o contato esta vivo na checagem e desconecta logo apos o envio.
2. Contato novo por mensagem: elimina a corrida, mas o AI agent **nao responde a InitialMessage**
   (turno 1 = so saudacao), entao a mensagem nao e respondida.
3. Prompt "nunca use Complete" (v:4): o orchestrator do Connect encerrou mesmo assim - nao confiavel.

Observacao chave: dentro de um contato VIVO, o agente responde os turnos 2+ normalmente (com tools).
O problema e (a) turno 1 nao responder e (b) o disconnect apos o agente concluir.

### Opcoes de correcao (a fazer com teste controlado)
- **Flow sem disconnect**: apos o bloco do bot, em vez de `DisconnectParticipant`, voltar/loopar
  mantendo o chat aberto (com `Text=" "` para nao re-saudar). RISCO: loop desenfreado se o agente
  concluir sem esperar input; precisa de guarda/teste.
- **Persistent chat**: contato novo por mensagem com `PersistentChat`/rehydration para carregar
  contexto; resolver o turno-1 (ex: greet-then-send com espera adequada). RISCO: rehydration pode
  re-emitir mensagens antigas no streaming (reenvio); precisa validar.
- **Orquestracao no gateway**: chamar o agente/Bedrock direto do Lambda e gerenciar a conversa;
  re-arquitetura maior (perde integracao nativa de escala/screen-pop).

## Estado atual (config)
- Event destination: SNS whatsapp-inbound (gateway ativo). Rollback para nativo: `scripts/rollback_voice.py`.
- Flow `acd511ac`: bloco Lex com `Text="Ola! Como posso ajudar?"`, `set-phone-attr` lendo `$.Attributes.phone`.
- Prompt do agente: `3d787af2:4` (ENTREGA + CONTINUIDADE). Rollback: `python3 scripts/repoint_agent_prompt.py 1`.
- Inbound: modelo de REUSO + checagem de contato vivo.

## Scripts relevantes
- `scripts/setup_voice_infra.py` - infra (SNS, DynamoDB, S3, IAM). Idempotente.
- `scripts/setup_voice_layers.py` - layers ffmpeg + deps.
- `scripts/deploy_voice_lambdas.py` - deploy das 2 lambdas + subscriptions.
- `scripts/flip_to_voice.py` - cutover (event destination -> SNS + ajuste do flow).
- `scripts/rollback_voice.py` - rollback total (event destination -> Connect + restaura flow).
- `scripts/repoint_agent_prompt.py <versao>` - aponta o AI agent para uma versao do prompt.
- `scripts/update_prompt_continuidade.py` - cria versao do prompt com regras ENTREGA+CONTINUIDADE.
- `scripts/test_voice_smoke.py` - smoke (Polly+ffmpeg -> Transcribe).
- `scripts/test_integration_startchat.py`, `scripts/test_outbound_voice.py` - testes de integracao.

## Backups
- `backups/voice_migration_20260826_191052/` - estado ORIGINAL (event destination + flows) + rollback.
- `backups/flip_*/`, `backups/flow_greeting_*/`, `backups/prompt_*/` - snapshots por etapa.

## Comportamento pratico atual (workaround)
Quando o bot parar de responder (contato desconectou), mandar "oi" reabre; a partir do 2o turno ele
responde (voz/texto/imagem). O fix definitivo do disconnect esta na lista de opcoes acima.
