import prompts


def test_essay_prompt_inclui_rubrica_e_criterios():
    rubric = {"name": "Minha Rubrica", "criteria": [
        {"name": "Coesão", "maxScore": 200, "description": "liga as ideias"}]}
    p = prompts.essay_prompt("Texto da redação", rubric)
    assert "Minha Rubrica" in p
    assert "Coesão" in p and "200" in p
    # Saída é via structured output (Pydantic), não JSON-em-texto: o prompt pede totalScore/feedback.
    assert "totalScore" in p and "feedback" in p


def test_exam_prompt_gabarito_vs_modelo():
    qa = [{"question": "Q1", "resposta": "R1"}]
    gab = [{"prompt": "Q1", "referenceAnswer": "Ref"}]
    com_gab = prompts.exam_prompt(qa, "gabarito", gab)
    sem_gab = prompts.exam_prompt(qa, "model", None)
    assert "gabarito do professor" in com_gab and "Ref" in com_gab
    assert "próprio conhecimento" in sem_gab


def test_transcription_prompt_por_tipo():
    # Prova extrai pares pergunta/resposta; redação transcreve o texto. (structured output, sem JSON no prompt)
    assert "prova" in prompts.transcription_prompt("exam").lower()
    assert "transcreva" in prompts.transcription_prompt("essay").lower()


def test_answersheet_prompt_com_estrutura_esperada():
    base = prompts.answersheet_prompt()
    assert "CARTÃO-RESPOSTA" in base
    com = prompts.answersheet_prompt({"questions": 90, "letters": ["A", "B", "C", "D", "E"]})
    assert "90" in com


def test_judge_prompt_tem_dimensoes():
    p = prompts.judge_prompt("essay", "Candidato A texto", "Candidato B texto")
    assert "Candidato A" in p and "Candidato B" in p and "winner" in p
