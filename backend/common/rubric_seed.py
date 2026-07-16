"""Rubrica padrão ENEM (5 competências, 200 pontos cada, total 1000).

Semente da tabela `rubrics` (editável e versionável pela UI). É o ponto de partida da
correção de redação; o professor pode criar rubricas próprias.
"""

ENEM_RUBRIC = {
    "rubricId": "enem",
    "version": "1",
    "name": "ENEM (5 competências)",
    "isDefault": True,
    "status": "active",
    "totalMaxScore": 1000,
    "criteria": [
        {
            "name": "Competência 1 — Domínio da norma culta",
            "maxScore": 200,
            "description": (
                "Demonstrar domínio da modalidade escrita formal da língua portuguesa "
                "(ortografia, concordância, regência, pontuação)."
            ),
        },
        {
            "name": "Competência 2 — Compreensão do tema",
            "maxScore": 200,
            "description": (
                "Compreender a proposta e aplicar conceitos das várias áreas de conhecimento "
                "para desenvolver o tema, dentro dos limites do texto dissertativo-argumentativo."
            ),
        },
        {
            "name": "Competência 3 — Seleção e organização de argumentos",
            "maxScore": 200,
            "description": (
                "Selecionar, relacionar, organizar e interpretar informações, fatos, opiniões "
                "e argumentos em defesa de um ponto de vista."
            ),
        },
        {
            "name": "Competência 4 — Coesão e coerência",
            "maxScore": 200,
            "description": (
                "Demonstrar conhecimento dos mecanismos linguísticos necessários para a "
                "construção da argumentação (coesão e articulação entre as partes)."
            ),
        },
        {
            "name": "Competência 5 — Proposta de intervenção",
            "maxScore": 200,
            "description": (
                "Elaborar proposta de intervenção para o problema abordado, respeitando os "
                "direitos humanos e detalhando agente, ação, meio, efeito e finalidade."
            ),
        },
    ],
}
