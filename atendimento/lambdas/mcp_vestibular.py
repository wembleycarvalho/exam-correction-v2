# Lambda: mcp-vestibular
# Runtime: python3.12 | Timeout: 30s | Memory: 128MB
# Role: LambdaMCPCursosRole
"""
MCP tool: consulta a base de conhecimento da instituicao (Bedrock KB).
Para alunos, retorna conteudo de disciplinas cursando/cursadas + conteudo publico.
Para nao-alunos, retorna apenas conteudo publico (vestibular, institucional).

Parametros:
  - pergunta (obrigatorio): texto da pergunta do usuario
  - cpf (opcional): CPF do aluno. Se informado, filtra conteudo por disciplinas permitidas.
"""
import json
import boto3
import os

KB_ID = os.environ.get('KB_VESTIBULAR_ID', 'ECCHPIL4ZK')
REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)

tbl_usuarios = dynamodb.Table('cadastro-usuarios')
tbl_academico = dynamodb.Table('academico')


def _get_disciplinas_permitidas(cpf):
    """
    Busca disciplinas permitidas para um aluno:
    - disciplinas_atuais[].nome (cursando agora)
    - historico[].disciplinas[].nome (aprovado ou reprovado — ja teve acesso ao material)
    Retorna lista de nomes de disciplinas, ou None se nao for aluno.
    """
    # 1. Verificar tipo do usuario
    try:
        resp_usuario = tbl_usuarios.get_item(Key={'cpf': cpf})
    except Exception as e:
        print(f"  Erro ao buscar cadastro-usuarios para cpf={cpf}: {e}")
        return None

    usuario = resp_usuario.get('Item')
    if not usuario:
        print(f"  CPF {cpf} nao encontrado em cadastro-usuarios")
        return None

    tipo = usuario.get('tipo', '')
    if tipo != 'aluno':
        print(f"  CPF {cpf} tipo={tipo} (nao e aluno) -> filtro publico")
        return None

    # 2. Buscar dados academicos
    try:
        resp_academico = tbl_academico.get_item(Key={'cpf': cpf})
    except Exception as e:
        print(f"  Erro ao buscar academico para cpf={cpf}: {e}")
        return None

    academico = resp_academico.get('Item')
    if not academico:
        print(f"  CPF {cpf} nao encontrado em academico -> filtro publico")
        return None

    disciplinas = set()

    # Disciplinas atuais
    for d in academico.get('disciplinas_atuais', []):
        nome = d.get('nome', '')
        if nome:
            disciplinas.add(nome)

    # Historico (todos os semestres, aprovado ou reprovado)
    for semestre in academico.get('historico', []):
        for d in semestre.get('disciplinas', []):
            nome = d.get('nome', '')
            if nome:
                disciplinas.add(nome)

    print(f"  Aluno {cpf}: {len(disciplinas)} disciplinas permitidas")
    return list(disciplinas) if disciplinas else None


def _build_retrieval_filter(cpf):
    """
    Monta o filtro de metadata para o retrieve da KB.
    - Aluno com disciplinas: tipo=publico OR disciplina IN [lista]
    - Nao-aluno ou sem CPF: tipo=publico
    """
    if not cpf:
        print("  Sem CPF -> filtro apenas publico")
        return {"equals": {"key": "tipo", "value": "publico"}}

    disciplinas = _get_disciplinas_permitidas(cpf)

    if disciplinas:
        print(f"  Filtro: publico + {len(disciplinas)} disciplinas")
        return {
            "orAll": [
                {"equals": {"key": "tipo", "value": "publico"}},
                {"in": {"key": "disciplina", "value": disciplinas}}
            ]
        }
    else:
        print("  Filtro: apenas publico (nao-aluno ou sem dados academicos)")
        return {"equals": {"key": "tipo", "value": "publico"}}


def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")

    pergunta = event.get('pergunta', event.get('query', ''))
    cpf = event.get('cpf', '')

    if not pergunta:
        return {"erro": True, "mensagem": "Pergunta nao informada"}

    print(f"  Query: {pergunta}")
    print(f"  CPF: {cpf or '(nao informado)'}")

    try:
        retrieval_filter = _build_retrieval_filter(cpf)

        resp = bedrock_runtime.retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={'text': pergunta},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 5,
                    'filter': retrieval_filter
                }
            }
        )

        results = resp.get('retrievalResults', [])
        if not results:
            return {"encontrado": False, "mensagem": "Nao encontrei informacoes sobre esse tema na base de conhecimento."}

        # Concatenar os trechos relevantes
        trechos = []
        for r in results:
            score = r.get('score', 0)
            if score < 0.3:
                continue
            text = r.get('content', {}).get('text', '')
            if text:
                trechos.append(text)

        if not trechos:
            return {"encontrado": False, "mensagem": "Nao encontrei informacoes relevantes sobre esse tema."}

        return {
            "encontrado": True,
            "informacoes": "\n\n".join(trechos),
            "fonte": "Base de Conhecimento Institucional"
        }

    except Exception as e:
        print(f"  KB error: {e}")
        return {"erro": True, "mensagem": f"Erro ao consultar base de conhecimento: {str(e)[:100]}"}
