# Lambda: connect-customer-timeline
# Runtime: python3.12 | Timeout: 30s | Memory: 256MB
# Role: LambdaCustomerTimelineRole
# Env vars: CONNECT_INSTANCE_ID
"""
Compila a linha do tempo de TODAS as interacoes do cliente.
Busca contatos passados (search_contacts), casa pelo telefone (get_contact_attributes),
recupera resumos armazenados (briefing_resumo) e, quando ausente, gera um resumo a partir
do transcript (Contact Lens) com Bedrock.

Input (via Connect Invoke Lambda): contact attributes com 'phone'
Output: timeline_markdown, timeline_count, e ate 10 entradas estruturadas (item_N_*)
"""
import json
import boto3
import os
import datetime

connect = boto3.client('connect')
bedrock = boto3.client('bedrock-runtime')

INSTANCE_ID = os.environ['CONNECT_INSTANCE_ID']
MAX_DAYS = 55          # limite da API (1345h)
MAX_CONTACTS = 30
MAX_TIMELINE = 10      # entradas exibidas

CHANNEL_PT = {'CHAT': 'Chat/WhatsApp', 'VOICE': 'Telefone', 'TASK': 'Tarefa', 'EMAIL': 'E-mail'}


def get_transcript(contact_id):
    try:
        lines = []
        resp = connect.list_realtime_contact_analysis_segments_v2(
            InstanceId=INSTANCE_ID, ContactId=contact_id,
            OutputType='Raw', SegmentTypes=['Transcript'])
        for s in resp.get('Segments', []):
            t = s.get('Transcript', {})
            content = (t.get('Content', '') or '').strip()
            if content:
                who = 'Cliente' if t.get('ParticipantRole') == 'CUSTOMER' else 'Assistente'
                lines.append(f"{who}: {content}")
        return "\n".join(lines)
    except Exception:
        return ""


def summarize(transcript):
    if not transcript:
        return ""
    prompt = (
        "Resuma em 1 frase objetiva (max 25 palavras), em portugues, o motivo/desfecho "
        "desta interacao de atendimento. Responda apenas o resumo, sem prefixos.\n\n" + transcript[:4000]
    )
    try:
        resp = bedrock.invoke_model(
            modelId='us.anthropic.claude-haiku-4-5-20251001-v1:0',
            body=json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 120,
                             "messages": [{"role": "user", "content": prompt}]}))
        return json.loads(resp['body'].read())['content'][0]['text'].strip()
    except Exception:
        return ""


def lambda_handler(event, context):
    print(f"Event: {json.dumps(event, default=str)}")
    details = event.get('Details', {})
    contact_data = details.get('ContactData', {})
    attributes = contact_data.get('Attributes') or {}
    phone = attributes.get('phone', '')
    if not phone:
        ce = contact_data.get('CustomerEndpoint') or {}
        phone = ce.get('Address', '')
    current_id = contact_data.get('ContactId', '')

    if not phone:
        return {"timeline_markdown": "Sem identificacao do cliente.", "timeline_count": "0"}

    now = datetime.datetime.utcnow()
    start = now - datetime.timedelta(days=MAX_DAYS)

    try:
        resp = connect.search_contacts(
            InstanceId=INSTANCE_ID,
            TimeRange={'Type': 'INITIATION_TIMESTAMP', 'StartTime': start, 'EndTime': now},
            SearchCriteria={'Channels': ['CHAT', 'VOICE', 'TASK', 'EMAIL']},
            Sort={'FieldName': 'INITIATION_TIMESTAMP', 'Order': 'DESCENDING'},
            MaxResults=MAX_CONTACTS)
    except Exception as e:
        print(f"search_contacts error: {e}")
        return {"timeline_markdown": "Erro ao buscar historico.", "timeline_count": "0"}

    interactions = []
    for c in resp.get('Contacts', []):
        cid = c['Id']
        if cid == current_id:
            continue
        try:
            attrs = connect.get_contact_attributes(InstanceId=INSTANCE_ID, InitialContactId=cid).get('Attributes', {})
        except Exception:
            attrs = {}
        if attrs.get('phone') != phone:
            continue

        ts = c.get('InitiationTimestamp')
        channel = CHANNEL_PT.get(c.get('Channel', ''), c.get('Channel', ''))
        resumo = attrs.get('briefing_resumo', '').strip()
        sentimento = attrs.get('briefing_sentimento', '').strip()
        intencao = attrs.get('briefing_intencao', '').strip()
        if not resumo:
            resumo = summarize(get_transcript(cid))
        if not resumo:
            resumo = 'Interacao sem resumo registrado.'

        interactions.append({
            'ts': ts, 'channel': channel, 'resumo': resumo,
            'sentimento': sentimento, 'intencao': intencao
        })
        if len(interactions) >= MAX_TIMELINE:
            break

    # Build markdown timeline
    if not interactions:
        md = 'Nenhuma interacao anterior registrada para este cliente.'
    else:
        parts = [f'## Linha do Tempo de Interacoes ({len(interactions)})\n']
        for it in interactions:
            ts = it['ts']
            data_fmt = ts.strftime('%d/%m/%Y %H:%M') if hasattr(ts, 'strftime') else str(ts)
            line = f"### {data_fmt} - {it['channel']}\n{it['resumo']}"
            extra = []
            if it['sentimento']:
                extra.append(f"Sentimento: {it['sentimento']}")
            if it['intencao']:
                extra.append(f"Intencao: {it['intencao']}")
            if extra:
                line += f"\n_{' | '.join(extra)}_"
            parts.append(line)
        md = "\n\n".join(parts)

    result = {"timeline_markdown": md, "timeline_count": str(len(interactions))}

    # Also expose first entries as flat fields (for views that don't render markdown)
    for i, it in enumerate(interactions[:MAX_TIMELINE], 1):
        ts = it['ts']
        data_fmt = ts.strftime('%d/%m/%Y %H:%M') if hasattr(ts, 'strftime') else str(ts)
        result[f'item_{i}_data'] = f"{data_fmt} - {it['channel']}"
        result[f'item_{i}_resumo'] = it['resumo'][:300]

    print(f"Timeline: {len(interactions)} interacoes")
    return result
