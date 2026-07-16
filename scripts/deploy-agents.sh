#!/usr/bin/env bash
# Empacota e implanta os agentes Strands no AgentCore Runtime (CodeZip, sem Docker) via
# o starter toolkit, e publica o ARN do Runtime no parâmetro SSM lido pelo worker/API.
#
# Pré-requisito: pip install bedrock-agentcore-starter-toolkit strands-agents
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${AWS_REGION:=us-east-1}"
: "${STACK_NAME:=exam-correction-v2}"
export AWS_REGION

BUILD="$(mktemp -d)"
echo ">> Empacotando agentes em ${BUILD}"
cp agents/entrypoint.py agents/prompts.py agents/specialists.py agents/requirements.txt "$BUILD/"
# 'common' é usado pelos agentes (extract_json). Copiado para dentro do pacote CodeZip.
mkdir -p "$BUILD/common"
cp backend/common/__init__.py backend/common/json_utils.py "$BUILD/common/"

pushd "$BUILD" >/dev/null
# Configura o agente (cria role de execução; instrumentação OTel habilitada por padrão).
agentcore configure -e entrypoint.py -n exam_agents -r "$AWS_REGION" -rf requirements.txt -ni
# Launch DEFAULT = build ARM64 no CodeBuild + deploy no runtime (SEM Docker local).
# --auto-update-on-conflict: atualiza o runtime existente em vez de falhar.
agentcore launch --auto-update-on-conflict 2>&1 | tee launch.out
agentcore status 2>&1 | tee status.out || true
popd >/dev/null

# Extrai o ARN do Runtime da saída do toolkit (ou consulta pelo nome).
RUNTIME_ARN="$(grep -Eo 'arn:aws[^ "]*runtime/[^ "]*' "$BUILD/launch.out" "$BUILD/status.out" | grep -Eo 'arn:aws[^ "]*' | head -n1 || true)"
if [[ -z "$RUNTIME_ARN" ]]; then
  RUNTIME_ARN="$(aws bedrock-agentcore-control list-agent-runtimes --region "$AWS_REGION" \
    --query "agentRuntimes[?contains(agentRuntimeName,'exam_agents')].agentRuntimeArn | [0]" --output text 2>/dev/null || true)"
fi
if [[ -z "$RUNTIME_ARN" || "$RUNTIME_ARN" == "None" ]]; then
  echo "!! Não foi possível determinar o ARN do Runtime. Verifique 'agentcore status'." >&2
  exit 1
fi

echo ">> Runtime ARN: ${RUNTIME_ARN}"
aws ssm put-parameter --region "$AWS_REGION" --overwrite \
  --name "/${STACK_NAME}/agent-runtime-arn" --type String --value "$RUNTIME_ARN" >/dev/null
echo ">> Publicado no SSM: /${STACK_NAME}/agent-runtime-arn"
