"""
Setup completo do ambiente.
Cria o .env com todos os IDs necessarios e executa os scripts de setup na ordem correta.

Pre-requisitos:
- AWS credentials configuradas (via aws configure, env vars ou .env com AWS_ACCESS_KEY_ID etc)
- Python 3.10+ com boto3 e pyyaml instalados
- Acesso a us-east-1

Uso:
  python3 setup.py                          # Setup interativo (pergunta os dados)
  python3 setup.py --discover               # Descobre recursos existentes e gera .env
  source .env && python3 setup.py --run     # Executa todos os scripts de setup
"""
import boto3
import json
import os
import sys
import subprocess

REGION = os.environ.get('AWS_REGION', 'us-east-1')


def get_account_id():
    sts = boto3.client('sts', region_name=REGION)
    return sts.get_caller_identity()['Account']


def discover_resources():
    """Descobre recursos existentes na conta e retorna dict com valores pro .env."""
    print('Descobrindo recursos existentes...\n')
    env = {}
    account_id = get_account_id()
    env['AWS_ACCOUNT_ID'] = account_id
    env['AWS_REGION'] = REGION
    print(f'  Account: {account_id}')

    # Connect instance
    print('\n--- Amazon Connect ---')
    connect = boto3.client('connect', region_name=REGION)
    instances = connect.list_instances()['InstanceSummaryList']
    if len(instances) == 1:
        inst = instances[0]
    else:
        print('  Instancias disponiveis:')
        for i, inst in enumerate(instances):
            print(f'    [{i}] {inst.get("InstanceAlias", "N/A")} ({inst["Id"]})')
        choice = input('  Escolha o numero da instancia: ')
        inst = instances[int(choice)]

    env['CONNECT_INSTANCE_ID'] = inst['Id']
    env['CONNECT_INSTANCE_URL'] = inst.get('InstanceAccessUrl', f'https://{inst.get("InstanceAlias", "")}.my.connect.aws')
    print(f'  Instance: {inst.get("InstanceAlias")} ({inst["Id"]})')

    # Connect flow
    flows = connect.list_contact_flows(InstanceId=inst['Id'], ContactFlowTypes=['CONTACT_FLOW'])
    whatsapp_flows = [f for f in flows['ContactFlowSummaryList'] if 'whatsapp' in f['Name'].lower()]
    if whatsapp_flows:
        env['CONNECT_FLOW_ID'] = whatsapp_flows[0]['Id']
        print(f'  WhatsApp Flow: {whatsapp_flows[0]["Name"]} ({whatsapp_flows[0]["Id"]})')

    # Connect queue
    queues = connect.list_queues(InstanceId=inst['Id'], QueueTypes=['STANDARD'])
    if queues['QueueSummaryList']:
        q = queues['QueueSummaryList'][0]
        env['CONNECT_QUEUE_ARN'] = q['Arn']
        print(f'  Queue: {q["Name"]}')

    # Wisdom/QConnect assistant
    resp = connect.list_integration_associations(InstanceId=inst['Id'])
    for assoc in resp['IntegrationAssociationSummaryList']:
        if assoc['IntegrationType'] == 'WISDOM_ASSISTANT':
            env['ASSISTANT_ID'] = assoc['IntegrationArn'].split('/')[-1]
            print(f'  Assistant: {env["ASSISTANT_ID"]}')

    # Lex bot
    try:
        bots = connect.list_bots(InstanceId=inst['Id'], LexVersion='V2')
        for b in bots.get('LexBots', []):
            lex_arn = b.get('LexV2Bot', {}).get('AliasArn', '')
            if lex_arn:
                env['LEX_BOT_ARN'] = lex_arn
                print(f'  Lex Bot: {lex_arn}')
    except Exception:
        pass

    # AgentCore harnesses
    print('\n--- Bedrock AgentCore ---')
    try:
        agentcore = boto3.client('bedrock-agentcore-control', region_name=REGION)
        harnesses = agentcore.list_harnesses()['harnesses']
        for h in harnesses:
            print(f'  Harness: {h["harnessName"]} ({h["harnessId"]})')
            if h['harnessName'] == 'harness_871f8':
                env['HARNESS_871F8_ARN'] = h['arn']

        # Execution role (from first harness)
        if harnesses:
            detail = agentcore.get_harness(harnessId=harnesses[0]['harnessId'])
            exec_role = detail['harness'].get('executionRoleArn', '')
            if exec_role:
                env['HARNESS_EXEC_ROLE_ARN'] = exec_role
                print(f'  Exec Role: {exec_role.split("/")[-1]}')

            # Memory
            memory = detail['harness'].get('memory', {})
            mem_config = memory.get('agentCoreMemoryConfiguration', {})
            if mem_config.get('arn'):
                env['HARNESS_MEMORY_ARN'] = mem_config['arn']
                print(f'  Memory: {mem_config["arn"].split("/")[-1]}')

        # If no memory found from harness, search directly
        if 'HARNESS_MEMORY_ARN' not in env:
            try:
                memories = agentcore.list_memories() if hasattr(agentcore, 'list_memories') else None
                # Try getting memory from any harness
                for h in harnesses:
                    detail = agentcore.get_harness(harnessId=h['harnessId'])
                    mem = detail['harness'].get('memory', {}).get('agentCoreMemoryConfiguration', {})
                    if mem.get('arn'):
                        env['HARNESS_MEMORY_ARN'] = mem['arn']
                        print(f'  Memory (from {h["harnessName"]}): {mem["arn"].split("/")[-1]}')
                        break
            except Exception:
                pass

        # Gateway
        gateways = agentcore.list_gateways()['items']
        for g in gateways:
            if 'connect' in g['name'].lower() or 'mcp' in g['name'].lower():
                env['GATEWAY_ID'] = g['gatewayId']
                env['GATEWAY_ROLE_ARN'] = f'arn:aws:iam::{account_id}:role/AgentCoreGatewayRole'
                print(f'  Gateway: {g["name"]} ({g["gatewayId"]})')
    except Exception as e:
        print(f'  AgentCore error: {e}')

    # Cognito
    print('\n--- Cognito ---')
    try:
        cognito = boto3.client('cognito-idp', region_name=REGION)
        pools = cognito.list_user_pools(MaxResults=20)['UserPools']
        for p in pools:
            if 'harness' in p['Name'].lower() or 'agent-pool' in p['Name'].lower():
                env['COGNITO_POOL_ID'] = p['Id']
                print(f'  Pool: {p["Name"]} ({p["Id"]})')

                # Get client
                clients = cognito.list_user_pool_clients(UserPoolId=p['Id'], MaxResults=5)['UserPoolClients']
                if clients:
                    env['COGNITO_CLIENT_ID'] = clients[0]['ClientId']
                    print(f'  Client: {clients[0]["ClientName"]} ({clients[0]["ClientId"]})')

                # Get user
                users = cognito.list_users(UserPoolId=p['Id'], Limit=5)['Users']
                if users:
                    env['COGNITO_USERNAME'] = users[0]['Username']
                    print(f'  User: {users[0]["Username"]}')

                env['COGNITO_PASSWORD'] = '<SET_MANUALLY>'
                break
    except Exception as e:
        print(f'  Cognito error: {e}')

    # WhatsApp
    print('\n--- WhatsApp ---')
    try:
        sm = boto3.client('socialmessaging', region_name=REGION)
        wabas = sm.list_linked_whatsapp_business_accounts()['linkedAccounts']
        if wabas:
            waba = wabas[0]
            env['WABA_ID'] = waba['id']
            print(f'  WABA: {waba["wabaName"]} ({waba["id"]})')

            detail = sm.get_linked_whatsapp_business_account(id=waba['id'])
            for pn in detail['account'].get('phoneNumbers', []):
                if pn.get('qualityRating') == 'GREEN' or '+55' in pn.get('phoneNumber', ''):
                    env['WHATSAPP_PHONE_NUMBER_ID'] = pn['phoneNumberId']
                    env['WHATSAPP_SOURCE_PHONE_ARN'] = pn['arn']
                    print(f'  Phone: {pn["phoneNumber"]} ({pn["phoneNumberId"]})')
                    break
    except Exception as e:
        print(f'  WhatsApp error: {e}')

    return env


