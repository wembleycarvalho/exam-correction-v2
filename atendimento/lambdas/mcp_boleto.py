# Lambda: mcp-boleto
# Runtime: python3.12 | Timeout: 30s | Memory: 256MB
# Role: LambdaBoletoRole
# Layer: reportlab-layer
"""
MCP tool: gera segunda via de boleto (PDF fake) e envia via WhatsApp.
- Valida mensalidade "Nao pago" no DynamoDB
- Gera PDF com reportlab (codigo de barras fake, linha digitavel fake)
- Salva no S3
- Envia como documento no WhatsApp via Social Messaging API
- Retorna linha digitavel para o AI Agent incluir na mensagem
"""
import json
import boto3
import os
import random
import io
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.pdfgen import canvas

S3_BUCKET = os.environ.get('S3_BUCKET_BOLETOS', 'boletos-demo-123456789012')
WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', 'phone-number-id-fe268d418d9b4e1296c47f86795987df')
REGION = os.environ.get('AWS_REGION', 'us-east-1')

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
social = boto3.client('socialmessaging', region_name=REGION)
tbl_academico = dynamodb.Table('academico')
tbl_usuarios = dynamodb.Table('cadastro-usuarios')


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def gerar_linha_digitavel():
    """Gera linha digitavel fake no formato de boleto bancario."""
    # Formato: AAABC.CCCCX DDDDD.DDDDDY EEEEE.EEEEEZ K UUUUVVVVVVVVVV
    banco = '237'  # fake
    moeda = '9'
    parts = []
    parts.append(f'{banco}{moeda}{random.randint(1,9)}.{random.randint(10000,99999)}')
    parts.append(f'{random.randint(10000,99999)}.{random.randint(10000,99999)}')
    parts.append(f'{random.randint(10000,99999)}.{random.randint(10000,99999)}')
    parts.append(str(random.randint(1, 9)))
    parts.append(f'{random.randint(1000,9999)}{random.randint(10000000, 99999999)}')
    return ' '.join(parts)


def desenhar_codigo_barras_fake(c, x, y, width, height):
    """Desenha barras verticais fake que parecem codigo de barras."""
    bar_x = x
    while bar_x < x + width:
        bar_width = random.choice([0.5, 1.0, 1.5, 2.0]) * mm
        space = random.choice([0.5, 1.0, 1.5]) * mm
        if bar_x + bar_width > x + width:
            break
        c.setFillColorRGB(0, 0, 0)
        c.rect(bar_x, y, bar_width, height, fill=1, stroke=0)
        bar_x += bar_width + space


