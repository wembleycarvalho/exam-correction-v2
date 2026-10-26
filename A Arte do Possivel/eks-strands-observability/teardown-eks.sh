#!/usr/bin/env bash
# Destroi TODOS os recursos do PoC para parar custos (o EKS control plane cobra ~US$0.10/h).
# Remove: cluster EKS (control plane + fargate profiles + IRSA/OIDC + SG) via eksctl, a IAM
# policy do agente, e opcionalmente o ECR/CodeBuild. NAO mexe na VPC reutilizada (pulso).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../ && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
CLUSTER="strands-obs-demo"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"

echo ">> apagando o cluster EKS (control plane + fargate + IRSA)…"
eksctl delete cluster --name "$CLUSTER" --region "$AWS_REGION" --disable-nodegroup-eviction --wait || true

echo ">> apagando a IAM policy do agente…"
aws iam delete-policy --policy-arn "arn:aws:iam::${ACCOUNT}:policy/eks-strands-agent-policy" 2>/dev/null || true

if [[ "${PURGE_BUILD:-no}" == "yes" ]]; then
  echo ">> PURGE_BUILD=yes: removendo ECR + CodeBuild + role de build…"
  aws ecr delete-repository --repository-name eks-strands-observability --force --region "$AWS_REGION" 2>/dev/null || true
  aws codebuild delete-project --name eks-strands-image --region "$AWS_REGION" 2>/dev/null || true
  aws iam delete-role-policy --role-name eks-strands-codebuild --policy-name build 2>/dev/null || true
  aws iam delete-role --role-name eks-strands-codebuild 2>/dev/null || true
fi

echo ">> feito. (A VPC reutilizada e o log group de observability nao sao removidos.)"
