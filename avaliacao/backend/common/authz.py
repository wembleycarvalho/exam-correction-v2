"""Autorização/verificação para as Lambdas atrás do CloudFront.

- verify_origin: confirma que a requisição veio do CloudFront (header secreto de origem).
  Principal barreira de borda da API. O segredo é lido do Secrets Manager em runtime e cacheado.
- get_claims / get_owner_id / has_group / require_group: leem as claims do JWT Cognito
  já validado pelo authorizer nativo do HTTP API.
"""
import os
from typing import Optional

import boto3

ORIGIN_HEADER = "x-origin-verify"
_ORIGIN_SECRET_ARN = os.environ.get("ORIGIN_SECRET_ARN", "")

_secrets = boto3.client("secretsmanager")
_cached_secret: Optional[str] = None


def _expected_origin_secret() -> str:
    global _cached_secret
    if _cached_secret is None:
        resp = _secrets.get_secret_value(SecretId=_ORIGIN_SECRET_ARN)
        _cached_secret = resp.get("SecretString", "")
    return _cached_secret


def _header(event: dict, name: str) -> str:
    headers = (event or {}).get("headers") or {}
    # API Gateway HTTP API normaliza headers para minúsculas.
    return headers.get(name) or headers.get(name.lower()) or ""


def verify_origin(event: dict) -> bool:
    """True se o header secreto de origem confere com o segredo esperado."""
    if not _ORIGIN_SECRET_ARN:
        # Sem segredo configurado (ex.: teste local): não bloqueia.
        return True
    return _header(event, ORIGIN_HEADER) == _expected_origin_secret()


def get_claims(event: dict) -> dict:
    return (
        (event or {})
        .get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    ) or {}


def get_owner_id(event: dict) -> str:
    """Identificador estável do usuário autenticado (sub do Cognito)."""
    return get_claims(event).get("sub", "")


def has_group(event: dict, group: str) -> bool:
    claims = get_claims(event)
    groups = claims.get("cognito:groups", "")
    if isinstance(groups, list):
        return group in groups
    # O authorizer do HTTP API serializa a lista como string, ex.: "[admin]" ou
    # "[admin, professor]". Normaliza removendo colchetes/aspas e separando.
    s = str(groups).strip().strip("[]")
    parts = [g.strip().strip('"\'') for g in s.replace(",", " ").split()]
    return group in parts


def require_group(event: dict, group: str) -> bool:
    return has_group(event, group)
