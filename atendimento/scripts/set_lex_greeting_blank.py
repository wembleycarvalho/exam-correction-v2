"""
Troca o campo Text do bloco ConnectParticipantWithLexBot do fluxo
connect-whatsapp-interaction de "Ola! Como posso ajudar?" para " " (espaco),
para o AI agent processar a InitialMessage (pergunta do cliente) e responder de
verdade, em vez de so mostrar a saudacao fixa.

Backup do fluxo antes. Rollback: restaurar Text (ver backup).

Uso: source .env && python3 scripts/set_lex_greeting_blank.py
"""
import boto3, json, os, datetime

INST = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
FLOW = 'acd511ac-afee-403b-9436-aa52f2f744cc'
c = boto3.client('connect', region_name='us-east-1')

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bdir = os.path.join('backups', f'flow_greeting_{ts}')
os.makedirs(bdir, exist_ok=True)

content = json.loads(c.describe_contact_flow(InstanceId=INST, ContactFlowId=FLOW)['ContactFlow']['Content'])
with open(os.path.join(bdir, 'flow_BEFORE.json'), 'w') as f:
    json.dump(content, f, indent=2, ensure_ascii=False)
print(f'backup: {bdir}/flow_BEFORE.json')

changed = False
for a in content['Actions']:
    if a['Type'] == 'ConnectParticipantWithLexBot':
        old = a['Parameters'].get('Text')
        if old != ' ':
            a['Parameters']['Text'] = ' '
            changed = True
            print(f'Text: {old!r} -> \' \'')

if changed:
    c.update_contact_flow_content(InstanceId=INST, ContactFlowId=FLOW, Content=json.dumps(content))
    print('fluxo atualizado.')
else:
    print('Text ja estava em branco.')
