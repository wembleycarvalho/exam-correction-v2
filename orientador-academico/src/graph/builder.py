"""Build the academic knowledge graph (NetworkX DiGraph) from the JSON dataset.

Node types: Discipline, Competency, Career, Program, Student.
Edge types (relation attr):
  PREREQUISITE_OF     Discipline -> Discipline
  DEVELOPS_COMPETENCY Discipline -> Competency  (weight)
  REQUIRES_COMPETENCY Career     -> Competency  (importance)
  COMPLEMENTS         Discipline -> Discipline  (reason)
  OFFERED_IN          Discipline -> Program     (derived from discipline.programs)
  COMPLETED           Student    -> Discipline  (grade, semester, year; from students.json)

Designed to migrate to Amazon Neptune later (same node/edge semantics).
"""
from __future__ import annotations

import json
import os
from typing import Any

import networkx as nx

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def _load(name: str) -> list[dict]:
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


class IntegrityError(ValueError):
    """Raised when the dataset has dangling references or invalid structure."""


def build_graph(data_dir: str | None = None) -> nx.DiGraph:
    """Load JSON files into a directed graph, validating referential integrity."""
    global DATA_DIR
    if data_dir:
        DATA_DIR = data_dir

    programs = _load("programs.json")
    disciplines = _load("disciplines.json")
    competencies = _load("competencies.json")
    careers = _load("careers.json")
    relationships = _load("relationships.json")
    students = _load("students.json")

    g = nx.DiGraph()

    # --- Nodes ---
    for p in programs:
        g.add_node(p["id"], **p)
    for c in competencies:
        g.add_node(c["id"], **c)
    for c in careers:
        g.add_node(c["id"], **c)
    for d in disciplines:
        g.add_node(d["id"], **d)
    for s in students:
        node = {k: v for k, v in s.items() if k not in ("completed", "enrolled")}
        g.add_node(s["id"], **node)

    node_ids = set(g.nodes)

    def require(node_id: str, ctx: str):
        if node_id not in node_ids:
            raise IntegrityError(f"Dangling reference to '{node_id}' in {ctx}")

    # --- Derived edges: OFFERED_IN (discipline -> program), com requirement por curso ---
    for d in disciplines:
        reqs = d.get("requirements") or {}
        for prog in d.get("programs", []):
            require(prog, f"discipline {d['id']}.programs")
            g.add_edge(d["id"], prog, relation="OFFERED_IN",
                       requirement=reqs.get(prog, "mandatory"))

    # --- Relationship edges ---
    for e in relationships:
        require(e["from"], f"relationship {e['type']}.from")
        require(e["to"], f"relationship {e['type']}.to")
        g.add_edge(e["from"], e["to"], relation=e["type"], **(e.get("properties") or {}))

    # --- COMPLETED edges (student -> discipline) ---
    for s in students:
        require(s["target_career"], f"student {s['id']}.target_career")
        require(s["program"], f"student {s['id']}.program")
        for c in s.get("completed", []):
            require(c["discipline"], f"student {s['id']}.completed")
            g.add_edge(s["id"], c["discipline"], relation="COMPLETED",
                       grade=c.get("grade"), semester=c.get("semester"), year=c.get("year"))
        # Matrícula do semestre atual (cursando agora).
        for did in s.get("enrolled", []):
            require(did, f"student {s['id']}.enrolled")
            g.add_edge(s["id"], did, relation="ENROLLED")

    _validate(g)
    return g


def _validate(g: nx.DiGraph) -> None:
    """Extra structural checks beyond dangling references."""
    # Prerequisite edges must not form a cycle (topological order must exist).
    prereq = prerequisite_subgraph(g)
    if not nx.is_directed_acyclic_graph(prereq):
        cycle = nx.find_cycle(prereq)
        raise IntegrityError(f"Prerequisite graph has a cycle: {cycle}")


def prerequisite_subgraph(g: nx.DiGraph) -> nx.DiGraph:
    """Subgraph containing only PREREQUISITE_OF edges (discipline -> discipline)."""
    sub = nx.DiGraph()
    sub.add_nodes_from(n for n, d in g.nodes(data=True) if d.get("type") == "Discipline")
    for u, v, d in g.edges(data=True):
        if d.get("relation") == "PREREQUISITE_OF":
            sub.add_edge(u, v, **d)
    return sub


def nodes_by_type(g: nx.DiGraph, node_type: str) -> list[dict]:
    return [dict(d) for _, d in g.nodes(data=True) if d.get("type") == node_type]
