# Custos e monitoramento — VideoPlatform

Premissa do projeto: monitorar todos os custos de conversão, armazenamento e
entrega. Nesta fase **monitoramos, sem gerar alertas**.

> Valores abaixo são ordens de grandeza em `us-east-1`, levantados de fontes
> públicas e reescritos aqui. Preços de nuvem mudam — confirme no
> [AWS Pricing Calculator](https://calculator.aws/) e nas páginas oficiais antes
> de fechar orçamento. Conteúdo adaptado para conformidade de licenciamento.

## 1. Onde o dinheiro é gasto

| Serviço              | Modelo de cobrança                          | Observação |
|----------------------|---------------------------------------------|------------|
| MediaConvert         | por minuto de **saída**, com multiplicadores| 4 renditions ⇒ ~4× a duração em minutos de saída |
| Transcribe (batch)   | por minuto de **áudio**                     | legenda pt-BR; tradução é à parte |
| Translate            | por caractere                               | só quando o usuário pedir es/en |
| Bedrock (Legenda IA) | por token (input/output)                    | só quando gerar legenda por IA; ver docs/05-legenda-ia.md |
| S3                   | por GB-mês armazenado + requisições         | bruto + profiles |
| CloudFront           | por GB transferido (egress) + requisições   | tende a dominar em escala/audiência |
| AWS WAF              | mensalidade fixa (web ACL + regras) + por requisição | **piso fixo mensal** mesmo sem tráfego |
| DynamoDB             | on-demand: por leitura/escrita + storage    | volume baixo neste protótipo |
| Lambda / Step Functions / API GW | por invocação/transição         | custo marginal baixo |
| Cognito              | por usuário ativo mensal (MAU)              | faixa gratuita generosa |

## 2. Referências de preço (aprox.)

- **MediaConvert**: cobrança **por minuto de cada saída (rendition)**, na faixa de
  resolução daquela saída. Como cada rendition dura o mesmo que o fonte, mais
  renditions = mais minutos faturados. A
  [solução de referência "Video on Demand on AWS"](https://docs.aws.amazon.com/solutions/latest/video-on-demand-on-aws/cost.html)
  estima **~US$ 4,23 para o job inteiro** de um fonte de 60 min em N. Virginia —
  **esse valor é o ladder completo somado, não por perfil**. O exemplo deles usa
  **5 saídas (3 SD + 2 HD)** no *professional tier* (SD US$ 0,0075/min, HD
  US$ 0,024/min):

  ```
  (3 × 60 × 0,0075) + (2 × 60 × 0,024) = 1,35 + 2,88 = US$ 4,23
  ```

  > **Atenção:** o nosso ladder é **1080p/720p/480p/360p = 4 saídas (2 HD + 2 SD)**,
  > diferente do exemplo da AWS (5 saídas). Nas mesmas tarifas, o nosso ficaria em
  > **~US$ 3,78 por hora de fonte** no professional tier
  > (`(2×60×0,024) + (2×60×0,0075) = 2,88 + 0,90`). O *Basic tier* (§5) é mais
  > barato quando os recursos avançados não forem necessários.

  Página oficial: [MediaConvert Pricing](https://aws.amazon.com/mediaconvert/pricing/).
- **Transcribe (batch)**: a partir de **~US$ 0,024/min** (≈ US$ 1,44/hora) na
  primeira faixa, com descontos por volume.
  [Transcribe Pricing](https://aws.amazon.com/transcribe/pricing/).
- **Translate**: por caractere traduzido (a tradução de uma legenda inteira
  costuma custar centavos).
- **S3 Standard**: na casa de **~US$ 0,023/GB-mês**.
- **CloudFront**: eg, **~US$ 0,085/GB** nas primeiras faixas (varia por região de
  borda e volume).
- **AWS WAF** (escopo CloudFront, cobrado em `us-east-1`): **web ACL US$ 5/mês** +
  **US$ 1/mês por regra ou grupo de regras** + **US$ 0,60 por milhão de
  requisições**. Ações padrão (Allow/Block/Count) sem custo. As **regras
  gerenciadas da AWS** (Common Rule Set, Known Bad Inputs) **não têm taxa de
  assinatura extra** — só o US$ 1/mês por grupo. *Bot Control* e *Fraud Control*
  custam à parte e **não** são usados aqui. Nossa config (ver `02-seguranca.md`):
  1 web ACL + 2 grupos gerenciados (Common + Known Bad Inputs) + 1 regra de
  *rate limit* por IP:

  ```
  5,00 (web ACL) + 2 × 1,00 (grupos) + 1 × 1,00 (rate limit) = US$ 8,00/mês fixos
  + 0,60 por milhão de requisições
  ```

  > **Atenção — piso fixo:** diferente do resto da stack (pay-per-use, ~zero
  > parado), o WAF cobra **~US$ 8/mês mesmo sem nenhum play**. É um dos poucos
  > custos fixos do protótipo. Em HLS, cada manifesto + segmento é uma requisição,
  > então a parcela "por milhão" acompanha o volume de entrega (ainda baixo em
  > protótipo). [AWS WAF Pricing](https://aws.amazon.com/waf/pricing/).

### Faixas de resolução e como adicionar 4K/UHD

Sim, **dá para adicionar renditions 4K/UHD** ao ladder — é só incluir a saída
2160p no perfil do MediaConvert (ver `backend/src/lib/mediaconvert-settings.js`).
O que muda é o custo, porque o MediaConvert cobra por **minuto normalizado** =
minutos de saída × **multiplicadores**, e o multiplicador principal é a
**resolução**, relativo ao baseline (AVC, 30 fps, single-pass):

| Faixa      | Resolução típica        | Multiplicador (vs. SD) |
|------------|-------------------------|------------------------|
| SD         | < 720p (480p, 360p)     | 1× |
| HD         | 720p a 1080p            | 2× |
| UHD / 4K   | > 1080p (até 2160p)     | 4× |

> **"4K" e "UHD" são a mesma faixa aqui** (UHD ≈ 3840×2160 ≈ 4K). Multiplicadores
> adicionais se **somam** ao de resolução: codec avançado (HEVC/VP9/AV1), frame
> rate > 30 fps e multi-pass (*quality optimized*). Por isso 4K "na vida real"
> quase sempre custa mais que o 4× puro — costuma vir com HEVC + bitrate alto +
> múltiplos passes.

Ancorando nas tarifas de referência da solução VOD da AWS (professional tier,
N. Virginia): SD ~US$ 0,0075/min e HD ~US$ 0,024/min. Pela relação de
multiplicadores (UHD = 4×, HD = 2×), uma rendition **UHD/4K custa ~2× a de HD** →
estimativa **~US$ 0,048/min**. Custo por hora de fonte, **por rendition**:

| Rendition          | ~US$/min            | 60 min de fonte |
|--------------------|---------------------|-----------------|
| SD (480p/360p)     | 0,0075              | ~US$ 0,45 |
| HD (720p/1080p)    | 0,024               | ~US$ 1,44 |
| UHD/4K (2160p)     | ~0,048 (estimado)   | ~US$ 2,88 |

Ou seja, **adicionar uma única rendition 4K** ao nosso ladder atual
(~US$ 3,78/h de fonte) soma na ordem de **~US$ 2,88/h de fonte** só de transcode —
quase dobra o custo de encode. Trate o número de 4K como **estimativa** e confirme
no [AWS Pricing Calculator](https://calculator.aws/), porque o valor real depende
de codec, fps e passes.

> **O custo maior do 4K não é o transcode, é a entrega.** Um stream 4K tem bitrate
> ~4× o de 1080p; como o **CloudFront (egress) já domina em escala** (ver tabela
> acima), oferecer 4K multiplica o custo de entrega por viewer. E só faz sentido
> se o **fonte for 4K** — não adianta fazer *upscale* de 1080p.

**Antes de ligar 4K:** (1) incluir a saída 2160p no perfil do MediaConvert;
(2) avaliar **HEVC** vs AVC (HEVC reduz bitrate/egress, mas adiciona multiplicador
de codec e exige suporte no player/CDM); (3) revisar o impacto no egress do
CloudFront para a audiência esperada.

### Exemplo ilustrativo (1 vídeo de 10 min)
- Transcode (nosso ladder 2 HD + 2 SD, professional tier):
  `(2 × 10 × 0,024) + (2 × 10 × 0,0075) = 0,48 + 0,15` ≈ **US$ 0,63**.
- Legenda: ~10 min × US$ 0,024 ≈ **US$ 0,24**.
- Storage: alguns GB → centavos/mês.
- Entrega: depende 100% de quantas pessoas assistem (egress).

## 3. Custo por vídeo (dentro da aplicação)

Ao finalizar a pipeline, uma Lambda calcula e grava no DynamoDB:

```json
"cost": {
  "transcodeUSD": 0.00,
  "transcribeUSD": 0.00,
  "translateUSD": 0.00,
  "sdhUSD": 0.00,
  "descriptionUSD": 0.00,
  "storageNote": "estimado por GB armazenado",
  "totalUSD": 0.00,
  "estimatedAt": "ISO-8601"
}
```

- `transcode`: minutos de saída reportados pelo job do MediaConvert × tarifa.
- `transcribe`: duração do áudio × tarifa.
- `translate`: nº de caracteres × tarifa (quando o usuário gerar es/en).

As tarifas ficam em variáveis de configuração (SSM Parameter Store) para você
ajustar sem redeploy. A **Biblioteca** e o **Analytics** mostram esse custo por
vídeo. É uma **estimativa** da aplicação — a fonte de verdade financeira é o Cost
Explorer.

## 4. Monitoramento no nível da conta

- **Cost Allocation Tags**: todos os recursos recebem tags
  `project=videoplatform` e `component=<storage|pipeline|delivery|api>` para
  fatiar o custo por componente no Cost Explorer.
- **Cost Explorer**: visão por serviço e por tag (sem custo adicional de uso
  básico).
- **CloudWatch**: métricas de uso (minutos MediaConvert, GB CloudFront) para um
  dashboard simples.
- **Sem AWS Budgets/alertas** nesta fase (decisão do projeto). A estrutura de
  tags já deixa pronto para ligar alertas depois, se quiser.

## 5. Alavancas de redução de custo

- **ABR enxuto**: 4 renditions cobrem bem; evitar renditions extras. Adicionar
  **4K/UHD** é possível, mas pesa no transcode (~2× a tarifa de HD) e, sobretudo,
  no **egress** do CloudFront — ver "Faixas de resolução e como adicionar 4K/UHD"
  na seção 2.
- **Perfil "Basic" do MediaConvert** quando os recursos avançados não forem
  necessários (tier mais barato).
- **CloudFront**: cache longo nos segmentos (imutáveis) reduz requisições à origem.
- **Transcribe só uma vez** (pt-BR); traduções são texto (baratas) via Translate,
  sem reprocessar áudio.
- **Lifecycle do bruto**: nesta fase o bruto fica em `raw-videos/` (sem Glacier,
  por decisão); se o custo de storage crescer, mover para classe mais barata é a
  alavanca mais fácil.
- **DynamoDB on-demand**: paga só pelo que usa; ideal para volume imprevisível de
  protótipo.
