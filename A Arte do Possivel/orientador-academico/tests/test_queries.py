"""Graph traversal query tests (no Bedrock)."""
from src.graph import queries as q


def test_stats(graph):
    s = q.graph_stats(graph)
    disc = [n for n, d in graph.nodes(data=True) if d.get("type") == "Discipline"]
    care = [n for n, d in graph.nodes(data=True) if d.get("type") == "Career"]
    assert s["disciplines"] == len(disc)
    assert s["careers"] == len(care)
    assert s["prerequisite_is_dag"] is True


def test_direct_and_transitive_prereqs(graph):
    # Data-agnóstico: encontra uma cadeia de 2 níveis (pp -> p -> d) e valida transitividade.
    found = False
    for d in [n for n, dd in graph.nodes(data=True) if dd.get("type") == "Discipline"]:
        for p in q.direct_prerequisites(graph, d):
            pps = q.direct_prerequisites(graph, p)
            if pps:
                pp = pps[0]
                allp = q.all_prerequisites(graph, d)
                assert p in allp and pp in allp
                found = True
                break
        if found:
            break
    assert found, "esperava ao menos uma cadeia de pré-requisitos de 2 níveis"


def test_order_respects_prerequisites(graph):
    ids = ["disc_028", "disc_014", "disc_023", "disc_008", "disc_004"]
    ordered = q.order_by_prerequisites(graph, ids)
    # cada disciplina aparece depois de seus pré-requisitos presentes na lista
    pos = {d: i for i, d in enumerate(ordered)}
    for d in ids:
        for pre in q.direct_prerequisites(graph, d):
            if pre in pos:
                assert pos[pre] < pos[d]


def test_program_membership(graph):
    # Cada disciplina do curso tem esse curso em 'programs'; e existe disciplina compartilhada.
    cc = q.disciplines_in_program(graph, "prog_cc")
    assert cc, "prog_cc deveria ter disciplinas"
    for did in cc:
        assert "prog_cc" in (graph.nodes[did].get("programs") or [])
    shared = [d for d in cc if len(graph.nodes[d].get("programs") or []) > 1]
    assert shared, "esperava disciplinas compartilhadas com outros cursos"


def test_student_completed(graph):
    # Escolhe um aluno com histórico e confere que bate com as arestas COMPLETED.
    sid = next(n for n, d in graph.nodes(data=True)
               if d.get("type") == "Student"
               and any(e.get("relation") == "COMPLETED" for _, _, e in graph.out_edges(n, data=True)))
    done = q.student_completed(graph, sid)
    edge_done = {v for _, v, e in graph.out_edges(sid, data=True) if e.get("relation") == "COMPLETED"}
    assert done == edge_done and len(done) > 0


def test_career_competencies(graph):
    cid = next(n for n, d in graph.nodes(data=True) if d.get("type") == "Career")
    comps = q.career_competencies(graph, cid)
    assert comps and all("importance" in c for c in comps)
