#!/usr/bin/env bash
# Implanta/atualiza o agente Orientador no Amazon Bedrock AgentCore Runtime SEM depender do
# agentcore starter toolkit.
#
# POR QUÊ: a partir da v0.1.x o starter toolkit REMOVEU o suporte a VPC do `agentcore
# configure/launch` (NetworkConfiguration só tem network_mode e força PUBLIC). Como o agente
# precisa alcançar o Neptune, ele TEM que rodar em VPC (subnets privadas com NAT). Então aqui
# fazemos o fluxo direto: build ARM64 (finch/docker) -> push no ECR -> create/update do
# runtime via control plane (bedrock-agentcore-control) preservando a VPC -> SSM -> carga do grafo.
#
# Pré-requisitos:
#   - CDK já implantado com -c modules=...,orientador (cria Neptune + role + SG + subnets + SSM + bridge).
#   - finch OU docker disponível (build linux/arm64; num Mac Apple Silicon é nativo).
#   - Credenciais com acesso a ECR, bedrock-agentcore(-control), SSM, CloudFormation.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${AWS_REGION:=us-east-1}"
: "${STACK_NAME:=exam-correction-v2}"
export AWS_REGION

AGENT_NAME="orientador_agent"
ECR_REPO="orientador-agent"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_URI="${REGISTRY}/${ECR_REPO}"

out() { aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" --output text; }

NEPTUNE_ENDPOINT="$(out OrientadorNeptuneEndpoint)"
SUBNETS_CSV="$(out OrientadorSubnets)"
AGENT_SG="$(out OrientadorAgentSg)"
ROLE_ARN="$(out OrientadorRuntimeRoleArn)"
PARAM="$(out OrientadorRuntimeArnParam)"
MODEL_ID="$(out OrientadorModelId)"; : "${MODEL_ID:=amazon.nova-pro-v1:0}"

if [[ -z "$NEPTUNE_ENDPOINT" || "$NEPTUNE_ENDPOINT" == "None" ]]; then
  echo "!! Outputs do Orientador ausentes. Rode o CDK com -c modules=...,orientador antes." >&2
  exit 1
fi
echo ">> Neptune=$NEPTUNE_ENDPOINT | subnets=$SUBNETS_CSV | sg=$AGENT_SG | role=$ROLE_ARN"

# --- Builder de container: finch (preferido) ou docker ---
if command -v finch >/dev/null 2>&1; then
  CTR=finch
  finch vm status 2>/dev/null | grep -qi running || { echo ">> iniciando a VM do finch…"; finch vm start >/dev/null 2>&1 || true; }
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  CTR=docker
else
  echo "!! Precisa de finch ou docker (com daemon rodando) para buildar a imagem ARM64." >&2
  exit 1
fi
echo ">> Builder: $CTR"

# --- Garante o repositório ECR ---
aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$ECR_REPO" --region "$AWS_REGION" >/dev/null

# --- Login + build ARM64 + push ---
TAG="v$(date +%s)"; IMAGE="${ECR_URI}:${TAG}"
aws ecr get-login-password --region "$AWS_REGION" | "$CTR" login --username AWS --password-stdin "$REGISTRY"
echo ">> Build ${IMAGE} (linux/arm64)…"
( cd orientador-academico && "$CTR" build --platform linux/arm64 -t "$IMAGE" . )
echo ">> Push…"; "$CTR" push "$IMAGE"

# --- Env do runtime (o agente hidrata o grafo do Neptune usando NEPTUNE_ENDPOINT) ---
ENV_JSON="$(python3 -c 'import json,sys; print(json.dumps({"AWS_REGION":sys.argv[1],"NEPTUNE_ENDPOINT":sys.argv[2],"ORIENTADOR_MODEL_ID":sys.argv[3]}))' "$AWS_REGION" "$NEPTUNE_ENDPOINT" "$MODEL_ID")"
ARTIFACT="$(python3 -c 'import json,sys; print(json.dumps({"containerConfiguration":{"containerUri":sys.argv[1]}}))' "$IMAGE")"

# --- Runtime existente? Atualiza; senão, cria. ---
# Pega o 1º runtime com esse nome e então o id (evita projeção multi-valor que retorna 'None').
find_rid() {
  aws bedrock-agentcore-control list-agent-runtimes --region "$AWS_REGION" \
    --query "agentRuntimes[?agentRuntimeName=='${AGENT_NAME}'] | [0].agentRuntimeId" --output text 2>/dev/null \
    | grep -vi '^none$' | head -n1 | tr -d '[:space:]'
}
RID="$(find_rid || true)"

if [[ -n "$RID" ]]; then
  echo ">> Atualizando runtime existente ($RID) — reusando a rede VPC atual (subnets/SG que já funcionam com NAT)…"
  # IMPORTANTE: reusar a networkConfiguration ATUAL e REMOVER requireServiceS3Endpoint
  # (imutável em runtimes criados após 2026-06-11 -> ValidationException se enviado).
  NETCFG="$(aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$RID" --region "$AWS_REGION" \
    --query networkConfiguration --output json \
    | python3 -c 'import sys,json; n=json.load(sys.stdin); n.get("networkModeConfig",{}).pop("requireServiceS3Endpoint",None); print(json.dumps(n))')"
  aws bedrock-agentcore-control update-agent-runtime --region "$AWS_REGION" \
    --agent-runtime-id "$RID" \
    --agent-runtime-artifact "$ARTIFACT" \
    --role-arn "$ROLE_ARN" \
    --network-configuration "$NETCFG" \
    --protocol-configuration '{"serverProtocol":"HTTP"}' \
    --environment-variables "$ENV_JSON" >/dev/null
