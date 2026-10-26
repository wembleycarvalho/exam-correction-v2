#!/usr/bin/env bash
# Deploy reproduzível do Exam Correction v2.
# Pré-requisitos: AWS CLI + credenciais (aws configure/SSO), Node/CDK, Python 3.12.
# Uso: ./scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# --- Carrega .env ---
if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${AWS_REGION:=us-east-1}"
: "${STACK_NAME:=exam-correction-v2}"
: "${WORKER_CONCURRENCY:=5}"
: "${DEFAULT_MODEL_ID:=}"
: "${MODEL_PRICING:=}"
# Cartão-resposta (OMR server-side). BUILD_OMR_LAYER=1 constrói/publica a layer OpenCV.
# Vazio = OMR server-side desabilitado (leitura no navegador segue funcionando).
: "${BUILD_OMR_LAYER:=1}"
: "${OMR_LAYER_ARN:=}"
# Provas Online (Knowledge Base). Provisione com DEPLOY_KB=1 (acervo sintético de demo)
# ou defina KB_ID/KB_BUCKET (KB próprio). Vazio = módulo Provas Online desabilitado.
: "${DEPLOY_KB:=0}"
: "${KB_ID:=}"
: "${KB_BUCKET:=}"
: "${BOOTSTRAP_ADMIN_EMAIL:=}"
# Entrevistador Virtual (serviço próprio, streaming/voz). URL embutida no capítulo do SPA.
# Vazio = capítulo mostra placeholder "não configurado".
: "${INTERVIEWER_URL:=}"
# Seleção de módulos do portal (opt-in). Vazio = comportamento padrão da stack
# (default correcao,entrevistador) — deploy inalterado. Para ativar o Orientador Context:
#   MODULES="correcao,entrevistador,orientador-context" ./scripts/deploy.sh
: "${MODULES:=}"
: "${MOODLE_STACK:=moodle-backbone}"
: "${ORIENTADOR_CONTEXT_LAKE_BUCKET:=}"
export AWS_REGION

echo ">> Conta/identidade:"; aws sts get-caller-identity --query Arn --output text

# --- Layer OpenCV do OMR (cartão-resposta server-side), independente da stack ---
if [[ -z "$OMR_LAYER_ARN" && "$BUILD_OMR_LAYER" == "1" ]]; then
  echo ">> Construindo/publicando a layer OMR (OpenCV)…"
  ./scripts/build-omr-layer.sh || echo "!! build-omr-layer.sh falhou — OMR server-side ficará desabilitado."
fi
if [[ -z "$OMR_LAYER_ARN" && -f infra/omr-layer.json ]]; then
  OMR_LAYER_ARN="$(python3 -c "import json;print(json.load(open('infra/omr-layer.json')).get('omrLayerArn',''))")"
fi
[[ -n "$OMR_LAYER_ARN" ]] && echo ">> OMR server-side habilitado." || \
  echo ">> OMR server-side desabilitado (só leitura de cartão no navegador)."

# --- Knowledge Base do módulo Provas Online (opcional) ---
if [[ "$DEPLOY_KB" == "1" ]]; then
  echo ">> Provisionando Knowledge Base DEMO (conteúdo sintético)…"
  ./scripts/deploy-kb.sh
fi
# Herda kbId/kbBucket do provisionamento (infra/kb-config.json), salvo se já vierem do ambiente.
if [[ -z "$KB_ID" && -f infra/kb-config.json ]]; then
  KB_ID="$(python3 -c "import json;print(json.load(open('infra/kb-config.json')).get('kbId',''))")"
  KB_BUCKET="$(python3 -c "import json;print(json.load(open('infra/kb-config.json')).get('kbBucket',''))")"
fi
[[ -n "$KB_ID" ]] && echo ">> Provas Online habilitado (kbId=${KB_ID})." || \
  echo ">> Provas Online desabilitado (sem KB). Defina DEPLOY_KB=1 ou KB_ID/KB_BUCKET."

# --- Módulo Orientador Context (opt-in): resolve o bucket do data lake do backbone Moodle ---
if [[ ",$MODULES," == *",orientador-context,"* && -z "$ORIENTADOR_CONTEXT_LAKE_BUCKET" ]]; then
  ORIENTADOR_CONTEXT_LAKE_BUCKET="$(aws cloudformation describe-stacks --stack-name "$MOODLE_STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='DataLakeBucket'].OutputValue" --output text 2>/dev/null || true)"
  [[ -n "$ORIENTADOR_CONTEXT_LAKE_BUCKET" ]] \
    && echo ">> Orientador Context: data lake = ${ORIENTADOR_CONTEXT_LAKE_BUCKET}" \
    || echo "!! Orientador Context ativado mas sem DataLakeBucket (stack '$MOODLE_STACK'). O agente subirá sem acesso ao S3."
fi
# Contexto extra (aditivo; vazio por padrão -> deploy padrão inalterado).
EXTRA_CTX=""
[[ -n "$MODULES" ]] && EXTRA_CTX="$EXTRA_CTX -c modules=$MODULES"
[[ -n "$ORIENTADOR_CONTEXT_LAKE_BUCKET" ]] && EXTRA_CTX="$EXTRA_CTX -c orientadorContextLakeBucket=$ORIENTADOR_CONTEXT_LAKE_BUCKET"

