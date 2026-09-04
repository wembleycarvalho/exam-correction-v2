# Lambda: mcp-catalogo-cursos
# Runtime: python3.12
# Timeout: 30s
# Memory: 128MB
# Role: LambdaMCPCursosRole
# Handler: lambda_function.lambda_handler
#

import json
import boto3
from decimal import Decimal

TABLE_NAME = 'catalogo-cursos'
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def listar_cursos(area=None):
    resp = table.scan()
    cursos = resp['Items']
    if area:
        cursos = [c for c in cursos if c.get('area', '').lower() == area.lower()]
    result = []
    for c in cursos:
        item = {
            'curso_id': c['curso_id'],
            'nome': c['nome'],
            'area': c['area'],
            'modalidade': c['modalidade'],
            'vagas_disponiveis': int(c.get('vagas_disponiveis', 0))
        }
        # Graduacao vs Extensao
        if c.get('tipo') == 'extensao':
            item['tipo'] = 'extensao'
            item['duracao_horas'] = int(c.get('duracao_horas', 0))
            item['duracao_meses'] = int(c.get('duracao_meses', 0))
        else:
            item['tipo'] = 'graduacao'
            item['duracao_semestres'] = int(c.get('duracao_semestres', 0))
        result.append(item)
    return result


def detalhe_curso(curso_id):
    resp = table.get_item(Key={'curso_id': curso_id})
    item = resp.get('Item')
    if not item:
        return {'error': f'Curso {curso_id} nao encontrado'}
    return json.loads(json.dumps(item, cls=DecimalEncoder))


def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")
    print(f"Context custom: {json.dumps(getattr(getattr(context, 'client_context', None), 'custom', None) or {})}")

    # Gateway sends tool name in context.client_context.custom
    delimiter = "___"
    tool_name = ""
    try:
        original = context.client_context.custom['bedrockAgentCoreToolName']
        tool_name = original[original.index(delimiter) + len(delimiter):]
    except Exception:
        # Fallback: check event for tool_name
        tool_name = event.get('tool_name', event.get('toolName', ''))

    # Auto-detect tool from parameters if tool_name is empty
    if not tool_name:
        if 'curso_id' in event:
            tool_name = 'detalhe_curso'
        else:
            tool_name = 'listar_cursos'

    print(f"Tool: {tool_name}")

    if tool_name == 'listar_cursos':
        area = event.get('area')
        result = listar_cursos(area)
    elif tool_name == 'detalhe_curso':
        curso_id = event.get('curso_id', '')
        result = detalhe_curso(curso_id)
    else:
        result = {'error': f'Tool {tool_name} nao reconhecida'}

    return json.loads(json.dumps(result, cls=DecimalEncoder, ensure_ascii=False))
