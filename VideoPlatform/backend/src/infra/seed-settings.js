'use strict';

/**
 * Custom Resource: popula a tabela de configurações (settings) com os valores
 * PADRÃO e os METADADOS (rótulo, descrição, categoria, tipo) de cada parâmetro.
 *
 * Grava com `attribute_not_exists(settingKey)` → só cria o que ainda não existe.
 * Assim o seed inicial roda uma vez; redeploys ADICIONAM chaves novas mas NUNCA
 * sobrescrevem valores já editados pelo usuário na tela de Config.
 *
 * Em runtime, os handlers leem SEMPRE da tabela (nenhum default de comportamento
 * fica no código dos handlers). Este arquivo é apenas o seed de inicialização.
 */

const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand } = require('@aws-sdk/lib-dynamodb');

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: process.env.AWS_REGION }));

// value é sempre string (o tipo diz como interpretar). order controla a exibição.
const SEED = [
  // ---- Modelos ----
  { settingKey: 'model.voxtral', type: 'string', category: 'Modelos', order: 2, editable: true,
    label: 'Modelo — legenda SDH (áudio)',
    description: 'Modelo de áudio (Mistral Voxtral) que transcreve a fala com timestamps precisos para a legenda SDH.',
    value: 'mistral.voxtral-small-24b-2507' },
  { settingKey: 'model.voxtralMini', type: 'string', category: 'Modelos', order: 3, editable: true,
    label: 'Modelo — legenda SDH (áudio, Mini)',
    description: 'Variante menor/mais barata do Voxtral (Mini 3B), usada na opção de legenda "Mini 1 passada" para comparação de qualidade × custo.',
    value: 'mistral.voxtral-mini-3b-2507' },
  { settingKey: 'model.pegasus', type: 'string', category: 'Modelos', order: 4, editable: true,
    label: 'Modelo — descrição de vídeo',
    description: 'Modelo de vídeo (TwelveLabs Pegasus) usado na DESCRIÇÃO do vídeo (cenas/visual). Não é usado na legenda SDH.',
    value: 'us.twelvelabs.pegasus-1-2-v1:0' },
  { settingKey: 'model.analysis', type: 'string', category: 'Modelos', order: 5, editable: true,
    label: 'Modelo — análise comparativa (Wizard)',
    description: 'LLM usado no Wizard de comparação de legendas (análise de diferenças e veredito).',
    value: 'us.anthropic.claude-sonnet-4-5-20250929-v1:0' },

  // ---- Idiomas ----
  { settingKey: 'lang.transcribe', type: 'string', category: 'Idiomas', order: 10, editable: true,
    label: 'Idioma do Transcribe',
    description: 'Código do idioma do áudio para a legenda automática (ex.: pt-BR, en-US, es-ES).',
    value: 'pt-BR' },
  { settingKey: 'lang.translations', type: 'csv', category: 'Idiomas', order: 11, editable: true,
    label: 'Idiomas de tradução',
    description: 'Idiomas-alvo oferecidos na tradução de legenda, separados por vírgula (ex.: es,en).',
    value: 'es,en' },

  // ---- Legenda SDH (Voxtral: fala + marcadores de som) ----
  { settingKey: 'sdh.prompt', type: 'string', category: 'Legenda SDH', order: 20, editable: true,
    label: 'Prompt de legendagem SDH (Voxtral)',
    description: 'Instrução enviada ao Voxtral. Define como transcrever a fala e marcar os sons não-falados ([música], [aplausos], [trovão]...). Ajuste aqui para calibrar o estilo dos marcadores sem redeploy.',
    value: `Você é um legendador profissional de legendas SDH (closed caption) em português do Brasil.
Transcreva a FALA exatamente, com timestamps precisos (use frações de segundo, ex.: 0m2.4s).
Marque também os SONS não-falados RELEVANTES (música, aplausos, risos, trovão, passos, motor, explosão...), essenciais para surdos — mas sem exagerar.
Formato: uma linha por trecho: [INÍCIO - FIM] CONTEÚDO
- CONTEÚDO = a fala, quando houver voz; OU o som entre colchetes minúsculos, ex.: [música].
- AGRUPE um som contínuo em UMA linha cobrindo toda a sua duração (ex.: risos por 20s = uma linha [risos] de 20s). NUNCA repita o mesmo som em linhas seguidas.
- Priorize a fala; marque o ambiente só quando ele muda. Não marque respiração/ruído mínimo. Não invente nem traduza.
Exemplo:
[0m0s - 0m4.5s] [música de abertura]
[0m5s - 0m8s] Bom dia!
[0m8s - 0m25s] [risos]
Responda apenas as linhas.` },
  { settingKey: 'sdh.maxAudioMB', type: 'number', category: 'Legenda SDH', order: 23, editable: true, unit: 'MB',
    label: 'Teto de áudio bruto por fatia (MB)',
    description: 'Teto de segurança do áudio (WAV bruto) por chamada ao Voxtral. O corpo do request do Voxtral é limitado a ~3 MiB em base64 (~1,33x), então ~2 MB brutos é o seguro. Cada fatia nunca excede este valor.',
    value: '2' },
  { settingKey: 'sdh.audioSampleRate', type: 'number', category: 'Legenda SDH', order: 24, editable: true, unit: 'Hz',
    label: 'Taxa de amostragem do áudio (Hz)',
    description: '16000 = melhor qualidade; 8000 = metade do tamanho (menos fatias). Afeta apenas novos processamentos.',
    value: '16000' },
  { settingKey: 'sdh.chunkSec', type: 'number', category: 'Legenda SDH', order: 25, editable: true, unit: 's',
    label: 'Duração de cada fatia de áudio (s)',
    description: 'O áudio é transcrito em fatias desta duração. A 16 kHz/mono, ~60s = ~2 MB (base64 ~2,4 MiB), com folga sob o limite de ~3 MiB do Voxtral. Limitado pelo teto de áudio por fatia.',
    value: '60' },
  { settingKey: 'sdh.chunkOverlapSec', type: 'number', category: 'Legenda SDH', order: 26, editable: true, unit: 's',
    label: 'Sobreposição entre fatias (s)',
    description: 'Trecho repetido entre fatias vizinhas. A costura usa o ponto médio da sobreposição, evitando que uma palavra na emenda seja cortada ou duplicada.',
    value: '3' },
  { settingKey: 'sdh.chunkConcurrency', type: 'number', category: 'Legenda SDH', order: 27, editable: true, unit: 'fatias',
    label: 'Fatias em paralelo',
    description: 'Quantas fatias são transcritas ao mesmo tempo. Maior = mais rápido, mas pode esbarrar em throttling do Bedrock.',
    value: '5' },
  { settingKey: 'sdh.maxChunks', type: 'number', category: 'Legenda SDH', order: 28, editable: true, unit: 'fatias',
    label: 'Número máximo de fatias',
    description: 'Limite de segurança para vídeos muito longos (duração máxima suportada = fatias × duração da fatia). Com 60s/fatia, 240 cobre ~4 h.',
    value: '240' },
  { settingKey: 'sdh.voxtralMaxTokens', type: 'number', category: 'Legenda SDH', order: 29, editable: true, unit: 'tokens',
    label: 'Voxtral — máximo de tokens de saída por fatia',
    description: 'Teto de tokens da transcrição por fatia. Deve ser folgado para não truncar a transcrição de uma fatia inteira.',
    value: '4000' },
  { settingKey: 'sdh.minCueSec', type: 'number', category: 'Legenda SDH', order: 30, editable: true, unit: 's',
    label: 'Duração mínima de cada legenda (s)',
    description: 'Cues muito curtas (ou de duração zero vindas do modelo) são estendidas até esta duração mínima.',
    value: '0.8' },
  { settingKey: 'sdh.speechMarginSec', type: 'number', category: 'Legenda SDH', order: 32, editable: true, unit: 's',
    label: 'Margem de silêncio p/ marcador de som (s)',
    description: 'Um marcador ([música], [risos]...) só aparece se NÃO houver fala dentro desta margem antes e depois. É o que impede o marcador de "grudar" na fala.',
    value: '2' },
  { settingKey: 'sdh.minMarkerSec', type: 'number', category: 'Legenda SDH', order: 33, editable: true, unit: 's',
    label: 'Duração mínima de marcador de som (s)',
    description: 'Marcadores em pausas mais curtas que isso são descartados.',
    value: '0.8' },
  { settingKey: 'sdh.maxMarkerSec', type: 'number', category: 'Legenda SDH', order: 34, editable: true, unit: 's',
    label: 'Duração máxima de marcador de som (s)',
    description: 'Tempo máximo que um marcador de som permanece na tela.',
    value: '6' },
  { settingKey: 'sdh.mergeMarkerGapSec', type: 'number', category: 'Legenda SDH', order: 31, editable: true, unit: 's',
    label: 'Fusão de marcadores de som iguais (s)',
    description: 'Marcadores de som idênticos e seguidos (ex.: [risos], [risos]...) separados por até este intervalo são fundidos em um único span. Evita repetição do mesmo som.',
    value: '2.5' },

  // ---- Análise comparativa (Wizard) ----
  { settingKey: 'analysis.maxCues', type: 'number', category: 'Análise comparativa', order: 35, editable: true, unit: 'trechos',
    label: 'Máx. de trechos por faixa (Wizard)',
    description: 'Quantos trechos (cues) de cada legenda são enviados ao LLM na comparação. Limita custo/latência; se a faixa for maior, analisa só os primeiros.',
    value: '150' },
  { settingKey: 'analysis.prompt', type: 'string', category: 'Análise comparativa', order: 36, editable: true,
    label: 'Prompt da análise comparativa (Wizard)',
    description: 'Instrução enviada ao LLM para comparar as duas legendas. Ajuste para calibrar o foco da análise.',
    value: `Você é um especialista em legendagem em português do Brasil. Vou te dar DUAS legendas do MESMO vídeo (A e B), com marcação de tempo. Compare-as e produza uma análise objetiva, em português, em tópicos:
1) Principais DIFERENÇAS (transcrição da fala, pontuação, onomatopeias, marcadores de som como [música]/[risos], sincronismo). Dê 3 a 6 exemplos citando o tempo.
2) Em cada exemplo, diga qual versão parece CORRETA e por quê.
3) VEREDITO: qual legenda é melhor no geral e o que faltaria para ficar ideal.
Seja conciso.` },

  // ---- Avaliação de legenda (qualidade do TEXTO) ----
  { settingKey: 'eval.autoAfterSdh', type: 'bool', category: 'Avaliação de legenda', order: 37, editable: true,
    label: 'Avaliar automaticamente após gerar SDH',
    description: 'Ao concluir uma legenda SDH (Voxtral), roda o avaliador de qualidade do texto (consenso + LLM-juiz) e grava a nota junto da variante.',
    value: 'true' },
  { settingKey: 'eval.weightConsensus', type: 'number', category: 'Avaliação de legenda', order: 37.1, editable: true,
    label: 'Peso do consenso na nota',
    description: 'Peso do método de consenso (concordância Voxtral×Transcribe) na nota final de confiança do texto.',
    value: '0.4' },
  { settingKey: 'eval.weightJudge', type: 'number', category: 'Avaliação de legenda', order: 37.2, editable: true,
    label: 'Peso do LLM-juiz na nota',
    description: 'Peso do LLM-juiz na nota final. Os pesos são reescalados automaticamente se algum método estiver indisponível.',
    value: '0.6' },
  { settingKey: 'eval.maxCues', type: 'number', category: 'Avaliação de legenda', order: 37.3, editable: true, unit: 'trechos',
    label: 'Máx. de trechos por faixa (juiz)',
    description: 'Quantos trechos de cada legenda são enviados ao LLM-juiz. Limita custo/latência; se maior, avalia só os primeiros.',
    value: '150' },
  { settingKey: 'eval.consensusWordCap', type: 'number', category: 'Avaliação de legenda', order: 37.4, editable: true, unit: 'palavras',
    label: 'Teto de palavras no consenso',
    description: 'Limite de palavras consideradas no cálculo de concordância (LCS). Protege o tempo de CPU em legendas muito longas.',
    value: '4000' },
  { settingKey: 'eval.prompt', type: 'string', category: 'Avaliação de legenda', order: 37.5, editable: true,
    label: 'Prompt do LLM-juiz',
    description: 'Instrução do juiz. Deve focar SÓ na qualidade do TEXTO (acerto das palavras) e pedir saída em JSON {score, comment, flags}.',
    value: `Você é um avaliador de qualidade de TRANSCRIÇÃO em português do Brasil.
Recebe a legenda CANDIDATA (gerada por uma IA que ouve o áudio) e uma legenda de REFERÊNCIA (Amazon Transcribe, que ouviu o MESMO áudio).
Avalie SOMENTE a qualidade do TEXTO da candidata — o acerto das PALAVRAS em relação ao que foi realmente dito. NÃO avalie o tempo/sincronismo.
Considere erros: palavra trocada, nome próprio errado, alucinação (texto inventado), repetição indevida, trecho sem sentido. Marcadores de som ([música], [risos]) são esperados na candidata e NÃO são erro.
Responda APENAS um JSON válido, sem texto fora dele, no formato:
{"score": <0-100>, "comment": "<1 a 3 frases em pt-BR>", "flags": [{"time":"mm:ss","issue":"<curto>"}]}
score = sua confiança de que o TEXTO da candidata está correto (100 = perfeito). flags = até 8 trechos mais suspeitos. Se não houver suspeitas, flags: [].` },
  { settingKey: 'pipeline.autoSdhMethod', type: 'string', category: 'Avaliação de legenda', order: 37.6, editable: true,
    label: 'Pipeline: gerar SDH automático (método)',
    description: 'Se preenchido (ex.: v24b1p), o pipeline gera a legenda SDH + avaliação automaticamente após o Transcribe, sem clique. Vazio = desligado (não adiciona custo de Voxtral a todo upload).',
    value: '' },

  // ---- Entrega e segurança ----
  { settingKey: 'delivery.signedCookieTtlSec', type: 'number', category: 'Entrega e segurança', order: 30, editable: true, unit: 's',
    label: 'TTL dos cookies assinados (s)',
    description: 'Por quanto tempo o acesso ao vídeo (cookies assinados do CloudFront) permanece válido após o play.',
    value: '7200' },

  // ---- Transcode (ABR) ----
  { settingKey: 'transcode.renditions', type: 'json', category: 'Transcode (ABR)', order: 40, editable: true,
    label: 'Perfis de resolução (ABR)',
    description: 'Resoluções/bitrates gerados no transcode. JSON: lista de {name,width,height,bitrate}. Afeta apenas novos processamentos.',
    value: JSON.stringify([
      { name: '1080p', width: 1920, height: 1080, bitrate: 5000000 },
      { name: '720p', width: 1280, height: 720, bitrate: 3000000 },
      { name: '480p', width: 854, height: 480, bitrate: 1500000 },
      { name: '360p', width: 640, height: 360, bitrate: 800000 },
    ]) },

  // ---- Custos (tarifas em USD) ----
  { settingKey: 'cost.mcSdPerMin', type: 'number', category: 'Custos (tarifas USD)', order: 50, editable: true, unit: 'USD/min',
    label: 'MediaConvert — SD (<720p) por min de saída', description: 'Tarifa por minuto de saída de perfis SD (ex.: 480p, 360p).', value: '0.0085' },
  { settingKey: 'cost.mcHdPerMin', type: 'number', category: 'Custos (tarifas USD)', order: 50.1, editable: true, unit: 'USD/min',
    label: 'MediaConvert — HD (720–1080p) por min de saída', description: 'Tarifa por minuto de saída de perfis HD (ex.: 720p, 1080p).', value: '0.017' },
  { settingKey: 'cost.mcUhdPerMin', type: 'number', category: 'Custos (tarifas USD)', order: 50.2, editable: true, unit: 'USD/min',
    label: 'MediaConvert — UHD (>1080p) por min de saída', description: 'Tarifa por minuto de saída de perfis UHD/4K.', value: '0.034' },
  { settingKey: 'cost.lambdaPerGbSecond', type: 'number', category: 'Custos (tarifas USD)', order: 50.3, editable: true, unit: 'USD/GB-s',
    label: 'Lambda — por GB-segundo', description: 'Tarifa de compute do Lambda (us-east-1 x86). Usada no custo do worker SDH e na orquestração.', value: '0.0000166667' },
  { settingKey: 'cost.sfnPerTransition', type: 'number', category: 'Custos (tarifas USD)', order: 50.4, editable: true, unit: 'USD/transição',
    label: 'Step Functions — por transição (Standard)', description: 'Tarifa por transição de estado do Step Functions Standard.', value: '0.000025' },
  { settingKey: 'cost.estSfnTransitions', type: 'number', category: 'Custos (tarifas USD)', order: 50.5, editable: true, unit: 'transições',
    label: 'Orquestração — transições estimadas por vídeo', description: 'Estimativa de transições do Step Functions por processamento (pipeline).', value: '8' },
  { settingKey: 'cost.estPipelineLambdaGbSec', type: 'number', category: 'Custos (tarifas USD)', order: 50.6, editable: true, unit: 'GB-s',
    label: 'Orquestração — GB-s de Lambda estimados por vídeo', description: 'Estimativa de GB-segundos somados das Lambdas curtas da pipeline (start/callbacks/finalize).', value: '6' },
  { settingKey: 'cost.transcribePerAudioMin', type: 'number', category: 'Custos (tarifas USD)', order: 51, editable: true, unit: 'USD/min',
    label: 'Transcribe — por minuto de áudio', description: 'Tarifa estimada por minuto de áudio transcrito.', value: '0.024' },
  { settingKey: 'cost.translatePerChar', type: 'number', category: 'Custos (tarifas USD)', order: 52, editable: true, unit: 'USD/char',
    label: 'Translate — por caractere', description: 'Tarifa estimada por caractere traduzido.', value: '0.000015' },
  { settingKey: 'cost.voxtralInputPer1k', type: 'number', category: 'Custos (tarifas USD)', order: 55, editable: true, unit: 'USD/1k',
    label: 'Voxtral 24B — input por 1k tokens', description: 'Tarifa real da Bedrock p/ Voxtral Small 24B: ~US$0,10/1M = 0,0001/1k.', value: '0.0001' },
  { settingKey: 'cost.voxtralOutputPer1k', type: 'number', category: 'Custos (tarifas USD)', order: 56, editable: true, unit: 'USD/1k',
    label: 'Voxtral 24B — output por 1k tokens', description: 'Tarifa real da Bedrock p/ Voxtral Small 24B: ~US$0,30/1M = 0,0003/1k.', value: '0.0003' },
  { settingKey: 'cost.voxtralMiniInputPer1k', type: 'number', category: 'Custos (tarifas USD)', order: 55.5, editable: true, unit: 'USD/1k',
    label: 'Voxtral Mini — input por 1k tokens', description: 'Tarifa do Voxtral Mini 3B (estimativa; ajuste pelo Cost Explorer). Tokens brutos são guardados por variante p/ recomputar.', value: '0.00005' },
  { settingKey: 'cost.voxtralMiniOutputPer1k', type: 'number', category: 'Custos (tarifas USD)', order: 56.5, editable: true, unit: 'USD/1k',
    label: 'Voxtral Mini — output por 1k tokens', description: 'Tarifa de saída do Voxtral Mini 3B (estimativa).', value: '0.00015' },
  { settingKey: 'cost.analysisInputPer1k', type: 'number', category: 'Custos (tarifas USD)', order: 59, editable: true, unit: 'USD/1k',
    label: 'Análise (Wizard) — input por 1k tokens', description: 'Tarifa de entrada do LLM da análise comparativa (ex.: Claude Sonnet).', value: '0.003' },
  { settingKey: 'cost.analysisOutputPer1k', type: 'number', category: 'Custos (tarifas USD)', order: 60, editable: true, unit: 'USD/1k',
    label: 'Análise (Wizard) — output por 1k tokens', description: 'Tarifa de saída do LLM da análise comparativa.', value: '0.015' },
  { settingKey: 'cost.pegasusPerMin', type: 'number', category: 'Custos (tarifas USD)', order: 57, editable: true, unit: 'USD/min',
    label: 'Pegasus — por minuto de vídeo (estimativa)', description: 'Estimativa de custo por minuto de vídeo analisado pelo Pegasus.', value: '0.08' },
  { settingKey: 'cost.s3PerGbMonth', type: 'number', category: 'Custos (tarifas USD)', order: 58, editable: true, unit: 'USD/GB-mês',
    label: 'S3 — por GB-mês', description: 'Tarifa estimada de armazenamento no S3.', value: '0.023' },
];

async function seed(tableName) {
  for (const item of SEED) {
    try {
      await ddb.send(
        new PutCommand({
          TableName: tableName,
          Item: { ...item, updatedAt: new Date().toISOString() },
          ConditionExpression: 'attribute_not_exists(settingKey)',
        })
      );
    } catch (e) {
      if (e.name === 'ConditionalCheckFailedException') continue; // já existe: preserva valor do usuário
      throw e;
    }
  }
}

exports.handler = async (event) => {
  const type = event.RequestType;
  if (type === 'Delete') return { PhysicalResourceId: event.PhysicalResourceId || 'settings-seed' };
  const tableName = event.ResourceProperties.SettingsTable;
  await seed(tableName);
  return { PhysicalResourceId: 'settings-seed', Data: { seeded: String(SEED.length) } };
};

module.exports.SEED = SEED;
module.exports.handler = exports.handler;
