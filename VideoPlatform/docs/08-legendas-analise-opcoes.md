# Legendas — Transcrição + Sincronia: análise comparativa das opções

> Documento de decisão. Compara todas as alternativas para gerar a legenda
> (texto + tempo) da plataforma, com custo, tempo, paralelismo, complexidade,
> fortes e fracos. Começa pelo **resumo executivo** (objetivo) e desce para o
> **detalhe técnico** e as **evidências medidas** (POC).
>
> Preços em `us-east-1`, ordens de grandeza de fontes públicas, reescritos aqui.
> Confirme no [AWS Pricing Calculator](https://calculator.aws/) antes de fechar
> orçamento. Conteúdo adaptado para conformidade de licenciamento.

---

## 1. Resumo executivo

### O problema em uma frase
Legenda é **dois trabalhos**: o **texto** (o que foi dito e os sons) e o **tempo**
(quando aparece na tela). Nenhuma ferramenta sozinha hoje faz os dois com
qualidade **e** preço baixo — por isso a decisão é sobre qual **combinação** usar.

### O que descobrimos (medido, não chute)
- O **Amazon Transcribe** acerta o **tempo** (alinhamento forçado), mas o **texto**
  é mais fraco no nosso conteúdo (desenho/onomatopeias) e custa **US$ 1,37** por
  vídeo de 57 min.
- O **Voxtral 24B** (nosso SDH atual) acerta o **texto**, mas **erra o tempo** de
  forma não-determinística (deriva de 5–7 s). **Diminuir o chunk piorou.**
  Sincronia confiável só com o 24B **não é possível** — é limite do modelo.
- **Alinhamento forçado** (pegar um texto pronto e descobrir *quando* cada palavra
  acontece) resolve o tempo por **compute, sem custo por minuto**. Validamos dois:
  **MMS** (via torchaudio) e **WhisperX** — ambos sincronizam a ~**0,06–0,08 s**.

### Recomendação
**24B + MMS (alinhamento forçado)** — melhor custo-benefício para o nosso SDH.
Mantém o texto do 24B que já aprovamos (fala **+ marcadores de som**) e conserta
o tempo com um alinhador leve. ~**US$ 0,14/vídeo** (≈ 9× mais barato que o
Transcribe), sincronia **~0,06 s**.

### Tabela de decisão (TL;DR)

| Opção | Texto | Sincronia | Custo/57min | Tempo (1 tarefa) | Complexidade | Veredito |
|---|---|---|---|---|---|---|
| **Transcribe** (atual base) | Médio | Preciso (ref.) | **US$ 1,37** | Rápido (gerenciado) | Nenhuma (pronto) | Caro, texto fraco |
| **Transcribe + 24B** (ancoragem) | Ótimo | Preciso | **US$ 1,37** (+0) | Rápido | Baixa | Bom, mas **não corta** o custo do Transcribe |
| **24B sozinho** (SDH atual) | Ótimo | ❌ Quebrada (5–7 s) | US$ 0,08 | ~9 min | Pronto | **Inviável** (sincronia) |
| **★ 24B + MMS** | Ótimo + marcadores | **~0,06 s** | **~US$ 0,14** | ~15–25 min | Média-alta | **Recomendado p/ SDH** |
| **WhisperX** (self-hosted) | Ótimo | **~0,08 s** | ~US$ 0,30 | ~45–75 min | Alta | Ótimo p/ fala; **não faz marcadores**; pesado sem GPU |

> "Tempo (1 tarefa)" é uma única execução; **com paralelismo (fan-out) cai para
> poucos minutos** em todas as opções self-hosted (ver §6).

---

## 2. Contexto

A legenda tem duas dimensões independentes:

| Dimensão | O que é | Quem resolve bem |
|---|---|---|
| **Texto** | Transcrição da fala + marcadores de som ([música], [risos]) | 24B, WhisperX/Whisper |
| **Tempo** | O instante exato de cada fala na timeline | Transcribe, **alinhamento forçado** (MMS/wav2vec2) |

O **alinhamento forçado** é a peça-chave: diferente do ASR (que *inventa* o texto
e chuta o tempo), ele recebe um **texto já pronto** e só descobre **quando** cada
palavra ocorre no áudio. Isso é feito por um modelo acústico rodando no **nosso
compute** — ou seja, **sem tarifa por minuto**, só CPU.

---

## 3. Critérios de avaliação

- **Qualidade de texto** — acerto da transcrição no nosso conteúdo (pt-BR, desenho).
- **Sincronia** — erro de tempo vs. a referência (Transcribe), medido em segundos.
- **Custo por vídeo** (57 min de referência).
- **Tempo de processamento** — numa tarefa e com paralelismo.
- **Paralelismo** — como escala e qual é o teto.
- **Complexidade de criação** — esforço para construir.
- **Complexidade de manutenção** — esforço para manter vivo.
- **Adequação ao SDH** — faz os **marcadores de som**? (requisito nosso).

---

## 4. As opções em detalhe

### 4.1 Amazon Transcribe (linha de base atual)

**Como funciona.** Serviço gerenciado de ASR da AWS. Já roda hoje no pipeline e
gera a faixa `pt` (texto + tempo preciso). É a base da tradução também.

- **Texto:** médio no nosso caso — erra onomatopeias/nomes ("Vrum!" vira "Bru").
- **Sincronia:** precisa (alinhamento forçado interno) — é a nossa **referência**.
- **Custo:** US$ 0,024/min × 57 ≈ **US$ 1,37/vídeo** ([AWS Transcribe pricing](https://aws.amazon.com/transcribe/pricing/)).
- **Tempo & paralelismo:** gerenciado; jobs batch assíncronos, a AWS paraleliza
  internamente; sem o teto de 15 min do Lambda. Concorrência limitada por cotas
  do serviço.
- **Criação:** nenhuma (já existe). **Manutenção:** nenhuma (gerenciado).
- **Fortes:** zero infra, tempo preciso, confiável, escala sozinho.
- **Fracos:** o **mais caro**, texto mais fraco no nosso conteúdo.
- **Quando usar:** quando custo não importa e texto "bom o suficiente" basta; ou
  como **fonte de tempo** para a ancoragem (§4.2).

### 4.2 Transcribe + 24B (ancoragem de tempo)

**Como funciona.** Usa o **texto do 24B** (bom) e os **tempos do Transcribe**
(precisos): casa as palavras das duas faixas e transfere o tempo. Como o
Transcribe **já roda** no pipeline, o custo dele é **afundado** — a ancoragem é
pós-processamento em JS puro, **US$ 0 a mais**.

- **Texto:** ótimo (24B). **Sincronia:** precisa (herda do Transcribe).
- **Custo:** **US$ 1,37** (o do Transcribe, que já pagamos) + ~US$ 0,08 (24B) +
  ~US$ 0 (ancoragem).
- **Tempo & paralelismo:** igual ao Transcribe + 24B (ambos já existentes).
- **Criação:** **baixa** — função de casamento de palavras (já prototipada e
  depois removida). **Manutenção:** baixa (JS no stack atual).
- **Fortes:** melhor texto **sem** nova infra; sincronia precisa; reaproveita tudo.
- **Fracos:** **não reduz** o custo do Transcribe (o objetivo era cortá-lo); o
  casamento falha onde os textos divergem muito.
- **Quando usar:** se o Transcribe **permanecer** no pipeline de qualquer forma
  (p.ex. porque a tradução depende dele). É o ganho de qualidade "grátis".

### 4.3 24B sozinho (SDH atual) — ❌ não viável para sincronia

**Como funciona.** O Voxtral 24B ouve o áudio e gera fala + marcadores numa
passada (é o SDH que já temos).

- **Texto:** ótimo. **Sincronia:** **quebrada** — o modelo *estima* o tempo e cai
  numa falha de "incremento de 1 em 1 segundo" (deriva de 5–7 s), de forma
  **não-determinística** (ver evidência em §8).
- **Custo:** ~US$ 0,08/vídeo. **Tempo:** ~9 min (worker Lambda).
- **Fortes:** barato, texto ótimo, **já construído**, faz marcadores de som.
- **Fracos:** **sincronia inutilizável**. Diminuir o chunk **piora** e encarece.
- **Veredito:** inviável como está. O texto é excelente — por isso ele vira a
  **fonte de texto** nas opções 4.2 e 4.4.

### 4.4 ★ 24B + MMS (alinhamento forçado) — recomendado

**Como funciona.** O 24B dá o **texto** (fala + marcadores). O **MMS**
(modelo multilíngue da Meta via torchaudio/`transformers`) alinha a **fala** ao
áudio e devolve o tempo exato por palavra. Os marcadores vão para as pausas da
fala (lógica que já temos).

```
24B  → texto (fala + [marcadores])  ─┐
                                     ├─► MMS forced align (fala×áudio) ─► tempo exato
áudio WAV ───────────────────────────┘        │
                                               └─► marcadores reposicionados nas pausas → VTT
```

- **Texto:** ótimo (24B, o que já aprovamos). **Sincronia:** **~0,06 s** (medido).
- **Custo:** ~US$ 0,08 (24B) + ~US$ 0,05–0,10 (Fargate CPU) ≈ **~US$ 0,14/vídeo**
  (**~9× mais barato** que o Transcribe).
- **Tempo & paralelismo:** alinhamento mede **0,17× do tempo real** (CPU 8 threads);
  57 min ≈ **~10 min** numa passada; Fargate ~15–25 min numa tarefa, **minutos**
  com fan-out. **CPU-bound → escala horizontalmente sem teto de cota externa.**
- **Criação:** **média-alta** — container Python no ECS Fargate, modelo MMS via
  HuggingFace `transformers`, orquestração do job, pós-processamento das
  interjeições curtas. **Manutenção:** média — é um serviço Python num stack hoje
  só-JS; atualizações de modelo/libs.
- **Fortes:** mais barato dos que resolvem sincronia; **coeso para SDH** (o 24B já
  entrega fala **e** marcadores — o MMS só reajusta o tempo); sem GPU.
- **Fracos:** novo componente (container) no stack; interjeições muito curtas
  ("Ah", "Ai") podem grudar no vizinho (contornável por fusão/filtro de score).
- **Nota:** não usar a API `Wav2Vec2FABundle` do torchaudio (**deprecada no 2.8**,
  remoção prevista no 2.9); carregar o **MMS via `transformers`**. O modelo e o
  algoritmo (CTC forced align) continuam vivos.

### 4.5 WhisperX (self-hosted) — um motor, texto + tempo

**Como funciona.** WhisperX = ASR Whisper (texto) + alinhamento wav2vec2 (tempo),
num container no ECS Fargate. Substitui Transcribe **e** 24B **na faixa de fala**.

- **Texto:** ótimo (Whisper large-v3), nível do 24B. **Sincronia:** **~0,08 s**
  (medido).
- **Custo:** ~**US$ 0,25–0,40/vídeo** (Fargate CPU; não precisa do 24B para a fala).
- **Tempo & paralelismo:** compute mede **0,74× do tempo real** (CPU) — o ASR
  autoregressivo é pesado; 57 min ≈ **~45 min** numa passada; Fargate ~45–75 min
  numa tarefa, **minutos** com fan-out. **CPU-bound**, escala horizontalmente.
- **Criação:** **alta** — container maior (modelos ~3 GB), job no Fargate, e
  **ainda precisa do 24B para os marcadores de som**. **Manutenção:** média-alta —
  WhisperX/pyannote/torch têm bastante rotatividade de versão.
- **Fortes:** autocontido (sem Bedrock para a fala), texto e tempo num motor só,
  mantido ativamente; ótimo se o alvo fosse legenda de fala comum.
- **Fracos:** **não faz marcadores SDH** (só fala) → ainda exige o 24B;
  **~2× mais caro** e **~4× mais pesado** que o 24B+MMS; sem GPU no Fargate.
- **Quando usar:** se quisermos um único motor open-source para a fala e aceitarmos
  o custo/compute maior; ou se um dia largarmos o SDH com marcadores.

### 4.6 Variações e menções

- **WhisperX + 24B (marcadores):** usa WhisperX para fala/tempo e o 24B só para os
  marcadores de som. Resolve o buraco do SDH do WhisperX, mas são **dois motores
  pesados** (WhisperX no Fargate + 24B no Bedrock) — mais caro e complexo que o
  24B+MMS, sem ganho claro.
- **faster-whisper sozinho (sem alinhamento):** mais leve que o WhisperX, mas os
  tempos ficam em ~±0,5 s (cross-attention), não ±0,05 s. Suficiente para legenda
  comum, folgado demais para karaokê/dublagem. Ainda não faz marcadores.
- **GPU via ECS no EC2 (g4dn/g5):** Whisper/MMS em GPU rodam ~10–30× mais rápido
  (57 min em ~2–4 min). Reduz tempo drasticamente, mas é **instância GPU
  gerenciada** (AMI, ciclo de vida, custo fixo ~US$ 0,5–1/h) — mais infra que o
  Fargate CPU. Só vale se latência virar prioridade.
- **APIs de terceiros (Deepgram/AssemblyAI):** costumam ser mais baratas que o
  Transcribe e dão timestamps de palavra. **Porém o áudio sai da AWS para um
  terceiro** — provavelmente **não permitido** neste ambiente. Não recomendado
  sem aval de segurança/compliance.

---

## 5. Matriz comparativa

Nota de 1 (ruim) a 5 (ótimo). Peso maior para Sincronia, Custo e Adequação SDH.

| Critério | Transcribe | Transcribe+24B | 24B só | **24B+MMS** | WhisperX |
|---|---|---|---|---|---|
| Qualidade de texto | 3 | 5 | 5 | **5** | 5 |
| Sincronia | 5 | 5 | 1 | **5** | 5 |
| Custo/vídeo | 1 | 1 | 5 | **4** | 3 |
| Tempo (c/ paralelismo) | 5 | 5 | 4 | **4** | 3 |
| Paralelismo (teto) | 4 | 4 | 3 | **5** | 5 |
| Complexidade criação | 5 | 4 | 5 | **2** | 1 |
| Complexidade manutenção | 5 | 4 | 4 | **3** | 2 |
| Adequação SDH (marcadores) | 2 | 5 | 5 | **5** | 2 |

> O 24B+MMS perde em "complexidade de criação" (é um componente novo), mas ganha
> onde mais importa para o produto: texto, sincronia, custo e adequação ao SDH.

---

## 6. Paralelismo — visão geral

| Abordagem | Natureza | Como escala | Teto |
|---|---|---|---|
| Transcribe | Gerenciado | AWS paraleliza; jobs batch | Cotas do serviço |
| 24B (Bedrock) | **I/O-bound** (espera o Bedrock) | Fan-out via fila (SQS), N chamadas simultâneas | **Cota Voxtral (RPM/TPM)** |
| MMS / WhisperX | **CPU-bound** | Mais vCPU por tarefa **e/ou** fatiar o áudio em janelas por N tarefas | Só o compute que quisermos pagar (**sem teto externo**) |

Padrão de fan-out (vale para 24B, MMS e WhisperX), igual ao que já desenhamos:

```
coordenador → fatia o trabalho em janelas → enfileira (SQS)
SQS → N workers em paralelo (maxConcurrency = K) → cada um grava sua parte
último a terminar → junta as partes → legenda final
```

- Para **24B**, K é limitado pela **cota do Bedrock**.
- Para **MMS/WhisperX**, K é limitado só pela **quantidade de tarefas Fargate**
  (ou vCPUs) que decidirmos rodar — sem teto de serviço externo.
- Como cada janela é curta, **nenhuma invocação chega perto de limite de tempo**,
  independentemente da duração do vídeo. Resolve de vez o problema do teto de
  15 min do Lambda.

---

## 7. Custos — modelo e premissas

> Estimativas. O que foi **medido** está marcado; o resto é extrapolação.

**Tarifas base (us-east-1, aprox.):**
- Transcribe batch: **US$ 0,024/min**.
- Voxtral 24B (Bedrock): input ~US$ 0,10 / 1M tokens, output ~US$ 0,30 / 1M.
- Fargate (x86): **US$ 0,04048/vCPU-hora** + **US$ 0,004445/GB-hora** (ARM ~20% menos).

**Vídeo de referência: 57 min (3447 s).**

| Item | Conta | Resultado |
|---|---|---|
| Transcribe | 57 × 0,024 | **US$ 1,37** |
| 24B (texto) | tokens medidos (~1 passada) | **~US$ 0,05–0,08** |
| MMS no Fargate | 4 vCPU+8 GB, ~0,3× realtime ⇒ ~17 min | **~US$ 0,06** |
| WhisperX no Fargate | 8 vCPU+16 GB, ~0,8× realtime ⇒ ~46 min | **~US$ 0,30** |

- **24B + MMS total:** ~US$ 0,08 + ~US$ 0,06 ≈ **US$ 0,14**.
- **WhisperX total:** ~**US$ 0,30** (dispensa o 24B na fala; some o custo do 24B
  só se mantiver os marcadores).
- O custo do Fargate é ~o mesmo com ou sem fan-out (mesmos vCPU-segundos totais,
  só distribuídos) — o fan-out compra **tempo**, não muda **custo**.

---

## 8. Evidências medidas (POC)

Rodado no áudio real do vídeo de teste ("PicaPau v4", 57 min), comparando com os
tempos do Transcribe (referência). Scripts: `scripts/sdh_align_poc.py` (MMS),
`scripts/sdh_whisperx_poc.py` (WhisperX), `scripts/sdh-sync-test.js` (Voxtral).

### 8.1 Voxtral 24B — sincronia quebrada e não-determinística
No mesmo `chunkSec=60`, 3 execuções: **1 acertou, 2 erraram** (deriva de 5–7 s,
tempos "empacotados" 2,0 / 3,0 / 4,0 / 5,0...). Diminuir para `chunkSec=20`
**piorou** (ainda perdeu falas e gastou ~3× mais tokens).

| Fala | Transcribe (verdade) | 24B publicado | 24B `chunk=20` |
|---|---|---|---|
| "toda esta chuva vai passar" | 12,5 s | 5,0 s ❌ | 5,0 s ❌ |
| "controle de tempo pro Leôncio" | 19,3 s | 11,0 s ❌ | sumiu ❌ |

### 8.2 MMS (alinhamento forçado) — fidelidade vs. Transcribe
Alinhando o **próprio texto do Transcribe** (casamento 1:1, 27 cues):

```
ERRO DO ALINHADOR vs Transcribe:  mediana = 0,06 s | média = 1,04 s | p90 = 1,41 s
```
Os poucos outliers são interjeições de 2 letras ("Ah"/"Ai") que grudam no vizinho
(contornável). Nas frases reais, erro de **centésimos de segundo**.

Alinhando o **texto do 24B** (caminho de produção) — sincronia restaurada:

| Fala | Transcribe (verdade) | 24B publicado | **24B + MMS** |
|---|---|---|---|
| "toda esta chuva vai passar" | 12,5 s | 5,0 s ❌ | **12,54 s** ✅ |
| "controle de tempo pro Leôncio" | 19,3 s | 11,0 s ❌ | **19,30 s** ✅ |
| "chuva vai embora" | 28,9 s | 14,0 s ❌ | **28,17 s** ✅ |
| "sol brilhar novamente" | 30,3 s | 15,0 s ❌ | **30,31 s** ✅ |
| "chuvas e trovões" | 43,6 s | ~20 s ❌ | **44,81 s** ✅ |

**Velocidade (CPU, 8 threads):** forward do modelo = **0,170 s por 1 s de áudio**
(≈ 0,17× realtime); alinhamento em si ~0,05 s (desprezível).

### 8.3 WhisperX — texto + tempo num motor
```
transcrição (ASR):  60,1 s p/ 90 s  => 0,667× realtime
alinhamento:         6,3 s          => 0,070× realtime
TOTAL compute:      66,4 s          => 0,737× realtime
PRECISÃO vs Transcribe:  mediana = 0,08 s | média = 0,43 s | p90 = 0,58 s (n=16)
```
Texto no nível do 24B. Carga dos modelos (first run 309 s + 83 s) é **download**
único — em produção vai embutido na imagem (carga quente ~19 s + 5 s).

---

## 9. Recomendação e próximos passos

**Recomendado: 24B + MMS (§4.4).** Melhor equação para o nosso SDH — texto que já
aprovamos (fala + marcadores), sincronia ~0,06 s, ~US$ 0,14/vídeo (~9× mais barato
que o Transcribe), e escala horizontal sem teto de cota.

**Alternativa forte: WhisperX (§4.5)** se preferirmos um motor open-source
autocontido para a fala e aceitarmos ~2× o custo e ~4× o compute — lembrando que
os **marcadores de som ainda exigiriam o 24B**.

**Caminho de menor esforço imediato: Transcribe + 24B (§4.2)** — se o Transcribe
for ficar no pipeline de qualquer jeito (pela tradução), a ancoragem dá o texto
bom **de graça**, sem container novo. Não corta o custo do Transcribe, mas é
entregável hoje.

### Decisão em aberto
1. O **Transcribe** vai sair do pipeline (corta US$ 1,37/vídeo) ou fica pela
   tradução? Isso decide entre "cortar custo" (24B+MMS/WhisperX) e "ganho grátis"
   (ancoragem).
2. Latência importa a ponto de justificar **GPU** (ECS no EC2)? Se não, Fargate
   CPU + fan-out basta.

### Se seguirmos com 24B + MMS
1. Container Python (MMS via `transformers`) + tarefa ECS Fargate.
2. Entrada: `track.wav` + texto do 24B (fala). Saída: VTT re-sincronizada + marcadores.
3. Pós-processamento das interjeições curtas (fusão/filtro de score).
4. Fan-out opcional (SQS) para vídeos longos.
5. Settings no DynamoDB (nada hardcoded), igual ao resto da plataforma.

---

### Anexo — ambiente dos POCs
- Máquina: Mac (Apple Silicon), 8 threads, 16 GB. CPU de datacenter rende
  diferente — números de Fargate são extrapolação.
- MMS: `torch 2.7.1` + `torchaudio 2.7.1`, modelo `MMS_FA` (uroman multilíngue).
- WhisperX: `whisperx` (torch 2.8), modelo `large-v3` int8, alinhador wav2vec2 pt.
- Transcribe como referência de tempo (faixa `pt` já no pipeline).
