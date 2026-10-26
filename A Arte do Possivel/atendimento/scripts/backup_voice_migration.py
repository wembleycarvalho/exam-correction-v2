# Backup do estado atual ANTES da migracao de voz (WhatsApp voice notes).
# Captura:
#   - Event destinations da WABA (End User Messaging Social) -> estado atual (Connect direto)
#   - Contact flows da instancia Connect -> conteudo JSON
#   - Gera um rollback script standalone que re-aponta o event destination pro Connect
#
# Uso: source .env && python3 scripts/backup_voice_migration.py
import boto3
import json
import os
import datetime

REGION = os.environ.get('AWS_REGION', 'us-east-1')
WABA_ID = os.environ.get('WABA_ID', 'waba-b7e8aaaa528c4a73a9dc4212f4323c79')

sm = boto3.client('socialmessaging', region_name=REGION)
connect = boto3.client('connect', region_name=REGION)

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup_dir = os.path.join('backups', f'voice_migration_{ts}')
os.makedirs(backup_dir, exist_ok=True)
print(f'Backup dir: {backup_dir}')


def save(name, obj):
    path = os.path.join(backup_dir, name)
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2, default=str, ensure_ascii=False)
    print(f'  salvo: {path}')


# 1. WABA event destinations (estado atual)
acct = sm.get_linked_whatsapp_business_account(id=WABA_ID)['account']
save('eum_waba_BEFORE.json', acct)

event_destinations = acct.get('eventDestinations', [])
print(f'\nEvent destinations atuais ({len(event_destinations)}):')
for ed in event_destinations:
    print(f'  - {ed.get("eventDestinationArn")}  role={ed.get("roleArn")}')

# Derivar instance id do event destination Connect (fonte da verdade)
instance_id = None
for ed in event_destinations:
    arn = ed.get('eventDestinationArn', '')
    if ':connect:' in arn and 'instance/' in arn:
        instance_id = arn.split('instance/')[-1].split('/')[0]
if not instance_id:
    instance_id = os.environ.get('CONNECT_INSTANCE_ID', '')
print(f'\nInstance Connect (do event destination): {instance_id}')

# 2. Snapshot dos contact flows da instancia
flows_snapshot = []
try:
    paginator = connect.get_paginator('list_contact_flows')
    for page in paginator.paginate(InstanceId=instance_id):
        for f in page['ContactFlowSummaryList']:
            try:
                detail = connect.describe_contact_flow(InstanceId=instance_id, ContactFlowId=f['Id'])['ContactFlow']
                flows_snapshot.append(detail)
                print(f'  flow: {f["Name"]} ({f["Id"]})')
            except Exception as e:
                print(f'  (skip flow {f.get("Name")}: {e})')
    save('connect_flows_BEFORE.json', flows_snapshot)
except Exception as e:
    print(f'  Erro ao listar flows: {e}')

# 3. Gerar rollback script standalone
rollback_path = os.path.join(backup_dir, 'rollback_event_destination.py')
rollback_code = f'''# ROLLBACK: re-aponta o event destination da WABA de volta pro Amazon Connect (estado original).
# Gerado por backup_voice_migration.py em {ts}
# Uso: source .env && python3 {rollback_path}
import boto3

REGION = "{REGION}"
WABA_ID = "{WABA_ID}"

# Estado ORIGINAL capturado no backup:
ORIGINAL_EVENT_DESTINATIONS = {json.dumps(event_destinations, indent=4)}

sm = boto3.client("socialmessaging", region_name=REGION)
print("Revertendo event destination para o estado original (Connect direto)...")
for ed in ORIGINAL_EVENT_DESTINATIONS:
    print("  ->", ed.get("eventDestinationArn"), "role=", ed.get("roleArn"))

# Reconstroi apenas os campos aceitos pela API (eventDestinationArn + roleArn)
payload = []
for ed in ORIGINAL_EVENT_DESTINATIONS:
    item = {{"eventDestinationArn": ed["eventDestinationArn"]}}
    if ed.get("roleArn"):
        item["roleArn"] = ed["roleArn"]
    payload.append(item)

resp = sm.put_whatsapp_business_account_event_destinations(id=WABA_ID, eventDestinations=payload)
print("OK. Resposta:", resp.get("ResponseMetadata", {{}}).get("HTTPStatusCode"))
print("Event destination revertido para Connect. WhatsApp volta a cair direto no fluxo nativo.")
'''
with open(rollback_path, 'w') as f:
    f.write(rollback_code)
print(f'\n  ROLLBACK gerado: {rollback_path}')

print('\n=== BACKUP COMPLETO ===')
print(f'Para reverter a qualquer momento: source .env && python3 {rollback_path}')
