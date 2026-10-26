#!/usr/bin/env bash
# Provisiona o Knowledge Base DEMO do modulo Provas Online (conteudo SINTETICO).
#
# Cria (idempotente): bucket S3 de origem + upload do acervo sintetico (assets/kb-demo/),
# vector bucket + index (Amazon S3 Vectors), role de servico do Bedrock, o Knowledge Base
# (embeddings Titan v2) e a data source S3, e dispara a ingestao.
#
# Escreve infra/kb-config.json com { kbId, kbBucket } — lido pelo deploy.sh (contexto do CDK).
#
# ATENCAO: o acervo em assets/kb-demo/ e SINTETICO, apenas para demonstracao (ver
#          assets/kb-demo/README.md). Em producao, aponte KB_ID/KB_BUCKET para o seu KB real.
#
# Pre-requisitos: AWS CLI v2 recente (subcomandos `s3vectors` e `bedrock-agent`), credenciais.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${AWS_REGION:=us-east-1}"
: "${STACK_NAME:=exam-correction-v2}"
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
echo ">> Conta: ${ACCOUNT} | Regiao: ${AWS_REGION}"

# ---- Nomes/params (sobrescreviveis via ambiente) ----
: "${KB_SOURCE_BUCKET:=${STACK_NAME}-kb-source-${ACCOUNT}}"   # documentos (data source)
: "${KB_VECTOR_BUCKET:=${STACK_NAME}-kb-vectors-${ACCOUNT}}"  # embeddings (S3 Vectors)
: "${KB_INDEX_NAME:=${STACK_NAME}-kb-index}"
: "${KB_NAME:=${STACK_NAME}-kb-demo}"
: "${KB_EMBED_MODEL:=amazon.titan-embed-text-v2:0}"
: "${KB_DIMENSION:=1024}"
: "${KB_THEMES_PREFIX:=privado/graduacao/eng-software/}"
KB_ROLE_NAME="${STACK_NAME}-kb-role"
EMBED_MODEL_ARN="arn:aws:bedrock:${AWS_REGION}::foundation-model/${KB_EMBED_MODEL}"
ASSETS_DIR="assets/kb-demo"

# ---- 1) Bucket de origem + upload do acervo sintetico ----
if aws s3api head-bucket --bucket "$KB_SOURCE_BUCKET" >/dev/null 2>&1; then
  echo ">> Bucket de origem ja existe: ${KB_SOURCE_BUCKET}"
else
  echo ">> Criando bucket de origem: ${KB_SOURCE_BUCKET}"
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$KB_SOURCE_BUCKET" >/dev/null
  else
    aws s3api create-bucket --bucket "$KB_SOURCE_BUCKET" \
      --create-bucket-configuration "LocationConstraint=${AWS_REGION}" >/dev/null
  fi
  aws s3api put-public-access-block --bucket "$KB_SOURCE_BUCKET" \
    --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" >/dev/null
  aws s3api put-bucket-encryption --bucket "$KB_SOURCE_BUCKET" \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' >/dev/null
fi
echo ">> Enviando acervo sintetico (${ASSETS_DIR}/ -> s3://${KB_SOURCE_BUCKET}/) ..."
aws s3 sync "${ASSETS_DIR}/" "s3://${KB_SOURCE_BUCKET}/" --exclude "README.md" --delete >/dev/null
echo ">> Acervo enviado."

# ---- 2) Vector bucket + index (S3 Vectors) ----
if aws s3vectors get-vector-bucket --vector-bucket-name "$KB_VECTOR_BUCKET" >/dev/null 2>&1; then
  echo ">> Vector bucket ja existe: ${KB_VECTOR_BUCKET}"
else
  echo ">> Criando vector bucket: ${KB_VECTOR_BUCKET}"
  aws s3vectors create-vector-bucket --vector-bucket-name "$KB_VECTOR_BUCKET" >/dev/null
fi
if aws s3vectors get-index --vector-bucket-name "$KB_VECTOR_BUCKET" \
     --index-name "$KB_INDEX_NAME" >/dev/null 2>&1; then
  echo ">> Vector index ja existe: ${KB_INDEX_NAME}"
else
  echo ">> Criando vector index: ${KB_INDEX_NAME} (dim=${KB_DIMENSION}, cosine)"
  # nonFilterableMetadataKeys exigidos pelo Bedrock KB ao usar S3 Vectors.
  aws s3vectors create-index --vector-bucket-name "$KB_VECTOR_BUCKET" \
    --index-name "$KB_INDEX_NAME" --data-type float32 \
    --dimension "$KB_DIMENSION" --distance-metric cosine \
    --metadata-configuration '{"nonFilterableMetadataKeys":["AMAZON_BEDROCK_TEXT","AMAZON_BEDROCK_METADATA"]}' >/dev/null
fi
VECTOR_BUCKET_ARN="$(aws s3vectors get-vector-bucket --vector-bucket-name "$KB_VECTOR_BUCKET" \
  --query 'vectorBucket.vectorBucketArn' --output text)"
INDEX_ARN="$(aws s3vectors get-index --vector-bucket-name "$KB_VECTOR_BUCKET" \
  --index-name "$KB_INDEX_NAME" --query 'index.indexArn' --output text)"

