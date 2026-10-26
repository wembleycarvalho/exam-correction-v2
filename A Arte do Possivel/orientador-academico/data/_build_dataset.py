"""Gerador único e determinístico do dataset do Orientador Acadêmico.

Produz TODOS os arquivos de data/ (programs, competencies, careers, disciplines,
relationships, students) de forma reprodutível (seed fixo), com:
  - 6 cursos: Eng. de Software, Ciência da Computação, Banco de Dados,
    Sistemas de Informação, Eng. Mecânica e Eng. de Produção;
  - 25 competências, 10 carreiras;
  - ~catálogo de disciplinas COMPARTILHADAS entre cursos (as engenharias dividem
    cálculo/física/estatística; SI/BD dividem base de computação/dados);
  - disciplinas OBRIGATÓRIAS e ELETIVAS por curso (requirement na aresta OFFERED_IN);
  - 40 alunos com histórico coerente (respeita pré-requisitos e semestre atual).

Uso: python data/_build_dataset.py   (a partir de orientador-academico/)

Integridade: valida referências e o DAG de pré-requisitos antes de gravar. Ao final,
reconstrói o grafo com o builder para garantir que tudo carrega sem erro.
"""
from __future__ import annotations

import json
import os
import random

SEED = 20260805
random.seed(SEED)

# --------------------------------------------------------------------------- #
# Programas (cursos)
# --------------------------------------------------------------------------- #
PROGRAMS = [
    {"id": "prog_es",   "name": "Engenharia de Software",   "code": "eng-software",        "kb_curso_id": "eng-software"},
    {"id": "prog_cc",   "name": "Ciência da Computação",    "code": "ciencia-computacao",  "kb_curso_id": ""},
    {"id": "prog_bd",   "name": "Banco de Dados",           "code": "banco-de-dados",      "kb_curso_id": ""},
    {"id": "prog_si",   "name": "Sistemas de Informação",   "code": "sistemas-informacao", "kb_curso_id": ""},
    {"id": "prog_mec",  "name": "Engenharia Mecânica",      "code": "eng-mecanica",        "kb_curso_id": ""},
    {"id": "prog_prod", "name": "Engenharia de Produção",   "code": "eng-producao",        "kb_curso_id": ""},
]

# --------------------------------------------------------------------------- #
# Competências (25)  key -> (nome, categoria, descrição)
# --------------------------------------------------------------------------- #
COMPETENCIES = {
    "math":       ("Pensamento Matemático", "foundational", "Modelar problemas com cálculo, álgebra e abstrações matemáticas."),
    "logic":      ("Raciocínio Lógico", "foundational", "Formular e avaliar argumentos formais, provas e lógica."),
    "prog":       ("Programação", "technical", "Escrever, depurar e organizar código em linguagens de propósito geral."),
    "dsa":        ("Estruturas de Dados e Algoritmos", "technical", "Escolher e implementar estruturas e algoritmos eficientes."),
    "stats":      ("Estatística e Probabilidade", "foundational", "Analisar dados sob incerteza com modelos estatísticos."),
    "modelagem":  ("Modelagem de Dados", "technical", "Modelar, normalizar e consultar dados em bancos de dados."),
    "ml":         ("Machine Learning", "applied", "Treinar, avaliar e ajustar modelos de aprendizado de máquina."),
    "engsw":      ("Engenharia de Software", "technical", "Projetar, testar e manter sistemas de software de forma sustentável."),
    "redes":      ("Redes e Sistemas Distribuídos", "technical", "Protocolos, concorrência e computação distribuída."),
    "cloud":      ("Infraestrutura e Cloud", "applied", "Provisionar, operar e automatizar infraestrutura em nuvem."),
    "analytics":  ("Análise de Dados", "applied", "Extrair, transformar e visualizar dados para gerar insights."),
    "produto":    ("Comunicação e Produto", "applied", "Traduzir necessidades de negócio em requisitos e comunicar resultados."),
    "seguranca":  ("Segurança da Informação", "technical", "Criptografia, autenticação, ameaças e defesa de sistemas."),
    "so":         ("Sistemas Operacionais", "technical", "Processos, memória, concorrência e o kernel."),
    "po":         ("Otimização e Pesquisa Operacional", "applied", "Formular e resolver problemas de otimização e decisão."),
    "fisica":     ("Física e Mecânica", "foundational", "Leis do movimento, forças, energia e mecânica aplicada."),
    "termo":      ("Termodinâmica e Fluidos", "technical", "Calor, energia, escoamentos e fenômenos de transporte."),
    "materiais":  ("Ciência dos Materiais", "technical", "Estrutura, propriedades e seleção de materiais de engenharia."),
    "manufatura": ("Manufatura e Processos", "applied", "Processos de fabricação, automação e manutenção industrial."),
    "qualidade":  ("Gestão da Qualidade", "applied", "Controle estatístico, melhoria contínua e normas de qualidade."),
    "logistica":  ("Logística e Cadeia de Suprimentos", "applied", "Planejamento de estoques, transporte e cadeia de valor."),
    "gestproc":   ("Gestão de Processos e Operações", "applied", "Mapear, medir e melhorar processos e operações."),
    "frontend":   ("Desenvolvimento Front-end e UX", "technical", "Interfaces web, usabilidade e experiência do usuário."),
    "dba":        ("Administração de Banco de Dados", "technical", "Operar, tunar e proteger bancos de dados em produção."),
    "govdata":    ("Governança e Ética de Dados", "applied", "Qualidade, privacidade, LGPD e governança de dados."),
}
COMP_ID = {k: f"comp_{i:03d}" for i, k in enumerate(COMPETENCIES, start=1)}

