# Lambda: wpp-gateway-outbound
# Runtime: python3.12 | Arch: x86_64 | Timeout: 60s | Memory: 512MB
# Layers: ffmpeg-layer (x86)
# Role: LambdaWppGatewayRole
# Env: SESSIONS_TABLE, MEDIA_BUCKET, POLLY_VOICE, POLLY_ENGINE, POLLY_LANG, META_API_VERSION
"""
Gateway de SAIDA Amazon Connect -> WhatsApp.

Acionado por SNS do contact streaming do chat (StartContactStreaming).
Para cada mensagem publicada pelo bot (SYSTEM) ou atendente humano (AGENT):
  - descobre telefone + numero de origem + last_modality pela sessao (DynamoDB, por contactId)
  - se last_modality == 'voice': Polly (Camila generative pt-BR) -> ffmpeg OGG/Opus
                                 -> post_whatsapp_message_media -> envia nota de voz (voice:true)
  - senao: envia texto
Mensagens do participante CUSTOMER sao ignoradas (evita echo do que injetamos).
Eventos de fim de chat removem a sessao.
"""
import json
import os
import decimal
import logging
import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
SESSIONS_TABLE = os.environ.get('SESSIONS_TABLE', 'whatsapp-connect-sessions')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', '')
POLLY_VOICE = os.environ.get('POLLY_VOICE', 'Camila')
POLLY_ENGINE = os.environ.get('POLLY_ENGINE', 'generative')
POLLY_LANG = os.environ.get('POLLY_LANG', 'pt-BR')
META_API_VERSION = os.environ.get('META_API_VERSION', 'v20.0')

import time
DEBOUNCE_SECONDS = float(os.environ.get('DEBOUNCE_SECONDS', '3'))

