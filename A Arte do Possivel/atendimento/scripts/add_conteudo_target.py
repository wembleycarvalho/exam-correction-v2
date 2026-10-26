"""
Adiciona target 'conteudo' (consultar_conteudo) aos gateways MCP.
Uso: source .env && python3 scripts/add_conteudo_target.py
"""
import boto3
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env

REGION = get_env('AWS_REGION', 'us-east-1')
ACCOUNT_ID = require_env('AWS_ACCOUNT_ID')
GATEWAY_ID = get_env('GATEWAY_ID', 'connect-mcp-gateway-je8rqivkd1')
LAMBDA_ARN = f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:mcp-vestibular'

agentcore = boto3.client('bedrock-agentcore-control', region_name=REGION)

tools = [{
    'name': 'consultar_conteudo',
    'description': 'Consulta a base de conhecimento da instituicao. Para alunos, retorna conteudo de disciplinas cursando/cursadas e informacoes publicas. Para nao-alunos, retorna apenas informacoes publicas (vestibular, institucional). Passe o CPF do aluno para filtrar o conteudo adequadamente.',
    'inputSchema': {
        'type': 'object',
        'properties': {
            'pergunta': {'type': 'string', 'description': 'Pergunta do usuario'},
            'cpf': {'type': 'string', 'description': 'CPF do aluno (opcional). Se informado, filtra conteudo por disciplinas permitidas.'}
        },
        'required': ['pergunta']
    }
}]

target_config = {
    'mcp': {
        'lambda': {
            'lambdaArn': LAMBDA_ARN,
            'toolSchema': {'inlinePayload': tools}
        }
    }
}
cred_config = [{'credentialProviderType': 'GATEWAY_IAM_ROLE'}]

# JWT Gateway (Connect)
print(f'JWT Gateway: {GATEWAY_ID}')
try:
    agentcore.create_gateway_target(
        gatewayIdentifier=GATEWAY_ID,
        name='conteudo',
        description='Consulta KB com controle de acesso por metadata.',
        targetConfiguration=target_config,
        credentialProviderConfigurations=cred_config
    )
    print('  conteudo: created')
except Exception as e:
    if 'Conflict' in str(type(e)) or 'Conflict' in str(e):
        print('  conteudo: already exists')
    else:
        print(f'  ERROR: {e}')

# IAM Gateway (Harnesses)
gws = agentcore.list_gateways()
for g in gws.get('items', []):
    if g['name'] == 'harness-mcp-gateway':
        iam_gw_id = g['gatewayId']
        print(f'IAM Gateway: {iam_gw_id}')
        try:
            agentcore.create_gateway_target(
                gatewayIdentifier=iam_gw_id,
                name='conteudo',
                description='Consulta KB com controle de acesso por metadata.',
                targetConfiguration=target_config,
                credentialProviderConfigurations=cred_config
            )
            print('  conteudo: created')
        except Exception as e:
            if 'Conflict' in str(type(e)) or 'Conflict' in str(e):
                print('  conteudo: already exists')
            else:
                print(f'  ERROR: {e}')
        break

print('Done!')