# --------------------------------------------------------------------------- #
# Carreiras  id -> (nome, área, demanda, ferramentas, [(comp, importância)])
# --------------------------------------------------------------------------- #
CAREERS = [
    ("Engenheiro de Machine Learning", "Inteligência Artificial", "high",
     ["Python", "TensorFlow", "PyTorch", "AWS SageMaker"],
     [("ml", "critical"), ("prog", "critical"), ("stats", "important"), ("math", "important"), ("dsa", "important"), ("cloud", "nice-to-have")]),
    ("Cientista de Dados", "Dados", "high",
     ["Python", "Pandas", "SQL", "scikit-learn"],
     [("stats", "critical"), ("ml", "critical"), ("analytics", "critical"), ("prog", "important"), ("modelagem", "important"), ("math", "important")]),
    ("Engenheiro Backend", "Engenharia de Software", "high",
     ["Java", "Python", "SQL", "APIs REST"],
     [("prog", "critical"), ("engsw", "critical"), ("modelagem", "critical"), ("dsa", "important"), ("redes", "important"), ("seguranca", "nice-to-have")]),
    ("Site Reliability Engineer (SRE)", "Infraestrutura", "medium",
     ["Linux", "Kubernetes", "Terraform", "AWS"],
     [("cloud", "critical"), ("so", "critical"), ("redes", "critical"), ("prog", "important"), ("seguranca", "important"), ("engsw", "nice-to-have")]),
    ("Product Manager de Tecnologia", "Produto", "medium",
     ["Analytics", "SQL", "Roadmapping", "Discovery"],
     [("produto", "critical"), ("analytics", "important"), ("engsw", "important"), ("gestproc", "important"), ("stats", "nice-to-have")]),
    ("Desenvolvedor Front-end", "Engenharia de Software", "high",
     ["JavaScript", "React", "TypeScript", "CSS"],
     [("frontend", "critical"), ("prog", "critical"), ("engsw", "important"), ("produto", "important")]),
    ("Administrador de Banco de Dados (DBA)", "Dados", "medium",
     ["SQL", "PostgreSQL", "Oracle", "backup/replicação"],
     [("dba", "critical"), ("modelagem", "critical"), ("seguranca", "important"), ("govdata", "important"), ("redes", "nice-to-have")]),
    ("Analista de BI", "Dados", "high",
     ["SQL", "Power BI", "ETL", "Data Warehouse"],
     [("analytics", "critical"), ("modelagem", "critical"), ("stats", "important"), ("produto", "important"), ("govdata", "nice-to-have")]),
    ("Engenheiro Mecânico", "Engenharia Mecânica", "medium",
     ["SolidWorks", "AutoCAD", "MATLAB", "Ansys"],
     [("fisica", "critical"), ("termo", "critical"), ("materiais", "critical"), ("math", "important"), ("manufatura", "important"), ("po", "nice-to-have")]),
    ("Engenheiro de Produção", "Engenharia de Produção", "high",
     ["Lean", "Six Sigma", "ERP", "Excel/Analytics"],
     [("po", "critical"), ("qualidade", "critical"), ("gestproc", "critical"), ("logistica", "important"), ("stats", "important"), ("manufatura", "nice-to-have")]),
    ("Projetista CAD / Engenheiro de Projetos", "Engenharia Mecânica", "medium",
     ["SolidWorks", "AutoCAD", "CATIA", "GD&T"],
     [("materiais", "critical"), ("fisica", "critical"), ("manufatura", "important"), ("math", "important")]),
    ("Engenheiro de Manutenção", "Engenharia Mecânica", "medium",
     ["Manutenção Preditiva", "SAP PM", "Confiabilidade", "Lubrificação"],
     [("manufatura", "critical"), ("materiais", "important"), ("termo", "important"), ("gestproc", "nice-to-have")]),
    ("Engenheiro de Energia", "Engenharia Mecânica", "medium",
     ["Termodinâmica", "HVAC", "Energias Renováveis", "MATLAB"],
     [("termo", "critical"), ("fisica", "critical"), ("math", "important"), ("materiais", "nice-to-have")]),
    ("Analista de Supply Chain / Logística", "Engenharia de Produção", "high",
     ["SAP", "ERP", "Excel", "Power BI"],
     [("logistica", "critical"), ("gestproc", "critical"), ("po", "important"), ("stats", "important"), ("manufatura", "nice-to-have")]),
    ("Engenheiro de Qualidade / Melhoria Contínua", "Engenharia de Produção", "high",
     ["Six Sigma", "Minitab", "ISO 9001", "CEP"],
     [("qualidade", "critical"), ("gestproc", "critical"), ("stats", "important"), ("po", "important"), ("manufatura", "nice-to-have")]),
]
CAREER_ID = {name: f"career_{i:03d}" for i, (name, *_rest) in enumerate(CAREERS, start=1)}

