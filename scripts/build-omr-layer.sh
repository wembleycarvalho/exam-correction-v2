#!/usr/bin/env bash
# Constrói e publica a layer OpenCV (headless) + numpy usada pelo OMR do cartão-resposta
# no worker. Usa wheels manylinux (sem Docker). Publica via um bucket de staging PRÓPRIO
# (independe da stack — pode rodar ANTES do CDK, quebrando o ovo-galinha).
#
# Uso: scripts/build-omr-layer.sh
# Saída: publica a layer e grava o ARN em infra/omr-layer.json (lido pelo deploy.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${AWS_REGION:=us-east-1}"
: "${STACK_NAME:=exam-correction-v2}"
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
# Bucket de staging dedicado (não depende de nenhum recurso da stack).
: "${LAYER_STAGING_BUCKET:=${STACK_NAME}-layer-staging-${ACCOUNT}}"

if ! aws s3api head-bucket --bucket "$LAYER_STAGING_BUCKET" >/dev/null 2>&1; then
  echo ">> Criando bucket de staging: ${LAYER_STAGING_BUCKET}"
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$LAYER_STAGING_BUCKET" >/dev/null
  else
    aws s3api create-bucket --bucket "$LAYER_STAGING_BUCKET" \
      --create-bucket-configuration "LocationConstraint=${AWS_REGION}" >/dev/null
  fi
  aws s3api put-public-access-block --bucket "$LAYER_STAGING_BUCKET" \
    --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" >/dev/null
fi

BUILD="$(mktemp -d)"; mkdir -p "$BUILD/python"
echo ">> baixando wheels (opencv-python-headless 4.10 + numpy<2, cp312 x86_64)"
python3 -m pip install \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 \
  --only-binary=:all: --target "$BUILD/python" \
  "opencv-python-headless==4.10.0.84" "numpy<2"

# enxuga: testes, caches, stubs, metadados e binários de linha de comando
find "$BUILD/python" -type d \( -name tests -o -name "__pycache__" -o -name "*.dist-info" \) -prune -exec rm -rf {} + 2>/dev/null || true
find "$BUILD/python" -name "*.pyi" -delete 2>/dev/null || true
rm -rf "$BUILD/python/bin" 2>/dev/null || true

( cd "$BUILD" && zip -qr /tmp/omr-layer.zip python )
echo ">> upload + publish"
aws s3 cp /tmp/omr-layer.zip "s3://${LAYER_STAGING_BUCKET}/layers/omr-layer.zip" >/dev/null
LAYER_ARN="$(aws lambda publish-layer-version \
  --layer-name exam-omr-opencv \
  --description "OpenCV headless 4.10 + numpy p/ OMR do cartao-resposta" \
  --content "S3Bucket=${LAYER_STAGING_BUCKET},S3Key=layers/omr-layer.zip" \
  --compatible-runtimes python3.12 --compatible-architectures x86_64 \
  --query LayerVersionArn --output text)"

cat > infra/omr-layer.json <<JSON
{"omrLayerArn": "${LAYER_ARN}"}
JSON
echo ">> Layer publicada: ${LAYER_ARN}"
echo ">> Escrito infra/omr-layer.json (lido pelo deploy.sh via contexto -c omrLayerArn)."
