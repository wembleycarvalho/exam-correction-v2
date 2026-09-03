#!/usr/bin/env bash
# Deploy REPRODUZÍVEL do agente Orientador Context no Amazon Bedrock AgentCore Runtime.
#
#   1) Gateway do AgentCore Web Search (CloudFormation, IAM/SigV4, conector web-search)
#   2) Runtime CodeZip (agente Strands) via AgentCore starter toolkit — SEM Docker local
#   3) IAM least-privilege na execution role auto-criada (Athena/Glue/S3/Bedrock/Gateway/SSM)
#   4) SSM params com o ARN do runtime e a URL do gateway (consumidos pelo Router Lambda)
#
# Nada de account-id/bucket fica hardcoded: tudo é resolvido em runtime a partir dos stacks
# (portal + moodle-backbone) e da conta corrente. Requer: AWS CLI + credenciais, Python 3.10+.
# NÃO requer Docker.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }

: "${AWS_REGION:=us-east-1}"; export AWS_REGION
: "${MOODLE_STACK:=moodle-backbone}"
: "${AGENT_NAME:=orientador_context}"
: "${GLUE_DB:=moodle_datalake}"
: "${WORKGROUP:=moodle-datalake}"
: "${MODEL_ID:=amazon.nova-pro-v1:0}"
: "${GATEWAY_STACK:=orientador-context-websearch}"

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
LAKE="$(aws cloudformation describe-stacks --stack-name "$MOODLE_STACK" --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DataLakeBucket'].OutputValue" --output text)"
echo ">> account=$ACCOUNT region=$AWS_REGION lake=$LAKE"

# ---------------------------------------------------------------- 1) Gateway (web search)
echo ">> Deploy do gateway AgentCore Web Search…"
aws cloudformation deploy --template-file gateway-websearch.yaml \
  --stack-name "$GATEWAY_STACK" --capabilities CAPABILITY_IAM --region "$AWS_REGION" >/dev/null
GW_URL="$(aws cloudformation describe-stacks --stack-name "$GATEWAY_STACK" --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='GatewayUrl'].OutputValue" --output text)"
GW_ID="$(aws cloudformation describe-stacks --stack-name "$GATEWAY_STACK" --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='GatewayId'].OutputValue" --output text)"
GW_ARN="arn:aws:bedrock-agentcore:${AWS_REGION}:${ACCOUNT}:gateway/${GW_ID}"
echo ">> gateway=$GW_URL"

# ---------------------------------------------------------------- 2) Runtime (CodeZip)
echo ">> Preparando toolkit…"
python3 -m venv .venv 2>/dev/null || true
./.venv/bin/pip install -q --upgrade bedrock-agentcore-starter-toolkit >/dev/null
export AGENTCORE_SUPPRESS_RECOMMENDATION=1

if [[ ! -f .bedrock_agentcore.yaml ]]; then
  echo ">> agentcore configure (direct code deploy, IAM, memória STM)…"
  yes '' | head -20 | ./.venv/bin/agentcore configure \
    -e agent.py -n "$AGENT_NAME" -rf requirements.txt -r "$AWS_REGION" >/dev/null
fi
echo ">> agentcore launch (cloud, sem Docker)…"
./.venv/bin/agentcore launch -auc >/dev/null
RUNTIME_ARN="$(./.venv/bin/python -c "import yaml;c=yaml.safe_load(open('.bedrock_agentcore.yaml'));a=c['agents'][c['default_agent']];print(a['bedrock_agentcore']['agent_arn'])")"
EXEC_ROLE_ARN="$(./.venv/bin/python -c "import yaml;c=yaml.safe_load(open('.bedrock_agentcore.yaml'));a=c['agents'][c['default_agent']];print(a['aws']['execution_role'])")"
EXEC_ROLE="${EXEC_ROLE_ARN##*/}"
MEM_ID="$(./.venv/bin/python -c "import yaml;c=yaml.safe_load(open('.bedrock_agentcore.yaml'));a=c['agents'][c['default_agent']];print((a.get('memory') or {}).get('memory_id') or '')")"
MEM_ARN="arn:aws:bedrock-agentcore:${AWS_REGION}:${ACCOUNT}:memory/${MEM_ID}"
echo ">> runtime=$RUNTIME_ARN role=$EXEC_ROLE memory=$MEM_ID"