# --------------------------------------------------------------------------- #
# Catálogo de disciplinas
# key -> (nome, área, dificuldade, créditos, [(comp, peso)], [prereq_keys], kb_slug|None)
# --------------------------------------------------------------------------- #
D = {
    # --- Base matemática (compartilhada por várias engenharias/computação) ---
    "calc1":   ("Cálculo I", "Matemática", "medium", 4, [("math", 0.9)], [], "calculo_i"),
    "calc2":   ("Cálculo II", "Matemática", "medium", 4, [("math", 0.8)], ["calc1"], "calculo_ii"),
    "calc3":   ("Cálculo III", "Matemática", "hard", 4, [("math", 0.8)], ["calc2"], None),
    "geoana":  ("Geometria Analítica", "Matemática", "easy", 4, [("math", 0.7)], [], None),
    "alglin":  ("Álgebra Linear", "Matemática", "medium", 4, [("math", 0.8)], ["geoana"], None),
    "logica":  ("Lógica Matemática", "Matemática", "easy", 4, [("logic", 0.9)], [], "logica_matematica"),
    "matdisc": ("Matemática Discreta", "Matemática", "medium", 4, [("logic", 0.7), ("dsa", 0.4)], [], None),
    "estat":   ("Estatística", "Matemática", "medium", 4, [("stats", 0.9), ("math", 0.4)], ["calc1"], "estatistica"),
    "calcnum": ("Cálculo Numérico", "Matemática", "medium", 4, [("math", 0.7), ("prog", 0.3)], ["calc2", "alglin"], None),
    "po":      ("Pesquisa Operacional", "Matemática", "hard", 4, [("po", 0.9)], ["alglin", "estat"], None),
    "otim":    ("Otimização", "Matemática", "hard", 4, [("po", 0.8), ("math", 0.4)], ["calc2", "alglin"], None),
    # --- Física / base de engenharia ---
    "fis1":    ("Física I (Mecânica)", "Física", "medium", 4, [("fisica", 0.9)], ["calc1"], None),
    "fis2":    ("Física II (Termodinâmica)", "Física", "medium", 4, [("fisica", 0.6), ("termo", 0.4)], ["fis1", "calc2"], None),
    "fis3":    ("Física III (Eletromagnetismo)", "Física", "hard", 4, [("fisica", 0.7)], ["fis2"], None),
    "quimica": ("Química Geral", "Química", "easy", 4, [("materiais", 0.4)], [], None),
    "desenho": ("Desenho Técnico", "Engenharia", "easy", 4, [("manufatura", 0.3)], [], None),
    "cad":     ("Projeto Assistido por Computador (CAD)", "Engenharia", "medium", 4, [("manufatura", 0.5)], ["desenho"], None),
    "estatica":("Estática", "Engenharia", "medium", 4, [("fisica", 0.8)], ["fis1"], None),
    "dinamica":("Dinâmica", "Engenharia", "hard", 4, [("fisica", 0.8)], ["estatica", "calc2"], None),
    "resmat":  ("Resistência dos Materiais", "Engenharia", "hard", 4, [("fisica", 0.6), ("materiais", 0.5)], ["estatica"], None),
    "ciemat":  ("Ciência dos Materiais", "Engenharia", "medium", 4, [("materiais", 0.9)], ["quimica"], None),
    "termod":  ("Termodinâmica", "Engenharia", "hard", 4, [("termo", 0.9)], ["fis2"], None),
    "mecflu":  ("Mecânica dos Fluidos", "Engenharia", "hard", 4, [("termo", 0.8)], ["calc3", "fis2"], None),
    "fentransp":("Fenômenos de Transporte", "Engenharia", "hard", 4, [("termo", 0.8), ("math", 0.3)], ["termod", "mecflu"], None),
    "elemmaq": ("Elementos de Máquinas", "Engenharia", "hard", 4, [("materiais", 0.6), ("manufatura", 0.5)], ["resmat"], None),
    "procfab": ("Processos de Fabricação", "Engenharia", "medium", 4, [("manufatura", 0.9)], ["ciemat"], None),
    "automacao":("Automação Industrial", "Engenharia", "hard", 4, [("manufatura", 0.7)], ["fis3"], None),
    "manutencao":("Manutenção Industrial", "Engenharia", "medium", 4, [("manufatura", 0.6)], ["elemmaq"], None),
    "vibracoes":("Vibrações Mecânicas", "Engenharia", "hard", 4, [("fisica", 0.7), ("math", 0.4)], ["dinamica"], None),
    "energia": ("Sistemas de Energia", "Engenharia", "medium", 4, [("termo", 0.6)], ["termod"], None),
    # --- Produção / gestão ---
    "admin":   ("Administração", "Gestão", "easy", 4, [("produto", 0.5), ("gestproc", 0.4)], [], None),
    "economia":("Economia", "Gestão", "easy", 4, [("gestproc", 0.4)], [], None),
    "engeco":  ("Engenharia Econômica", "Gestão", "medium", 4, [("gestproc", 0.6), ("po", 0.3)], ["economia"], None),
    "gestproj":("Gestão de Projetos", "Gestão", "easy", 4, [("gestproc", 0.6), ("produto", 0.4)], [], "gestao_de_projetos"),
    "gestproc":("Gestão de Processos", "Gestão", "medium", 4, [("gestproc", 0.9)], ["admin"], None),
    "qualidade":("Gestão da Qualidade", "Gestão", "medium", 4, [("qualidade", 0.9), ("stats", 0.4)], ["estat"], None),
    "pcp":     ("Planejamento e Controle da Produção", "Produção", "hard", 4, [("gestproc", 0.6), ("po", 0.5)], ["po", "gestproc"], None),
    "logistica":("Logística e Cadeia de Suprimentos", "Produção", "medium", 4, [("logistica", 0.9)], ["gestproc"], None),
    "ergonomia":("Ergonomia e Segurança do Trabalho", "Produção", "easy", 4, [("qualidade", 0.4), ("gestproc", 0.4)], [], None),
    "simulacao":("Simulação de Sistemas", "Produção", "hard", 4, [("po", 0.7), ("stats", 0.5)], ["estat", "po"], None),
    "gestind": ("Gestão Industrial", "Produção", "medium", 4, [("gestproc", 0.7), ("logistica", 0.4)], ["gestproc"], None),
    "empreend":("Empreendedorismo", "Gestão", "easy", 2, [("produto", 0.6)], [], "empreendedorismo_digital"),
    # --- Humanas / base comum ---
    "comexp":  ("Comunicação e Expressão", "Humanas", "easy", 2, [("produto", 0.5)], [], "comunicacao_e_expressao"),
    "etica":   ("Ética e Cidadania", "Humanas", "easy", 2, [("govdata", 0.3)], [], "etica_em_ti"),
    "metod":   ("Metodologia Científica", "Humanas", "easy", 2, [("produto", 0.4)], [], None),
    # --- Computação / dados (núcleo compartilhado CC/ES/SI/BD) ---
    "fundcomp":("Fundamentos de Computação", "Computação", "easy", 4, [("prog", 0.3)], [], "fundamentos_de_computacao"),
    "introprog":("Introdução à Programação (Python)", "Computação", "easy", 4, [("prog", 0.9)], [], "introducao_a_programacao_python"),
    "estrdados":("Estrutura de Dados", "Computação", "medium", 4, [("dsa", 0.9), ("prog", 0.4)], ["introprog"], "estrutura_de_dados"),
    "poo":     ("Programação Orientada a Objetos", "Computação", "medium", 4, [("prog", 0.7), ("engsw", 0.4)], ["introprog"], "programacao_orientada_a_objetos"),
    "bd1":     ("Banco de Dados I", "Computação", "medium", 4, [("modelagem", 0.9)], ["introprog"], "banco_de_dados_i"),
    "bd2":     ("Banco de Dados II", "Computação", "hard", 4, [("modelagem", 0.7), ("dba", 0.5)], ["bd1"], "banco_de_dados_ii"),
    "dba":     ("Administração de Banco de Dados", "Dados", "hard", 4, [("dba", 0.9), ("seguranca", 0.3)], ["bd2"], None),
    "nosql":   ("NoSQL e Dados Distribuídos", "Dados", "hard", 4, [("modelagem", 0.6), ("redes", 0.4)], ["bd1"], None),
    "dataware":("Data Warehouse e BI", "Dados", "medium", 4, [("analytics", 0.7), ("modelagem", 0.5)], ["bd1", "estat"], None),
    "govdados":("Governança de Dados", "Dados", "medium", 4, [("govdata", 0.9)], ["bd1"], None),
    "anlise":  ("Análise de Dados", "Dados", "medium", 4, [("analytics", 0.9), ("stats", 0.4)], ["estat", "introprog"], None),
    "so":      ("Sistemas Operacionais", "Computação", "hard", 4, [("so", 0.9)], ["introprog"], "sistemas_operacionais"),
    "arqcomp": ("Arquitetura de Computadores", "Computação", "medium", 4, [("so", 0.6)], ["fundcomp"], None),
    "redes":   ("Redes de Computadores", "Computação", "medium", 4, [("redes", 0.8)], ["fundcomp"], "redes_de_computadores"),
    "sisdist": ("Sistemas Distribuídos", "Computação", "hard", 4, [("redes", 0.9)], ["redes", "so"], None),
    "engsw1":  ("Engenharia de Software I", "Computação", "medium", 4, [("engsw", 0.8)], ["poo"], "engenharia_de_software_i"),
    "engsw2":  ("Engenharia de Software II", "Computação", "hard", 4, [("engsw", 0.9)], ["engsw1"], "engenharia_de_software_ii"),
    "arqsw":   ("Arquitetura de Software", "Computação", "medium", 4, [("engsw", 0.8)], ["engsw1"], "arquitetura_de_software"),
    "testes":  ("Testes de Software", "Computação", "medium", 4, [("engsw", 0.7)], ["poo"], "testes_de_software"),
    "web":     ("Desenvolvimento Web", "Computação", "medium", 4, [("prog", 0.5), ("frontend", 0.5)], ["poo"], "desenvolvimento_web"),
    "frontadv":("Front-end Avançado", "Computação", "medium", 4, [("frontend", 0.9)], ["web"], None),
    "ux":      ("UX/UI Design", "Design", "easy", 4, [("frontend", 0.6), ("produto", 0.5)], [], "ux_ui_design"),
    "mobile":  ("Desenvolvimento Mobile", "Computação", "medium", 4, [("prog", 0.5), ("frontend", 0.4)], ["poo"], "desenvolvimento_mobile"),
    "microsvc":("Microsserviços e APIs", "Computação", "hard", 4, [("engsw", 0.6), ("redes", 0.4)], ["arqsw"], "microsservicos_e_apis"),
    "devops":  ("DevOps e Cloud Computing", "Computação", "medium", 4, [("cloud", 0.8)], ["redes"], "devops_e_cloud_computing"),
    "cloudadv":("Computação em Nuvem Avançada", "Computação", "hard", 4, [("cloud", 0.9), ("redes", 0.4)], ["devops"], "computacao_em_nuvem_avancada"),
    "seg":     ("Segurança da Informação", "Computação", "medium", 4, [("seguranca", 0.9)], ["redes"], "seguranca_da_informacao"),
    "ia":      ("Inteligência Artificial", "IA", "hard", 4, [("ml", 0.6), ("logic", 0.4)], ["estrdados", "estat"], "inteligencia_artificial"),
    "ml":      ("Machine Learning", "IA", "hard", 4, [("ml", 0.9), ("stats", 0.5)], ["ia"], "machine_learning"),
    "deep":    ("Deep Learning", "IA", "hard", 4, [("ml", 0.9)], ["ml"], None),
    "nlp":     ("Processamento de Linguagem Natural", "IA", "hard", 4, [("ml", 0.7)], ["ml"], None),
    "bigdata": ("Big Data", "IA", "hard", 4, [("analytics", 0.6), ("cloud", 0.4)], ["anlise", "devops"], None),
    "teoriacomp":("Teoria da Computação", "Computação", "hard", 4, [("logic", 0.8)], ["matdisc"], None),
    "analalg": ("Análise de Algoritmos", "Computação", "hard", 4, [("dsa", 0.9)], ["estrdados", "matdisc"], None),
    "grafos":  ("Teoria dos Grafos", "Computação", "medium", 4, [("dsa", 0.6), ("math", 0.4)], ["matdisc"], None),
    "compiladores":("Compiladores", "Computação", "hard", 4, [("dsa", 0.6), ("engsw", 0.4)], ["analalg"], None),
    "compgraf":("Computação Gráfica", "Computação", "medium", 4, [("math", 0.5), ("prog", 0.4)], ["alglin", "estrdados"], None),
    # --- SI específicas ---
    "sig":     ("Sistemas de Informação Gerenciais", "Gestão", "medium", 4, [("gestproc", 0.6), ("produto", 0.4)], ["admin"], None),
    "govti":   ("Governança de TI", "Gestão", "medium", 4, [("gestproc", 0.5), ("seguranca", 0.4)], ["sig"], None),
    "analsist":("Análise de Sistemas", "Computação", "medium", 4, [("engsw", 0.6), ("produto", 0.4)], ["poo"], None),
    # --- Prática / TCC ---
    "projint": ("Projeto Integrador", "Prática", "medium", 4, [("engsw", 0.4), ("produto", 0.4)], ["poo"], "projeto_integrador_i"),
    "estagio": ("Estágio Supervisionado", "Prática", "easy", 2, [("produto", 0.3)], [], "estagio_supervisionado_i"),
    "tcc1":    ("TCC I", "Prática", "medium", 2, [("produto", 0.4)], ["metod"], "tcc_i"),
    "tcc2":    ("TCC II", "Prática", "medium", 2, [("produto", 0.4)], ["tcc1"], "tcc_ii"),
}

