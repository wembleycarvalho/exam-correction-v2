"""
Setup Knowledge Base do Vestibular no Bedrock.
- Cria bucket S3 e faz upload do PDF
- Cria IAM Role para a KB
- Cria collection OpenSearch Serverless
- Cria Knowledge Base no Bedrock
- Cria data source e sincroniza

Uso: source .env && python3 scripts/setup_kb_vestibular.py
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
BUCKET_NAME = f'kb-vestibular-demo-{ACCOUNT_ID}'
KB_NAME = 'kb-vestibular'
COLLECTION_NAME = 'kb-vestibular-vectors'
ROLE_NAME = 'BedrockKBVestibularRole'
PDF_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'edital_vestibular_2026_2.pdf')

s3 = boto3.client('s3', region_name=REGION)
iam = boto3.client('iam')
aoss = boto3.client('opensearchserverless', region_name=REGION)
bedrock_agent = boto3.client('bedrock-agent', region_name=REGION)

# ============================================================
# STEP 1: S3 Bucket + Upload PDF
# ============================================================
print('=== S3 Bucket ===')
try:
    s3.create_bucket(Bucket=BUCKET_NAME)
    print(f'  Created: {BUCKET_NAME}')
except Exception as e:
    if 'BucketAlreadyOwnedByYou' in str(type(e)) or 'BucketAlreadyExists' in str(e):
        print(f'  Exists: {BUCKET_NAME}')
    else:
        raise

print('  Uploading PDF...')
with open(PDF_PATH, 'rb') as f:
    s3.put_object(Bucket=BUCKET_NAME, Key='edital_vestibular_2026_2.pdf', Body=f.read(), ContentType='application/pdf')
print('  PDF uploaded')
set_env('KB_VESTIBULAR_BUCKET', BUCKET_NAME)

# ============================================================
# STEP 2: IAM Role
# ============================================================
print('\n=== IAM Role ===')
trust = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "bedrock.amazonaws.com"},
        "Action": "sts:AssumeRole",
        "Condition": {
            "StringEquals": {"aws:SourceAccount": ACCOUNT_ID},
            "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:knowledge-base/*"}
        }
    }]
}

try:
    resp = iam.create_role(RoleName=ROLE_NAME, AssumeRolePolicyDocument=json.dumps(trust))
    print(f'  Role created: {ROLE_NAME}')
    time.sleep(10)  # Wait for role propagation
except iam.exceptions.EntityAlreadyExistsException:
    print(f'  Role exists: {ROLE_NAME}')

role_arn = f'arn:aws:iam::{ACCOUNT_ID}:role/{ROLE_NAME}'

# Policy
policy_name = 'BedrockKBVestibularPolicy'
policy_doc = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:ListBucket"],
            "Resource": [f"arn:aws:s3:::{BUCKET_NAME}", f"arn:aws:s3:::{BUCKET_NAME}/*"]
        },
        {
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel"],
            "Resource": [f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0"]
        },
        {
            "Effect": "Allow",
            "Action": ["aoss:APIAccessAll"],
            "Resource": [f"arn:aws:aoss:{REGION}:{ACCOUNT_ID}:collection/*"]
        }
    ]
}

policy_arn = f'arn:aws:iam::{ACCOUNT_ID}:policy/{policy_name}'
try:
    iam.create_policy(PolicyName=policy_name, PolicyDocument=json.dumps(policy_doc))
    print(f'  Policy created: {policy_name}')
except iam.exceptions.EntityAlreadyExistsException:
    versions = iam.list_policy_versions(PolicyArn=policy_arn)['Versions']
    for v in versions:
        if not v['IsDefaultVersion']:
            iam.delete_policy_version(PolicyArn=policy_arn, VersionId=v['VersionId'])
    iam.create_policy_version(PolicyArn=policy_arn, PolicyDocument=json.dumps(policy_doc), SetAsDefault=True)
    print(f'  Policy updated: {policy_name}')

iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=policy_arn)

# ============================================================
# STEP 3: OpenSearch Serverless Collection
# ============================================================
print('\n=== OpenSearch Serverless ===')

# Encryption policy
try:
    aoss.create_security_policy(
        name=f'{COLLECTION_NAME}-enc',
        type='encryption',
        policy=json.dumps({
            "Rules": [{"ResourceType": "collection", "Resource": [f"collection/{COLLECTION_NAME}"]}],
            "AWSOwnedKey": True
        })
    )
    print('  Encryption policy created')
except Exception as e:
    if 'Conflict' in str(e):
        print('  Encryption policy exists')
    else:
        print(f'  Encryption policy error: {e}')

# Network policy
try:
    aoss.create_security_policy(
        name=f'{COLLECTION_NAME}-net',
        type='network',
        policy=json.dumps([{
            "Rules": [{"ResourceType": "collection", "Resource": [f"collection/{COLLECTION_NAME}"]}, {"ResourceType": "dashboard", "Resource": [f"collection/{COLLECTION_NAME}"]}],
            "AllowFromPublic": True
        }])
    )
    print('  Network policy created')
except Exception as e:
    if 'Conflict' in str(e):
        print('  Network policy exists')
    else:
        print(f'  Network policy error: {e}')

# Data access policy
try:
    aoss.create_access_policy(
        name=f'{COLLECTION_NAME}-access',
        type='data',
        policy=json.dumps([{
            "Rules": [
                {"ResourceType": "collection", "Resource": [f"collection/{COLLECTION_NAME}"], "Permission": ["aoss:CreateCollectionItems", "aoss:DeleteCollectionItems", "aoss:UpdateCollectionItems", "aoss:DescribeCollectionItems"]},
                {"ResourceType": "index", "Resource": [f"index/{COLLECTION_NAME}/*"], "Permission": ["aoss:CreateIndex", "aoss:DeleteIndex", "aoss:UpdateIndex", "aoss:DescribeIndex", "aoss:ReadDocument", "aoss:WriteDocument"]}
            ],
            "Principal": [role_arn, f"arn:aws:iam::{ACCOUNT_ID}:root"],
            "Description": "KB access"
        }])
    )
    print('  Data access policy created')
except Exception as e:
    if 'Conflict' in str(e):
        print('  Data access policy exists')
    else:
        print(f'  Data access policy error: {e}')

# Create collection
collection_id = None
try:
    resp = aoss.create_collection(name=COLLECTION_NAME, type='VECTORSEARCH', description='Vector store for vestibular KB')
    collection_id = resp['createCollectionDetail']['id']
    print(f'  Collection creating: {collection_id}')
except Exception as e:
    if 'Conflict' in str(e):
        # Find existing
        colls = aoss.list_collections(collectionFilters={'name': COLLECTION_NAME})
        if colls['collectionSummaries']:
            collection_id = colls['collectionSummaries'][0]['id']
            print(f'  Collection exists: {collection_id}')
    else:
        print(f'  Collection error: {e}')

# Wait for collection to be active
if collection_id:
    print('  Waiting for collection to be ACTIVE...')
    for i in range(60):
        resp = aoss.batch_get_collection(ids=[collection_id])
        details = resp.get('collectionDetails', [])
        if details and details[0].get('status') == 'ACTIVE':
            collection_arn = details[0]['arn']
            collection_endpoint = details[0].get('collectionEndpoint', '')
            print(f'  ACTIVE: {collection_endpoint}')
            set_env('AOSS_COLLECTION_ID', collection_id)
            set_env('AOSS_COLLECTION_ENDPOINT', collection_endpoint)
            break
        time.sleep(10)
    else:
        print('  WARNING: Collection not active after 10 min, continuing...')
        collection_endpoint = f'https://{collection_id}.{REGION}.aoss.amazonaws.com'

# Create index via OpenSearch
print('  Creating vector index...')
try:
    from opensearchpy import OpenSearch, RequestsHttpHandler
    from requests_aws4auth import AWS4Auth
    import boto3

    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, REGION, 'aoss', session_token=credentials.token)

    host = collection_endpoint.replace('https://', '')
    client = OpenSearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpHandler,
        timeout=300
    )

    index_body = {
        "settings": {"index.knn": True},
        "mappings": {
            "properties": {
                "bedrock-knowledge-base-default-vector": {"type": "knn_vector", "dimension": 1024, "method": {"engine": "faiss", "name": "hnsw"}},
                "AMAZON_BEDROCK_TEXT_CHUNK": {"type": "text"},
                "AMAZON_BEDROCK_METADATA": {"type": "text"}
            }
        }
    }
    client.indices.create(index='bedrock-knowledge-base-default-index', body=index_body)
    print('  Index created')
except ImportError:
    print('  WARNING: opensearchpy not installed. Index must be created manually or via console.')
    print('  Install: pip install opensearch-py requests-aws4auth')
except Exception as e:
    if '400' in str(e) and 'already exists' in str(e).lower():
        print('  Index exists')
    else:
        print(f'  Index error: {e}')

# ============================================================
# STEP 4: Bedrock Knowledge Base
# ============================================================
print('\n=== Bedrock Knowledge Base ===')
kb_id = None
try:
    resp = bedrock_agent.create_knowledge_base(
        name=KB_NAME,
        description='Base de conhecimento com edital do vestibular 2026.2',
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            'type': 'VECTOR',
            'vectorKnowledgeBaseConfiguration': {
                'embeddingModelArn': f'arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0'
            }
        },
        storageConfiguration={
            'type': 'OPENSEARCH_SERVERLESS',
            'opensearchServerlessConfiguration': {
                'collectionArn': f'arn:aws:aoss:{REGION}:{ACCOUNT_ID}:collection/{collection_id}',
                'vectorIndexName': 'bedrock-knowledge-base-default-index',
                'fieldMapping': {
                    'vectorField': 'bedrock-knowledge-base-default-vector',
                    'textField': 'AMAZON_BEDROCK_TEXT_CHUNK',
                    'metadataField': 'AMAZON_BEDROCK_METADATA'
                }
            }
        }
    )
    kb_id = resp['knowledgeBase']['knowledgeBaseId']
    print(f'  KB created: {kb_id}')
except Exception as e:
    if 'Conflict' in str(e):
        # Find existing
        kbs = bedrock_agent.list_knowledge_bases()
        for kb in kbs.get('knowledgeBaseSummaries', []):
            if kb['name'] == KB_NAME:
                kb_id = kb['knowledgeBaseId']
                print(f'  KB exists: {kb_id}')
                break
    else:
        print(f'  KB error: {e}')

if kb_id:
    set_env('KB_VESTIBULAR_ID', kb_id)

    # Wait for KB to be active
    for i in range(30):
        kb = bedrock_agent.get_knowledge_base(knowledgeBaseId=kb_id)
        if kb['knowledgeBase']['status'] == 'ACTIVE':
            print(f'  KB ACTIVE')
            break
        time.sleep(5)

    # Create data source
    print('  Creating data source...')
    ds_id = None
    try:
        resp = bedrock_agent.create_data_source(
            knowledgeBaseId=kb_id,
            name='edital-vestibular',
            description='PDF do edital do vestibular 2026.2',
            dataSourceConfiguration={
                'type': 'S3',
                's3Configuration': {
                    'bucketArn': f'arn:aws:s3:::{BUCKET_NAME}'
                }
            }
        )
        ds_id = resp['dataSource']['dataSourceId']
        print(f'  Data source created: {ds_id}')
    except Exception as e:
        if 'Conflict' in str(e):
            dss = bedrock_agent.list_data_sources(knowledgeBaseId=kb_id)
            for ds in dss.get('dataSourceSummaries', []):
                if ds['name'] == 'edital-vestibular':
                    ds_id = ds['dataSourceId']
                    print(f'  Data source exists: {ds_id}')
                    break
        else:
            print(f'  Data source error: {e}')

    # Sync
    if ds_id:
        print('  Starting sync...')
        try:
            bedrock_agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
            print('  Sync started (runs in background)')
        except Exception as e:
            print(f'  Sync error: {e}')

print('\nDone!')
print(f'KB ID: {kb_id}')
print(f'PROXIMO PASSO (console): Adicionar KB no AI Agent Designer do Connect')
