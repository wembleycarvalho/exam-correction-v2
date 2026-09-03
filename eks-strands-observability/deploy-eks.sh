#!/usr/bin/env bash
# Deploy do agente Strands no EKS Fargate com observability nativa (ADOT SDK -> CloudWatch
# GenAI Observability). Pré-requisitos: cluster já criado (eksctl create cluster -f
# eksctl-cluster.yaml), imagem já no ECR (CodeBuild), Transaction Search habilitado, e o
# resource policy do X-Ray incluindo o log group /aws/eks-strands-observability/agent.
#
# Reproduzível e idempotente. Requer: AWS CLI + creds, eksctl, kubectl.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../ && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
CLUSTER="strands-obs-demo"
NS="strands"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/eks-strands-observability"
IMAGE_TAG="${IMAGE_TAG:-v1}"

echo ">> kubeconfig"
eksctl utils write-kubeconfig --cluster "$CLUSTER" --region "$AWS_REGION" >/dev/null

echo ">> log group + stream de observability (o exportador OTLP nao cria o stream sozinho)"
aws logs create-log-group  --log-group-name /aws/eks-strands-observability/agent --region "$AWS_REGION" 2>/dev/null || true
aws logs create-log-stream --log-group-name /aws/eks-strands-observability/agent --log-stream-name default --region "$AWS_REGION" 2>/dev/null || true

echo ">> IAM policy (IRSA) — resolve placeholders (ACCOUNT_ID/REGION) do template"
sed -e "s/ACCOUNT_ID/${ACCOUNT}/g" -e "s/REGION/${AWS_REGION}/g" iam/agent-irsa-policy.json > /tmp/eks-strands-irsa.json
POLICY_ARN="$(aws iam create-policy --policy-name eks-strands-agent-policy \
  --policy-document file:///tmp/eks-strands-irsa.json --query 'Policy.Arn' --output text 2>/dev/null || \
  echo "arn:aws:iam::${ACCOUNT}:policy/eks-strands-agent-policy")"
echo "   policy=$POLICY_ARN"

echo ">> namespace + IRSA service account"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
eksctl create iamserviceaccount \
  --cluster "$CLUSTER" --region "$AWS_REGION" \
  --namespace "$NS" --name strands-agent \
  --attach-policy-arn "$POLICY_ARN" \
  --approve --override-existing-serviceaccounts

echo ">> deploy do agente (imagem $ECR_URI:$IMAGE_TAG)"
sed "s#__IMAGE__#${ECR_URI}:${IMAGE_TAG}#g" k8s/deployment.yaml | kubectl apply -f -
kubectl -n "$NS" rollout status deploy/strands-agent --timeout=300s

echo ">> pronto. Teste via port-forward:"
echo "   kubectl -n $NS port-forward svc/strands-agent 8080:80 &"
echo "   curl -s localhost:8080/health"
echo "   curl -s -XPOST localhost:8080/invoke -H 'content-type: application/json' -d '{\"question\":\"que horas sao em UTC? some 2+3\",\"session_id\":\"demo-eks-1\"}'"