else
  echo ">> Criando runtime novo em VPC (subnets=$SUBNETS_CSV sg=$AGENT_SG)…"
  NETCFG="$(python3 -c 'import json,sys; subs=[s for s in sys.argv[1].split(",") if s]; print(json.dumps({"networkMode":"VPC","networkModeConfig":{"subnets":subs,"securityGroups":[sys.argv[2]]}}))' "$SUBNETS_CSV" "$AGENT_SG")"
  aws bedrock-agentcore-control create-agent-runtime --region "$AWS_REGION" \
    --agent-runtime-name "$AGENT_NAME" \
    --agent-runtime-artifact "$ARTIFACT" \
    --role-arn "$ROLE_ARN" \
    --network-configuration "$NETCFG" \
    --protocol-configuration '{"serverProtocol":"HTTP"}' \
    --environment-variables "$ENV_JSON" >/dev/null
  RID="$(find_rid)"
fi

ARN="$(aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$RID" --region "$AWS_REGION" --query agentRuntimeArn --output text)"
echo ">> Runtime ARN: $ARN"

# --- Aguarda READY ---
echo ">> Aguardando o runtime ficar READY…"
for _ in $(seq 1 60); do
  S="$(aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$RID" --region "$AWS_REGION" --query status --output text 2>/dev/null || true)"
  echo "   status=$S"
  [[ "$S" == "READY" ]] && break
  [[ "$S" == "CREATE_FAILED" || "$S" == "UPDATE_FAILED" ]] && { echo "!! Deploy falhou (status=$S)." >&2; exit 1; }
  sleep 10
done

# --- Publica o ARN no SSM (lido pelo bridge/worker) ---
aws ssm put-parameter --region "$AWS_REGION" --overwrite --name "$PARAM" --type String --value "$ARN" >/dev/null
echo ">> Publicado no SSM: $PARAM"

# --- Carrega o grafo no Neptune (action=load, de dentro da VPC) ---
echo ">> Carregando o grafo no Neptune (action=load)…"
printf '{"action":"load","clear":true}' > /tmp/ori-load.json
aws bedrock-agentcore invoke-agent-runtime --region "$AWS_REGION" \
  --agent-runtime-arn "$ARN" --runtime-session-id "load-session-$(date +%s)-000000000000" \
  --content-type application/json --accept application/json \
  --payload fileb:///tmp/ori-load.json /tmp/ori-load.out && cat /tmp/ori-load.out || \
  echo "(carga: verifique manualmente — invoque action=load)"
echo; echo ">> Concluído."
