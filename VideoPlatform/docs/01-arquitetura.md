# Arquitetura — VideoPlatform

Protótipo VOD serverless na AWS (`us-east-1`, conta única). Pay-per-use em todos
os componentes: você só paga pelo que processar/armazenar/entregar.

## 1. Componentes

| Camada            | Serviço AWS                         | Papel |
|-------------------|-------------------------------------|-------|
| Login             | Amazon Cognito (User Pool)          | Autenticação; emite JWT para a API |
| Frontend          | S3 + CloudFront                     | Hospeda a SPA React |
| API               | API Gateway (HTTP API) + Lambda     | Upload, status, revisão, legenda, tradução, play, analytics |
| Metadados         | Amazon DynamoDB                     | Registro do vídeo, status, metadados, plays, custo |
| Armazenamento     | Amazon S3 (bucket privado)          | `raw-videos/` (bruto) e `video-profiles/` (saídas) |
| Orquestração      | AWS Step Functions                  | Encadeia transcode + legenda + atualização de status |
| Transcode         | AWS Elemental MediaConvert          | HLS ABR 1080/720/480/360 |
| Legenda           | Amazon Transcribe                   | Fala → WebVTT (pt-BR) |
| Tradução          | Amazon Translate                    | WebVTT pt-BR → es/en (sob demanda, na revisão) |
| Entrega           | CloudFront + OAC + cookies assinados + WAF | Streaming protegido |
| Custos            | Cost Explorer + Cost Allocation Tags + CloudWatch | Monitoramento (sem alertas nesta fase) |

## 2. Fluxo de upload

1. Usuário autenticado abre o menu **Upload**.
2. Frontend chama `POST /uploads` na API. A Lambda:
   - gera um `videoId` (UUID — a "unique ID" registrada no DynamoDB);
   - cria o item no DynamoDB com `status = enviando` (o objeto ainda **não**
     existe no S3);
   - devolve credenciais de **multipart upload** (presigned) para
     `raw-videos/{videoId}/source.<ext>`.
3. Frontend faz o upload direto ao S3 em partes (sem limite de tamanho prático),
   exibindo progresso. Enquanto não concluir, o vídeo permanece em `enviando`.
4. O `ObjectCreated` no prefixo `raw-videos/` dispara a pipeline, que então
   muda o status de `enviando` → `processando`.

> Se o upload for abandonado (usuário fecha a aba antes do fim), o objeto nunca
> se materializa, o `ObjectCreated` não dispara e o registro fica em `enviando`
> (nunca em `processando`). O multipart incompleto é abortado automaticamente
> pela regra de ciclo de vida do bucket (2 dias).

> O upload vai **direto do navegador para o S3** (presigned). O arquivo bruto
> nunca passa pela API/Lambda, então não há limite de tamanho imposto por nós.

## 3. Pipeline de processamento (Step Functions)

```
S3 ObjectCreated(raw-videos/*)
      │
      ▼
[Lambda trigger] ──> inicia execução da State Machine (com videoId)
      │
      ├─(paralelo)─> [MediaConvert]  cria HLS ABR → video-profiles/{videoId}/hls/
      │                               (renditions 1080p, 720p, 480p, 360p)
      │
      └─(paralelo)─> [Transcribe]    pt-BR → WebVTT → video-profiles/{videoId}/legenda/{videoId}.pt.vtt
      │
      ▼
[Lambda finalize]
      ├─ sucesso: calcula custo estimado (min de saída × tarifa + min transcrição × tarifa)
      │           grava no DynamoDB e seta status = "revisar"
      └─ falha:   status = "erro" + motivo
```

- A conclusão do MediaConvert é capturada por regra do **EventBridge**
  (`MediaConvert Job State Change` → `COMPLETE`/`ERROR`), que retoma a State Machine
  via *task token* (padrão `waitForTaskToken`).
- O Transcribe é consultado da mesma forma (callback por evento/polling).