social = boto3.client('socialmessaging', region_name=REGION)
polly = boto3.client('polly', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)
participant = boto3.client('connectparticipant', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sessions = dynamodb.Table(SESSIONS_TABLE)


def get_session(contact_id):
    resp = sessions.query(KeyConditionExpression=Key('contactId').eq(contact_id))
    return resp['Items'][0] if resp.get('Items') else None


def delete_session(contact_id):
    try:
        sessions.delete_item(Key={'contactId': contact_id})
    except Exception as e:
        logger.error(f'delete_session error: {e}')


import re
_PROGRESS_MARKERS = [
    'vou verificar', 'vou consultar', 'vou buscar', 'vou identificar', 'vou acessar',
    'vou checar', 'vou analisar', 'agora vou', 'deixe-me identific', 'deixa eu verific',
    'deixe-me verific', 'deixe-me buscar', 'um momento', 'so um momento', 'só um momento',
    'aguarde', 'estou verificando', 'estou consultando', 'permita-me',
]

def is_noise(text):
    """Suprime ruido: vazio, so pontuacao/reticencias ('...', '…'), ou muito curto."""
    t = (text or '').strip()
    if not t:
        return True
    if re.sub(r'[\s.\u2026,;:!?_\-]', '', t) == '':  # so pontuacao/reticencias/espaco
        return True
    return len(t) < 3


def is_progress_message(text):
    """Rede de seguranca: suprime mensagens curtas de 'progresso' (o orchestrator emite
    uma antes de cada tool call). O outbound so encaminha a resposta final."""
    t = (text or '').strip().lower()
    if len(t) > 200:
        return False  # respostas de verdade tendem a ser mais longas
    return any(mk in t for mk in _PROGRESS_MARKERS)


def extract_text(streaming_msg):
    """Extrai texto enviavel de uma mensagem de streaming do chat."""
    content_type = streaming_msg.get('ContentType', '')
    content = streaming_msg.get('Content', '')
    if content_type in ('text/plain', 'text/markdown'):
        return content
    # Mensagem interativa do Lex (botoes/listas): extrai um fallback textual
    if 'interactive' in content_type:
        try:
            data = json.loads(content)
            tmpl = data.get('templateType', '')
            d = data.get('data', {}).get('content', {})
            title = d.get('title', '')
            subtitle = d.get('subtitle', '')
            elements = d.get('elements', [])
            opts = '\n'.join(f'- {e.get("title", "")}' for e in elements)
            parts = [p for p in [title, subtitle, opts] if p]
            return '\n'.join(parts) if parts else ''
        except Exception:
            return ''
    return content if isinstance(content, str) else ''


def synth_voice_ogg(text, contact_id):
    """Polly -> mp3 -> ffmpeg OGG/Opus mono. Retorna key no S3 ou None."""
    import subprocess, tempfile
    # 1. Polly (com fallback de engine)
    audio_mp3 = None
    for engine in [POLLY_ENGINE, 'neural', 'standard']:
        try:
            r = polly.synthesize_speech(
                Text=text[:2900], OutputFormat='mp3',
                VoiceId=POLLY_VOICE, Engine=engine, LanguageCode=POLLY_LANG)
            audio_mp3 = r['AudioStream'].read()
            logger.info(f'polly ok (engine={engine}, {len(audio_mp3)} bytes)')
            break
        except Exception as e:
            logger.error(f'polly engine={engine} falhou: {e}')
    if not audio_mp3:
        return None

    tmp = tempfile.mkdtemp()
    local_mp3 = os.path.join(tmp, 'tts.mp3')
    local_ogg = os.path.join(tmp, 'tts.ogg')
    try:
        with open(local_mp3, 'wb') as f:
            f.write(audio_mp3)
        cmd = ['/opt/bin/ffmpeg', '-y', '-i', local_mp3,
               '-c:a', 'libopus', '-b:a', '24k', '-ac', '1', '-application', 'voip', local_ogg]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            logger.error(f'ffmpeg opus falhou: {res.stderr[:300]}')
            return None
        key = f'outbound/{contact_id}/{abs(hash(text)) % 10_000_000}.ogg'
        # ContentType audio/ogg e OBRIGATORIO: o PostWhatsAppMessageMedia le o
        # ContentType do objeto S3 e rejeita binary/octet-stream.
        s3.upload_file(local_ogg, MEDIA_BUCKET, key, ExtraArgs={'ContentType': 'audio/ogg'})
        return key
    except Exception as e:
        logger.error(f'synth_voice_ogg error: {e}')
        return None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def wa_send(origination_id, payload):
    social.send_whatsapp_message(
        originationPhoneNumberId=origination_id,
        message=bytes(json.dumps(payload), 'utf-8'),
        metaApiVersion=META_API_VERSION,
    )


def send_text(origination_id, phone, text):
    to = phone if phone.startswith('+') else '+' + phone
    if len(text) > 4096:
        text = text[:4093] + '...'
    wa_send(origination_id, {
        'messaging_product': 'whatsapp', 'recipient_type': 'individual',
        'to': to, 'type': 'text', 'text': {'preview_url': False, 'body': text}})
    logger.info(f'texto enviado -> {to}')


def send_voice(origination_id, phone, ogg_key):
    to = phone if phone.startswith('+') else '+' + phone
    media = social.post_whatsapp_message_media(
        originationPhoneNumberId=origination_id,
        sourceS3File={'bucketName': MEDIA_BUCKET, 'key': ogg_key})
    media_id = media['mediaId']
    wa_send(origination_id, {
        'messaging_product': 'whatsapp', 'recipient_type': 'individual',
        'to': to, 'type': 'audio', 'audio': {'id': media_id, 'voice': True}})
    logger.info(f'nota de voz enviada -> {to} (media {media_id})')


def process_streaming_message(msg):
    msg_type = msg.get('Type', '')
    role = msg.get('ParticipantRole', '')
    contact_id = msg.get('ContactId', '')

    if not contact_id:
        return

    # Fim de chat -> limpa sessao
    if msg_type == 'EVENT':
        ct = msg.get('ContentType', '')
        if ct.endswith('chat.ended') or ct.endswith('participant.left'):
            # so limpa quando o chat encerra de fato
            if ct.endswith('chat.ended'):
                delete_session(contact_id)
        return

    # Ignora o proprio cliente (evita echo do que injetamos)
    if role == 'CUSTOMER':
        return

    if msg_type not in ('MESSAGE', 'ATTACHMENT'):
        return

    session = get_session(contact_id)
    if not session:
        logger.info(f'sem sessao pra contact {contact_id}, ignorando')
        return

    phone = session.get('customerId', '')
    origination_id = session.get('systemNumber', '')
    modality = session.get('last_modality', 'text')

    if msg_type == 'ATTACHMENT':
        # anexo do atendente -> encaminha via signed url (imagem/doc/audio)
        forward_agent_attachment(msg, session, origination_id, phone)
        return

    text = extract_text(msg)
    if not text or not text.strip():
        return  # nao enviar mensagem vazia (sem filtro de conteudo)

    # COALESCE por turno (nao e filtro de conteudo): o orchestrator emite uma mensagem
    # 'trabalhando...' antes de cada tool call + a resposta final. Registramos esta mensagem
    # e esperamos um instante; se o bot emitir outra logo depois, esta era intermediaria e
    # nao e enviada. A ULTIMA mensagem do turno (a final) sempre passa.
    msg_id = msg.get('Id', '')
    if msg_id:
        try:
            sessions.update_item(
                Key={'contactId': contact_id},
                UpdateExpression='SET last_bot_msg_id = :i',
                ExpressionAttributeValues={':i': msg_id})
            time.sleep(DEBOUNCE_SECONDS)
            cur = get_session(contact_id)
            if cur and cur.get('last_bot_msg_id') and cur.get('last_bot_msg_id') != msg_id:
                logger.info(f'msg intermediaria superada (coalesce), nao envia: {text[:60]!r}')
                return
        except Exception as e:
            logger.error(f'debounce error (envia mesmo assim): {e}')

    if modality == 'voice':
        ogg_key = synth_voice_ogg(text, contact_id)
        if ogg_key:
            try:
                send_voice(origination_id, phone, ogg_key)
                return
            except Exception as e:
                logger.error(f'send_voice falhou, caindo pra texto: {e}')
        # fallback pra texto se a sintese/envio falhar
    send_text(origination_id, phone, text)


def forward_agent_attachment(msg, session, origination_id, phone):
    """Encaminha anexo do atendente pro WhatsApp via signed URL da Participant API."""
    try:
        attachments = msg.get('Attachments', [])
        connection_token = session.get('connectionToken')
        to = phone if phone.startswith('+') else '+' + phone
        for att in attachments:
            if att.get('Status') != 'APPROVED':
                continue
            att_id = att.get('AttachmentId')
            content_type = att.get('ContentType', '')
            name = att.get('AttachmentName', 'file')
            url = participant.get_attachment(AttachmentId=att_id, ConnectionToken=connection_token)['Url']
            if content_type.startswith('image/'):
                wtype, body = 'image', {'link': url}
            elif content_type.startswith('video/'):
                wtype, body = 'video', {'link': url}
            elif content_type.startswith('audio/'):
                wtype, body = 'audio', {'link': url}
            else:
                wtype, body = 'document', {'link': url, 'filename': name}
            wa_send(origination_id, {
                'messaging_product': 'whatsapp', 'recipient_type': 'individual',
                'to': to, 'type': wtype, wtype: body})
            logger.info(f'anexo do atendente encaminhado ({wtype}) -> {to}')
    except Exception as e:
        logger.error(f'forward_agent_attachment error: {e}')


def lambda_handler(event, context):
    logger.info(json.dumps(event)[:2000])

    # --- autoteste (nao e caminho de producao; streaming SNS nunca envia _selftest) ---
    st = event.get('_selftest')
    if st:
        if st.get('action') == 'synth':
            key = synth_voice_ogg(st.get('text', 'Ola, teste de voz.'), 'selftest')
            return {'ok': bool(key), 'ogg_key': key, 'bucket': MEDIA_BUCKET}
        return {'ok': False, 'error': 'acao de selftest desconhecida'}

    for record in event.get('Records', []):
        sns = record.get('Sns', {})
        try:
            msg = json.loads(sns.get('Message', '{}'), parse_float=decimal.Decimal)
        except Exception as e:
            logger.error(f'parse streaming msg error: {e}')
            continue
        try:
            process_streaming_message(msg)
        except Exception as e:
            logger.exception(f'process_streaming_message error: {e}')
    return {'statusCode': 200}
