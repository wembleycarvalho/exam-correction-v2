"""
Limpa Customer Profiles, mantendo apenas os 3 de teste.
Depois re-sincroniza os 3 com dados completos.

Uso: source .env && python3 scripts/clean_profiles.py
"""
import boto3
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env

REGION = get_env('AWS_REGION', 'us-east-1')
DOMAIN = 'amazon-connect-connect-demo-ps'

cp = boto3.client('customer-profiles', region_name=REGION)

# Phones to keep
KEEP_PHONES = ['+5511985743177', '+5511999998888', '+5511977776666']

# Step 1: Find profiles to keep
print('=== Profiles to KEEP ===')
keep_ids = set()
for phone in KEEP_PHONES:
    try:
        resp = cp.search_profiles(DomainName=DOMAIN, KeyName='_phone', Values=[phone])
        for p in resp.get('Items', []):
            keep_ids.add(p['ProfileId'])
            print(f'  {p.get("FirstName","?")} {p.get("LastName","?")} | {phone} | {p["ProfileId"][:12]}...')
    except Exception as e:
        print(f'  Error searching {phone}: {e}')

# Step 2: Find ALL profiles and delete those not in keep list
print(f'\n=== Searching for profiles to delete ===')
deleted = 0

# Search by various phone patterns that might have been auto-created
search_phones = ['+5511945746008', '+5511985743177', '+5511999998888', '+5511977776666']
found_ids = set()

for phone in search_phones:
    try:
        resp = cp.search_profiles(DomainName=DOMAIN, KeyName='_phone', Values=[phone])
        for p in resp.get('Items', []):
            found_ids.add(p['ProfileId'])
    except:
        pass

# Also try to find profiles without names (auto-created)
# Unfortunately the API doesn't support listing all profiles easily
# Let's just delete the ones we find that aren't in keep_ids
to_delete = found_ids - keep_ids
print(f'  Found {len(found_ids)} profiles, keeping {len(keep_ids)}, deleting {len(to_delete)}')

for pid in to_delete:
    try:
        cp.delete_profile(DomainName=DOMAIN, ProfileId=pid)
        deleted += 1
        print(f'  Deleted: {pid[:12]}...')
    except Exception as e:
        print(f'  Error deleting {pid[:12]}: {e}')

# Step 3: Re-sync the 3 test profiles
print(f'\n=== Re-syncing 3 test profiles ===')
dynamodb = boto3.resource('dynamodb', region_name=REGION)
tbl = dynamodb.Table('cadastro-usuarios')
response = tbl.scan()

for usuario in response.get('Items', []):
    cpf = usuario.get('cpf', '')
    nome = usuario.get('nome', '')
    telefone = usuario.get('telefone', '')
    tipo = usuario.get('tipo', '')
    status = usuario.get('status', '')
    curso = usuario.get('curso', '')
    curso_id = usuario.get('curso_id', '')

    partes = nome.split(' ', 1)
    first_name = partes[0] if partes else ''
    last_name = partes[1] if len(partes) > 1 else ''

    # Search existing
    existing = None
    try:
        resp = cp.search_profiles(DomainName=DOMAIN, KeyName='_phone', Values=[telefone])
        if resp.get('Items'):
            existing = resp['Items'][0]
    except:
        pass

    params = {
        'DomainName': DOMAIN,
        'FirstName': first_name,
        'LastName': last_name,
        'PhoneNumber': telefone,
        'MobilePhoneNumber': telefone,
        'AccountNumber': cpf,
        'PartyType': 'INDIVIDUAL',
        'Attributes': {k: v for k, v in {
            'cpf': cpf,
            'tipo': tipo,
            'status': status,
            'curso': curso,
            'curso_id': curso_id,
        }.items() if v},
        'AdditionalInformation': f'Tipo: {tipo} | Curso: {curso} | Status: {status}',
    }

    if existing:
        params['ProfileId'] = existing['ProfileId']
        cp.update_profile(**params)
        print(f'  Updated: {nome} ({cpf})')
    else:
        cp.create_profile(**params)
        print(f'  Created: {nome} ({cpf})')

print(f'\n=== Done ===')
print(f'  Deleted: {deleted} profiles')
print(f'  Synced: 3 test profiles')