## 4. Estrutura no S3

```
s3://<bucket-privado>/
├── raw-videos/
│   └── {videoId}/source.mp4           # bruto (mantido; sem Glacier nesta fase)
└── video-profiles/
    └── {videoId}/
        ├── hls/
        │   ├── master.m3u8            # playlist mestre (ABR)
        │   ├── 1080p/…                # segmentos
        │   ├── 720p/…
        │   ├── 480p/…
        │   └── 360p/…
        └── legenda/
            ├── {videoId}.pt.vtt       # gerada pelo Transcribe
            ├── {videoId}.es.vtt       # (opcional) tradução sob demanda
            └── {videoId}.en.vtt       # (opcional) tradução sob demanda
```

> Decisão: o "profile" não é um `.mp4` por pasta e sim **HLS** (playlist +
> segmentos). É isso que entrega **ABR** (o player troca de resolução sozinho
> conforme a banda) e **legenda selecionável** no mesmo manifesto.

## 5. Modelo de dados (DynamoDB)

### Tabela `Videos`
| Atributo        | Tipo   | Observação |
|-----------------|--------|------------|
| `videoId` (PK)  | S      | UUID gerado no upload |
| `status`        | S      | `enviando` \| `processando` \| `revisar` \| `pronto` \| `erro` |
| `title`         | S      | preenchido na revisão |
| `description`   | S      | preenchido na revisão |
| `sourceKey`     | S      | chave do bruto no S3 |
| `hlsKey`        | S      | chave do `master.m3u8` |
| `subtitles`     | M/L    | lista de idiomas disponíveis (`pt`, `es`, `en`) + chave + offset |
| `durationSec`   | N      | duração detectada |
| `playCount`     | N      | contador de plays (analytics) |
| `cost`          | M      | `{ transcodeUSD, transcribeUSD, totalUSD, estimatedAt }` |
| `errorReason`   | S      | preenchido se `erro` |
| `createdAt`     | S      | ISO-8601 |
| `updatedAt`     | S      | ISO-8601 |

### Tabela `Plays` (eventos de play, para analytics)
| Atributo        | Tipo   | Observação |
|-----------------|--------|------------|
| `videoId` (PK)  | S      | |
| `ts` (SK)       | S      | timestamp do play |
| `user`          | S      | sub do Cognito |

> O **contador agregado** (`playCount`) fica em `Videos` via `UpdateItem` com
> `ADD playCount 1` (atômico). A tabela `Plays` guarda o detalhe por evento,
> caso você queira granularidade depois. Não é monitoramento de tráfego de rede
> — é só "quantos plays cada vídeo recebeu".

## 6. Entrega segura (resumo)

- Bucket **privado**; CloudFront acessa via **Origin Access Control (OAC)**.
- No menu Player, a API valida o JWT (Cognito), confirma `status = pronto` e emite
  **cookies assinados** do CloudFront com escopo `video-profiles/{videoId}/*` e
  **TTL curto**. Sem cookie válido → `403` na borda.
- WAF e HTTPS obrigatórios no CloudFront.
- Detalhes e limitações em `docs/02-seguranca.md`.

## 7. Ajuste de sincronismo de legenda

- O WebVTT é "sidecar" (arquivo separado), então o sincronismo é editável.
- A revisão permite **offset global** (±N s em todos os cues) e **por cue**.
- Ao salvar, uma Lambda reescreve o `.vtt` no S3 recalculando os timestamps.

## 8. Decisões e trade-offs

- **MediaConvert** (não MediaLive): é VOD por arquivo, não ao vivo.
- **HLS/CMAF**: formato de saída padrão para ABR + legenda + futura adição de DRM
  sem reencode.
- **Serverless**: sem servidor ocioso; custo acompanha o uso (bom para protótipo).
- **Shaka Player**: free, ABR HLS/DASH, WebVTT, e já suporta DRM se um dia precisar.
