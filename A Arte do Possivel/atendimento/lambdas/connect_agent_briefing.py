# Lambda: connect-agent-briefing
# Runtime: python3.12 | Timeout: 30s | Memory: 256MB
# Role: LambdaAgentBriefingRole
# Env vars: FOTOS_BUCKET, CONNECT_INSTANCE_ID
"""
Gera dados completos para o painel de briefing do atendente.
Chamada pelo Connect (Invoke AWS Lambda block) antes do Show View.
Retorna: nome, tipo, curso, foto_url, sentimento, resumo, dicas.
"""
import json
import boto3
import os

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime')
connect_client = boto3.client('connect')

tbl_usuarios = dynamodb.Table('cadastro-usuarios')
tbl_academico = dynamodb.Table('academico')

FOTOS_BUCKET = os.environ['FOTOS_BUCKET']
INSTANCE_ID = os.environ['CONNECT_INSTANCE_ID']
URL_EXPIRATION = 3600


def get_transcript(contact_id):
    """Busca o transcript da conversa via Contact Lens real-time API."""
    if not contact_id:
        return ""
    try:
        lines = []
        next_token = None
        for _ in range(3):  # paginate up to 3 pages
            kwargs = {
                'InstanceId': INSTANCE_ID,
                'ContactId': contact_id,
                'OutputType': 'Raw',
                'SegmentTypes': ['Transcript']
            }
            if next_token:
                kwargs['NextToken'] = next_token
            resp = connect_client.list_realtime_contact_analysis_segments_v2(**kwargs)
            for s in resp.get('Segments', []):
                t = s.get('Transcript', {})
                role = t.get('ParticipantRole', '')
                content = (t.get('Content', '') or '').strip()
                if content:
                    who = 'Cliente' if role == 'CUSTOMER' else 'Assistente'
                    lines.append(f"{who}: {content}")
            next_token = resp.get('NextToken')
            if not next_token:
                break
        return "\n".join(lines)
    except Exception as e:
        print(f"Transcript error: {e}")
        return ""


def get_foto_url(cpf):
    """Gera presigned URL para foto do cliente.
    Tenta o CPF formatado e a versao apenas com digitos."""
    cpf_digits = ''.join(c for c in cpf if c.isdigit())
    cpf_variants = [cpf, cpf_digits]
    for cpf_var in cpf_variants:
        for ext in ['jpg', 'png', 'webp']:
            key = f"fotos/{cpf_var}.{ext}"
            try:
                s3.head_object(Bucket=FOTOS_BUCKET, Key=key)
                return s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': FOTOS_BUCKET, 'Key': key},
                    ExpiresIn=URL_EXPIRATION
                )
            except:
                continue
    return ""


def get_user_by_phone(phone):
    """Busca usuario por telefone."""
    for p in [phone, f"+{phone}", phone.replace('+', '')]:
        resp = tbl_usuarios.query(
            IndexName='telefone-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('telefone').eq(p)
        )
        if resp['Items']:
            return resp['Items'][0]
    return None


def get_academico(cpf):
    """Busca dados academicos."""
    resp = tbl_academico.get_item(Key={'cpf': cpf})
    return resp.get('Item', {})


