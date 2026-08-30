#!/usr/bin/env bash
# Deploy CIRÚRGICO (interino) do Orientador Context — NÃO redeploya o portal.
#  1) stack CDK standalone (Lambda + HTTP API + Cognito importado + IAM)
#  2) liga o behavior /orientador-context/* na distribution existente (aditivo/idempotente)
#  3) publica o frontend/app.js + invalida o cache
# Reproduzível. Requer: AWS CLI + credenciais, Node/npx. NÃO requer Docker.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"

[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
: "${STACK:=exam-correction-v2}"; : "${MOODLE_STACK:=moodle-backbone}"
export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
export CDK_DEFAULT_REGION="$AWS_REGION"
export JSII_SILENCE_WARNING_DEPRECATED_NODE_VERSION=1

O(){ aws cloudformation describe-stacks --stack-name "$STACK" --region "$AWS_REGION" \
       --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
export OCTX_USER_POOL_ID="$(O UserPoolId)"
export OCTX_CLIENT_ID="$(O UserPoolClientId)"
DIST_ID="$(O DistributionId)"; FE_BUCKET="$(O FrontendBucketName)"
export OCTX_LAKE_BUCKET="$(aws cloudformation describe-stacks --stack-name "$MOODLE_STACK" \
  --region "$AWS_REGION" --query "Stacks[0].Outputs[?OutputKey=='DataLakeBucket'].OutputValue" --output text)"
echo ">> UserPool=$OCTX_USER_POOL_ID Dist=$DIST_ID Lake=$OCTX_LAKE_BUCKET"

echo ">> Construindo layer boto3 recente…"
rm -rf layer && mkdir -p layer/python && python3 -m pip install -q --target layer/python "boto3>=1.35.0"

echo ">> Deploy da stack standalone…"
python3 -m venv .venv 2>/dev/null || true
./.venv/bin/pip install -q -r requirements.txt
CDK_APP=".venv/bin/python app.py"
npx --yes aws-cdk@latest deploy orientador-context --app "$CDK_APP" --require-approval never \
  --outputs-file out.json >/dev/null
API_DOMAIN="$(python3 -c "import json;print(json.load(open('out.json'))['orientador-context']['ApiDomain'])")"
echo ">> API=$API_DOMAIN"

echo ">> Ligando o behavior /orientador-context/* no CloudFront…"
./.venv/bin/python cloudfront_behavior.py --dist "$DIST_ID" --api "$API_DOMAIN"

echo ">> Publicando o frontend (app.js) + invalidando…"
aws s3 cp "$ROOT/frontend/app.js" "s3://$FE_BUCKET/app.js" --content-type application/javascript --region "$AWS_REGION" >/dev/null
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/app.js" --region "$AWS_REGION" >/dev/null

echo ">> Pronto. Aguarde a distribution propagar (~5 min) e teste /orientador-context/health."
