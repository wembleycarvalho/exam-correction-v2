"""
Test script para invocar o harness via CLI.
Uso: source .env && python3 test.py "sua mensagem" [session_id] [actor_id]
"""
import boto3
import json
import sys
import os
import uuid
import hashlib
from botocore import UNSIGNED
from botocore.config import Config

if len(sys.argv) < 2:
    print('Uso: python test.py "sua mensagem" [session_id] [actor_id]')
    sys.exit(1)

message = sys.argv[1]
session_id = sys.argv[2] if len(sys.argv) > 2 else str(uuid.uuid4())
actor_id = sys.argv[3] if len(sys.argv) > 3 else None

if len(session_id) < 33:
    session_id = session_id + '-' + uuid.uuid4().hex[:33 - len(session_id) - 1]

if actor_id:
    actor_id = hashlib.sha256(actor_id.encode()).hexdigest()

REGION = os.environ.get('AWS_REGION', 'us-east-1')
COGNITO_CLIENT_ID = os.environ['COGNITO_CLIENT_ID']
COGNITO_USERNAME = os.environ['COGNITO_USERNAME']
COGNITO_PASSWORD = os.environ['COGNITO_PASSWORD']
HARNESS_ARN = os.environ['HARNESS_871F8_ARN']

# Cognito auth
cognito = boto3.client('cognito-idp', region_name=REGION)
auth_resp = cognito.initiate_auth(
    ClientId=COGNITO_CLIENT_ID, AuthFlow='USER_PASSWORD_AUTH',
    AuthParameters={'USERNAME': COGNITO_USERNAME, 'PASSWORD': COGNITO_PASSWORD}
)
access_token = auth_resp['AuthenticationResult']['AccessToken']

# Invoke harness with Bearer token (no SigV4)
client = boto3.client('bedrock-agentcore', region_name=REGION, config=Config(signature_version=UNSIGNED))

def add_bearer_token(request, **kwargs):
    request.headers['Authorization'] = f'Bearer {access_token}'
client.meta.events.register('before-send.bedrock-agentcore.InvokeHarness', add_bearer_token)

params = {'harnessArn': HARNESS_ARN, 'runtimeSessionId': session_id,
          'messages': [{'role': 'user', 'content': [{'text': message}]}]}
if actor_id:
    params['actorId'] = actor_id

response = client.invoke_harness(**params)

for event in response['stream']:
    if 'contentBlockDelta' in event:
        delta = event['contentBlockDelta'].get('delta', {})
        if 'text' in delta:
            print(delta['text'], end='')
print()
