# Lambda: wpp-gateway-inbound
# Runtime: python3.12 | Arch: x86_64 | Timeout: 120s | Memory: 512MB
# Layers: ffmpeg-layer (x86), amazon-transcribe-layer
# Role: LambdaWppGatewayRole
# Env: SESSIONS_TABLE, MEDIA_BUCKET, CONNECT_INSTANCE_ID, CONNECT_FLOW_ID,
#      STREAMING_TOPIC_ARN, CHAT_DURATION_MINUTES, TRANSCRIBE_LANG, META_API_VERSION
"""
Gateway de ENTRADA WhatsApp -> Amazon Connect (substitui o event destination nativo).

Fluxo (acionado por SNS do End User Messaging Social):
  1. Faz parse do evento SNS -> webhook entry (contacts, messages, metadata, context).
  2. Para cada mensagem:
     - texto  -> texto direto (modalidade = texto)
     - audio  -> baixa OGG (get_whatsapp_message_media) -> Transcribe Streaming (pt-BR)
                 -> texto (modalidade = voz). Opcional: converte OGG->WAV e anexa no chat
                 pra o atendente humano ouvir.
  3. Sessao existente (DynamoDB por telefone) -> send_message via connectionToken.
     Sessao nova -> StartChatContact (mesmo flow) + StartContactStreaming + participant conn.
  4. Grava/atualiza a sessao com last_modality (o outbound usa pra responder no mesmo formato).

Preserva screen pop / copiloto / briefing porque entra no MESMO contact flow.
"""
import json
import os
import time
import decimal
import logging
import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
SESSIONS_TABLE = os.environ.get('SESSIONS_TABLE', 'whatsapp-connect-sessions')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', '')
INSTANCE_ID = os.environ.get('CONNECT_INSTANCE_ID', '')
CONTACT_FLOW_ID = os.environ.get('CONNECT_FLOW_ID', '')
STREAMING_TOPIC_ARN = os.environ.get('STREAMING_TOPIC_ARN', '')
CHAT_DURATION_MINUTES = int(os.environ.get('CHAT_DURATION_MINUTES', '60'))
TRANSCRIBE_LANG = os.environ.get('TRANSCRIBE_LANG', 'pt-BR')
META_API_VERSION = os.environ.get('META_API_VERSION', 'v20.0')
ATTACH_AUDIO_TO_CHAT = os.environ.get('ATTACH_AUDIO_TO_CHAT', 'true').lower() == 'true'

VISION_MODEL = os.environ.get('VISION_MODEL', 'us.anthropic.claude-haiku-4-5-20251001-v1:0')

