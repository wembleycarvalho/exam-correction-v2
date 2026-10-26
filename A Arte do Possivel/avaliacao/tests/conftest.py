"""Configura o ambiente de testes: paths de import (espelham o layout de runtime) e env."""
import os
import sys

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("MODEL_CONFIG_TABLE", "test-model-config")

_ROOT = os.path.dirname(os.path.dirname(__file__))
# backend/ e agents/ ficam na raiz do sys.path do runtime; espelhamos aqui.
for p in ("backend", "agents"):
    full = os.path.join(_ROOT, p)
    if full not in sys.path:
        sys.path.insert(0, full)
