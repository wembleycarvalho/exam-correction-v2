"""
Configura o assistant demo-connect-nova com:
- KB conteudo-institucional associada
- AI Agent copiloto-atendente para Agent Assistance
- Atualiza fluxo com novo assistant ARN

NAO altera o que ja existe (agent-nova, prompt-nova, associacao Bedrock KB).

Uso: source .env && python3 scripts/setup_connect_nova.py
"""
import boto3
import json
import os
import sys
import time
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env, set_env

REGION = get_env('AWS_REGION', 'us-east-1')
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
FLOW_ID = 'acd511ac-afee-403b-9436-aa52f2f744cc'
ASSISTANT_ID = '4c588966-3671-4170-b53d-a6115502e9d1'
ASSISTANT_ARN = f'arn:aws:wisdom:{REGION}:123456789012:assistant/{ASSISTANT_ID}'
ACCOUNT_ID = '123456789012'
KB_CONTEUDO_ID = 'f980bec2-5fab-4a67-b629-fbb5e22a6d3d'
GATEWAY_ID = 'connect-jwt-gateway-4njugyplcw'

qconnect = boto3.client('qconnect', region_name=REGION)
connect = boto3.client('connect', region_name=REGION)

# ============================================================
# STEP 1: Associate KB conteudo-institucional
# ============================================================
print('=== Associando KB conteudo-institucional ===')
try:
    qconnect.create_assistant_association(
        assistantId=ASSISTANT_ID,
        associationType='KNOWLEDGE_BASE',
        association={'knowledgeBaseId': KB_CONTEUDO_ID}
    )
    print(f'  KB associada: {KB_CONTEUDO_ID}')
except Exception as e:
    if 'Conflict' in str(e):
        print(f'  KB ja associada')
    else:
        print(f'  Erro: {e}')

# ============================================================
# STEP 2: Create copiloto-atendente prompt
# ============================================================
print('\n=== Criando prompt copiloto-atendente ===')
PROMPT_TEXT = 'system: |\n' \
'    You are an AI assistant helping a human customer service agent at a Brazilian educational institution. ALWAYS respond in Portuguese (pt-BR).\n' \
'\n' \
'    <formatting_requirements>\n' \
'    MUST format all responses with this structure:\n' \
'\n' \
'    <message>\n' \
'    Your response goes here. Write clearly in Portuguese.\n' \
'    </message>\n' \
'\n' \
'    MUST always start with message tags.\n' \
'    </formatting_requirements>\n' \
'\n' \
'    <instructions>\n' \
'    Voce e um copiloto que ajuda o atendente humano a resolver questoes de alunos e clientes.\n' \
'\n' \
'    FERRAMENTAS DISPONIVEIS:\n' \
'    - consultar_usuario: busca dados do usuario por telefone (phone) ou CPF (cpf)\n' \
'    - consultar_academico: busca notas, disciplinas, provas, historico e financeiro por CPF. Parametros: cpf e tipo_consulta (disciplina, prova, historico, financeiro, todos)\n' \
'    - consultar_conteudo: busca na base de conhecimento. Parametros: pergunta e cpf (opcional)\n' \
'    - listar_cursos: lista cursos disponiveis\n' \
'    - detalhe_curso: detalhes de um curso. Parametro: curso_id\n' \
'\n' \
'    Quando o atendente perguntar sobre notas ou dados academicos, use consultar_academico.\n' \
'    Quando perguntar sobre financeiro, use consultar_academico com tipo_consulta=financeiro.\n' \
'    Responda SEMPRE em portugues. Seja direto e objetivo.\n' \
'    Se o atendente nao informar o CPF, peca educadamente.\n' \
'    </instructions>\n' \
'\n' \
'    {{$.toolConfigurationList}}\n' \
'\n' \
'    <system_variables>\n' \
'    contactId: {{$.contactId}}\n' \
'    dateTime: {{$.dateTime}}\n' \
'    </system_variables>\n' \
'messages:\n' \
'    - "{{$.conversationHistory}}"\n' \
'    - role: assistant\n' \
'      content: <message>\n'

prompt_id = None
try:
    resp = qconnect.create_ai_prompt(
        assistantId=ASSISTANT_ID,
        name='copiloto-atendente-prompt',
        type='ORCHESTRATION',
        templateType='TEXT',
        visibilityStatus='PUBLISHED',
        apiFormat='MESSAGES',
        modelId='us.anthropic.claude-sonnet-4-5-20250929-v1:0',
        templateConfiguration={
            'textFullAIPromptEditTemplateConfiguration': {
                'text': PROMPT_TEXT
            }
        },
        description='Prompt do copiloto do atendente em portugues'
    )
    prompt_id = resp['aiPrompt']['aiPromptId']
    print(f'  Prompt criado: {prompt_id}')
except Exception as e:
    if 'Conflict' in str(e):
        prompts = qconnect.list_ai_prompts(assistantId=ASSISTANT_ID)
        for p in prompts.get('aiPromptSummaries', []):
            if p['name'] == 'copiloto-atendente-prompt':
                prompt_id = p['aiPromptId']
                print(f'  Prompt ja existe: {prompt_id}')
                break
    else:
        print(f'  Erro: {e}')

# ============================================================
# STEP 3: Create copiloto-atendente AI Agent
# ============================================================
print('\n=== Criando AI Agent copiloto-atendente ===')