def write_env(env, filepath='.env'):
    """Escreve o .env preservando credenciais AWS existentes."""
    existing = {}
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('export ') and '=' in line:
                    key = line.split('=', 1)[0].replace('export ', '')
                    val = line.split('=', 1)[1]
                    existing[key] = val

    # Merge: keep existing AWS creds, update everything else
    for key in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN']:
        if key in existing:
            env[key] = existing[key]

    # Keep manually set password if exists
    if 'COGNITO_PASSWORD' in existing and existing['COGNITO_PASSWORD'] != '<SET_MANUALLY>':
        env['COGNITO_PASSWORD'] = existing['COGNITO_PASSWORD']

    with open(filepath, 'w') as f:
        f.write('# Auto-generated by setup.py\n')
        f.write('# AWS Credentials\n')
        for key in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN']:
            if key in env:
                f.write(f'export {key}={env[key]}\n')

        f.write('\n# AWS Account\n')
        for key in ['AWS_ACCOUNT_ID', 'AWS_REGION']:
            if key in env:
                f.write(f'export {key}={env[key]}\n')

        f.write('\n# Amazon Connect\n')
        for key in ['CONNECT_INSTANCE_ID', 'CONNECT_INSTANCE_URL', 'CONNECT_FLOW_ID', 'CONNECT_QUEUE_ARN']:
            if key in env:
                f.write(f'export {key}={env[key]}\n')

        f.write('\n# Bedrock AgentCore\n')
        for key in ['HARNESS_EXEC_ROLE_ARN', 'HARNESS_MEMORY_ARN', 'HARNESS_871F8_ARN']:
            if key in env:
                f.write(f'export {key}={env[key]}\n')

        f.write('\n# Cognito\n')
        for key in ['COGNITO_POOL_ID', 'COGNITO_CLIENT_ID', 'COGNITO_USERNAME', 'COGNITO_PASSWORD']:
            if key in env:
                f.write(f'export {key}={env[key]}\n')

        f.write('\n# WhatsApp\n')
        for key in ['WABA_ID', 'WHATSAPP_PHONE_NUMBER_ID', 'WHATSAPP_SOURCE_PHONE_ARN']:
            if key in env:
                f.write(f'export {key}={env[key]}\n')

        f.write('\n# Gateway MCP\n')
        for key in ['GATEWAY_ROLE_ARN', 'GATEWAY_ID']:
            if key in env:
                f.write(f'export {key}={env[key]}\n')

        f.write('\n# QConnect\n')
        for key in ['ASSISTANT_ID', 'LEX_BOT_ARN']:
            if key in env:
                f.write(f'export {key}={env[key]}\n')

    print(f'\n.env salvo em {filepath}')


