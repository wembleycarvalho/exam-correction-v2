"""
Deploy all Lambda functions.
Uso: source .env && python3 scripts/setup_lambdas.py
"""
import boto3
import zipfile
import io
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env

REGION = get_env('AWS_REGION', 'us-east-1')
ACCOUNT_ID = require_env('AWS_ACCOUNT_ID')
INSTANCE_ID = require_env('CONNECT_INSTANCE_ID')
LAYER_ARN = get_env('BOTO3_LAYER_ARN')

if not LAYER_ARN:
    print('WARNING: BOTO3_LAYER_ARN not set. Run setup_boto3_layer.py first.')
    print('Lambdas that need invoke_harness will fail without it.\n')

lmb = boto3.client('lambda', region_name=REGION)
connect = boto3.client('connect', region_name=REGION)

REPORTLAB_LAYER = get_env('REPORTLAB_LAYER_ARN')
S3_BUCKET_BOLETOS = get_env('S3_BUCKET_BOLETOS', '')
WHATSAPP_PHONE_ID = get_env('WHATSAPP_PHONE_NUMBER_ID', '')

lambdas = {
    'mcp-catalogo-cursos': {'file': 'lambdas/mcp_catalogo_cursos.py', 'role': 'LambdaMCPCursosRole', 'timeout': 30, 'memory': 128, 'needs_layer': False},
    'connect-user-lookup': {'file': 'lambdas/connect_user_lookup.py', 'role': 'LexFulfillmentLambdaRole', 'timeout': 10, 'memory': 128, 'needs_layer': False},
    'mcp-academico': {'file': 'lambdas/mcp_academico.py', 'role': 'LambdaMCPCursosRole', 'timeout': 30, 'memory': 128, 'needs_layer': False},
    'mcp-boleto': {'file': 'lambdas/mcp_boleto.py', 'role': 'LambdaBoletoRole', 'timeout': 30, 'memory': 256, 'needs_layer': False, 'layer': REPORTLAB_LAYER, 'env': {'S3_BUCKET_BOLETOS': S3_BUCKET_BOLETOS, 'WHATSAPP_PHONE_NUMBER_ID': WHATSAPP_PHONE_ID}},
    'connect-harness-integration': {'file': 'lambdas/connect_harness_integration.py', 'role': 'ConnectHarnessLambdaRole', 'timeout': 120, 'memory': 256, 'needs_layer': True},
    'connect-harness-async': {'file': 'lambdas/connect_harness_async.py', 'role': 'ConnectHarnessLambdaRole', 'timeout': 120, 'memory': 256, 'needs_layer': True},
    'lex-harness-fulfillment': {'file': 'lambdas/lex_harness_fulfillment.py', 'role': 'LexFulfillmentLambdaRole', 'timeout': 120, 'memory': 256, 'needs_layer': True},
    'mcp-vestibular': {'file': 'lambdas/mcp_vestibular.py', 'role': 'LambdaMCPCursosRole', 'timeout': 30, 'memory': 128, 'needs_layer': False, 'env': {'KB_VESTIBULAR_ID': get_env('KB_VESTIBULAR_ID', 'ECCHPIL4ZK')}},
}

for name, config in lambdas.items():
    if not os.path.exists(config['file']):
        print(f'{name}: SKIP (file not found)')
        continue

    role_arn = f'arn:aws:iam::{ACCOUNT_ID}:role/{config["role"]}'
    layers = []
    if config['needs_layer'] and LAYER_ARN:
        layers.append(LAYER_ARN)
    if config.get('layer'):
        layers.append(config['layer'])

    env_vars = config.get('env', {})

    with open(config['file'], 'r') as f:
        code = f.read()

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('lambda_function.py', code)
    zip_buf.seek(0)

    create_params = {
        'FunctionName': name, 'Runtime': 'python3.12', 'Role': role_arn,
        'Handler': 'lambda_function.lambda_handler',
        'Code': {'ZipFile': zip_buf.read()},
        'Timeout': config['timeout'], 'MemorySize': config['memory'],
        'Layers': layers
    }
    if env_vars:
        create_params['Environment'] = {'Variables': env_vars}

    try:
        lmb.create_function(**create_params)
        print(f'{name}: created')
    except lmb.exceptions.ResourceConflictException:
        zip_buf.seek(0)
        lmb.update_function_code(FunctionName=name, ZipFile=zip_buf.read())
        if env_vars or layers:
            import time
            # Wait for code update to finish before updating config
            waiter = lmb.get_waiter('function_updated')
            waiter.wait(FunctionName=name, WaiterConfig={'Delay': 3, 'MaxAttempts': 20})
            lmb.update_function_configuration(FunctionName=name, Environment={'Variables': env_vars}, Layers=layers)
        print(f'{name}: updated')

    for stmt, principal in [('AllowConnect', 'connect.amazonaws.com'), ('AllowAgentCore', 'bedrock-agentcore.amazonaws.com')]:
        try:
            lmb.add_permission(FunctionName=name, StatementId=stmt, Action='lambda:InvokeFunction', Principal=principal, SourceAccount=ACCOUNT_ID)
        except lmb.exceptions.ResourceConflictException:
            pass

    try:
        connect.associate_lambda_function(InstanceId=INSTANCE_ID, FunctionArn=f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{name}')
    except Exception:
        pass

print('\nDone!')
