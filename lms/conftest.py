"""Coloca a raiz do módulo (lms/) no sys.path para que os pacotes de topo
`common`/`api`/`ingest` sejam importáveis nos testes — o mesmo layout do bundle da Lambda
(cujo task root é o conteúdo de lms/)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
