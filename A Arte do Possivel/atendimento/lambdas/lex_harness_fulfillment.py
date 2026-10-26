# Lambda: lex-harness-fulfillment
# Runtime: python3.12 | Timeout: 120s | Memory: 256MB
# Role: LexFulfillmentLambdaRole
# Layers: boto3-latest
# Env vars: HARNESS_VENDAS_ARN, HARNESS_ALUNOS_ARN, HARNESS_SAUDE_ARN
"""
Lex fulfillment - valida usuario e roteia pro harness correto via SigV4.
"""
import json
import os
import boto3
import hashlib
import uuid

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_USUARIOS = os.environ.get('TABLE_USUARIOS', 'cadastro-usuarios')

HARNESS_MAP = {
    'EducacaoNovoCurso': os.environ.get('HARNESS_VENDAS_ARN', ''),
    'EducacaoAluno': os.environ.get('HARNESS_ALUNOS_ARN', ''),
    'SaudePaciente': os.environ.get('HARNESS_SAUDE_ARN', ''),
}

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table_usuarios = dynamodb.Table(TABLE_USUARIOS)


def invoke_harness(harness_arn, message, session_id, actor_id=None):
    client = boto3.client('bedrock-agentcore', region_name=REGION)
    params = {'harnessArn': harness_arn, 'runtimeSessionId': session_id,
              'messages': [{'role': 'user', 'content': [{'text': message}]}]}
    if actor_id:
        params['actorId'] = hashlib.sha256(actor_id.encode()).hexdigest()
    response = client.invoke_harness(**params)
    result = ''
    for event in response['stream']:
        if 'contentBlockDelta' in event:
            delta = event['contentBlockDelta'].get('delta', {})
            if 'text' in delta:
                result += delta['text']
    return result


def check_user(phone):
    try:
        return table_usuarios.get_item(Key={'telefone': phone}).get('Item')
    except Exception:
        return None


def close(intent, message, session_attrs=None):
    resp = {'sessionState': {'dialogAction': {'type': 'Close'}, 'intent': {'name': intent, 'state': 'Fulfilled'}},
            'messages': [{'contentType': 'PlainText', 'content': message}]}
    if session_attrs:
        resp['sessionState']['sessionAttributes'] = session_attrs
    return resp


def lambda_handler(event, context):
    print(f"Lex event: {json.dumps(event)}")
    intent_name = event['sessionState']['intent']['name']
    input_text = event.get('inputTranscript', '')
    session_id = event.get('sessionId', str(uuid.uuid4()))
    session_attrs = event.get('sessionState', {}).get('sessionAttributes', {}) or {}
    phone = session_attrs.get('phone', '')

    if len(session_id) < 33:
        session_id = session_id + '-' + uuid.uuid4().hex[:33 - len(session_id) - 1]

    harness_arn = HARNESS_MAP.get(intent_name)
    if not harness_arn:
        return close(intent_name, 'Desculpe, nao entendi. Posso ajudar com educacao ou saude.')

    user = check_user(phone) if phone else None
    user_name = user.get('nome', '') if user else ''
    user_type = user.get('tipo', '') if user else ''

    if user:
        session_attrs.update({'user_name': user_name, 'user_type': user_type, 'phone': phone})

    context_prefix = f"[Usuario: {user_name}, Tipo: {user_type}] " if user_name else "[Usuario nao cadastrado. Pergunte o nome.] "

    if intent_name == 'EducacaoAluno' and (not user or 'aluno' not in user_type):
        return close(intent_name, 'Nao encontrei seu cadastro como aluno. Digite "cursos" para saber mais.', session_attrs)
    if intent_name == 'SaudePaciente' and (not user or 'paciente' not in user_type):
        return close(intent_name, 'Nao encontrei seu cadastro como paciente. Ligue (11) 3333-4444.', session_attrs)

    try:
        response = invoke_harness(harness_arn, context_prefix + input_text, session_id, phone or 'anonymous')
        return close(intent_name, response, session_attrs)
    except Exception as e:
        print(f"Harness error: {e}")
        return close(intent_name, 'Desculpe, dificuldades tecnicas. Tente novamente.', session_attrs)
