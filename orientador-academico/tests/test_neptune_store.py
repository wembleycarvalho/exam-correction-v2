"""Round-trip test for the Neptune store using an in-memory fake openCypher engine.

Validates that load_json_to_neptune() + build_graph_from_neptune() reproduce the same
graph the JSON builder produces — without needing a real Neptune cluster.
"""
import re

from src.graph import neptune_store as ns
from src.graph.builder import build_graph
from src.graph import queries as q


class FakeNeptune:
    """Interprets only the handful of openCypher shapes neptune_store issues."""

    def __init__(self):
        self.nodes = {}   # id -> (label, props)
        self.edges = []   # (relation, src, dst, props)

    def query(self, cypher, parameters=None):
        p = parameters or {}
        if cypher.startswith("MATCH (n) DETACH DELETE"):
            self.nodes.clear(); self.edges.clear(); return []
        m = re.match(r"MERGE \(n:(\w+) \{id: \$id\}\)", cypher)
        if m:
            self.nodes[p["id"]] = (m.group(1), dict(p["props"], id=p["id"])); return []
        m = re.search(r"MERGE \(a\)-\[r:(\w+)\]->\(b\)", cypher)
        if m and cypher.startswith("MATCH (a {id: $f})"):
            self.edges.append((m.group(1), p["f"], p["t"], dict(p["props"]))); return []
        if "RETURN labels(n)" in cypher:
            return [{"labels": [lbl], "props": props} for _, (lbl, props) in self.nodes.items()]
        if "RETURN a.id AS src" in cypher:
            return [{"src": s, "dst": d, "relation": rel, "props": pr}
                    for rel, s, d, pr in self.edges]
        raise AssertionError("query não suportada pelo fake: " + cypher)


def test_roundtrip_matches_json_graph():
    fake = FakeNeptune()
    counts = ns.load_json_to_neptune(fake)
    g_nep = ns.build_graph_from_neptune(fake)
    g_json = build_graph()

    # mesmo número de nós e arestas
    assert g_nep.number_of_nodes() == g_json.number_of_nodes()
    assert g_nep.number_of_edges() == g_json.number_of_edges()
    assert counts["nodes"] == g_json.number_of_nodes()

    # traversals-chave coincidem
    assert set(q.direct_prerequisites(g_nep, "disc_028")) == set(q.direct_prerequisites(g_json, "disc_028"))
    assert set(q.disciplines_in_program(g_nep, "prog_cc")) == set(q.disciplines_in_program(g_json, "prog_cc"))
    assert q.student_completed(g_nep, "student_003") == q.student_completed(g_json, "student_003")

    # tipos preservados
    assert g_nep.nodes["disc_028"]["type"] == "Discipline"
    assert g_nep.nodes["career_001"]["type"] == "Career"
