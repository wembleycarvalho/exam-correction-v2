#!/usr/bin/env bash
# Constrói e publica a layer OpenCV (headless) + numpy usada pelo OMR do cartão-resposta
# no worker. Usa wheels manylinux (sem Docker). Publica via S3 (zip > 50MB).
#
# Uso: scripts/build-omr-layer.sh
# Pré: .env com credenciais + AWS_REGION; bucket de uploads existente.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${AWS_REGION:=us-east-1}"
: "${STACK_NAME:=exam-correction-v2}"
export AWS_REGION

UPLOAD_BUCKET="$(aws cloudformation describe-stack-resources --stack-name "$STACK_NAME" \
  --query "StackResources[?ResourceType=='AWS::S3::Bucket' && contains(LogicalResourceId,'uploads')].PhysicalResourceId | [0]" \
  --output text)"

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
aws s3 cp /tmp/omr-layer.zip "s3://${UPLOAD_BUCKET}/layers/omr-layer.zip" >/dev/null
aws lambda publish-layer-version \
  --layer-name exam-omr-opencv \
  --description "OpenCV headless 4.10 + numpy p/ OMR do cartao-resposta" \
  --content "S3Bucket=${UPLOAD_BUCKET},S3Key=layers/omr-layer.zip" \
  --compatible-runtimes python3.12 --compatible-architectures x86_64 \
  --query LayerVersionArn --output text
echo ">> Atualize o ARN em infra/exam_stack.py (OmrLayer) se a versão mudou."
