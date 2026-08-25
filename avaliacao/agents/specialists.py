"""Agentes especialistas (Strands) — executam no AgentCore Runtime.

Grading e transcrição de prova usam **structured output** (o modelo preenche um schema
Pydantic via tool-calling), eliminando o parse frágil de JSON-em-texto. Transcrição de
redação e o wizard retornam texto simples.

Contrato uniforme por função:
    {"result": <dict|str>, "usage": {"tokensIn": int, "tokensOut": int}, "model": <id>}
"""
import base64
from typing import List

from pydantic import BaseModel, Field
from strands import Agent
from strands.models import BedrockModel

from prompts import (
    ESSAY_SYSTEM, EXAM_SYSTEM, AUTHOR_SYSTEM, JUDGE_SYSTEM, ANSWERSHEET_SYSTEM, EXAMGEN_SYSTEM,
    essay_prompt, exam_prompt, author_prompt, transcription_prompt, judge_prompt,
    answersheet_prompt, examgen_prompt, examgen_discursive_prompt,
)

_IMAGE_FORMATS = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg", "gif": "gif", "webp": "webp"}


# --- Schemas de saída (structured output) ---------------------------------------
class Criterion(BaseModel):
    name: str = Field(description="Nome do critério")
    score: float = Field(description="Nota atribuída ao critério")
    maxScore: float = Field(description="Nota máxima do critério")
    feedback: str = Field(description="Justificativa em português")


class EssayResult(BaseModel):
    criteria: List[Criterion]
    totalScore: float = Field(description="Soma das notas dos critérios")
    feedback: str = Field(default="", description="Comentário geral em português")


class Questao(BaseModel):
    nota: float
    notaMaxima: float
    justificativa: str = Field(description="Justificativa da nota em português")
    fontes: List[str] = Field(default_factory=list)


class ExamResult(BaseModel):
    questoes: List[Questao]
    notaTotal: float


class QAPair(BaseModel):
    question: str
    resposta: str


class ExamTranscription(BaseModel):
    transcricao: List[QAPair]


class MarkedAnswer(BaseModel):
    questao: int = Field(description="Número da questão (a partir de 1)")
    marcada: str = Field(description="Alternativa marcada (A-E), '-' se em branco, '*' se múltiplas")


class AnswerSheetResult(BaseModel):
    respostas: List[MarkedAnswer]


class MCQuestion(BaseModel):
    enunciado: str = Field(description="Enunciado da questão")
    alternativas: List[str] = Field(description="Exatamente 5 alternativas; índice 0=A, 1=B, ...")
    correta: str = Field(description="Letra da alternativa correta: A, B, C, D ou E")
    explicacao: str = Field(description="Por que a correta está certa (curta, baseada no material)")
    tema: str = Field(default="", description="Assunto específico da questão")


class ExamGenResult(BaseModel):
    questoes: List[MCQuestion]


class DiscursiveQuestion(BaseModel):
    enunciado: str = Field(description="Pergunta aberta que exige resposta redigida")
    respostaReferencia: str = Field(description="Resposta de referência (gabarito), baseada no material")
    tema: str = Field(default="", description="Assunto específico da questão")


class ExamGenDiscResult(BaseModel):
    questoes: List[DiscursiveQuestion]


class JudgeDimension(BaseModel):
    name: str = Field(description="Nome da dimensão avaliada")
    scoreA: float = Field(description="Nota do Candidato A nesta dimensão, de 0 a 10")
    scoreB: float = Field(description="Nota do Candidato B nesta dimensão, de 0 a 10")
    note: str = Field(default="", description="Observação curta comparando A e B nesta dimensão")


class JudgeResult(BaseModel):
    winner: str = Field(description="Qual candidato é melhor: 'A', 'B' ou 'empate'")
    scoreA: float = Field(description="Nota geral do candidato A, de 0 a 10")
    scoreB: float = Field(description="Nota geral do candidato B, de 0 a 10")
    dimensions: List[JudgeDimension] = Field(default_factory=list,
                                             description="Notas por dimensão avaliada")
    rationale: str = Field(description="Resumo comparativo em português")


