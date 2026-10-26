"""Graph construction + referential integrity tests (no Bedrock)."""
import json
import os

import networkx as nx
import pytest

from src.graph import builder
from src.graph.builder import build_graph, IntegrityError, prerequisite_subgraph

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def test_builds_under_1s():
    import time
    t0 = time.time()
    g = build_graph()
    assert time.time() - t0 < 1.0
    assert g.number_of_nodes() > 0


def _json(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def test_node_counts(graph):
    # Data-agnóstico: as contagens do grafo batem com os arquivos JSON (fonte da verdade).
    types = {}
    for _, d in graph.nodes(data=True):
        types[d["type"]] = types.get(d["type"], 0) + 1
    assert types["Discipline"] == len(_json("disciplines.json"))
    assert types["Competency"] == len(_json("competencies.json"))
    assert types["Career"] == len(_json("careers.json"))
    assert types["Program"] == len(_json("programs.json"))
    assert types["Student"] == len(_json("students.json"))


def test_no_dangling_edges(graph):
    ids = set(graph.nodes)
    for u, v in graph.edges():
        assert u in ids and v in ids


def test_prerequisite_graph_is_dag(graph):
    assert nx.is_directed_acyclic_graph(prerequisite_subgraph(graph))


def test_offered_in_edges_match_programs(graph):
    for n, d in graph.nodes(data=True):
        if d.get("type") != "Discipline":
            continue
        offered = {v for _, v, e in graph.out_edges(n, data=True) if e["relation"] == "OFFERED_IN"}
        assert offered == set(d["programs"])


def test_shared_disciplines_exist(graph):
    shared = [n for n, d in graph.nodes(data=True)
              if d.get("type") == "Discipline" and len(d.get("programs", [])) > 1]
    assert len(shared) >= 10  # ES ∩ CC


def test_cycle_detection(tmp_path, monkeypatch):
    # Cria um dataset temporário com ciclo de pré-requisito e espera IntegrityError.
    import shutil
    dst = tmp_path / "data"
    shutil.copytree(DATA, dst)
    rels = json.load(open(dst / "relationships.json"))
    rels.append({"type": "PREREQUISITE_OF", "from": "disc_004", "to": "disc_001", "properties": {}})
    rels.append({"type": "PREREQUISITE_OF", "from": "disc_001", "to": "disc_004", "properties": {}})
    json.dump(rels, open(dst / "relationships.json", "w"))
    with pytest.raises(IntegrityError):
        build_graph(data_dir=str(dst))
    build_graph(data_dir=DATA)  # restaura DATA_DIR global para os demais testes
