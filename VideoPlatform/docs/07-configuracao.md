# Configuração (tela de Config + tabela de settings)

Todos os **parâmetros de comportamento** da plataforma vivem na tabela DynamoDB
`videoplatform-settings` e são editáveis no menu **Config** — sem alterar código
nem fazer redeploy.

## Princípio

- **Nenhum parâmetro de comportamento hardcoded** nos handlers. Em runtime, cada
  handler lê os valores da tabela (`getSettings()` em `backend/src/lib/common.js`,
  com cache de 30s por instância da Lambda).
- O código mantém apenas **identidade de infraestrutura** (nomes de tabela/bucket,
  prefixos de pasta, `ACCOUNT_ID`, região) — mudá-los recria recursos/quebra dados,
  então não são "configuração".
- Os **defaults + metadados** (rótulo, descrição, tipo, categoria) ficam no seed
  `backend/src/infra/seed-settings.js`, aplicado no deploy por um custom resource.
  O seed só cria o que **ainda não existe** (`attribute_not_exists`), então
  redeploys adicionam chaves novas mas **nunca sobrescrevem** valores editados.

## Como funciona

```
Tela de Config (frontend)
   │  GET /api/settings  (lista com label/descrição/tipo/categoria)
   │  PUT /api/settings  (grava novos valores)
   ▼
DynamoDB videoplatform-settings  (1 item por parâmetro)
   ▲
   │  getSettings() — cache 30s
Handlers (pipeline + API + worker)  ← leem os valores em runtime
```

- Editou na tela → grava no DynamoDB → novos processamentos usam o valor novo em
  até ~30s. Não precisa redeploy.
- A tela agrupa por categoria e mostra a descrição de cada parâmetro.

## Parâmetros (categorias)

| Categoria            | Exemplos de chave |
|----------------------|-------------------|
| Modelos              | `model.voxtral`, `model.voxtralMini`, `model.pegasus` |
| Idiomas              | `lang.transcribe`, `lang.translations` |
| Legenda SDH          | `sdh.speechMarginSec`, `sdh.minEventSec`, `sdh.maxEventSec`, `sdh.maxAudioMB`, `sdh.audioSampleRate` |
| Entrega e segurança  | `delivery.signedCookieTtlSec` |
| Transcode (ABR)      | `transcode.renditions` (JSON) |
| Custos (tarifas USD) | `cost.mediaConvertPerOutputMin`, `cost.transcribePerAudioMin`, `cost.translatePerChar`, `cost.voxtralInputPer1k`, `cost.voxtralOutputPer1k`, `cost.voxtralMiniInputPer1k`, `cost.voxtralMiniOutputPer1k`, `cost.pegasusPerMin`, `cost.s3PerGbMonth` |

Cada item guarda: `settingKey`, `value` (string), `type`
(`string|number|csv|json|bool`), `category`, `label`, `description`, `unit`,
`editable`, `order`, `updatedAt`.

## Observações

- Alguns parâmetros afetam **apenas novos processamentos** (ex.:
  `transcode.renditions`, `sdh.audioSampleRate`), pois valem no momento do
  transcode/geração.
- A tela de Config fica atrás do login (JWT do Cognito), como o resto da API.
- Para adicionar um novo parâmetro: inclua no seed (`seed-settings.js`), suba o
  `SeedVersion`, faça deploy (o custom resource adiciona a chave) e leia no
  handler via `getSettings()`.