# --- Helpers --------------------------------------------------------------------
def _agent(model_id: str, system_prompt: str, temperature: float = 0.0) -> Agent:
    if not model_id:
        raise ValueError("modelId não informado (configure os modelos por capacidade).")
    return Agent(model=BedrockModel(model_id=model_id, temperature=temperature),
                 system_prompt=system_prompt)


def _usage(result) -> dict:
    try:
        acc = result.metrics.accumulated_usage
        return {"tokensIn": int(acc.get("inputTokens", 0)), "tokensOut": int(acc.get("outputTokens", 0))}
    except Exception:
        return {"tokensIn": 0, "tokensOut": 0}


def _content_block(image_b64: str, ext: str) -> dict:
    raw = base64.b64decode(image_b64)
    ext = (ext or "png").lower()
    if ext == "pdf":
        return {"document": {"format": "pdf", "name": "documento", "source": {"bytes": raw}}}
    return {"image": {"format": _IMAGE_FORMATS.get(ext, "png"), "source": {"bytes": raw}}}


# --- Capacidades ----------------------------------------------------------------
def run_transcription(model_id: str, image_b64: str, ext: str, kind: str = "essay") -> dict:
    agent = _agent(model_id, "Você transcreve provas com fidelidade.")
    content = [{"text": transcription_prompt(kind)}, _content_block(image_b64, ext)]
    if kind == "exam":
        result = agent(content, structured_output_model=ExamTranscription)
        out = result.structured_output.model_dump()
    else:
        result = agent(content)
        out = {"text": str(result).strip()}
    return {"result": out, "usage": _usage(result), "model": model_id}


def run_essay(model_id: str, essay_text: str, rubric: dict) -> dict:
    agent = _agent(model_id, ESSAY_SYSTEM)
    result = agent(essay_prompt(essay_text, rubric), structured_output_model=EssayResult)
    return {"result": result.structured_output.model_dump(), "usage": _usage(result), "model": model_id}


def run_exam(model_id: str, qa_pairs: list, strategy: str, gabarito: list = None,
             max_score_per_question: float = 10.0) -> dict:
    agent = _agent(model_id, EXAM_SYSTEM)
    result = agent(exam_prompt(qa_pairs, strategy, gabarito, max_score_per_question),
                   structured_output_model=ExamResult)
    return {"result": result.structured_output.model_dump(), "usage": _usage(result), "model": model_id}


def run_author(model_id: str, question: str) -> dict:
    agent = _agent(model_id, AUTHOR_SYSTEM, temperature=0.2)
    result = agent(author_prompt(question))
    return {"result": {"resposta": str(result).strip()}, "usage": _usage(result), "model": model_id}


def run_answersheet(model_id: str, image_b64: str, ext: str = "png", expected: dict = None) -> dict:
    """Lê um cartão-resposta e retorna as alternativas marcadas por questão (sem correção)."""
    agent = _agent(model_id, ANSWERSHEET_SYSTEM)
    content = [{"text": answersheet_prompt(expected)}, _content_block(image_b64, ext)]
    result = agent(content, structured_output_model=AnswerSheetResult)
    return {"result": result.structured_output.model_dump(), "usage": _usage(result), "model": model_id}


def run_judge(model_id: str, kind: str, candidate_a: str, candidate_b: str,
              context: str = "") -> dict:
    """Juiz (model as a judge): compara duas saídas e aponta a de maior qualidade."""
    agent = _agent(model_id, JUDGE_SYSTEM)
    result = agent(judge_prompt(kind, candidate_a, candidate_b, context),
                   structured_output_model=JudgeResult)
    return {"result": result.structured_output.model_dump(), "usage": _usage(result), "model": model_id}


def run_examgen(model_id: str, theme: str, passages: list, num: int = 5, fmt: str = "mc") -> dict:
    """Gera questões ancoradas em trechos do KB. fmt='mc' (múltipla escolha) ou 'discursive'."""
    agent = _agent(model_id, EXAMGEN_SYSTEM, temperature=0.3)
    if fmt == "discursive":
        result = agent(examgen_discursive_prompt(theme, passages, num),
                       structured_output_model=ExamGenDiscResult)
    else:
        result = agent(examgen_prompt(theme, passages, num), structured_output_model=ExamGenResult)
    return {"result": result.structured_output.model_dump(), "usage": _usage(result), "model": model_id}
