"""Ambiente de testes do módulo Entrevistador Virtual (FastAPI + WebSocket).

Coloca a raiz do módulo no sys.path para `import server` funcionar, espelhando o runtime.
"""
import os
import sys

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

_MOD_ROOT = os.path.dirname(os.path.dirname(__file__))
if _MOD_ROOT not in sys.path:
    sys.path.insert(0, _MOD_ROOT)
