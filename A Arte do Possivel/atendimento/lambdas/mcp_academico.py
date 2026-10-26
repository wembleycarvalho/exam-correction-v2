# Lambda: mcp-academico
# Runtime: python3.12 | Timeout: 30s | Memory: 128MB
# Role: LambdaMCPCursosRole
"""
MCP tool: consulta informacoes academicas do aluno por CPF.
Retorna documento unico com disciplinas, provas, historico, financeiro.
"""
import json
import boto3
from decimal import Decimal

TABLE = 'academico'
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")

    delimiter = "___"
    tool_name = ""
    try:
        original = context.client_context.custom['bedrockAgentCoreToolName']
        tool_name = original[original.index(delimiter) + len(delimiter):]
    except Exception:
        tool_name = event.get('tool_name', 'consultar_academico')

    cpf = event.get('cpf', '')
    tipo = event.get('tipo_consulta', 'todos')

    print(f"Tool: {tool_name} | CPF: {cpf} | Tipo: {tipo}")

    if not cpf:
        return {"error": "CPF nao informado"}

    resp = table.get_item(Key={'cpf': cpf})
    item = resp.get('Item')

    if not item:
        return {"message": "Nenhum registro academico encontrado para este CPF"}

    result = json.loads(json.dumps(item, cls=DecimalEncoder))

    # Filter by tipo_consulta
    if tipo == 'disciplina':
        return {"disciplinas_atuais": result.get("disciplinas_atuais", []), "semestre_atual": result.get("semestre_atual"), "cr_acumulado": result.get("cr_acumulado")}
    elif tipo == 'prova':
        return {"provas": result.get("provas", [])}
    elif tipo == 'historico':
        return {"historico": result.get("historico", []), "cr_acumulado": result.get("cr_acumulado")}
    elif tipo == 'financeiro':
        return {"financeiro": result.get("financeiro", [])}
    else:
        return result
