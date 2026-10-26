# Lambda: connect-harness-async
# Runtime: python3.12 | Timeout: 120s | Memory: 256MB
# Role: ConnectHarnessLambdaRole
# Layers: boto3-latest
# Env vars: COGNITO_CLIENT_ID, COGNITO_USERNAME, COGNITO_PASSWORD,
#           HARNESS_ARN, WHATSAPP_PHONE_NUMBER_ID, CONNECT_INSTANCE_ID
"""
Lambda async - chama o harness e envia resposta via WhatsApp.
"""
import json
import os
import uuid
import hashlib
import boto3
from botocore import UNSIGNED
from botocore.config import Config

COGNITO_CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID', '')
COGNITO_USERNAME = os.environ.get('COGNITO_USERNAME', '')
COGNITO_PASSWORD = os.environ.get('COGNITO_PASSWORD', '')
HARNESS_ARN = os.environ.get('HARNESS_ARN', '')
PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
INSTANCE_ID = os.environ.get('CONNECT_INSTANCE_ID', '')
REGION = os.environ.get('AWS_REGION', 'us-east-1')

_cached_token = None


def get_bearer_token():
    global _cached_token
    if _cached_token:
        return _cached_token
    cognito = boto3.client('cognito-idp', region_name=REGION)
    resp = cognito.initiate_auth(
        ClientId=COGNITO_CLIENT_ID,
        AuthFlow='USER_PASSWORD_AUTH',
        AuthParameters={'USERNAME': COGNITO_USERNAME, 'PASSWORD': COGNITO_PASSWORD}
    )
    _cached_token = resp['AuthenticationResult']['AccessToken']
    return _cached_token


def invoke_harness(message, session_id, actor_id=None):
    access_token = get_bearer_token()
    client = boto3.client('bedrock-agentcore', region_name=REGION, config=Config(signature_version=UNSIGNED))

    def add_bearer(request, **kwargs):
        request.headers['Authorization'] = f'Bearer {access_token}'
    client.meta.events.register('before-send.bedrock-agentcore.InvokeHarness', add_bearer)

    params = {'harnessArn': HARNESS_ARN, 'runtimeSessionId': session_id,
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


def send_whatsapp(phone_number, message):
    sm = boto3.client('socialmessaging', region_name=REGION)
    if len(message) > 4096:
        message = message[:4093] + '...'
    data = json.dumps({
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": f"+{phone_number}" if not phone_number.startswith('+') else phone_number,
        "type": "text", "text": {"body": message},
    })
    sm.send_whatsapp_message(originationPhoneNumberId=PHONE_NUMBER_ID, message=data, metaApiVersion='v20.0')


def lambda_handler(event, context):
    print(f"Async event: {json.dumps(event)}")
    phone = event.get('phone', '')
    contact_id = event.get('contactId', '')
    customer_message = event.get('message', 'Ola')
    phone_clean = phone.replace('+', '') if phone else ''

    session_id = f'connect-{contact_id}'
    if len(session_id) < 33:
        session_id = session_id + '-' + uuid.uuid4().hex[:33 - len(session_id) - 1]

    try:
        response_text = invoke_harness(customer_message, session_id, phone)
        if phone_clean:
            send_whatsapp(phone_clean, response_text)
    except Exception as e:
        print(f"Error: {e}")
        if phone_clean:
            send_whatsapp(phone_clean, 'Desculpe, estou com dificuldades. Tente novamente.')
    return {'status': 'ok'}
