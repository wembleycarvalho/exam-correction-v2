"""
Sincroniza dados do DynamoDB cadastro-usuarios para o Amazon Connect Customer Profiles.
Popula nome, telefone, CPF, tipo, curso e status para que o atendente humano
veja os dados do cliente no CCP quando receber um escalate.

Uso: source .env && python3 scripts/sync_customer_profiles.py
"""
import boto3
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env

REGION = get_env('AWS_REGION', 'us-east-1')
DOMAIN_NAME = 'amazon-connect-connect-demo-ps'

dynamodb = boto3.resource('dynamodb', region_name=REGION)
cp = boto3.client('customer-profiles', region_name=REGION)

tbl_usuarios = dynamodb.Table('cadastro-usuarios')


def sync_profile(usuario):
    """Cria ou atualiza um perfil no Customer Profiles a partir dos dados do DynamoDB."""
    cpf = usuario.get('cpf', '')
    nome = usuario.get('nome', '')
    telefone = usuario.get('telefone', '')
    tipo = usuario.get('tipo', '')
    status = usuario.get('status', '')
    curso = usuario.get('curso', '')
    curso_id = usuario.get('curso_id', '')

    # Separar nome em first/last
    partes = nome.split(' ', 1)
    first_name = partes[0] if partes else ''
    last_name = partes[1] if len(partes) > 1 else ''

    # Buscar perfil existente pelo telefone
    existing = None
    try:
        search = cp.search_profiles(
            DomainName=DOMAIN_NAME,
            KeyName='_phone',
            Values=[telefone]
        )
        items = search.get('Items', [])
        if items:
            existing = items[0]
    except Exception as e:
        print(f'  Erro ao buscar perfil: {e}')

    profile_params = {
        'DomainName': DOMAIN_NAME,
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
        # Update
        profile_id = existing['ProfileId']
        profile_params['ProfileId'] = profile_id
        cp.update_profile(**profile_params)
        print(f'  {nome} ({cpf}): atualizado (ProfileId: {profile_id})')
    else:
        # Create
        resp = cp.create_profile(**profile_params)
        profile_id = resp['ProfileId']
        print(f'  {nome} ({cpf}): criado (ProfileId: {profile_id})')

    return profile_id


def main():
    print('=== Sync DynamoDB -> Customer Profiles ===')
    print(f'  Domain: {DOMAIN_NAME}')
    print()

    # Scan all users from DynamoDB
    response = tbl_usuarios.scan()
    usuarios = response.get('Items', [])

    print(f'  {len(usuarios)} usuarios encontrados no DynamoDB')
    print()

    synced = 0
    errors = 0

    for usuario in usuarios:
        try:
            sync_profile(usuario)
            synced += 1
        except Exception as e:
            nome = usuario.get('nome', '?')
            print(f'  ERRO {nome}: {e}')
            errors += 1

    print(f'\n=== Resultado ===')
    print(f'  Sincronizados: {synced}')
    print(f'  Erros: {errors}')
    print(f'  Total: {len(usuarios)}')


if __name__ == '__main__':
    main()
