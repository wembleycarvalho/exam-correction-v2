# Campanhas WhatsApp Outbound (Amazon Connect) — fiel ao CSV

Disparo nativo de um template WhatsApp aprovado para uma lista de destinatários (CSV),
usando **Amazon Connect Outbound Campaigns** + **Customer Profiles** + **Q in Connect (Wisdom)**.

## Arquitetura (o que realmente funciona)

```
CSV (phone,var1,var2...)
  │
  ├─ put_profile_object (object type Campaign-<slug>)  → cria/atualiza perfis (var1..varN)
  ├─ segmento por PhoneNumber (fiel ao CSV)            → seg-<slug>
  │
  ▼
connectcampaignsv2 create_campaign (type=MANAGED, agentless WhatsApp)
  ├─ source = customerProfilesSegmentArn (seg-<slug>)
  ├─ connectCampaignFlowArn = flow CAMPAIGN "campanha-<slug>-flow"
  │      └─ bloco SendWhatsAppMessage → WisdomMessageTemplateArn (template ATUAL)
  ├─ channelSubtypeConfig.whatsApp.defaultOutboundConfig.wisdomTemplateArn
  ├─ schedule (startTime >= agora+5min, obrigatorio) + communicationTimeConfig (open hours)
  ├─ tag owner = ARN da instancia
  └─ start_campaign
  │
  ▼
Service role AWSServiceRoleForConnectCampaigns:
  GetMessageTemplate + SendOutboundChatMessage → social-messaging:SendWhatsAppMessage → Meta
```

## CAUSAS-RAIZ que impediam o envio (todas corrigidas — NÃO repetir)

Sintoma: campanha ia para `Completed` sem enviar nada, **sem erro visível**. As falhas eram
**IAM AccessDenied/UnauthorizedException silenciosos** na service role do connect-campaigns.
Fonte de verdade para diagnosticar: **CloudTrail** (chamadas da service role) e o
**EventBridge `aws.social-messaging`** (status real de entrega).

1. **Binding da variável errado.** A referência correta para atributo custom de perfil é
   `{{Attributes.Customer.Attributes.varN}}` (validado via `qconnect RenderMessageTemplate`,
   `attributesNotInterpolated: []`). `{{var1}}`, `{{Customer.Attributes.var1}}` etc. NÃO resolvem.

2. **Tags obrigatórias `AmazonConnectCampaignsEnabled=True`.** A policy
   `AmazonConnectCampaignsServiceLinkedRolePolicy` tem condições:
   - `social-messaging:SendWhatsAppMessage` exige `AmazonConnectEnabled=True` no **phone-number-id**.
   - `wisdom:GetMessageTemplate`/`RenderMessageTemplate` exige `AmazonConnectCampaignsEnabled=True`
     no **message template E no knowledge base**. Sem isso → `UnauthorizedException` silencioso.

3. **O flow da campanha precisa apontar para o template ATUAL.** No modo `agentless`, é o
   **flow** (`SendWhatsAppMessage`) que envia — usando o `WisdomMessageTemplateArn` embutido no
   flow. Se o flow apontar para um template antigo/deletado, o envio falha em silêncio, mesmo
   que o `wisdomTemplateArn` da campanha esteja certo. `campaign_lib.ensure_campaign_flow`
   sempre reconstrói o flow com o template atual.

Outros pré-requisitos já satisfeitos: instância onboarded para outbound campaigns; número
WhatsApp CLAIMED; `communicationTimeConfig` com timezone padrão (senão o destinatário pode ser
descartado por timezone); schedule com início >= agora+5min (mínimo da API).

## Como disparar

Pré-requisito: template aprovado na Meta.

### Via CLI (loader)
```bash
source .env && python3 scripts/campaign_load_profiles.py --template <nome_template> arquivo.csv
```
CSV: coluna `phone` (com DDI) obrigatória + `var1,var2,...` na ordem das variáveis do template.
O loader grava os perfis, monta template+flow+segmento+campanha e inicia. Envio ocorre na
janela do schedule (~5-6 min depois — mínimo da API; não dá para reduzir).

### Via HTML (tester)
`tools/campaign_tester/server.py` → aba **Campanha (CSV)**: seleciona template, carrega CSV
(valida os campos), "Disparar" faz o mesmo fluxo do loader.

### Preparar só os recursos reusáveis (sem CSV)
```bash
source .env && python3 scripts/campaign_setup.py --template <nome_template>
```
Cria/atualiza message template (tagueado) + campaign flow + object type. A campanha em si
nasce no disparo (com os telefones do CSV).

## Como monitorar a entrega (sem depender do console)

EventBridge `aws.social-messaging` → CloudWatch Logs `/aws/events/wpp-camp-debug`:
`WhatsApp Message Handover Succeeded (accepted) → Sent → Delivered → Read`, com `errors` em caso
de falha. Para erros de autorização da campanha, use **CloudTrail** (EventName
`GetMessageTemplate`, `SendOutboundChatMessage`, filtrando a role `AWSServiceRoleForConnectCampaigns`).

## Modelo: uma campanha NOVA por disparo (sem reuso)

Cada disparo cria uma **campanha nova** e um **segmento dedicado** — não reutiliza campanha
(o reuso não re-disparava, pois o schedule é one-shot). `campaign_lib.dispatch_campaign`:

1. **Dedup de perfis por telefone** (`dedupe_profiles_by_phone` + `merge_profiles`) — garante
   1 perfil por número no disparo, evitando envio duplicado (o AutoMerging do domínio é batch).
2. Garante message template (binding+tags) e campaign flow (template atual).
3. Cria **segmento dedicado** `seg-<label>-<AAAAMMDD-HHMMSS>` (fiel ao CSV, por PhoneNumber).
4. Cria **campanha nova** com nome `<label>-<AAAAMMDD-HHMMSS>` (rótulo do HTML/`--name` +
   data/hora → sem colisão) e a inicia.

No HTML há o campo **Nome da campanha** (o rótulo). No CLI, use `--name`.

## Follow-ups conhecidos

- O domínio já tem AutoMerging por PhoneNumber (batch); o dedup no disparo cobre o gap de tempo.
- Campanhas/segmentos antigos (do modelo de reuso) podem ser apagados sem impacto — cada
  disparo agora usa recursos com nome único.
