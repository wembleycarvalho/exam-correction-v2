/// <reference types="vite/client" />

// Shaka é importado do build compilado; tipamos como any para evitar fricção.
declare module 'shaka-player/dist/shaka-player.compiled.js';

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_REGION?: string;
  readonly VITE_USER_POOL_ID?: string;
  readonly VITE_USER_POOL_CLIENT_ID?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface Window {
  __CONFIG__?: {
    apiBase?: string;
    region?: string;
    userPoolId?: string;
    userPoolClientId?: string;
  };
}
