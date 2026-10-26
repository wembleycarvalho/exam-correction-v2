"""
Atualiza o fluxo connect-whatsapp-interaction para incluir:
1. Invoke Lambda (connect-agent-briefing) no caminho de Escalate
2. Set Contact Attributes com os dados do briefing

Faz BACKUP do fluxo atual antes de modificar.

Uso: source .env && python3 scripts/update_flow_briefing.py
"""
import boto3
import json
import os
import sys
import time
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env

REGION = get_env('AWS_REGION', 'us-east-1')
ACCOUNT_ID = get_env('AWS_ACCOUNT_ID', '123456789012')
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
FLOW_ID = 'acd511ac-afee-403b-9436-aa52f2f744cc'
LAMBDA_ARN = f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:connect-agent-briefing'

connect = boto3.client('connect', region_name=REGION)

# ============================================================
# Step 1: BACKUP
# ============================================================
print('=== Atualizando Fluxo com Briefing ===\n')
print('1. Backup do fluxo atual...')

resp = connect.describe_contact_flow(
    InstanceId=INSTANCE_ID,
    ContactFlowId=FLOW_ID
)
flow = resp['ContactFlow']
content = json.loads(flow['Content'])

# Save backup
backup_dir = os.path.join(os.path.dirname(__file__), '..', 'backups')
os.makedirs(backup_dir, exist_ok=True)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_file = os.path.join(backup_dir, f'flow_backup_{timestamp}.json')

with open(backup_file, 'w') as f:
    json.dump(content, f, indent=2, ensure_ascii=False)
print(f'   Backup salvo: {backup_file}')
print(f'   Flow: {flow["Name"]}')
print(f'   Actions: {len(content["Actions"])}')

# ============================================================
# Step 2: Analisar estrutura do fluxo
# ============================================================
print('\n2. Analisando fluxo...')

# Find the escalate path - look for where "Escalate" leads
# From the architecture: check-tool-result -> Escalate -> Connect assistant (copiloto) -> set-queue -> transfer
# The copiloto block is 7fa94e88-27ea-4082-acf6-614909e8c88c (CreateWisdomSession)

# Find check-tool-result block and its Escalate transition
escalate_target = None
check_tool_block = None

for action in content['Actions']:
    ident = action.get('Identifier', '')
    if ident == 'check-tool-result' or 'check-tool' in ident.lower():
        check_tool_block = action
        # Find Escalate condition
        transitions = action.get('Transitions', {})
        conditions = transitions.get('Conditions', [])
        for cond in conditions:
            # The condition value might be "Escalate" or "transferir_atendente"
            condition_value = cond.get('Condition', {}).get('Operands', [''])[0] if 'Condition' in cond else ''
            next_action = cond.get('NextAction', '')
            if 'Escalate' in str(cond) or 'transferir' in str(cond):
                escalate_target = next_action
                print(f'   Escalate -> {next_action}')

if not escalate_target:
    # Try different approach - look at all transitions
    for action in content['Actions']:
        ident = action.get('Identifier', '')
        if 'check-tool' in ident.lower():
            print(f'   Found: {ident}')
            print(f'   Transitions: {json.dumps(action.get("Transitions", {}), indent=2)[:500]}')

# Let me dump the check-tool-result block to understand structure
print('\n   Looking for escalate path...')
for action in content['Actions']:
    ident = action.get('Identifier', '')
    transitions = action.get('Transitions', {})
    conditions = transitions.get('Conditions', [])
    for cond in conditions:
        next_act = cond.get('NextAction', '')
        # If this transitions to the copiloto (7fa94e88...)
        if next_act == '7fa94e88-27ea-4082-acf6-614909e8c88c':
            escalate_target = next_act
            print(f'   {ident} -> (escalate) -> {next_act} (copiloto)')
            check_tool_block = action
            break

if not escalate_target:
    print('   ERRO: Nao encontrou caminho de escalate')
    print('   Dumping all transitions:')
    for action in content['Actions']:
        ident = action.get('Identifier', '')
        transitions = action.get('Transitions', {})
        if transitions.get('Conditions'):
            for cond in transitions['Conditions']:
                print(f'     {ident} -> {cond.get("NextAction", "?")}')
        if transitions.get('NextAction'):
            print(f'     {ident} -> {transitions["NextAction"]}')
    sys.exit(1)

# ============================================================
# Step 3: Insert Lambda + Set Attributes blocks
# ============================================================
print('\n3. Inserindo blocos...')

# New block IDs
LAMBDA_BLOCK_ID = 'invoke-briefing-lambda'
SET_ATTRS_BLOCK_ID = 'set-briefing-attrs'

