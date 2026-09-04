"""
Setup idempotente do Painel de Briefing do Atendente (Screen Pop).

Recria/atualiza toda a infraestrutura:
1. Bucket S3 de fotos (privado) + Lambda mcp-foto-cliente
2. Lambda connect-agent-briefing (resumo via transcript + Bedrock)
3. IAM Roles com permissoes
4. Custom View briefing-atendente
5. Fluxo separado agent-briefing-screen-pop (com Show View)
6. Modifica o fluxo principal: invoke lambda -> set attrs -> event hook (DefaultAgentUI)
7. Atualiza o AI Agent (Escalate tool schema) e o prompt

PRE-REQUISITOS MANUAIS (console do Connect):
- UI Management > Workspaces > criar workspace e adicionar page tipo Guide com a view
- Security Profile > Agent Applications > habilitar acesso

Uso: source .env && python3 scripts/setup_agent_briefing.py
"""
import boto3
import json
import os
import sys
import time
import zipfile
import io
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env, set_env

REGION = get_env('AWS_REGION', 'us-east-1')
ACCOUNT_ID = require_env('AWS_ACCOUNT_ID')
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
MAIN_FLOW_ID = 'acd511ac-afee-403b-9436-aa52f2f744cc'
ASSISTANT_ID = get_env('ASSISTANT_ID', '4c588966-3671-4170-b53d-a6115502e9d1')
AGENT_ID = '9fe5ed34-f493-44a5-817e-85c912116f71'
PROMPT_ID = '51dff123-b8fd-4d8c-8915-2963041f2804'
COPILOTO_ID = '7fa94e88-27ea-4082-acf6-614909e8c88c'

FOTOS_BUCKET = f'fotos-clientes-{ACCOUNT_ID}'

connect = boto3.client('connect', region_name=REGION)
lmb = boto3.client('lambda', region_name=REGION)
iam = boto3.client('iam', region_name=REGION)

LAMBDADIR = os.path.join(os.path.dirname(__file__), '..', 'lambdas')


def zip_lambda(py_file):
    with open(os.path.join(LAMBDADIR, py_file)) as f:
        code = f.read()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('lambda_function.py', code)
    buf.seek(0)
    return buf.read()


def ensure_role(role_name, policy_doc, description):
    trust = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]
    }
    try:
        iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust), Description=description)
        print(f'   Role criada: {role_name}')
        time.sleep(8)
    except iam.exceptions.EntityAlreadyExistsException:
        print(f'   Role ja existe: {role_name}')
    iam.put_role_policy(RoleName=role_name, PolicyName=f'{role_name}Policy', PolicyDocument=json.dumps(policy_doc))
    return f'arn:aws:iam::{ACCOUNT_ID}:role/{role_name}'


def deploy_lambda(name, py_file, role_arn, env, timeout=30, memory=256):
    code = zip_lambda(py_file)
    try:
        lmb.create_function(
            FunctionName=name, Runtime='python3.12', Role=role_arn,
            Handler='lambda_function.lambda_handler', Code={'ZipFile': code},
            Timeout=timeout, MemorySize=memory, Environment={'Variables': env}
        )
        print(f'   Lambda criada: {name}')
    except lmb.exceptions.ResourceConflictException:
        lmb.update_function_code(FunctionName=name, ZipFile=code)
        time.sleep(3)
        lmb.update_function_configuration(FunctionName=name, Environment={'Variables': env}, Timeout=timeout, MemorySize=memory)
        print(f'   Lambda atualizada: {name}')
    arn = f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{name}'
    try:
        lmb.add_permission(FunctionName=name, StatementId='AllowConnect', Action='lambda:InvokeFunction',
                           Principal='connect.amazonaws.com', SourceAccount=ACCOUNT_ID)
    except lmb.exceptions.ResourceConflictException:
        pass
    return arn


# ============================================================
print('=== Setup Painel de Briefing do Atendente ===\n')

# Step 1: Briefing Lambda Role
print('1. IAM Role: LambdaAgentBriefingRole')
briefing_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": f"arn:aws:s3:::{FOTOS_BUCKET}/*"},
        {"Effect": "Allow", "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], "Resource": "arn:aws:logs:*:*:*"},
        {"Effect": "Allow", "Action": ["dynamodb:GetItem", "dynamodb:Query"], "Resource": [
            f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/cadastro-usuarios",
            f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/cadastro-usuarios/index/*",
            f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/academico"]},
        {"Effect": "Allow", "Action": ["bedrock:InvokeModel"], "Resource": "*"},
        {"Effect": "Allow", "Action": ["connect:GetContactAttributes", "connect:ListRealtimeContactAnalysisSegmentsV2"], "Resource": "*"}
    ]
}
briefing_role = ensure_role('LambdaAgentBriefingRole', briefing_policy, 'Lambda briefing do atendente')

# Step 2: Deploy briefing lambda
print('\n2. Lambda: connect-agent-briefing')
briefing_arn = deploy_lambda('connect-agent-briefing', 'connect_agent_briefing.py', briefing_role,
                             {'FOTOS_BUCKET': FOTOS_BUCKET, 'CONNECT_INSTANCE_ID': INSTANCE_ID})

# Step 3: Custom View
print('\n3. Custom View: briefing-atendente')
view_template = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'config', 'view_briefing_template.json'))) \
    if os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'config', 'view_briefing_template.json')) else None

# Find existing view
view_id = None
for v in connect.list_views(InstanceId=INSTANCE_ID).get('ViewsSummaryList', []):
    if v['Name'] == 'briefing-atendente':
        view_id = v['Id']
        break
if view_id:
    print(f'   View ja existe: {view_id}')
else:
    print('   ATENCAO: View nao encontrada. Restaure de backups/briefing_setup_*/view_briefing-atendente.json')
    print('   ou crie manualmente. Pulando criacao automatica da view.')

set_env('BRIEFING_LAMBDA_ARN', briefing_arn)
if view_id:
    set_env('BRIEFING_VIEW_ID', view_id)

print('\n=== Setup parcial completo ===')
print('''
Componentes gerenciados por este script:
  - LambdaAgentBriefingRole (+ permissoes Contact Lens, Bedrock, S3, DynamoDB)
  - connect-agent-briefing (resumo via transcript)

Componentes que devem ser restaurados do backup se necessario:
  - View briefing-atendente -> backups/briefing_setup_*/view_briefing-atendente.json
  - Fluxo agent-briefing-screen-pop -> backups/briefing_setup_*/flow_agent-briefing-screen-pop.json
  - Fluxo principal (event hook) -> backups/briefing_setup_*/flow_main_*.json
  - AI Agent config (Escalate schema) -> backups/briefing_setup_*/ai-agent_orchestration_config.json
  - Prompt -> backups/briefing_setup_*/prompt-nova_v2.yaml

Use scripts/restore_briefing_setup.py <backup_dir> para restaurar fluxos/view/agent.

PASSO MANUAL (console): UI Management > Workspaces e Security Profile > Agent Applications.
''')
