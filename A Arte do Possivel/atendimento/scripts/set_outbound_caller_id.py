"""
Associa um numero de telefone (caller ID) a fila de saida, habilitando chamadas outbound.
Resolve o erro "Invalid outbound configuration - you must associate a phone number with this queue".

Uso: source .env && python3 scripts/set_outbound_caller_id.py
"""
import boto3
import json

REGION = 'us-east-1'
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
QUEUE_ID = '1e2366ac-a64e-4016-b0a1-0599a13110e7'  # BasicQueue (default outbound do Basic Routing Profile)

# Numero a usar como caller ID (US DID - ideal para outbound)
CALLER_ID_NUMBER_ID = '4252e089-0ab2-49d0-a976-91c76aef2ea5'  # +15557401578
CALLER_ID_NAME = 'Faculdade Nova Horizonte'

connect = boto3.client('connect', region_name=REGION)

# Estado atual
q = connect.describe_queue(InstanceId=INSTANCE_ID, QueueId=QUEUE_ID)['Queue']
print(f'Fila: {q["Name"]}')
print(f'OutboundCallerConfig atual: {json.dumps(q.get("OutboundCallerConfig", {}))}')

# Atualiza com o caller ID
connect.update_queue_outbound_caller_config(
    InstanceId=INSTANCE_ID,
    QueueId=QUEUE_ID,
    OutboundCallerConfig={
        'OutboundCallerIdName': CALLER_ID_NAME,
        'OutboundCallerIdNumberId': CALLER_ID_NUMBER_ID
    }
)
print('\nCaller ID associado com sucesso!')

# Confirma
q2 = connect.describe_queue(InstanceId=INSTANCE_ID, QueueId=QUEUE_ID)['Queue']
print(f'Novo OutboundCallerConfig: {json.dumps(q2.get("OutboundCallerConfig", {}))}')
print('\nAgora as chamadas outbound devem funcionar (recarregue o CCP/Agent Workspace).')
