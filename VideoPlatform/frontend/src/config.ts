/**
 * Configuração resolvida em runtime: window.__CONFIG__ (/config.js) tem
 * prioridade; cai para as variáveis VITE_* do build em desenvolvimento.
 */
export interface AppConfig {
  apiBase: string; // '' = same-origin (CloudFront). Em dev, URL do API Gateway.
  region: string;
  userPoolId: string;
  userPoolClientId: string;
}

const rt = (typeof window !== 'undefined' && window.__CONFIG__) || {};

export const config: AppConfig = {
  apiBase: (rt.apiBase ?? import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, ''),
  region: rt.region ?? import.meta.env.VITE_REGION ?? 'us-east-1',
  userPoolId: rt.userPoolId ?? import.meta.env.VITE_USER_POOL_ID ?? '',
  userPoolClientId: rt.userPoolClientId ?? import.meta.env.VITE_USER_POOL_CLIENT_ID ?? '',
};

export const isConfigured = () => Boolean(config.userPoolId && config.userPoolClientId);
