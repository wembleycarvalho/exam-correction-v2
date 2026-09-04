# Lambda: mcp-foto-cliente
# Runtime: python3.12 | Timeout: 10s | Memory: 128MB
# Role: LambdaFotoClienteRole
# Env vars: FOTOS_BUCKET, URL_EXPIRATION
"""
MCP tool: gera presigned URL para a foto do cliente.
Pode ser usado pelo AI Agent ou pelo step-by-step guide.
Input: {"cpf": "12345678900"} ou {"telefone": "+5511999999999"}
Output: {"foto_url": "https://...", "has_foto": true/false}
"""
import json
import boto3
import os

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('cadastro-usuarios')

BUCKET = os.environ['FOTOS_BUCKET']
EXPIRATION = int(os.environ.get('URL_EXPIRATION', '3600'))  # 1 hora


def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")

    cpf = event.get('cpf', '')
    telefone = event.get('telefone', '')

    # Se recebeu telefone, buscar CPF no DynamoDB
    if not cpf and telefone:
        for p in [telefone, f"+{telefone}", telefone.replace('+', '')]:
            resp = table.query(
                IndexName='telefone-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('telefone').eq(p)
            )
            if resp['Items']:
                cpf = resp['Items'][0].get('cpf', '')
                break

    if not cpf:
        return {"has_foto": False, "message": "CPF nao encontrado"}

    # Tentar gerar URL para foto (tenta CPF formatado e so-digitos, .jpg, .png, .webp)
    cpf_digits = ''.join(c for c in cpf if c.isdigit())
    for cpf_var in [cpf, cpf_digits]:
        for ext in ['jpg', 'png', 'webp']:
            key = f"fotos/{cpf_var}.{ext}"
            try:
                s3.head_object(Bucket=BUCKET, Key=key)
                # Foto existe, gerar presigned URL
                url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': BUCKET, 'Key': key},
                    ExpiresIn=EXPIRATION
                )
                return {
                    "has_foto": True,
                    "foto_url": url,
                    "cpf": cpf,
                    "formato": ext
                }
            except s3.exceptions.ClientError:
                continue

    return {"has_foto": False, "cpf": cpf, "message": "Foto nao encontrada no S3"}
