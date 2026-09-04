"""
Cria um fluxo de VOZ inbound (connect-voice-inbound) clonando a logica do
connect-whatsapp-interaction, adaptado para voz:
- Adiciona voz TTS pt-BR (Camila, Generative)
- Troca recording/analytics de Chat para Voice
- Mantem IDENTICOS: AI agent self-service, escalate -> briefing (lambda) -> timeline ->
  event hook (DefaultAgentUI screen pop) -> copiloto -> BasicQueue -> transfer

Reaproveita: connect-agent-briefing, connect-customer-timeline, agent-briefing-screen-pop,
view briefing-atendente, fila BasicQueue, AI agent self-service.

Uso: source .env && python3 scripts/create_voice_inbound_flow.py
"""
import boto3
import json
import sys

REGION = 'us-east-1'
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
MAIN_FLOW_ID = 'acd511ac-afee-403b-9436-aa52f2f744cc'
VOICE_FLOW_NAME = 'connect-voice-inbound'

connect = boto3.client('connect', region_name=REGION)

# 1. Pega o conteudo do fluxo principal (WhatsApp) como base
f = connect.describe_contact_flow(InstanceId=INSTANCE_ID, ContactFlowId=MAIN_FLOW_ID)['ContactFlow']
content = json.loads(f['Content'])
print(f'Base: {f["Name"]} ({len(content["Actions"])} blocos)')

# 2. Adaptar bloco de recording/analytics: Chat -> Voice (formato validado)
for a in content['Actions']:
    if a.get('Type') == 'UpdateContactRecordingAndAnalyticsBehavior':
        a['Parameters'] = {
            'VoiceBehavior': {
                'VoiceRecordingBehavior': {'RecordedParticipants': ['Agent', 'Customer'], 'IVRRecordingBehavior': 'Enabled'},
                'VoiceAnalyticsBehavior': {
                    'Enabled': 'True',
                    'AnalyticsLanguage': 'pt-BR',
                    'AnalyticsModes': ['RealTime', 'AutomatedInteraction'],
                    'ConversationalAnalyticsRedactionConfiguration': {'Enabled': 'False'},
                    'SentimentConfiguration': {'Enabled': 'True'}
                }
            }
        }
        # Limpar transicoes de erro chat-especificas (ChannelMismatch/InFlightRedaction)
        nxt = a['Transitions'].get('NextAction')
        a['Transitions']['Errors'] = [
            {'NextAction': nxt, 'ErrorType': 'NoMatchingError'},
            {'NextAction': nxt, 'ErrorType': 'ChannelMismatch'}
        ]
        print('  Recording/analytics adaptado para Voice')

# 3. Inserir bloco de voz TTS (Camila, Generative, pt-BR) logo apos enable-logging
TTS_ID = 'set-tts-voice'
start_action = content['StartAction']  # enable-logging
# Descobrir para onde enable-logging aponta
enable_next = None
for a in content['Actions']:
    if a.get('Identifier') == start_action:
        enable_next = a['Transitions'].get('NextAction')

tts_block = {
    'Identifier': TTS_ID,
    'Type': 'UpdateContactTextToSpeechVoice',
    'Parameters': {'TextToSpeechVoice': 'Camila', 'TextToSpeechEngine': 'Generative', 'TextToSpeechStyle': 'None'},
    'Transitions': {'NextAction': enable_next, 'Errors': [{'NextAction': enable_next, 'ErrorType': 'NoMatchingError'}]}
}
content['Actions'] = [a for a in content['Actions'] if a.get('Identifier') != TTS_ID]
content['Actions'].append(tts_block)
# enable-logging passa a apontar para o TTS
for a in content['Actions']:
    if a.get('Identifier') == start_action:
        a['Transitions']['NextAction'] = TTS_ID
content.setdefault('Metadata', {}).setdefault('ActionMetadata', {})[TTS_ID] = {'position': {'x': -60, 'y': 200}}
print('  Bloco TTS voz pt-BR (Camila) inserido')

# 4. Criar o novo fluxo de voz
try:
    resp = connect.create_contact_flow(
        InstanceId=INSTANCE_ID, Name=VOICE_FLOW_NAME, Type='CONTACT_FLOW',
        Content=json.dumps(content),
        Description='Voz inbound (toll-free) - mesma logica do WhatsApp: AI agent, escalate, briefing, timeline, BasicQueue')
    flow_id = resp['ContactFlowId']
    print(f'\nFluxo de voz criado: {flow_id}')
    print(f'ARN: {resp["ContactFlowArn"]}')
except connect.exceptions.DuplicateResourceException:
    # Atualiza se ja existir
    flows = connect.list_contact_flows(InstanceId=INSTANCE_ID, ContactFlowTypes=['CONTACT_FLOW'])
    flow_id = next((x['Id'] for x in flows['ContactFlowSummaryList'] if x['Name'] == VOICE_FLOW_NAME), None)
    connect.update_contact_flow_content(InstanceId=INSTANCE_ID, ContactFlowId=flow_id, Content=json.dumps(content))
    print(f'\nFluxo de voz atualizado: {flow_id}')

print(f'''
=== Proximo passo: associar o toll-free ao fluxo ===
O numero +18667787229 deve ser apontado para o fluxo "{VOICE_FLOW_NAME}".
Isso e feito no console: Channels/Phone numbers > +18667787229 > Contact flow/IVR > {VOICE_FLOW_NAME}
(ou via API associate_phone_number_contact_flow, se disponivel - o script tenta a seguir)

Flow ID: {flow_id}
''')

# 5. Tenta associar o toll-free ao fluxo via API
TOLLFREE_ID = '3f5225f6-991a-4371-9073-2505da132c05'
try:
    connect.associate_phone_number_contact_flow(
        PhoneNumberId=TOLLFREE_ID, InstanceId=INSTANCE_ID, ContactFlowId=flow_id)
    print('Toll-free associado ao fluxo de voz via API!')
except Exception as e:
    print(f'Associacao via API falhou ({type(e).__name__}). Faca pelo console.')
