"""
Fundacao da campanha nativa (Customer event via put_profile_object) - nao-destrutivo:
  1. Bucket dedicado para CSVs de campanha (privado, sem lifecycle).
  2. Object type custom 'Campaign-WhatsApp' no Customer Profiles (mapa CSV->perfil; chave=telefone).
     Escrever um objeto desse tipo gera o evento que dispara a campanha (event trigger).

O event trigger + a campanha em si sao criados na aprovacao do template (campaign_setup.py).

Uso: source .env && python3 scripts/setup_campaign_native.py
"""
import boto3, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env, set_env

REGION = get_env('AWS_REGION', 'us-east-1')
ACCOUNT = require_env('AWS_ACCOUNT_ID')
DOMAIN = 'amazon-connect-connect-demo-ps'
BUCKET = f'campanhas-connect-{ACCOUNT}'
OBJECT_TYPE = 'Campaign-WhatsApp'

s3 = boto3.client('s3', region_name=REGION)
cp = boto3.client('customer-profiles', region_name=REGION)

# 1. bucket dedicado (privado)
print(f'=== S3: {BUCKET} ===')
try:
    s3.create_bucket(Bucket=BUCKET)
    print('  criado')
except s3.exceptions.BucketAlreadyOwnedByYou:
    print('  ja existe')
except Exception as e:
    if 'BucketAlreadyExists' in str(e): print('  ja existe')
    else: raise
s3.put_public_access_block(Bucket=BUCKET, PublicAccessBlockConfiguration={
    'BlockPublicAcls': True, 'IgnorePublicAcls': True,
    'BlockPublicPolicy': True, 'RestrictPublicBuckets': True})
print('  public access bloqueado (sem lifecycle de expiracao)')
set_env('CAMPAIGN_BUCKET', BUCKET)

# 2. object type Campaign-WhatsApp
print(f'\n=== Customer Profiles object type: {OBJECT_TYPE} ===')
fields = {
    'phone':     {'Source': '_source.phone',     'Target': '_profile.PhoneNumber', 'ContentType': 'PHONE_NUMBER'},
    'firstName': {'Source': '_source.FirstName', 'Target': '_profile.FirstName'},
    'lastName':  {'Source': '_source.LastName',  'Target': '_profile.LastName'},
    'curso':     {'Source': '_source.curso',     'Target': '_profile.Attributes.curso'},
    'protocolo': {'Source': '_source.protocolo', 'Target': '_profile.Attributes.protocolo'},
    'mes':       {'Source': '_source.mes',       'Target': '_profile.Attributes.mes'},
}
keys = {
    '_phone': [{'StandardIdentifiers': ['PROFILE', 'UNIQUE'], 'FieldNames': ['phone']}],
}
cp.put_profile_object_type(
    DomainName=DOMAIN,
    ObjectTypeName=OBJECT_TYPE,
    Description='Objetos de campanha WhatsApp - disparo fiel ao CSV (Customer event)',
    AllowProfileCreation=True,
    Fields=fields,
    Keys=keys,
)
print('  object type criado/atualizado (chave=telefone, cria perfil se nao existir)')
set_env('CAMPAIGN_OBJECT_TYPE', OBJECT_TYPE)

print('\n=== FUNDACAO PRONTA ===')
print(f'  bucket:      {BUCKET}')
print(f'  object type: {OBJECT_TYPE}')
print('Disparo (fiel ao CSV): scripts/campaign_load_profiles.py escreve objetos desse tipo.')
print('Falta (na aprovacao do template): event trigger + campanha (campaign_setup.py).')
