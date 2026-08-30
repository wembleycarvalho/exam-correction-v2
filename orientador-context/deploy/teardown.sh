#!/usr/bin/env bash
# Remove o deploy CIRÚRGICO do Orientador Context (para reconciliar com o CDK do portal).
# Depois disto, ative o módulo de forma gerenciada pelo portal (requer Docker p/ o Entrevistador):
#   MODULES="correcao,entrevistador,orientador,lms,orientador-context" ./scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
: "${STACK:=exam-correction-v2}"

DIST_ID="$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" --output text)"

echo ">> Desligando o behavior /orientador-context/* no CloudFront…"
PYBOTO="$(command -v python3)"
if [[ -x .venv/bin/python ]]; then PYBOTO=".venv/bin/python"; fi
"$PYBOTO" cloudfront_behavior.py --dist "$DIST_ID" --remove

echo ">> Deletando a stack standalone orientador-context…"
aws cloudformation delete-stack --stack-name orientador-context --region "$AWS_REGION"
aws cloudformation wait stack-delete-complete --stack-name orientador-context --region "$AWS_REGION" 2>/dev/null || true
echo ">> Removido. O módulo sai do ar até ser reativado via o CDK do portal (deploy.sh com MODULES)."
