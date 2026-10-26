/**
 * Identidade de INFRAESTRUTURA (não é "configuração de comportamento").
 * Todos os parâmetros ajustáveis (modelos, idiomas, tarifas, TTL, ajustes de
 * SDH, perfis de ABR, taxa de áudio) ficam na tabela DynamoDB de settings e são
 * editáveis na tela de Config — ver backend/src/infra/seed-settings.js.
 *
 * O que fica aqui são apenas nomes/prefixos estruturais: mudá-los implica
 * recriar recursos e/ou quebrar dados existentes, então não são "config".
 */

export const APP_PREFIX = process.env.APP_PREFIX ?? 'videoplatform';
export const REGION = process.env.CDK_DEFAULT_REGION ?? process.env.AWS_REGION ?? 'us-east-1';

/** Prefixos (pastas lógicas) no bucket. Estruturais. */
export const RAW_PREFIX = 'raw-videos';
export const PROFILES_PREFIX = 'video-profiles';

/** Tags de alocação de custo aplicadas a todos os recursos. */
export const COST_TAGS = {
  project: APP_PREFIX,
};