# ---------------------------------------------------------------- 3) IAM least-privilege
echo ">> Anexando policy least-privilege à execution role…"
POLICY="$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid":"AthenaQuery","Effect":"Allow","Action":["athena:StartQueryExecution","athena:StopQueryExecution","athena:GetQueryExecution","athena:GetQueryResults","athena:GetWorkGroup"],"Resource":"arn:aws:athena:${AWS_REGION}:${ACCOUNT}:workgroup/${WORKGROUP}"},
    {"Sid":"GlueCatalogRead","Effect":"Allow","Action":["glue:GetDatabase","glue:GetDatabases","glue:GetTable","glue:GetTables","glue:GetPartition","glue:GetPartitions"],"Resource":["arn:aws:glue:${AWS_REGION}:${ACCOUNT}:catalog","arn:aws:glue:${AWS_REGION}:${ACCOUNT}:database/${GLUE_DB}","arn:aws:glue:${AWS_REGION}:${ACCOUNT}:table/${GLUE_DB}/*"]},
    {"Sid":"DataLakeBucket","Effect":"Allow","Action":["s3:ListBucket","s3:GetBucketLocation"],"Resource":"arn:aws:s3:::${LAKE}"},
    {"Sid":"DataLakeObjects","Effect":"Allow","Action":["s3:GetObject","s3:PutObject"],"Resource":"arn:aws:s3:::${LAKE}/*"},
    {"Sid":"WebSearchGateway","Effect":"Allow","Action":"bedrock-agentcore:InvokeGateway","Resource":"${GW_ARN}"},
    {"Sid":"AgentCoreMemory","Effect":"Allow","Action":["bedrock-agentcore:CreateEvent","bedrock-agentcore:GetEvent","bedrock-agentcore:ListEvents","bedrock-agentcore:ListSessions","bedrock-agentcore:RetrieveMemoryRecords","bedrock-agentcore:ListMemoryRecords","bedrock-agentcore:GetMemoryRecord"],"Resource":["${MEM_ARN}","${MEM_ARN}/*"]},
    {"Sid":"ConfigParams","Effect":"Allow","Action":"ssm:GetParameter","Resource":"arn:aws:ssm:${AWS_REGION}:${ACCOUNT}:parameter/orientador-context/*"},
    {"Sid":"BedrockInvoke","Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],"Resource":["arn:aws:bedrock:*::foundation-model/amazon.nova-*","arn:aws:bedrock:*::foundation-model/anthropic.claude-*","arn:aws:bedrock:${AWS_REGION}:${ACCOUNT}:inference-profile/us.amazon.nova-*","arn:aws:bedrock:${AWS_REGION}:${ACCOUNT}:inference-profile/us.anthropic.claude-*"]}
  ]
}
JSON
)"
aws iam put-role-policy --role-name "$EXEC_ROLE" --policy-name octx-datalake-bedrock \
  --policy-document "$POLICY" --region "$AWS_REGION"

# ---------------------------------------------------------------- 4) SSM params (contrato c/ o Router)
echo ">> Publicando SSM params…"
aws ssm put-parameter --name /orientador-context/runtime-arn --type String --overwrite \
  --value "$RUNTIME_ARN" --region "$AWS_REGION" >/dev/null
aws ssm put-parameter --name /orientador-context/gateway-url --type String --overwrite \
  --value "$GW_URL" --region "$AWS_REGION" >/dev/null

echo ">> Pronto. runtime-arn e gateway-url no SSM. Teste: ./.venv/bin/agentcore invoke '{\"question\":\"...\",\"mode\":\"coord\",\"groups\":[\"admin\"]}'"
