"""
Teste de integracao (sem flip, sem celular real): simula um evento SNS do EUM Social
com uma mensagem de TEXTO de um numero FAKE, invoca a wpp-gateway-inbound e valida:
  - StartChatContact cria contato no flow (bot engaja)
  - sessao gravada na tabela whatsapp-connect-sessions
  - streaming entrega a saudacao do bot -> wpp-gateway-outbound (tenta enviar; numero fake falha, ok)
Depois LIMPA: encerra o contato e apaga a sessao de teste.

Uso: source .env && python3 scripts/test_integration_startchat.py
"""
import boto3
import json
import os
import sys
import time

REGION = os.environ.get('AWS_REGION', 'us-east-1')
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
FAKE_PHONE = '5599999999999'
OUR_ARN = 'arn:aws:social-messaging:us-east-1:123456789012:phone-number-id/fe268d418d9b4e1296c47f86795987df'
META_ID = '708149892370876'

lam = boto3.client('lambda', region_name=REGION)
connect = boto3.client('connect', region_name=REGION)
logs = boto3.client('logs', region_name=REGION)
ddb = boto3.resource('dynamodb', region_name=REGION)
sessions = ddb.Table('whatsapp-connect-sessions')

webhook_entry = {
    "changes": [{
        "field": "messages",
        "value": {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": META_ID},
            "contacts": [{"wa_id": FAKE_PHONE, "profile": {"name": "Teste Integracao"}}],
            "messages": [{
                "from": FAKE_PHONE, "id": "wamid.TESTINTEGRACAO", "type": "text",
                "text": {"body": "ola, teste de integracao"}
            }],
        },
    }]
}
sns_message = {
    "context": {"MetaPhoneNumberIds": [{"metaPhoneNumberId": META_ID, "arn": OUR_ARN}]},
    "whatsAppWebhookEntry": json.dumps(webhook_entry),
}
event = {"Records": [{"Sns": {"Message": json.dumps(sns_message)}}]}

print('=== 1. Invocando wpp-gateway-inbound com evento sintetico (texto) ===')
t0 = time.time()
resp = lam.invoke(FunctionName='wpp-gateway-inbound', InvocationType='RequestResponse',
                  Payload=json.dumps(event))
body = json.loads(resp['Payload'].read() or 'null')
print(f'  resposta: {body} FunctionError={resp.get("FunctionError")} ({time.time()-t0:.1f}s)')

print('\n=== 2. Aguardando sessao aparecer na tabela ===')
item = None
for _ in range(10):
    r = sessions.query(
        IndexName='customerId-index',
        KeyConditionExpression=boto3.dynamodb.conditions.Key('customerId').eq(FAKE_PHONE))
    if r.get('Items'):
        item = r['Items'][0]
        break
    time.sleep(2)

if item:
    print(f'  OK sessao criada: contactId={item["contactId"]} modality={item.get("last_modality")}')
    contact_id = item['contactId']
else:
    print('  FALHA: sessao nao apareceu. Ver logs abaixo.')
    contact_id = None

print('\n=== 3. Aguardando streaming -> outbound (bot respondeu?) ===')
time.sleep(8)

def tail_logs(group, seconds=120):
    try:
        streams = logs.describe_log_streams(logGroupName=group, orderBy='LastEventTime',
                                            descending=True, limit=1)['logStreams']
        if not streams:
            return '  (sem log streams)'
        ls = streams[0]['logStreamName']
        start = int((time.time() - seconds) * 1000)
        ev = logs.get_log_events(logGroupName=group, logStreamName=ls, startTime=start)['events']
        return '\n'.join('    ' + e['message'].rstrip() for e in ev[-25:])
    except Exception as e:
        return f'  (erro logs: {e})'

print('--- wpp-gateway-inbound logs ---')
print(tail_logs('/aws/lambda/wpp-gateway-inbound'))
print('--- wpp-gateway-outbound logs ---')
print(tail_logs('/aws/lambda/wpp-gateway-outbound'))

print('\n=== 4. Limpeza (encerra contato + apaga sessao de teste) ===')
if contact_id:
    try:
        connect.stop_contact(InstanceId=INSTANCE_ID, ContactId=contact_id)
        print(f'  contato {contact_id} encerrado')
    except Exception as e:
        print(f'  (stop_contact: {e})')
    try:
        sessions.delete_item(Key={'contactId': contact_id})
        print('  sessao de teste apagada')
    except Exception as e:
        print(f'  (delete session: {e})')

print('\n=== FIM DO TESTE DE INTEGRACAO ===')
