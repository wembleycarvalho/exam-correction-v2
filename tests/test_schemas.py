from common import schemas


def test_essay_valido_e_invalido():
    ok = {"criteria": [{"name": "c", "score": 180, "maxScore": 200, "feedback": "bom"}],
          "totalScore": 180, "feedback": "ok"}
    assert schemas.validate_essay_result(ok)[0]
    assert not schemas.validate_essay_result({"criteria": [], "totalScore": 0})[0]
    assert not schemas.validate_essay_result({"criteria": [{"score": 1}], "totalScore": 1})[0]


def test_exam_valido_e_invalido():
    ok = {"questoes": [{"nota": 8, "notaMaxima": 10, "justificativa": "x"}], "notaTotal": 8}
    assert schemas.validate_exam_result(ok)[0]
    assert not schemas.validate_exam_result({"questoes": [], "notaTotal": 0})[0]


def test_transcription_e_author():
    assert schemas.validate_transcription_result({"text": "abc"}, "essay")[0]
    assert not schemas.validate_transcription_result({"text": " "}, "essay")[0]
    assert schemas.validate_transcription_result({"transcricao": []}, "exam")[0]
    assert schemas.validate_author_result({"resposta": "uma resposta"})[0]
    assert not schemas.validate_author_result({"resposta": ""})[0]


def test_ensure_levanta():
    import pytest
    with pytest.raises(schemas.SchemaError):
        schemas.ensure((False, "erro"))
