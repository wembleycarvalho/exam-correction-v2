"""Prompts e builders dos agentes (PT-BR).

Funções puras (sem dependência de Strands/boto3) para serem testáveis isoladamente.
Cada builder devolve (system_prompt, user_prompt) ou o texto do prompt.
"""

# --- Transcrição -----------------------------------------------------------------
TRANSCRIPTION_ESSAY_PROMPT = (
    "Transcreva fielmente todo o texto manuscrito/impresso desta redação, preservando "
    "parágrafos e ordem. Responda APENAS com o texto transcrito, sem comentários."
)

TRANSCRIPTION_EXAM_PROMPT = (
    "Este documento é uma prova discursiva respondida por um aluno. Extraia fielmente os "
    "pares de pergunta (enunciado) e resposta do aluno, na ordem em que aparecem."
)


def transcription_prompt(kind: str) -> str:
    return TRANSCRIPTION_EXAM_PROMPT if kind == "exam" else TRANSCRIPTION_ESSAY_PROMPT


# --- Cartão resposta (múltipla escolha) ------------------------------------------
ANSWERSHEET_SYSTEM = (
    "Você lê cartões-resposta de múltipla escolha com precisão. Identifica, para cada "
    "questão, qual alternativa foi marcada, sem inventar respostas."
)

ANSWERSHEET_PROMPT = (
    "Esta imagem é um CARTÃO-RESPOSTA de múltipla escolha. Para CADA questão, identifique a "
    "alternativa marcada (preenchida). Regras para o campo 'marcada':\n"
    "- use a letra da alternativa (ex.: A, B, C, D, E) quando houver exatamente uma marcação;\n"
    "- use '-' quando a questão estiver em branco (nenhuma marcação);\n"
    "- use '*' quando houver DUAS OU MAIS marcações na mesma questão (anulada/ambígua).\n"
    "ATENÇÃO AO ALINHAMENTO (evite deslocar a resposta): a alternativa 'A' é SEMPRE a "
    "PRIMEIRA bolha (mais à esquerda) de cada questão; conte as bolhas da esquerda para a "
    "direita e associe a posição preenchida à letra correta — não desloque para a bolha "
    "vizinha. Leia coluna por coluna, de cima para baixo e da esquerda para a direita. "
    "Liste as questões na ordem correta, numerando a partir de 1. Não corrija nem julgue se "
    "está certo ou errado — apenas registre o que foi marcado."
)


def answersheet_prompt(expected: dict = None) -> str:
    """Prompt de leitura do cartão; se houver estrutura esperada (do template), reforça
    a contagem de questões e as alternativas válidas para reduzir alucinação."""
    base = ANSWERSHEET_PROMPT
    if expected:
        q = expected.get("questions")
        letters = expected.get("letters") or []
        if q:
            base += (f"\nO cartão tem EXATAMENTE {q} questões, numeradas de 1 a {q}. "
                     "Retorne todas elas, em ordem.")
        if letters:
            base += f" As únicas alternativas possíveis são: {', '.join(letters)}."
    return base


# --- Redação ---------------------------------------------------------------------
ESSAY_SYSTEM = (
    "Você é um corretor de redações experiente e criterioso. Corrige em português, "
    "com justificativas objetivas por critério."
)

_ESSAY_SCHEMA = (
    '{"criteria":[{"name":"str","score":int,"maxScore":int,"feedback":"str"}],'
    '"totalScore":int,"feedback":"str"}'
)


def essay_prompt(essay_text: str, rubric: dict) -> str:
    criteria = rubric.get("criteria", [])
    criteria_desc = "\n".join(
        f"- {c['name']} (máx {c['maxScore']}): {c.get('description', '')}" for c in criteria
    )
    return (
        f"Corrija a redação a seguir usando a rubrica \"{rubric.get('name', 'rubrica')}\".\n"
        f"Critérios:\n{criteria_desc}\n\n"
        f'Redação:\n"""\n{essay_text}\n"""\n\n'
        f"Regras: score entre 0 e o máximo de cada critério; totalScore = soma dos scores; "
        f"feedback em português e específico para cada critério."
    )


# --- Prova discursiva ------------------------------------------------------------
EXAM_SYSTEM = (
    "Você é um professor corrigindo uma prova discursiva. Corrige em português, questão a questão."
)

_EXAM_SCHEMA = (
    '{"questoes":[{"nota":number,"notaMaxima":number,"justificativa":"str","fontes":["str"]}],'
    '"notaTotal":number}'
)


def _fmt_qa(qa_pairs: list) -> str:
    linhas = []
    for i, item in enumerate(qa_pairs, 1):
        linhas.append(
            f"Questão {i}: {item.get('question', '')}\n"
            f"Resposta do aluno: {item.get('resposta', '')}"
        )
    return "\n\n".join(linhas)


def exam_prompt(qa_pairs: list, strategy: str, gabarito: list = None,
                max_score_per_question: float = 10.0) -> str:
    base = (
        f"Corrija as questões abaixo. Cada questão vale até {max_score_per_question} pontos.\n\n"
        f"{_fmt_qa(qa_pairs)}\n\n"
    )
    if strategy == "gabarito" and gabarito:
        ref = "\n\n".join(
            f"Questão {i}: {g.get('prompt', g.get('question', ''))}\n"
            f"Resposta de referência: {g.get('referenceAnswer', g.get('resposta', ''))}"
            for i, g in enumerate(gabarito, 1)
        )
        base += f"Use como referência o gabarito do professor:\n{ref}\n\n"
    else:
        base += "Use seu próprio conhecimento para avaliar a correção das respostas.\n\n"
    base += ("Para cada questão, atribua nota (0..notaMaxima), justificativa em português e, "
             "quando houver, as fontes usadas.")
    return base