def run_scripts():
    """Executa todos os scripts de setup na ordem correta."""
    scripts = [
        ('scripts/setup_iam.py', 'IAM Roles e Policies'),
        ('scripts/setup_dynamodb.py', 'DynamoDB Tables'),
        ('scripts/setup_boto3_layer.py', 'Lambda Layer (boto3)'),
        ('scripts/setup_lambdas.py', 'Lambda Functions'),
        ('scripts/setup_harnesses.py', 'AgentCore Harnesses'),
        ('scripts/setup_gateway.py', 'AgentCore Gateway MCP'),
    ]

    for script, desc in scripts:
        print(f'\n{"="*60}')
        print(f'  {desc} ({script})')
        print(f'{"="*60}')

        if not os.path.exists(script):
            print(f'  SKIP: {script} not found')
            continue

        # Reload .env before each script (previous script may have updated it)
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('export ') and '=' in line:
                        key, val = line.replace('export ', '', 1).split('=', 1)
                        os.environ[key] = val

        result = subprocess.run(
            ['python3', script],
            env={**os.environ},
            capture_output=False
        )

        if result.returncode != 0:
            resp = input(f'\n  ERRO no {script}! Continuar? (s/n) ')
            if resp.strip().lower() != 's':
                print('Setup interrompido.')
                sys.exit(1)

    print(f'\n{"="*60}')
    print('  SETUP AUTOMATIZADO COMPLETO')
    print(f'{"="*60}')
    print('\nPassos manuais restantes (ver docs/SETUP.md):')
    print('  1. Console AWS > Connect > Integrations > Add integration > MCP server')
    print('  2. Console Connect > AI Agents > Create (Orchestration from SelfServiceOrchestrator)')
    print('  3. Adicionar MCP tools ao AI Agent')
    print('  4. Definir como default Self Service agent')


if __name__ == '__main__':
    if '--discover' in sys.argv:
        env = discover_resources()
        write_env(env)
        print('\nAgora execute: source .env && python3 setup.py --run')

    elif '--run' in sys.argv:
        # Verify .env is loaded
        if not os.environ.get('AWS_ACCOUNT_ID'):
            print('Erro: .env nao carregado. Execute: source .env && python3 setup.py --run')
            sys.exit(1)
        run_scripts()

    else:
        print('Setup completo do ambiente\n')
        print('Passo 1: Descobrir recursos e gerar .env')
        print('  python3 setup.py --discover\n')
        print('Passo 2: Revisar e ajustar o .env (especialmente COGNITO_PASSWORD)')
        print('  vi .env\n')
        print('Passo 3: Executar setup automatizado')
        print('  source .env && python3 setup.py --run\n')
        print('Passo 4: Configuracao manual no console (ver docs/SETUP.md)')
