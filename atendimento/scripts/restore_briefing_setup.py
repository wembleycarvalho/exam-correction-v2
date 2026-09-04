"""
Restaura o setup do Painel de Briefing a partir de um diretorio de backup.
Recria/atualiza: view, fluxo screen pop, fluxo principal, AI agent config, prompt.

Uso: source .env && python3 scripts/restore_briefing_setup.py backups/briefing_setup_YYYYMMDD_HHMMSS
"""
import boto3
import json
import os
import sys

REGION = 'us-east-1'
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
ASSISTANT_ID = '4c588966-3671-4170-b53d-a6115502e9d1'
AGENT_ID = '9fe5ed34-f493-44a5-817e-85c912116f71'
PROMPT_ID = '51dff123-b8fd-4d8c-8915-2963041f2804'
MAIN_FLOW = 'acd511ac-afee-403b-9436-aa52f2f744cc'
SCREENPOP_FLOW = 'f944e9cf-6849-49f8-ad24-312abf30b553'
VIEW_ID = '13a21bf5-65f2-4fd1-b364-2f61ed32e644'

connect = boto3.client('connect', region_name=REGION)
qconnect = boto3.client('qconnect', region_name=REGION)

if len(sys.argv) < 2:
    # Find latest backup
    backups = sorted([d for d in os.listdir('backups') if d.startswith('briefing_setup_')])
    if not backups:
        print('Nenhum backup encontrado. Uso: restore_briefing_setup.py <backup_dir>')
        sys.exit(1)
    bdir = os.path.join('backups', backups[-1])
    print(f'Usando backup mais recente: {bdir}')
else:
    bdir = sys.argv[1]

if not os.path.isdir(bdir):
    print(f'Diretorio nao encontrado: {bdir}')
    sys.exit(1)

# 1. Restore main flow
print('\n1. Restaurando fluxo principal...')
content = open(f'{bdir}/flow_main_connect-whatsapp-interaction.json').read()
connect.update_contact_flow_content(InstanceId=INSTANCE_ID, ContactFlowId=MAIN_FLOW, Content=content)
print('   OK')

# 2. Restore screen pop flow
print('2. Restaurando fluxo screen pop...')
content2 = open(f'{bdir}/flow_agent-briefing-screen-pop.json').read()
try:
    connect.update_contact_flow_content(InstanceId=INSTANCE_ID, ContactFlowId=SCREENPOP_FLOW, Content=content2)
    print('   OK')
except connect.exceptions.ResourceNotFoundException:
    r = connect.create_contact_flow(InstanceId=INSTANCE_ID, Name='agent-briefing-screen-pop',
                                     Type='CONTACT_FLOW', Content=content2,
                                     Description='Painel de briefing (screen pop)')
    print(f'   Recriado: {r["ContactFlowId"]}')

# 3. Restore view
print('3. Restaurando view...')
vdata = json.load(open(f'{bdir}/view_briefing-atendente.json'))
try:
    connect.update_view_content(InstanceId=INSTANCE_ID, ViewId=VIEW_ID, Status='PUBLISHED',
                                Content={'Template': vdata['Content']['Template'], 'Actions': vdata['Content'].get('Actions', ['ActionSelected'])})
    print('   OK')
except connect.exceptions.ResourceNotFoundException:
    r = connect.create_view(InstanceId=INSTANCE_ID, Name='briefing-atendente', Status='PUBLISHED',
                            Content={'Template': vdata['Content']['Template'], 'Actions': vdata['Content'].get('Actions', ['ActionSelected'])})
    print(f'   Recriada: {r["View"]["Id"]}')

# 4. Restore AI agent config
print('4. Restaurando config do AI Agent...')
orch = json.load(open(f'{bdir}/ai-agent_orchestration_config.json'))

# MCP tools nao permitem override de schema/description - manter apenas campos essenciais
MCP_KEEP = {'toolName', 'toolType', 'toolId', 'overrideInputValues', 'userInteractionConfiguration'}
clean_tools = []
for t in orch.get('toolConfigurations', []):
    if t.get('toolType') == 'MODEL_CONTEXT_PROTOCOL':
        clean_tools.append({k: v for k, v in t.items() if k in MCP_KEEP})
    else:
        clean_tools.append(t)
orch['toolConfigurations'] = clean_tools

with open('/tmp/restore_agent_config.json', 'w') as f:
    json.dump({'orchestrationAIAgentConfiguration': orch}, f)
import subprocess
r = subprocess.run(['aws', 'qconnect', 'update-ai-agent', '--assistant-id', ASSISTANT_ID,
                    '--ai-agent-id', AGENT_ID, '--configuration', 'file:///tmp/restore_agent_config.json',
                    '--visibility-status', 'PUBLISHED'], capture_output=True, text=True)
print('   OK' if r.returncode == 0 else f'   ERRO: {r.stderr[:200]}')

# 5. Restore prompt
print('5. Restaurando prompt...')
ptext = open(f'{bdir}/prompt-nova_v2.yaml').read()
qconnect.update_ai_prompt(assistantId=ASSISTANT_ID, aiPromptId=PROMPT_ID,
                          templateConfiguration={'textFullAIPromptEditTemplateConfiguration': {'text': ptext}},
                          visibilityStatus='PUBLISHED')
qconnect.create_ai_prompt_version(assistantId=ASSISTANT_ID, aiPromptId=PROMPT_ID)
print('   OK')

print(f'\n=== Restauracao completa de {bdir} ===')
print('Lembre: workspace e security profile sao config manual (console).')