def generate_summary(conversation_history):
    """Usa Bedrock para gerar resumo da conversa."""
    if not conversation_history:
        return {
            "motivo": "Nao ha historico de conversa disponivel",
            "acoes_bot": "N/A",
            "resultado": "Contato direto com atendente",
            "sentimento": "Neutro",
            "intencao": "Nao identificada",
            "dicas": "Pergunte ao cliente como pode ajudar",
            "resumo": "Sem historico de interacao com o bot."
        }

    prompt = f"""Analise o seguinte historico de conversa entre um bot de atendimento e um cliente.
Gere um JSON com os seguintes campos:
- motivo: motivo do contato em 1-2 frases
- acoes_bot: o que o bot ja fez/tentou (max 2 frases)
- resultado: por que foi transferido para atendente humano
- sentimento: sentimento do cliente (Satisfeito/Neutro/Frustrado/Irritado)
- intencao: intencao principal do cliente
- dicas: 1-2 dicas para o atendente lidar com esse caso
- resumo: resumo completo em 2-3 frases

Historico:
{conversation_history}

Responda APENAS com o JSON valido, sem texto adicional."""

    try:
        resp = bedrock.invoke_model(
            modelId='us.anthropic.claude-haiku-4-5-20251001-v1:0',
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        result = json.loads(resp['body'].read())
        text = result['content'][0]['text'].strip()
        # Remove markdown fences if present
        if text.startswith('```'):
            text = text.split('```', 2)[1]
            if text.startswith('json'):
                text = text[4:]
            text = text.strip()
        # Extract the JSON object substring
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            text = text[start:end+1]
        return json.loads(text)
    except Exception as e:
        print(f"Bedrock error: {e}")
        return {
            "motivo": "Erro ao gerar resumo",
            "acoes_bot": "N/A",
            "resultado": "Transferido para atendente",
            "sentimento": "Neutro",
            "intencao": "Nao identificada",
            "dicas": "Pergunte ao cliente como pode ajudar",
            "resumo": "Nao foi possivel gerar resumo automatico."
        }


def lambda_handler(event, context):
    """
    Gera dados completos para o painel de briefing do atendente.
    Input: contact attributes (phone, contactId) via Connect Invoke Lambda
    Output: dados formatados para Show View block
    """
    print(f"Event: {json.dumps(event, default=str)}")

    details = event.get('Details', {})
    contact_data = details.get('ContactData', {})
    params = details.get('Parameters', {})

    # Obter telefone dos contact attributes
    attributes = contact_data.get('Attributes') or {}
    phone = attributes.get('phone', '')
    if not phone:
        customer_endpoint = contact_data.get('CustomerEndpoint') or {}
        phone = customer_endpoint.get('Address', '')

    contact_id = contact_data.get('ContactId', '')

    # Buscar usuario
    user = get_user_by_phone(phone) if phone else None

    nome = user.get('nome', 'Nao identificado') if user else 'Nao identificado'
    cpf = user.get('cpf', '') if user else ''
    tipo = user.get('tipo', 'nao-cadastrado') if user else 'nao-cadastrado'
    curso = user.get('curso', '') if user else ''
    status = user.get('status', '') if user else ''

    # Foto - sempre retorna uma URL valida (placeholder se nao houver foto)
    foto_url = get_foto_url(cpf) if cpf else ''
    if not foto_url:
        # Placeholder com as iniciais do nome (URI valida)
        import urllib.parse
        nome_encoded = urllib.parse.quote(nome if nome != 'Nao identificado' else 'Cliente')
        foto_url = f'https://ui-avatars.com/api/?name={nome_encoded}&size=200&background=7c4dff&color=fff&rounded=true'

    # Dados academicos (se aluno)
    situacao_financeira = 'N/A'
    if cpf and tipo == 'aluno':
        acad = get_academico(cpf)
        financeiro = acad.get('financeiro', [])
        vencidas = [m for m in financeiro if m.get('status') == 'Nao pago']
        if vencidas:
            situacao_financeira = f'{len(vencidas)} mensalidade(s) em aberto'
        else:
            situacao_financeira = 'Adimplente'

    # Gerar resumo com Bedrock - busca o transcript da conversa via Contact Lens
    conversation_history = get_transcript(contact_id)
    if not conversation_history:
        # fallback: tenta o parametro passado pelo flow
        conversation_history = params.get('conversationHistory', '')
    summary = generate_summary(conversation_history)

    # Montar resposta - Connect Lambda responses must be flat string map
    result = {
        "nome": nome,
        "telefone": phone,
        "cpf": cpf,
        "tipo": tipo,
        "curso": curso,
        "status": status,
        "foto_url": foto_url,
        "situacao_financeira": situacao_financeira,
        "motivo": summary.get("motivo", ""),
        "acoes_bot": summary.get("acoes_bot", ""),
        "resultado_transferencia": summary.get("resultado", ""),
        "sentimento": summary.get("sentimento", "Neutro"),
        "intencao": summary.get("intencao", ""),
        "dicas": summary.get("dicas", ""),
        "resumo_conversa": summary.get("resumo", ""),
        # Campo combinado para a view
        "dados_cliente": f"Nome: {nome} | Tipo: {tipo} | Curso: {curso} | Financeiro: {situacao_financeira}"
    }

    print(f"Result: {json.dumps(result, default=str)}")
    return result
