"""Helpers de resposta HTTP e contrato de erro padronizado (PT-BR).

Formato de erro: {"code": "<CODIGO>", "message": "<mensagem em PT-BR>"}.
Nunca expor detalhes internos/sensíveis nas mensagens.
"""
import json
from decimal import Decimal
from typing import Any


def _json_default(value: Any):
    # DynamoDB retorna números como Decimal; serializa como int/float.
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, set):
        return list(value)
    raise TypeError(f"Tipo não serializável: {type(value)}")


def response(status: int, body: Any) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False, default=_json_default),
    }


def error(status: int, code: str, message: str) -> dict:
    return response(status, {"code": code, "message": message})


def parse_json_body(event: dict) -> dict:
    """Lê e faz parse do corpo JSON de um evento de API Gateway (proxy)."""
    raw = event.get("body") if isinstance(event, dict) else None
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    return json.loads(raw)  # pode lançar JSONDecodeError; tratar no chamador


# Códigos de erro comuns
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
INVALID_BODY = "INVALID_BODY"
FORBIDDEN = "FORBIDDEN"
UNAUTHORIZED = "UNAUTHORIZED"
NOT_FOUND = "NOT_FOUND"
METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
