"""Update copiloto-atendente agent with new prompt and clean tools."""
import boto3
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env

REGION = get_env('AWS_REGION', 'us-east-1')
ASSISTANT_ID = '8a30d6b7-c8db-420e-b8af-8f8bf75f2dc3'
AGENT_ID = 'd06e1208-c80f-4417-90b0-86e40d2a15af'
PROMPT_ID = 'f14b2e4d-66c3-4e6c-a2f1-54c08659f478'

qconnect = boto3.client('qconnect', region_name=REGION)

# Get current config
detail = qconnect.get_ai_agent(assistantId=ASSISTANT_ID, aiAgentId=AGENT_ID)
config = detail['aiAgent']['configuration']['orchestrationAIAgentConfiguration']

# Print current tools for debugging
print('Current tools:')
for t in config.get('toolConfigurations', []):
    keys = list(t.keys())
    print(f'  {t["toolName"]}: keys={keys}')

# Build minimal config - only change the prompt, keep tools as-is but remove Retrieve
new_config = {
    'orchestrationAIPromptId': PROMPT_ID,
    'locale': 'pt_BR',
}

# Only include tools without schema overrides
tools = []
for t in config.get('toolConfigurations', []):
    if t['toolName'] == 'Retrieve':
        continue
    # Only keep toolName, toolType, and toolId
    tool = {
        'toolName': t['toolName'],
        'toolType': t['toolType'],
        'toolId': t['toolId'],
    }
    tools.append(tool)

new_config['toolConfigurations'] = tools

print(f'\nNew config tools: {len(tools)}')
for t in tools:
    print(f'  {t["toolName"]}')

try:
    qconnect.update_ai_agent(
        assistantId=ASSISTANT_ID,
        aiAgentId=AGENT_ID,
        visibilityStatus='PUBLISHED',
        configuration={
            'orchestrationAIAgentConfiguration': new_config
        }
    )
    print('\nAgent atualizado com sucesso!')
except Exception as e:
    print(f'\nErro: {e}')
