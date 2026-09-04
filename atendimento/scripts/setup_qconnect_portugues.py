"""
Configura o Q Connect Assistant para responder em portugues.
Cria AI Agent para ANSWER_RECOMMENDATION e MANUAL_SEARCH com locale pt_BR.

Uso: source .env && python3 scripts/setup_qconnect_portugues.py
"""
import boto3
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env

REGION = get_env('AWS_REGION', 'us-east-1')
ASSISTANT_ID = get_env('ASSISTANT_ID', '8a30d6b7-c8db-420e-b8af-8f8bf75f2dc3')

qconnect = boto3.client('qconnect', region_name=REGION)

# Step 1: Create AI Agent for ANSWER_RECOMMENDATION with locale pt_BR
print('=== Criando AI Agent ANSWER_RECOMMENDATION (pt_BR) ===')
agent_id = None
try:
    resp = qconnect.create_ai_agent(
        assistantId=ASSISTANT_ID,
        name='assistente-portugues-ar',
        type='ANSWER_RECOMMENDATION',
        visibilityStatus='PUBLISHED',
        configuration={
            'answerRecommendationAIAgentConfiguration': {
                'locale': 'pt_BR'
            }
        },
        description='Answer Recommendation em portugues'
    )
    agent_id = resp['aiAgent']['aiAgentId']
    print(f'  Agent criado: {agent_id}')
except Exception as e:
    if 'Conflict' in str(e):
        agents = qconnect.list_ai_agents(assistantId=ASSISTANT_ID)
        for a in agents.get('aiAgentSummaries', []):
            if a['name'] == 'assistente-portugues-ar':
                agent_id = a['aiAgentId']
                print(f'  Agent ja existe: {agent_id}')
                break
    else:
        print(f'  Erro: {e}')

if agent_id:
    # Set as default
    try:
        qconnect.update_assistant_ai_agent(
            assistantId=ASSISTANT_ID,
            aiAgentType='ANSWER_RECOMMENDATION',
            configuration={'aiAgentId': agent_id}
        )
        print(f'  Definido como padrao para ANSWER_RECOMMENDATION')
    except Exception as e:
        print(f'  Erro ao definir padrao: {e}')

# Step 2: Create AI Agent for MANUAL_SEARCH with locale pt_BR
print('\n=== Criando AI Agent MANUAL_SEARCH (pt_BR) ===')
ms_agent_id = None
try:
    resp = qconnect.create_ai_agent(
        assistantId=ASSISTANT_ID,
        name='assistente-portugues-ms',
        type='MANUAL_SEARCH',
        visibilityStatus='PUBLISHED',
        configuration={
            'manualSearchAIAgentConfiguration': {
                'locale': 'pt_BR'
            }
        },
        description='Manual Search em portugues'
    )
    ms_agent_id = resp['aiAgent']['aiAgentId']
    print(f'  Agent criado: {ms_agent_id}')
except Exception as e:
    if 'Conflict' in str(e):
        agents = qconnect.list_ai_agents(assistantId=ASSISTANT_ID)
        for a in agents.get('aiAgentSummaries', []):
            if a['name'] == 'assistente-portugues-ms':
                ms_agent_id = a['aiAgentId']
                print(f'  Agent ja existe: {ms_agent_id}')
                break
    else:
        print(f'  Erro: {e}')

if ms_agent_id:
    try:
        qconnect.update_assistant_ai_agent(
            assistantId=ASSISTANT_ID,
            aiAgentType='MANUAL_SEARCH',
            configuration={'aiAgentId': ms_agent_id}
        )
        print(f'  Definido como padrao para MANUAL_SEARCH')
    except Exception as e:
        print(f'  Erro ao definir padrao: {e}')

print('\nDone! Q Connect agora responde em portugues (pt_BR).')
