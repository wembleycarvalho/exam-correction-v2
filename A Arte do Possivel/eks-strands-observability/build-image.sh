#!/usr/bin/env bash
# Build da imagem do agente NA NUVEM via CodeBuild -> ECR (sem Docker/finch local).
# Idempotente e sem account-id hardcoded (resolve de $AWS_REGION + STS). Requer AWS CLI+creds.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../ && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }
: "${AWS_REGION:=us-east-1}"; export AWS_REGION
: "${IMAGE_TAG:=v1}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REPO="eks-strands-observability"
ECR_URI="${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO}"
BUCKET="eks-strands-build-${ACCOUNT}-${AWS_REGION}"
ROLE="eks-strands-codebuild"
PROJECT="eks-strands-image"

echo ">> ECR repo"
aws ecr create-repository --repository-name "$REPO" --region "$AWS_REGION" \
  --image-scanning-configuration scanOnPush=true >/dev/null 2>&1 || true

echo ">> source bucket + upload"
aws s3api create-bucket --bucket "$BUCKET" --region "$AWS_REGION" >/dev/null 2>&1 || true
( cd app && zip -q -r /tmp/eks-strands-src.zip . -x "*__pycache__*" )
aws s3 cp /tmp/eks-strands-src.zip "s3://${BUCKET}/source.zip" --region "$AWS_REGION" >/dev/null

echo ">> CodeBuild service role"
aws iam create-role --role-name "$ROLE" --region "$AWS_REGION" \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codebuild.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null 2>&1 || true
aws iam put-role-policy --role-name "$ROLE" --policy-name build --region "$AWS_REGION" --policy-document "$(cat <<JSON
{"Version":"2012-10-17","Statement":[
 {"Sid":"Logs","Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],"Resource":"arn:aws:logs:${AWS_REGION}:${ACCOUNT}:log-group:/aws/codebuild/${PROJECT}*"},
 {"Sid":"EcrAuth","Effect":"Allow","Action":["ecr:GetAuthorizationToken"],"Resource":"*"},
 {"Sid":"EcrPush","Effect":"Allow","Action":["ecr:BatchCheckLayerAvailability","ecr:InitiateLayerUpload","ecr:UploadLayerPart","ecr:CompleteLayerUpload","ecr:PutImage","ecr:BatchGetImage","ecr:GetDownloadUrlForLayer"],"Resource":"arn:aws:ecr:${AWS_REGION}:${ACCOUNT}:repository/${REPO}"},
 {"Sid":"Src","Effect":"Allow","Action":["s3:GetObject","s3:GetObjectVersion"],"Resource":"arn:aws:s3:::${BUCKET}/*"}
]}
JSON
)"
sleep 8  # deixa a role propagar

echo ">> CodeBuild project"
PROJ_JSON="$(cat <<JSON
{"name":"${PROJECT}","source":{"type":"S3","location":"${BUCKET}/source.zip","buildspec":"buildspec.yml"},
 "artifacts":{"type":"NO_ARTIFACTS"},
 "environment":{"type":"LINUX_CONTAINER","image":"aws/codebuild/standard:7.0","computeType":"BUILD_GENERAL1_SMALL","privilegedMode":true,
  "environmentVariables":[
   {"name":"AWS_REGION","value":"${AWS_REGION}"},
   {"name":"ECR_REGISTRY","value":"${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"},
   {"name":"ECR_URI","value":"${ECR_URI}"},
   {"name":"IMAGE_TAG","value":"${IMAGE_TAG}"}]},
 "serviceRole":"arn:aws:iam::${ACCOUNT}:role/${ROLE}"}
JSON
)"
echo "$PROJ_JSON" > /tmp/eks-strands-cb.json
aws codebuild create-project --cli-input-json file:///tmp/eks-strands-cb.json --region "$AWS_REGION" >/dev/null 2>&1 \
  || aws codebuild update-project --cli-input-json file:///tmp/eks-strands-cb.json --region "$AWS_REGION" >/dev/null

echo ">> start build"
BID="$(aws codebuild start-build --project-name "$PROJECT" --region "$AWS_REGION" --query 'build.id' --output text)"
echo "   build=$BID"
while :; do
  ST="$(aws codebuild batch-get-builds --ids "$BID" --region "$AWS_REGION" --query 'builds[0].buildStatus' --output text)"
  echo "   status=$ST"; [ "$ST" != "IN_PROGRESS" ] && break; sleep 15
done
[ "$ST" = "SUCCEEDED" ] && echo ">> imagem pronta: ${ECR_URI}:${IMAGE_TAG}" || { echo "BUILD FALHOU"; exit 1; }
