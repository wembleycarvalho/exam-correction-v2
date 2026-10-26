"""
Setup do sistema de fotos de clientes.
Cria o bucket S3, a Lambda geradora de presigned URLs e a policy necessaria.

Uso: source .env && python3 scripts/setup_fotos_clientes.py
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

s3 = boto3.client('s3', region_name=REGION)
iam = boto3.client('iam', region_name=REGION)
lmb = boto3.client('lambda', region_name=REGION)

BUCKET_NAME = f'fotos-clientes-{ACCOUNT_ID}'
LAMBDA_NAME = 'mcp-foto-cliente'
LAMBDA_ROLE_NAME = 'LambdaFotoClienteRole'

# ============================================================
# Step 1: Create S3 bucket for client photos
# ============================================================
print('=== Setup Fotos de Clientes ===')
print()
print(f'1. Criando bucket S3: {BUCKET_NAME}')

try:
    if REGION == 'us-east-1':
        s3.create_bucket(Bucket=BUCKET_NAME)
    else:
        s3.create_bucket(
            Bucket=BUCKET_NAME,
            CreateBucketConfiguration={'LocationConstraint': REGION}
        )
    print(f'   Bucket criado: {BUCKET_NAME}')
except s3.exceptions.BucketAlreadyOwnedByYou:
    print(f'   Bucket ja existe: {BUCKET_NAME}')
except Exception as e:
    if 'BucketAlreadyOwnedByYou' in str(e) or 'BucketAlreadyExists' in str(e):
        print(f'   Bucket ja existe: {BUCKET_NAME}')
    else:
        raise

# Block public access
s3.put_public_access_block(
    Bucket=BUCKET_NAME,
    PublicAccessBlockConfiguration={
        'BlockPublicAcls': True,
        'IgnorePublicAcls': True,
        'BlockPublicPolicy': True,
        'RestrictPublicBuckets': True
    }
)
print('   Public access bloqueado')

# CORS para permitir que o agent workspace carregue imagens
s3.put_bucket_cors(
    Bucket=BUCKET_NAME,
    CORSConfiguration={
        'CORSRules': [{
            'AllowedHeaders': ['*'],
            'AllowedMethods': ['GET'],
            'AllowedOrigins': [
                'https://*.my.connect.aws',
                'https://*.awsapps.com'
            ],
            'ExposeHeaders': ['Content-Length', 'Content-Type'],
            'MaxAgeSeconds': 3600
        }]
    }
)
print('   CORS configurado para Connect agent workspace')

# ============================================================
# Step 2: Create IAM Role for Lambda
# ============================================================
print(f'\n2. Criando IAM Role: {LAMBDA_ROLE_NAME}')

trust_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole"
    }]
}

try:
    role_resp = iam.create_role(
        RoleName=LAMBDA_ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description='Role for Lambda that generates presigned URLs for client photos'
    )
    role_arn = role_resp['Role']['Arn']
    print(f'   Role criada: {role_arn}')
    time.sleep(8)  # Wait for IAM propagation
except iam.exceptions.EntityAlreadyExistsException:
    role_arn = f'arn:aws:iam::{ACCOUNT_ID}:role/{LAMBDA_ROLE_NAME}'
    print(f'   Role ja existe: {role_arn}')

# Attach policies
inline_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": f"arn:aws:s3:::{BUCKET_NAME}/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": ["dynamodb:GetItem", "dynamodb:Query"],
            "Resource": [
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/cadastro-usuarios",
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/cadastro-usuarios/index/*"
            ]
        }
    ]
}

iam.put_role_policy(
    RoleName=LAMBDA_ROLE_NAME,
    PolicyName='FotoClientePolicy',
    PolicyDocument=json.dumps(inline_policy)
)
print('   Inline policy attached')

# ============================================================
# Step 3: Create Lambda function
# ============================================================
print(f'\n3. Criando Lambda: {LAMBDA_NAME}')

lambda_code = '''
import json
import boto3
import os

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('cadastro-usuarios')

BUCKET = os.environ['FOTOS_BUCKET']
EXPIRATION = int(os.environ.get('URL_EXPIRATION', '3600'))  # 1 hora


def lambda_handler(event, context):
    """
    Gera presigned URL para a foto do cliente.
    Input: {"cpf": "12345678900"} ou {"telefone": "+5511999999999"}
    Output: {"foto_url": "https://...", "has_foto": true/false}
    """
    print(f"Event: {json.dumps(event)}")

    cpf = event.get('cpf', '')
    telefone = event.get('telefone', '')

    # Se recebeu telefone, buscar CPF no DynamoDB
    if not cpf and telefone:
        for p in [telefone, f"+{telefone}", telefone.replace('+', '')]:
            resp = table.query(
                IndexName='telefone-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('telefone').eq(p)
            )
            if resp['Items']:
                cpf = resp['Items'][0].get('cpf', '')
                break

    if not cpf:
        return {"has_foto": False, "message": "CPF nao encontrado"}

    # Tentar gerar URL para foto (tenta .jpg, .png, .webp)
    for ext in ['jpg', 'png', 'webp']:
        key = f"fotos/{cpf}.{ext}"
        try:
            s3.head_object(Bucket=BUCKET, Key=key)
            # Foto existe, gerar presigned URL
            url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': BUCKET, 'Key': key},
                ExpiresIn=EXPIRATION
            )
            return {
                "has_foto": True,
                "foto_url": url,
                "cpf": cpf,
                "formato": ext
            }
        except s3.exceptions.ClientError:
            continue

    return {"has_foto": False, "cpf": cpf, "message": "Foto nao encontrada no S3"}
'''

import zipfile
import io

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('lambda_function.py', lambda_code.strip())
zip_buffer.seek(0)

try:
    resp = lmb.create_function(
        FunctionName=LAMBDA_NAME,
        Runtime='python3.12',
        Role=role_arn,
        Handler='lambda_function.lambda_handler',
        Code={'ZipFile': zip_buffer.read()},
        Timeout=10,
        MemorySize=128,
        Environment={
            'Variables': {
                'FOTOS_BUCKET': BUCKET_NAME,
                'URL_EXPIRATION': '3600'
            }
        }
    )
    print(f'   Lambda criada: {resp["FunctionArn"]}')
except lmb.exceptions.ResourceConflictException:
    # Update existing
    zip_buffer.seek(0)
    lmb.update_function_code(
        FunctionName=LAMBDA_NAME,
        ZipFile=zip_buffer.read()
    )
    lmb.update_function_configuration(
        FunctionName=LAMBDA_NAME,
        Environment={
            'Variables': {
                'FOTOS_BUCKET': BUCKET_NAME,
                'URL_EXPIRATION': '3600'
            }
        }
    )
    print(f'   Lambda atualizada: {LAMBDA_NAME}')

# ============================================================
# Step 4: Add Lambda to Gateway targets
# ============================================================
print(f'\n4. Adicionando target ao Gateway...')

GATEWAY_ID = get_env('GATEWAY_ID', '')
if GATEWAY_ID:
    try:
        agentcore = boto3.client('bedrock-agentcore', region_name=REGION)
        # Note: Adding gateway target may need to be done separately
        # depending on the gateway setup
        print(f'   Gateway ID: {GATEWAY_ID}')
        print(f'   NOTA: Adicionar target "foto-cliente" -> {LAMBDA_NAME} manualmente se necessario')
    except Exception as e:
        print(f'   Aviso: {e}')
else:
    print('   GATEWAY_ID nao encontrado no .env, pular gateway config')

# ============================================================
# Step 5: Save env vars
# ============================================================
print(f'\n5. Salvando variaveis de ambiente...')
set_env('FOTOS_BUCKET', BUCKET_NAME)
print(f'   FOTOS_BUCKET={BUCKET_NAME}')

print(f'\n=== Setup completo! ===')
print(f'''
Proximos passos:
  1. Fazer upload de fotos: python3 scripts/upload_foto_cliente.py <cpf> <arquivo.jpg>
  2. Sync customer profiles: python3 scripts/sync_customer_profiles.py
  3. Configurar step-by-step guide no Connect console (opcional)

Estrutura no S3:
  s3://{BUCKET_NAME}/fotos/<cpf>.jpg
  s3://{BUCKET_NAME}/fotos/<cpf>.png
  s3://{BUCKET_NAME}/fotos/<cpf>.webp
''')
