"""
Teste automatizado: inicia um chat (com websocket), conversa com o bot, pede atendente,
e captura os contact attributes briefing_* para validar o painel.

Uso: source .env && python3 scripts/test_chat_escalate.py
"""
import boto3
import json
import time
import sys
import threading
import websocket

REGION = 'us-east-1'
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
FLOW_ID = 'acd511ac-afee-403b-9436-aa52f2f744cc'
TEST_PHONE = '+5511985743177'  # Wembley (tem foto e dados)

connect = boto3.client('connect', region_name=REGION)
participant = boto3.client('connectparticipant', region_name=REGION)

bot_messages = []


def send_message(conn_token, text):
    participant.send_message(
        ContentType='text/plain',
        Content=text,
        ConnectionToken=conn_token
    )


def start_websocket(ws_url):
    """Conecta ao websocket para que o bot processe as mensagens."""
    def on_message(ws, message):
        try:
            data = json.loads(message)
            content = data.get('content')
            if content:
                inner = json.loads(content)
                if inner.get('Type') == 'MESSAGE' and inner.get('ParticipantRole') in ('SYSTEM', 'AGENT'):
                    bot_messages.append(inner.get('Content', ''))
        except:
            pass

    ws = websocket.WebSocketApp(ws_url, on_message=on_message)
    t = threading.Thread(target=ws.run_forever, daemon=True)
    t.start()
    return ws


def get_messages(conn_token):
    resp = participant.get_transcript(ConnectionToken=conn_token, MaxResults=50)
    msgs = []
    for item in resp.get('Transcript', []):
        if item.get('Type') == 'MESSAGE':
            who = item.get('ParticipantRole', '?')
            content = item.get('Content', '')
            msgs.append((who, content))
    return msgs


def main():
    print('=== Teste de Chat com Escalate (websocket) ===\n')

    resp = connect.start_chat_contact(
        InstanceId=INSTANCE_ID,
        ContactFlowId=FLOW_ID,
        Attributes={'phone': TEST_PHONE},
        ParticipantDetails={'DisplayName': 'TesteWembley'},
        SupportedMessagingContentTypes=['text/plain', 'text/markdown']
    )
    contact_id = resp['ContactId']
    participant_token = resp['ParticipantToken']
    print(f'ContactId: {contact_id}')

    conn = participant.create_participant_connection(
        Type=['WEBSOCKET', 'CONNECTION_CREDENTIALS'],
        ParticipantToken=participant_token
    )
    conn_token = conn['ConnectionCredentials']['ConnectionToken']
    ws_url = conn['Websocket']['Url']
    print('Conexao criada, conectando websocket...')

    ws = start_websocket(ws_url)
    time.sleep(3)
    # Send subscribe message to the websocket topic
    try:
        ws.send(json.dumps({"topic": "aws/subscribe", "content": {"topics": ["aws/chat"]}}))
    except Exception as e:
        print(f'subscribe err: {e}')

    time.sleep(10)  # wait for bot greeting

    script = [
        'Ola, tenho uma reclamacao sobre minha mensalidade',
        'Voces cobraram um valor errado e estou muito insatisfeito! Quero falar com um atendente humano agora',
    ]

    for msg in script:
        print(f'>> Cliente: {msg}')
        send_message(conn_token, msg)
        time.sleep(15)

    print('\n=== Transcript ===')
    for who, content in get_messages(conn_token):
        print(f'  [{who}] {content[:150]}')

    print(f'\nContactId para checar logs: {contact_id}')
    time.sleep(5)
    return contact_id

    print(f'\nContactId para checar logs: {contact_id}')
    print('Aguardando 5s para o flow processar o escalate...')
    time.sleep(5)
    return contact_id


if __name__ == '__main__':
    cid = main()
    print(f'\n=== Agora rode: ===')
    print(f"checar briefing attrs do contato {cid} nos logs do flow")
