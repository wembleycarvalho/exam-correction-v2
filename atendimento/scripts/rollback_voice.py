"""
ROLLBACK COMPLETO da migracao de voz -> volta ao estado original:
  1. Restaura o event destination da WABA pro Amazon Connect (direto).
  2. Restaura o conteudo do flow connect-whatsapp-interaction do backup.

Usa os backups em backups/voice_migration_20260826_191052/ (estado ORIGINAL) e,
se existir, o backup mais recente de flip_*/flow_BEFORE.json.

Uso: source .env && python3 scripts/rollback_voice.py
"""
import boto3
import json
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env

REGION = get_env('AWS_REGION', 'us-east-1')
WABA_ID = require_env('WABA_ID')

INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
FLOW_ID = 'acd511ac-afee-403b-9436-aa52f2f744cc'

ORIGINAL_EVENT_DESTINATIONS = [{
    'eventDestinationArn': f'arn:aws:connect:{REGION}:123456789012:instance/{INSTANCE_ID}',
    'roleArn': 'arn:aws:iam::123456789012:role/EndUserMessagingConnectRole',
}]

connect = boto3.client('connect', region_name=REGION)
sm = boto3.client('socialmessaging', region_name=REGION)

# ---------- 1. Event destination de volta pro Connect ----------
print('=== 1. Event destination -> Connect (original) ===')
payload = []
for ed in ORIGINAL_EVENT_DESTINATIONS:
    item = {'eventDestinationArn': ed['eventDestinationArn']}
    if ed.get('roleArn'):
        item['roleArn'] = ed['roleArn']
    payload.append(item)
sm.put_whatsapp_business_account_event_destinations(id=WABA_ID, eventDestinations=payload)
print(f'  revertido para: {ORIGINAL_EVENT_DESTINATIONS[0]["eventDestinationArn"]}')

# ---------- 2. Restaura o flow ----------
print('\n=== 2. Restaura o flow connect-whatsapp-interaction ===')
flow_content = None

# preferir o flow_BEFORE.json do flip mais recente
flips = sorted(glob.glob('backups/flip_*/flow_BEFORE.json'))
if flips:
    src = flips[-1]
    with open(src) as f:
        flow_content = json.load(f)
    print(f'  usando backup do flip: {src}')
else:
    # fallback: connect_flows_BEFORE.json (snapshot inicial de todos os flows)
    src = 'backups/voice_migration_20260826_191052/connect_flows_BEFORE.json'
    if os.path.exists(src):
        with open(src) as f:
            flows = json.load(f)
        for fl in flows:
            if fl.get('Id') == FLOW_ID or fl.get('Arn', '').endswith(FLOW_ID):
                flow_content = json.loads(fl['Content']) if isinstance(fl['Content'], str) else fl['Content']
                break
        print(f'  usando snapshot inicial: {src}')

if flow_content:
    connect.update_contact_flow_content(
        InstanceId=INSTANCE_ID, ContactFlowId=FLOW_ID,
        Content=json.dumps(flow_content))
    print('  flow restaurado.')
else:
    print('  AVISO: nenhum backup de flow encontrado; flow NAO restaurado.')

print('\n=== ROLLBACK COMPLETO ===')
print('WhatsApp volta a cair direto no Connect nativo. Mate sessoes ativas se necessario:')
print('  python3 scripts/manage_sessions.py kill')
