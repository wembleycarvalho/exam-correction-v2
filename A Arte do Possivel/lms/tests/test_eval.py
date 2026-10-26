"""Testes da auto-avaliação (funções puras com search_fn fake)."""
from eval.evaluate import evaluate, is_correct, overlaps

DISC = [{
    "disc_id": "disc_029", "name": "Física II",
    "chapters": [
        {"index": 0, "title": "Leis", "start_sec": 0.0, "dur_sec": 5.0, "narration": "Leis."},
        {"index": 1, "title": "Equilíbrio", "start_sec": 5.0, "dur_sec": 5.0, "narration": "Equilíbrio."},
    ],
}]


def _hit(disc_id, start, end):
    return {"disc_id": disc_id, "start_sec": start, "end_sec": end}


def test_overlaps():
    assert overlaps(4, 8, 5, 10)
    assert not overlaps(0, 4, 5, 10)
    assert overlaps(4.5, 5.0, 5.0, 10.0, tol=1.0)   # tolerância aproxima


def test_is_correct():
    ch = DISC[0]["chapters"][1]  # janela [5,10)
    assert is_correct(_hit("disc_029", 5.5, 9.0), "disc_029", ch)
    assert not is_correct(_hit("disc_029", 0.0, 4.0), "disc_029", ch)   # janela errada
    assert not is_correct(_hit("outra", 5.5, 9.0), "disc_029", ch)      # disciplina errada


def test_evaluate_perfect():
    # search_fn devolve exatamente o segmento do capítulo consultado -> tudo acerta.
    def sf(query, did):
        ch = DISC[0]["chapters"][0] if "Leis" in query else DISC[0]["chapters"][1]
        return [_hit(did, ch["start_sec"], ch["start_sec"] + ch["dur_sec"])]
    r = evaluate(DISC, sf, k=3)
    assert r["total"] == 2
    assert r["precision_at_1"] == 1.0
    assert r["hit_at_k"] == 1.0
    assert r["discipline_at_1"] == 1.0


def test_evaluate_wrong_chapter_but_right_discipline():
    # sempre devolve o capítulo 0 -> só acerta o capítulo 0; disciplina sempre certa.
    def sf(query, did):
        ch = DISC[0]["chapters"][0]
        return [_hit(did, ch["start_sec"], ch["start_sec"] + ch["dur_sec"])]
    r = evaluate(DISC, sf, k=3)
    assert r["precision_at_1"] == 0.5        # acerta 1 de 2 capítulos
    assert r["discipline_at_1"] == 1.0       # disciplina certa nos 2


def test_evaluate_empty_results():
    r = evaluate(DISC, lambda q, d: [], k=3)
    assert r["precision_at_1"] == 0.0 and r["hit_at_k"] == 0.0
