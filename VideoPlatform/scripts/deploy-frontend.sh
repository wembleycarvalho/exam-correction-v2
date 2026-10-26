#!/usr/bin/env bash
# Builda a SPA, injeta a config da stack (same-origin) e publica no bucket do
# frontend, invalidando o cache do CloudFront.
#
# Pré-requisitos: stack já implantada (cdk deploy) e credenciais no shell (source .env).
set -euo pipefail

STACK="${STACK:-videoplatform-stack}"
REGION="${AWS_REGION:-us-east-1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

out() {
  aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

echo "==> Lendo outputs da stack $STACK"
USER_POOL_ID="$(out UserPoolId)"
CLIENT_ID="$(out UserPoolClientId)"
FRONTEND_BUCKET="$(out FrontendBucketName)"
DIST_DOMAIN="$(out CloudFrontDomain)"
DIST_ID="$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?DomainName=='$DIST_DOMAIN'].Id" --output text)"

echo "    UserPool=$USER_POOL_ID Client=$CLIENT_ID Bucket=$FRONTEND_BUCKET Dist=$DIST_ID"

echo "==> Build do frontend"
cd "$ROOT/frontend"
npm install --no-audit --no-fund
npm run build

echo "==> Injetando config.js (apiBase vazio = same-origin via CloudFront)"
cat > dist/config.js <<EOF
window.__CONFIG__ = {
  apiBase: "",
  region: "$REGION",
  userPoolId: "$USER_POOL_ID",
  userPoolClientId: "$CLIENT_ID"
};
EOF

echo "==> Sync para s3://$FRONTEND_BUCKET"
aws s3 sync dist "s3://$FRONTEND_BUCKET/" --delete

echo "==> Invalidando CloudFront"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null

echo "==> Pronto! Acesse: https://$DIST_DOMAIN"
