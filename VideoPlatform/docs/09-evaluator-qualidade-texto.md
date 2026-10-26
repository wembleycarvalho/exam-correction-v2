# Evaluator de qualidade do texto da legenda

> Motor automático que dá uma **nota de confiança** à qualidade do TEXTO
> transcrito (acerto das palavras vs. o que foi realmente dito), com um
> comentário do juiz, os métodos usados e os **custos individualizados**.
> Avalia apenas o **texto** — tempo/sincronia e legibilidade são outro assunto
> (ver `docs/08-legendas-analise-opcoes.md`).

---

## 1. Resumo executivo

A plataforma gera **duas legendas** do mesmo áudio:
1. **Transcribe** (faixa `pt`) — tempo preciso, texto mediano.
2. **Voxtral/24B** (faixa `pt-sdh`) — texto ótimo (fala + marcadores de som).

O **terceiro passo é o avaliador** — ele **não cria uma terceira legenda**.
Produz um **relatório de nota** (0-100) sobre a legenda do 24B, usando duas
técnicas que se complementam, e grava o resultado junto da própria variante
(`sdhVariants.<método>.eval`).

> Por que não gerar uma 3ª legenda "perfeita" fundindo as duas? Fundir texto de
> dois modelos automaticamente cria "frankentexto" e pode introduzir erro. O
> avaliador **certifica** a melhor legenda e **aponta onde revisar** — a decisão
> de corrigir fica com o humano (ou, no futuro, com o re-timing por MMS).

### Saída (o que aparece ao final)
- **Nota do juiz** (0-100) + rótulo (Alta / Média / Baixa confiança).
- **Comentário** curto (se pertinente).
- **Métodos usados** (chips): Consenso, LLM-juiz.
- **Custos individualizados**: Transcribe, Voxtral e Juiz (LLM), cada um em USD.
- **Trechos suspeitos** (flags): tempo + motivo (palavra provável errada, nome
  próprio, alucinação, repetição).

---

## 2. Os dois métodos (e por que juntos)

"Comparar legendas entre si" sozinho é **relativo** e cego ao áudio. Como não há
transcrição humana de referência, a "realidade" é o **áudio** — então os sinais
precisam ser ancorados nele.

### Método 1 — Consenso (Voxtral × Transcribe)
Dois motores **independentes** ouviram o mesmo áudio. Onde concordam na palavra →
alta confiança; onde divergem → suspeita. Medimos a **concordância** por
subsequência comum (LCS) entre as palavras das duas transcrições (normalizadas:
minúsculas, sem acento/pontuação). É determinístico, barato (JS puro) e ancorado
no áudio (via a 2ª opinião do Transcribe).
- **Força:** pega substituições que um modelo faria e o outro não.
- **Furo:** se os dois erram igual, não percebe → por isso não vai sozinho.

### Método 2 — LLM-juiz ancorado
Um LLM (o mesmo do Wizard, `model.analysis`) recebe a legenda **candidata** + a
**referência** (Transcribe) e devolve, em JSON, uma **nota 0-100**, um
**comentário** e uma lista de **trechos suspeitos**. Como recebe as duas faixas
como evidência, ele julga discrepâncias concretas em vez de "achismo".
- **Força:** entende semântica — pega alucinação, repetição, frase sem sentido,
  nome próprio errado.
- **Cuidado:** LLM-juiz pode descalibrar; por isso a nota final combina com o
  consenso (determinístico).

### Nota final
```
textConfidence = round( wConsenso × consensoPct + wJuiz × notaLLM )   (0-100)
```
Pesos (`eval.weightConsensus`, `eval.weightJudge`) e tudo mais ficam em
**settings** (nada hardcoded). Padrão: 0,4 × consenso + 0,6 × juiz.

