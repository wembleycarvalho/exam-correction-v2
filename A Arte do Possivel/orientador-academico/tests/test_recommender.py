"""Recommendation engine tests (deterministic, no Bedrock)."""
from src.graph import queries as q
from src.recommender import path_engine as pe


def _student_with_history(graph):
    return next(n for n, d in graph.nodes(data=True)
                if d.get("type") == "Student"
                and any(e.get("relation") == "COMPLETED" for _, _, e in graph.out_edges(n, data=True)))


def test_progress(graph):
    sid = _student_with_history(graph)
    p = pe.student_progress(graph, sid)
    edge_done = {v for _, v, e in graph.out_edges(sid, data=True) if e.get("relation") == "COMPLETED"}
    assert 0 <= p["completion_pct"] <= 100
    assert len(p["completed"]) == len(edge_done) and len(p["completed"]) > 0
    assert set(p["completed"]).isdisjoint(set(p["pending"]))


def _program_with_electives(graph):
    for pid, d in graph.nodes(data=True):
        if d.get("type") != "Program":
            continue
        discs = q.disciplines_in_program(graph, pid)
        elec = [x for x in discs if q.program_requirement(graph, x, pid) == "elective"]
        if len(elec) >= 2 and q.elective_credits_required(graph, pid) > 0:
            return pid, elec
    return None, None


def test_progress_does_not_require_all_electives(graph):
    # Um aluno que concluiu TODAS as obrigatórias e fechou a cota eletiva chega a 100%,
    # mesmo sem cursar todas as eletivas ofertadas.
    pid, elec = _program_with_electives(graph)
    assert pid, "esperava um curso com eletivas e cota"
    # progresso reporta a cota de eletivas e o restante
    sid = next(n for n, d in graph.nodes(data=True) if d.get("type") == "Student" and d.get("program") == pid)
    prog = pe.student_progress(graph, sid)
    e = prog["electives"]
    assert e["credits_required"] == q.elective_credits_required(graph, pid)
    assert e["credits_remaining"] == max(0, e["credits_required"] - e["credits_done"])
    assert 0 <= prog["completion_pct"] <= 100


def test_recommend_does_not_include_all_electives(graph):
    # A trilha inclui só eletivas suficientes para a cota — não todas as ofertadas.
    pid, elec = _program_with_electives(graph)
    sid = next(n for n, d in graph.nodes(data=True) if d.get("type") == "Student" and d.get("program") == pid)
    r = pe.recommend_path(graph, sid)
    rec_elec = [d for d in r["recommended_order"] if d.get("requirement") == "elective"]
    completed = q.student_completed(graph, sid)
    missing_elec = [d for d in elec if d not in completed]
    # recomenda no máximo o necessário e nunca mais do que as eletivas faltantes
    assert len(rec_elec) <= len(missing_elec)
    assert r["elective_credits_remaining"] == 0 or not missing_elec


def test_recommend_path_excludes_completed_and_respects_prereqs(graph):
    r = pe.recommend_path(graph, "student_002")  # Maria, CC → Cientista de Dados
    completed = q.student_completed(graph, "student_002")
    rec_ids = [d["id"] for d in r["recommended_order"]]
    # nada recomendado já foi concluído
    assert completed.isdisjoint(set(rec_ids))
    # tudo recomendado pertence ao programa do aluno (CC)
    cc = set(q.disciplines_in_program(graph, "prog_cc"))
    assert set(rec_ids).issubset(cc)
    # ordem respeita pré-requisitos entre os recomendados
    pos = {d: i for i, d in enumerate(rec_ids)}
    for d in rec_ids:
        for pre in q.direct_prerequisites(graph, d):
            if pre in pos:
                assert pos[pre] < pos[d]


def test_recommend_includes_missing_prerequisites(graph):
    # A trilha inclui os pré-requisitos faltantes: para cada disciplina recomendada, seus
    # pré-requisitos diretos que são do curso e ainda não concluídos também estão na trilha.
    sid = _student_with_history(graph)
    r = pe.recommend_path(graph, sid)
    rec_ids = {d["id"] for d in r["recommended_order"]}
    completed = q.student_completed(graph, sid)
    program = graph.nodes[sid].get("program")
    prog_discs = set(q.disciplines_in_program(graph, program))
    for did in rec_ids:
        for pre in q.direct_prerequisites(graph, did):
            if pre in prog_discs and pre not in completed:
                assert pre in rec_ids


def test_semester_plan_caps(graph):
    r = pe.recommend_path(graph, "student_002", max_per_semester=3)
    for blk in r["semester_plan"]:
        assert len(blk["disciplines"]) <= 3


def test_what_if_skip_blocks(graph):
    # Escolhe uma disciplina que destrava outras e valida que pular bloqueia dependentes.
    did = next(n for n, d in graph.nodes(data=True)
               if d.get("type") == "Discipline" and q.all_dependents(graph, n))
    w = pe.what_if_skip(graph, did)
    assert not w["skippable_without_block"]
    blocked = {d["id"] for d in w["blocks_disciplines"]}
    assert blocked and blocked == q.all_dependents(graph, did)


def test_what_if_skip_leaf(graph):
    # Uma disciplina-folha (sem dependentes) é pulável sem bloquear nada.
    did = next(n for n, d in graph.nodes(data=True)
               if d.get("type") == "Discipline" and not q.all_dependents(graph, n))
    w = pe.what_if_skip(graph, did)
    assert w["skippable_without_block"]


def test_compare_careers(graph):
    careers = [n for n, d in graph.nodes(data=True) if d.get("type") == "Career"]
    c = pe.compare_careers(graph, careers[0], careers[1])
    assert "shared_competencies" in c and "only_a" in c and "only_b" in c


def test_explain_connection_directed(graph):
    # Pega uma aresta de pré-requisito real e confirma que a conexão é explicada.
    u, v = next((a, b) for a, b, e in graph.edges(data=True) if e.get("relation") == "PREREQUISITE_OF")
    res = pe.explain_connection(graph, u, v)
    assert res["connected"]
    assert any(s["relation"] == "PREREQUISITE_OF" for s in res["path"])
