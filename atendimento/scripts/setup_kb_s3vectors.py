"""
Recria a Knowledge Base usando S3 Vectors como vector store (em vez de OpenSearch).
- Deleta a KB existente (OpenSearch)
- Cria vector bucket S3
- Cria vector index no bucket
- Cria nova KB com S3_VECTORS storage
- Cria data source apontando pro bucket de documentos
- Inicia sync

Uso: source .env && python3 scripts/setup_kb_s3vectors.py
"""
import boto3
import json
import os
import sys
import time
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env, set_env

REGION = get_env('AWS_REGION', 'us-east-1')
ACCOUNT_ID = require_env('AWS_ACCOUNT_ID')
OLD_KB_ID = get_env('KB_VESTIBULAR_ID', '')
DOCS_BUCKET = require_env('KB_VESTIBULAR_BUCKET')  # bucket com os PDFs

KB_NAME = 'kb-vestibular'
VECTOR_BUCKET_NAME = f'kb-vestibular-vectors-{ACCOUNT_ID}'
VECTOR_INDEX_NAME = 'kb-vestibular-index'
ROLE_NAME = 'BedrockKBVestibularRole'
EMBEDDING_MODEL = f'arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0'

s3 = boto3.client('s3', region_name=REGION)
s3vectors = boto3.client('s3vectors', region_name=REGION)
iam = boto3.client('iam')
bedrock_agent = boto3.client('bedrock-agent', region_name=REGION)

role_arn = f'arn:aws:iam::{ACCOUNT_ID}:role/{ROLE_NAME}'

# STEP 1: KB antiga ja foi deletada na execucao anterior
print('=== KB antiga ja deletada ===')

# ============================================================
# STEP 2: Create S3 Vector Bucket
# ============================================================
print(f'\n=== Criando Vector Bucket: {VECTOR_BUCKET_NAME} ===')
try:
    s3vectors.create_vector_bucket(vectorBucketName=VECTOR_BUCKET_NAME)
    print(f'  Vector bucket criado: {VECTOR_BUCKET_NAME}')
except Exception as e:
    if 'BucketAlreadyExists' in str(e) or 'already exists' in str(e).lower() or 'Conflict' in str(e):
        print(f'  Vector bucket ja existe: {VECTOR_BUCKET_NAME}')
    else:
        print(f'  Erro: {e}')
        raise

# Get vector bucket ARN
vector_bucket_arn = f'arn:aws:s3vectors:{REGION}:{ACCOUNT_ID}:bucket/{VECTOR_BUCKET_NAME}'
print(f'  ARN: {vector_bucket_arn}')

# ============================================================
# STEP 3: Create Vector Index
# ============================================================
print(f'\n=== Criando Vector Index: {VECTOR_INDEX_NAME} ===')
try:
    resp = s3vectors.create_index(
        vectorBucketName=VECTOR_BUCKET_NAME,
        indexName=VECTOR_INDEX_NAME,
        dataType='float32',
        dimension=1024,  # Titan Embed Text v2 dimension
        distanceMetric='cosine'
    )
    print(f'  Vector index criado: {VECTOR_INDEX_NAME}')
except Exception as e:
    if 'already exists' in str(e).lower() or 'Conflict' in str(e):
        print(f'  Vector index ja existe: {VECTOR_INDEX_NAME}')
    else:
        print(f'  Erro: {e}')
        raise

# Get index ARN
index_arn = f'arn:aws:s3vectors:{REGION}:{ACCOUNT_ID}:bucket/{VECTOR_BUCKET_NAME}/index/{VECTOR_INDEX_NAME}'
print(f'  Index ARN: {index_arn}')

# ============================================================
# STEP 4: Update IAM Role policy for S3 Vectors
# ============================================================
print(f'\n=== Atualizando IAM Policy ===')
policy_name = 'BedrockKBVestibularPolicy'
policy_doc = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:ListBucket"],
            "Resource": [f"arn:aws:s3:::{DOCS_BUCKET}", f"arn:aws:s3:::{DOCS_BUCKET}/*"]
        },
        {
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel"],
            "Resource": [EMBEDDING_MODEL]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3vectors:CreateVectorBucket",
                "s3vectors:GetVectorBucket",
                "s3vectors:ListVectorBuckets",
                "s3vectors:CreateVectorIndex",
                "s3vectors:GetVectorIndex",
                "s3vectors:ListVectorIndexes",
                "s3vectors:PutVectors",
                "s3vectors:GetVectors",
                "s3vectors:DeleteVectors",
                "s3vectors:QueryVectors",
                "s3vectors:ListVectors"
            ],
            "Resource": [
                vector_bucket_arn,
                f'{vector_bucket_arn}/*',
                index_arn
            ]
        }
    ]
}

policy_arn = f'arn:aws:iam::{ACCOUNT_ID}:policy/{policy_name}'
try:
    # Delete old versions to make room
    versions = iam.list_policy_versions(PolicyArn=policy_arn)['Versions']
    for v in versions:
        if not v['IsDefaultVersion']:
            iam.delete_policy_version(PolicyArn=policy_arn, VersionId=v['VersionId'])
    iam.create_policy_version(PolicyArn=policy_arn, PolicyDocument=json.dumps(policy_doc), SetAsDefault=True)
    print(f'  Policy atualizada: {policy_name}')
