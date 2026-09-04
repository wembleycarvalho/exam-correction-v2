#!/usr/bin/env bash
# Deploy do agente "Atendimento — Assistente" no AgentCore Runtime (CodeZip, sem Docker).
# Streaming nativo (stream_async). Tools = Lambdas existentes (lambda:invoke direto).
# Idempotente; sem account-id hardcoded (resolve de STS). Requer AWS CLI + creds + o toolkit
# agentcore (bedrock-agentcore-starter-toolkit).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
: "${AGENT_NAME:=atendimento_assistant}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
export AGENTCORE_SUPPRESS_RECOMMENDATION=1
: "${FN_CURSOS:=mcp-catalogo-cursos}"; : "${FN_LOOKUP:=connect-user-lookup}"
: "${FN_ACADEMICO:=mcp-academico}"; : "${FN_BOLETO:=mcp-boleto}"; : "${FN_CONTEUDO:=mcp-vestibular}"

python3 -m venv .venv 2>/dev/null || true
./.venv/bin/pip install -q --upgrade bedrock-agentcore-starter-toolkit >/dev/null
[[ -f .bedrock_agentcore.yaml ]] || yes '' | head -20 | \
  ./.venv/bin/agentcore configure -e agent.py -n "$AGENT_NAME" -rf requirements.txt -r "$AWS_REGION" >/dev/null
./.venv/bin/agentcore launch -auc >/dev/null
RUNTIME_ARN="$(./.venv/bin/python -c "import yaml;c=yaml.safe_load(open('.bedrock_agentcore.yaml'));a=c['agents'][c['default_agent']];print(a['bedrock_agentcore']['agent_arn'])")"
EXEC_ROLE="$(./.venv/bin/python -c "import yaml;c=yaml.safe_load(open('.bedrock_agentcore.yaml'));a=c['agents'][c['default_agent']];print(a['aws']['execution_role'].split('/')[-1])")"
aws ssm put-parameter --name /atendimento/runtime-arn --value "$RUNTIME_ARN" --type String --overwrite --region "$AWS_REGION" >/dev/null

echo ">> IAM: Bedrock Converse + lambda:invoke nas 5 tools (privilégio mínimo) na execution role"
LAMBDA_ARNS="$(printf '"arn:aws:lambda:%s:%s:function:%s",' "$AWS_REGION" "$ACCOUNT" "$FN_CURSOS" "$FN_LOOKUP" "$FN_ACADEMICO" "$FN_BOLETO" "$FN_CONTEUDO" | sed 's/,$//')"
aws iam put-role-policy --role-name "$EXEC_ROLE" --policy-name atendimento-agent --region "$AWS_REGION" \
  --policy-document "$(cat <<JSON
{"Version":"2012-10-17","Statement":[
 {"Sid":"BedrockConverse","Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],
  "Resource":["arn:aws:bedrock:*::foundation-model/*","arn:aws:bedrock:${AWS_REGION}:${ACCOUNT}:inference-profile/*"]},
 {"Sid":"Tools","Effect":"Allow","Action":"lambda:InvokeFunction","Resource":[${LAMBDA_ARNS}]}
]}
JSON
)"
echo ">> pronto. runtime=$RUNTIME_ARN (SSM /atendimento/runtime-arn)"
