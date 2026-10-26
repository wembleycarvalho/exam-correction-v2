# Legenda SDH por IA (Voxtral) e Descrição de vídeo (Pegasus)

Duas capacidades de GenAI que ouvem/entendem a mídia de verdade, com **custos
separados** e UI para **comparar legendas** e exibir a **descrição sincronizada**
com o play.

> A legenda SDH é gerada por um modelo que **ouve o áudio** (Voxtral): detecta a
> fala E os sons não-falados (`[música]`, `[risos]`, `[suspiro]`).

## Modelos (Amazon Bedrock, confirmados na conta)

| Capacidade        | Modelo                                   | API         | Entrada |
|-------------------|------------------------------------------|-------------|---------|
| Legenda SDH       | `mistral.voxtral-small-24b-2507`         | Converse    | ÁUDIO (bytes inline) |
| Descrição vídeo   | `us.twelvelabs.pegasus-1-2-v1:0`         | InvokeModel | VÍDEO (via S3) |

Observações de API (validadas em teste real):
- **Voxtral** só aceita áudio por **bytes** (não aceita S3). Formatos aceitos:
  **wav/mp3** (m4a/flac/ogg não funcionaram). A pipeline gera um `track.wav`
  (16 kHz mono) via MediaConvert (Container RAW + codec WAV).
- **Pegasus** não é modelo Converse — usa **InvokeModel** com
  `{inputPrompt, mediaSource:{s3Location:{uri,bucketOwner}}}` e responde
  `{message}`. Lê o vídeo direto do S3.

## 1. Legenda SDH por IA (Voxtral) — uma passada, com chunking

O Voxtral **ouve o áudio** e gera a legenda SDH completa em uma única passada:
a **fala** transcrita (pt-BR, com timestamps) **e** os **marcadores de som**
não-falados (`[música]`, `[aplausos]`, `[risos]`, `[trovão]`, `[suspiro]`...),
que são essenciais para quem não ouve. O **Pegasus NÃO participa** do SDH — ele
é só para a descrição de conteúdo (seção 2).

```
track.wav (16kHz mono)
   → fatiamento em janelas (chunking) de ~60s com sobreposição
   → Voxtral por fatia (prompt SDH): fala + [marcadores de som]
   → reposiciona timestamps (offset da fatia) e costura pelas fronteiras
   → limpeza (normaliza rótulos, funde marcadores repetidos, duração mínima)
   → legenda SDH `pt-sdh` (WebVTT)
```

**Chunking (vídeos longos).** O request do Voxtral tem limite de corpo (~3 MiB
em base64 ≈ ~60s de WAV 16 kHz/mono). Para durações maiores, o WAV PCM é fatiado
em janelas (puro JS, sem ffmpeg), cada fatia é legendada em paralelo (limitado),
os timestamps recebem o offset da fatia e as fatias são costuradas pelo ponto
médio da sobreposição — sem palavras cortadas nem duplicadas na emenda.

- Rodado de forma **assíncrona** (worker Lambda, 15 min / 2048 MB) porque o API
  HTTP corta em 30s. A API retorna `sdhStatus = processando`; o frontend faz
  polling até `pronto`/`erro`. Resiliência a throttling do Bedrock (retry com
  backoff).
- Custo: `cost.sdhUSD` = tokens do Voxtral (input+output) × tarifa. O custo
  **substitui** o anterior a cada regeração (não acumula).
- Tudo parametrizável na tela de Config (categoria "Legenda SDH"): `sdh.prompt`
  (estilo dos marcadores), `sdh.chunkSec`, `sdh.chunkOverlapSec`,
  `sdh.chunkConcurrency`, `sdh.maxChunks`, `sdh.maxAudioMB` (teto por fatia),
  `sdh.voxtralMaxTokens`, `sdh.minCueSec`, `sdh.mergeMarkerGapSec`.

## 2. Descrição de vídeo (Pegasus)

- O Pegasus recebe o vídeo (S3) e devolve **segmentos cronológicos**
  `[{start,end,text}]` cobrindo cena, ação e áudio.
- Salvo em `video-profiles/{id}/description/description.json`.
- Também **assíncrono** (worker Lambda + polling `descriptionStatus`).
- Custo: `cost.descriptionUSD` = duração (min) × tarifa (o InvokeModel não
  retorna tokens no corpo; usamos estimativa por duração).

## 3. UI

- **Revisão (Biblioteca)**: botões "Gerar legenda SDH" e "Gerar descrição"
  (com status em tempo real). O seletor de idioma inclui `Português (SDH)`.
- **Comparar legendas (lado a lado)**: componente com duas faixas selecionáveis
  (Transcribe × SDH × traduções), alinhadas por tempo.
- **Player**: seletor de legenda (troca de faixa ao vivo) + painel de
  **descrição que acompanha o play** (o trecho atual é destacado e rola sozinho;
  clicar num trecho pula o vídeo para aquele tempo).

## 4. Custos separados (requisito)

`cost` no DynamoDB e colunas próprias no Analytics:

| Técnica                 | Campo            |
|-------------------------|------------------|
| Transcode (MediaConvert)| `transcodeUSD`   |
| Legenda (Transcribe)    | `transcribeUSD`  |
| Traduções (Translate)   | `translateUSD`   |
| **Legenda SDH (Voxtral)** | `sdhUSD`       |
| **Descrição (Pegasus)**   | `descriptionUSD` |
| Total                   | `totalUSD`       |

Tarifas na tabela de **settings** (categoria "Custos", editáveis na tela de
Config): `cost.voxtralInputPer1k`, `cost.voxtralOutputPer1k`, `cost.pegasusPerMin`
etc. São estimativas — a fonte de verdade é o Cost Explorer.

## 5. Faixas de legenda (nomenclatura)

| Faixa     | Origem |
|-----------|--------|
| `pt`      | Transcribe (fala) |
| `pt-sdh`  | Voxtral 24B 1 passada (fala + sons, SDH) |
| `pt-sdh-mini` | Voxtral Mini 1 passada (SDH) |
| `pt-sdh-2p` | Voxtral 24B 2 passadas (SDH) |
| `es`,`en` | Traduções (Translate) |

## 6. Próximos passos

- Descrição (Pegasus) em vídeos longos: a chamada única é lenta (minutos) e pode
  esbarrar em limite de duração — avaliar amostragem/segmentação do vídeo.
- Capturar tokens reais do Pegasus (headers do InvokeModel) para custo exato.
- Opção de traduzir a partir da faixa SDH.
