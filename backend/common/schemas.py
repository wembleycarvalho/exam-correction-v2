"""Validação leve dos contratos JSON de saída dos agentes (R1.4).

Sem dependências externas (nada de jsonschema). Valida o mínimo necessário para persistir
uma correção consistente e falhar cedo com mensagem clara (PT-BR) quando o modelo devolve
algo fora do contrato.
"""
from typing import Tuple


class SchemaError(ValueError):
    pass


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_essay_result(d: dict) -> Tuple[bool, str]:
    if not isinstance(d, dict):
        return False, "Resultado de redação não é um objeto."
    crit = d.get("criteria")
    if not isinstance(crit, list) or not crit:
        return False, "Resultado de redação sem lista de critérios."
    for c in crit:
        if not isinstance(c, dict) or "score" not in c or "maxScore" not in c:
            return False, "Critério de redação incompleto (score/maxScore)."
        if not _num(c["score"]) or not _num(c["maxScore"]):
            return False, "Notas de critério devem ser numéricas."
    if not _num(d.get("totalScore")):
        return False, "totalScore ausente ou não numérico."
    return True, ""


def validate_exam_result(d: dict) -> Tuple[bool, str]:
    if not isinstance(d, dict):
        return False, "Resultado de prova não é um objeto."
    questoes = d.get("questoes")
    if not isinstance(questoes, list) or not questoes:
        return False, "Resultado de prova sem lista de questões."
    for q in questoes:
        if not isinstance(q, dict) or "nota" not in q or "notaMaxima" not in q:
            return False, "Questão incompleta (nota/notaMaxima)."
        if not _num(q["nota"]) or not _num(q["notaMaxima"]):
            return False, "Notas de questão devem ser numéricas."
    if not _num(d.get("notaTotal")):
        return False, "notaTotal ausente ou não numérico."
    return True, ""


def validate_transcription_result(d: dict, kind: str) -> Tuple[bool, str]:
    if not isinstance(d, dict):
        return False, "Transcrição não é um objeto."
    if kind == "exam":
        if not isinstance(d.get("transcricao"), list):
            return False, "Transcrição de prova sem lista 'transcricao'."
    else:
        if not isinstance(d.get("text"), str) or not d.get("text").strip():
            return False, "Transcrição de redação vazia."
    return True, ""


def validate_author_result(d: dict) -> Tuple[bool, str]:
    if not isinstance(d, dict) or not isinstance(d.get("resposta"), str) or not d["resposta"].strip():
        return False, "Resposta sugerida vazia."
    return True, ""


def ensure(valid_msg: Tuple[bool, str]) -> None:
    ok, msg = valid_msg
    if not ok:
        raise SchemaError(msg)