# Check if already added
existing_ids = [a.get('Identifier') for a in content['Actions']]
if LAMBDA_BLOCK_ID in existing_ids:
    print('   Blocos ja existem, atualizando...')
    # Remove existing blocks to re-add
    content['Actions'] = [a for a in content['Actions'] if a.get('Identifier') not in [LAMBDA_BLOCK_ID, SET_ATTRS_BLOCK_ID]]

# Create Invoke Lambda block
lambda_block = {
    "Identifier": LAMBDA_BLOCK_ID,
    "Type": "InvokeLambdaFunction",
    "Parameters": {
        "LambdaFunctionARN": LAMBDA_ARN,
        "InvocationTimeLimitSeconds": "8",
        "LambdaInvocationAttributes": {},
        "ResponseValidation": {
            "ResponseType": "STRING_MAP"
        }
    },
    "Transitions": {
        "NextAction": SET_ATTRS_BLOCK_ID,
        "Errors": [
            {
                "NextAction": escalate_target,  # If Lambda fails, continue to copiloto anyway
                "ErrorType": "NoMatchingError"
            }
        ]
    }
}

# Create Set Contact Attributes block
set_attrs_block = {
    "Identifier": SET_ATTRS_BLOCK_ID,
    "Type": "UpdateContactAttributes",
    "Parameters": {
        "Attributes": {
            "briefing_nome": "$.External.nome",
            "briefing_sentimento": "$.External.sentimento",
            "briefing_intencao": "$.External.intencao",
            "briefing_resumo": "$.External.resumo_conversa",
            "briefing_dicas": "$.External.dicas",
            "briefing_tipo": "$.External.tipo",
            "briefing_curso": "$.External.curso",
            "briefing_financeiro": "$.External.situacao_financeira",
            "briefing_foto_url": "$.External.foto_url"
        }
    },
    "Transitions": {
        "NextAction": escalate_target,  # Continue to copiloto
        "Errors": [
            {
                "NextAction": escalate_target,
                "ErrorType": "NoMatchingError"
            }
        ]
    }
}

# Add new blocks
content['Actions'].append(lambda_block)
content['Actions'].append(set_attrs_block)

# Update the transition that previously pointed to escalate_target
# to now point to our Lambda block
updated = 0
for action in content['Actions']:
    if action.get('Identifier') in [LAMBDA_BLOCK_ID, SET_ATTRS_BLOCK_ID]:
        continue  # Don't modify our own blocks
    
    transitions = action.get('Transitions', {})
    
    # Check Conditions
    conditions = transitions.get('Conditions', [])
    for cond in conditions:
        if cond.get('NextAction') == escalate_target:
            cond['NextAction'] = LAMBDA_BLOCK_ID
            updated += 1
    
    # Check DefaultAction
    if transitions.get('DefaultAction') == escalate_target:
        # Only update if this is the check-tool-result block
        if action.get('Identifier') == check_tool_block.get('Identifier'):
            transitions['DefaultAction'] = LAMBDA_BLOCK_ID
            updated += 1

print(f'   Lambda block: {LAMBDA_BLOCK_ID}')
print(f'   Set attrs block: {SET_ATTRS_BLOCK_ID}')
print(f'   Transitions atualizadas: {updated}')
print(f'   Total actions: {len(content["Actions"])}')

# ============================================================
# Step 4: Atualizar fluxo
# ============================================================
print('\n4. Atualizando fluxo no Connect...')

try:
    connect.update_contact_flow_content(
        InstanceId=INSTANCE_ID,
        ContactFlowId=FLOW_ID,
        Content=json.dumps(content)
    )
    print('   SUCCESS: Fluxo atualizado!')
except Exception as e:
    print(f'   ERRO: {e}')
    print(f'\n   Restaurando backup...')
    with open(backup_file, 'r') as f:
        backup_content = f.read()
    try:
        connect.update_contact_flow_content(
            InstanceId=INSTANCE_ID,
            ContactFlowId=FLOW_ID,
            Content=backup_content
        )
        print('   Backup restaurado com sucesso.')
    except Exception as e2:
        print(f'   ERRO ao restaurar: {e2}')
    sys.exit(1)

print(f'''
=== Fluxo Atualizado! ===

Caminho de Escalate:
  check-tool-result (Escalate/transferir)
    -> Invoke Lambda (connect-agent-briefing) [NOVO]
    -> Set Contact Attributes (briefing_*) [NOVO]
    -> Connect assistant (copiloto-atendente)
    -> Set Queue
    -> Transfer

Se Lambda falhar: pula direto pro copiloto (nao trava o fluxo).

Backup: {backup_file}
Para restaurar: source .env && python3 -c "
import boto3, json
connect = boto3.client('connect', region_name='us-east-1')
with open('{backup_file}') as f:
    connect.update_contact_flow_content(
        InstanceId='{INSTANCE_ID}',
        ContactFlowId='{FLOW_ID}',
        Content=f.read()
    )
print('Restaurado!')
"
''')