> **Evolução (v2):** quando o alinhamento forçado (MMS/WhisperX) entrar, ele
> fornece **confiança acústica por palavra** — o sinal mais forte e mais barato,
> direto contra o áudio. Entra como um 3º método, com peso próprio, sem mudar o
> resto.

---

## 3. Fluxo no pipeline

```
upload → transcode (MediaConvert) ─┐
                                   ├─ Transcribe → pt.vtt           (legenda 1)
                                   │
                               Finalize (status=revisar + custo)
                                   │
                                   └─(se pipeline.autoSdhMethod ≠ "")→ Worker SDH
                                          │
                                          ├─ Voxtral/24B → pt-sdh.vtt (legenda 2)
                                          └─ Evaluator (consenso + juiz) → eval  (passo 3)
```

- O avaliador roda **automaticamente** logo após a geração da legenda SDH
  (setting `eval.autoAfterSdh`, padrão ligado). Gerou SDH → já sai com nota.
- O disparo automático da **transcrição SDH no pipeline** (sem clique) é
  **opcional**, controlado por `pipeline.autoSdhMethod` (vazio = desligado, para
  não adicionar custo de Voxtral a todo upload sem decisão explícita). Defina
  para `v24b1p` para o pipeline produzir a legenda do 24B + avaliação sozinho.
- Também é possível rodar sob demanda: botão **Avaliar** por variante na tela de
  revisão → `POST /api/videos/{id}/evaluate-subtitle { method }`.

---

## 4. Custos individualizados

O relatório mostra o custo de cada peça que participou da legenda avaliada:

| Peça | Como é calculado |
|---|---|
| **Transcribe** | minutos de áudio × `cost.transcribePerAudioMin` (já no `cost.transcribeUSD` do vídeo) |
| **Voxtral/24B** | tokens da variante × tarifa (já em `sdhVariants.<método>.usd`) |
| **Juiz (LLM)** | tokens do Claude × `cost.analysisInputPer1k` / `cost.analysisOutputPer1k` |

O custo do **consenso** é ~zero (JS puro, sem chamada externa). O custo do juiz
por avaliação é da ordem de **US$ 0,003–0,01** (poucos milhares de tokens).

---

## 5. Settings (categoria "Avaliação de legenda")

| Chave | Padrão | O que faz |
|---|---|---|
| `eval.autoAfterSdh` | `true` | Roda o avaliador automaticamente após gerar uma legenda SDH |
| `eval.weightConsensus` | `0.4` | Peso do consenso na nota final |
| `eval.weightJudge` | `0.6` | Peso do LLM-juiz na nota final |
| `eval.maxCues` | `150` | Máx. de trechos por faixa enviados ao juiz (limita custo/latência) |
| `eval.prompt` | (texto) | Instrução do LLM-juiz (foco em texto, saída JSON) |
| `pipeline.autoSdhMethod` | `` (vazio) | Se setado (ex.: `v24b1p`), o pipeline gera a legenda SDH + avaliação automaticamente após o Transcribe |

Reusa `model.analysis` (Claude) e `cost.analysisInputPer1k`/`OutputPer1k`.

---

## 6. Onde isso aparece na UI

- **Tela de revisão (VideoReview):** botão **Avaliar** por variante; card com a
  **nota do juiz**, comentário, métodos (chips), custos individualizados e os
  trechos suspeitos. Nova seção **"Assets gerados"** lista todos os arquivos do
  vídeo (legenda do Transcribe, cada variante do Voxtral, descrição, HLS).
- **Analytics (detalhe do vídeo):** a nota e os custos individualizados por
  variante entram junto da tabela de custo/tempo.

---

## 7. Limite honesto

Sem referência humana, a nota é a **melhor aproximação** possível (não um "% de
acerto" calibrado). Se um dia quiser régua absoluta, transcreva ~2-3 min à mão
**uma vez** e calibre os pesos. O consenso e o juiz, juntos, já separam bem
"texto confiável" de "texto suspeito" — que é o que o fluxo de revisão precisa.
