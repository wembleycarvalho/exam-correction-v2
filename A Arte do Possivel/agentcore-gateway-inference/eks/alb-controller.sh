#!/usr/bin/env bash
# Instala o AWS Load Balancer Controller no cluster (via helm + IRSA), pré-requisito para
# expor o Service por um ALB (Ingress). Fargate-only NÃO suporta Service type=LoadBalancer
# in-tree — o LB Controller é o caminho suportado. Idempotente.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../../ && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
CLUSTER="strands-obs-demo"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
VPC_ID="$(aws eks describe-cluster --name "$CLUSTER" --region "$AWS_REGION" --query 'cluster.resourcesVpcConfig.vpcId' --output text)"
POLICY_ARN="arn:aws:iam::${ACCOUNT}:policy/AWSLoadBalancerControllerIAMPolicy"

echo ">> VPC=$VPC_ID"

echo ">> associa IAM OIDC provider (idempotente)"
eksctl utils associate-iam-oidc-provider --cluster "$CLUSTER" --region "$AWS_REGION" --approve >/dev/null

echo ">> IAM policy do controller"
if ! aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
  curl -fsSL -o /tmp/alb-iam-policy.json \
    https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.9.2/docs/install/iam_policy.json
  aws iam create-policy --policy-name AWSLoadBalancerControllerIAMPolicy \
    --policy-document file:///tmp/alb-iam-policy.json >/dev/null
fi
echo "   policy=$POLICY_ARN"

echo ">> IRSA service account (kube-system/aws-load-balancer-controller)"
eksctl create iamserviceaccount \
  --cluster "$CLUSTER" --region "$AWS_REGION" \
  --namespace kube-system --name aws-load-balancer-controller \
  --attach-policy-arn "$POLICY_ARN" \
  --approve --override-existing-serviceaccounts >/dev/null

echo ">> helm install/upgrade do controller"
helm repo add eks https://aws.github.io/eks-charts >/dev/null 2>&1 || true
helm repo update eks >/dev/null
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  --namespace kube-system \
  --set clusterName="$CLUSTER" \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region="$AWS_REGION" \
  --set vpcId="$VPC_ID"

echo ">> aguardando controller ready"
kubectl -n kube-system rollout status deploy/aws-load-balancer-controller --timeout=300s
