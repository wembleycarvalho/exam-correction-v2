"""
Gera PDFs de apostilas para a Knowledge Base do Bedrock.
- 40 apostilas de disciplinas de Eng. Software (8 semestres x 5 disciplinas)
- 15 apostilas de cursos de extensao (1 por curso)
- 1 PDF institucional (sobre_instituicao.pdf)

Saida: output/apostilas/{publico,privado/graduacao/eng-software,privado/extensao/{curso_id}}/

Uso: python3 scripts/gerar_apostilas.py
"""
import os
import re
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors

# Importar conteudo de material de estudo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _material_content import MATERIAL_DISCIPLINAS, MATERIAL_EXTENSAO, gerar_conteudo_unidade_generico

# ============================================================
# Diretorio base de saida
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output', 'apostilas')

INSTITUICAO = 'Instituicao de Ensino Demo'
CURSO_GRAD = 'Engenharia de Software'
CURSO_ID_GRAD = 'eng-software'

# ============================================================
# Grade curricular (mesma de setup_academico.py)
# ============================================================
GRADE_CURRICULAR = {
    '1_semestre': ['Introducao a Programacao (Python)', 'Logica Matematica', 'Calculo I', 'Comunicacao e Expressao', 'Fundamentos de Computacao'],
    '2_semestre': ['Estrutura de Dados', 'Programacao Orientada a Objetos', 'Calculo II', 'Banco de Dados I', 'Sistemas Operacionais'],
    '3_semestre': ['Engenharia de Software I', 'Redes de Computadores', 'Estatistica', 'Banco de Dados II', 'Desenvolvimento Web'],
    '4_semestre': ['Engenharia de Software II', 'Arquitetura de Software', 'Testes de Software', 'Desenvolvimento Mobile', 'Projeto Integrador I'],
    '5_semestre': ['DevOps e Cloud Computing', 'Inteligencia Artificial', 'Seguranca da Informacao', 'Metodologias Ageis', 'Estagio Supervisionado I'],
    '6_semestre': ['Microsservicos e APIs', 'Machine Learning', 'Gestao de Projetos', 'UX/UI Design', 'Estagio Supervisionado II'],
    '7_semestre': ['Computacao em Nuvem Avancada', 'Big Data', 'Empreendedorismo Digital', 'Etica em TI', 'TCC I'],
    '8_semestre': ['IoT e Sistemas Embarcados', 'Blockchain', 'Inovacao Tecnologica', 'TCC II', 'Projeto Final'],
}

# ============================================================
# Cursos de extensao (mesmos de setup_academico.py)
# ============================================================
CURSOS_EXTENSAO = [
    {'curso_id': 'ext-ia-aplicada', 'nome': 'Inteligencia Artificial Aplicada', 'area': 'Tecnologia', 'modalidade': 'EAD', 'duracao_horas': 60, 'duracao_meses': 3, 'diferenciais': 'Projetos praticos com ChatGPT, visao computacional e NLP', 'mercado': 'Profissionais que querem aplicar IA no dia a dia'},
    {'curso_id': 'ext-cybersecurity', 'nome': 'Cybersecurity Essentials', 'area': 'Tecnologia', 'modalidade': 'EAD', 'duracao_horas': 40, 'duracao_meses': 2, 'diferenciais': 'Laboratorios virtuais de pentest, certificacao preparatoria CompTIA Security+', 'mercado': 'Analistas de seguranca, pentesters, gestores de TI'},
    {'curso_id': 'ext-data-science', 'nome': 'Data Science com Python', 'area': 'Tecnologia', 'modalidade': 'EAD', 'duracao_horas': 80, 'duracao_meses': 4, 'diferenciais': 'Pandas, Scikit-learn, projetos com dados reais', 'mercado': 'Cientistas de dados, analistas de BI, engenheiros de dados'},
    {'curso_id': 'ext-cloud-aws', 'nome': 'Cloud Computing com AWS', 'area': 'Tecnologia', 'modalidade': 'EAD', 'duracao_horas': 60, 'duracao_meses': 3, 'diferenciais': 'Preparatorio AWS Solutions Architect, laboratorios praticos', 'mercado': 'Arquitetos cloud, DevOps engineers, SREs'},
    {'curso_id': 'ext-ux-design', 'nome': 'UX/UI Design', 'area': 'Design', 'modalidade': 'EAD', 'duracao_horas': 50, 'duracao_meses': 3, 'diferenciais': 'Figma, pesquisa com usuarios, portfolio profissional', 'mercado': 'UX designers, UI designers, product designers'},
    {'curso_id': 'ext-gestao-projetos', 'nome': 'Gestao de Projetos e Metodologias Ageis', 'area': 'Negocios', 'modalidade': 'EAD', 'duracao_horas': 40, 'duracao_meses': 2, 'diferenciais': 'Scrum, Kanban, preparatorio PSM I', 'mercado': 'Scrum masters, product owners, gerentes de projeto'},
    {'curso_id': 'ext-marketing-digital', 'nome': 'Marketing Digital e Analytics', 'area': 'Negocios', 'modalidade': 'EAD', 'duracao_horas': 45, 'duracao_meses': 2, 'diferenciais': 'Google Ads, SEO, analytics, redes sociais', 'mercado': 'Analistas de marketing, social media, growth hackers'},
    {'curso_id': 'ext-devops', 'nome': 'DevOps e CI/CD', 'area': 'Tecnologia', 'modalidade': 'EAD', 'duracao_horas': 60, 'duracao_meses': 3, 'diferenciais': 'Docker, Kubernetes, Jenkins, GitHub Actions, Terraform', 'mercado': 'DevOps engineers, SREs, platform engineers'},
    {'curso_id': 'ext-blockchain', 'nome': 'Blockchain e Web3', 'area': 'Tecnologia', 'modalidade': 'EAD', 'duracao_horas': 40, 'duracao_meses': 2, 'diferenciais': 'Smart contracts, Solidity, DeFi, NFTs', 'mercado': 'Desenvolvedores blockchain, consultores Web3'},
    {'curso_id': 'ext-lideranca', 'nome': 'Lideranca e Gestao de Pessoas', 'area': 'Negocios', 'modalidade': 'EAD', 'duracao_horas': 30, 'duracao_meses': 2, 'diferenciais': 'Coaching, feedback, gestao de conflitos, lideranca situacional', 'mercado': 'Lideres, gestores, coordenadores, supervisores'},
    {'curso_id': 'ext-saude-mental', 'nome': 'Saude Mental no Trabalho', 'area': 'Saude', 'modalidade': 'EAD', 'duracao_horas': 30, 'duracao_meses': 2, 'diferenciais': 'Burnout, ansiedade, mindfulness, qualidade de vida', 'mercado': 'Profissionais de RH, gestores, profissionais de saude'},
    {'curso_id': 'ext-primeiros-socorros', 'nome': 'Primeiros Socorros e Urgencias', 'area': 'Saude', 'modalidade': 'Presencial', 'duracao_horas': 20, 'duracao_meses': 1, 'diferenciais': 'Pratica em manequins, certificado de socorrista', 'mercado': 'Profissionais de saude, bombeiros, brigadistas'},
    {'curso_id': 'ext-nutricao-esportiva', 'nome': 'Nutricao Esportiva', 'area': 'Saude', 'modalidade': 'EAD', 'duracao_horas': 40, 'duracao_meses': 2, 'diferenciais': 'Suplementacao, periodizacao nutricional, composicao corporal', 'mercado': 'Nutricionistas, personal trainers, atletas'},
    {'curso_id': 'ext-direito-digital', 'nome': 'Direito Digital e LGPD', 'area': 'Humanas', 'modalidade': 'EAD', 'duracao_horas': 30, 'duracao_meses': 2, 'diferenciais': 'LGPD, crimes digitais, contratos eletronicos, Marco Civil', 'mercado': 'Advogados, DPOs, compliance officers, profissionais de TI'},
    {'curso_id': 'ext-ingles-negocios', 'nome': 'Ingles para Negocios', 'area': 'Negocios', 'modalidade': 'EAD', 'duracao_horas': 60, 'duracao_meses': 3, 'diferenciais': 'Business English, apresentacoes, negociacoes, emails profissionais', 'mercado': 'Executivos, gestores, profissionais em empresas multinacionais'},
]


