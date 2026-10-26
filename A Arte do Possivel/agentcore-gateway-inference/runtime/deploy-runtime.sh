#!/usr/bin/env bash
# Deploy do agente "Gateway Inference" no AgentCore Runtime (CodeZip, sem Docker).
# Reusa o AgentCore Gateway existente (target bedrock-mantle) — config no SSM /gateway-inference/*.
# Idempotente; sem account-id hardcoded (resolve de STS). Requer AWS CLI + creds + o toolkit
# agentcore (pip install bedrock-agentcore-starter-toolkit).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
: "${AGENT_NAME:=gateway_inference}"
: "${INFERENCE_STACK:=InferenceDemoStack}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
export AGENTCORE_SUPPRESS_RECOMMENDATION=1

echo ">> resolvendo config do Gateway (do stack $INFERENCE_STACK) para o SSM /gateway-inference/*"
O(){ aws cloudformation describe-stacks --stack-name "$INFERENCE_STACK" --region "$AWS_REGION" \
      --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
SECRET_ARN="$(aws cloudformation list-stack-resources --stack-name "$INFERENCE_STACK" --region "$AWS_REGION" \
  --query "StackResourceSummaries[?ResourceType=='AWS::SecretsManager::Secret'].PhysicalResourceId" --output text)"
put(){ aws ssm put-parameter --name "$1" --value "$2" --type String --overwrite --region "$AWS_REGION" >/dev/null; }
put /gateway-inference/base-url         "$(O GatewayInferenceBaseUrl)"
put /gateway-inference/token-endpoint   "$(O CognitoTokenEndpoint)"
put /gateway-inference/client-id        "$(O CognitoClientId)"
put /gateway-inference/scope            "$(O CognitoScope)"
put /gateway-inference/client-secret-arn "$SECRET_ARN"

python3 -m venv .venv 2>/dev/null || true
./.venv/bin/pip install -q --upgrade bedrock-agentcore-starter-toolkit >/dev/null
[[ -f .bedrock_agentcore.yaml ]] || yes '' | head -20 | ./.venv/bin/agentcore configure -e agent.py -n "$AGENT_NAME" -rf requirements.txt -r "$AWS_REGION" >/dev/null
./.venv/bin/agentcore launch -auc >/dev/null
RUNTIME_ARN="$(./.venv/bin/python -c "import yaml;c=yaml.safe_load(open('.bedrock_agentcore.yaml'));a=c['agents'][c['default_agent']];print(a['bedrock_agentcore']['agent_arn'])")"
EXEC_ROLE="$(./.venv/bin/python -c "import yaml;c=yaml.safe_load(open('.bedrock_agentcore.yaml'));a=c['agents'][c['default_agent']];print(a['aws']['execution_role'].split('/')[-1])")"
put /gateway-inference/runtime-arn "$RUNTIME_ARN"

echo ">> IAM: SSM GetParameter + Secrets GetSecretValue (mint token m2m) na execution role"
aws iam put-role-policy --role-name "$EXEC_ROLE" --policy-name gwinf-config-secret --region "$AWS_REGION" \
  --policy-document "$(cat <<JSON
{"Version":"2012-10-17","Statement":[
 {"Sid":"ConfigParams","Effect":"Allow","Action":"ssm:GetParameter","Resource":"arn:aws:ssm:${AWS_REGION}:${ACCOUNT}:parameter/gateway-inference/*"},
 {"Sid":"M2MClientSecret","Effect":"Allow","Action":"secretsmanager:GetSecretValue","Resource":"${SECRET_ARN%-*}-*"}
]}
JSON
)"
echo ">> pronto. runtime=$RUNTIME_ARN"
