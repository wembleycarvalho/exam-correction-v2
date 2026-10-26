"""Amazon Neptune as the source of truth for the academic knowledge graph.

- load_json_to_neptune(): loads the JSON dataset into Neptune (idempotent MERGE).
- build_graph_from_neptune(): hydrates the same nx.DiGraph the engine/queries expect,
  so all the tested traversal/recommendation logic runs unchanged on Neptune-backed data.

Node label = node type (Discipline/Competency/Career/Program/Student).
Edge type  = relation (PREREQUISITE_OF/DEVELOPS_COMPETENCY/REQUIRES_COMPETENCY/
             COMPLEMENTS/OFFERED_IN/COMPLETED).
List attributes (programs, key_tools) are not stored as scalar props: `programs` is
represented by OFFERED_IN edges; `key_tools` is flattened to a CSV string.
"""
from __future__ import annotations

import json
import os

import networkx as nx

from . import builder as jb
from .neptune_client import NeptuneClient

# Não viram propriedade escalar de nó (listas/dicts são derivados de arestas).
_SKIP_PROPS = {"type", "programs", "completed", "enrolled", "requirements"}
NODE_GROUPS = ["Program", "Competency", "Career", "Discipline", "Student"]


def _scalar_props(node: dict) -> dict:
    out = {}
    for k, v in node.items():
        if k in _SKIP_PROPS or v is None:
            continue
        out[k] = "; ".join(map(str, v)) if isinstance(v, list) else v
    return out


def _load_json(data_dir: str) -> dict:
    def rd(name):
        with open(os.path.join(data_dir, name), encoding="utf-8") as fh:
            return json.load(fh)
    return {
        "programs": rd("programs.json"), "competencies": rd("competencies.json"),
        "careers": rd("careers.json"), "disciplines": rd("disciplines.json"),
        "students": rd("students.json"), "relationships": rd("relationships.json"),
    }


def clear_graph(client: NeptuneClient) -> None:
    client.query("MATCH (n) DETACH DELETE n")


def load_json_to_neptune(client: NeptuneClient, data_dir: str | None = None) -> dict:
    """Idempotently load the JSON dataset into Neptune. Returns counts."""
    data = _load_json(data_dir or jb.DATA_DIR)

    label_of = {"programs": "Program", "competencies": "Competency", "careers": "Career",
                "disciplines": "Discipline", "students": "Student"}
    n_nodes = 0
    for key, label in label_of.items():
        for item in data[key]:
            client.query(f"MERGE (n:{label} {{id: $id}}) SET n += $props",
                         {"id": item["id"], "props": _scalar_props(item)})
            n_nodes += 1

    n_edges = 0
    for d in data["disciplines"]:
        reqs = d.get("requirements") or {}
        for prog in d.get("programs", []):
            _edge(client, "OFFERED_IN", d["id"], prog,
                  {"requirement": reqs.get(prog, "mandatory")}); n_edges += 1
    for e in data["relationships"]:
        _edge(client, e["type"], e["from"], e["to"], e.get("properties") or {}); n_edges += 1
    for s in data["students"]:
        for c in s.get("completed", []):
            _edge(client, "COMPLETED", s["id"], c["discipline"],
                  {"grade": c.get("grade"), "semester": c.get("semester"), "year": c.get("year")})
            n_edges += 1
        for did in s.get("enrolled", []):
            _edge(client, "ENROLLED", s["id"], did, {})
            n_edges += 1

    return {"nodes": n_nodes, "edges": n_edges}


def set_student_target(client: NeptuneClient, student_id: str, career_id: str) -> None:
    """Grava o novo objetivo de carreira do aluno no Neptune (WriteDataViaQuery)."""
    client.query("MATCH (s:Student {id: $sid}) SET s.target_career = $cid",
                 {"sid": student_id, "cid": career_id})


def list_pending_course_changes(client: NeptuneClient) -> list[dict]:
    """Lê do Neptune (ao vivo) os alunos com pedido de troca de curso pendente. Evita a
    inconsistência do grafo em cache por container (o pedido pode ter sido criado noutro)."""
    return client.query(
        "MATCH (s:Student) WHERE s.course_change_to IS NOT NULL "
        "RETURN s.id AS id, s.name AS name, s.program AS program, s.course_change_to AS to_program, "
        "s.course_change_career AS career, s.course_change_at AS at, s.course_change_status AS status")


def resolve_course_change(client: NeptuneClient, student_id: str, decision: str,
                          to_program: str | None = None) -> None:
    """Coordenador decide um pedido de troca de curso. `accept` efetiva a troca (muda o
    curso do aluno); `deny` apenas marca como negado. Em ambos, limpa o pedido pendente."""
    if decision == "accept" and to_program:
        client.query(
            "MATCH (s:Student {id: $sid}) SET s.program = $p, s.course_change_status = 'accepted' "
            "REMOVE s.course_change_to, s.course_change_career, s.course_change_at",
            {"sid": student_id, "p": to_program})
    else:
        client.query(
            "MATCH (s:Student {id: $sid}) SET s.course_change_status = 'denied' "
            "REMOVE s.course_change_to, s.course_change_career, s.course_change_at",
            {"sid": student_id})


def request_course_change(client: NeptuneClient, student_id: str, program_id: str,
                          career_id: str, when: str) -> None:
    """Registra um PEDIDO de troca de curso no perfil do aluno (pendente). A troca NÃO
    acontece automaticamente — fica visível para análise do coordenador/instituição."""
    client.query(
        "MATCH (s:Student {id: $sid}) SET s.course_change_to = $p, s.course_change_career = $c, "
        "s.course_change_at = $at, s.course_change_status = 'pending'",
        {"sid": student_id, "p": program_id, "c": career_id or "", "at": when})


def _edge(client: NeptuneClient, relation: str, frm: str, to: str, props: dict) -> None:
    client.query(
        f"MATCH (a {{id: $f}}), (b {{id: $t}}) MERGE (a)-[r:{relation}]->(b) SET r += $props",
        {"f": frm, "t": to, "props": {k: v for k, v in props.items() if v is not None}})


def build_graph_from_neptune(client: NeptuneClient) -> nx.DiGraph:
    """Hydrate a NetworkX DiGraph from Neptune (source of truth)."""
    g = nx.DiGraph()
    for row in client.query("MATCH (n) RETURN labels(n) AS labels, properties(n) AS props"):
        props = dict(row["props"])
        node_type = (row["labels"] or [props.get("type")])[0]
        props["type"] = node_type
        g.add_node(props.get("id"), **props)
    for row in client.query(
            "MATCH (a)-[r]->(b) RETURN a.id AS src, b.id AS dst, type(r) AS relation, "
            "properties(r) AS props"):
        g.add_edge(row["src"], row["dst"], relation=row["relation"], **(row.get("props") or {}))
    # Reconstrói programs[] e requirements{} das arestas OFFERED_IN (compat. com o JSON).
    for n, d in g.nodes(data=True):
        if d.get("type") == "Discipline":
            offered = [(v, e) for _, v, e in g.out_edges(n, data=True)
                       if e.get("relation") == "OFFERED_IN"]
            d["programs"] = [v for v, _ in offered]
            d["requirements"] = {v: e.get("requirement", "mandatory") for v, e in offered}
    return g