# ============================================================
# Conteudo detalhado por disciplina (ementa, objetivos, topicos, bibliografia)
# ============================================================
CONTEUDO_DISCIPLINAS = {
    'Introducao a Programacao (Python)': {
        'ementa': 'Fundamentos de logica de programacao. Variaveis, tipos de dados, operadores. Estruturas de controle (condicionais e repeticao). Funcoes e modularizacao. Manipulacao de strings e listas. Introducao a orientacao a objetos. Tratamento de excecoes. Leitura e escrita de arquivos.',
        'objetivos': [
            'Compreender os fundamentos da logica de programacao e algoritmos',
            'Desenvolver programas em Python utilizando estruturas basicas',
            'Aplicar conceitos de modularizacao e reutilizacao de codigo',
            'Resolver problemas computacionais de forma estruturada',
        ],
        'topicos': [
            'Unidade 1: Algoritmos e logica de programacao - pseudocodigo, fluxogramas',
            'Unidade 2: Variaveis, tipos de dados, entrada e saida',
            'Unidade 3: Estruturas condicionais (if/elif/else) e de repeticao (for/while)',
            'Unidade 4: Funcoes, parametros, retorno e escopo de variaveis',
            'Unidade 5: Listas, tuplas, dicionarios e manipulacao de colecoes',
            'Unidade 6: Manipulacao de strings e expressoes regulares basicas',
            'Unidade 7: Tratamento de excecoes e leitura/escrita de arquivos',
            'Unidade 8: Introducao a orientacao a objetos - classes e objetos',
        ],
        'bibliografia': [
            'MENEZES, N. Introducao a Programacao com Python. Novatec, 2019.',
            'DOWNEY, A. Pense em Python. Novatec, 2016.',
            'RAMALHO, L. Python Fluente. Novatec, 2023.',
        ],
    },
    'Logica Matematica': {
        'ementa': 'Proposicoes e conectivos logicos. Tabelas-verdade. Equivalencias e implicacoes logicas. Quantificadores. Metodos de demonstracao. Logica de predicados. Algebra booleana. Aplicacoes em computacao.',
        'objetivos': [
            'Dominar os fundamentos da logica proposicional e de predicados',
            'Construir e analisar tabelas-verdade e demonstracoes formais',
            'Aplicar logica matematica na resolucao de problemas computacionais',
            'Compreender a relacao entre logica e circuitos digitais',
        ],
        'topicos': [
            'Unidade 1: Proposicoes, conectivos logicos e tabelas-verdade',
            'Unidade 2: Equivalencias logicas e leis de De Morgan',
            'Unidade 3: Implicacao logica e argumentos validos',
            'Unidade 4: Quantificadores universal e existencial',
            'Unidade 5: Metodos de demonstracao (direta, contradicao, inducao)',
            'Unidade 6: Logica de predicados e formulas bem formadas',
            'Unidade 7: Algebra booleana e circuitos logicos',
            'Unidade 8: Aplicacoes em computacao e verificacao de software',
        ],
        'bibliografia': [
            'ALENCAR FILHO, E. Iniciacao a Logica Matematica. Nobel, 2002.',
            'GERSTING, J. Fundamentos Matematicos para Ciencia da Computacao. LTC, 2017.',
            'SOUZA, J. Logica para Ciencia da Computacao. Elsevier, 2015.',
        ],
    },
    'Calculo I': {
        'ementa': 'Funcoes reais de uma variavel. Limites e continuidade. Derivadas e aplicacoes. Integrais definidas e indefinidas. Teorema fundamental do calculo. Tecnicas de integracao.',
        'objetivos': [
            'Compreender os conceitos de limite, derivada e integral',
            'Aplicar tecnicas de derivacao e integracao na resolucao de problemas',
            'Modelar problemas de engenharia usando calculo diferencial e integral',
            'Desenvolver raciocinio matematico formal',
        ],
        'topicos': [
            'Unidade 1: Revisao de funcoes - dominio, imagem, graficos',
            'Unidade 2: Limites e continuidade de funcoes',
            'Unidade 3: Derivadas - definicao, regras de derivacao',
            'Unidade 4: Aplicacoes de derivadas - maximos, minimos, taxas de variacao',
            'Unidade 5: Integrais indefinidas e tecnicas de integracao',
            'Unidade 6: Integrais definidas e o Teorema Fundamental do Calculo',
            'Unidade 7: Aplicacoes de integrais - areas e volumes',
            'Unidade 8: Sequencias e series numericas (introducao)',
        ],
        'bibliografia': [
            'STEWART, J. Calculo, Vol. 1. Cengage Learning, 2021.',
            'GUIDORIZZI, H. Um Curso de Calculo, Vol. 1. LTC, 2018.',
            'THOMAS, G. Calculo, Vol. 1. Pearson, 2020.',
        ],
    },
    'Comunicacao e Expressao': {
        'ementa': 'Leitura e interpretacao de textos tecnicos e academicos. Producao textual: relatorios, artigos, documentacao tecnica. Comunicacao oral: apresentacoes e seminarios. Normas ABNT para trabalhos academicos.',
        'objetivos': [
            'Desenvolver habilidades de leitura critica e interpretacao textual',
            'Produzir textos tecnicos e academicos com clareza e coesao',
            'Aprimorar a comunicacao oral em contextos profissionais',
            'Aplicar normas ABNT na elaboracao de trabalhos academicos',
        ],
        'topicos': [
            'Unidade 1: Leitura e interpretacao de textos tecnicos',
            'Unidade 2: Coesao e coerencia textual',
            'Unidade 3: Generos textuais academicos - resumo, resenha, artigo',
            'Unidade 4: Relatorios tecnicos e documentacao de software',
            'Unidade 5: Normas ABNT (NBR 14724, NBR 6023, NBR 10520)',
            'Unidade 6: Comunicacao oral - tecnicas de apresentacao',
            'Unidade 7: Seminarios e defesa de trabalhos',
            'Unidade 8: Redacao profissional - emails, propostas, especificacoes',
        ],
        'bibliografia': [
            'MEDEIROS, J. Redacao Cientifica. Atlas, 2019.',
            'FARACO, C.; TEZZA, C. Pratica de Texto para Estudantes Universitarios. Vozes, 2018.',
            'ASSOCIACAO BRASILEIRA DE NORMAS TECNICAS. NBR 14724. ABNT, 2011.',
        ],
    },
    'Fundamentos de Computacao': {
        'ementa': 'Historia da computacao. Arquitetura de computadores (Von Neumann). Representacao de dados (binario, hexadecimal). Sistemas operacionais basicos. Redes de computadores (introducao). Etica e sociedade digital.',
        'objetivos': [
            'Compreender a evolucao historica e os fundamentos da computacao',
            'Entender a arquitetura basica de um computador',
            'Converter e manipular dados em diferentes bases numericas',
            'Conhecer os conceitos basicos de sistemas operacionais e redes',
        ],
        'topicos': [
            'Unidade 1: Historia da computacao - de Babbage aos dias atuais',
            'Unidade 2: Arquitetura de Von Neumann - CPU, memoria, E/S',
            'Unidade 3: Representacao de dados - binario, octal, hexadecimal',
            'Unidade 4: Logica digital e portas logicas',
            'Unidade 5: Sistemas operacionais - conceitos fundamentais',
            'Unidade 6: Introducao a redes de computadores',
            'Unidade 7: Internet, protocolos e servicos web',
            'Unidade 8: Etica, privacidade e sociedade digital',
        ],
        'bibliografia': [
            'BROOKSHEAR, J. Ciencia da Computacao: Uma Visao Abrangente. Bookman, 2013.',
            'TANENBAUM, A. Organizacao Estruturada de Computadores. Pearson, 2013.',
            'STALLINGS, W. Arquitetura e Organizacao de Computadores. Pearson, 2017.',
        ],
    },
    'Estrutura de Dados': {
        'ementa': 'Listas, pilhas e filas. Arvores binarias e de busca. Grafos. Tabelas hash. Algoritmos de ordenacao e busca. Complexidade de algoritmos (notacao Big-O). Recursividade.',
        'objetivos': [
            'Implementar e utilizar estruturas de dados fundamentais',
            'Analisar a complexidade de algoritmos',
            'Escolher a estrutura de dados adequada para cada problema',
            'Aplicar algoritmos de ordenacao e busca eficientes',
        ],
        'topicos': [
            'Unidade 1: Revisao de ponteiros e alocacao dinamica',
            'Unidade 2: Listas encadeadas (simples, dupla, circular)',
            'Unidade 3: Pilhas e filas - implementacao e aplicacoes',
            'Unidade 4: Arvores binarias e arvores de busca (BST)',
            'Unidade 5: Arvores balanceadas (AVL) e heaps',
            'Unidade 6: Tabelas hash - funcoes de dispersao e colisoes',
            'Unidade 7: Grafos - representacao, BFS, DFS',
            'Unidade 8: Algoritmos de ordenacao (quicksort, mergesort, heapsort)',
        ],
        'bibliografia': [
            'CORMEN, T. et al. Algoritmos: Teoria e Pratica. Elsevier, 2012.',
            'ZIVIANI, N. Projeto de Algoritmos. Cengage Learning, 2010.',
            'GOODRICH, M.; TAMASSIA, R. Estruturas de Dados e Algoritmos em Java. Bookman, 2013.',
        ],
    },
    'Programacao Orientada a Objetos': {
        'ementa': 'Paradigma orientado a objetos. Classes, objetos, atributos e metodos. Encapsulamento, heranca e polimorfismo. Classes abstratas e interfaces. Padroes de projeto basicos. Tratamento de excecoes. Colecoes e generics.',
        'objetivos': [
            'Dominar os pilares da programacao orientada a objetos',
            'Projetar sistemas utilizando classes, heranca e polimorfismo',
            'Aplicar padroes de projeto basicos (Singleton, Factory, Observer)',
            'Desenvolver aplicacoes robustas com tratamento de excecoes',
        ],
        'topicos': [
            'Unidade 1: Paradigma OO - classes, objetos, construtores',
            'Unidade 2: Encapsulamento e modificadores de acesso',
            'Unidade 3: Heranca e composicao',
            'Unidade 4: Polimorfismo e sobrecarga/sobrescrita de metodos',
            'Unidade 5: Classes abstratas e interfaces',
            'Unidade 6: Colecoes, generics e iteradores',
            'Unidade 7: Tratamento de excecoes e boas praticas',
            'Unidade 8: Padroes de projeto - Singleton, Factory, Observer, Strategy',
        ],
        'bibliografia': [
            'GAMMA, E. et al. Padroes de Projeto. Bookman, 2000.',
            'DEITEL, P.; DEITEL, H. Java: Como Programar. Pearson, 2017.',
            'MARTIN, R. Codigo Limpo. Alta Books, 2009.',
        ],
    },
    'Calculo II': {
        'ementa': 'Funcoes de varias variaveis. Derivadas parciais. Integrais duplas e triplas. Equacoes diferenciais ordinarias. Transformada de Laplace (introducao). Aplicacoes em engenharia.',
        'objetivos': [
            'Estender os conceitos de calculo para funcoes de varias variaveis',
            'Calcular derivadas parciais e integrais multiplas',
            'Resolver equacoes diferenciais ordinarias basicas',
            'Aplicar calculo avancado em problemas de engenharia',
        ],
        'topicos': [
            'Unidade 1: Funcoes de varias variaveis - dominio, graficos, curvas de nivel',
            'Unidade 2: Derivadas parciais e gradiente',
            'Unidade 3: Maximos e minimos de funcoes de varias variaveis',
            'Unidade 4: Integrais duplas e aplicacoes',
            'Unidade 5: Integrais triplas e mudanca de coordenadas',
            'Unidade 6: Equacoes diferenciais ordinarias de 1a ordem',
            'Unidade 7: EDOs de 2a ordem com coeficientes constantes',
            'Unidade 8: Introducao a Transformada de Laplace',
        ],
        'bibliografia': [
            'STEWART, J. Calculo, Vol. 2. Cengage Learning, 2021.',
            'GUIDORIZZI, H. Um Curso de Calculo, Vol. 2. LTC, 2018.',
            'BOYCE, W.; DIPRIMA, R. Equacoes Diferenciais Elementares. LTC, 2015.',
        ],
    },
    'Banco de Dados I': {
        'ementa': 'Conceitos de banco de dados. Modelo entidade-relacionamento. Modelo relacional. SQL (DDL, DML, DQL). Normalizacao. Indices e otimizacao basica. Transacoes e controle de concorrencia.',
        'objetivos': [
            'Projetar bancos de dados relacionais usando modelagem ER',
            'Implementar e consultar bancos de dados usando SQL',
            'Aplicar normalizacao para eliminar redundancias',
            'Compreender transacoes e controle de concorrencia',
        ],
        'topicos': [
            'Unidade 1: Conceitos fundamentais de banco de dados e SGBDs',
            'Unidade 2: Modelo Entidade-Relacionamento (ER)',
            'Unidade 3: Modelo relacional e algebra relacional',
            'Unidade 4: SQL - DDL (CREATE, ALTER, DROP)',
            'Unidade 5: SQL - DML (INSERT, UPDATE, DELETE) e DQL (SELECT)',
            'Unidade 6: Joins, subconsultas e funcoes de agregacao',
            'Unidade 7: Normalizacao (1FN, 2FN, 3FN, BCNF)',
            'Unidade 8: Transacoes, ACID e controle de concorrencia',
        ],
        'bibliografia': [
            'ELMASRI, R.; NAVATHE, S. Sistemas de Banco de Dados. Pearson, 2019.',
            'DATE, C. Introducao a Sistemas de Bancos de Dados. Elsevier, 2004.',
            'SILBERSCHATZ, A. Sistema de Banco de Dados. Elsevier, 2012.',
        ],
    },
    'Sistemas Operacionais': {
        'ementa': 'Conceitos de sistemas operacionais. Processos e threads. Escalonamento de CPU. Gerenciamento de memoria. Sistemas de arquivos. Entrada e saida. Virtualizacao e containers (introducao).',
        'objetivos': [
            'Compreender a arquitetura e funcionamento de sistemas operacionais',
            'Entender gerenciamento de processos, memoria e E/S',
            'Analisar algoritmos de escalonamento e paginacao',
            'Conhecer conceitos de virtualizacao e containers',
        ],
        'topicos': [
            'Unidade 1: Introducao a sistemas operacionais - historia e tipos',
            'Unidade 2: Processos e threads - criacao, estados, comunicacao',
            'Unidade 3: Escalonamento de CPU - FCFS, SJF, Round Robin, prioridade',
            'Unidade 4: Sincronizacao e deadlocks',
            'Unidade 5: Gerenciamento de memoria - paginacao e segmentacao',
            'Unidade 6: Memoria virtual e algoritmos de substituicao de paginas',
            'Unidade 7: Sistemas de arquivos e gerenciamento de E/S',
            'Unidade 8: Virtualizacao, containers e introducao ao Linux',
        ],
        'bibliografia': [
            'TANENBAUM, A. Sistemas Operacionais Modernos. Pearson, 2016.',
            'SILBERSCHATZ, A. Fundamentos de Sistemas Operacionais. LTC, 2015.',
            'STALLINGS, W. Operating Systems: Internals and Design Principles. Pearson, 2018.',
        ],
    },
    'Engenharia de Software I': {
        'ementa': 'Processos de desenvolvimento de software. Engenharia de requisitos. Modelagem UML. Ciclo de vida do software. Metodologias tradicionais (cascata, espiral). Documentacao de software. Qualidade de software.',
        'objetivos': [
            'Compreender os processos e modelos de desenvolvimento de software',
            'Aplicar tecnicas de engenharia de requisitos',
            'Modelar sistemas usando UML (casos de uso, classes, sequencia)',
            'Elaborar documentacao tecnica de projetos de software',
        ],
        'topicos': [
            'Unidade 1: Introducao a engenharia de software - conceitos e importancia',
            'Unidade 2: Processos de software - cascata, incremental, espiral',
            'Unidade 3: Engenharia de requisitos - elicitacao e especificacao',
            'Unidade 4: Modelagem UML - diagramas de casos de uso',
            'Unidade 5: Modelagem UML - diagramas de classes e sequencia',
            'Unidade 6: Projeto de software - arquitetura e design',
            'Unidade 7: Documentacao de software - SRS, SDD',
            'Unidade 8: Qualidade de software - metricas e padroes (ISO 25010)',
        ],
        'bibliografia': [
            'SOMMERVILLE, I. Engenharia de Software. Pearson, 2019.',
            'PRESSMAN, R. Engenharia de Software: Uma Abordagem Profissional. McGraw-Hill, 2021.',
            'LARMAN, C. Utilizando UML e Padroes. Bookman, 2007.',
        ],
    },
    'Redes de Computadores': {
        'ementa': 'Modelo OSI e TCP/IP. Camada fisica e enlace. Protocolos de rede (IP, ICMP). Camada de transporte (TCP, UDP). Camada de aplicacao (HTTP, DNS, SMTP). Seguranca em redes. Redes sem fio.',
        'objetivos': [
            'Compreender a arquitetura e os protocolos de redes de computadores',
            'Analisar o funcionamento das camadas do modelo TCP/IP',
            'Configurar e diagnosticar redes basicas',
            'Entender conceitos de seguranca em redes',
        ],
        'topicos': [
            'Unidade 1: Introducao a redes - topologias, classificacao, modelo OSI',
            'Unidade 2: Camada fisica - meios de transmissao, sinalizacao',
            'Unidade 3: Camada de enlace - Ethernet, switches, VLANs',
            'Unidade 4: Camada de rede - IP, roteamento, sub-redes',
            'Unidade 5: Camada de transporte - TCP, UDP, portas',
            'Unidade 6: Camada de aplicacao - HTTP, DNS, SMTP, FTP',
            'Unidade 7: Seguranca em redes - firewalls, VPN, SSL/TLS',
            'Unidade 8: Redes sem fio e computacao em nuvem (introducao)',
        ],
        'bibliografia': [
            'KUROSE, J.; ROSS, K. Redes de Computadores e a Internet. Pearson, 2021.',
            'TANENBAUM, A. Redes de Computadores. Pearson, 2011.',
            'FOROUZAN, B. Comunicacao de Dados e Redes de Computadores. McGraw-Hill, 2008.',
        ],
    },
    'Estatistica': {
        'ementa': 'Estatistica descritiva. Probabilidade. Distribuicoes de probabilidade. Amostragem. Estimacao e intervalos de confianca. Testes de hipoteses. Regressao linear. Aplicacoes em engenharia de software.',
        'objetivos': [
            'Aplicar metodos estatisticos na analise de dados',
            'Compreender distribuicoes de probabilidade e inferencia estatistica',
            'Realizar testes de hipoteses e regressao linear',
            'Utilizar estatistica em metricas de software e qualidade',
        ],
        'topicos': [
            'Unidade 1: Estatistica descritiva - medidas de tendencia central e dispersao',
            'Unidade 2: Probabilidade - conceitos, eventos, probabilidade condicional',
            'Unidade 3: Variaveis aleatorias e distribuicoes (binomial, Poisson)',
            'Unidade 4: Distribuicao normal e teorema central do limite',
            'Unidade 5: Amostragem e estimacao pontual e intervalar',
            'Unidade 6: Testes de hipoteses - z, t, qui-quadrado',
            'Unidade 7: Regressao linear simples e correlacao',
            'Unidade 8: Aplicacoes em engenharia de software - metricas e estimativas',
        ],
        'bibliografia': [
            'MONTGOMERY, D.; RUNGER, G. Estatistica Aplicada e Probabilidade para Engenheiros. LTC, 2018.',
            'BUSSAB, W.; MORETTIN, P. Estatistica Basica. Saraiva, 2017.',
            'TRIOLA, M. Introducao a Estatistica. LTC, 2017.',
        ],
    },
    'Banco de Dados II': {
        'ementa': 'Bancos de dados NoSQL. MongoDB, DynamoDB, Redis. Modelagem de dados NoSQL. Bancos de dados distribuidos. Replicacao e sharding. Data warehousing. Introducao a Big Data.',
        'objetivos': [
            'Compreender os diferentes paradigmas de bancos de dados NoSQL',
            'Projetar e implementar solucoes com bancos NoSQL',
            'Entender conceitos de bancos distribuidos e escalabilidade',
            'Conhecer fundamentos de data warehousing e Big Data',
        ],
        'topicos': [
            'Unidade 1: Limitacoes do modelo relacional e motivacao para NoSQL',
            'Unidade 2: Bancos de dados chave-valor (Redis, DynamoDB)',
            'Unidade 3: Bancos de dados de documentos (MongoDB)',
            'Unidade 4: Bancos de dados colunares e de grafos',
            'Unidade 5: Modelagem de dados NoSQL - desnormalizacao e padroes',
            'Unidade 6: Bancos distribuidos - CAP theorem, consistencia eventual',
            'Unidade 7: Replicacao, sharding e particionamento',
            'Unidade 8: Data warehousing, ETL e introducao a Big Data',
        ],
        'bibliografia': [
            'SADALAGE, P.; FOWLER, M. NoSQL Essencial. Novatec, 2013.',
            'MONGODB INC. MongoDB Manual. docs.mongodb.com, 2024.',
            'AMAZON WEB SERVICES. DynamoDB Developer Guide. docs.aws.amazon.com, 2024.',
        ],
    },
    'Desenvolvimento Web': {
        'ementa': 'HTML5, CSS3 e JavaScript. Frameworks front-end (React). APIs REST. Node.js e Express. Autenticacao e autorizacao. Deploy e hospedagem. Acessibilidade e responsividade.',
        'objetivos': [
            'Desenvolver aplicacoes web completas (front-end e back-end)',
            'Utilizar frameworks modernos de desenvolvimento web',
            'Implementar APIs RESTful e integracao com bancos de dados',
            'Aplicar boas praticas de acessibilidade e responsividade',
        ],
        'topicos': [
            'Unidade 1: HTML5 - estrutura semantica, formularios, multimedia',
            'Unidade 2: CSS3 - layout (Flexbox, Grid), animacoes, responsividade',
            'Unidade 3: JavaScript - DOM, eventos, fetch API, async/await',
            'Unidade 4: React - componentes, estado, hooks, roteamento',
            'Unidade 5: Node.js e Express - servidor, rotas, middleware',
            'Unidade 6: APIs REST - design, documentacao (OpenAPI), versionamento',
            'Unidade 7: Autenticacao (JWT, OAuth) e autorizacao',
            'Unidade 8: Deploy, CI/CD basico e hospedagem (Vercel, AWS)',
        ],
        'bibliografia': [
            'FLANAGAN, D. JavaScript: O Guia Definitivo. Bookman, 2013.',
            'BANKS, A.; PORCELLO, E. O Guia Completo do React. Novatec, 2021.',
            'BROWN, E. Desenvolvimento Web com Node e Express. Novatec, 2020.',
        ],
    },
    'Engenharia de Software II': {
        'ementa': 'Padroes de projeto avancados. Refatoracao. Principios SOLID. Clean Architecture. Domain-Driven Design (DDD). Documentacao tecnica avancada. Revisao de codigo e code review.',
        'objetivos': [
            'Aplicar padroes de projeto avancados em sistemas reais',
            'Refatorar codigo aplicando principios SOLID e Clean Code',
            'Projetar sistemas usando Clean Architecture e DDD',
            'Conduzir revisoes de codigo eficazes',
        ],
        'topicos': [
            'Unidade 1: Principios SOLID - SRP, OCP, LSP, ISP, DIP',
            'Unidade 2: Padroes de projeto - Adapter, Decorator, Facade, Proxy',
            'Unidade 3: Padroes de projeto - Command, Template Method, Chain of Responsibility',
            'Unidade 4: Refatoracao - tecnicas e ferramentas',
            'Unidade 5: Clean Architecture - camadas e dependencias',
            'Unidade 6: Domain-Driven Design - entidades, value objects, aggregates',
            'Unidade 7: Documentacao tecnica - ADRs, diagramas C4',
            'Unidade 8: Code review - boas praticas e ferramentas',
        ],
        'bibliografia': [
            'MARTIN, R. Arquitetura Limpa. Alta Books, 2019.',
            'EVANS, E. Domain-Driven Design. Alta Books, 2016.',
            'FOWLER, M. Refatoracao. Novatec, 2020.',
        ],
    },
    'Arquitetura de Software': {
        'ementa': 'Estilos arquiteturais. Arquitetura em camadas. Microsservicos vs monolito. Event-driven architecture. Mensageria. API Gateway. Service mesh. Documentacao arquitetural (C4 model).',
        'objetivos': [
            'Projetar arquiteturas de software escalaveis e mantiveis',
            'Avaliar trade-offs entre diferentes estilos arquiteturais',
            'Implementar comunicacao entre servicos (sincrona e assincrona)',
            'Documentar decisoes arquiteturais usando modelos padrao',
        ],
        'topicos': [
            'Unidade 1: Fundamentos de arquitetura de software',
            'Unidade 2: Arquitetura em camadas e MVC',
            'Unidade 3: Microsservicos - decomposicao, comunicacao, dados',
            'Unidade 4: Event-driven architecture e CQRS',
            'Unidade 5: Mensageria - RabbitMQ, Kafka, SQS',
            'Unidade 6: API Gateway e service mesh',
            'Unidade 7: Arquitetura serverless e FaaS',
            'Unidade 8: Documentacao - C4 model, ADRs, diagramas de arquitetura',
        ],
        'bibliografia': [
            'RICHARDS, M.; FORD, N. Fundamentals of Software Architecture. OReilly, 2020.',
            'NEWMAN, S. Construindo Microsservicos. Novatec, 2022.',
            'BROWN, S. Software Architecture for Developers. Leanpub, 2019.',
        ],
    },
    'Testes de Software': {
        'ementa': 'Fundamentos de testes. Testes unitarios, integracao e E2E. TDD e BDD. Automacao de testes. Testes de performance e seguranca. Cobertura de codigo. Ferramentas (JUnit, pytest, Selenium).',
        'objetivos': [
            'Planejar e executar estrategias de teste de software',
            'Implementar testes automatizados em diferentes niveis',
            'Aplicar TDD e BDD no desenvolvimento de software',
            'Utilizar ferramentas de automacao e cobertura de testes',
        ],
        'topicos': [
            'Unidade 1: Fundamentos de testes - tipos, niveis, tecnicas',
            'Unidade 2: Testes unitarios - JUnit, pytest, mocking',
            'Unidade 3: TDD - Test-Driven Development na pratica',
            'Unidade 4: BDD - Behavior-Driven Development com Cucumber/Gherkin',
            'Unidade 5: Testes de integracao e testes de API',
            'Unidade 6: Testes E2E - Selenium, Cypress, Playwright',
            'Unidade 7: Testes de performance (JMeter) e seguranca (OWASP ZAP)',
            'Unidade 8: Cobertura de codigo, CI/CD e qualidade continua',
        ],
        'bibliografia': [
            'BECK, K. TDD: Desenvolvimento Guiado por Testes. Bookman, 2010.',
            'DELAMARO, M. Introducao ao Teste de Software. Elsevier, 2016.',
            'SMART, J. BDD in Action. Manning, 2014.',
        ],
    },
    'Desenvolvimento Mobile': {
        'ementa': 'Plataformas mobile (Android, iOS). React Native e Flutter. UI/UX mobile. Armazenamento local. Consumo de APIs. Notificacoes push. Publicacao em lojas (Play Store, App Store).',
        'objetivos': [
            'Desenvolver aplicativos mobile multiplataforma',
            'Aplicar padroes de UI/UX especificos para mobile',
            'Integrar aplicativos com APIs e armazenamento local',
            'Publicar aplicativos nas lojas oficiais',
        ],
        'topicos': [
            'Unidade 1: Ecossistema mobile - Android, iOS, multiplataforma',
            'Unidade 2: React Native - componentes, navegacao, estado',
            'Unidade 3: Flutter - widgets, layout, gerenciamento de estado',
            'Unidade 4: UI/UX mobile - Material Design, Human Interface Guidelines',
            'Unidade 5: Armazenamento local - SQLite, AsyncStorage, SharedPreferences',
            'Unidade 6: Consumo de APIs REST e autenticacao',
            'Unidade 7: Notificacoes push, geolocalizacao e camera',
            'Unidade 8: Publicacao - Play Store, App Store, CI/CD mobile',
        ],
        'bibliografia': [
            'EISENMAN, B. Learning React Native. OReilly, 2017.',
            'NAPOLI, M. Beginning Flutter. Wiley, 2019.',
            'GOOGLE. Flutter Documentation. flutter.dev, 2024.',
        ],
    },
    'Projeto Integrador I': {
        'ementa': 'Projeto pratico integrando disciplinas do semestre. Definicao de escopo e requisitos. Desenvolvimento em equipe. Metodologia agil (Scrum). Apresentacao e defesa do projeto. Documentacao tecnica.',
        'objetivos': [
            'Integrar conhecimentos de multiplas disciplinas em um projeto real',
            'Trabalhar em equipe utilizando metodologias ageis',
            'Desenvolver um sistema completo do levantamento a entrega',
            'Apresentar e defender o projeto perante banca avaliadora',
        ],
        'topicos': [
            'Unidade 1: Formacao de equipes e definicao do projeto',
            'Unidade 2: Levantamento de requisitos e product backlog',
            'Unidade 3: Sprint 1 - Arquitetura e prototipo',
            'Unidade 4: Sprint 2 - Desenvolvimento do MVP',
            'Unidade 5: Sprint 3 - Funcionalidades complementares',
            'Unidade 6: Sprint 4 - Testes e refinamento',
            'Unidade 7: Documentacao tecnica e manual do usuario',
            'Unidade 8: Apresentacao final e defesa do projeto',
        ],
        'bibliografia': [
            'SCHWABER, K.; SUTHERLAND, J. O Guia do Scrum. scrumguides.org, 2020.',
            'COHN, M. Desenvolvimento de Software com Scrum. Bookman, 2011.',
            'PRESSMAN, R. Engenharia de Software. McGraw-Hill, 2021.',
        ],
    },
    'DevOps e Cloud Computing': {
        'ementa': 'Cultura DevOps. Integracao e entrega continua (CI/CD). Containers (Docker). Orquestracao (Kubernetes). Infraestrutura como codigo (Terraform). Monitoramento e observabilidade. Cloud providers (AWS, Azure, GCP).',
        'objetivos': [
            'Implementar pipelines de CI/CD automatizados',
            'Utilizar containers e orquestracao em ambientes de producao',
            'Provisionar infraestrutura como codigo',
            'Monitorar e observar sistemas em producao',
        ],
        'topicos': [
            'Unidade 1: Cultura DevOps - principios, praticas, ferramentas',
            'Unidade 2: Controle de versao avancado - Git flow, trunk-based',
            'Unidade 3: CI/CD - GitHub Actions, Jenkins, GitLab CI',
            'Unidade 4: Docker - imagens, containers, Dockerfile, compose',
            'Unidade 5: Kubernetes - pods, services, deployments, ingress',
            'Unidade 6: Infraestrutura como codigo - Terraform, CloudFormation',
            'Unidade 7: Cloud computing - AWS (EC2, S3, Lambda, RDS)',
            'Unidade 8: Monitoramento - Prometheus, Grafana, CloudWatch, logs',
        ],
        'bibliografia': [
            'KIM, G. et al. O Projeto Phoenix. Alta Books, 2016.',
            'MORRIS, K. Infrastructure as Code. OReilly, 2020.',
            'BURNS, B. Kubernetes: Tudo Sobre Orquestracao de Containers. Novatec, 2019.',
        ],
    },
    'Inteligencia Artificial': {
        'ementa': 'Fundamentos de IA. Busca e otimizacao. Representacao de conhecimento. Aprendizado de maquina (introducao). Redes neurais artificiais. Processamento de linguagem natural. Etica em IA.',
        'objetivos': [
            'Compreender os fundamentos e tecnicas de inteligencia artificial',
            'Implementar algoritmos de busca e otimizacao',
            'Aplicar tecnicas basicas de aprendizado de maquina',
            'Discutir implicacoes eticas do uso de IA',
        ],
        'topicos': [
            'Unidade 1: Historia e fundamentos da IA - teste de Turing, agentes inteligentes',
            'Unidade 2: Busca - BFS, DFS, A*, busca heuristica',
            'Unidade 3: Representacao de conhecimento - logica, ontologias',
            'Unidade 4: Aprendizado de maquina - supervisionado, nao-supervisionado',
            'Unidade 5: Redes neurais artificiais - perceptron, backpropagation',
            'Unidade 6: Deep learning - CNNs, RNNs (introducao)',
            'Unidade 7: Processamento de linguagem natural - NLP, chatbots, LLMs',
            'Unidade 8: Etica em IA - vies, fairness, explicabilidade, regulamentacao',
        ],
        'bibliografia': [
            'RUSSELL, S.; NORVIG, P. Inteligencia Artificial. Elsevier, 2022.',
            'GERON, A. Maos a Obra: Aprendizado de Maquina com Scikit-Learn, Keras e TensorFlow. Alta Books, 2021.',
            'GOODFELLOW, I. et al. Deep Learning. MIT Press, 2016.',
        ],
    },
    'Seguranca da Informacao': {
        'ementa': 'Principios de seguranca (CIA). Criptografia simetrica e assimetrica. Autenticacao e autorizacao. OWASP Top 10. Pentest e analise de vulnerabilidades. LGPD e compliance. Seguranca em cloud.',
        'objetivos': [
            'Aplicar principios de seguranca da informacao em sistemas',
            'Implementar mecanismos de criptografia e autenticacao',
            'Identificar e mitigar vulnerabilidades (OWASP Top 10)',
            'Compreender aspectos legais e regulatorios (LGPD)',
        ],
        'topicos': [
            'Unidade 1: Fundamentos - confidencialidade, integridade, disponibilidade',
            'Unidade 2: Criptografia simetrica (AES) e assimetrica (RSA)',
            'Unidade 3: Hashing, assinaturas digitais e certificados',
            'Unidade 4: Autenticacao - senhas, MFA, OAuth, SAML',
            'Unidade 5: OWASP Top 10 - SQL injection, XSS, CSRF',
            'Unidade 6: Pentest - metodologia, ferramentas (Nmap, Burp Suite)',
            'Unidade 7: LGPD - principios, direitos, sancoes, DPO',
            'Unidade 8: Seguranca em cloud - IAM, encryption, compliance',
        ],
        'bibliografia': [
            'STALLINGS, W. Criptografia e Seguranca de Redes. Pearson, 2015.',
            'OWASP FOUNDATION. OWASP Top 10. owasp.org, 2021.',
            'KIM, D.; SOLOMON, M. Fundamentos de Seguranca de Sistemas de Informacao. LTC, 2014.',
        ],
    },
    'Metodologias Ageis': {
        'ementa': 'Manifesto Agil. Scrum - papeis, eventos, artefatos. Kanban. XP (Extreme Programming). SAFe (introducao). Metricas ageis. Ferramentas (Jira, Trello). Transformacao agil.',
        'objetivos': [
            'Dominar os frameworks ageis mais utilizados no mercado',
            'Aplicar Scrum e Kanban em projetos de software',
            'Utilizar metricas ageis para melhoria continua',
            'Compreender desafios da transformacao agil em organizacoes',
        ],
        'topicos': [
            'Unidade 1: Manifesto Agil - valores, principios, mindset',
            'Unidade 2: Scrum - papeis (PO, SM, Dev Team)',
            'Unidade 3: Scrum - eventos (Sprint, Planning, Daily, Review, Retro)',
            'Unidade 4: Scrum - artefatos (Product Backlog, Sprint Backlog, Incremento)',
            'Unidade 5: Kanban - principios, quadro, WIP limits, metricas',
            'Unidade 6: XP - pair programming, TDD, refactoring, CI',
            'Unidade 7: Metricas ageis - velocity, burndown, lead time, cycle time',
            'Unidade 8: SAFe (introducao) e transformacao agil organizacional',
        ],
        'bibliografia': [
            'SCHWABER, K.; SUTHERLAND, J. O Guia do Scrum. scrumguides.org, 2020.',
            'ANDERSON, D. Kanban: Mudanca Evolucionaria de Sucesso. Blue Hole Press, 2010.',
            'BECK, K. Extreme Programming Explained. Addison-Wesley, 2004.',
        ],
    },
    'Estagio Supervisionado I': {
        'ementa': 'Vivencia profissional em empresa ou projeto. Aplicacao pratica dos conhecimentos academicos. Relatorio de atividades. Orientacao academica. Etica profissional. Desenvolvimento de competencias.',
        'objetivos': [
            'Aplicar conhecimentos academicos em ambiente profissional real',
            'Desenvolver competencias tecnicas e comportamentais',
            'Elaborar relatorios tecnicos de atividades realizadas',
            'Refletir sobre a pratica profissional e etica',
        ],
        'topicos': [
            'Unidade 1: Orientacoes gerais - regulamento, documentacao, prazos',
            'Unidade 2: Plano de estagio - objetivos, atividades, cronograma',
            'Unidade 3: Acompanhamento - reunioes com orientador',
            'Unidade 4: Desenvolvimento de atividades na empresa',
            'Unidade 5: Relatorio parcial - estrutura e conteudo',
            'Unidade 6: Etica profissional e sigilo empresarial',
            'Unidade 7: Relatorio final - analise critica e aprendizados',
            'Unidade 8: Apresentacao do estagio e avaliacao',
        ],
        'bibliografia': [
            'BIANCHI, A. Manual de Orientacao: Estagio Supervisionado. Cengage, 2011.',
            'OLIVO, S.; LIMA, M. Estagio Supervisionado e Trabalho de Conclusao de Curso. Thomson, 2006.',
            'CONSELHO FEDERAL DE ENGENHARIA. Codigo de Etica Profissional. confea.org.br, 2019.',
        ],
    },
    'Microsservicos e APIs': {
        'ementa': 'Arquitetura de microsservicos. Design de APIs RESTful. GraphQL. gRPC. API Gateway e rate limiting. Documentacao (OpenAPI/Swagger). Versionamento de APIs. Service discovery.',
        'objetivos': [
            'Projetar e implementar arquiteturas baseadas em microsservicos',
            'Desenvolver APIs RESTful seguindo boas praticas',
            'Utilizar GraphQL e gRPC em cenarios apropriados',
            'Documentar e versionar APIs profissionalmente',
        ],
        'topicos': [
            'Unidade 1: Microsservicos - principios, decomposicao, bounded contexts',
            'Unidade 2: APIs RESTful - design, verbos HTTP, status codes, HATEOAS',
            'Unidade 3: GraphQL - schema, queries, mutations, subscriptions',
            'Unidade 4: gRPC - Protocol Buffers, streaming, performance',
            'Unidade 5: API Gateway - roteamento, rate limiting, autenticacao',
            'Unidade 6: Documentacao - OpenAPI/Swagger, Postman, exemplos',
            'Unidade 7: Versionamento, deprecacao e backward compatibility',
            'Unidade 8: Service discovery, circuit breaker e resiliencia',
        ],
        'bibliografia': [
            'NEWMAN, S. Construindo Microsservicos. Novatec, 2022.',
            'LAURET, A. The Design of Web APIs. Manning, 2019.',
            'RICHARDSON, C. Microsservicos: Padroes e Aplicacoes. Alta Books, 2021.',
        ],
    },
    'Machine Learning': {
        'ementa': 'Aprendizado supervisionado (regressao, classificacao). Aprendizado nao-supervisionado (clustering). Avaliacao de modelos. Feature engineering. Scikit-learn e TensorFlow. MLOps (introducao).',
        'objetivos': [
            'Implementar algoritmos de aprendizado de maquina',
            'Avaliar e otimizar modelos de ML',
            'Aplicar feature engineering e preprocessamento de dados',
            'Conhecer praticas de MLOps para producao',
        ],
        'topicos': [
            'Unidade 1: Fundamentos de ML - tipos de aprendizado, pipeline',
            'Unidade 2: Regressao linear e logistica',
            'Unidade 3: Arvores de decisao, Random Forest, Gradient Boosting',
            'Unidade 4: SVM e KNN',
            'Unidade 5: Clustering - K-Means, DBSCAN, hierarquico',
            'Unidade 6: Feature engineering e preprocessamento de dados',
            'Unidade 7: Avaliacao de modelos - metricas, validacao cruzada, overfitting',
            'Unidade 8: MLOps - deploy de modelos, monitoramento, retraining',
        ],
        'bibliografia': [
            'GERON, A. Maos a Obra: Aprendizado de Maquina. Alta Books, 2021.',
            'MULLER, A.; GUIDO, S. Introduction to Machine Learning with Python. OReilly, 2016.',
            'BURKOV, A. The Hundred-Page Machine Learning Book. 2019.',
        ],
    },
    'Gestao de Projetos': {
        'ementa': 'Fundamentos de gestao de projetos. PMBOK. Escopo, tempo, custo e qualidade. Gestao de riscos. Gestao de stakeholders. Ferramentas de gestao. Lideranca e comunicacao.',
        'objetivos': [
            'Planejar e gerenciar projetos de software',
            'Aplicar tecnicas de gestao de escopo, tempo e custo',
            'Identificar e mitigar riscos em projetos',
            'Desenvolver habilidades de lideranca e comunicacao',
        ],
        'topicos': [
            'Unidade 1: Fundamentos - projeto, programa, portfolio, PMO',
            'Unidade 2: PMBOK - areas de conhecimento e grupos de processos',
            'Unidade 3: Gestao de escopo - WBS, requisitos, controle de mudancas',
            'Unidade 4: Gestao de tempo - cronograma, caminho critico, Gantt',
            'Unidade 5: Gestao de custos - orcamento, valor agregado (EVM)',
            'Unidade 6: Gestao de riscos - identificacao, analise, resposta',
            'Unidade 7: Gestao de stakeholders e comunicacao',
            'Unidade 8: Lideranca, negociacao e resolucao de conflitos',
        ],
        'bibliografia': [
            'PMI. Guia PMBOK. Project Management Institute, 2021.',
            'VARGAS, R. Gerenciamento de Projetos. Brasport, 2018.',
            'KERZNER, H. Gestao de Projetos: As Melhores Praticas. Bookman, 2017.',
        ],
    },
    'UX/UI Design': {
        'ementa': 'Fundamentos de UX. Pesquisa com usuarios. Arquitetura de informacao. Wireframes e prototipos. Design de interfaces (UI). Design systems. Testes de usabilidade. Acessibilidade.',
        'objetivos': [
            'Aplicar metodologias de UX no design de produtos digitais',
            'Criar wireframes e prototipos interativos',
            'Projetar interfaces acessiveis e usaveis',
            'Conduzir testes de usabilidade e iterar com base em feedback',
        ],
        'topicos': [
            'Unidade 1: Fundamentos de UX - design centrado no usuario',
            'Unidade 2: Pesquisa com usuarios - entrevistas, personas, jornada',
            'Unidade 3: Arquitetura de informacao e card sorting',
            'Unidade 4: Wireframes e prototipos de baixa fidelidade',
            'Unidade 5: UI Design - tipografia, cores, grid, componentes',
            'Unidade 6: Prototipos de alta fidelidade com Figma',
            'Unidade 7: Design systems e bibliotecas de componentes',
            'Unidade 8: Testes de usabilidade e acessibilidade (WCAG)',
        ],
        'bibliografia': [
            'NORMAN, D. O Design do Dia a Dia. Rocco, 2006.',
            'KRUG, S. Nao Me Faca Pensar. Alta Books, 2014.',
            'TEIXEIRA, F. Introducao e Boas Praticas em UX Design. Casa do Codigo, 2014.',
        ],
    },
    'Estagio Supervisionado II': {
        'ementa': 'Continuacao do estagio supervisionado. Aprofundamento das atividades profissionais. Projeto aplicado na empresa. Relatorio final detalhado. Apresentacao dos resultados.',
        'objetivos': [
            'Aprofundar a experiencia profissional iniciada no Estagio I',
            'Desenvolver um projeto aplicado na empresa de estagio',
            'Elaborar relatorio final com analise critica dos resultados',
            'Apresentar contribuicoes e aprendizados do estagio',
        ],
        'topicos': [
            'Unidade 1: Revisao do plano de estagio e objetivos do semestre',
            'Unidade 2: Definicao do projeto aplicado',
            'Unidade 3: Desenvolvimento do projeto - fase 1',
            'Unidade 4: Desenvolvimento do projeto - fase 2',
            'Unidade 5: Acompanhamento e ajustes com orientador',
            'Unidade 6: Resultados e metricas do projeto',
            'Unidade 7: Relatorio final - metodologia, resultados, conclusoes',
            'Unidade 8: Apresentacao final e avaliacao do estagio',
        ],
        'bibliografia': [
            'BIANCHI, A. Manual de Orientacao: Estagio Supervisionado. Cengage, 2011.',
            'MARCONI, M.; LAKATOS, E. Metodologia do Trabalho Cientifico. Atlas, 2017.',
            'SEVERINO, A. Metodologia do Trabalho Cientifico. Cortez, 2016.',
        ],
    },
    'Computacao em Nuvem Avancada': {
        'ementa': 'Arquiteturas cloud-native. Serverless (AWS Lambda, Azure Functions). Containers em producao. Multi-cloud e hybrid cloud. FinOps. Well-Architected Framework. Certificacoes cloud.',
        'objetivos': [
            'Projetar arquiteturas cloud-native escalaveis',
            'Implementar solucoes serverless e event-driven',
            'Aplicar praticas de FinOps e otimizacao de custos',
            'Compreender o Well-Architected Framework da AWS',
        ],
        'topicos': [
            'Unidade 1: Cloud-native - 12-factor apps, microservices, containers',
            'Unidade 2: Serverless - AWS Lambda, API Gateway, Step Functions',
            'Unidade 3: Servicos gerenciados - RDS, DynamoDB, S3, SQS, SNS',
            'Unidade 4: Arquiteturas event-driven e streaming (Kinesis, EventBridge)',
            'Unidade 5: Multi-cloud e hybrid cloud - estrategias e ferramentas',
            'Unidade 6: FinOps - otimizacao de custos, reserved instances, spot',
            'Unidade 7: Well-Architected Framework - 6 pilares',
            'Unidade 8: Preparacao para certificacoes (AWS SAA, Azure AZ-900)',
        ],
        'bibliografia': [
            'AMAZON WEB SERVICES. AWS Well-Architected Framework. aws.amazon.com, 2024.',
            'WITTIG, M.; WITTIG, A. Amazon Web Services in Action. Manning, 2018.',
            'BASS, L. et al. DevOps: A Software Architects Perspective. Addison-Wesley, 2015.',
        ],
    },
    'Big Data': {
        'ementa': 'Ecossistema Big Data. Hadoop e MapReduce. Apache Spark. Data lakes. ETL e pipelines de dados. Streaming de dados. Visualizacao de dados. Governanca de dados.',
        'objetivos': [
            'Compreender o ecossistema e tecnologias de Big Data',
            'Processar grandes volumes de dados com Spark',
            'Projetar pipelines de dados e data lakes',
            'Aplicar tecnicas de visualizacao e governanca de dados',
        ],
        'topicos': [
            'Unidade 1: Fundamentos de Big Data - 5 Vs, ecossistema',
            'Unidade 2: Hadoop - HDFS, MapReduce, YARN',
            'Unidade 3: Apache Spark - RDDs, DataFrames, SparkSQL',
            'Unidade 4: Data lakes - arquitetura, S3, Delta Lake',
            'Unidade 5: ETL e pipelines de dados - Airflow, Glue',
            'Unidade 6: Streaming de dados - Kafka, Spark Streaming, Kinesis',
            'Unidade 7: Visualizacao de dados - Tableau, Power BI, Matplotlib',
            'Unidade 8: Governanca de dados - qualidade, catalogo, linhagem',
        ],
        'bibliografia': [
            'WHITE, T. Hadoop: The Definitive Guide. OReilly, 2015.',
            'CHAMBERS, B.; ZAHARIA, M. Spark: The Definitive Guide. OReilly, 2018.',
            'KLEPPMANN, M. Designing Data-Intensive Applications. OReilly, 2017.',
        ],
    },
    'Empreendedorismo Digital': {
        'ementa': 'Modelos de negocio digitais. Lean Startup. MVP e validacao. Marketing digital. Growth hacking. Financiamento (bootstrapping, investidores, venture capital). Pitch e apresentacao.',
        'objetivos': [
            'Desenvolver mentalidade empreendedora no contexto digital',
            'Criar e validar modelos de negocio usando Lean Startup',
            'Aplicar estrategias de marketing digital e growth',
            'Elaborar pitch e buscar financiamento para startups',
        ],
        'topicos': [
            'Unidade 1: Empreendedorismo digital - ecossistema de startups',
            'Unidade 2: Modelos de negocio - Canvas, SaaS, marketplace, freemium',
            'Unidade 3: Lean Startup - build-measure-learn, pivotar',
            'Unidade 4: MVP - tipos, validacao, metricas',
            'Unidade 5: Marketing digital - SEO, SEM, redes sociais, conteudo',
            'Unidade 6: Growth hacking - aquisicao, ativacao, retencao, receita',
            'Unidade 7: Financiamento - bootstrapping, anjos, seed, Series A',
            'Unidade 8: Pitch - storytelling, deck, apresentacao para investidores',
        ],
        'bibliografia': [
            'RIES, E. A Startup Enxuta. Leya, 2012.',
            'OSTERWALDER, A. Business Model Generation. Alta Books, 2011.',
            'BLANK, S. Startup: Manual do Empreendedor. Alta Books, 2014.',
        ],
    },
    'Etica em TI': {
        'ementa': 'Etica profissional em tecnologia. Privacidade e protecao de dados. LGPD e GDPR. Propriedade intelectual e software livre. Impacto social da tecnologia. Responsabilidade digital. Vies algoritmico.',
        'objetivos': [
            'Refletir sobre questoes eticas no desenvolvimento de tecnologia',
            'Compreender legislacao de protecao de dados (LGPD, GDPR)',
            'Analisar impactos sociais e ambientais da tecnologia',
            'Aplicar principios eticos no exercicio profissional',
        ],
        'topicos': [
            'Unidade 1: Etica - conceitos fundamentais e etica profissional',
            'Unidade 2: Privacidade digital e vigilancia',
            'Unidade 3: LGPD - principios, bases legais, direitos dos titulares',
            'Unidade 4: GDPR e regulamentacoes internacionais',
            'Unidade 5: Propriedade intelectual - copyright, patentes, software livre',
            'Unidade 6: Vies algoritmico e discriminacao em IA',
            'Unidade 7: Impacto social - automacao, emprego, inclusao digital',
            'Unidade 8: Sustentabilidade digital e responsabilidade corporativa',
        ],
        'bibliografia': [
            'PINHEIRO, P. Direito Digital. Saraiva, 2021.',
            'DONEDA, D. Da Privacidade a Protecao de Dados Pessoais. RT, 2019.',
            'ONEIL, C. Algoritmos de Destruicao em Massa. Rua do Sabao, 2020.',
        ],
    },
    'TCC I': {
        'ementa': 'Metodologia de pesquisa cientifica. Definicao do tema e problema de pesquisa. Revisao bibliografica. Elaboracao do projeto de TCC. Normas ABNT. Orientacao academica.',
        'objetivos': [
            'Definir tema e problema de pesquisa para o TCC',
            'Realizar revisao bibliografica sistematica',
            'Elaborar projeto de pesquisa seguindo normas academicas',
            'Desenvolver habilidades de escrita cientifica',
        ],
        'topicos': [
            'Unidade 1: Metodologia cientifica - tipos de pesquisa',
            'Unidade 2: Escolha do tema e definicao do problema',
            'Unidade 3: Revisao bibliografica - busca, selecao, fichamento',
            'Unidade 4: Referencial teorico e estado da arte',
            'Unidade 5: Metodologia - abordagem, procedimentos, instrumentos',
            'Unidade 6: Cronograma e plano de trabalho',
            'Unidade 7: Redacao do projeto - introducao, objetivos, justificativa',
            'Unidade 8: Apresentacao do projeto para banca de qualificacao',
        ],
        'bibliografia': [
            'GIL, A. Como Elaborar Projetos de Pesquisa. Atlas, 2019.',
            'MARCONI, M.; LAKATOS, E. Fundamentos de Metodologia Cientifica. Atlas, 2017.',
            'WAZLAWICK, R. Metodologia de Pesquisa para Ciencia da Computacao. Elsevier, 2014.',
        ],
    },
    'IoT e Sistemas Embarcados': {
        'ementa': 'Internet das Coisas - conceitos e arquitetura. Sensores e atuadores. Protocolos IoT (MQTT, CoAP). Plataformas IoT (AWS IoT, Azure IoT). Edge computing. Sistemas embarcados (Arduino, Raspberry Pi).',
        'objetivos': [
            'Compreender a arquitetura e protocolos de IoT',
            'Desenvolver projetos com Arduino e Raspberry Pi',
            'Integrar dispositivos IoT com plataformas cloud',
            'Aplicar conceitos de edge computing',
        ],
        'topicos': [
            'Unidade 1: IoT - conceitos, arquitetura, aplicacoes',
            'Unidade 2: Sensores, atuadores e microcontroladores',
            'Unidade 3: Arduino - programacao, GPIO, comunicacao serial',
            'Unidade 4: Raspberry Pi - Linux embarcado, GPIO, Python',
            'Unidade 5: Protocolos IoT - MQTT, CoAP, HTTP, WebSocket',
            'Unidade 6: Plataformas IoT - AWS IoT Core, Azure IoT Hub',
            'Unidade 7: Edge computing e fog computing',
            'Unidade 8: Projeto IoT integrado - sensores + cloud + dashboard',
        ],
        'bibliografia': [
            'MCEWAN, A.; CASSIMALLY, H. Designing the Internet of Things. Wiley, 2014.',
            'MONK, S. Programacao com Arduino. Bookman, 2017.',
            'AMAZON WEB SERVICES. AWS IoT Developer Guide. docs.aws.amazon.com, 2024.',
        ],
    },
    'Blockchain': {
        'ementa': 'Fundamentos de blockchain. Criptografia aplicada. Bitcoin e criptomoedas. Ethereum e smart contracts. Solidity. DeFi e NFTs. Aplicacoes empresariais. Web3.',
        'objetivos': [
            'Compreender os fundamentos tecnologicos de blockchain',
            'Desenvolver smart contracts em Solidity',
            'Analisar aplicacoes de blockchain alem de criptomoedas',
            'Avaliar casos de uso empresariais para blockchain',
        ],
        'topicos': [
            'Unidade 1: Fundamentos - hash, merkle tree, consenso distribuido',
            'Unidade 2: Bitcoin - mineracao, transacoes, wallets',
            'Unidade 3: Ethereum - EVM, gas, contas, transacoes',
            'Unidade 4: Solidity - tipos, funcoes, modificadores, eventos',
            'Unidade 5: Smart contracts - padroes, seguranca, auditoria',
            'Unidade 6: DeFi - DEX, lending, stablecoins, yield farming',
            'Unidade 7: NFTs - ERC-721, ERC-1155, marketplaces',
            'Unidade 8: Blockchain empresarial - Hyperledger, supply chain, identidade',
        ],
        'bibliografia': [
            'ANTONOPOULOS, A. Mastering Bitcoin. OReilly, 2017.',
            'ANTONOPOULOS, A.; WOOD, G. Mastering Ethereum. OReilly, 2018.',
            'TAPSCOTT, D.; TAPSCOTT, A. Blockchain Revolution. Senai-SP, 2016.',
        ],
    },
    'Inovacao Tecnologica': {
        'ementa': 'Gestao da inovacao. Design Thinking. Tendencias tecnologicas. Transformacao digital. Inovacao aberta. Propriedade intelectual. Ecossistemas de inovacao. Futuro do trabalho.',
        'objetivos': [
            'Aplicar metodologias de inovacao em contextos tecnologicos',
            'Analisar tendencias e seu impacto nos negocios',
            'Desenvolver projetos inovadores usando Design Thinking',
            'Compreender ecossistemas de inovacao e propriedade intelectual',
        ],
        'topicos': [
            'Unidade 1: Inovacao - tipos, modelos, ciclo de vida',
            'Unidade 2: Design Thinking - empatia, definicao, ideacao, prototipo, teste',
            'Unidade 3: Tendencias - IA generativa, quantum computing, metaverso',
            'Unidade 4: Transformacao digital - estrategia, cultura, tecnologia',
            'Unidade 5: Inovacao aberta - hackathons, labs, parcerias',
            'Unidade 6: Propriedade intelectual - patentes de software, trade secrets',
            'Unidade 7: Ecossistemas de inovacao - incubadoras, aceleradoras, hubs',
            'Unidade 8: Futuro do trabalho - automacao, novas profissoes, lifelong learning',
        ],
        'bibliografia': [
            'BROWN, T. Design Thinking. Alta Books, 2010.',
            'CHRISTENSEN, C. O Dilema da Inovacao. M.Books, 2012.',
            'SCHWAB, K. A Quarta Revolucao Industrial. Edipro, 2016.',
        ],
    },
    'TCC II': {
        'ementa': 'Desenvolvimento do trabalho de conclusao de curso. Implementacao do projeto. Coleta e analise de dados. Redacao da monografia. Defesa perante banca examinadora.',
        'objetivos': [
            'Desenvolver e implementar o projeto definido no TCC I',
            'Coletar e analisar dados conforme metodologia proposta',
            'Redigir monografia completa seguindo normas academicas',
            'Defender o trabalho perante banca examinadora',
        ],
        'topicos': [
            'Unidade 1: Revisao do projeto e ajustes pos-qualificacao',
            'Unidade 2: Implementacao - desenvolvimento do sistema/pesquisa',
            'Unidade 3: Implementacao - testes e validacao',
            'Unidade 4: Coleta de dados e experimentos',
            'Unidade 5: Analise de resultados e discussao',
            'Unidade 6: Redacao - capitulos de resultados e conclusao',
            'Unidade 7: Revisao final e formatacao ABNT',
            'Unidade 8: Defesa do TCC perante banca examinadora',
        ],
        'bibliografia': [
            'GIL, A. Como Elaborar Projetos de Pesquisa. Atlas, 2019.',
            'WAZLAWICK, R. Metodologia de Pesquisa para Ciencia da Computacao. Elsevier, 2014.',
            'ASSOCIACAO BRASILEIRA DE NORMAS TECNICAS. NBR 14724. ABNT, 2011.',
        ],
    },
    'Projeto Final': {
        'ementa': 'Projeto integrador final do curso. Desenvolvimento de sistema completo. Aplicacao de todas as competencias adquiridas. Trabalho em equipe. Apresentacao publica. Portfolio profissional.',
        'objetivos': [
            'Desenvolver um sistema completo integrando todas as competencias do curso',
            'Trabalhar em equipe simulando ambiente profissional real',
            'Aplicar boas praticas de engenharia de software end-to-end',
            'Construir portfolio profissional com o projeto desenvolvido',
        ],
        'topicos': [
            'Unidade 1: Definicao do projeto e formacao de equipes',
            'Unidade 2: Arquitetura e design do sistema',
            'Unidade 3: Sprint 1 - Backend e infraestrutura',
            'Unidade 4: Sprint 2 - Frontend e integracao',
            'Unidade 5: Sprint 3 - Testes, seguranca e performance',
            'Unidade 6: Sprint 4 - Deploy, CI/CD e monitoramento',
            'Unidade 7: Documentacao final e video de demonstracao',
            'Unidade 8: Apresentacao publica e avaliacao final',
        ],
        'bibliografia': [
            'MARTIN, R. Codigo Limpo. Alta Books, 2009.',
            'MARTIN, R. Arquitetura Limpa. Alta Books, 2019.',
            'HUMBLE, J.; FARLEY, D. Entrega Continua. Bookman, 2014.',
        ],
    },
}


