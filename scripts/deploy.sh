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
export AWS_REGION

echo ">> Conta/identidade:"; aws sts get-caller-identity --query Arn --output text

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
};
EOF
aws s3 sync frontend/ "s3://${FE_BUCKET}/" --exclude "*.example.js" --delete
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null

# --- Agentes no AgentCore Runtime ---
echo ">> Implantando agentes no AgentCore Runtime…"
./scripts/deploy-agents.sh || echo "!! deploy-agents.sh falhou — rode manualmente (ver README)."

echo ">> Concluído. Acesse: ${APP_URL}"
echo ">> Crie o 1º admin: ./scripts/create-admin-user.sh <email>"
