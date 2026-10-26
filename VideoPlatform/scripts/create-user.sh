#!/usr/bin/env bash
# Cria um usuário admin no Cognito (self sign-up está desabilitado por segurança).
# Uso: scripts/create-user.sh email@exemplo.com 'SenhaForte123'
set -euo pipefail

STACK="${STACK:-videoplatform-stack}"
REGION="${AWS_REGION:-us-east-1}"
EMAIL="${1:?informe o e-mail}"
PASSWORD="${2:?informe a senha (min 10, maiúsc, minúsc e dígito)}"

USER_POOL_ID="$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)"

echo "==> Criando usuário $EMAIL no pool $USER_POOL_ID"
aws cognito-idp admin-create-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "$EMAIL" \
  --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true \
  --message-action SUPPRESS >/dev/null

aws cognito-idp admin-set-user-password \
  --user-pool-id "$USER_POOL_ID" \
  --username "$EMAIL" \
  --password "$PASSWORD" \
  --permanent

echo "==> Usuário pronto. Faça login na SPA com esse e-mail e senha."
