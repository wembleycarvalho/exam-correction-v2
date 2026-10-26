// Config em runtime. O deploy sobrescreve este arquivo no bucket do frontend
// com os valores reais da stack (apiBase vazio = same-origin via CloudFront).
// Em desenvolvimento, prefira o arquivo .env (VITE_*).
window.__CONFIG__ = window.__CONFIG__ || {};
