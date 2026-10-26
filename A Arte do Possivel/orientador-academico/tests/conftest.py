import os
import sys

import pytest

# Garante que 'src' e a raiz do módulo estejam no path ao rodar pytest de qualquer lugar.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.graph.builder import build_graph  # noqa: E402


@pytest.fixture(scope="session")
def graph():
    return build_graph()