social = boto3.client('socialmessaging', region_name=REGION)
connect = boto3.client('connect', region_name=REGION)
participant = boto3.client('connectparticipant', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)
bedrock = boto3.client('bedrock-runtime', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sessions = dynamodb.Table(SESSIONS_TABLE)


# ----------------------------- SNS / webhook parsing -----------------------------
def parse_sns_records(event):
    """Extrai as mensagens WhatsApp normalizadas de um evento SNS do EUM Social."""
    parsed = []
    for record in event.get('Records', []):
        sns = record.get('Sns', {})
        try:
            sns_message = json.loads(sns.get('Message', '{}'), parse_float=decimal.Decimal)
        except Exception as e:
            logger.error(f'SNS message parse error: {e}')
            continue

        context = sns_message.get('context', {})
        meta_phone_numbers = context.get('MetaPhoneNumberIds', [])
        try:
            webhook_entry = json.loads(sns_message.get('whatsAppWebhookEntry', '{}'))
        except Exception as e:
            logger.error(f'webhook entry parse error: {e}')
            continue

        for change in webhook_entry.get('changes', []):
            value = change.get('value', {})
            if change.get('field') != 'messages':
                continue
            metadata = value.get('metadata', {})
            contacts = value.get('contacts', [])
            meta_phone_number_id = metadata.get('phone_number_id', '')
            origination_arn = _resolve_origination_arn(meta_phone_numbers, meta_phone_number_id)
            for message in value.get('messages', []):
                parsed.append({
                    'message': message,
                    'contacts': contacts,
                    'origination_arn': origination_arn,
                })
    return parsed


def _resolve_origination_arn(meta_phone_numbers, meta_phone_number_id):
    """Nosso numero de negocio (ARN) a partir do phone_number_id do Meta."""
    for pn in meta_phone_numbers:
        if pn.get('metaPhoneNumberId') == meta_phone_number_id:
            return pn.get('arn', '')
    if meta_phone_numbers:
        return meta_phone_numbers[0].get('arn', '')
    return ''


def _origination_id_from_arn(arn):
    # arn:aws:social-messaging:region:acct:phone-number-id/xxxx -> phone-number-id-xxxx
    return arn.split(':')[-1].replace('/', '-') if arn else ''


def _customer_name(message, contacts):
    wa_id = message.get('from', '')
    for c in contacts:
        if c.get('wa_id') == wa_id:
            return c.get('profile', {}).get('name', 'Cliente')
    return 'Cliente'


def detect_modality_override(text):
    """Se o usuario pedir explicitamente o formato da resposta, honra o pedido.
    Retorna 'text', 'voice' ou None (mantem a regra padrao = mesmo formato da entrada)."""
    t = (text or '').lower()
    text_kw = ['por texto', 'por escrito', 'responde escrevendo', 'responda escrevendo',
               'me escreve', 'escreve pra mim', 'sem audio', 'sem áudio',
               'nao manda audio', 'não manda áudio', 'por mensagem', 'responde por texto',
               'responda por texto', 'responde por escrito', 'responda por escrito']
    voice_kw = ['por audio', 'por áudio', 'por voz', 'manda audio', 'manda áudio',
                'manda um audio', 'manda um áudio', 'responde falando', 'responda falando',
                'responde por audio', 'responda por audio', 'responde por áudio',
                'responda por áudio', 'me responde falando']
    if any(k in t for k in text_kw):
        return 'text'
    if any(k in t for k in voice_kw):
        return 'voice'
    return None


# ----------------------------- media / transcription -----------------------------
def download_media_to_s3(media_id, origination_arn, phone):
    """Baixa uma midia (audio, imagem, doc) do WhatsApp pro S3. Retorna (bucket, key).
    OBS: get_whatsapp_message_media trata 'key' como PREFIXO e anexa o nome do
    arquivo. Por isso passamos um prefixo e descobrimos a key real via list."""
    prefix = f'inbound/{phone}/{media_id}/'
    social.get_whatsapp_message_media(
        mediaId=media_id,
        originationPhoneNumberId=origination_arn,
        destinationS3File={'bucketName': MEDIA_BUCKET, 'key': prefix},
    )
    resp = s3.list_objects_v2(Bucket=MEDIA_BUCKET, Prefix=prefix)
    objs = resp.get('Contents', [])
    if not objs:
        raise RuntimeError(f'media nao encontrada apos download em {prefix}')
    key = objs[0]['Key']
    logger.info(f'midia baixada: s3://{MEDIA_BUCKET}/{key}')
    return MEDIA_BUCKET, key


def interpret_image(bucket, key, caption=''):
    """Interpreta a imagem com Claude (visao) e retorna uma transcricao/descricao
    fiel do conteudo (textos, questoes, respostas, diagramas)."""
    import base64
    obj = s3.get_object(Bucket=bucket, Key=key)
    img = obj['Body'].read()
    ext = key.rsplit('.', 1)[-1].lower()
    media_type = {'png': 'image/png', 'webp': 'image/webp', 'gif': 'image/gif'}.get(ext, 'image/jpeg')
    instrucao = (
        "Voce recebeu uma imagem enviada por um aluno via WhatsApp. "
        "Transcreva FIELMENTE o conteudo relevante: enunciados de questoes, alternativas, "
        "respostas marcadas/escritas pelo aluno, formulas e dados de tabelas/diagramas. "
        "Seja CONCISO (no maximo ~160 palavras), preservando o essencial. NAO resolva nem "
        "corrija - apenas transcreva para outro assistente usar."
    )
    if caption:
        instrucao += f"\nLegenda enviada pelo aluno: {caption}"
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 500,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                          "data": base64.b64encode(img).decode()}},
            {"type": "text", "text": instrucao},
        ]}],
    }
    try:
        resp = bedrock.invoke_model(modelId=VISION_MODEL, body=json.dumps(body))
        text = json.loads(resp['body'].read())['content'][0]['text'].strip()
        logger.info(f'imagem interpretada ({len(text)} chars)')
        return text
    except Exception as e:
        logger.exception(f'interpret_image error: {e}')
        return ''


