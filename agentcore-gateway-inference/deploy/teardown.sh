#!/usr/bin/env bash
# Remove o deploy CIRÚRGICO do módulo AgentCore — Gateway Inference (behavior + stack).
# NÃO remove o Runtime (use agentcore delete) nem o InferenceDemoStack/Gateway (reusados).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
: "${STACK:=exam-correction-v2}"
DIST_ID="$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" --output text)"
PYBOTO="$(command -v python3)"; [[ -x .venv/bin/python ]] && PYBOTO=".venv/bin/python"
echo ">> Desligando o behavior /agentcore/* no CloudFront…"
"$PYBOTO" cloudfront_behavior.py --dist "$DIST_ID" --remove
echo ">> Deletando a stack standalone agentcore-gateway-inference…"
aws cloudformation delete-stack --stack-name agentcore-gateway-inference --region "$AWS_REGION"
aws cloudformation wait stack-delete-complete --stack-name agentcore-gateway-inference --region "$AWS_REGION" 2>/dev/null || true
echo ">> Removido."
