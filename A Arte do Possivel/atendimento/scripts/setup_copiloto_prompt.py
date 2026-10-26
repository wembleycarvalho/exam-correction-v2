"""
Cria prompt dedicado para o copiloto-atendente e atualiza o agent.
Uso: source .env && python3 scripts/setup_copiloto_prompt.py
"""
import boto3
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env

REGION = get_env('AWS_REGION', 'us-east-1')
ASSISTANT_ID = '8a30d6b7-c8db-420e-b8af-8f8bf75f2dc3'
AGENT_ID = 'd06e1208-c80f-4417-90b0-86e40d2a15af'

qconnect = boto3.client('qconnect', region_name=REGION)

PROMPT_TEXT = """system: |
    You are an AI assistant helping a human customer service agent at a Brazilian educational institution. ALWAYS respond in Portuguese (pt-BR).

    <formatting_requirements>
    MUST format all responses with this structure:

    <message>
    Your response goes here. Write clearly in Portuguese.
    </message>

    MUST always start with message tags.
    </formatting_requirements>

    <instructions>
    Voce e um copiloto que ajuda o atendente humano a resolver questoes de alunos.

    FERRAMENTAS DISPONIVEIS:
    - consultar_usuario: busca dados do usuario por telefone ou CPF
    - consultar_academico: busca notas, disciplinas, provas, historico e financeiro por CPF. Parametros: cpf e tipo_consulta (disciplina, prova, historico, financeiro, todos)
    - consultar_conteudo: busca na base de conhecimento (apostilas, vestibular, institucional). Parametros: pergunta e cpf (opcional)
    - listar_cursos: lista cursos disponiveis. Parametro opcional: area
    - detalhe_curso: detalhes de um curso. Parametro: curso_id

    Quando o atendente perguntar sobre notas ou dados academicos, use consultar_academico.
    Quando perguntar sobre financeiro, use consultar_academico com tipo_consulta=financeiro.
    Responda SEMPRE em portugues. Seja direto e objetivo.
    </instructions>

    {{$.toolConfigurationList}}

    <system_variables>
    contactId: {{$.contactId}}
    dateTime: {{$.dateTime}}
    </system_variables>
messages:
    - "{{$.conversationHistory}}"
    - role: assistant
      content: <message>
"""

# Step 1: Create prompt
print('=== Criando prompt ===')
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
    print(f'  Criado: {prompt_id}')
except Exception as e:
    if 'Conflict' in str(e):
        prompts = qconnect.list_ai_prompts(assistantId=ASSISTANT_ID)
        for p in prompts.get('aiPromptSummaries', []):
            if p['name'] == 'copiloto-atendente-prompt':
                prompt_id = p['aiPromptId']
                print(f'  Ja existe: {prompt_id}')
                break
    else:
        print(f'  Erro: {e}')
        sys.exit(1)

# Step 2: Update agent with new prompt
print('\n=== Atualizando agent ===')
try:
    detail = qconnect.get_ai_agent(assistantId=ASSISTANT_ID, aiAgentId=AGENT_ID)
    config = detail['aiAgent']['configuration']['orchestrationAIAgentConfiguration']
    config['orchestrationAIPromptId'] = prompt_id

    qconnect.update_ai_agent(
        assistantId=ASSISTANT_ID,
        aiAgentId=AGENT_ID,
        visibilityStatus='PUBLISHED',
        configuration={
            'orchestrationAIAgentConfiguration': config
        }
    )
    print(f'  Agent atualizado com prompt: {prompt_id}')
except Exception as e:
    print(f'  Erro: {e}')

print('\nDone!')
