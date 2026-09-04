"""
CUTOVER (passo destrutivo, reversivel) — faz a virada pra arquitetura de voz.
Executa DOIS ajustes atomicamente-ish:
  1. Edita o flow connect-whatsapp-interaction: bloco set-phone-attr passa a ler
     $.Attributes.phone (o StartChatContact injeta 'phone' como atributo; nao ha
     CustomerEndpoint.Address em chat via API).
  2. Aponta o event destination da WABA pro SNS whatsapp-inbound (deixa de ir direto
     pro Connect). A partir daqui o WhatsApp passa pelos gateways de voz.

Faz backup do flow ANTES. Rollback: scripts/rollback_voice.py

Uso: source .env && python3 scripts/flip_to_voice.py --confirm
"""
import boto3
import json
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env

REGION = get_env('AWS_REGION', 'us-east-1')
WABA_ID = require_env('WABA_ID')
INBOUND_TOPIC_ARN = require_env('WPP_INBOUND_TOPIC_ARN')

INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
FLOW_ID = 'acd511ac-afee-403b-9436-aa52f2f744cc'

connect = boto3.client('connect', region_name=REGION)
sm = boto3.client('socialmessaging', region_name=REGION)

if '--confirm' not in sys.argv:
    print('ATENCAO: este script faz a VIRADA (reroteia TODO o WhatsApp pro gateway de voz).')
    print('Rode com --confirm quando estiver pronto (de preferencia com um celular pra testar).')
    print('Rollback disponivel: scripts/rollback_voice.py')
    sys.exit(0)

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup_dir = os.path.join('backups', f'flip_{ts}')
os.makedirs(backup_dir, exist_ok=True)

# ---------- 1. Backup + edicao do flow ----------
print('=== 1. Ajuste do flow set-phone-attr ===')
d = connect.describe_contact_flow(InstanceId=INSTANCE_ID, ContactFlowId=FLOW_ID)['ContactFlow']
content = json.loads(d['Content'])
with open(os.path.join(backup_dir, 'flow_BEFORE.json'), 'w') as f:
    json.dump(content, f, indent=2, ensure_ascii=False)
print(f'  backup do flow salvo em {backup_dir}/flow_BEFORE.json')

changed = False
for act in content.get('Actions', []):
    if act.get('Identifier') == 'set-phone-attr':
        old = act['Parameters'].get('Attributes', {}).get('phone')
        if old != '$.Attributes.phone':
            act['Parameters']['Attributes']['phone'] = '$.Attributes.phone'
            changed = True
            print(f'  set-phone-attr: "{old}" -> "$.Attributes.phone"')
if changed:
    connect.update_contact_flow_content(
        InstanceId=INSTANCE_ID, ContactFlowId=FLOW_ID,
        Content=json.dumps(content))
    print('  flow atualizado.')
else:
    print('  flow ja estava ajustado.')

# ---------- 2. Flip do event destination ----------
print('\n=== 2. Event destination -> SNS whatsapp-inbound ===')
sm.put_whatsapp_business_account_event_destinations(
    id=WABA_ID,
    eventDestinations=[{'eventDestinationArn': INBOUND_TOPIC_ARN}])
print(f'  event destination agora: {INBOUND_TOPIC_ARN}')

print('\n=== VIRADA CONCLUIDA ===')
print('Teste: mande uma nota de voz no WhatsApp pro +5511945746008.')
print('Se algo quebrar: source .env && python3 scripts/rollback_voice.py')
