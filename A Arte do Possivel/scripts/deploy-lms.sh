#!/usr/bin/env bash
# Publica o acervo do módulo LMS de Vídeo e dispara a ingestão:
#   1) cria o vector bucket + índice no S3 Vectors (fora do CDK);
#   2) sobe os vídeos de assets/lms-demo/videos/ para o bucket do acervo (prefixo lms/media/);
#   3) invoca a Lambda de ingestão (Marengo -> S3 Vectors) por disciplina, do manifesto.
#
# Pré-requisitos: deploy do CDK já feito com -c modules=...,lms (cria bucket/tabelas/Lambdas/
#   HTTP API) e os vídeos gerados por assets/lms-demo/build_lms_videos.py.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${AWS_REGION:=us-east-1}"
: "${STACK_NAME:=exam-correction-v2}"
export AWS_REGION

PY="${LMS_PY:-orientador-academico/.venv/bin/python}"
MANIFEST="assets/lms-demo/manifest.json"
VIDEOS_DIR="assets/lms-demo/videos"

out() { aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" --output text; }

MEDIA_BUCKET="$(out LmsMediaBucket)"
VECTOR_BUCKET="$(out LmsVectorBucket)"
VECTOR_INDEX="$(out LmsVectorIndex)"
INGEST_FN="$(out LmsIngestFn)"

if [[ -z "$MEDIA_BUCKET" || "$MEDIA_BUCKET" == "None" ]]; then
  echo "!! Outputs do LMS ausentes. Rode o CDK com -c modules=...,lms antes." >&2
  exit 1
fi
echo ">> media=$MEDIA_BUCKET | vectors=$VECTOR_BUCKET/$VECTOR_INDEX | fn=$INGEST_FN"

# 1) S3 Vectors: vector bucket + índice (idempotente). Dim 512 (Marengo 3.0), cosseno.
echo ">> [1/3] S3 Vectors (bucket + índice)"
"$PY" - "$AWS_REGION" "$VECTOR_BUCKET" "$VECTOR_INDEX" <<'PY'
import sys, boto3
region, bucket, index = sys.argv[1:4]
c = boto3.client("s3vectors", region_name=region)
try:
    c.create_vector_bucket(vectorBucketName=bucket)
    print("   vector bucket criado:", bucket)
except Exception as e:
    print("   vector bucket:", type(e).__name__, "(provavelmente já existe)")
try:
    c.create_index(vectorBucketName=bucket, indexName=index, dataType="float32",
                   dimension=512, distanceMetric="cosine",
                   metadataConfiguration={"nonFilterableMetadataKeys":
                                          ["narration", "chapter_title", "name"]})
    print("   índice criado:", index)
except Exception as e:
    print("   índice:", type(e).__name__, "(provavelmente já existe)")
PY

# 2) Upload dos vídeos para lms/media/ (mesmo path do behavior CloudFront /lms/media/*).
echo ">> [2/3] upload dos vídeos -> s3://$MEDIA_BUCKET/lms/media/"
if [[ -d "$VIDEOS_DIR" ]]; then
  aws s3 sync "$VIDEOS_DIR" "s3://$MEDIA_BUCKET/lms/media" --region "$AWS_REGION" \
    --exclude "*" --include "*.mp4"
else
  echo "!! $VIDEOS_DIR não existe (gere os vídeos com build_lms_videos.py)" >&2
fi

# 3) Ingestão por disciplina (invoca a Lambda com a entrada do manifesto).
echo ">> [3/3] ingestão (Marengo -> S3 Vectors) por disciplina"
"$PY" - "$AWS_REGION" "$INGEST_FN" "$MANIFEST" <<'PY'
import sys, json, boto3
region, fn, manifest = sys.argv[1:4]
lam = boto3.client("lambda", region_name=region)
items = json.load(open(manifest, encoding="utf-8"))
ok = fail = 0
for d in items:
    payload = {"action": "ingest", "discipline": d}
    r = lam.invoke(FunctionName=fn, Payload=json.dumps(payload).encode())
    try:
        res = json.loads(r["Payload"].read() or b"{}")
    except Exception:
        res = {}
    status = (res or {}).get("status", "?")
    segs = (res or {}).get("segments", "")
    print(f"   {d['discipline_id']:9s} {d['name'][:32]:32s} -> {status} {segs}")
    if status == "ready":
        ok += 1
    else:
        fail += 1
print(f">> ingestão: OK={ok} FALHAS={fail}")
PY

echo ">> Concluído."
