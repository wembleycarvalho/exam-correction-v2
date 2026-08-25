"""Graph traversal helpers over the academic knowledge graph.

Kept intentionally small and pure so they map cleanly to Gremlin/openCypher when the
prototype migrates to Amazon Neptune.
"""
from __future__ import annotations

import networkx as nx

from .builder import prerequisite_subgraph


def get_node(g: nx.DiGraph, node_id: str) -> dict:
    if node_id not in g.nodes:
        raise KeyError(node_id)
    return dict(g.nodes[node_id])


def graph_stats(g: nx.DiGraph) -> dict:
    by_type: dict[str, int] = {}
    for _, d in g.nodes(data=True):
        by_type[d.get("type", "?")] = by_type.get(d.get("type", "?"), 0) + 1
    by_rel: dict[str, int] = {}
    for _, _, d in g.edges(data=True):
        by_rel[d.get("relation", "?")] = by_rel.get(d.get("relation", "?"), 0) + 1
    prereq = prerequisite_subgraph(g)
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "disciplines": by_type.get("Discipline", 0),
        "competencies": by_type.get("Competency", 0),
        "careers": by_type.get("Career", 0),
        "programs": by_type.get("Program", 0),
        "students": by_type.get("Student", 0),
        "nodes_by_type": by_type,
        "edges_by_relation": by_rel,
        "prerequisite_is_dag": nx.is_directed_acyclic_graph(prereq),
    }


def _out(g: nx.DiGraph, node_id: str, relation: str):
    """Successors reached via edges of a given relation."""
    for _, v, d in g.out_edges(node_id, data=True):
        if d.get("relation") == relation:
            yield v, d


def _in(g: nx.DiGraph, node_id: str, relation: str):
    """Predecessors that reach node_id via edges of a given relation."""
    for u, _, d in g.in_edges(node_id, data=True):
        if d.get("relation") == relation:
            yield u, d


def career_competencies(g: nx.DiGraph, career_id: str) -> list[dict]:
    """Competencies required by a career, with importance."""
    out = []
    for comp_id, d in _out(g, career_id, "REQUIRES_COMPETENCY"):
        out.append({"competency": comp_id, "importance": d.get("importance", "important")})
    return out


def disciplines_developing(g: nx.DiGraph, competency_id: str) -> list[dict]:
    """Disciplines that develop a competency, with weight."""
    out = []
    for disc_id, d in _in(g, competency_id, "DEVELOPS_COMPETENCY"):
        out.append({"discipline": disc_id, "weight": float(d.get("weight", 0.0))})
    return out


def competencies_of_discipline(g: nx.DiGraph, discipline_id: str) -> list[dict]:
    out = []
    for comp_id, d in _out(g, discipline_id, "DEVELOPS_COMPETENCY"):
        out.append({"competency": comp_id, "weight": float(d.get("weight", 0.0))})
    return out


def direct_prerequisites(g: nx.DiGraph, discipline_id: str) -> list[str]:
    """Immediate prerequisites of a discipline (edge prereq -> discipline)."""
    return [u for u, _ in _in(g, discipline_id, "PREREQUISITE_OF")]


def all_prerequisites(g: nx.DiGraph, discipline_id: str) -> set[str]:
    """Transitive closure of prerequisites (everything that must come before)."""
    prereq = prerequisite_subgraph(g)
    if discipline_id not in prereq:
        return set()
    return set(nx.ancestors(prereq, discipline_id))


def unlocks(g: nx.DiGraph, discipline_id: str) -> list[str]:
    """Disciplines that have this discipline as a direct prerequisite."""
    return [v for v, _ in _out(g, discipline_id, "PREREQUISITE_OF")]


def all_dependents(g: nx.DiGraph, discipline_id: str) -> set[str]:
    """Transitive closure of disciplines that (in)directly depend on this one."""
    prereq = prerequisite_subgraph(g)
    if discipline_id not in prereq:
        return set()
    return set(nx.descendants(prereq, discipline_id))


def complements(g: nx.DiGraph, discipline_id: str) -> list[dict]:
    out = []
    for v, d in _out(g, discipline_id, "COMPLEMENTS"):
        out.append({"discipline": v, "reason": d.get("reason", "")})
    for u, d in _in(g, discipline_id, "COMPLEMENTS"):
        out.append({"discipline": u, "reason": d.get("reason", "")})
    return out


def disciplines_in_program(g: nx.DiGraph, program_id: str) -> list[str]:
    return [u for u, _ in _in(g, program_id, "OFFERED_IN")]


def program_requirement(g: nx.DiGraph, discipline_id: str, program_id: str) -> str:
    """'mandatory' ou 'elective' de uma disciplina num curso (lê o mapa do nó ou a aresta)."""
    reqs = g.nodes[discipline_id].get("requirements") or {}
    if program_id in reqs:
        return reqs[program_id]
    for _, v, d in g.out_edges(discipline_id, data=True):
        if v == program_id and d.get("relation") == "OFFERED_IN":
            return d.get("requirement", "mandatory")
    return "mandatory"


def elective_credits_required(g: nx.DiGraph, program_id: str) -> int:
    """Créditos eletivos que o curso exige (0 = sem cota / sem eletivas)."""
    if program_id not in g.nodes:
        return 0
    return int(g.nodes[program_id].get("elective_credits_required") or 0)


def credits_of(g: nx.DiGraph, discipline_id: str) -> int:
    return int(g.nodes[discipline_id].get("credits") or 0)


def student_completed(g: nx.DiGraph, student_id: str) -> set[str]:
    return {v for v, _ in _out(g, student_id, "COMPLETED")}


def student_enrolled(g: nx.DiGraph, student_id: str) -> set[str]:
    """Disciplinas que o aluno está cursando neste semestre (aresta ENROLLED)."""
    return {v for v, _ in _out(g, student_id, "ENROLLED")}


def order_by_prerequisites(g: nx.DiGraph, discipline_ids: list[str]) -> list[str]:
    """Order the given disciplines so prerequisites come first.

    Uses topological sort on the induced prerequisite subgraph; ties broken by
    suggested semester then code for a stable, sensible ordering.
    """
    prereq = prerequisite_subgraph(g)
    wanted = set(discipline_ids)
    induced = prereq.subgraph(wanted).copy()
    # Lexicographic topo sort with (semester, code) as the tie-break key.
    def key(n):
        nd = g.nodes[n]
        return (nd.get("semester_suggested", 99), nd.get("code", n))
    ordered = list(nx.lexicographical_topological_sort(induced, key=key))
    # Isolated disciplines (no prereq relations among the set) are included by subgraph.
    return ordered
