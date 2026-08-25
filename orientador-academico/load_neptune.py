#!/usr/bin/env python3
"""Carrega o dataset (JSON) no Amazon Neptune via openCypher (idempotente).

Uso:
  NEPTUNE_ENDPOINT=<cluster-endpoint> AWS_REGION=us-east-1 \
    python load_neptune.py [--clear]

Requer credenciais AWS com acesso ao Neptune (neptune-db:*ViaQuery) e conectividade de
rede ao cluster (dentro da VPC, ou via túnel). --clear apaga o grafo antes de recarregar.
"""
import os
import sys

from src.graph.neptune_client import NeptuneClient
from src.graph import neptune_store as ns


def main(argv):
    if not os.environ.get("NEPTUNE_ENDPOINT"):
        print("Defina NEPTUNE_ENDPOINT (endpoint do cluster Neptune).")
        return 1
    client = NeptuneClient()
    if "--clear" in argv:
        print("Limpando grafo existente…")
        ns.clear_graph(client)
    print(f"Carregando dataset em {client.url} …")
    counts = ns.load_json_to_neptune(client)
    print(f"OK — {counts['nodes']} nós e {counts['edges']} arestas carregados.")
    # sanidade: reconstrói e reporta stats
    from src.graph import queries as q
    g = ns.build_graph_from_neptune(client)
    print("Stats do grafo no Neptune:", q.graph_stats(g))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
