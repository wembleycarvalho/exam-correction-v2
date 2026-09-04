"""
Deploy das Lambdas de voz (idempotente):
  - wpp-gateway-inbound  (SNS whatsapp-inbound)     layers: ffmpeg + voice-deps
  - wpp-gateway-outbound (SNS whatsapp-connect-streaming) layers: ffmpeg

Cria/atualiza funcao, env vars, layers, subscriptions SNS e permissoes de invoke.

Uso: source .env && python3 scripts/deploy_voice_lambdas.py
Requer infra (setup_voice_infra.py) e layers (setup_voice_layers.py) ja criadas.
"""
import boto3
import os
import sys
import io
import time
import zipfile

sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env

REGION = get_env('AWS_REGION', 'us-east-1')
ACCOUNT_ID = require_env('AWS_ACCOUNT_ID')

INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
FLOW_ID = 'acd511ac-afee-403b-9436-aa52f2f744cc'

ROLE_ARN = require_env('WPP_GATEWAY_ROLE_ARN')
SESSIONS_TABLE = get_env('SESSIONS_TABLE', 'whatsapp-connect-sessions')
MEDIA_BUCKET = require_env('MEDIA_BUCKET')
INBOUND_TOPIC_ARN = require_env('WPP_INBOUND_TOPIC_ARN')
STREAMING_TOPIC_ARN = require_env('WPP_STREAMING_TOPIC_ARN')
FFMPEG_LAYER_ARN = require_env('FFMPEG_LAYER_ARN')
VOICE_DEPS_LAYER_ARN = require_env('VOICE_DEPS_LAYER_ARN')

LAMBDAS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lambdas')

lam = boto3.client('lambda', region_name=REGION)
sns = boto3.client('sns', region_name=REGION)


def make_zip(src_file):
    """Zipa o .py como lambda_function.py."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(LAMBDAS_DIR, src_file), 'lambda_function.py')
    buf.seek(0)
    return buf.read()


def deploy(name, src_file, env, layers, timeout, memory):
    code = make_zip(src_file)
    config = dict(
        Role=ROLE_ARN,
        Handler='lambda_function.lambda_handler',
        Runtime='python3.12',
        Timeout=timeout,
        MemorySize=memory,
        Environment={'Variables': env},
        Layers=layers,
    )
    try:
        lam.get_function(FunctionName=name)
        exists = True
    except lam.exceptions.ResourceNotFoundException:
        exists = False

    if exists:
        print(f'  atualizando {name}...')
        lam.update_function_code(FunctionName=name, ZipFile=code, Architectures=['x86_64'])
        _wait_updated(name)
        lam.update_function_configuration(FunctionName=name, **config)
        _wait_updated(name)
    else:
        print(f'  criando {name}...')
        for attempt in range(5):
            try:
                lam.create_function(
                    FunctionName=name, Code={'ZipFile': code},
                    Architectures=['x86_64'], PackageType='Zip', **config)
                break
            except lam.exceptions.InvalidParameterValueException as e:
                # role recem-criada pode nao ter propagado
                if 'cannot be assumed' in str(e) or 'role' in str(e).lower():
                    print(f'    role ainda propagando, retry {attempt+1}/5...')
                    time.sleep(6)
                else:
                    raise
        _wait_updated(name)
    arn = lam.get_function(FunctionName=name)['Configuration']['FunctionArn']
    print(f'  {name}: {arn}')
    return arn


def _wait_updated(name):
    for _ in range(30):
        st = lam.get_function_configuration(FunctionName=name)
        if st.get('LastUpdateStatus') != 'InProgress' and st.get('State') != 'Pending':
            return
        time.sleep(2)


def subscribe(topic_arn, fn_arn, fn_name, sid):
    # permissao pro SNS invocar a lambda
    try:
        lam.add_permission(
            FunctionName=fn_name, StatementId=sid, Action='lambda:InvokeFunction',
            Principal='sns.amazonaws.com', SourceArn=topic_arn)
    except lam.exceptions.ResourceConflictException:
        pass
    # evita subscription duplicada
    existing = sns.list_subscriptions_by_topic(TopicArn=topic_arn)['Subscriptions']
    for s in existing:
        if s.get('Endpoint') == fn_arn:
            print(f'  subscription ja existe: {topic_arn.split(":")[-1]} -> {fn_name}')
            return
    sns.subscribe(TopicArn=topic_arn, Protocol='lambda', Endpoint=fn_arn)
    print(f'  subscribed: {topic_arn.split(":")[-1]} -> {fn_name}')


print('=== Deploy wpp-gateway-inbound ===')
inbound_arn = deploy(
    'wpp-gateway-inbound', 'wpp_gateway_inbound.py',
    env={
        'SESSIONS_TABLE': SESSIONS_TABLE,
        'MEDIA_BUCKET': MEDIA_BUCKET,
        'CONNECT_INSTANCE_ID': INSTANCE_ID,
        'CONNECT_FLOW_ID': FLOW_ID,
        'STREAMING_TOPIC_ARN': STREAMING_TOPIC_ARN,
        'CHAT_DURATION_MINUTES': '60',
        'TRANSCRIBE_LANG': 'pt-BR',
        'META_API_VERSION': 'v20.0',
        'ATTACH_AUDIO_TO_CHAT': 'false',
    },
    layers=[FFMPEG_LAYER_ARN, VOICE_DEPS_LAYER_ARN],
    timeout=120, memory=512)

print('\n=== Deploy wpp-gateway-outbound ===')
outbound_arn = deploy(
    'wpp-gateway-outbound', 'wpp_gateway_outbound.py',
    env={
        'SESSIONS_TABLE': SESSIONS_TABLE,
        'MEDIA_BUCKET': MEDIA_BUCKET,
        'POLLY_VOICE': 'Camila',
        'POLLY_ENGINE': 'generative',
        'POLLY_LANG': 'pt-BR',
        'META_API_VERSION': 'v20.0',
    },
    layers=[FFMPEG_LAYER_ARN],
    timeout=60, memory=512)

print('\n=== Subscriptions SNS ===')
subscribe(INBOUND_TOPIC_ARN, inbound_arn, 'wpp-gateway-inbound', 'sns-inbound-invoke')
subscribe(STREAMING_TOPIC_ARN, outbound_arn, 'wpp-gateway-outbound', 'sns-streaming-invoke')

print('\n=== DEPLOY COMPLETO ===')
print('Falta: (1) editar flow set-phone-attr, (2) smoke test, (3) flip do event destination (manual/manha).')
