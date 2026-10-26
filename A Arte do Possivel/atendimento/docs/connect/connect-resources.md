---
inclusion: always
---

# Amazon Connect - Mapa de Recursos (instancia connect-demo-ps)

## Instancia
- ID: `82a1c25d-b923-4bd2-9c21-e7eba7f052ac` (alias: connect-demo-ps)
- URL admin: https://connect-wembley.my.connect.aws
- ATENCAO: o `CONNECT_INSTANCE_ID` no `.env` pode estar desatualizado (`ff227fe7...`). O ID correto e `82a1c25d...` (confirmado no CONNECT_QUEUE_ARN).

## Fluxos (Contact Flows)
| Nome | ID | Uso |
|------|-----|-----|
| connect-whatsapp-interaction | `acd511ac-afee-403b-9436-aa52f2f744cc` | WhatsApp/chat inbound |
| connect-voice-inbound | `a915ca30-7098-478a-9542-3a192779dc4f` | Voz inbound (toll-free) |
| agent-briefing-screen-pop | `f944e9cf-6849-49f8-ad24-312abf30b553` | Show View do painel (via DefaultAgentUI) |

## Q in Connect
- Assistant: `4c588966-3671-4170-b53d-a6115502e9d1`
- AI Agent self-service (orchestration): `9fe5ed34-f493-44a5-817e-85c912116f71` (agent-nova)
- AI Agent copiloto-atendente: `69d86b4f-bb2e-4984-b4a1-570062837755`
- Prompt ativo: `51dff123-b8fd-4d8c-8915-2963041f2804` versao `:2` (prompt-nova)
- Lex bot: `bot-nova` (alias IIGUGVMZDL/TSTALIASID, locale pt_BR)

## Views / Lambdas / Fila
- View painel: briefing-atendente (`13a21bf5-65f2-4fd1-b364-2f61ed32e644`)
- Lambda briefing: `connect-agent-briefing` (foto + dados + resumo via transcript + Bedrock)
- Lambda timeline: `connect-customer-timeline`
- Lambda lookup: `connect-user-lookup`
- Bucket fotos: `fotos-clientes-123456789012` (PRIVADO)
- Fila: BasicQueue (`1e2366ac-a64e-4016-b0a1-0599a13110e7`)

## Numeros de telefone
| Numero | Tipo | Uso |
|--------|------|-----|
| +5511945746008 | DID BR | WhatsApp (End User Messaging Social) - NAO reaproveitar pra voz |
| +18667787229 | Toll-free US | Voz inbound (associado ao connect-voice-inbound). Caller ID outbound da BasicQueue. NAO faz outbound internacional. |
| +15557401578 | DID US "555" | FICTICIO - NAO usar (a API rejeita como caller ID) |

## Backups
- Backups completos em `backups/FULL_<timestamp>/` (flows, views, ai-agent, prompt, _RESOURCE_MAP.json)
- Restaurar painel/briefing: `scripts/restore_briefing_setup.py <backup_dir>`
