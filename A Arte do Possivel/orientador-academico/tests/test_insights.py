"""Tests for the graph-native analytics (src.recommender.insights) over the real dataset."""
from src.graph.builder import build_graph
from src.graph import queries as q
from src.recommender import insights as ins
from src.recommender import path_engine as pe


G = build_graph()


def test_bottlenecks_sorted_positive_and_program_scoped():
    rows = ins.prerequisite_bottlenecks(G, top=10)
    assert rows, "deveria haver disciplinas-gargalo"
    # Todas destravam algo e a lista está ordenada por unlocks_total desc.
    assert all(r["unlocks_total"] > 0 for r in rows)
    assert rows == sorted(rows, key=lambda r: (r["unlocks_total"], r["unlocks_direct"]), reverse=True)
    # Escopo por programa nunca aumenta o alcance de uma disciplina.
    es = {r["id"]: r for r in ins.prerequisite_bottlenecks(G, program_id="prog_es", top=None)}
    glob = {r["id"]: r for r in ins.prerequisite_bottlenecks(G, top=None)}
    for did, r in es.items():
        assert r["unlocks_total"] <= glob[did]["unlocks_total"]


def test_critical_path_is_a_real_prerequisite_chain():
    cp = ins.critical_path(G, program_id="prog_es")
    assert cp["length"] >= 2
    path = [d["id"] for d in cp["path"]]
    # Cada passo consecutivo deve ser um pré-requisito direto do próximo.
    for a, b in zip(path, path[1:]):
        assert a in q.direct_prerequisites(G, b), f"{a} deveria ser pré-req de {b}"


def test_competency_gaps_partition_and_shape():
    r = ins.competency_gaps(G, "student_001")
    total = len(q.career_competencies(G, r["target_career"]))
    s = r["summary"]
    assert s["lacunas"] + s["pendentes"] + s["cobertas"] == total == len(r["gaps"])
    assert all(g["status"] in ("lacuna", "pendente", "coberta") for g in r["gaps"])
    # Ordenação: lacunas antes de pendentes antes de cobertas.
    order = {"lacuna": 0, "pendente": 1, "coberta": 2}
    seq = [order[g["status"]] for g in r["gaps"]]
    assert seq == sorted(seq)


def test_curriculum_overview_bridges_and_overlap():
    cur = ins.curriculum_overview(G)
    n_programs = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "Program")
    assert len(cur["programs"]) == n_programs >= 2
    bridges = cur["bridges"]
    assert bridges and all(len(b["programs"]) > 1 for b in bridges)
    # A sobreposição ES×CC deve bater com as disciplinas presentes nos dois cursos.
    ov = next(o for o in cur["overlaps"] if {o["a"], o["b"]} == {"prog_es", "prog_cc"})
    inter = set(q.disciplines_in_program(G, "prog_es")) & set(q.disciplines_in_program(G, "prog_cc"))
    assert ov["shared"] == len(inter) == len(ov["shared_disciplines"])


