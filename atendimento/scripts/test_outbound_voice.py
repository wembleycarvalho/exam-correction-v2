"""
Testa o branch de VOZ do wpp-gateway-outbound (sem celular real):
  - cria sessao de teste com last_modality=voice (numero fake)
  - injeta um evento de streaming (MESSAGE, role SYSTEM) simulando resposta do bot
  - o outbound deve: Polly -> ffmpeg OGG/Opus -> post_whatsapp_message_media -> send audio (voice:true)
Valida a cadeia de SAIDA em voz (o envio pro numero fake e aceito pela API mas nao entregue).
Limpa a sessao de teste ao final.

Uso: source .env && python3 scripts/test_outbound_voice.py
"""
import boto3
import json
import os
import time

REGION = os.environ.get('AWS_REGION', 'us-east-1')
lam = boto3.client('lambda', region_name=REGION)
logs = boto3.client('logs', region_name=REGION)
ddb = boto3.resource('dynamodb', region_name=REGION)
sessions = ddb.Table('whatsapp-connect-sessions')

CONTACT_ID = 'test-voice-contact-0001'
FAKE_PHONE = '5599999999999'
SYS_NUMBER = 'phone-number-id-fe268d418d9b4e1296c47f86795987df'

print('=== 1. Cria sessao de teste (last_modality=voice) ===')
sessions.put_item(Item={
    'contactId': CONTACT_ID, 'customerId': FAKE_PHONE,
    'connectionToken': 'x', 'participantToken': 'x',
    'name': 'Teste Voz Out', 'systemNumber': SYS_NUMBER,
    'channel': 'Whatsapp', 'last_modality': 'voice'})
print('  ok')

print('\n=== 2. Injeta evento de streaming (bot respondeu em texto -> deve virar voz) ===')
streaming_msg = {
    "Type": "MESSAGE", "ParticipantRole": "SYSTEM", "ContactId": CONTACT_ID,
    "ContentType": "text/plain",
    "Content": "Ola! Recebi sua mensagem. Esta e uma resposta em voz de teste do assistente.",
    "Id": "msg-test-0001",
}
event = {"Records": [{"Sns": {"Message": json.dumps(streaming_msg)}}]}
t0 = time.time()
resp = lam.invoke(FunctionName='wpp-gateway-outbound', InvocationType='RequestResponse',
                  Payload=json.dumps(event))
print(f'  resposta: FunctionError={resp.get("FunctionError")} ({time.time()-t0:.1f}s)')

print('\n=== 3. Logs do outbound ===')
time.sleep(3)
try:
    ls = logs.describe_log_streams(logGroupName='/aws/lambda/wpp-gateway-outbound',
        orderBy='LastEventTime', descending=True, limit=1)['logStreams'][0]['logStreamName']
    start = int((time.time() - 90) * 1000)
    for e in logs.get_log_events(logGroupName='/aws/lambda/wpp-gateway-outbound',
                                 logStreamName=ls, startTime=start)['events'][-20:]:
        m = e['message'].rstrip()
        if any(k in m for k in ['polly', 'ffmpeg', 'nota de voz', 'send_voice', 'ERROR', 'texto enviado', 'media']):
            print('   ', m)
except Exception as e:
    print(f'  (erro logs: {e})')

print('\n=== 4. Limpeza ===')
sessions.delete_item(Key={'contactId': CONTACT_ID})
print('  sessao de teste apagada')
print('\n=== FIM ===')
