#!/usr/bin/env bash
# Deploy CIRÚRGICO do módulo AgentCore — Gateway Inference — NÃO redeploya o portal.
#  1) stack CDK standalone (Router Lambda + HTTP API + Cognito importado + IAM)
#  2) liga o behavior /agentcore/* na distribution existente (aditivo/idempotente)
#  3) publica o frontend/app.js + invalida o cache
# Pré-requisito: o agente já no Runtime (agentcore-gateway-inference/runtime/deploy-runtime.sh)
# e o InferenceDemoStack presente (Gateway + segredo m2m). Reproduzível. NÃO requer Docker.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
: "${STACK:=exam-correction-v2}"; : "${INFERENCE_STACK:=InferenceDemoStack}"
export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
export CDK_DEFAULT_REGION="$AWS_REGION"
export JSII_SILENCE_WARNING_DEPRECATED_NODE_VERSION=1

O(){ aws cloudformation describe-stacks --stack-name "$STACK" --region "$AWS_REGION" \
       --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
export OCTX_USER_POOL_ID="$(O UserPoolId)"
export OCTX_CLIENT_ID="$(O UserPoolClientId)"
DIST_ID="$(O DistributionId)"; FE_BUCKET="$(O FrontendBucketName)"
export GWINF_SECRET_ARN="$(aws cloudformation list-stack-resources --stack-name "$INFERENCE_STACK" \
  --region "$AWS_REGION" --query "StackResourceSummaries[?ResourceType=='AWS::SecretsManager::Secret'].PhysicalResourceId" --output text)"
echo ">> UserPool=$OCTX_USER_POOL_ID Dist=$DIST_ID Secret=${GWINF_SECRET_ARN:0:60}…"

echo ">> Construindo layer boto3 recente…"
rm -rf layer && mkdir -p layer/python && python3 -m pip install -q --target layer/python "boto3>=1.35.0"

echo ">> Deploy da stack standalone…"
python3 -m venv .venv 2>/dev/null || true
./.venv/bin/pip install -q -r requirements.txt
npx --yes aws-cdk@latest deploy agentcore-gateway-inference --app ".venv/bin/python app.py" \
  --require-approval never --outputs-file out.json >/dev/null
API_DOMAIN="$(python3 -c "import json;print(json.load(open('out.json'))['agentcore-gateway-inference']['ApiDomain'])")"
echo ">> API=$API_DOMAIN"

echo ">> Ligando o behavior /agentcore/* no CloudFront…"
./.venv/bin/python cloudfront_behavior.py --dist "$DIST_ID" --api "$API_DOMAIN"

echo ">> Publicando o frontend (app.js) + invalidando…"
aws s3 cp "$ROOT/frontend/app.js" "s3://$FE_BUCKET/app.js" --content-type application/javascript --region "$AWS_REGION" >/dev/null
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/app.js" --region "$AWS_REGION" >/dev/null

echo ">> Pronto. Aguarde a distribution propagar (~5 min) e teste /agentcore/health."
