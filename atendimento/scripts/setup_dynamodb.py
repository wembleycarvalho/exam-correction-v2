"""
Setup DynamoDB tables: cadastro-usuarios, catalogo-cursos, academico.
Cria as tabelas vazias. Dados sao populados por setup_academico.py.
Uso: source .env && python3 scripts/setup_dynamodb.py
"""
import boto3
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env

REGION = get_env('AWS_REGION', 'us-east-1')
dynamodb_client = boto3.client('dynamodb', region_name=REGION)

# === cadastro-usuarios (PK=cpf, GSI=telefone-index) ===
print('=== cadastro-usuarios ===')
try:
    dynamodb_client.create_table(
        TableName='cadastro-usuarios',
        KeySchema=[{'AttributeName': 'cpf', 'KeyType': 'HASH'}],
        AttributeDefinitions=[
            {'AttributeName': 'cpf', 'AttributeType': 'S'},
            {'AttributeName': 'telefone', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[{
            'IndexName': 'telefone-index',
            'KeySchema': [{'AttributeName': 'telefone', 'KeyType': 'HASH'}],
            'Projection': {'ProjectionType': 'ALL'}
        }],
        BillingMode='PAY_PER_REQUEST'
    )
    dynamodb_client.get_waiter('table_exists').wait(TableName='cadastro-usuarios')
    print('  Table created (PK=cpf, GSI=telefone-index)')
except dynamodb_client.exceptions.ResourceInUseException:
    print('  Table exists')

# === catalogo-cursos (PK=curso_id) ===
print('\n=== catalogo-cursos ===')
try:
    dynamodb_client.create_table(
        TableName='catalogo-cursos',
        KeySchema=[{'AttributeName': 'curso_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'curso_id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )
    dynamodb_client.get_waiter('table_exists').wait(TableName='catalogo-cursos')
    print('  Table created (PK=curso_id)')
except dynamodb_client.exceptions.ResourceInUseException:
    print('  Table exists')

# === academico (PK=cpf, documento unico) ===
print('\n=== academico ===')
try:
    dynamodb_client.create_table(
        TableName='academico',
        KeySchema=[{'AttributeName': 'cpf', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'cpf', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )
    dynamodb_client.get_waiter('table_exists').wait(TableName='academico')
    print('  Table created (PK=cpf)')
except dynamodb_client.exceptions.ResourceInUseException:
    print('  Table exists')

print('\nDone! Tabelas criadas. Execute setup_academico.py para popular dados.')