# --------------------------------------------------------------------------- #
# Currículos por curso: program -> lista de (disc_key, semestre, requirement)
# 'M' = obrigatória, 'E' = eletiva. O compartilhamento acontece quando a mesma
# chave aparece em mais de um currículo.
# --------------------------------------------------------------------------- #
M, E = "mandatory", "elective"
CURRICULA = {
    "prog_es": [
        ("comexp", 1, M), ("logica", 1, M), ("fundcomp", 1, M), ("introprog", 1, M), ("calc1", 1, M),
        ("matdisc", 2, M), ("estrdados", 2, M), ("poo", 2, M), ("bd1", 2, M), ("calc2", 2, E),
        ("estat", 3, M), ("engsw1", 3, M), ("web", 3, M), ("redes", 3, M), ("so", 3, E),
        ("arqsw", 4, M), ("testes", 4, M), ("bd2", 4, M), ("gestproj", 4, M), ("mobile", 4, E),
        ("engsw2", 5, M), ("microsvc", 5, M), ("devops", 5, M), ("seg", 5, E), ("ux", 5, E),
        ("ia", 6, M), ("cloudadv", 6, E), ("frontadv", 6, E), ("projint", 6, M),
        ("ml", 7, E), ("metod", 7, M), ("empreend", 7, E), ("tcc1", 7, M),
        ("estagio", 8, M), ("tcc2", 8, M), ("etica", 8, M),
    ],
    "prog_cc": [
        ("logica", 1, M), ("fundcomp", 1, M), ("introprog", 1, M), ("calc1", 1, M), ("geoana", 1, M),
        ("matdisc", 2, M), ("estrdados", 2, M), ("poo", 2, M), ("calc2", 2, M), ("alglin", 2, M),
        ("arqcomp", 3, M), ("grafos", 3, M), ("bd1", 3, M), ("estat", 3, M), ("so", 3, M),
        ("analalg", 4, M), ("teoriacomp", 4, M), ("redes", 4, M), ("engsw1", 4, E),
        ("compiladores", 5, M), ("calcnum", 5, M), ("ia", 5, M), ("sisdist", 5, E),
        ("compgraf", 6, E), ("ml", 6, M), ("seg", 6, E), ("otim", 6, E),
        ("anlise", 6, E), ("devops", 6, E),
        ("deep", 7, E), ("nlp", 7, E), ("metod", 7, M), ("tcc1", 7, M),
        ("tcc2", 8, M), ("etica", 8, M),
    ],
    "prog_bd": [
        ("comexp", 1, M), ("logica", 1, M), ("fundcomp", 1, M), ("introprog", 1, M),
        ("estrdados", 2, M), ("bd1", 2, M), ("estat", 2, M), ("redes", 2, E),
        ("bd2", 3, M), ("anlise", 3, M), ("govdados", 3, M), ("seg", 3, E),
        ("dba", 4, M), ("nosql", 4, M), ("dataware", 4, M), ("devops", 4, E),
        ("bigdata", 5, E), ("gestproj", 5, M), ("etica", 5, M), ("estagio", 5, M),
    ],
    "prog_si": [
        ("comexp", 1, M), ("admin", 1, M), ("fundcomp", 1, M), ("introprog", 1, M), ("logica", 1, E),
        ("estrdados", 2, M), ("bd1", 2, M), ("economia", 2, M), ("poo", 2, E),
        ("sig", 3, M), ("redes", 3, M), ("estat", 3, M), ("analsist", 3, M),
        ("engsw1", 4, M), ("web", 4, M), ("govti", 4, M), ("bd2", 4, E),
        ("anlise", 5, M), ("dataware", 5, M), ("gestproj", 5, M), ("seg", 5, E),
        ("govdados", 6, M), ("bigdata", 6, E), ("ux", 6, E), ("metod", 6, M),
        ("tcc1", 7, M), ("empreend", 7, E), ("estagio", 7, M),
        ("tcc2", 8, M), ("etica", 8, M),
    ],
    "prog_mec": [
        ("calc1", 1, M), ("geoana", 1, M), ("quimica", 1, M), ("desenho", 1, M), ("comexp", 1, M),
        ("calc2", 2, M), ("alglin", 2, M), ("fis1", 2, M), ("cad", 2, M),
        ("calc3", 3, M), ("fis2", 3, M), ("estatica", 3, M), ("ciemat", 3, M), ("estat", 3, E),
        ("fis3", 4, M), ("dinamica", 4, M), ("resmat", 4, M), ("termod", 4, M),
        ("mecflu", 5, M), ("elemmaq", 5, M), ("fentransp", 5, M), ("calcnum", 5, E),
        ("vibracoes", 6, M), ("procfab", 6, M), ("energia", 6, E), ("gestproj", 6, E),
        ("automacao", 7, M), ("manutencao", 7, E), ("metod", 7, M), ("tcc1", 7, M),
        ("estagio", 8, M), ("tcc2", 8, M), ("etica", 8, E),
    ],
    "prog_prod": [
        ("calc1", 1, M), ("geoana", 1, M), ("comexp", 1, M), ("admin", 1, M), ("quimica", 1, E),
        ("calc2", 2, M), ("fis1", 2, M), ("economia", 2, M), ("estat", 2, M),
        ("estatica", 3, M), ("desenho", 3, M), ("ciemat", 3, E), ("gestproc", 3, M), ("qualidade", 3, M),
        ("po", 4, M), ("resmat", 4, E), ("procfab", 4, M), ("engeco", 4, M),
        ("pcp", 5, M), ("logistica", 5, M), ("ergonomia", 5, M), ("simulacao", 5, E),
        ("gestind", 6, M), ("gestproj", 6, M), ("automacao", 6, E), ("manutencao", 6, E),
        ("metod", 7, M), ("empreend", 7, E), ("tcc1", 7, M), ("estagio", 7, M),
        ("tcc2", 8, M), ("etica", 8, M),
    ],
}