# ============================================================
# Conteudo para cursos de extensao
# ============================================================
CONTEUDO_EXTENSAO = {
    'ext-ia-aplicada': {
        'ementa': 'Fundamentos de inteligencia artificial. Aprendizado de maquina supervisionado e nao-supervisionado. Redes neurais e deep learning. Processamento de linguagem natural. Visao computacional. Aplicacoes praticas com ChatGPT e APIs de IA. Projetos hands-on.',
        'objetivos': [
            'Compreender os fundamentos de IA e aprendizado de maquina',
            'Aplicar modelos de IA em problemas reais do dia a dia',
            'Utilizar APIs de IA generativa (ChatGPT, DALL-E)',
            'Desenvolver projetos praticos com visao computacional e NLP',
        ],
        'topicos': [
            'Modulo 1: Fundamentos de IA - historia, tipos, aplicacoes',
            'Modulo 2: Aprendizado de maquina - regressao, classificacao',
            'Modulo 3: Redes neurais e deep learning basico',
            'Modulo 4: NLP e chatbots com LLMs',
            'Modulo 5: Visao computacional - deteccao de objetos',
            'Modulo 6: Projeto final - aplicacao de IA em caso real',
        ],
        'bibliografia': [
            'GERON, A. Maos a Obra: Aprendizado de Maquina. Alta Books, 2021.',
            'RUSSELL, S.; NORVIG, P. Inteligencia Artificial. Elsevier, 2022.',
        ],
    },
    'ext-cybersecurity': {
        'ementa': 'Fundamentos de seguranca cibernetica. Ameacas e vulnerabilidades. Pentest e ethical hacking. Seguranca de redes e aplicacoes. Criptografia. Resposta a incidentes. Preparatorio CompTIA Security+.',
        'objetivos': [
            'Identificar e mitigar ameacas ciberneticas',
            'Realizar testes de penetracao basicos',
            'Aplicar praticas de seguranca em redes e aplicacoes',
            'Preparar-se para a certificacao CompTIA Security+',
        ],
        'topicos': [
            'Modulo 1: Fundamentos de cybersecurity - CIA, ameacas, riscos',
            'Modulo 2: Seguranca de redes - firewalls, IDS/IPS, VPN',
            'Modulo 3: Pentest - metodologia, Nmap, Burp Suite',
            'Modulo 4: Seguranca de aplicacoes web - OWASP Top 10',
            'Modulo 5: Criptografia e gestao de identidade',
            'Modulo 6: Resposta a incidentes e forense digital',
        ],
        'bibliografia': [
            'STALLINGS, W. Criptografia e Seguranca de Redes. Pearson, 2015.',
            'OWASP FOUNDATION. OWASP Top 10. owasp.org, 2021.',
        ],
    },
    'ext-data-science': {
        'ementa': 'Fundamentos de data science. Python para analise de dados. Pandas e NumPy. Visualizacao de dados. Machine learning com Scikit-learn. Projetos com dados reais. Storytelling com dados.',
        'objetivos': [
            'Dominar ferramentas Python para analise de dados',
            'Realizar analise exploratoria e visualizacao de dados',
            'Aplicar algoritmos de machine learning com Scikit-learn',
            'Comunicar insights atraves de storytelling com dados',
        ],
        'topicos': [
            'Modulo 1: Python para data science - NumPy, Pandas',
            'Modulo 2: Analise exploratoria de dados (EDA)',
            'Modulo 3: Visualizacao - Matplotlib, Seaborn, Plotly',
            'Modulo 4: Machine learning - regressao e classificacao',
            'Modulo 5: Feature engineering e avaliacao de modelos',
            'Modulo 6: Projeto final com dados reais e storytelling',
        ],
        'bibliografia': [
            'MCKINNEY, W. Python para Analise de Dados. Novatec, 2019.',
            'GERON, A. Maos a Obra: Aprendizado de Maquina. Alta Books, 2021.',
        ],
    },
    'ext-cloud-aws': {
        'ementa': 'Fundamentos de cloud computing. Servicos AWS essenciais (EC2, S3, RDS, Lambda). Arquitetura cloud. Seguranca e IAM. Monitoramento. Preparatorio AWS Solutions Architect Associate.',
        'objetivos': [
            'Compreender os fundamentos de computacao em nuvem',
            'Utilizar servicos AWS essenciais na pratica',
            'Projetar arquiteturas cloud seguras e escalaveis',
            'Preparar-se para a certificacao AWS SAA',
        ],
        'topicos': [
            'Modulo 1: Cloud computing - conceitos, modelos, AWS Global Infrastructure',
            'Modulo 2: Computacao - EC2, Lambda, ECS, Auto Scaling',
            'Modulo 3: Armazenamento - S3, EBS, EFS, Glacier',
            'Modulo 4: Banco de dados - RDS, DynamoDB, ElastiCache',
            'Modulo 5: Redes e seguranca - VPC, IAM, Security Groups',
            'Modulo 6: Arquitetura - Well-Architected, alta disponibilidade, custos',
        ],
        'bibliografia': [
            'AMAZON WEB SERVICES. AWS Well-Architected Framework. aws.amazon.com, 2024.',
            'WITTIG, M.; WITTIG, A. Amazon Web Services in Action. Manning, 2018.',
        ],
    },
    'ext-ux-design': {
        'ementa': 'Fundamentos de UX/UI. Pesquisa com usuarios. Wireframes e prototipos. Design de interfaces com Figma. Design systems. Testes de usabilidade. Portfolio profissional.',
        'objetivos': [
            'Aplicar metodologias de UX no design de produtos digitais',
            'Criar prototipos interativos com Figma',
            'Conduzir pesquisas e testes de usabilidade',
            'Construir portfolio profissional de UX/UI',
        ],
        'topicos': [
            'Modulo 1: Fundamentos de UX - design centrado no usuario',
            'Modulo 2: Pesquisa - entrevistas, personas, jornada do usuario',
            'Modulo 3: Wireframes e prototipos de baixa fidelidade',
            'Modulo 4: UI Design com Figma - componentes, auto layout',
            'Modulo 5: Design systems e acessibilidade',
            'Modulo 6: Testes de usabilidade e portfolio',
        ],
        'bibliografia': [
            'NORMAN, D. O Design do Dia a Dia. Rocco, 2006.',
            'KRUG, S. Nao Me Faca Pensar. Alta Books, 2014.',
        ],
    },
    'ext-gestao-projetos': {
        'ementa': 'Fundamentos de gestao de projetos. Scrum e Kanban. Ferramentas (Jira, Trello). Metricas ageis. Gestao de stakeholders. Preparatorio PSM I.',
        'objetivos': [
            'Dominar frameworks ageis (Scrum e Kanban)',
            'Utilizar ferramentas de gestao de projetos',
            'Aplicar metricas ageis para melhoria continua',
            'Preparar-se para a certificacao PSM I',
        ],
        'topicos': [
            'Modulo 1: Fundamentos de gestao de projetos e Manifesto Agil',
            'Modulo 2: Scrum - papeis, eventos, artefatos',
            'Modulo 3: Kanban - principios, quadro, WIP limits',
            'Modulo 4: Ferramentas - Jira, Trello, Confluence',
            'Modulo 5: Metricas ageis - velocity, burndown, lead time',
            'Modulo 6: Simulado PSM I e revisao',
        ],
        'bibliografia': [
            'SCHWABER, K.; SUTHERLAND, J. O Guia do Scrum. scrumguides.org, 2020.',
            'ANDERSON, D. Kanban. Blue Hole Press, 2010.',
        ],
    },
    'ext-marketing-digital': {
        'ementa': 'Fundamentos de marketing digital. Google Ads e SEO. Redes sociais e conteudo. Email marketing. Analytics e metricas. Growth hacking.',
        'objetivos': [
            'Planejar e executar estrategias de marketing digital',
            'Criar campanhas em Google Ads e redes sociais',
            'Analisar metricas e otimizar resultados',
            'Aplicar tecnicas de growth hacking',
        ],
        'topicos': [
            'Modulo 1: Fundamentos de marketing digital e funil de vendas',
            'Modulo 2: SEO - on-page, off-page, tecnico',
            'Modulo 3: Google Ads - pesquisa, display, remarketing',
            'Modulo 4: Redes sociais - estrategia, conteudo, anuncios',
            'Modulo 5: Email marketing e automacao',
            'Modulo 6: Analytics, metricas e growth hacking',
        ],
        'bibliografia': [
            'KOTLER, P. Marketing 5.0. Sextante, 2021.',
            'ELLIS, S.; BROWN, M. Se Manda! Hacking Growth. Alta Books, 2017.',
        ],
    },
    'ext-devops': {
        'ementa': 'Cultura DevOps. Docker e containers. Kubernetes. CI/CD com GitHub Actions e Jenkins. Infraestrutura como codigo com Terraform. Monitoramento.',
        'objetivos': [
            'Implementar pipelines de CI/CD automatizados',
            'Utilizar Docker e Kubernetes em ambientes de producao',
            'Provisionar infraestrutura como codigo com Terraform',
            'Monitorar aplicacoes em producao',
        ],
        'topicos': [
            'Modulo 1: Cultura DevOps - principios e praticas',
            'Modulo 2: Docker - imagens, containers, Dockerfile, compose',
            'Modulo 3: Kubernetes - pods, services, deployments',
            'Modulo 4: CI/CD - GitHub Actions, Jenkins, GitLab CI',
            'Modulo 5: Terraform - providers, resources, modules',
            'Modulo 6: Monitoramento - Prometheus, Grafana, alertas',
        ],
        'bibliografia': [
            'KIM, G. et al. O Projeto Phoenix. Alta Books, 2016.',
            'MORRIS, K. Infrastructure as Code. OReilly, 2020.',
        ],
    },
    'ext-blockchain': {
        'ementa': 'Fundamentos de blockchain. Bitcoin e criptomoedas. Ethereum e smart contracts. Solidity. DeFi e NFTs. Aplicacoes empresariais.',
        'objetivos': [
            'Compreender os fundamentos de blockchain',
            'Desenvolver smart contracts em Solidity',
            'Analisar aplicacoes de DeFi e NFTs',
            'Avaliar casos de uso empresariais',
        ],
        'topicos': [
            'Modulo 1: Fundamentos - hash, consenso, blocos',
            'Modulo 2: Bitcoin - mineracao, transacoes, wallets',
            'Modulo 3: Ethereum e smart contracts',
            'Modulo 4: Solidity - desenvolvimento de contratos',
            'Modulo 5: DeFi - DEX, lending, yield farming',
            'Modulo 6: NFTs e aplicacoes empresariais',
        ],
        'bibliografia': [
            'ANTONOPOULOS, A. Mastering Bitcoin. OReilly, 2017.',
            'ANTONOPOULOS, A.; WOOD, G. Mastering Ethereum. OReilly, 2018.',
        ],
    },
    'ext-lideranca': {
        'ementa': 'Fundamentos de lideranca. Estilos de lideranca. Coaching e mentoring. Gestao de conflitos. Feedback eficaz. Lideranca situacional. Inteligencia emocional.',
        'objetivos': [
            'Desenvolver competencias de lideranca',
            'Aplicar tecnicas de coaching e feedback',
            'Gerenciar conflitos e equipes diversas',
            'Praticar lideranca situacional',
        ],
        'topicos': [
            'Modulo 1: Fundamentos de lideranca e autoconhecimento',
            'Modulo 2: Estilos de lideranca e lideranca situacional',
            'Modulo 3: Coaching e mentoring',
            'Modulo 4: Comunicacao e feedback eficaz',
            'Modulo 5: Gestao de conflitos e negociacao',
            'Modulo 6: Inteligencia emocional e resiliencia',
        ],
        'bibliografia': [
            'GOLEMAN, D. Inteligencia Emocional. Objetiva, 2012.',
            'BLANCHARD, K. Lideranca de Alto Nivel. Bookman, 2019.',
        ],
    },
    'ext-saude-mental': {
        'ementa': 'Saude mental no ambiente de trabalho. Burnout e estresse. Ansiedade e depressao. Mindfulness e meditacao. Qualidade de vida. Programas de bem-estar corporativo.',
        'objetivos': [
            'Identificar sinais de burnout e estresse no trabalho',
            'Aplicar tecnicas de mindfulness e gestao emocional',
            'Promover qualidade de vida no ambiente corporativo',
            'Desenvolver programas de bem-estar organizacional',
        ],
        'topicos': [
            'Modulo 1: Saude mental - conceitos e importancia no trabalho',
            'Modulo 2: Burnout - identificacao, prevencao, tratamento',
            'Modulo 3: Ansiedade e estresse - tecnicas de manejo',
            'Modulo 4: Mindfulness e meditacao na pratica',
            'Modulo 5: Qualidade de vida e equilibrio trabalho-vida',
            'Modulo 6: Programas de bem-estar corporativo',
        ],
        'bibliografia': [
            'MASLACH, C.; LEITER, M. The Truth About Burnout. Jossey-Bass, 2008.',
            'KABAT-ZINN, J. Atencao Plena para Iniciantes. Sextante, 2017.',
        ],
    },
    'ext-primeiros-socorros': {
        'ementa': 'Primeiros socorros basicos. Suporte basico de vida (BLS). Parada cardiorrespiratoria. Hemorragias e fraturas. Queimaduras e intoxicacoes. Emergencias clinicas.',
        'objetivos': [
            'Prestar primeiros socorros em situacoes de emergencia',
            'Realizar suporte basico de vida (BLS)',
            'Identificar e agir em diferentes tipos de emergencia',
            'Obter certificado de socorrista',
        ],
        'topicos': [
            'Modulo 1: Fundamentos de primeiros socorros e avaliacao da cena',
            'Modulo 2: Suporte basico de vida - RCP e DEA',
            'Modulo 3: Hemorragias, fraturas e imobilizacao',
            'Modulo 4: Queimaduras, intoxicacoes e picadas',
            'Modulo 5: Emergencias clinicas - desmaio, convulsao, AVC',
            'Modulo 6: Pratica em manequins e simulacoes',
        ],
        'bibliografia': [
            'AMERICAN HEART ASSOCIATION. BLS Provider Manual. AHA, 2020.',
            'BRASIL. Manual de Primeiros Socorros. Ministerio da Saude, 2003.',
        ],
    },
    'ext-nutricao-esportiva': {
        'ementa': 'Fundamentos de nutricao esportiva. Macronutrientes e micronutrientes. Suplementacao. Periodizacao nutricional. Composicao corporal. Nutricao para diferentes modalidades.',
        'objetivos': [
            'Compreender os fundamentos da nutricao esportiva',
            'Aplicar estrategias de suplementacao adequadas',
            'Planejar periodizacao nutricional para atletas',
            'Avaliar composicao corporal e necessidades nutricionais',
        ],
        'topicos': [
            'Modulo 1: Fundamentos de nutricao - macro e micronutrientes',
            'Modulo 2: Metabolismo energetico e exercicio',
            'Modulo 3: Suplementacao - whey, creatina, cafeina, BCAA',
            'Modulo 4: Periodizacao nutricional e timing de nutrientes',
            'Modulo 5: Composicao corporal - avaliacao e estrategias',
            'Modulo 6: Nutricao para diferentes modalidades esportivas',
        ],
        'bibliografia': [
            'MCARDLE, W. Fisiologia do Exercicio. Guanabara Koogan, 2016.',
            'KLEINER, S. Nutricao para o Treinamento de Forca. Manole, 2015.',
        ],
    },
    'ext-direito-digital': {
        'ementa': 'Direito digital e internet. LGPD - Lei Geral de Protecao de Dados. Crimes digitais. Contratos eletronicos. Marco Civil da Internet. Propriedade intelectual digital.',
        'objetivos': [
            'Compreender o marco regulatorio do direito digital',
            'Aplicar a LGPD em organizacoes',
            'Identificar e prevenir crimes digitais',
            'Elaborar contratos eletronicos validos',
        ],
        'topicos': [
            'Modulo 1: Direito digital - conceitos e evolucao',
            'Modulo 2: LGPD - principios, bases legais, direitos',
            'Modulo 3: LGPD - implementacao, DPO, sancoes',
            'Modulo 4: Crimes digitais - tipificacao e investigacao',
            'Modulo 5: Contratos eletronicos e assinatura digital',
            'Modulo 6: Marco Civil da Internet e propriedade intelectual',
        ],
        'bibliografia': [
            'PINHEIRO, P. Direito Digital. Saraiva, 2021.',
            'DONEDA, D. Da Privacidade a Protecao de Dados Pessoais. RT, 2019.',
        ],
    },
    'ext-ingles-negocios': {
        'ementa': 'Business English. Vocabulario corporativo. Apresentacoes em ingles. Negociacoes e reunioes. Emails e comunicacao escrita profissional. Entrevistas de emprego em ingles.',
        'objetivos': [
            'Comunicar-se profissionalmente em ingles',
            'Realizar apresentacoes e negociacoes em ingles',
            'Redigir emails e documentos profissionais em ingles',
            'Preparar-se para entrevistas de emprego em ingles',
        ],
        'topicos': [
            'Modulo 1: Business vocabulary e expressoes corporativas',
            'Modulo 2: Emails profissionais e comunicacao escrita',
            'Modulo 3: Apresentacoes - estrutura, slides, delivery',
            'Modulo 4: Reunioes e conference calls',
            'Modulo 5: Negociacoes e persuasao em ingles',
            'Modulo 6: Entrevistas de emprego e networking',
        ],
        'bibliografia': [
            'MASCULL, B. Business Vocabulary in Use. Cambridge, 2017.',
            'POWELL, M. Presenting in English. Cengage, 2011.',
        ],
    },
}