# --- Autor (wizard) --------------------------------------------------------------
AUTHOR_SYSTEM = (
    "Você é um professor elaborando o gabarito de uma prova discursiva."
)


def author_prompt(question: str) -> str:
    return (
        "Escreva uma resposta de referência clara, correta e completa (em português) para a "
        f"questão a seguir. Responda apenas com a resposta de referência.\n\nQuestão: {question}"
    )


# --- Juiz (model as a judge) -----------------------------------------------------
JUDGE_SYSTEM = (
    "Você é um avaliador imparcial (juiz) de qualidade. Compara duas saídas geradas por "
    "modelos de IA diferentes para a MESMA tarefa e decide qual tem maior qualidade, com "
    "justificativa objetiva em português. Você NÃO sabe qual modelo produziu cada saída e "
    "não deve ter preferência por nenhum. Baseie-se apenas no conteúdo apresentado."
)

_JUDGE_KIND_DESC = {
    "transcription": ("duas TRANSCRIÇÕES do mesmo material manuscrito/impresso. Avalie "
                      "completude, coerência, organização e legibilidade do texto transcrito."),
    "essay": ("duas CORREÇÕES da mesma redação (notas por critério e feedback). Avalie a "
              "consistência das notas com as justificativas, a profundidade e a utilidade "
              "do feedback e o alinhamento à rubrica."),
    "exam": ("duas CORREÇÕES da mesma prova discursiva (notas e justificativas por questão). "
             "Avalie a corretude aparente, a consistência e a qualidade das justificativas."),
}

# Dimensões avaliadas por tipo (o juiz dá nota 0..10 a cada candidato em cada uma).
_JUDGE_DIMENSIONS = {
    "transcription": ["Fidelidade ao original", "Completude", "Coerência e legibilidade",
                      "Organização"],
    "essay": ["Consistência nota×justificativa", "Profundidade do feedback",
              "Alinhamento à rubrica", "Utilidade para o aluno"],
    "exam": ["Corretude da avaliação", "Consistência das notas",
             "Qualidade das justificativas", "Cobertura das questões"],
}


def judge_prompt(kind: str, candidate_a: str, candidate_b: str, context: str = "") -> str:
    desc = _JUDGE_KIND_DESC.get(kind, "duas saídas para a mesma tarefa.")
    dims = _JUDGE_DIMENSIONS.get(kind, ["Qualidade geral"])
    dim_txt = "; ".join(dims)
    ctx = f"\nContexto (material que foi avaliado):\n\"\"\"\n{context}\n\"\"\"\n" if context else ""
    return (
        f"Você vai comparar {desc}{ctx}\n"
        f"=== Candidato A ===\n{candidate_a}\n\n"
        f"=== Candidato B ===\n{candidate_b}\n\n"
        "Avalie CADA uma das dimensões a seguir, atribuindo nota de 0 a 10 ao Candidato A e "
        f"ao Candidato B, com uma observação curta comparando os dois: {dim_txt}.\n"
        "Em seguida forneça: winner ('A', 'B' ou 'empate'), scoreA e scoreB (nota GERAL de 0 a "
        "10 de cada candidato) e rationale (resumo comparativo em português citando pontos "
        "concretos). Seja imparcial — você não sabe qual modelo gerou cada candidato."
    )


# --- Geração de prova online (a partir do Knowledge Base) ------------------------
EXAMGEN_SYSTEM = (
    "Você é um elaborador de provas para estudo. Cria questões claras, corretas e SEM "
    "ambiguidade, fundamentadas EXCLUSIVAMENTE no material fornecido (trechos do material de "
    "estudo). Não inventa fatos fora do material. Escreve em português."
)


def examgen_prompt(theme: str, passages: list, num: int) -> str:
    ctx = "\n\n".join(f"[Trecho {i + 1}]\n{p}" for i, p in enumerate(passages or []))
    tema = f" sobre o tema \"{theme}\"" if theme else ""
    return (
        f"Gere {num} questões de MÚLTIPLA ESCOLHA{tema}, fundamentadas apenas no material "
        f"abaixo. Cada questão deve ter:\n"
        "- enunciado claro;\n"
        "- exatamente 5 alternativas (a primeira é a letra A, a segunda B, e assim por diante);\n"
        "- uma única alternativa correta (campo 'correta' com a letra A–E);\n"
        "- 'explicacao': por que a correta está certa (curta, baseada no material);\n"
        "- 'tema': o assunto específico da questão.\n"
        "Evite 'todas as anteriores' e pegadinhas triviais. Varie a posição da correta.\n\n"
        f"=== MATERIAL DE ESTUDO ===\n{ctx}"
    )


def examgen_discursive_prompt(theme: str, passages: list, num: int) -> str:
    ctx = "\n\n".join(f"[Trecho {i + 1}]\n{p}" for i, p in enumerate(passages or []))
    tema = f" sobre o tema \"{theme}\"" if theme else ""
    return (
        f"Gere {num} questões DISCURSIVAS (resposta aberta, redigida){tema}, fundamentadas "
        f"apenas no material abaixo. Cada questão deve ter:\n"
        "- enunciado: pergunta aberta e clara, que exija uma resposta redigida (não use "
        "múltipla escolha, verdadeiro/falso nem sim/não);\n"
        "- respostaReferencia: uma resposta de referência (gabarito) completa, correta e "
        "objetiva, baseada no material, servindo de base para correção;\n"
        "- tema: o assunto específico da questão.\n\n"
        f"=== MATERIAL DE ESTUDO ===\n{ctx}"
    )
