"""
Setup AgentCore Gateways MCP with Lambda targets.
Cria 2 gateways:
  - connect-jwt-gateway: CUSTOM_JWT auth (para Connect AI Agent)
  - harness-mcp-gateway: AWS_IAM auth (para harnesses)

IMPORTANTE: allowedAudience DEVE ser o Gateway ID (nao o instance ID).
Resource policy DEVE usar Principal: * (wildcard) para OAuth/JWT.

Uso: source .env && python3 scripts/setup_gateway.py
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
GW_ROLE = require_env('GATEWAY_ROLE_ARN')
CONNECT_INSTANCE_URL = require_env('CONNECT_INSTANCE_URL')
DISCOVERY_URL = f'{CONNECT_INSTANCE_URL}/.well-known/openid-configuration'

LAMBDA_CURSOS = f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:mcp-catalogo-cursos'
LAMBDA_LOOKUP = f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:connect-user-lookup'
LAMBDA_ACADEMICO = f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:mcp-academico'
LAMBDA_BOLETO = f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:mcp-boleto'
LAMBDA_VESTIBULAR = f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:mcp-vestibular'

agentcore = boto3.client('bedrock-agentcore-control', region_name=REGION)

# Tool schemas compartilhados entre os 2 gateways
TARGETS = [
    {
        'name': 'catalogo-cursos',
        'description': 'Catalogo de cursos de graduacao e extensao da instituicao.',
        'lambdaArn': LAMBDA_CURSOS,
        'tools': [
            {
                'name': 'listar_cursos',
                'description': 'Lista cursos disponiveis. Pode filtrar por area (Tecnologia, Saude, Negocios, Humanas, Design).',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'area': {'type': 'string', 'description': 'Area para filtrar (opcional). Ex: Tecnologia, Saude, Negocios'}
                    }
                }
            },
            {
                'name': 'detalhe_curso',
                'description': 'Detalhes completos de um curso: ementa, grade curricular, diferenciais, mercado de trabalho, mensalidade.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'curso_id': {'type': 'string', 'description': 'ID do curso. Ex: eng-software, ext-ia-aplicada'}
                    },
                    'required': ['curso_id']
                }
            }
        ]
    },
    {
        'name': 'user-lookup',
        'description': 'Consulta dados cadastrais do usuario por telefone ou CPF.',
        'lambdaArn': LAMBDA_LOOKUP,
        'tools': [
            {
                'name': 'consultar_usuario',
                'description': 'Busca usuario pelo telefone (via GSI) ou CPF (via PK). Retorna nome, tipo, status, curso.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'phone': {'type': 'string', 'description': 'Telefone formato +5511999999999'},
                        'cpf': {'type': 'string', 'description': 'CPF formato 123.456.789-00'}
                    }
                }
            }
        ]
    },
    {
        'name': 'academico',
        'description': 'Consulta informacoes academicas do aluno por CPF: disciplinas, notas, provas, historico, financeiro.',
        'lambdaArn': LAMBDA_ACADEMICO,
        'tools': [
            {
                'name': 'consultar_academico',
                'description': 'Consulta informacoes academicas do aluno. Use tipo_consulta para especificar: disciplina (notas e faltas do semestre atual), prova (proximas provas), historico (semestres anteriores com notas e presenca), financeiro (mensalidades com status Pago/Nao pago), ou todos (tudo de uma vez).',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'cpf': {'type': 'string', 'description': 'CPF do aluno formato 123.456.789-00'},
                        'tipo_consulta': {'type': 'string', 'description': 'Tipo: disciplina, prova, historico, financeiro, ou todos'}
                    },
                    'required': ['cpf', 'tipo_consulta']
                }
            }
        ]
    },
    {
        'name': 'boleto',
        'description': 'Gera segunda via de boleto de mensalidade e envia como documento no WhatsApp.',
        'lambdaArn': LAMBDA_BOLETO,
        'tools': [
            {
                'name': 'gerar_boleto',
                'description': 'Gera segunda via de boleto de mensalidade nao paga. Gera PDF fake com codigo de barras e envia como documento no WhatsApp do aluno. Retorna a linha digitavel para copiar e colar. So funciona para mensalidades com status Nao pago.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'cpf': {'type': 'string', 'description': 'CPF do aluno formato 123.456.789-00'},
                        'mes': {'type': 'string', 'description': 'Mes da mensalidade. Ex: Maio/2026, Janeiro/2026'}
                    },
                    'required': ['cpf', 'mes']
                }
            }
        ]
    },
    {
        'name': 'conteudo',
        'description': 'Consulta a base de conhecimento da instituicao. Para alunos, retorna conteudo de disciplinas cursando/cursadas e informacoes publicas. Para nao-alunos, retorna apenas informacoes publicas.',
        'lambdaArn': LAMBDA_VESTIBULAR,
        'tools': [
            {
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
            }
        ]
    }
]


def wait_gateway_ready(gw_id, max_wait=120):
    for i in range(max_wait // 5):
        gw = agentcore.get_gateway(gatewayIdentifier=gw_id)
        if gw.get('status') == 'READY':
            return gw
        time.sleep(5)
    raise Exception(f'Gateway {gw_id} not ready after {max_wait}s')


def create_gateway(name, auth_type, auth_config=None):
    """Cria gateway ou retorna ID se ja existe."""
    try:
        params = {
            'name': name,
            'roleArn': GW_ROLE,
            'protocolType': 'MCP',
            'authorizerType': auth_type,
            'description': f'MCP Gateway ({auth_type})'
        }
        if auth_config:
            params['authorizerConfiguration'] = auth_config
        resp = agentcore.create_gateway(**params)
        gw_id = resp['gatewayId']
        print(f'  Created: {gw_id}')
        return gw_id
    except Exception as e:
        if 'Conflict' in str(type(e)):
            for g in agentcore.list_gateways()['items']:
                if g['name'] == name:
                    print(f'  Exists: {g["gatewayId"]}')
                    return g['gatewayId']
        raise


def add_targets(gw_id):
    """Adiciona targets Lambda ao gateway."""
    for t in TARGETS:
        try:
            agentcore.create_gateway_target(
                gatewayIdentifier=gw_id,
                name=t['name'],
                description=t['description'],
                targetConfiguration={
                    'mcp': {
                        'lambda': {
                            'lambdaArn': t['lambdaArn'],
                            'toolSchema': {'inlinePayload': t['tools']}
                        }
                    }
                },
                credentialProviderConfigurations=[{'credentialProviderType': 'GATEWAY_IAM_ROLE'}]
            )
            print(f'  {t["name"]}: created')
        except Exception as e:
            if 'Conflict' in str(type(e)):
                print(f'  {t["name"]}: exists')
            else:
                print(f'  {t["name"]}: ERROR - {e}')


def add_resource_policy(gw_id, gw_arn):
    """Adiciona resource policy com Principal: * (obrigatorio para JWT)."""
    policy = {
        'Version': '2012-10-17',
        'Statement': [{
            'Effect': 'Allow',
            'Principal': '*',
            'Action': 'bedrock-agentcore:InvokeGateway',
            'Resource': gw_arn
        }]
    }
    try:
        agentcore.put_gateway_resource_policy(
            gatewayIdentifier=gw_id,
            policy=json.dumps(policy)
        )
        print('  Resource policy set (Principal: *)')
    except Exception as e:
        print(f'  Resource policy error: {e}')


# ============================================================
# Gateway 1: CUSTOM_JWT (para Connect AI Agent)
# ============================================================
print('=== Gateway JWT (Connect) ===')

# Nota: allowedAudience sera atualizado apos criacao com o gateway ID
jwt_gw_id = create_gateway('connect-jwt-gateway', 'CUSTOM_JWT', {
    'customJWTAuthorizer': {
        'discoveryUrl': DISCOVERY_URL,
        'allowedAudience': ['placeholder']  # sera atualizado
    }
})

gw = wait_gateway_ready(jwt_gw_id)
gw_arn = gw.get('gatewayArn', gw.get('arn', ''))
print(f'  READY: {jwt_gw_id}')

# Atualizar allowedAudience com o gateway ID
try:
    agentcore.update_gateway(
        gatewayIdentifier=jwt_gw_id,
        authorizerConfiguration={
            'customJWTAuthorizer': {
                'discoveryUrl': DISCOVERY_URL,
                'allowedAudience': [jwt_gw_id]
            }
        }
    )
    print(f'  allowedAudience updated to: [{jwt_gw_id}]')
except Exception as e:
    print(f'  allowedAudience update error: {e}')

# Resource policy
add_resource_policy(jwt_gw_id, gw_arn)

# Tags para Connect
try:
    agentcore.tag_resource(
        resourceArn=gw_arn,
        tags={'AmazonConnectEnabled': 'true', 'owner': ACCOUNT_ID}
    )
    print('  Tags set')
except Exception as e:
    print(f'  Tags error: {e}')

# Targets
print('\n  Targets:')
add_targets(jwt_gw_id)

set_env('GATEWAY_ID', jwt_gw_id)
set_env('GATEWAY_ARN', gw_arn)

# ============================================================
# Gateway 2: AWS_IAM (para Harnesses)
# ============================================================
print('\n=== Gateway IAM (Harnesses) ===')

iam_gw_id = create_gateway('harness-mcp-gateway', 'AWS_IAM')
gw2 = wait_gateway_ready(iam_gw_id)
print(f'  READY: {iam_gw_id}')

print('\n  Targets:')
add_targets(iam_gw_id)

print(f'\nDone!')
print(f'JWT Gateway: {jwt_gw_id} (registrar no Connect console como MCP server)')
print(f'IAM Gateway: {iam_gw_id} (para harnesses)')
print(f'\nPROXIMOS PASSOS (console):')
print(f'1. Connect > Integrations > Add integration > MCP server > selecionar {jwt_gw_id}')
print(f'2. AI Agent > adicionar tools do namespace gateway_{jwt_gw_id}')
print(f'3. Security Profile > permissoes "Sufficient" para os tools')
