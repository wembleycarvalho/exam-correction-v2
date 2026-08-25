#!/usr/bin/env bash
# Bateria de smoke/e2e por módulo contra a infra VIVA (via CloudFront).
# Verifica que cada módulo "voltou funcionando" após um deploy.
#
# Uso:
#   ./scripts/smoke-test.sh                 # checagens públicas (frontend, entrevistador, lms health)
#   COGNITO_ID_TOKEN=<jwt> ./scripts/smoke-test.sh   # + checagens autenticadas (api/orientador/lms)
#
# O JWT pode ser copiado do navegador logado (sessionStorage 'id_token') — as rotas /api,
# /orientador e /lms (exceto /lms/health) exigem Cognito.
set -uo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${AWS_REGION:=us-east-1}"
: "${STACK_NAME:=exam-correction-v2}"

# Base URL = domínio do CloudFront (dos outputs do stack, ou BASE_URL do ambiente).
if [[ -z "${BASE_URL:-}" ]]; then
  DOMAIN="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='DistributionDomain'].OutputValue | [0]" --output text 2>/dev/null)"
  [[ -n "$DOMAIN" && "$DOMAIN" != "None" ]] && BASE_URL="https://$DOMAIN"
fi
[[ -z "${BASE_URL:-}" ]] && { echo "!! defina BASE_URL ou garanta o output DistributionDomain"; exit 2; }
echo ">> Base: $BASE_URL"
TOKEN="${COGNITO_ID_TOKEN:-}"

PASS=0; FAIL=0; SKIP=0
# check <nome> <método> <path> <status_esperado> <auth:0|1> [grep_no_corpo]
check() {
  local name="$1" method="$2" path="$3" want="$4" auth="$5" needle="${6:-}"
  local hdr=(); if [[ "$auth" == "1" ]]; then
    if [[ -z "$TOKEN" ]]; then printf "  SKIP  %-28s (sem COGNITO_ID_TOKEN)\n" "$name"; SKIP=$((SKIP+1)); return; fi
    hdr=(-H "Authorization: Bearer $TOKEN")
  fi
  local body sc
  body="$(curl -s -m 25 -o /tmp/smoke_body -w '%{http_code}' -X "$method" ${hdr[@]+"${hdr[@]}"} "$BASE_URL$path")"
  sc="$body"
  local ok=1
  [[ "$sc" == "$want" ]] || ok=0
  if [[ -n "$needle" ]] && ! grep -q "$needle" /tmp/smoke_body 2>/dev/null; then ok=0; fi
  if [[ "$ok" == "1" ]]; then printf "  PASS  %-28s [%s %s -> %s]\n" "$name" "$method" "$path" "$sc"; PASS=$((PASS+1));
  else printf "  FAIL  %-28s [%s %s -> %s, esperado %s]\n" "$name" "$method" "$path" "$sc" "$want"; FAIL=$((FAIL+1)); fi
}

echo "== Público =="
check "frontend"            GET  "/"                          200 0 "app.js"
check "entrevistador health" GET "/entrevistador/health"      200 0 "ok"
check "entrevistador vagas"  GET "/entrevistador/api/vagas"   200 0
check "lms health"          GET  "/lms/health"                200 0 "ok"

echo "== Autenticado (Cognito) =="
check "api pricing"         GET  "/api/pricing"               200 1
check "orientador bootstrap" GET "/orientador/api/bootstrap"  200 1
check "lms catalog"         GET  "/lms/catalog"               200 1
# busca por texto (só valida que responde 200 com JSON de resultados)
if [[ -n "$TOKEN" ]]; then
  sc="$(curl -s -m 40 -o /tmp/smoke_body -w '%{http_code}' -X POST \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"mode":"text","query":"introducao","top_k":3}' "$BASE_URL/lms/search")"
  if [[ "$sc" == "200" ]] && grep -q '"results"' /tmp/smoke_body; then
    printf "  PASS  %-28s [POST /lms/search -> 200]\n" "lms search (texto)"; PASS=$((PASS+1));
  else printf "  FAIL  %-28s [POST /lms/search -> %s]\n" "lms search (texto)" "$sc"; FAIL=$((FAIL+1)); fi
else printf "  SKIP  %-28s (sem COGNITO_ID_TOKEN)\n" "lms search (texto)"; SKIP=$((SKIP+1)); fi

echo ">> Resultado: PASS=$PASS FAIL=$FAIL SKIP=$SKIP"
[[ "$FAIL" == "0" ]] || exit 1
