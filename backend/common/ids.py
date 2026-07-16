"""Geração de identificadores.

TestID: código compacto e único impresso no QR da prova. NÃO contém PII — apenas resolve
o vínculo em `test_registry`. Formato legível (sem caracteres ambíguos).
"""
import secrets

# Alfabeto sem 0/O/1/I/L para evitar ambiguidade em impressão/leitura.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_test_id(length: int = 10) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