# Carreiras plausíveis por curso (para sortear alvo dos alunos).
PROGRAM_CAREERS = {
    "prog_es": ["Engenheiro Backend", "Desenvolvedor Front-end", "Engenheiro de Machine Learning", "Product Manager de Tecnologia", "Site Reliability Engineer (SRE)"],
    "prog_cc": ["Engenheiro de Machine Learning", "Cientista de Dados", "Engenheiro Backend", "Site Reliability Engineer (SRE)"],
    "prog_bd": ["Administrador de Banco de Dados (DBA)", "Analista de BI"],
    "prog_si": ["Analista de BI", "Product Manager de Tecnologia", "Desenvolvedor Front-end"],
    "prog_mec": ["Engenheiro Mecânico", "Projetista CAD / Engenheiro de Projetos",
                 "Engenheiro de Manutenção", "Engenheiro de Energia"],
    "prog_prod": ["Engenheiro de Produção", "Analista de Supply Chain / Logística",
                  "Engenheiro de Qualidade / Melhoria Contínua"],
}

FIRST_NAMES = ["Ana", "Bruno", "Carla", "Daniel", "Eduarda", "Felipe", "Gabriela", "Hugo", "Isabela",
               "João", "Karina", "Lucas", "Marina", "Nicolas", "Olívia", "Pedro", "Queila", "Rafael",
               "Sofia", "Thiago", "Ursula", "Vinícius", "Yasmin", "Rodrigo", "Beatriz", "Caio",
               "Débora", "Enzo", "Fernanda", "Gustavo", "Helena", "Igor", "Júlia", "Kleber",
               "Larissa", "Matheus", "Natália", "Otávio", "Paula", "Renato"]
