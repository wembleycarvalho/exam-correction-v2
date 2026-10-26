# Watermarking forense por sessão — guia completo (quando/como/custo)

Este documento aprofunda o complemento citado em `docs/03-drm.md` (seção 8): a
**marca d'água forense por sessão**. É o tema que mais importa quando a pergunta
real é *"o conteúdo vai vazar — e aí?"*, porque ataca o cenário que **nenhum DRM
resolve**: o usuário autorizado que captura e redistribui.

> Posição honesta, já de saída: watermarking **não impede** download nem cópia.
> Ele não é prevenção, é **atribuição** — permite descobrir *de qual sessão/conta*
> saiu um vazamento, para então agir (takedown, encerramento de conta, ação
> legal). Só tem valor se você **realmente agir** sobre o que ele revela.

## 1. DRM × watermarking (não são a mesma coisa)

| | DRM | Watermarking forense |
|---|---|---|
| O que faz | **impede** decodificar sem licença | **identifica** quem vazou depois |
| Momento | antes/durante o play | depois do vazamento |
| Contra o atacante autorizado | não ajuda | **é a resposta** |
| Impede download? | não (ver `03-drm.md` §7) | não |
| Valor | dissuasão + conformidade | rastreio + base para takedown/ação |

São **complementares**. DRM eleva a barra para extrair; watermarking garante que,
quando a cópia aparecer (e pela §7 do doc de DRM, pode aparecer), você saiba a
origem. A boa prática da AWS (Streaming Media Lens, SMSEC03-BP01) descreve
exatamente isso: marca por sessão permite identificar o viewer/dispositivo
responsável pelo vazamento e embasar encerramento de conta e ação legal
([SMSEC03-BP01](https://docs.aws.amazon.com/wellarchitected/latest/streaming-media-lens/smsec03-bp01.html)).

## 2. Tipos de marca d'água

### 2.1 Por visibilidade
- **Visível (burned-in overlay):** um texto/logo sobre o vídeo (ex.: id do usuário
  em opacidade baixa). Dissuade, mas é feio e **recortável**.
- **Invisível (forense):** identificador imperceptível embutido no sinal do vídeo,
  projetado para sobreviver a recompressão, recorte, mudança de resolução e até
  re-filmagem (*cam*). É o que os fornecedores de OTT vendem
  ([Synamedia](https://www.synamedia.com/blog/video-watermarking-explained/) —
  conteúdo reescrito para conformidade).

### 2.2 Por onde a marca é inserida
- **Client-side overlay (no player):** o Shaka/HTML desenha a marca por cima do
  vídeo no dispositivo. **Barato e DIY**, porém fraco (ver §4.1).
- **Head-end (no encode):** a marca entra no transcode. Marca por arquivo
  (bom para *screeners*/pré-lançamento), não escala para "um encode por viewer".
- **A/B por sessão (bitstream) — padrão de mercado para OTT em escala:** ver §3.
- **Edge (na borda/CDN):** a seleção A/B por sessão acontece no ponto de entrega,
  que é o lugar natural para isso em streaming
  ([watermarking at the edge, AWS](https://aws.amazon.com/blogs/media/securing-media-content-using-watermarking-at-the-edge/)).

## 3. Como funciona o A/B por sessão (o modelo que escala)

A ideia central, usada por praticamente todos os fornecedores de OTT:

1. **Duas variantes.** Um pré-processador/encoder gera **duas versões
   perceptualmente idênticas** de cada segmento: **variante A** e **variante B**.
   Elas diferem em escolhas sutis de codificação — cada segmento carrega, na
   prática, **1 bit** (A=0, B=1).
2. **Payload por sessão.** Cada sessão de play recebe um **identificador binário
   único** (derivado do usuário + sessão). Para o segmento *i*, entrega-se A ou B
   conforme o bit *i* do payload.
3. **Seleção na entrega.** Ao longo de N segmentos, a sequência de A/B escolhida
   **codifica o id da sessão**. Essa seleção é feita na borda (função no CloudFront
   / Lambda@Edge reescrevendo manifesto/URLs por sessão) ou por um empacotador
   *just-in-time* (ex.: MediaPackage faz isso para live/CMAF —
   [A/B watermarking no MediaPackage](https://docs.aws.amazon.com/mediapackage/latest/userguide/ab-watermarking.html)).
4. **Detecção.** Dado um arquivo pirata (mesmo um trecho), o **detector do
   fornecedor** lê qual variante é cada segmento → recupera os bits → mapeia de
   volta para a sessão/conta via o registro de tokens.

```
                 PRÉ-PROCESSO (uma vez por vídeo)
   source.mp4 ──> encode/preprocessador ──> ladder HLS em DUAS variantes
                                             A: .../hls/1080p/segA_*.ts
                                             B: .../hls/1080p/segB_*.ts
                 (≈2× minutos de encode e/ou ≈2× storage de segmentos)

                 ENTREGA (por sessão de play)
   POST /play/{videoId}  ──> Lambda gera payload da sessão (user+sessão)
                             e um token assinado com a sequência A/B
          │
          ▼
   CloudFront + função na borda  ──> para cada segmento, serve A ou B
          │                           conforme o bit do payload
          ▼
   Shaka toca normalmente (a marca é invisível)

                 PÓS-VAZAMENTO
   cópia pirata ──> detector do fornecedor ──> bits ──> id da sessão ──> conta/usuário
```

## 4. Encaixe na arquitetura de vocês (VOD serverless)

A stack atual (`01-arquitetura.md`) é **S3 + MediaConvert + CloudFront + OAC +
cookies assinados + Cognito + Shaka**. Há três rotas realistas, da mais barata/
fraca à mais cara/robusta:

### 4.1 Rota DIY — overlay dinâmico no cliente (dissuasão barata)
O player desenha o id do usuário + timestamp da sessão em opacidade baixa,
mudando de posição periodicamente.
- **Custo:** ~zero (só frontend).
- **Serve para:** desencorajar screen-record/cam casual e "print pra zap".
- **Limite honesto (importante):** a marca é desenhada **no player**, não está nos
  segmentos. Se o atacante **ripa os segmentos limpos** (caminho Widevine L3 da
  §7 do DRM), **não há marca nenhuma** na cópia. Além disso é recortável. Ou seja:
  só ajuda contra captura da tela/câmera, **não** contra ripagem do stream.

### 4.2 Rota AWS-nativa — MediaConvert + NexGuard File Marker (VOD/pré-lançamento)
O MediaConvert integra o **NAGRA NexGuard File Marker** para marca forense em
arquivo, incluindo fluxos de pré-lançamento (NGPR/G2) e OTT
([ref. SDK MediaConvert NexGuard](https://docs.aws.amazon.com/sdk-for-sap-abap/v1/api/latest/mdc/model/_AWS1_CL_MDCNEXGUARDFILEMARK00.html)).
- **Bom para:** audiências pequenas e alto valor (ex.: *screeners*, revisão
  interna), onde marcar **um arquivo por destinatário** é aceitável.
- **Limite:** marca-por-arquivo **não escala** para "um encode por viewer" em
  streaming aberto; para escala, combina-se com o modelo A/B (§4.3).

### 4.3 Rota robusta — A/B por sessão com fornecedor + seleção na borda
Pré-processa o vídeo em duas variantes (via fornecedor/MediaConvert) e seleciona
A/B por sessão numa função no CloudFront/Lambda@Edge. É o padrão de OTT em escala;
na AWS aparece em MediaPackage (live) e nos fornecedores NexGuard/Irdeto.
- **Robusto, invisível, escalável.** Funciona mesmo contra a cópia ripada e
  redistribuída, porque a marca está **nas variantes**, não no player.
- **É aqui que entram custo e complexidade de verdade** (§5 e §6).

## 5. Complexidade — o que você constrói e opera

Além do que já existe hoje:
- **Pré-processamento A/B** no encode (perfil do MediaConvert ou preprocessador do
  fornecedor), com **segmentos A e B alinhados** (mesmos limites de GOP/segmento,
  mesmas chaves de DRM se houver) para serem intercambiáveis.
- **Serviço de sessão/token:** estende o `POST /play/{videoId}` para gerar o
  **payload** por sessão (ligado ao `sub` do Cognito) e assiná-lo.
- **Lógica na borda:** função no CloudFront / Lambda@Edge que, por requisição,
  resolve qual variante servir. Atenção: no limite isso é **uma decisão por
  segmento por viewer** (muitas invocações) — manipular no nível do **manifesto**
  reduz bastante o volume.
- **Armazenamento das duas variantes** (ou de um *sidecar* só com os segmentos
  marcados, trocando robustez por storage).
- **Workflow de detecção + ação:** portal/serviço do fornecedor para analisar
  suspeitas, **mais o processo humano/jurídico** de takedown e encerramento de
  conta. Sem esse processo, o watermarking não entrega valor.
- **Matriz de testes** ampliada (troca A/B não pode causar *glitch* de playback).

## 6. Custos (ordem de grandeza — validar na contratação)

> Como em `docs/04-custos.md`: valores são ponto de partida para cotação, não
> preço fechado. O licenciamento de watermarking forense é **enterprise e
> tipicamente opaco** (sem tabela pública).

| Item | Modelo | Observação honesta |
|---|---|---|
| **Licença do fornecedor** (NexGuard, Irdeto TraceMark, Verimatrix, Synamedia ContentArmor, Friend MTS) | por título/asset, por stream/sessão, por assinante/mês, ou plataforma | **maior custo e o mais imprevisível**; exige contato comercial |
| **Encode A/B** | ~2× minutos de saída do MediaConvert (ladder duplicada) *ou* passo de preprocessamento | some ao custo de transcode do `04-custos.md` |
| **Storage** | ~2× os segmentos HLS (ou menos com *sidecar*) | S3 ~US$ 0,023/GB-mês |
| **Seleção na borda** | invocações de CloudFront Functions / Lambda@Edge | pode doer em escala (muitas requisições); manifesto-level reduz |
| **Detecção/operação** | serviço do fornecedor + tempo de equipe + jurídico | custo recorrente "invisível", mas real |

**Comparação com a fase atual:** hoje a proteção tem custo marginal ~zero (OAC +
cookies). DRM adiciona custo **por play** (licença). Watermarking A/B adiciona
custo de **fornecedor + ~2× pipeline/storage + borda + operação** — é o
complemento mais caro de todos, e o que mais exige maturidade de processo.

## 7. Robustez e ataques contra o próprio watermark (honestidade)

Watermarking forense também não é mágica:
- **Ataque de conluio (*collusion*):** vários usuários comparam suas cópias
  (bits A/B diferentes) e produzem uma cópia média/mesclada para apagar a
  atribuição. Fornecedores sérios usam **códigos resistentes a conluio** (ex.:
  Tardos), o que exige **mais segmentos/duração** para detecção confiável.
- **Trecho curto demais:** poucos segmentos = poucos bits = atribuição frágil.
  Clipes muito curtos podem não carregar payload suficiente.
- **Reprocessamento agressivo:** recorte forte, *downscale*, filtros e re-cam
  degradam a marca; a robustez varia por fornecedor e é o principal diferencial
  que você está pagando.
- **Depende de operar:** sem monitoramento de pirataria + detecção + takedown, a
  marca nunca é "lida" e o investimento vira enfeite.

## 8. Limite honesto (uma frase por ponto)

- Watermarking **não impede** cópia nem download — é rastreio **pós-vazamento**.
- O overlay DIY só pega captura de tela/câmera; **não** aparece em segmento ripado.
- A/B forense pega até a cópia redistribuída, mas custa **fornecedor + 2× pipeline
  + borda + operação**.
- Só vale se você **agir** sobre o que ele revela (takedown/conta/jurídico).

## 9. Recomendação para a fase atual (protótipo)

- **Não ligar watermarking A/B agora.** Igual ao DRM, é um investimento para
  quando houver conteúdo premium/licenciado, evidência de pirataria, ou exigência
  contratual — e **orçamento + disposição de agir** sobre vazamentos.
- **Se quiser dissuasão barata já:** adicionar o **overlay dinâmico no cliente**
  (§4.1) com id do usuário + sessão. É quase grátis e desencoraja o compartilhamento
  casual — sendo honesto sobre o que ele **não** cobre (ripagem de segmento).
- **Caminho de evolução:** como já usamos **HLS/CMAF + Shaka + CloudFront**, a
  migração para A/B é incremental — entra o preprocessamento A/B, o payload por
  sessão no `POST /play`, a função na borda e o fluxo de detecção, **sem trocar
  player nem refazer o frontend** (mesmo princípio da adição de DRM).
- **Para *screeners*/revisão interna de alto valor:** considerar
  **MediaConvert + NexGuard File Marker** (§4.2), que marca por arquivo sem
  precisar da infra de borda.

## 10. Resumo em uma frase

DRM tenta impedir a extração; **watermarking forense assume que o vídeo pode
vazar e garante que você saiba de qual sessão/conta saiu** — barato e fraco como
overlay no cliente, robusto e caro como A/B por sessão de fornecedor, e **só útil
se houver um processo real de detecção e resposta por trás**.
