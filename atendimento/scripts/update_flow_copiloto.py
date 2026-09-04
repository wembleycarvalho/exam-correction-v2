"""
Atualiza o fluxo do Connect para usar o copiloto-atendente no Q Connect.
Modifica o bloco ai-agent (CreateWisdomSession) para incluir o AI Agent
de agent assistance (copiloto-atendente) na sessao.

Uso: source .env && python3 scripts/update_flow_copiloto.py
"""
import boto3
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env

REGION = get_env('AWS_REGION', 'us-east-1')
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
FLOW_ID = 'acd511ac-afee-403b-9436-aa52f2f744cc'
ASSISTANT_ID = '8a30d6b7-c8db-420e-b8af-8f8bf75f2dc3'
COPILOTO_AGENT_ID = 'd06e1208-c80f-4417-90b0-86e40d2a15af'
COPILOTO_ARN = f'arn:aws:wisdom:us-east-1:123456789012:ai-agent/{ASSISTANT_ID}/{COPILOTO_AGENT_ID}:$LATEST'

connect = boto3.client('connect', region_name=REGION)

# Get current flow
resp = connect.describe_contact_flow(InstanceId=INSTANCE_ID, ContactFlowId=FLOW_ID)
content = json.loads(resp['ContactFlow']['Content'])

# Find the Lex bot action and add the copiloto agent ARN for agent assistance
for action in content['Actions']:
    if action['Identifier'] == '39dd4e13-c0fd-4bfa-96fc-12912bb93f6e':
        # This is the ConnectParticipantWithLexBot action
        # Add the copiloto agent ARN for agent assistance
        lex_attrs = action['Parameters'].get('LexSessionAttributes', {})
        lex_attrs['x-amz-lex:q-in-connect:agent-assistance-ai-agent-arn'] = COPILOTO_ARN
        action['Parameters']['LexSessionAttributes'] = lex_attrs
        print(f'Updated Lex session attributes with copiloto ARN')
        print(f'  x-amz-lex:q-in-connect:agent-assistance-ai-agent-arn: {COPILOTO_ARN}')
        break

# Also update metadata
meta = content['Metadata']['ActionMetadata'].get('39dd4e13-c0fd-4bfa-96fc-12912bb93f6e', {})
if 'dynamicMetadata' not in meta:
    meta['dynamicMetadata'] = {}
meta['dynamicMetadata']['x-amz-lex:q-in-connect:agent-assistance-ai-agent-arn'] = False

# Save updated flow
updated_content = json.dumps(content)
connect.update_contact_flow_content(
    InstanceId=INSTANCE_ID,
    ContactFlowId=FLOW_ID,
    Content=updated_content
)
print('Flow atualizado e publicado!')
print(f'Copiloto ARN: {COPILOTO_ARN}')