# Get tools from the gateway
TOOL_NAMES = [
    'academico___consultar_academico',
    'catalogo_cursos___detalhe_curso',
    'catalogo_cursos___listar_cursos',
    'user_lookup___consultar_usuario',
    'conteudo___consultar_conteudo',
    'vestibular___consultar_vestibular',
]

# Build tool configs - minimal, just name and type
tools = []
for name in TOOL_NAMES:
    tools.append({
        'toolName': name,
        'toolType': 'MODEL_CONTEXT_PROTOCOL',
    })

agent_config = {
    'orchestrationAIAgentConfiguration': {
        'orchestrationAIPromptId': prompt_id,
        'locale': 'pt_BR',
        'toolConfigurations': tools,
    }
}

copiloto_id = None
try:
    resp = qconnect.create_ai_agent(
        assistantId=ASSISTANT_ID,
        name='copiloto-atendente',
        type='ORCHESTRATION',
        visibilityStatus='PUBLISHED',
        configuration=agent_config,
        description='Copiloto do atendente com acesso a tools MCP'
    )
    copiloto_id = resp['aiAgent']['aiAgentId']
    print(f'  Agent criado: {copiloto_id}')
except Exception as e:
    if 'Conflict' in str(e):
        agents = qconnect.list_ai_agents(assistantId=ASSISTANT_ID)
        for a in agents.get('aiAgentSummaries', []):
            if a['name'] == 'copiloto-atendente':
                copiloto_id = a['aiAgentId']
                print(f'  Agent ja existe: {copiloto_id}')
                break
    else:
        print(f'  Erro: {e}')

# ============================================================
# STEP 4: Update flow with new assistant ARN
# ============================================================
print('\n=== Atualizando fluxo ===')
try:
    flow_resp = connect.describe_contact_flow(InstanceId=INSTANCE_ID, ContactFlowId=FLOW_ID)
    content = json.loads(flow_resp['ContactFlow']['Content'])

    # Replace old assistant ARN with new one in all actions
    old_arn = 'arn:aws:wisdom:us-east-1:123456789012:assistant/8a30d6b7-c8db-420e-b8af-8f8bf75f2dc3'
    content_str = json.dumps(content)
    content_str = content_str.replace(old_arn, ASSISTANT_ARN)

    # Also update the AI Agent ARN for self-service (agent-nova)
    self_service_agent_id = '9fe5ed34-f493-44a5-817e-85c912116f71'
    old_agent_arn = 'arn:aws:wisdom:us-east-1:123456789012:ai-agent/8a30d6b7-c8db-420e-b8af-8f8bf75f2dc3/940697f0-4aab-4cbc-91a5-9205f59c9d65:$LATEST'
    new_agent_arn = f'arn:aws:wisdom:{REGION}:{ACCOUNT_ID}:ai-agent/{ASSISTANT_ID}/{self_service_agent_id}:$LATEST'
    content_str = content_str.replace(old_agent_arn, new_agent_arn)

    # Update copiloto ARN if it exists in the flow
    if copiloto_id:
        old_copiloto_arn = 'arn:aws:wisdom:us-east-1:123456789012:ai-agent/8a30d6b7-c8db-420e-b8af-8f8bf75f2dc3/d06e1208-c80f-4417-90b0-86e40d2a15af:$LATEST'
        new_copiloto_arn = f'arn:aws:wisdom:{REGION}:{ACCOUNT_ID}:ai-agent/{ASSISTANT_ID}/{copiloto_id}:$LATEST'
        content_str = content_str.replace(old_copiloto_arn, new_copiloto_arn)

    # Also update metadata references
    content = json.loads(content_str)

    # Update metadata for ai-agent block
    if 'ai-agent' in content.get('Metadata', {}).get('ActionMetadata', {}):
        meta = content['Metadata']['ActionMetadata']['ai-agent']
        meta['aiAgentName'] = 'agent-nova'
        meta['aiAgentVersionArn'] = new_agent_arn
        if 'parameters' in meta:
            meta['parameters']['WisdomAssistantArn'] = {
                'useAIAgentDropdown': True,
                'aiAgentName': 'agent-nova',
                'aiAgentVersionArn': new_agent_arn
            }

    connect.update_contact_flow_content(
        InstanceId=INSTANCE_ID,
        ContactFlowId=FLOW_ID,
        Content=json.dumps(content)
    )
    print(f'  Fluxo atualizado com assistant: {ASSISTANT_ID}')
    print(f'  Self-service agent: agent-nova ({self_service_agent_id})')
    if copiloto_id:
        print(f'  Agent assistance: copiloto-atendente ({copiloto_id})')
except Exception as e:
    print(f'  Erro: {e}')

# ============================================================
# STEP 5: Set Agent Assistance default (if copiloto was created)
# ============================================================
if copiloto_id:
    print('\n=== Configurando Agent Assistance default ===')
    # This needs to be done via console (Default AI Agent Configurations > Agent Assistance)
    print(f'  MANUAL: Va no console > AI agent designer > AI Agents')
    print(f'  Na tabela "Default AI Agent Configurations", edite "Agent Assistance"')
    print(f'  Selecione: copiloto-atendente')

# ============================================================
# STEP 6: Update .env
# ============================================================
set_env('ASSISTANT_ID', ASSISTANT_ID)
print(f'\n=== Done! ===')
print(f'  Assistant: {ASSISTANT_ID} (demo-connect-nova)')
print(f'  Flow atualizado')
print(f'  .env atualizado')