LAST_NAMES = ["Silva", "Souza", "Lima", "Oliveira", "Santos", "Pereira", "Costa", "Almeida", "Nunes",
              "Carvalho", "Rocha", "Gomes", "Martins", "Araújo", "Ribeiro", "Barbosa", "Teixeira",
              "Fernandes", "Cardoso", "Moraes"]

AREA_PREFIX = {"Matemática": "MAT", "Computação": "CC", "IA": "IA", "Gestão": "GES", "Humanas": "HUM",
               "Design": "DES", "Prática": "PRA", "Física": "FIS", "Química": "QUI",
               "Engenharia": "ENG", "Produção": "PRD", "Dados": "DAT"}


def main():
    # 1) Ordena disciplinas usadas por (menor semestre em que aparecem, key) → ids estáveis.
    used = set()
    min_sem = {}
    prog_of = {}   # key -> {pid: requirement}
    for pid, items in CURRICULA.items():
        for key, sem, req in items:
            if key not in D:
                raise SystemExit(f"Disciplina '{key}' do currículo de {pid} não está no catálogo D.")
            used.add(key)
            min_sem[key] = min(sem, min_sem.get(key, 99))
            prog_of.setdefault(key, {})[pid] = req

    # Inclui pré-requisitos que por acaso não estejam em nenhum currículo (evita refs soltas).
    for key in list(used):
        for pre in D[key][5]:
            if pre not in used:
                used.add(pre); min_sem[pre] = min_sem.get(pre, 1)

    ordered = sorted(used, key=lambda k: (min_sem.get(k, 99), k))
    disc_id = {k: f"disc_{i:03d}" for i, k in enumerate(ordered, start=1)}

    # 2) Monta disciplines.json
    disciplines = []
    for k in ordered:
        name, area, diff, credits, comps, prereqs, kb = D[k]
        progs = list(prog_of.get(k, {}).keys())
        requirements = prog_of.get(k, {})
        # disciplina que só existe como pré-requisito e não está em currículo: oferta em todos que a exigem
        if not progs:
            progs = ["prog_cc"]; requirements = {"prog_cc": M}
        disciplines.append({
            "id": disc_id[k], "type": "Discipline", "name": name,
            "code": f"{AREA_PREFIX.get(area, 'CC')}{list(ordered).index(k)+1:03d}",
            "semester_suggested": min_sem.get(k, 1), "credits": credits,
            "area": area, "difficulty": diff,
            "programs": progs, "requirements": requirements,
            "kb_slug": kb, "kb_disciplina": None,
        })

    # 3) competencies.json / careers.json / programs.json
    competencies = [{"id": COMP_ID[k], "type": "Competency", "name": nm,
                     "category": cat, "description": desc}
                    for k, (nm, cat, desc) in COMPETENCIES.items()]
    careers = []
    for name, area, demand, tools, _reqs in CAREERS:
        careers.append({"id": CAREER_ID[name], "type": "Career", "name": name, "area": area,
                        "demand_level": demand, "key_tools": tools})
    # Cota de eletivas por curso: exige ~metade dos créditos eletivos ofertados (múltiplo de
    # 4), para não obrigar o aluno a cursar TODAS as eletivas. 0 se o curso não tem eletiva.
    offered_elec = {pid: 0 for pid in CURRICULA}
    for k, reqs in prog_of.items():
        for pid, req in reqs.items():
            if req == E:
                offered_elec[pid] += D[k][3]
    programs = []
    for p in PROGRAMS:
        off = offered_elec.get(p["id"], 0)
        required = 0 if off == 0 else min(off, max(4, round(off * 0.5 / 4) * 4))
        programs.append({"id": p["id"], "type": "Program", "name": p["name"], "code": p["code"],
                         "kb_curso_id": p["kb_curso_id"],
                         "elective_credits_required": required,
                         "elective_credits_offered": off})

    # 4) relationships.json
    edges = []
    for k in ordered:
        for pre in D[k][5]:
            edges.append({"type": "PREREQUISITE_OF", "from": disc_id[pre], "to": disc_id[k],
                          "properties": {"type": "mandatory"}})
        for comp, w in D[k][4]:
            edges.append({"type": "DEVELOPS_COMPETENCY", "from": disc_id[k], "to": COMP_ID[comp],
                          "properties": {"weight": w}})
    for name, _a, _d, _t, reqs in CAREERS:
        for comp, imp in reqs:
            edges.append({"type": "REQUIRES_COMPETENCY", "from": CAREER_ID[name], "to": COMP_ID[comp],
                          "properties": {"importance": imp}})
    # COMPLEMENTS não pode coincidir com um par de PREREQUISITE_OF (mesmo (u,v) colapsaria
    # no DiGraph e apagaria o pré-requisito). Escolhemos pares SEM relação de pré-requisito.
    prereq_pairs = set()
    for k in ordered:
        for pre in D[k][5]:
            prereq_pairs.add((pre, k)); prereq_pairs.add((k, pre))
    COMPLEMENTS = [
        ("ux", "web", "UX/UI potencializa o desenvolvimento web"),
        ("deep", "nlp", "Deep Learning fundamenta o NLP moderno"),
        ("qualidade", "pcp", "Qualidade e PCP andam juntos na produção"),
        ("logistica", "pcp", "Logística e PCP se reforçam na operação"),
        ("seg", "redes", "Segurança se apoia em redes de computadores"),
        ("ia", "estat", "IA moderna se apoia fortemente em estatística"),
        ("gestproj", "engsw1", "Gestão de projetos complementa engenharia de software"),
        ("cad", "procfab", "CAD apoia o planejamento dos processos de fabricação"),
        ("govdados", "seg", "Governança de dados anda junto com segurança"),
    ]
    for a, b, reason in COMPLEMENTS:
        if a in disc_id and b in disc_id and (a, b) not in prereq_pairs:
            edges.append({"type": "COMPLEMENTS", "from": disc_id[a], "to": disc_id[b],
                          "properties": {"reason": reason}})

    # 5) students.json — 40 alunos coerentes
    students = build_students(disc_id)

    # 6) Validação de integridade referencial
    valid = {d["id"] for d in disciplines} | {c["id"] for c in competencies} | {c["id"] for c in careers}
    for e in edges:
        if e["from"] not in valid or e["to"] not in valid:
            raise SystemExit(f"Aresta com nó inexistente: {e}")

    # 6b) Coerência curso × carreira-alvo: toda competência CRÍTICA de uma carreira que os
    # alunos de um curso podem mirar precisa ser desenvolvida por alguma disciplina do curso
    # (senão vira uma "lacuna" impossível — ex.: Produção mirando termodinâmica de Mecânica).
    prog_comps = {pid: set() for pid in CURRICULA}
    for k, reqs in prog_of.items():
        for comp, _w in D[k][4]:
            for pid in reqs:
                prog_comps[pid].add(comp)
    reqs_by_career = {name: reqs for name, *_r, reqs in CAREERS}
    for pid, career_names in PROGRAM_CAREERS.items():
        for cname in career_names:
            for comp, imp in reqs_by_career.get(cname, []):
                if imp == "critical" and comp not in prog_comps[pid]:
                    raise SystemExit(
                        f"Pareamento inválido: alunos de {pid} podem mirar '{cname}', que exige "
                        f"'{comp}' (crítica), mas o curso não desenvolve essa competência.")

    # 7) Grava
    dump("programs.json", programs)
    dump("competencies.json", competencies)
    dump("careers.json", careers)
    dump("disciplines.json", disciplines)
    dump("relationships.json", edges)
    dump("students.json", students)

    counts = {}
    for e in edges:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    shared = sum(1 for d in disciplines if len(d["programs"]) > 1)
    print(f"programs={len(programs)} competencies={len(competencies)} careers={len(careers)} "
          f"disciplines={len(disciplines)} ({shared} compartilhadas) students={len(students)}")
    print("relationships:", counts, "total:", len(edges))

    # 8) Sanidade: reconstrói com o builder (valida DAG e refs)
    import sys
    sys.path.insert(0, os.path.abspath("."))
    from src.graph.builder import build_graph
    g = build_graph()
    print(f"builder OK: {g.number_of_nodes()} nós, {g.number_of_edges()} arestas")


