# Atendimento — omnichannel com Amazon Connect (demo do portal)

Capítulo **Atendimento** do portal *A Arte do Possível WEB*. Demonstra um **assistente de
atendimento** (educação/saúde) sobre **Amazon Connect** + **WhatsApp** + **voz**, com bot
self-service (AI Agent), **copiloto do atendente** (Agent Assistance), **MCP tools** via
AgentCore Gateway, **Knowledge Base (RAG)** institucional/vestibular e **campanhas WhatsApp
outbound**.

## Problema real
Atendimento ao aluno/candidato em escala: tirar dúvidas (cursos, notas, financeiro, boleto,
vestibular), identificar o usuário pelo telefone, resolver no self-service e, quando escala
para humano, entregar ao atendente um **briefing pronto** + copiloto que consulta os dados.

## Proveniência (import do projeto Harness)
Este diretório foi **importado** de `~/Documents/GenIA/Labs/Harness` (assistente WhatsApp/voz
que roda na **mesma instância Amazon Connect** que o portal já abre: `connect-demo-ps`). É
**código de referência** — a meta é **reembalar na identidade do portal** (sem a UI verde de
WhatsApp do original), trazendo as capacidades para dentro do portal.

- **Account-id neutralizado:** o account-id real do original foi substituído pelo placeholder
  `123456789012` em todo o módulo. Valores reais vêm de **env/SSM** no reempacotamento (nada
  de conta específica no repo).
- **Não** foram importados: `.env` (segredos), `backups/`, `output/`, `fotos/` (imagens de
  clientes demo). `.env.example` está incluído como referência de variáveis.
- AI Agents do Connect (triagem, copiloto) são **criados/editados pelo console** (não via
  API) — parte da infra é manual; o que automatizamos são Lambdas/tools/campanhas.

## O que tem aqui
```
atendimento/
  lambdas/        # MCP tools + gateways (backend reutilizável):
                  #   mcp_catalogo_cursos, connect_user_lookup, mcp_academico, mcp_boleto,
                  #   mcp_vestibular (KB c/ metadata filter), mcp_foto_cliente,
                  #   connect_agent_briefing (screen-pop), connect_customer_timeline,
                  #   connect_harness_*, wpp_gateway_inbound/outbound (voz/imagem), lex_*
  scripts/        # setup de infra + campanhas + voz (setup_gateway, setup_dynamodb,
                  #   setup_lambdas, setup_kb_s3vectors, sync_customer_profiles, campaign_*,
                  #   setup_voice_*, etc.) — referência p/ reprovisionar
  tools/campaign_tester/   # server.py: testador de templates + disparo de campanha (HTML local)
  docs/           # ARQUITETURA.md, SETUP.md, PROMPT_COMPLETO.md, PROMPT_COPILOTO_ATENDENTE.md,
                  #   CAMPANHAS.md, STATUS_VOZ_IMAGEM.md, HARNESS_ORIGINAL_README.md
  docs/connect/   # lições aprendidas + inventário de recursos do Connect (do Harness)
  tests/          # testes do Harness (CLI/integração)
  .env.example    # variáveis (Connect instance, WABA, phone id, KB, buckets…)
```

## Alinhamento com a steering
- **Agentes:** preferir **AgentCore Runtime** (microVM). O **chat in-portal** do assistente
  (Fase 2) deve reaproveitar o padrão **EKS/Strands** do Gateway Inference **só** por causa do
  **streaming ao browser** (exceção documentada) — ou, sem streaming, ficar no Runtime.
- **KB:** **reutilizar** a KB existente (institucional/vestibular) em vez de criar nova;
  **S3 Vectors** por padrão; GraphRAG/Neptune só se o caso virar relacional/multi-hop.
- **Borda/segurança:** tudo atrás do CloudFront; JWT do portal; sem segredos/account-id no
  repo; IAM de privilégio mínimo por Lambda/tool.

