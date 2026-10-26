#!/usr/bin/env bash
# Deploy do backend Gateway Inference no EKS Fargate (cluster strands-obs-demo) com
# observability nativa (ADOT SDK -> CloudWatch GenAI Observability) e STREAMING SSE.
# Pré-requisitos: cluster criado, imagem no ECR (build-image.sh), Transaction Search
# habilitado, resource policy do X-Ray incluindo o log group /aws/gwinf-eks/agent.
# Idempotente. Requer: AWS CLI + creds, eksctl, kubectl.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../../ && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
CLUSTER="strands-obs-demo"
NS="gwinf"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/gateway-inference-eks"
IMAGE_TAG="${IMAGE_TAG:-v1}"
POOL_ID="${POOL_ID:-us-east-1_qbqZGnOPK}"

echo ">> kubeconfig"
eksctl utils write-kubeconfig --cluster "$CLUSTER" --region "$AWS_REGION" >/dev/null

echo ">> log group + stream de observability (o exportador OTLP nao cria o stream sozinho)"
aws logs create-log-group  --log-group-name /aws/gwinf-eks/agent --region "$AWS_REGION" 2>/dev/null || true
aws logs create-log-stream --log-group-name /aws/gwinf-eks/agent --log-stream-name default --region "$AWS_REGION" 2>/dev/null || true

echo ">> autoriza o X-Ray (Transaction Search) a entregar spans no log group (resource policy)"
# Sem isso o endpoint OTLP do X-Ray retorna 400 (logs:PutLogEvents negado no /aws/gwinf-eks/agent).
LG_ARN="arn:aws:logs:${AWS_REGION}:${ACCOUNT}:log-group:/aws/gwinf-eks/agent:*"
aws logs describe-resource-policies --region "$AWS_REGION" --output json > /tmp/gwinf-rp.json 2>/dev/null || echo '{"resourcePolicies":[]}' > /tmp/gwinf-rp.json
AWS_REGION="$AWS_REGION" python3 - "$LG_ARN" <<'PY' || echo "   (aviso: nao consegui atualizar a resource policy; ajuste manual pode ser necessario)"
import json, os, subprocess, sys
lg = sys.argv[1]; region = os.environ["AWS_REGION"]
d = json.load(open("/tmp/gwinf-rp.json"))
pol = next((p for p in d.get("resourcePolicies", []) if p["policyName"] == "TransactionSearchXRayAccess"), None)
if pol is None:
    doc = {"Version": "2012-10-17", "Statement": [{"Sid": "TransactionSearchXRayAccess",
        "Effect": "Allow", "Principal": {"Service": "xray.amazonaws.com"},
        "Action": "logs:PutLogEvents", "Resource": [lg]}]}
else:
    doc = json.loads(pol["policyDocument"]); st = doc["Statement"][0]
    res = st["Resource"]; res = [res] if isinstance(res, str) else res
    if lg in res:
        print("   idempotente: log group ja autorizado"); sys.exit(0)
    res.append(lg); st["Resource"] = res
open("/tmp/gwinf-rp-new.json", "w").write(json.dumps(doc))
subprocess.run(["aws", "logs", "put-resource-policy", "--region", region,
    "--policy-name", "TransactionSearchXRayAccess",
    "--policy-document", "file:///tmp/gwinf-rp-new.json"], check=True, stdout=subprocess.DEVNULL)
print("   OK: /aws/gwinf-eks/agent autorizado na TransactionSearchXRayAccess")
PY

echo ">> IAM policy (IRSA) — resolve placeholders (ACCOUNT_ID/REGION) do template"
sed -e "s/ACCOUNT_ID/${ACCOUNT}/g" -e "s/REGION/${AWS_REGION}/g" iam/agent-irsa-policy.json > /tmp/gwinf-eks-irsa.json
POLICY_ARN="$(aws iam create-policy --policy-name gwinf-eks-agent-policy \
  --policy-document file:///tmp/gwinf-eks-irsa.json --query 'Policy.Arn' --output text 2>/dev/null || \
  echo "arn:aws:iam::${ACCOUNT}:policy/gwinf-eks-agent-policy")"
# se ja existe, garante que a versao esta atualizada
aws iam create-policy-version --policy-arn "$POLICY_ARN" \
  --policy-document file:///tmp/gwinf-eks-irsa.json --set-as-default >/dev/null 2>&1 || true
echo "   policy=$POLICY_ARN"

echo ">> namespace + IRSA service account"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
eksctl create iamserviceaccount \
  --cluster "$CLUSTER" --region "$AWS_REGION" \
  --namespace "$NS" --name gwinf-agent \
  --attach-policy-arn "$POLICY_ARN" \
  --approve --override-existing-serviceaccounts

echo ">> deploy do agente (imagem $ECR_URI:$IMAGE_TAG, pool $POOL_ID)"
sed -e "s#__IMAGE__#${ECR_URI}:${IMAGE_TAG}#g" -e "s#__POOL_ID__#${POOL_ID}#g" \
  k8s/deployment.yaml | kubectl apply -f -
kubectl -n "$NS" rollout status deploy/gwinf-agent --timeout=300s

echo ">> pronto. Teste via port-forward (REQUIRE_AUTH=true valida JWT; use REQUIRE_AUTH=false p/ testar sem token):"
echo "   kubectl -n $NS port-forward svc/gwinf-agent 8080:80 &"
echo "   curl -s localhost:8080/health"