def gerar_pdf_boleto(nome, cpf, mes, valor, vencimento, linha_digitavel):
    """Gera PDF de boleto fake com reportlab."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    # Header
    c.setFont('Helvetica-Bold', 16)
    c.drawString(2 * cm, h - 2 * cm, 'INSTITUICAO DE ENSINO DEMO')
    c.setFont('Helvetica', 10)
    c.drawString(2 * cm, h - 2.6 * cm, 'CNPJ: 00.000.000/0001-00')

    # Linha separadora
    c.setLineWidth(2)
    c.line(2 * cm, h - 3 * cm, w - 2 * cm, h - 3 * cm)

    # Dados do boleto
    y = h - 4 * cm
    c.setFont('Helvetica-Bold', 11)
    c.drawString(2 * cm, y, 'BOLETO BANCARIO - SEGUNDA VIA')
    y -= 1 * cm

    campos = [
        ('Beneficiario:', 'Instituicao de Ensino Demo'),
        ('Pagador:', f'{nome} - CPF: {cpf}'),
        ('Referencia:', f'Mensalidade {mes}'),
        ('Vencimento:', vencimento),
        ('Valor:', f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')),
    ]

    for label, value in campos:
        c.setFont('Helvetica-Bold', 10)
        c.drawString(2 * cm, y, label)
        c.setFont('Helvetica', 10)
        c.drawString(5.5 * cm, y, value)
        y -= 0.7 * cm

    # Separador
    y -= 0.5 * cm
    c.setLineWidth(1)
    c.line(2 * cm, y, w - 2 * cm, y)
    y -= 1 * cm

    # Codigo de barras fake
    c.setFont('Helvetica-Bold', 10)
    c.drawString(2 * cm, y, 'Codigo de Barras:')
    y -= 0.5 * cm
    desenhar_codigo_barras_fake(c, 2 * cm, y - 1.5 * cm, 14 * cm, 1.5 * cm)
    y -= 2.5 * cm

    # Linha digitavel
    c.setFont('Helvetica-Bold', 10)
    c.drawString(2 * cm, y, 'Linha Digitavel:')
    y -= 0.6 * cm
    c.setFont('Courier', 11)
    c.drawString(2 * cm, y, linha_digitavel)
    y -= 1.5 * cm

    # Separador
    c.setLineWidth(1)
    c.line(2 * cm, y, w - 2 * cm, y)
    y -= 0.8 * cm

    # Aviso
    c.setFont('Helvetica-Bold', 9)
    c.setFillColorRGB(0.8, 0, 0)
    c.drawString(2 * cm, y, 'DOCUMENTO DE DEMONSTRACAO - SEM VALOR FISCAL')
    y -= 0.5 * cm
    c.setFont('Helvetica', 8)
    c.drawString(2 * cm, y, 'Este boleto e ficticio e nao pode ser utilizado para pagamento real.')

    c.save()
    buf.seek(0)
    return buf.read()


def enviar_whatsapp_documento(telefone, s3_key, filename):
    """Envia PDF como documento no WhatsApp via Social Messaging API."""
    # 1. Upload media pro WhatsApp
    media_resp = social.post_whatsapp_message_media(
        originationPhoneNumberId=WHATSAPP_PHONE_ID,
        sourceS3File={'bucketName': S3_BUCKET, 'key': s3_key}
    )
    media_id = media_resp.get('mediaId', '')
    print(f'  Media uploaded: {media_id}')

    # 2. Enviar documento
    # WhatsApp Cloud API via Social Messaging precisa do telefone COM o +
    phone_clean = telefone.strip()
    if not phone_clean.startswith('+'):
        phone_clean = '+' + phone_clean
    print(f'  Phone: {telefone} -> {phone_clean}')

    message_payload = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_clean,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": filename,
            "caption": "Segunda via do boleto"
        }
    }).encode('utf-8')

    send_resp = social.send_whatsapp_message(
        originationPhoneNumberId=WHATSAPP_PHONE_ID,
        message=message_payload,
        metaApiVersion='v20.0'
    )
    msg_id = send_resp.get('messageId', '')
    print(f'  WhatsApp sent: {msg_id}')
    return msg_id


def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")

    cpf = event.get('cpf', '')
    mes = event.get('mes', '')

    if not cpf or not mes:
        return {"erro": True, "mensagem": "CPF e mes sao obrigatorios"}

    # 1. Buscar dados academicos
    resp = tbl_academico.get_item(Key={'cpf': cpf})
    item = resp.get('Item')
    if not item:
        return {"erro": True, "mensagem": "Nenhum registro academico encontrado"}

    # 2. Buscar mensalidade (busca flexivel por mes)
    financeiro = item.get('financeiro', [])
    mensalidade = None
    mes_input = mes.strip()

    # Normalizar: extrair nome do mes e ano do input
    MESES_NUM = {'janeiro':'01','fevereiro':'02','marco':'03','abril':'04','maio':'05','junho':'06',
                 'julho':'07','agosto':'08','setembro':'09','outubro':'10','novembro':'11','dezembro':'12'}
    MESES_NOME = {v: k for k, v in MESES_NUM.items()}

    def normalizar_mes(m):
        """Retorna (nome_mes_lower, ano) ou None."""
        m = m.lower().strip()
        # "Maio/2026" -> ("maio", "2026")
        for sep in ['/', '-', ' ']:
            if sep in m:
                parts = m.split(sep)
                for p in parts:
                    p = p.strip()
                    if p in MESES_NUM:
                        ano = [x.strip() for x in parts if x.strip() != p]
                        return (p, ano[0] if ano else '')
                    if p in MESES_NOME:
                        ano = [x.strip() for x in parts if x.strip() != p]
                        return (MESES_NOME[p], ano[0] if ano else '')
        # Sem separador: "maio" ou "05"
        if m in MESES_NUM:
            return (m, '')
        if m in MESES_NOME:
            return (MESES_NOME[m], '')
        return None

    input_norm = normalizar_mes(mes_input)
    print(f"  Mes input: '{mes_input}' -> normalized: {input_norm}")

    for f in financeiro:
        f_mes = f.get('mes', '')
        f_norm = normalizar_mes(f_mes)
        if input_norm and f_norm and input_norm[0] == f_norm[0]:
            # Se ambos tem ano, verificar
            if input_norm[1] and f_norm[1] and input_norm[1] != f_norm[1]:
                continue
            mensalidade = f
            print(f"  Matched: '{f_mes}'")
            break

    if not mensalidade:
        return {"erro": True, "mensagem": f"Mensalidade de {mes} nao encontrada"}

    if mensalidade.get('status') == 'Pago':
        return {"erro": True, "mensagem": f"A mensalidade de {mes} ja esta paga"}

    # 3. Buscar dados do usuario
    resp_user = tbl_usuarios.get_item(Key={'cpf': cpf})
    usuario = resp_user.get('Item', {})
    nome = usuario.get('nome', 'Aluno')
    telefone = usuario.get('telefone', '')

    if not telefone:
        return {"erro": True, "mensagem": "Telefone do aluno nao encontrado no cadastro"}

    # 4. Gerar boleto
    valor = float(mensalidade.get('valor', 0))
    vencimento = mensalidade.get('vencimento', '')
    linha_digitavel = gerar_linha_digitavel()

    pdf_bytes = gerar_pdf_boleto(nome, cpf, mes, valor, vencimento, linha_digitavel)

    # 5. Salvar no S3
    mes_clean = mes.replace('/', '-').replace(' ', '_')
    s3_key = f'{cpf}/{mes_clean}.pdf'
    s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=pdf_bytes, ContentType='application/pdf')
    print(f'  S3: s3://{S3_BUCKET}/{s3_key}')

    # 6. Enviar via WhatsApp
    filename = f'Boleto_{mes_clean}.pdf'
    try:
        enviar_whatsapp_documento(telefone, s3_key, filename)
    except Exception as e:
        print(f'  WhatsApp error: {e}')
        return {
            "erro": False,
            "mensagem": f"Boleto gerado mas houve erro ao enviar no WhatsApp: {str(e)[:100]}",
            "linha_digitavel": linha_digitavel,
            "valor": valor,
            "vencimento": vencimento
        }

    return {
        "erro": False,
        "mensagem": f"Boleto de {mes} enviado com sucesso no WhatsApp",
        "linha_digitavel": linha_digitavel,
        "valor": valor,
        "vencimento": vencimento,
        "mes": mes
    }