except iam.exceptions.NoSuchEntityException:
    iam.create_policy(PolicyName=policy_name, PolicyDocument=json.dumps(policy_doc))
    iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=policy_arn)
    print(f'  Policy criada: {policy_name}')
except Exception as e:
    print(f'  Erro: {e}')

time.sleep(10)  # Wait for IAM propagation

# ============================================================
# STEP 5: Create new KB with S3_VECTORS
# ============================================================
print(f'\n=== Criando KB com S3 Vectors ===')
kb_id = None
try:
    resp = bedrock_agent.create_knowledge_base(
        name=KB_NAME,
        description='Base de conhecimento institucional com apostilas, material didatico e conteudo publico. Vector store: S3 Vectors.',
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            'type': 'VECTOR',
            'vectorKnowledgeBaseConfiguration': {
                'embeddingModelArn': EMBEDDING_MODEL
            }
        },
        storageConfiguration={
            'type': 'S3_VECTORS',
            's3VectorsConfiguration': {
                'vectorBucketArn': vector_bucket_arn,
                'indexName': VECTOR_INDEX_NAME
            }
        }
    )
    kb_id = resp['knowledgeBase']['knowledgeBaseId']
    print(f'  KB criada: {kb_id}')
except Exception as e:
    if 'Conflict' in str(e):
        kbs = bedrock_agent.list_knowledge_bases()
        for kb in kbs.get('knowledgeBaseSummaries', []):
            if kb['name'] == KB_NAME:
                kb_id = kb['knowledgeBaseId']
                print(f'  KB ja existe: {kb_id}')
                break
    else:
        print(f'  Erro: {e}')
        raise

if not kb_id:
    print('ERRO: Nao foi possivel criar a KB')
    sys.exit(1)

set_env('KB_VESTIBULAR_ID', kb_id)

# Wait for KB to be active
print('  Aguardando KB ficar ACTIVE...')
for i in range(30):
    kb = bedrock_agent.get_knowledge_base(knowledgeBaseId=kb_id)
    status = kb['knowledgeBase']['status']
    if status == 'ACTIVE':
        print(f'  KB ACTIVE: {kb_id}')
        break
    elif status == 'FAILED':
        reasons = kb['knowledgeBase'].get('failureReasons', [])
        print(f'  KB FAILED: {reasons}')
        sys.exit(1)
    time.sleep(5)
else:
    print('  WARNING: KB nao ficou ACTIVE em 150s')

# ============================================================
# STEP 6: Create data source
# ============================================================
print(f'\n=== Criando Data Source ===')
ds_id = None
try:
    resp = bedrock_agent.create_data_source(
        knowledgeBaseId=kb_id,
        name='apostilas-e-conteudo',
        description='PDFs de apostilas, material didatico, newsletters e conteudo publico',
        dataSourceConfiguration={
            'type': 'S3',
            's3Configuration': {
                'bucketArn': f'arn:aws:s3:::{DOCS_BUCKET}'
            }
        }
    )
    ds_id = resp['dataSource']['dataSourceId']
    print(f'  Data source criado: {ds_id}')
except Exception as e:
    if 'Conflict' in str(e):
        dss = bedrock_agent.list_data_sources(knowledgeBaseId=kb_id)
        for ds in dss.get('dataSourceSummaries', []):
            ds_id = ds['dataSourceId']
            print(f'  Data source ja existe: {ds_id}')
            break
    else:
        print(f'  Erro: {e}')

# ============================================================
# STEP 7: Start sync
# ============================================================
if ds_id:
    print(f'\n=== Iniciando Sync ===')
    try:
        bedrock_agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
        print('  Sync iniciado (roda em background)')
        print('  A indexacao pode levar alguns minutos.')
    except Exception as e:
        print(f'  Erro ao iniciar sync: {e}')

# ============================================================
# STEP 8: Update Lambda env var
# ============================================================
print(f'\n=== Atualizando Lambda mcp-vestibular ===')
try:
    lmb = boto3.client('lambda', region_name=REGION)
    lmb.update_function_configuration(
        FunctionName='mcp-vestibular',
        Environment={'Variables': {'KB_VESTIBULAR_ID': kb_id}}
    )
    print(f'  Lambda atualizada com KB_VESTIBULAR_ID={kb_id}')
except Exception as e:
    print(f'  Erro: {e}')

# ============================================================
# Done
# ============================================================
print(f'\n=== Done! ===')
print(f'  KB ID: {kb_id}')
print(f'  Vector Bucket: {VECTOR_BUCKET_NAME}')
print(f'  Vector Index: {VECTOR_INDEX_NAME}')
print(f'  Docs Bucket: {DOCS_BUCKET}')
print(f'  .env atualizado com novo KB_VESTIBULAR_ID')
