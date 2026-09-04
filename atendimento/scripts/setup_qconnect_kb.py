"""
Configura Amazon Q in Connect com uma Knowledge Base do tipo CUSTOM.
Faz upload dos PDFs do bucket S3 para o Q Connect para que o atendente
humano tenha acesso ao conteudo no CCP.

Uso: source .env && python3 scripts/setup_qconnect_kb.py
"""
import boto3
import json
import os
import sys
import time
import io
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env, set_env

REGION = get_env('AWS_REGION', 'us-east-1')
ACCOUNT_ID = require_env('AWS_ACCOUNT_ID')
DOCS_BUCKET = require_env('KB_VESTIBULAR_BUCKET')
ASSISTANT_ID = get_env('ASSISTANT_ID', '8a30d6b7-c8db-420e-b8af-8f8bf75f2dc3')

qconnect = boto3.client('qconnect', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)

KB_NAME = 'conteudo-institucional'

# ============================================================
# STEP 1: Create CUSTOM Knowledge Base in Q Connect
# ============================================================
print('=== Criando KB CUSTOM no Q Connect ===')
kb_id = None
try:
    resp = qconnect.create_knowledge_base(
        name=KB_NAME,
        knowledgeBaseType='CUSTOM',
        description='Conteudo institucional: apostilas, material didatico, edital vestibular, informacoes da instituicao.',
    )
    kb_id = resp['knowledgeBase']['knowledgeBaseId']
    print(f'  KB criada: {kb_id}')
except Exception as e:
    if 'Conflict' in str(e):
        # Find existing
        kbs = qconnect.list_knowledge_bases()
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

# Wait for KB to be active
print('  Aguardando KB ficar ACTIVE...')
for i in range(30):
    kb = qconnect.get_knowledge_base(knowledgeBaseId=kb_id)
    status = kb['knowledgeBase']['status']
    if status == 'ACTIVE':
        print(f'  KB ACTIVE')
        break
    time.sleep(3)

# ============================================================
# STEP 2: Associate KB with Assistant
# ============================================================
print(f'\n=== Associando KB ao Assistant ===')
print(f'  Assistant: {ASSISTANT_ID}')
try:
    resp = qconnect.create_assistant_association(
        assistantId=ASSISTANT_ID,
        associationType='KNOWLEDGE_BASE',
        association={
            'knowledgeBaseId': kb_id
        }
    )
    print(f'  Associacao criada')
except Exception as e:
    if 'Conflict' in str(e):
        print(f'  Associacao ja existe')
    else:
        print(f'  Erro: {e}')

# ============================================================
# STEP 3: Upload content from S3 to Q Connect KB
# ============================================================
print(f'\n=== Fazendo upload de conteudo para Q Connect KB ===')

# List only PDF files from S3 (not metadata JSONs)
paginator = s3.get_paginator('list_objects_v2')
pdfs = []
for page in paginator.paginate(Bucket=DOCS_BUCKET):
    for obj in page.get('Contents', []):
        key = obj['Key']
        if key.endswith('.pdf'):
            pdfs.append(key)

print(f'  {len(pdfs)} PDFs encontrados no S3')

uploaded = 0
errors = 0

for key in pdfs:
    # Use the S3 key as the content title (clean up path)
    title = key.replace('/', ' - ').replace('.pdf', '').replace('_', ' ').title()
    
    try:
        # Download PDF from S3
        obj = s3.get_object(Bucket=DOCS_BUCKET, Key=key)
        pdf_bytes = obj['Body'].read()
        
        # Upload to Q Connect
        # First create a content upload URL
        resp = qconnect.start_content_upload(
            knowledgeBaseId=kb_id,
            contentType='application/pdf'
        )
        upload_id = resp['uploadId']
        url = resp['url']
        headers_to_include = resp.get('headersToInclude', {})
        
        # Upload the file to the presigned URL
        import urllib.request
        req = urllib.request.Request(url, data=pdf_bytes, method='PUT')
        req.add_header('Content-Type', 'application/pdf')
        for h_key, h_val in headers_to_include.items():
            req.add_header(h_key, h_val)
        urllib.request.urlopen(req)
        
        # Create the content record
        qconnect.create_content(
            knowledgeBaseId=kb_id,
            name=key.split('/')[-1].replace('.pdf', ''),
            title=title,
            uploadId=upload_id,
        )
        
        uploaded += 1
        if uploaded % 10 == 0:
            print(f'  [{uploaded}/{len(pdfs)}] uploading...')
            
    except Exception as e:
        errors += 1
        if errors <= 5:
            print(f'  ERRO {key}: {e}')
        elif errors == 6:
            print(f'  ... suprimindo erros adicionais ...')

print(f'\n=== Resultado ===')
print(f'  PDFs enviados: {uploaded}')
print(f'  Erros: {errors}')
print(f'  KB ID: {kb_id}')
print(f'  Assistant: {ASSISTANT_ID}')
set_env('QCONNECT_KB_ID', kb_id)
print(f'\nDone! O Q Connect Assistant agora tem acesso ao conteudo institucional.')