# ---- 3) Role de servico do Bedrock KB (privilegio minimo) ----
TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"bedrock.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
if aws iam get-role --role-name "$KB_ROLE_NAME" >/dev/null 2>&1; then
  echo ">> Role ja existe: ${KB_ROLE_NAME}"
else
  echo ">> Criando role de servico: ${KB_ROLE_NAME}"
  aws iam create-role --role-name "$KB_ROLE_NAME" \
    --assume-role-policy-document "$TRUST" >/dev/null
fi
KB_ROLE_ARN="$(aws iam get-role --role-name "$KB_ROLE_NAME" --query 'Role.Arn' --output text)"
POLICY=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid":"Embed","Effect":"Allow","Action":["bedrock:InvokeModel"],
     "Resource":["${EMBED_MODEL_ARN}"]},
    {"Sid":"SourceRead","Effect":"Allow","Action":["s3:GetObject","s3:ListBucket"],
     "Resource":["arn:aws:s3:::${KB_SOURCE_BUCKET}","arn:aws:s3:::${KB_SOURCE_BUCKET}/*"]},
    {"Sid":"Vectors","Effect":"Allow",
     "Action":["s3vectors:GetIndex","s3vectors:PutVectors","s3vectors:GetVectors",
               "s3vectors:QueryVectors","s3vectors:ListVectors","s3vectors:DeleteVectors"],
     "Resource":["${VECTOR_BUCKET_ARN}","${INDEX_ARN}"]}
  ]
}
JSON
)
aws iam put-role-policy --role-name "$KB_ROLE_NAME" \
  --policy-name "${STACK_NAME}-kb-access" --policy-document "$POLICY" >/dev/null
echo ">> Politica da role atualizada."
sleep 10  # propagacao da role antes do create-knowledge-base

# ---- 4) Knowledge Base (idempotente por nome) ----
KB_ID="$(aws bedrock-agent list-knowledge-bases \
  --query "knowledgeBaseSummaries[?name=='${KB_NAME}'].knowledgeBaseId | [0]" --output text 2>/dev/null || true)"
if [[ -n "$KB_ID" && "$KB_ID" != "None" ]]; then
  echo ">> Knowledge Base ja existe: ${KB_NAME} (${KB_ID})"
else
  echo ">> Criando Knowledge Base: ${KB_NAME}"
  KB_ID="$(aws bedrock-agent create-knowledge-base \
    --name "$KB_NAME" \
    --description "KB DEMO (conteudo sintetico) do modulo Provas Online." \
    --role-arn "$KB_ROLE_ARN" \
    --knowledge-base-configuration "{\"type\":\"VECTOR\",\"vectorKnowledgeBaseConfiguration\":{\"embeddingModelArn\":\"${EMBED_MODEL_ARN}\"}}" \
    --storage-configuration "{\"type\":\"S3_VECTORS\",\"s3VectorsConfiguration\":{\"vectorBucketArn\":\"${VECTOR_BUCKET_ARN}\",\"indexArn\":\"${INDEX_ARN}\"}}" \
    --query 'knowledgeBase.knowledgeBaseId' --output text)"
  echo ">> KB criado: ${KB_ID}"
fi

# ---- 5) Data source S3 (idempotente por nome) ----
DS_NAME="${STACK_NAME}-kb-source"
DS_ID="$(aws bedrock-agent list-data-sources --knowledge-base-id "$KB_ID" \
  --query "dataSourceSummaries[?name=='${DS_NAME}'].dataSourceId | [0]" --output text 2>/dev/null || true)"
if [[ -n "$DS_ID" && "$DS_ID" != "None" ]]; then
  echo ">> Data source ja existe: ${DS_NAME} (${DS_ID})"
else
  echo ">> Criando data source: ${DS_NAME} (prefixo ${KB_THEMES_PREFIX})"
  DS_ID="$(aws bedrock-agent create-data-source \
    --knowledge-base-id "$KB_ID" --name "$DS_NAME" \
    --data-source-configuration "{\"type\":\"S3\",\"s3Configuration\":{\"bucketArn\":\"arn:aws:s3:::${KB_SOURCE_BUCKET}\",\"inclusionPrefixes\":[\"${KB_THEMES_PREFIX}\"]}}" \
    --query 'dataSource.dataSourceId' --output text)"
  echo ">> Data source criada: ${DS_ID}"
fi

# ---- 6) Ingestao ----
echo ">> Disparando ingestao (embeddings). Pode levar alguns minutos ..."
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id "$KB_ID" --data-source-id "$DS_ID" \
  --query 'ingestionJob.{status:status,id:ingestionJobId}' --output json || \
  echo "!! Falha ao iniciar ingestao — rode manualmente (start-ingestion-job)."

# ---- 7) Persiste config lida pelo deploy.sh ----
cat > infra/kb-config.json <<JSON
{"kbId": "${KB_ID}", "kbBucket": "${KB_SOURCE_BUCKET}"}
JSON
echo ">> Escrito infra/kb-config.json:"; cat infra/kb-config.json
echo
echo ">> KB DEMO provisionado. kbId=${KB_ID} kbBucket=${KB_SOURCE_BUCKET}"
echo ">> A ingestao roda em background; acompanhe com:"
echo "   aws bedrock-agent list-ingestion-jobs --knowledge-base-id ${KB_ID} --data-source-id ${DS_ID}"