def transcribe_ogg(bucket, key):
    """Transcreve OGG/Opus via Amazon Transcribe Streaming (pt-BR). Retorna texto."""
    import asyncio
    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    from amazon_transcribe.model import TranscriptEvent

    SAMPLE_RATE = 48000
    CHUNK = 1024 * 16          # chunk maior = menos iteracoes
    PACE_DIVISOR = 3.0         # envia ~3x mais rapido que tempo real (reduz latencia)

    class Handler(TranscriptResultStreamHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.parts = []

        async def handle_transcript_event(self, ev: TranscriptEvent):
            for result in ev.transcript.results:
                if not result.is_partial:
                    for alt in result.alternatives:
                        self.parts.append(alt.transcript)

    async def run():
        client = TranscribeStreamingClient(region=REGION)
        stream = await client.start_stream_transcription(
            language_code=TRANSCRIBE_LANG,
            media_sample_rate_hz=SAMPLE_RATE,
            media_encoding='ogg-opus',
        )

        async def write_chunks():
            obj = s3.get_object(Bucket=bucket, Key=key)
            data = obj['Body'].read()
            import io
            buf = io.BytesIO(data)
            while True:
                chunk = buf.read(CHUNK)
                if not chunk:
                    break
                await stream.input_stream.send_audio_event(audio_chunk=chunk)
                await asyncio.sleep((CHUNK * 8) / (SAMPLE_RATE * 2 * PACE_DIVISOR))
            await stream.input_stream.end_stream()

        handler = Handler(stream.output_stream)
        await asyncio.gather(write_chunks(), handler.handle_events())
        return ' '.join(handler.parts).strip()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        text = loop.run_until_complete(run())
        logger.info(f'transcricao: {text!r}')
        return text
    except Exception as e:
        logger.error(f'transcribe error: {e}')
        return ''


def convert_ogg_to_wav(bucket, key):
    """Converte OGG/Opus -> WAV (16k mono) via ffmpeg. Retorna (bucket, wav_key) ou None."""
    import subprocess, tempfile
    tmp = tempfile.mkdtemp()
    local_ogg = os.path.join(tmp, 'in.ogg')
    local_wav = os.path.join(tmp, 'voice.wav')
    try:
        s3.download_file(bucket, key, local_ogg)
        cmd = ['/opt/bin/ffmpeg', '-y', '-i', local_ogg,
               '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', local_wav]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if r.returncode != 0:
            logger.error(f'ffmpeg falhou: {r.stderr[:300]}')
            return None
        wav_key = key.rsplit('.', 1)[0] + '.wav'
        s3.upload_file(local_wav, bucket, wav_key)
        return bucket, wav_key
    except Exception as e:
        logger.error(f'convert wav error: {e}')
        return None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------- Connect chat -----------------------------
def get_session_by_phone(phone):
    resp = sessions.query(
        IndexName='customerId-index',
        KeyConditionExpression=Key('customerId').eq(phone),
    )
    return resp['Items'][0] if resp.get('Items') else None


def contact_is_live(contact_id):
    """True se o contato ainda esta ativo (sem DisconnectTimestamp).
    Um chat que ja completou/desconectou nao recebe respostas do bot -> precisa
    iniciar um novo (igual ao comportamento nativo, que cria 1 contato por conversa)."""
    try:
        d = connect.describe_contact(InstanceId=INSTANCE_ID, ContactId=contact_id)['Contact']
        return d.get('DisconnectTimestamp') is None
    except Exception as e:
        logger.info(f'describe_contact falhou ({contact_id}): {e} -> tratando como morto')
        return False


def save_session(contact_id, phone, participant_token, connection_token, name, system_number, modality):
    sessions.put_item(Item={
        'contactId': contact_id,
        'customerId': phone,
        'participantToken': participant_token,
        'connectionToken': connection_token,
        'name': name,
        'systemNumber': system_number,
        'channel': 'Whatsapp',
        'last_modality': modality,
    })


def update_modality(contact_id, modality):
    try:
        sessions.update_item(
            Key={'contactId': contact_id},
            UpdateExpression='SET last_modality = :m',
            ExpressionAttributeValues={':m': modality},
        )
    except Exception as e:
        logger.error(f'update_modality error: {e}')


def delete_session(contact_id):
    try:
        sessions.delete_item(Key={'contactId': contact_id})
    except Exception as e:
        logger.error(f'delete_session error: {e}')


def start_chat_and_stream(text, phone, name, system_number, modality, source_contact_id=None):
    kwargs = dict(
        InstanceId=INSTANCE_ID,
        ContactFlowId=CONTACT_FLOW_ID,
        Attributes={
            'Channel': 'Whatsapp',
            'phone': phone,               # o flow le esse attribute (nao ha CustomerEndpoint em chat API)
            'customerId': phone,
            'customerName': name,
            'systemNumber': system_number,
            'input_modality': modality,
        },
        ParticipantDetails={'DisplayName': name},
        InitialMessage={'ContentType': 'text/plain', 'Content': text},
        ChatDurationInMinutes=CHAT_DURATION_MINUTES,
        SupportedMessagingContentTypes=[
            'text/plain', 'text/markdown', 'application/json',
            'application/vnd.amazonaws.connect.message.interactive',
            'application/vnd.amazonaws.connect.message.interactive.response',
        ],
    )
    # Persistent Chat: encadeia ao contato anterior e reidrata o historico inteiro
    # (memoria/contexto/identificacao mantidos entre mensagens, mesmo apos o contato morrer).
    if source_contact_id:
        kwargs['PersistentChat'] = {
            'RehydrationType': 'ENTIRE_PAST_SESSION',
            'SourceContactId': source_contact_id,
        }
    try:
        resp = connect.start_chat_contact(**kwargs)
    except Exception as e:
        # se o source expirou/invalido, refaz sem persistent chat
        if source_contact_id:
            logger.error(f'start_chat_contact com persistent falhou ({e}); refazendo sem rehydration')
            kwargs.pop('PersistentChat', None)
            resp = connect.start_chat_contact(**kwargs)
        else:
            raise
    contact_id = resp['ContactId']
    participant_token = resp['ParticipantToken']
    if STREAMING_TOPIC_ARN:
        try:
            connect.start_contact_streaming(
                InstanceId=INSTANCE_ID,
                ContactId=contact_id,
                ChatStreamingConfiguration={'StreamingEndpointArn': STREAMING_TOPIC_ARN},
            )
        except Exception as e:
            logger.error(f'start_contact_streaming error: {e}')
    conn = participant.create_participant_connection(
        Type=['CONNECTION_CREDENTIALS'],
        ParticipantToken=participant_token,
        ConnectParticipant=True,
    )
    connection_token = conn['ConnectionCredentials']['ConnectionToken']
    return contact_id, participant_token, connection_token


def send_to_connect(text, connection_token):
    try:
        participant.send_message(ContentType='text/plain', Content=text, ConnectionToken=connection_token)
        return True
    except participant.exceptions.AccessDeniedException:
        return False  # sessao expirada
    except Exception as e:
        logger.error(f'send_message error: {e}')
        return False


def upload_attachment(connection_token, content_bytes, filename, content_type):
    import sys, requests
    from urllib.parse import urlparse
    try:
        up = participant.start_attachment_upload(
            ContentType=content_type,
            AttachmentSizeInBytes=len(content_bytes),
            AttachmentName=filename,
            ConnectionToken=connection_token,
        )
        url = up['UploadMetadata']['Url']
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.netloc.endswith('.amazonaws.com'):
            logger.error('upload url rejeitada')
            return
        requests.put(url, data=content_bytes,
                     headers=up['UploadMetadata']['HeadersToInclude'], timeout=30).raise_for_status()
        participant.complete_attachment_upload(
            AttachmentIds=[up['AttachmentId']], ConnectionToken=connection_token)
        logger.info(f'anexo enviado ao chat: {filename}')
    except Exception as e:
        logger.error(f'upload_attachment error: {e}')


# ----------------------------- WhatsApp send helpers -----------------------------
def wa_send(origination_id, payload):
    social.send_whatsapp_message(
        originationPhoneNumberId=origination_id,
        message=bytes(json.dumps(payload), 'utf-8'),
        metaApiVersion=META_API_VERSION,
    )


def wa_mark_read(origination_arn, message_id):
    try:
        wa_send(origination_arn, {
            'messaging_product': 'whatsapp', 'status': 'read', 'message_id': message_id})
    except Exception as e:
        logger.error(f'mark_read error: {e}')


# ----------------------------- main per-message -----------------------------
def process_message(item):
    message = item['message']
    contacts = item['contacts']
    origination_arn = item['origination_arn']
    origination_id = _origination_id_from_arn(origination_arn)

    msg_type = message.get('type', '')
    phone = message.get('from', '')
    message_id = message.get('id', '')
    name = _customer_name(message, contacts)

    logger.info(f'MSG recebida: type={msg_type!r} phone={phone} keys={list(message.keys())}')

    if not phone:
        logger.info('mensagem sem telefone, ignorando')
        return

    wa_mark_read(origination_arn, message_id)

    modality = 'text'
    text = ''
    audio_s3 = None

    if msg_type == 'text':
        text = message.get('text', {}).get('body', '')
    elif msg_type == 'audio':
        modality = 'voice'
        media_id = message.get('audio', {}).get('id', '')
        logger.info(f'AUDIO detectado: media_id={media_id} bucket={MEDIA_BUCKET}')
        if media_id and MEDIA_BUCKET:
            try:
                bucket, key = download_media_to_s3(media_id, origination_arn, phone)
                audio_s3 = (bucket, key)
                text = transcribe_ogg(bucket, key)
                logger.info(f'AUDIO transcrito: {text!r}')
            except Exception as e:
                logger.exception(f'falha no pipeline de audio: {e}')
        if not text:
            text = '[nota de voz nao compreendida]'
    elif msg_type == 'image':
        # imagem: visao (Claude) interpreta -> texto injetado no chat. Responde em texto.
        modality = 'text'
        media_id = message.get('image', {}).get('id', '')
        caption = message.get('image', {}).get('caption', '')
        logger.info(f'IMAGEM detectada: media_id={media_id} caption={caption!r}')
        if media_id and MEDIA_BUCKET:
            try:
                bucket, key = download_media_to_s3(media_id, origination_arn, phone)
                descricao = interpret_image(bucket, key, caption)
                if descricao:
                    prefixo = f'{caption}\n\n' if caption else ''
                    text = (f'{prefixo}[O cliente enviou uma imagem. Conteudo identificado na '
                            f'imagem abaixo. Use-o para atender o pedido do cliente '
                            f'(ex: corrigir, explicar, resolver).]\n\n{descricao}')
            except Exception as e:
                logger.exception(f'falha no pipeline de imagem: {e}')
        if not text:
            text = '[o cliente enviou uma imagem, mas nao foi possivel interpreta-la. '\
                   'Peca desculpas e sugira reenviar a foto com boa iluminacao.]'
    else:
        # documento/video/etc: marcador (evolucao futura)
        text = f'[mensagem do tipo {msg_type}]'

    # Se o usuario pediu explicitamente o formato da resposta, sobrepoe a regra padrao
    override = detect_modality_override(text)
    if override:
        logger.info(f'modalidade sobrescrita por pedido do usuario: {modality} -> {override}')
        modality = override

    text_for_connect = (text or '').strip()[:1024] or 'Nova conversa'

    # MEMORIA via Persistent Chat:
    # - Se ha contato VIVO, reusa (memoria in-session, sem re-identificar).
    # - Se morreu/nao existe, abre um contato NOVO ENCADEADO ao anterior (rehydration do
    #   historico inteiro) e envia a mensagem real como TURNO 2. Assim o contexto e a
    #   identificacao continuam mesmo apos o contato expirar (~5min).
    session = get_session_by_phone(phone)
    prev_contact_id = session['contactId'] if session else None
    contact_id = None
    connection_token = None

    if session and contact_is_live(session['contactId']):
        connection_token = session.get('connectionToken')
        if send_to_connect(text_for_connect, connection_token):
            contact_id = session['contactId']
            update_modality(contact_id, modality)
        else:
            connection_token = None  # expirou -> abre novo com rehydration

    if not contact_id:
        contact_id, participant_token, connection_token = start_chat_and_stream(
            ' ', phone, name, origination_id, modality, source_contact_id=prev_contact_id)
        time.sleep(5)  # deixa o turno 1 assentar antes do turno 2
        send_to_connect(text_for_connect, connection_token)
        if prev_contact_id:
            delete_session(prev_contact_id)
        save_session(contact_id, phone, participant_token, connection_token,
                     name, origination_id, modality)

    # Anexa o audio original no chat pra o atendente humano poder ouvir
    if audio_s3 and ATTACH_AUDIO_TO_CHAT and connection_token:
        conv = convert_ogg_to_wav(*audio_s3)
        if conv:
            try:
                wav_obj = s3.get_object(Bucket=conv[0], Key=conv[1])
                upload_attachment(connection_token, wav_obj['Body'].read(),
                                  'voice.wav', 'audio/wav')
            except Exception as e:
                logger.error(f'anexo audio error: {e}')

    logger.info(f'processado: phone={phone} modality={modality} contact={contact_id}')


def lambda_handler(event, context):
    logger.info(json.dumps(event)[:2000])

    # --- autoteste (nao e caminho de producao; SNS/WhatsApp nunca enviam _selftest) ---
    st = event.get('_selftest')
    if st:
        action = st.get('action')
        if action == 'transcribe':
            text = transcribe_ogg(st['bucket'], st['key'])
            return {'ok': True, 'transcription': text}
        return {'ok': False, 'error': 'acao de selftest desconhecida'}

    if not (INSTANCE_ID and CONTACT_FLOW_ID):
        logger.error('CONNECT_INSTANCE_ID / CONNECT_FLOW_ID nao configurados')
        return {'statusCode': 200, 'body': 'missing config'}
    for item in parse_sns_records(event):
        try:
            process_message(item)
        except Exception as e:
            logger.exception(f'process_message error: {e}')
    return {'statusCode': 200}
