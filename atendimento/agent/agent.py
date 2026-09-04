"""Atendimento — Assistente (agente Strands no AgentCore Runtime, STREAMING).

Chat in-portal do módulo Atendimento. Roda no AgentCore Runtime (CodeZip), fala PT-BR e usa
as MESMAS tools do assistente do Harness (educação): catálogo de cursos, cadastro, acadêmico,
boleto e conteúdo (KB). As tools são as Lambdas já existentes — o agente as invoca direto
(`lambda:invoke`) com o mesmo payload que o AgentCore Gateway usa (os Lambdas leem um event
plano). Escolha consciente: nosso próprio agente no Runtime chama os Lambdas diretamente
(mesma lógica das tools), sem a fragilidade de assinar MCP-sobre-IAM no Gateway; dá para
trocar para o Gateway MCP depois se quisermos expor a mesma UX a clientes externos.

Streaming: `stream_async` do Strands → o entrypoint faz `yield` dos deltas de texto; o
AgentCore Runtime entrega como stream, e a ponte Lambda (Node, response streaming) repassa
como SSE ao browser. Observability nativa (ADOT) — `aws-opentelemetry-distro` no requirements.
"""
import json
import os

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

app = BedrockAgentCoreApp()

REGION = os.environ.get("AWS_REGION", "us-east-1")
# Modelo via Bedrock Converse direto (parametrizável, nunca hardcoded de conta).
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

# Nomes das Lambdas-tool (overridáveis por env). Defaults = recursos de demo do Harness.
FN_CURSOS = os.environ.get("FN_CURSOS", "mcp-catalogo-cursos")
FN_LOOKUP = os.environ.get("FN_LOOKUP", "connect-user-lookup")
FN_ACADEMICO = os.environ.get("FN_ACADEMICO", "mcp-academico")
FN_BOLETO = os.environ.get("FN_BOLETO", "mcp-boleto")
FN_CONTEUDO = os.environ.get("FN_CONTEUDO", "mcp-vestibular")

_lambda = boto3.client("lambda", region_name=REGION)

_SYSTEM = (
    "Você é o assistente virtual de atendimento de uma instituição de ensino, no portal web. "
    "Responda SEMPRE em português do Brasil, de forma clara, cordial e objetiva.\n"
    "Use as ferramentas disponíveis para dar respostas corretas em vez de adivinhar:\n"
    "- listar_cursos / detalhe_curso: catálogo (graduação e extensão).\n"
    "- consultar_usuario: identifica o aluno por CPF (ou telefone).\n"
    "- consultar_academico: notas, disciplinas, provas, histórico e financeiro (precisa do CPF).\n"
    "- gerar_boleto: 2ª via de mensalidade não paga (precisa de CPF e mês).\n"
    "- consultar_conteudo: base de conhecimento (vestibular/institucional; conteúdo de "
    "disciplinas para alunos).\n"
    "Regras: para dados pessoais/acadêmicos/financeiros, peça o CPF antes (no portal não há "
    "identificação automática por telefone). Nunca invente notas, valores ou datas. Se a "
    "ferramenta não retornar o dado, diga com transparência. Seja conciso."
)


def _invoke(fn, payload):
    try:
        r = _lambda.invoke(FunctionName=fn, InvocationType="RequestResponse",
                           Payload=json.dumps(payload).encode("utf-8"))
        raw = r["Payload"].read()
        data = json.loads(raw or b"{}")
        # Lambdas podem responder no formato proxy ({statusCode, body}) ou objeto direto.
        if isinstance(data, dict) and "body" in data and "statusCode" in data:
            try:
                return json.loads(data["body"])
            except (ValueError, TypeError):
                return {"result": data.get("body")}
        return data
    except Exception as e:  # noqa: BLE001
        return {"error": f"falha na tool {fn}: {str(e)[:200]}"}


@tool
def listar_cursos(area: str = "") -> dict:
    """Lista cursos de graduação e extensão. Pode filtrar por área (Tecnologia, Saúde,
    Negócios, Humanas, Design)."""
    return _invoke(FN_CURSOS, {"tool": "listar_cursos", "area": area} if area
                   else {"tool": "listar_cursos"})


@tool
def detalhe_curso(curso_id: str) -> dict:
    """Detalhes de um curso (ementa, grade, diferenciais, mensalidade). Ex.: eng-software,
    ext-ia-aplicada."""
    return _invoke(FN_CURSOS, {"tool": "detalhe_curso", "curso_id": curso_id})


@tool
def consultar_usuario(cpf: str = "", phone: str = "") -> dict:
    """Consulta cadastro do usuário por CPF (123.456.789-00) ou telefone (+55...). Retorna
    nome, tipo, status e curso."""
    return _invoke(FN_LOOKUP, {"cpf": cpf, "phone": phone})


@tool
def consultar_academico(cpf: str, tipo_consulta: str = "todos") -> dict:
    """Informações acadêmicas do aluno por CPF. tipo_consulta: disciplina, prova, historico,
    financeiro ou todos."""
    return _invoke(FN_ACADEMICO, {"cpf": cpf, "tipo_consulta": tipo_consulta})


@tool
def gerar_boleto(cpf: str, mes: str) -> dict:
    """Gera a 2ª via de um boleto de mensalidade NÃO paga (precisa de CPF e mês, ex.:
    Maio/2026). Retorna a linha digitável."""
    return _invoke(FN_BOLETO, {"cpf": cpf, "mes": mes})


@tool
def consultar_conteudo(pergunta: str, cpf: str = "") -> dict:
    """Consulta a base de conhecimento (RAG): vestibular/institucional para todos; conteúdo
    de disciplinas para alunos (passe o CPF para liberar o conteúdo permitido)."""
    return _invoke(FN_CONTEUDO, {"pergunta": pergunta, "cpf": cpf})


_TOOLS = [listar_cursos, detalhe_curso, consultar_usuario, consultar_academico,
          gerar_boleto, consultar_conteudo]


def _messages(history):
    msgs = []
    for h in (history or []):
        if not isinstance(h, dict):
            continue
        role = h.get("role")
        text = (h.get("text") or "").strip()
        if role in ("user", "assistant") and text:
            msgs.append({"role": role, "content": [{"text": text}]})
    return msgs


@app.entrypoint
async def invoke(payload):
    """STREAMING: faz yield dos deltas de texto do agente. A ponte Lambda transforma em SSE."""
    question = (payload.get("question") or payload.get("prompt") or "").strip()
    system = (payload.get("system_prompt") or "").strip() or _SYSTEM
    history = payload.get("history") or []
    if not question:
        yield "Faça uma pergunta."
        return
    agent = Agent(
        model=BedrockModel(model_id=MODEL_ID, region_name=REGION),
        system_prompt=system, tools=_TOOLS,
        messages=_messages(history), callback_handler=None)
    async for event in agent.stream_async(question):
        if isinstance(event, dict) and event.get("data"):
            yield event["data"]


if __name__ == "__main__":
    app.run()