# --- Segredo de origem (CloudFront -> API) ---
ORIGIN_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"

# --- CDK ---
pushd infra >/dev/null
python3 -m venv .venv 2>/dev/null || true
./.venv/bin/pip install -q --upgrade pip >/dev/null
./.venv/bin/pip install -q -r requirements.txt boto3
export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
export CDK_DEFAULT_REGION="$AWS_REGION"
export JSII_SILENCE_WARNING_DEPRECATED_NODE_VERSION=1
CDK_APP=".venv/bin/python app.py"
npx --yes aws-cdk@latest bootstrap "aws://${CDK_DEFAULT_ACCOUNT}/${AWS_REGION}" \
  --app "$CDK_APP" >/dev/null 2>&1 || true
npx --yes aws-cdk@latest deploy "$STACK_NAME" --app "$CDK_APP" --require-approval never \
  -c stackName="$STACK_NAME" -c workerConcurrency="$WORKER_CONCURRENCY" \
  -c defaultModelId="$DEFAULT_MODEL_ID" -c modelPricing="$MODEL_PRICING" \
  -c kbId="$KB_ID" -c kbBucket="$KB_BUCKET" -c omrLayerArn="$OMR_LAYER_ARN" \
  $EXTRA_CTX \
  --parameters "OriginSecret=${ORIGIN_SECRET}" \
  --outputs-file cdk-outputs.json
popd >/dev/null

out(){ python3 -c "import json,sys;print(json.load(open('infra/cdk-outputs.json'))['$STACK_NAME'].get('$1',''))"; }
DIST_DOMAIN="$(out DistributionDomain)"; DIST_ID="$(out DistributionId)"
USER_POOL_ID="$(out UserPoolId)"; CLIENT_ID="$(out UserPoolClientId)"
COG_PREFIX="$(out CognitoDomainPrefix)"; FE_BUCKET="$(out FrontendBucketName)"
UPLOADS_BUCKET="$(out UploadsBucketName)"
APP_URL="https://${DIST_DOMAIN}"

echo ">> App: ${APP_URL}"

# --- Callback/logout URLs do Cognito -> domínio do CloudFront ---
aws cognito-idp update-user-pool-client --user-pool-id "$USER_POOL_ID" --client-id "$CLIENT_ID" \
  --allowed-o-auth-flows code --allowed-o-auth-scopes openid email profile \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers COGNITO \
  --callback-urls "${APP_URL}/" --logout-urls "${APP_URL}/" >/dev/null

# --- Restringe CORS do bucket de uploads ao domínio do CloudFront ---
aws s3api put-bucket-cors --bucket "$UPLOADS_BUCKET" --cors-configuration "{
  \"CORSRules\":[{\"AllowedMethods\":[\"PUT\",\"GET\"],\"AllowedOrigins\":[\"${APP_URL}\"],
  \"AllowedHeaders\":[\"*\"],\"MaxAgeSeconds\":3000}]}"

# --- Semente: rubrica ENEM (+ model_config se DEFAULT_MODEL_ID) ---
STACK_NAME="$STACK_NAME" AWS_REGION="$AWS_REGION" DEFAULT_MODEL_ID="$DEFAULT_MODEL_ID" \
  infra/.venv/bin/python scripts/seed.py

# --- runtime-config.js + sync do frontend ---
cat > frontend/runtime-config.js <<EOF
window.EXAM_CONFIG = {
  region: "${AWS_REGION}",
  userPoolId: "${USER_POOL_ID}",
  clientId: "${CLIENT_ID}",
  cognitoDomain: "${COG_PREFIX}",
  apiBase: "/api",
  interviewerUrl: "${INTERVIEWER_URL}",
};
EOF
# opencv.js (leitura de cartão no navegador) — baixado se ausente (~11MB, não versionado no
# repo). Precisa existir localmente para o `sync --delete` não removê-lo do bucket.
if [[ ! -f frontend/opencv.js ]]; then
  echo ">> Baixando opencv.js (OMR no navegador)…"
  curl -fsSL -o frontend/opencv.js "https://docs.opencv.org/4.x/opencv.js" || \
    echo "!! Falha ao baixar opencv.js — leitura de cartão no navegador ficará indisponível."
fi
aws s3 sync frontend/ "s3://${FE_BUCKET}/" --exclude "*.example.js" --delete
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null

# --- Agentes no AgentCore Runtime ---
echo ">> Implantando agentes no AgentCore Runtime…"
./scripts/deploy-agents.sh || echo "!! deploy-agents.sh falhou — rode manualmente (ver README)."

# --- 1º admin (opcional, se BOOTSTRAP_ADMIN_EMAIL definido) ---
if [[ -n "$BOOTSTRAP_ADMIN_EMAIL" ]]; then
  echo ">> Criando 1º admin (${BOOTSTRAP_ADMIN_EMAIL})…"
  ./scripts/create-admin-user.sh "$BOOTSTRAP_ADMIN_EMAIL" || \
    echo "!! Falha ao criar admin — rode: ./scripts/create-admin-user.sh <email>"
fi

echo ">> Concluído. Acesse: ${APP_URL}"
[[ -z "$BOOTSTRAP_ADMIN_EMAIL" ]] && \
  echo ">> Crie o 1º admin: ./scripts/create-admin-user.sh <email>"