def build_students(disc_id: dict) -> list:
    """Gera 40 alunos, distribuídos pelos cursos, com histórico coerente: cursa as
    disciplinas do seu currículo com semestre < semestre atual, em ordem, com notas."""
    # Currículo por programa em estrutura util: lista de (key, sem, req)
    students = []
    programs = list(CURRICULA.keys())
    used_names = set()
    for i in range(1, 41):
        pid = programs[(i - 1) % len(programs)]
        # nome único
        while True:
            nm = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            if nm not in used_names:
                used_names.add(nm); break
        cur_sem = random.randint(1, 8)
        target = CAREER_ID[random.choice(PROGRAM_CAREERS[pid])]
        # disciplinas do currículo com semestre estritamente menor que o atual
        plan = sorted(CURRICULA[pid], key=lambda t: t[1])
        completed = []
        base_year = 2026 - (cur_sem // 2 + 1)
        for key, sem, req in plan:
            if sem >= cur_sem:
                continue
            # ~85% das obrigatórias concluídas; ~45% das eletivas
            p = 0.85 if req == M else 0.45
            if random.random() > p:
                continue
            grade = round(random.uniform(6.0, 9.8), 1)
            year = base_year + (sem - 1) // 2
            completed.append({"discipline": disc_id[key], "grade": grade,
                              "semester": sem, "year": year})
        completed.sort(key=lambda c: (c["year"], c["semester"]))
        students.append({
            "id": f"student_{i:03d}", "type": "Student", "name": nm,
            "program": pid, "current_semester": cur_sem, "target_career": target,
            "email": f"aluno{i:03d}@faculdade.edu.br", "completed": completed,
        })
    return students


def dump(name: str, obj) -> None:
    with open(os.path.join("data", name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