## Plano de reempacotamento (portal)
- **Fase 1 — Campanhas + Testador de templates como view nativa ✅ IMPLEMENTADA** (deploy/verificação
  pendentes): backend Lambda em `api/` sob `/atendimento/api/*` (auth JWT do portal) + views
  nativas no `frontend/app.js` (menu **Atendimento → Templates WhatsApp / Campanhas**), na
  identidade do portal (sem a UI verde do WhatsApp). Ver "Fase 1 — como rodar" abaixo.
- **Fase 2 — Chat in-portal do assistente:** reaproveitar EKS/Strands + as MCP tools como
  ferramentas do agente; evita o problema de CSP/iframe do Connect (que hoje força abrir em
  janela separada) e ganha streaming/observability/guardrail que já temos.
- **Fase 3 — Copiloto / screen-pop / timeline / voz:** vivem no **Agent Workspace do Connect**
  (Show View / Q Connect). "Trazer" = versionar Lambdas/scripts aqui e documentar; a UX
  permanece no workspace do Connect.

## Fase 1 — como rodar

Estrutura nova (Fase 1):
```
atendimento/
  api/            handler.py (Lambda proxy) + campaign_lib.py (co-localizado)
  deploy/         standalone_stack.py, app.py, cdk.json, requirements.txt,
                  cloudfront_behavior.py (/atendimento/*), deploy.sh, teardown.sh
```

Rotas (`/atendimento/api/*`, JWT do portal): `GET health`, `GET templates`,
`GET template?metaTemplateId=..`, `GET campaign/format?metaTemplateId=..`,
`POST send` (1-a-1 transacional), `POST campaign/send` (cria campanha + dispara).

Deploy cirúrgico (não redeploya o portal; reproduzível; sem Docker):
```bash
cd atendimento/deploy && ./deploy.sh
```
O `deploy.sh`: semeia `SSM /atendimento/*` (waba-id, phone-number-id, campaign-bucket,
cp-domain, meta-api-version — defaults = recursos de demo do Harness, sobrescrevíveis por
env), garante o bucket `campanhas-connect-<acct>`, builda a layer boto3, faz `cdk deploy`
da stack `atendimento` (Lambda + HTTP API + authorizer Cognito importado do portal + IAM
least-privilege), liga o behavior `/atendimento/*` no CloudFront e publica o `app.js`.

Verificação: `GET https://<api-domain>/atendimento/health` (sem token) ou, pela borda,
`GET https://<cloudfront>/atendimento/api/health` (com token do portal); depois abrir o
portal em **Atendimento → Templates WhatsApp** (lista/preview) e **Campanhas** (CSV).

Config no SSM (sobrescrevível por env no deploy): `WABA_ID`, `WHATSAPP_PHONE_NUMBER_ID`,
`CAMPAIGN_BUCKET`, `CP_DOMAIN`, `META_API_VERSION`, `CONNECT_INSTANCE_ID`. A instância
Connect, o KB Wisdom de campanhas e o phone ARN de origem usam defaults de demo (env
`CONNECT_INSTANCE_ID`, `CAMPAIGN_WISDOM_KB_ID`, `CAMPAIGN_PHONE_ARN`).

> **Envio real:** `POST send` e `POST campaign/send` disparam WhatsApp de verdade
> (transacional / campanha). São ações que o usuário aciona pela UI — não fazem parte da
> verificação automatizada.

Teardown do módulo (mantém Connect/WABA/KB/portal): `cd atendimento/deploy && ./teardown.sh`.

## Cuidados conhecidos
- **Instância Connect compartilhada** com o Harness: mudar flow/event-destination afeta os
  dois. O **gateway de voz/imagem** troca o event destination (blast-radius maior) — não trazer
  isso sem necessidade.
- **Voz/imagem no WhatsApp:** tem limitação conhecida de **desconexão em ~5 min** de sessão do
  bot (contornada parcialmente) — ver `docs/STATUS_VOZ_IMAGEM.md`.
- **Campanhas:** dependem de tags `AmazonConnectCampaignsEnabled=true` e binding correto de
  variável (`{{Attributes.Customer.Attributes.varN}}`) — ver `docs/CAMPANHAS.md`.