def test_strategic_competencies_sorted_desc():
    rows = ins.strategic_competencies(G)
    assert rows
    scores = [r["strategic_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    assert all(r["coverage"] >= 0 and r["demand"] >= 0 for r in rows)


def test_subgraph_full_matches_graph_and_has_labels():
    sg = ins.subgraph(G, "full")
    assert sg["counts"]["nodes"] == G.number_of_nodes()
    assert sg["counts"]["edges"] == G.number_of_edges()
    # Toda label é um nome legível (nunca um id interno tipo disc_/prog_/career_).
    for n in sg["nodes"]:
        assert n["label"] and not str(n["label"]).startswith(("disc_", "prog_", "career_", "comp_", "student_"))
        assert n["type"] in {"Student", "Discipline", "Competency", "Career", "Program"}


def test_subgraph_scopes_edge_integrity_and_focus():
    for scope, nid in [("student", "student_001"), ("discipline", "disc_004"), ("career", "career_002")]:
        sg = ins.subgraph(G, scope, nid)
        ids = {n["id"] for n in sg["nodes"]}
        assert nid in ids and sg["focus"] and sg["focus"]["id"] == nid
        assert all(e["source"] in ids and e["target"] in ids for e in sg["edges"])
        assert all(e["label"] for e in sg["edges"])  # relação em PT
    # Escopo aluno inclui a carreira-alvo (aresta 'almeja').
    sg = ins.subgraph(G, "student", "student_001")
    assert any(e["relation"] == "TARGETS" for e in sg["edges"])


def test_program_detail_requirement_counts():
    pd = ins.program_detail(G, "prog_es")
    c = pd["counts"]
    assert c["mandatory"] + c["elective"] == c["disciplines"]
    assert c["mandatory"] > 0 and c["elective"] > 0  # o curso tem obrigatórias e eletivas
    for s in pd["semesters"]:
        for d in s["disciplines"]:
            assert d["requirement"] in ("mandatory", "elective")


def test_program_detail_consistency():
    pd = ins.program_detail(G, "prog_cc")
    assert pd["name"] and pd["counts"]["disciplines"] == len(q.disciplines_in_program(G, "prog_cc"))
    assert pd["counts"]["exclusive"] + pd["counts"]["shared"] == pd["counts"]["disciplines"]
    # soma das áreas == total de disciplinas; semestres cobrem todas
    assert sum(pd["by_area"].values()) == pd["counts"]["disciplines"]
    assert sum(len(s["disciplines"]) for s in pd["semesters"]) == pd["counts"]["disciplines"]
    # alunos do curso batem com o grafo
    enrolled = [n for n, d in G.nodes(data=True) if d.get("type") == "Student" and d.get("program") == "prog_cc"]
    assert pd["counts"]["students"] == len(enrolled)


def test_career_detail_consistency():
    cd = ins.career_detail(G, "career_001")
    assert cd["name"] and cd["demand_level"] and cd["competencies"]
    assert "avg_salary_brl" not in cd
    # competências == exigidas pela carreira; ordenadas por importância
    assert len(cd["competencies"]) == len(q.career_competencies(G, "career_001"))
    order = {"critical": 0, "important": 1, "nice-to-have": 2}
    seq = [order[c["importance"]] for c in cd["competencies"]]
    assert seq == sorted(seq)
    # top_disciplines com relevância positiva e decrescente
    rels = [d["relevance"] for d in cd["top_disciplines"]]
    assert rels == sorted(rels, reverse=True) and all(r > 0 for r in rels)


def test_questionnaire_maps_to_competencies():
    qs = ins.career_questionnaire(G)
    comp_ids = {n for n, d in G.nodes(data=True) if d.get("type") == "Competency"}
    assert qs and all(q_["competency"] in comp_ids and q_["question"] for q_ in qs)


def test_score_careers_reflects_interest():
    # Interesse alto só em ML/analytics/stats deve rankear carreiras de dados no topo.
    name2id = {G.nodes[n]["name"]: n for n, d in G.nodes(data=True) if d.get("type") == "Competency"}
    interest = {name2id[n]: 1.0 for n in ["Machine Learning", "Análise de Dados", "Estatística e Probabilidade"] if n in name2id}
    ranking = ins.score_careers(G, interest)
    assert ranking and ranking == sorted(ranking, key=lambda r: r["fit"], reverse=True)
    assert 0.0 <= ranking[0]["fit"] <= 1.0
    top_names = {r["name"] for r in ranking[:3]}
    assert "Cientista de Dados" in top_names


def test_program_coverage_and_fit_report():
    # Aluno de Produção mirando Cientista de Dados: curso atual mal alinhado; melhor curso cobre mais.
    sid = next(n for n, d in G.nodes(data=True) if d.get("type") == "Student" and d.get("program") == "prog_prod")
    ds = next(n for n, d in G.nodes(data=True) if d.get("type") == "Career" and d.get("name") == "Cientista de Dados")
    rep = ins.career_fit_report(G, sid, ds)
    assert 0 <= rep["current"]["coverage_pct"] <= 100
    assert rep["best_program"]["coverage_pct"] >= rep["current"]["coverage_pct"]
    # reaproveitamento nunca excede o que já foi concluído
    completed = q.student_completed(G, sid)
    assert rep["best_program"]["aproveita_disciplinas"] <= len(completed)


def test_plan_for_target_reuses_completed():
    sid = next(n for n, d in G.nodes(data=True) if d.get("type") == "Student")
    completed = q.student_completed(G, sid)
    program = G.nodes[sid]["program"]
    career = G.nodes[sid]["target_career"]
    plan = pe.plan_for_target(G, completed, program, career)
    prog_discs = set(q.disciplines_in_program(G, program))
    assert plan["reused_count"] == len(completed & prog_discs)
    # nada recomendado já foi concluído
    assert all(d["id"] not in completed for d in plan["recommended_order"])


def test_subgraph_student_has_status_map():
    sid = next(n for n, d in G.nodes(data=True) if d.get("type") == "Student")
    sg = ins.subgraph(G, "student", sid)
    by_id = {n["id"]: n for n in sg["nodes"]}
    completed = q.student_completed(G, sid)
    career = G.nodes[sid].get("target_career")
    # aluno e carreira marcados; carreira em 'career'
    assert by_id[sid]["status"] == "student"
    if career in by_id:
        assert by_id[career]["status"] == "career"
    # disciplinas: done sse concluída, senão todo; competências: done/todo
    for n in sg["nodes"]:
        if n["type"] == "Discipline":
            assert n["status"] == ("done" if n["id"] in completed else "todo")
        elif n["type"] == "Competency":
            assert n["status"] in ("done", "todo")
    # deve haver ao menos uma disciplina 'todo' (falta) para dar sentido ao mapa
    assert any(n["type"] == "Discipline" and n["status"] == "todo" for n in sg["nodes"])


def test_subgraph_invalid_scope_raises():
    import pytest
    with pytest.raises(ValueError):
        ins.subgraph(G, "nope")


def test_student_profile_uses_names_and_is_consistent():
    p = ins.student_profile(G, "student_001")
    # Nomes legíveis presentes (não só ids).
    assert p["name"] and p["program"]["name"] and p["target_career"]["name"]
    assert p["program"]["name"] != p["program"]["id"]
    assert p["target_career"]["name"] != p["target_career"]["id"]
    # Contagens coerentes: a matrícula do semestre sai de 'pending' e vira 'enrolled'.
    prog = pe.student_progress(G, "student_001")
    enrolled_ids = q.student_enrolled(G, "student_001")
    assert p["counts"]["completed"] == len(prog["completed"])
    assert p["counts"]["enrolled"] == len(enrolled_ids)
    # 'em curso' são disciplinas não concluídas do programa (subconjunto das pendentes do progresso).
    assert enrolled_ids <= set(prog["pending"])
    faltantes = [x for x in prog["pending"] if x not in enrolled_ids]
    assert p["counts"]["pending"] == len(faltantes)
    # Concluídas trazem código; faltantes ordenadas por pré-requisito e disjuntas de 'em curso'.
    assert all("code" in c for c in p["completed"])
    pend_ids = [d["id"] for d in p["pending"]]
    assert pend_ids == q.order_by_prerequisites(G, faltantes)
    assert not (set(pend_ids) & enrolled_ids)
    # Próximos passos = trilha recomendada excluindo o que já está em curso (5 primeiros).
    rec = pe.recommend_path(G, "student_001", p["target_career"]["id"])
    expected_next = [d["id"] for d in rec["recommended_order"] if d["id"] not in enrolled_ids][:5]
    assert [d["id"] for d in p["recommended_next"]] == expected_next


def test_career_competency_report_covers_all_programs():
    rep = ins.career_competency_report(G, "career_002")
    assert rep["competencies"], "carreira deveria exigir competências"
    prog_ids = {p["id"] for p in rep["programs"]}
    all_progs = {n for n, d in G.nodes(data=True) if d.get("type") == "Program"}
    assert prog_ids == all_progs
    for c in rep["competencies"]:
        assert set(c["by_program"].keys()) == prog_ids
        # coerência: total de disciplinas >= o que qualquer programa cobre
        assert all(bp["count"] <= c["total_disciplines"] for bp in c["by_program"].values())
