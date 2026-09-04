# Lambda: connect-user-lookup
# Runtime: python3.12 | Timeout: 10s | Memory: 128MB
# Role: LexFulfillmentLambdaRole
"""
MCP tool: consulta usuario pelo telefone (via GSI) ou CPF (via PK).
Retorna nome, tipo, status, curso.
"""
import json
import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('cadastro-usuarios')


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def lookup_by_phone(phone):
    for p in [phone, f"+{phone}", phone.replace('+', '')]:
        resp = table.query(
            IndexName='telefone-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('telefone').eq(p)
        )
        if resp['Items']:
            return resp['Items'][0]
    return None


def lookup_by_cpf(cpf):
    resp = table.get_item(Key={'cpf': cpf})
    return resp.get('Item')


def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")

    phone = event.get('phone', event.get('telefone', ''))
    cpf = event.get('cpf', '')

    item = None
    if cpf:
        item = lookup_by_cpf(cpf)
    elif phone:
        item = lookup_by_phone(phone)

    if not item:
        return {"found": False, "message": "Usuario nao cadastrado"}

    return json.loads(json.dumps({
        "found": True,
        "cpf": item.get("cpf"),
        "nome": item.get("nome"),
        "tipo": item.get("tipo"),
        "status": item.get("status"),
        "curso": item.get("curso", ""),
        "curso_id": item.get("curso_id", ""),
        "especialidade": item.get("especialidade", "")
    }, cls=DecimalEncoder))