# ============================================================
# Estilos de PDF
# ============================================================
def get_styles():
    """Retorna estilos customizados para os PDFs."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='TituloInstituicao',
        parent=styles['Title'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name='SubtituloCurso',
        parent=styles['Heading2'],
        fontSize=13,
        alignment=TA_CENTER,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name='DisciplinaTitulo',
        parent=styles['Heading1'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=12,
        spaceBefore=6,
    ))
    styles.add(ParagraphStyle(
        name='Secao',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=14,
        spaceAfter=6,
        textColor=colors.HexColor('#1a5276'),
    ))
    styles.add(ParagraphStyle(
        name='Corpo',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        leading=14,
    ))
    styles.add(ParagraphStyle(
        name='ItemLista',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        spaceAfter=3,
        leading=13,
    ))
    styles.add(ParagraphStyle(
        name='Rodape',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.grey,
    ))
    # Estilos adicionais para material de estudo
    styles.add(ParagraphStyle(
        name='MaterialTitulo',
        parent=styles['Title'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=8,
        textColor=colors.HexColor('#1a5276'),
    ))
    styles.add(ParagraphStyle(
        name='UnidadeTitulo',
        parent=styles['Heading1'],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=10,
        textColor=colors.HexColor('#1a5276'),
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name='SubSecao',
        parent=styles['Heading3'],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor('#2c3e50'),
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name='CorpoMaterial',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        leading=15,
    ))
    styles.add(ParagraphStyle(
        name='Codigo',
        fontName='Courier',
        fontSize=8,
        leading=11,
        leftIndent=20,
        rightIndent=20,
        spaceAfter=8,
        spaceBefore=4,
        backColor=colors.HexColor('#f4f4f4'),
    ))
    styles.add(ParagraphStyle(
        name='Dica',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=20,
        rightIndent=20,
        spaceAfter=8,
        spaceBefore=4,
        leading=13,
        backColor=colors.HexColor('#eaf2f8'),
        borderColor=colors.HexColor('#2980b9'),
        borderWidth=1,
        borderPadding=6,
    ))
    styles.add(ParagraphStyle(
        name='Exercicio',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        spaceAfter=6,
        leading=14,
        textColor=colors.HexColor('#1a5276'),
    ))
    styles.add(ParagraphStyle(
        name='DefinicaoTermo',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=15,
        spaceAfter=4,
        leading=13,
    ))
    return styles



def sanitize_filename(nome):
    """Converte nome de disciplina em nome de arquivo seguro."""
    nome = nome.lower()
    nome = nome.replace('(', '').replace(')', '').replace('/', '_')
    nome = re.sub(r'[^a-z0-9_]', '_', nome)
    nome = re.sub(r'_+', '_', nome).strip('_')
    return nome


def gerar_apostila_graduacao(disciplina, semestre_num, output_path, styles):
    """Gera PDF de apostila para uma disciplina de graduacao."""
    conteudo = CONTEUDO_DISCIPLINAS.get(disciplina)
    if not conteudo:
        print(f'  WARN: Sem conteudo para "{disciplina}", pulando.')
        return False

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2*cm,
        leftMargin=2.5*cm,
        rightMargin=2.5*cm,
    )

    story = []

    # Cabecalho
    story.append(Paragraph(INSTITUICAO, styles['TituloInstituicao']))
    story.append(Paragraph(f'Curso: {CURSO_GRAD}', styles['SubtituloCurso']))
    story.append(Paragraph(f'{semestre_num}o Semestre', styles['SubtituloCurso']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(disciplina, styles['DisciplinaTitulo']))
    story.append(Spacer(1, 8))

    # Linha separadora
    line_data = [[''] ]
    line_table = Table(line_data, colWidths=[doc.width])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1, colors.HexColor('#1a5276')),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 12))

    # Ementa
    story.append(Paragraph('1. EMENTA', styles['Secao']))
    story.append(Paragraph(conteudo['ementa'], styles['Corpo']))

    # Objetivos
    story.append(Paragraph('2. OBJETIVOS', styles['Secao']))
    for obj in conteudo['objetivos']:
        story.append(Paragraph(f'\u2022 {obj}', styles['ItemLista']))

    # Conteudo programatico
    story.append(Paragraph('3. CONTEUDO PROGRAMATICO', styles['Secao']))
    for topico in conteudo['topicos']:
        story.append(Paragraph(f'\u2022 {topico}', styles['ItemLista']))

    # Metodologia
    story.append(Paragraph('4. METODOLOGIA', styles['Secao']))
    story.append(Paragraph(
        'A disciplina adota uma abordagem pedagogica que combina teoria e pratica, '
        'visando o desenvolvimento integral das competencias do aluno. As estrategias '
        'de ensino-aprendizagem incluem:',
        styles['Corpo']
    ))
    metodologias = [
        'Aulas expositivas dialogadas com recursos audiovisuais e exemplos praticos',
        'Exercicios praticos em laboratorio com acompanhamento do professor',
        'Trabalhos individuais para fixacao dos conceitos teoricos',
        'Trabalhos em grupo para desenvolvimento de competencias colaborativas',
        'Seminarios e apresentacoes para desenvolvimento da comunicacao tecnica',
        'Estudos de caso baseados em cenarios reais do mercado de trabalho',
        'Projetos praticos integradores que simulam desafios profissionais',
        'Utilizacao de ambiente virtual de aprendizagem (AVA) como apoio',
        'Atividades extraclasse com leituras dirigidas e exercicios complementares',
    ]
    for m in metodologias:
        story.append(Paragraph(f'\u2022 {m}', styles['ItemLista']))

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'O professor atuara como mediador do processo de aprendizagem, estimulando '
        'a participacao ativa dos alunos e promovendo discussoes que conectem os '
        'conteudos teoricos com a pratica profissional. Serao utilizadas ferramentas '
        'e tecnologias atualizadas, alinhadas com as demandas do mercado de trabalho.',
        styles['Corpo']
    ))

    # Avaliacao
    story.append(Paragraph('5. AVALIACAO', styles['Secao']))
    story.append(Paragraph(
        'O sistema de avaliacao e composto por multiplos instrumentos que permitem '
        'aferir o desenvolvimento das competencias previstas nos objetivos da disciplina:',
        styles['Corpo']
    ))

    aval_data = [
        ['Instrumento', 'Peso', 'Descricao'],
        ['Prova 1 (P1)', '30%', 'Avaliacao individual escrita cobrindo conteudo das Unidades 1-4'],
        ['Prova 2 (P2)', '30%', 'Avaliacao individual escrita cobrindo conteudo das Unidades 5-8'],
        ['Trabalhos/Projetos', '25%', 'Atividades praticas individuais ou em grupo ao longo do semestre'],
        ['Participacao', '15%', 'Exercicios em aula, frequencia e contribuicao nas discussoes'],
    ]
    aval_table = Table(aval_data, colWidths=[3.5*cm, 1.5*cm, 10.5*cm])
    aval_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(aval_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        'Media final (MF) = P1 x 0,30 + P2 x 0,30 + Trabalhos x 0,25 + Participacao x 0,15. '
        'Criterios de aprovacao: Media final maior ou igual a 6,0 (seis) e frequencia '
        'minima de 75% das aulas ministradas. Alunos com media entre 4,0 e 5,9 terao '
        'direito a Prova Final (PF). Neste caso, a media final sera recalculada como '
        '(MF + PF) / 2, devendo atingir no minimo 5,0 para aprovacao.',
        styles['Corpo']
    ))

    # Cronograma resumido
    story.append(Paragraph('6. CRONOGRAMA RESUMIDO', styles['Secao']))
    cron_data = [['Periodo', 'Conteudo', 'Avaliacao']]
    mid = len(conteudo['topicos']) // 2
    for i, topico in enumerate(conteudo['topicos']):
        unidade = topico.split(':')[0] if ':' in topico else topico
        aval = ''
        if i == mid - 1:
            aval = 'P1'
        elif i == len(conteudo['topicos']) - 1:
            aval = 'P2'
        cron_data.append([f'Semana {(i*2)+1}-{(i*2)+2}', unidade, aval])

    cron_table = Table(cron_data, colWidths=[3*cm, 9*cm, 3.5*cm])
    cron_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(cron_table)

    # Bibliografia
    story.append(Paragraph('7. BIBLIOGRAFIA', styles['Secao']))
    story.append(Paragraph('Bibliografia basica:', styles['Corpo']))
    for ref in conteudo['bibliografia']:
        story.append(Paragraph(f'\u2022 {ref}', styles['ItemLista']))
    story.append(Spacer(1, 4))
    story.append(Paragraph('Bibliografia complementar:', styles['Corpo']))
    story.append(Paragraph(
        '\u2022 Artigos cientificos e materiais disponibilizados pelo professor no AVA.',
        styles['ItemLista']
    ))
    story.append(Paragraph(
        '\u2022 Documentacao oficial das tecnologias e ferramentas utilizadas na disciplina.',
        styles['ItemLista']
    ))
    story.append(Paragraph(
        '\u2022 Tutoriais e cursos online recomendados pelo professor.',
        styles['ItemLista']
    ))

    # Informacoes adicionais
    story.append(Paragraph('8. INFORMACOES ADICIONAIS', styles['Secao']))
    story.append(Paragraph(
        f'Disciplina: {disciplina}  |  Semestre: {semestre_num}o  |  '
        f'Curso: {CURSO_GRAD}  |  Modalidade: Presencial',
        styles['Corpo']
    ))
    story.append(Paragraph(
        'Carga horaria: 80 horas (40 encontros de 2 horas). '
        'Pre-requisitos: consultar grade curricular do curso. '
        'Horario de atendimento do professor: a definir no inicio do semestre.',
        styles['Corpo']
    ))

    # Rodape
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f'{INSTITUICAO} - {CURSO_GRAD} - Apostila de {disciplina}',
        styles['Rodape']
    ))

    doc.build(story)
    return True


def gerar_apostila_extensao(curso, output_path, styles):
    """Gera PDF de apostila para um curso de extensao."""
    curso_id = curso['curso_id']
    conteudo = CONTEUDO_EXTENSAO.get(curso_id)
    if not conteudo:
        print(f'  WARN: Sem conteudo para extensao "{curso_id}", pulando.')
        return False

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2*cm,
        leftMargin=2.5*cm,
        rightMargin=2.5*cm,
    )

    story = []

    # Cabecalho
    story.append(Paragraph(INSTITUICAO, styles['TituloInstituicao']))
    story.append(Paragraph('Curso de Extensao', styles['SubtituloCurso']))
    story.append(Spacer(1, 8))
    story.append(Paragraph(curso['nome'], styles['DisciplinaTitulo']))
    story.append(Spacer(1, 4))

    # Info do curso
    info_data = [
        ['Area:', curso['area']],
        ['Modalidade:', curso['modalidade']],
        ['Carga Horaria:', f"{curso['duracao_horas']}h"],
        ['Duracao:', f"{curso['duracao_meses']} meses"],
    ]
    info_table = Table(info_data, colWidths=[3.5*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 8))

    # Linha separadora
    line_data = [[''] ]
    line_table = Table(line_data, colWidths=[doc.width])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1, colors.HexColor('#1a5276')),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 12))

    # Ementa
    story.append(Paragraph('1. EMENTA', styles['Secao']))
    story.append(Paragraph(conteudo['ementa'], styles['Corpo']))

    # Objetivos
    story.append(Paragraph('2. OBJETIVOS', styles['Secao']))
    for obj in conteudo['objetivos']:
        story.append(Paragraph(f'\u2022 {obj}', styles['ItemLista']))

    # Conteudo programatico
    story.append(Paragraph('3. CONTEUDO PROGRAMATICO', styles['Secao']))
    for topico in conteudo['topicos']:
        story.append(Paragraph(f'\u2022 {topico}', styles['ItemLista']))

    # Metodologia
    story.append(Paragraph('4. METODOLOGIA', styles['Secao']))
    story.append(Paragraph(
        'O curso de extensao adota uma abordagem pratica e aplicada, com foco no '
        'desenvolvimento de competencias diretamente utilizaveis no mercado de trabalho. '
        'As estrategias de ensino incluem:',
        styles['Corpo']
    ))
    met_ext = [
        'Aulas online ao vivo com interacao em tempo real (ou presenciais conforme modalidade)',
        'Atividades praticas hands-on com ferramentas e tecnologias do mercado',
        'Estudos de caso baseados em cenarios reais de empresas',
        'Projetos praticos individuais e em grupo',
        'Material didatico disponivel na plataforma de ensino',
        'Forum de discussao e suporte com instrutores',
        'Gravacao das aulas para revisao posterior',
    ]
    for m in met_ext:
        story.append(Paragraph(f'\u2022 {m}', styles['ItemLista']))

    # Diferenciais
    story.append(Paragraph('5. DIFERENCIAIS DO CURSO', styles['Secao']))
    story.append(Paragraph(curso['diferenciais'], styles['Corpo']))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'Ao concluir o curso, o aluno recebera certificado de extensao emitido pela '
        f'{INSTITUICAO}, reconhecido pelo MEC, com carga horaria de {curso["duracao_horas"]} horas.',
        styles['Corpo']
    ))

    # Mercado
    story.append(Paragraph('6. MERCADO DE TRABALHO', styles['Secao']))
    story.append(Paragraph(
        f'Este curso e voltado para: {curso["mercado"]}.',
        styles['Corpo']
    ))
    story.append(Paragraph(
        'O mercado de trabalho para profissionais com essa qualificacao esta em '
        'constante crescimento, com demanda por profissionais atualizados e com '
        'competencias praticas comprovadas. A certificacao de extensao agrega valor '
        'ao curriculo e demonstra comprometimento com o desenvolvimento profissional.',
        styles['Corpo']
    ))

    # Avaliacao
    story.append(Paragraph('7. AVALIACAO', styles['Secao']))
    story.append(Paragraph(
        'O sistema de avaliacao do curso de extensao e composto por:',
        styles['Corpo']
    ))
    aval_data = [
        ['Instrumento', 'Peso', 'Descricao'],
        ['Atividades Praticas', '40%', 'Exercicios e laboratorios praticos de cada modulo'],
        ['Projeto Final', '40%', 'Projeto integrador aplicando todos os conceitos do curso'],
        ['Participacao', '20%', 'Frequencia, contribuicao em discussoes e entregas no prazo'],
    ]
    aval_table = Table(aval_data, colWidths=[3.5*cm, 1.5*cm, 10.5*cm])
    aval_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(aval_table)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'Media minima para certificacao: 7,0 (sete). Frequencia minima: 75% das aulas. '
        'Alunos que nao atingirem a media poderao realizar atividade complementar a '
        'criterio do instrutor.',
        styles['Corpo']
    ))

    # Bibliografia
    story.append(Paragraph('8. BIBLIOGRAFIA', styles['Secao']))
    story.append(Paragraph('Bibliografia basica:', styles['Corpo']))
    for ref in conteudo['bibliografia']:
        story.append(Paragraph(f'\u2022 {ref}', styles['ItemLista']))
    story.append(Spacer(1, 4))
    story.append(Paragraph('Materiais complementares:', styles['Corpo']))
    story.append(Paragraph(
        '\u2022 Documentacao oficial das ferramentas e tecnologias abordadas no curso.',
        styles['ItemLista']
    ))
    story.append(Paragraph(
        '\u2022 Artigos e tutoriais recomendados pelo instrutor na plataforma de ensino.',
        styles['ItemLista']
    ))

    # Cronograma
    story.append(Paragraph('9. CRONOGRAMA', styles['Secao']))
    weeks_per_mod = max(1, (curso['duracao_meses'] * 4) // len(conteudo['topicos']))
    cron_data = [['Periodo', 'Conteudo', 'Entrega']]
    for i, topico in enumerate(conteudo['topicos']):
        mod_name = topico.split(':')[0] if ':' in topico else topico
        sem_start = i * weeks_per_mod + 1
        sem_end = sem_start + weeks_per_mod - 1
        entrega = ''
        if i == len(conteudo['topicos']) // 2 - 1:
            entrega = 'Atividade parcial'
        elif i == len(conteudo['topicos']) - 1:
            entrega = 'Projeto final'
        cron_data.append([f'Semana {sem_start}-{sem_end}', mod_name, entrega])

    cron_table = Table(cron_data, colWidths=[3*cm, 8*cm, 4.5*cm])
    cron_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(cron_table)

    # Informacoes adicionais
    story.append(Paragraph('10. INFORMACOES ADICIONAIS', styles['Secao']))
    story.append(Paragraph(
        f'Curso: {curso["nome"]}  |  Area: {curso["area"]}  |  '
        f'Modalidade: {curso["modalidade"]}  |  Duracao: {curso["duracao_meses"]} meses',
        styles['Corpo']
    ))
    story.append(Paragraph(
        f'Carga horaria total: {curso["duracao_horas"]} horas. '
        'Pre-requisitos: nao ha pre-requisitos formais, porem recomenda-se '
        'conhecimento basico na area do curso. '
        'Inscricoes abertas no site da instituicao.',
        styles['Corpo']
    ))
    story.append(Paragraph(
        'Para mais informacoes sobre matricula, valores e datas de inicio, '
        f'entre em contato com a secretaria da {INSTITUICAO} ou acesse o site '
        'institucional. Descontos especiais para alunos e ex-alunos da instituicao.',
        styles['Corpo']
    ))

    # Rodape
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f'{INSTITUICAO} - Extensao - {curso["nome"]}',
        styles['Rodape']
    ))

    doc.build(story)
    return True


# ============================================================
# Geracao de Material de Estudo (apostilas educacionais)
# ============================================================

def _add_unit_content(story, unit_data, unit_num, styles):
    """Adiciona conteudo de uma unidade ao story do PDF."""
    story.append(Paragraph(f'Unidade {unit_num}: {unit_data["titulo"]}', styles['UnidadeTitulo']))

    # Explicacao principal
    story.append(Paragraph(unit_data['explicacao'], styles['CorpoMaterial']))

    # Definicoes e terminologia
    story.append(Paragraph('Definicoes e Terminologia', styles['SubSecao']))
    for defn in unit_data.get('definicoes', []):
        story.append(Paragraph(f'\u2022 <b>{defn.split(":")[0]}</b>:{defn.split(":", 1)[1]}' if ':' in defn else f'\u2022 {defn}', styles['DefinicaoTermo']))

    # Exemplo pratico
    story.append(Paragraph('Exemplo Pratico', styles['SubSecao']))
    exemplo = unit_data.get('exemplo', '')
    if unit_data.get('exemplo_tipo') == 'codigo':
        # Codigo formatado - escapar caracteres HTML
        code_escaped = exemplo.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        for line in code_escaped.split('\n'):
            story.append(Paragraph(line if line.strip() else '&nbsp;', styles['Codigo']))
    else:
        for para in exemplo.split('\n\n'):
            if para.strip():
                story.append(Paragraph(para.replace('\n', '<br/>'), styles['CorpoMaterial']))

    # Dica/Nota importante
    if unit_data.get('dica'):
        story.append(Spacer(1, 4))
        story.append(Paragraph(f'\u26a0 {unit_data["dica"]}', styles['Dica']))

    # Exercicios
    story.append(Paragraph('Exercicios', styles['SubSecao']))
    for i, ex in enumerate(unit_data.get('exercicios', []), 1):
        story.append(Paragraph(f'{i}. {ex}', styles['Exercicio']))

    story.append(Spacer(1, 12))


def gerar_material_graduacao(disciplina, semestre_num, output_path, styles):
    """Gera PDF de material de estudo para uma disciplina de graduacao."""
    conteudo = CONTEUDO_DISCIPLINAS.get(disciplina)
    if not conteudo:
        return False

    # Obter material detalhado ou gerar generico
    material_units = MATERIAL_DISCIPLINAS.get(disciplina)
    topicos = conteudo.get('topicos', [])

    if not material_units:
        # Gerar conteudo generico para cada topico
        material_units = []
        for i, topico in enumerate(topicos):
            unit = gerar_conteudo_unidade_generico(disciplina, topico, i, len(topicos), conteudo.get('ementa', ''))
            material_units.append(unit)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2*cm,
        leftMargin=2.5*cm,
        rightMargin=2.5*cm,
    )

    story = []

    # Capa
    story.append(Spacer(1, 3*cm))
    story.append(Paragraph(INSTITUICAO, styles['TituloInstituicao']))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f'Curso: {CURSO_GRAD}', styles['SubtituloCurso']))
    story.append(Paragraph(f'{semestre_num}o Semestre', styles['SubtituloCurso']))
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph('MATERIAL DE ESTUDO', styles['MaterialTitulo']))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(disciplina, styles['DisciplinaTitulo']))
    story.append(Spacer(1, 2*cm))

    # Linha separadora
    line_data = [[''] ]
    line_table = Table(line_data, colWidths=[doc.width])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor('#1a5276')),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 1*cm))

    story.append(Paragraph(
        f'Este material de estudo apresenta o conteudo educacional da disciplina '
        f'{disciplina}, oferecida no {semestre_num}o semestre do curso de {CURSO_GRAD}. '
        f'O material cobre os principais topicos da ementa, com explicacoes detalhadas, '
        f'exemplos praticos, definicoes importantes e exercicios para fixacao.',
        styles['CorpoMaterial']
    ))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        f'<b>Ementa:</b> {conteudo["ementa"]}',
        styles['CorpoMaterial']
    ))

    story.append(PageBreak())

    # Sumario
    story.append(Paragraph('SUMARIO', styles['Secao']))
    story.append(Spacer(1, 8))
    for i, unit in enumerate(material_units, 1):
        story.append(Paragraph(f'{i}. {unit["titulo"]}', styles['ItemLista']))
    story.append(Paragraph(f'{len(material_units) + 1}. Resumo e Revisao', styles['ItemLista']))
    story.append(PageBreak())

    # Conteudo das unidades
    for i, unit in enumerate(material_units, 1):
        _add_unit_content(story, unit, i, styles)
        # Page break a cada 2 unidades para manter ~8-15 paginas
        if i % 2 == 0 and i < len(material_units):
            story.append(PageBreak())

    # Secao de Resumo e Revisao
    story.append(PageBreak())
    story.append(Paragraph('Resumo e Revisao', styles['UnidadeTitulo']))
    story.append(Paragraph(
        f'Neste material, estudamos os principais topicos de {disciplina}. '
        f'A seguir, apresentamos um resumo dos conceitos-chave abordados em cada unidade:',
        styles['CorpoMaterial']
    ))
    story.append(Spacer(1, 8))

    for i, unit in enumerate(material_units, 1):
        story.append(Paragraph(
            f'<b>Unidade {i} - {unit["titulo"]}:</b> '
            f'{unit["explicacao"][:150].rsplit(" ", 1)[0]}...',
            styles['CorpoMaterial']
        ))

    story.append(Spacer(1, 12))
    story.append(Paragraph('Pontos-chave para revisao:', styles['SubSecao']))
    review_points = [
        f'Revise as definicoes e terminologia de cada unidade.',
        f'Refaca os exercicios propostos sem consultar o material.',
        f'Busque exemplos adicionais na bibliografia recomendada.',
        f'Relacione os conceitos de diferentes unidades entre si.',
        f'Pratique com projetos pessoais para consolidar o aprendizado.',
    ]
    for point in review_points:
        story.append(Paragraph(f'\u2022 {point}', styles['ItemLista']))

    # Bibliografia
    story.append(Spacer(1, 12))
    story.append(Paragraph('Bibliografia Recomendada', styles['SubSecao']))
    for ref in conteudo.get('bibliografia', []):
        story.append(Paragraph(f'\u2022 {ref}', styles['ItemLista']))

    # Rodape
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f'{INSTITUICAO} - {CURSO_GRAD} - Material de Estudo: {disciplina}',
        styles['Rodape']
    ))

    doc.build(story)
    return True


def gerar_material_extensao(curso, output_path, styles):
    """Gera PDF de material de estudo para um curso de extensao."""
    curso_id = curso['curso_id']
    conteudo = CONTEUDO_EXTENSAO.get(curso_id)
    if not conteudo:
        return False

    # Obter material detalhado ou gerar generico
    material_units = MATERIAL_EXTENSAO.get(curso_id)

    if not material_units:
        material_units = []
        for i, topico in enumerate(conteudo.get('topicos', [])):
            unit = gerar_conteudo_unidade_generico(curso['nome'], topico, i, len(conteudo.get('topicos', [])), conteudo.get('ementa', ''))
            material_units.append(unit)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2*cm,
        leftMargin=2.5*cm,
        rightMargin=2.5*cm,
    )

    story = []

    # Capa
    story.append(Spacer(1, 3*cm))
    story.append(Paragraph(INSTITUICAO, styles['TituloInstituicao']))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph('Curso de Extensao', styles['SubtituloCurso']))
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph('MATERIAL DE ESTUDO', styles['MaterialTitulo']))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(curso['nome'], styles['DisciplinaTitulo']))
    story.append(Spacer(1, 1*cm))

    # Info do curso
    info_data = [
        ['Area:', curso['area']],
        ['Modalidade:', curso['modalidade']],
        ['Carga Horaria:', f"{curso['duracao_horas']}h"],
        ['Duracao:', f"{curso['duracao_meses']} meses"],
    ]
    info_table = Table(info_data, colWidths=[3.5*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 1*cm))

    line_data = [[''] ]
    line_table = Table(line_data, colWidths=[doc.width])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor('#1a5276')),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph(
        f'Este material de estudo apresenta o conteudo educacional do curso de extensao '
        f'{curso["nome"]}. O material cobre os principais modulos do curso, com explicacoes '
        f'detalhadas, exemplos praticos e exercicios para fixacao do aprendizado.',
        styles['CorpoMaterial']
    ))
    story.append(Paragraph(
        f'<b>Ementa:</b> {conteudo["ementa"]}',
        styles['CorpoMaterial']
    ))

    story.append(PageBreak())

    # Sumario
    story.append(Paragraph('SUMARIO', styles['Secao']))
    story.append(Spacer(1, 8))
    for i, unit in enumerate(material_units, 1):
        story.append(Paragraph(f'{i}. {unit["titulo"]}', styles['ItemLista']))
    story.append(Paragraph(f'{len(material_units) + 1}. Resumo e Revisao', styles['ItemLista']))
    story.append(PageBreak())

    # Conteudo dos modulos
    for i, unit in enumerate(material_units, 1):
        _add_unit_content(story, unit, i, styles)
        if i % 2 == 0 and i < len(material_units):
            story.append(PageBreak())

    # Resumo
    story.append(PageBreak())
    story.append(Paragraph('Resumo e Revisao', styles['UnidadeTitulo']))
    story.append(Paragraph(
        f'Neste material, estudamos os principais topicos de {curso["nome"]}. '
        f'Revise os conceitos-chave de cada modulo:',
        styles['CorpoMaterial']
    ))
    story.append(Spacer(1, 8))

    for i, unit in enumerate(material_units, 1):
        story.append(Paragraph(
            f'<b>Modulo {i} - {unit["titulo"]}:</b> '
            f'{unit["explicacao"][:150].rsplit(" ", 1)[0]}...',
            styles['CorpoMaterial']
        ))

    story.append(Spacer(1, 12))
    story.append(Paragraph('Proximos passos:', styles['SubSecao']))
    next_steps = [
        f'Revise os exercicios de cada modulo e tente resolve-los sem consultar o material.',
        f'Aplique os conceitos em um projeto pratico pessoal.',
        f'Consulte a bibliografia recomendada para aprofundamento.',
        f'Participe dos foruns de discussao e tire duvidas com os instrutores.',
    ]
    for step in next_steps:
        story.append(Paragraph(f'\u2022 {step}', styles['ItemLista']))

    # Bibliografia
    story.append(Spacer(1, 12))
    story.append(Paragraph('Bibliografia Recomendada', styles['SubSecao']))
    for ref in conteudo.get('bibliografia', []):
        story.append(Paragraph(f'\u2022 {ref}', styles['ItemLista']))

    # Rodape
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f'{INSTITUICAO} - Extensao - Material de Estudo: {curso["nome"]}',
        styles['Rodape']
    ))

    doc.build(story)
    return True


# ============================================================
# Main
# ============================================================
def gerar_pdf_institucional(output_path, styles):
    """Gera PDF institucional sobre_instituicao.pdf com informacoes publicas da instituicao."""
    import json as _json

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2*cm,
        leftMargin=2.5*cm,
        rightMargin=2.5*cm,
    )

    story = []

    # ---- Capa / Cabecalho ----
    story.append(Paragraph(INSTITUICAO, styles['TituloInstituicao']))
    story.append(Spacer(1, 8))
    story.append(Paragraph('Guia Institucional', styles['DisciplinaTitulo']))
    story.append(Spacer(1, 8))

    # Linha separadora
    line_data = [['']]
    line_table = Table(line_data, colWidths=[doc.width])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1, colors.HexColor('#1a5276')),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 16))

    # ---- 1. Sobre a Instituicao ----
    story.append(Paragraph('1. SOBRE A INSTITUICAO', styles['Secao']))
    story.append(Paragraph(
        'A Instituicao de Ensino Demo e uma instituicao de ensino superior comprometida com a '
        'formacao integral de seus alunos, combinando excelencia academica com pratica profissional. '
        'Fundada com o proposito de transformar vidas por meio da educacao, a instituicao atua nas '
        'areas de Tecnologia, Saude, Negocios e Humanas, oferecendo cursos de graduacao e extensao '
        'reconhecidos pelo MEC.',
        styles['Corpo']
    ))

    # ---- 2. Missao, Visao e Valores ----
    story.append(Paragraph('2. MISSAO, VISAO E VALORES', styles['Secao']))

    story.append(Paragraph('<b>Missao</b>', styles['Corpo']))
    story.append(Paragraph(
        'Formar profissionais competentes e cidadaos eticos, promovendo o desenvolvimento '
        'humano e tecnologico por meio de ensino de qualidade, pesquisa aplicada e extensao '
        'comunitaria.',
        styles['Corpo']
    ))

    story.append(Paragraph('<b>Visao</b>', styles['Corpo']))
    story.append(Paragraph(
        'Ser referencia nacional em ensino superior inovador, reconhecida pela qualidade de '
        'seus egressos e pela contribuicao ao desenvolvimento da sociedade.',
        styles['Corpo']
    ))

    story.append(Paragraph('<b>Valores</b>', styles['Corpo']))
    valores = [
        'Excelencia academica e compromisso com a qualidade do ensino',
        'Inovacao e uso de tecnologias educacionais modernas',
        'Etica, transparencia e responsabilidade social',
        'Inclusao e respeito a diversidade',
        'Formacao pratica e alinhada ao mercado de trabalho',
        'Colaboracao entre alunos, professores e comunidade',
    ]
    for v in valores:
        story.append(Paragraph(f'\u2022 {v}', styles['ItemLista']))

    # ---- 3. Cursos Oferecidos ----
    story.append(Paragraph('3. CURSOS OFERECIDOS', styles['Secao']))

    story.append(Paragraph('<b>Graduacao</b>', styles['Corpo']))
    story.append(Paragraph(
        'A instituicao oferece 6 cursos de graduacao nas areas de Tecnologia, Saude, '
        'Negocios e Humanas:',
        styles['Corpo']
    ))

    cursos_grad = [
        ['Curso', 'Area', 'Modalidade', 'Duracao'],
        ['Engenharia de Software', 'Tecnologia', 'Presencial', '8 semestres'],
        ['Ciencia da Computacao', 'Tecnologia', 'Presencial', '8 semestres'],
        ['Analise e Desenv. de Sistemas', 'Tecnologia', 'EAD', '5 semestres'],
        ['Enfermagem', 'Saude', 'Presencial', '10 semestres'],
        ['Administracao', 'Negocios', 'Presencial', '8 semestres'],
        ['Direito', 'Humanas', 'Presencial', '10 semestres'],
    ]
    t_grad = Table(cursos_grad, colWidths=[doc.width * 0.35, doc.width * 0.2, doc.width * 0.2, doc.width * 0.25])
    t_grad.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_grad)
    story.append(Spacer(1, 12))

    story.append(Paragraph('<b>Extensao</b>', styles['Corpo']))
    story.append(Paragraph(
        'Sao oferecidos 15 cursos de extensao, a maioria na modalidade EAD, com duracao '
        'de 1 a 4 meses. Os cursos abrangem areas como Tecnologia, Negocios, Saude e Humanas, '
        'permitindo atualizacao profissional rapida e acessivel. Destaques:',
        styles['Corpo']
    ))

    cursos_ext_lista = [
        'Inteligencia Artificial Aplicada (60h)',
        'Cybersecurity Essentials (40h)',
        'Data Science com Python (80h)',
        'Cloud Computing com AWS (60h)',
        'UX/UI Design (50h)',
        'Gestao de Projetos e Metodologias Ageis (40h)',
        'Marketing Digital e Analytics (45h)',
        'DevOps e CI/CD (60h)',
        'Blockchain e Web3 (40h)',
        'Lideranca e Gestao de Pessoas (30h)',
        'Saude Mental no Trabalho (30h)',
        'Primeiros Socorros e Urgencias (20h)',
        'Nutricao Esportiva (40h)',
        'Direito Digital e LGPD (30h)',
        'Ingles para Negocios (60h)',
    ]
    for c in cursos_ext_lista:
        story.append(Paragraph(f'\u2022 {c}', styles['ItemLista']))

    # ---- Page break ----
    story.append(PageBreak())

    # ---- 4. Infraestrutura ----
    story.append(Paragraph('4. INFRAESTRUTURA', styles['Secao']))
    story.append(Paragraph(
        'A instituicao conta com infraestrutura moderna e completa para proporcionar a melhor '
        'experiencia de aprendizagem aos seus alunos:',
        styles['Corpo']
    ))

    story.append(Paragraph('<b>Laboratorios</b>', styles['Corpo']))
    labs = [
        'Laboratorio de Informatica com 120 estacoes de trabalho (desktops e notebooks)',
        'Laboratorio de Redes e Seguranca com equipamentos Cisco e ambientes de pentest',
        'Laboratorio de Inteligencia Artificial com GPUs dedicadas para treinamento de modelos',
        'Laboratorio de Simulacao em Saude com manequins de alta fidelidade',
        'Laboratorio de Pratica Juridica (Nucleo de Pratica Juridica)',
    ]
    for l in labs:
        story.append(Paragraph(f'\u2022 {l}', styles['ItemLista']))

    story.append(Paragraph('<b>Biblioteca</b>', styles['Corpo']))
    story.append(Paragraph(
        'Acervo com mais de 50.000 titulos fisicos e acesso a bases digitais como IEEE Xplore, '
        'ACM Digital Library, Scielo e Periodicos CAPES. Salas de estudo individual e em grupo, '
        'com horario de funcionamento estendido ate as 22h.',
        styles['Corpo']
    ))

    story.append(Paragraph('<b>Campus</b>', styles['Corpo']))
    campus = [
        'Campus principal com 25.000 m2 de area construida',
        'Auditorio com capacidade para 500 pessoas',
        'Centro de convivencia com praca de alimentacao e areas de lazer',
        'Estacionamento com 300 vagas',
        'Acessibilidade completa: rampas, elevadores, sinalizacao tatil e em Braille',
        'Wi-Fi de alta velocidade em todo o campus',
    ]
    for c in campus:
        story.append(Paragraph(f'\u2022 {c}', styles['ItemLista']))

    # ---- 5. Diferenciais ----
    story.append(Paragraph('5. DIFERENCIAIS', styles['Secao']))

    story.append(Paragraph('<b>Parcerias com Empresas</b>', styles['Corpo']))
    story.append(Paragraph(
        'A instituicao mantem parcerias estrategicas com empresas líderes de mercado, '
        'proporcionando oportunidades de estagio, projetos reais e empregabilidade. '
        'Entre os parceiros estao empresas de tecnologia, hospitais, escritorios de advocacia '
        'e consultorias de gestao.',
        styles['Corpo']
    ))

    story.append(Paragraph('<b>Projetos Praticos</b>', styles['Corpo']))
    story.append(Paragraph(
        'Desde o primeiro semestre, os alunos participam de projetos praticos que simulam '
        'desafios reais do mercado de trabalho. Projetos integradores, hackathons, empresa '
        'junior e incubadora de startups fazem parte da vivencia academica.',
        styles['Corpo']
    ))

    story.append(Paragraph('<b>Corpo Docente Qualificado</b>', styles['Corpo']))
    story.append(Paragraph(
        'O corpo docente e composto por mestres e doutores com experiencia academica e '
        'profissional. Muitos professores atuam simultaneamente no mercado, trazendo casos '
        'reais e praticas atualizadas para a sala de aula.',
        styles['Corpo']
    ))

    diferenciais_extras = [
        'Programas de monitoria e tutoria para apoio academico',
        'Nucleo de carreiras com orientacao profissional e preparacao para entrevistas',
        'Intercambio academico com universidades parceiras no exterior',
        'Certificacoes intermediarias em cursos de tecnologia',
        'Descontos e bolsas de estudo para alunos de alto desempenho',
    ]
    for d in diferenciais_extras:
        story.append(Paragraph(f'\u2022 {d}', styles['ItemLista']))

    # ---- 6. Contato e Localizacao ----
    story.append(Paragraph('6. CONTATO E LOCALIZACAO', styles['Secao']))

    contato_data = [
        ['Endereco', 'Av. da Educacao, 1000 - Centro, Sao Paulo - SP, CEP 01000-000'],
        ['Telefone', '(11) 3000-1000'],
        ['WhatsApp', '+55 11 94574-6008'],
        ['E-mail', 'contato@instituicaodemo.edu.br'],
        ['Site', 'www.instituicaodemo.edu.br'],
        ['Horario', 'Segunda a Sexta, 8h as 22h | Sabado, 8h as 13h'],
    ]
    t_contato = Table(contato_data, colWidths=[doc.width * 0.25, doc.width * 0.75])
    t_contato.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')]),
    ]))
    story.append(t_contato)
    story.append(Spacer(1, 16))

    # Rodape
    story.append(Paragraph(
        f'{INSTITUICAO} - Transformando vidas por meio da educacao',
        styles['Rodape']
    ))

    # Build PDF
    try:
        doc.build(story)
    except Exception as e:
        print(f'  ERRO ao gerar PDF institucional: {e}')
        return False

    # Gerar metadata JSON
    metadata = {
        "metadataAttributes": {
            "tipo": "publico",
            "categoria": "institucional"
        }
    }
    metadata_path = output_path + '.metadata.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        _json.dump(metadata, f, ensure_ascii=False, indent=2)

    return True


def main():
    styles = get_styles()

    total_grad_ementa = 0
    total_grad_material = 0
    total_ext_ementa = 0
    total_ext_material = 0

    # --- Graduacao: Ementas (existente) ---
    print('=== Gerando ementas de graduacao (Eng. Software) ===')
    for semestre_key, disciplinas in GRADE_CURRICULAR.items():
        semestre_num = int(semestre_key.split('_')[0])
        for disciplina in disciplinas:
            filename = sanitize_filename(disciplina) + '.pdf'
            out_dir = os.path.join(OUTPUT_DIR, 'privado', 'graduacao', CURSO_ID_GRAD)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, filename)

            ok = gerar_apostila_graduacao(disciplina, semestre_num, out_path, styles)
            if ok:
                total_grad_ementa += 1
                print(f'  [{semestre_num}o sem] {disciplina} -> {filename}')

    # --- Graduacao: Material de Estudo (NOVO) ---
    print('\n=== Gerando material de estudo de graduacao (Eng. Software) ===')
    for semestre_key, disciplinas in GRADE_CURRICULAR.items():
        semestre_num = int(semestre_key.split('_')[0])
        for disciplina in disciplinas:
            filename = sanitize_filename(disciplina) + '_material.pdf'
            out_dir = os.path.join(OUTPUT_DIR, 'privado', 'graduacao', CURSO_ID_GRAD)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, filename)

            ok = gerar_material_graduacao(disciplina, semestre_num, out_path, styles)
            if ok:
                total_grad_material += 1
                print(f'  [{semestre_num}o sem] {disciplina} -> {filename}')

    # --- Extensao: Ementas (existente) ---
    print('\n=== Gerando ementas de extensao ===')
    for curso in CURSOS_EXTENSAO:
        filename = sanitize_filename(curso['nome']) + '.pdf'
        out_dir = os.path.join(OUTPUT_DIR, 'privado', 'extensao', curso['curso_id'])
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)

        ok = gerar_apostila_extensao(curso, out_path, styles)
        if ok:
            total_ext_ementa += 1
            print(f'  {curso["nome"]} -> {curso["curso_id"]}/{filename}')

    # --- Extensao: Material de Estudo (NOVO) ---
    print('\n=== Gerando material de estudo de extensao ===')
    for curso in CURSOS_EXTENSAO:
        filename = sanitize_filename(curso['nome']) + '_material.pdf'
        out_dir = os.path.join(OUTPUT_DIR, 'privado', 'extensao', curso['curso_id'])
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)

        ok = gerar_material_extensao(curso, out_path, styles)
        if ok:
            total_ext_material += 1
            print(f'  {curso["nome"]} -> {curso["curso_id"]}/{filename}')

    # --- Institucional (publico) ---
    print('\n=== Gerando PDF institucional ===')
    total_institucional = 0
    out_dir_pub = os.path.join(OUTPUT_DIR, 'publico')
    os.makedirs(out_dir_pub, exist_ok=True)
    inst_path = os.path.join(out_dir_pub, 'sobre_instituicao.pdf')
    ok = gerar_pdf_institucional(inst_path, styles)
    if ok:
        total_institucional = 1
        print(f'  sobre_instituicao.pdf -> publico/sobre_instituicao.pdf')
        print(f'  sobre_instituicao.pdf.metadata.json -> publico/sobre_instituicao.pdf.metadata.json')

    # --- Resumo ---
    total_ementas = total_grad_ementa + total_ext_ementa
    total_materiais = total_grad_material + total_ext_material
    total = total_ementas + total_materiais + total_institucional
    print(f'\nDone!')
    print(f'  Graduacao ementas:   {total_grad_ementa} PDFs')
    print(f'  Graduacao material:  {total_grad_material} PDFs')
    print(f'  Extensao ementas:    {total_ext_ementa} PDFs')
    print(f'  Extensao material:   {total_ext_material} PDFs')
    print(f'  Institucional:       {total_institucional} PDF')
    print(f'  Total ementas:       {total_ementas} PDFs')
    print(f'  Total material:      {total_materiais} PDFs')
    print(f'  TOTAL GERAL:         {total} PDFs')
    print(f'  Diretorio: {OUTPUT_DIR}')


if __name__ == '__main__':
    main()
