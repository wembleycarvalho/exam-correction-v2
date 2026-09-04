#!/usr/bin/env bash
# Deploy CIRÚRGICO do módulo Atendimento — NÃO redeploya o portal.
#  1) semeia a config no SSM /atendimento/* (WABA, phone-number-id, bucket de campanhas, etc.)
#  2) stack CDK standalone (Router Lambda + HTTP API + Cognito importado + IAM por serviço)
#  3) liga o behavior /atendimento/* na distribution existente (aditivo/idempotente)
#  4) publica o frontend/app.js + invalida o cache
# Reproduzível. NÃO requer Docker. Pré-req: instância Connect de demo + WABA já existentes.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
: "${STACK:=exam-correction-v2}"
export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
export CDK_DEFAULT_REGION="$AWS_REGION"
export JSII_SILENCE_WARNING_DEPRECATED_NODE_VERSION=1
ACCOUNT="$CDK_DEFAULT_ACCOUNT"

O(){ aws cloudformation describe-stacks --stack-name "$STACK" --region "$AWS_REGION" \
       --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
export OCTX_USER_POOL_ID="$(O UserPoolId)"
export OCTX_CLIENT_ID="$(O UserPoolClientId)"
DIST_ID="$(O DistributionId)"; FE_BUCKET="$(O FrontendBucketName)"

# --- config do módulo (defaults = recursos de demo do projeto Harness; sobrescrevíveis por env) ---
: "${WABA_ID:=waba-b7e8aaaa528c4a73a9dc4212f4323c79}"
: "${WHATSAPP_PHONE_NUMBER_ID:=phone-number-id-fe268d418d9b4e1296c47f86795987df}"
: "${CP_DOMAIN:=amazon-connect-connect-demo-ps}"
: "${META_API_VERSION:=v20.0}"
: "${CONNECT_INSTANCE_ID:=82a1c25d-b923-4bd2-9c21-e7eba7f052ac}"
export ATEND_CAMPAIGN_BUCKET="${CAMPAIGN_BUCKET:-campanhas-connect-${ACCOUNT}}"
export CONNECT_INSTANCE_ID CP_DOMAIN

echo ">> UserPool=$OCTX_USER_POOL_ID Dist=$DIST_ID Bucket=$ATEND_CAMPAIGN_BUCKET"

echo ">> Semeando SSM /atendimento/* …"
put(){ aws ssm put-parameter --name "/atendimento/$1" --type String --overwrite --value "$2" --region "$AWS_REGION" >/dev/null; }
put waba-id           "$WABA_ID"
put phone-number-id   "$WHATSAPP_PHONE_NUMBER_ID"
put campaign-bucket   "$ATEND_CAMPAIGN_BUCKET"
put cp-domain         "$CP_DOMAIN"
put meta-api-version  "$META_API_VERSION"

echo ">> Garantindo o bucket de campanhas ($ATEND_CAMPAIGN_BUCKET)…"
aws s3api create-bucket --bucket "$ATEND_CAMPAIGN_BUCKET" --region "$AWS_REGION" >/dev/null 2>&1 || true

echo ">> Construindo layer boto3 recente…"
rm -rf layer && mkdir -p layer/python && python3 -m pip install -q --target layer/python "boto3>=1.35.0"

echo ">> Deploy da stack standalone…"
python3 -m venv .venv 2>/dev/null || true
./.venv/bin/pip install -q -r requirements.txt
npx --yes aws-cdk@latest deploy atendimento --app ".venv/bin/python app.py" \
  --require-approval never --outputs-file out.json >/dev/null
API_DOMAIN="$(python3 -c "import json;print(json.load(open('out.json'))['atendimento']['ApiDomain'])")"
echo ">> API=$API_DOMAIN"

echo ">> Ligando o behavior /atendimento/* no CloudFront… (python3 do sistema tem boto3; a venv do CDK não)"
python3 cloudfront_behavior.py --dist "$DIST_ID" --api "$API_DOMAIN"

echo ">> Publicando o frontend (app.js) + invalidando…"
aws s3 cp "$ROOT/frontend/app.js" "s3://$FE_BUCKET/app.js" --content-type application/javascript --region "$AWS_REGION" >/dev/null
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/app.js" --region "$AWS_REGION" >/dev/null

echo ">> Pronto. Aguarde a distribution propagar (~5 min) e teste https://<cf>/atendimento/api/health (com token) ou o API domain /atendimento/health (sem token)."
