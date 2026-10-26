#!/usr/bin/env bash
# Cria o 1º usuário admin no Cognito (sem self-signup). Uso: ./scripts/create-admin-user.sh <email>
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${AWS_REGION:=us-east-1}"; : "${STACK_NAME:=exam-correction-v2}"; export AWS_REGION

EMAIL="${1:-${BOOTSTRAP_ADMIN_EMAIL:-}}"
[[ -z "$EMAIL" ]] && { echo "Uso: $0 <email>"; exit 1; }

USER_POOL_ID="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)"

aws cognito-idp admin-create-user --user-pool-id "$USER_POOL_ID" --username "$EMAIL" \
  --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL >/dev/null
aws cognito-idp admin-add-user-to-group --user-pool-id "$USER_POOL_ID" \
  --username "$EMAIL" --group-name admin >/dev/null
echo ">> Admin criado: ${EMAIL} (senha temporária enviada por e-mail; troca no 1º acesso)."
