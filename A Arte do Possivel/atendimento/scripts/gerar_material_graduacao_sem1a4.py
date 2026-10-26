"""
Gera PDFs de MATERIAL DIDATICO (estudo) para disciplinas de graduacao - Semestres 1 a 4.
Diferente das ementas (gerar_apostilas.py), este script gera conteudo educacional
simplificado que um aluno usaria para estudar.

Cada PDF tem ~5-8 paginas com:
1. Cabecalho institucional
2. Introducao ao tema
3. Conceitos fundamentais (2-3 conceitos-chave com exemplos)
4. Resumo dos principais topicos
5. Exercicios de fixacao (3-5 questoes)
6. Dicas de estudo e recursos adicionais
7. Glossario de termos importantes (5-10 termos)

Saida: output/apostilas/privado/graduacao/eng-software/{disciplina}_material.pdf

Uso: source .env && python3 scripts/gerar_material_graduacao_sem1a4.py
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
from _material_content import MATERIAL_DISCIPLINAS, gerar_conteudo_unidade_generico

# ============================================================
# Constantes
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output', 'apostilas')

INSTITUICAO = 'Instituicao de Ensino Demo'
CURSO_GRAD = 'Engenharia de Software'
CURSO_ID_GRAD = 'eng-software'

# ============================================================
# Grade curricular — apenas semestres 1 a 4 (20 disciplinas)
# ============================================================
GRADE_SEM1A4 = {
    '1_semestre': [
        'Introducao a Programacao (Python)',
        'Logica Matematica',
        'Calculo I',
        'Comunicacao e Expressao',
        'Fundamentos de Computacao',
    ],
    '2_semestre': [
        'Estrutura de Dados',
        'Programacao Orientada a Objetos',
        'Calculo II',
        'Banco de Dados I',
        'Sistemas Operacionais',
    ],
    '3_semestre': [
        'Engenharia de Software I',
        'Redes de Computadores',
        'Estatistica',
        'Banco de Dados II',
        'Desenvolvimento Web',
    ],
    '4_semestre': [
        'Engenharia de Software II',
        'Arquitetura de Software',
        'Testes de Software',
        'Desenvolvimento Mobile',
        'Projeto Integrador I',
    ],
}

# ============================================================
# Conteudo detalhado por disciplina (ementa, objetivos, topicos, bibliografia)
# Mesmo conteudo de gerar_apostilas.py para manter consistencia
# ============================================================
CONTEUDO_DISCIPLINAS = {
    'Introducao a Programacao (Python)': {
        'ementa': 'Fundamentos de logica de programacao. Variaveis, tipos de dados, operadores. Estruturas de controle (condicionais e repeticao). Funcoes e modularizacao. Manipulacao de strings e listas. Introducao a orientacao a objetos. Tratamento de excecoes. Leitura e escrita de arquivos.',
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
        'introducao': (
            'A programacao e a habilidade fundamental de todo profissional de tecnologia. '
            'Nesta disciplina, voce aprendera a pensar de forma logica e estruturada, '
            'traduzindo problemas do mundo real em solucoes computacionais usando Python, '
            'uma das linguagens mais populares e versateis do mercado. O dominio da '
            'programacao abre portas para todas as demais disciplinas do curso e para '
            'uma carreira solida em engenharia de software.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Algoritmos e Logica de Programacao',
                'explicacao': (
                    'Um algoritmo e uma sequencia finita de passos para resolver um problema. '
                    'Antes de escrever codigo, e essencial planejar a solucao usando pseudocodigo '
                    'ou fluxogramas. A capacidade de decompor problemas complexos em passos simples '
                    'e a habilidade mais importante de um programador.'
                ),
                'exemplo': (
                    'Exemplo: Para calcular a media de dois numeros:\n'
                    '1. Leia o primeiro numero\n'
                    '2. Leia o segundo numero\n'
                    '3. Some os dois numeros\n'
                    '4. Divida a soma por 2\n'
                    '5. Exiba o resultado\n\n'
                    'Em Python:\n'
                    'n1 = float(input("Numero 1: "))\n'
                    'n2 = float(input("Numero 2: "))\n'
                    'media = (n1 + n2) / 2\n'
                    'print(f"Media: {media}")'
                ),
            },
            {
                'titulo': 'Estruturas de Controle',
                'explicacao': (
                    'Estruturas condicionais (if/elif/else) permitem que o programa tome decisoes. '
                    'Estruturas de repeticao (for/while) executam blocos de codigo varias vezes. '
                    'Juntas, essas estruturas permitem criar programas que respondem a diferentes '
                    'situacoes e processam grandes volumes de dados automaticamente.'
                ),
                'exemplo': (
                    'Exemplo - verificar se um aluno foi aprovado:\n'
                    'nota = float(input("Nota: "))\n'
                    'if nota >= 7.0:\n'
                    '    print("Aprovado!")\n'
                    'elif nota >= 5.0:\n'
                    '    print("Recuperacao")\n'
                    'else:\n'
                    '    print("Reprovado")'
                ),
            },
            {
                'titulo': 'Funcoes e Modularizacao',
                'explicacao': (
                    'Funcoes sao blocos de codigo reutilizaveis definidos com "def". Elas recebem '
                    'parametros, processam dados e retornam resultados. A modularizacao divide o '
                    'programa em funcoes menores e mais gerenciaveis, facilitando a manutencao, '
                    'os testes e a reutilizacao de codigo.'
                ),
                'exemplo': (
                    'def calcular_media(notas):\n'
                    '    return sum(notas) / len(notas)\n\n'
                    'notas = [8.5, 7.0, 9.0, 6.5]\n'
                    'media = calcular_media(notas)\n'
                    'print(f"Media: {media:.1f}")'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual estrutura de repeticao e mais adequada quando sabemos exatamente quantas vezes o bloco deve ser executado?', 'alternativas': ['a) while', 'b) for', 'c) if/else', 'd) try/except'], 'resposta': 'b'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que a funcao input() retorna em Python?', 'alternativas': ['a) Um numero inteiro', 'b) Um numero decimal', 'c) Uma string', 'd) Um booleano'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique a diferenca entre uma lista e uma tupla em Python. Em que situacoes voce usaria cada uma?'},
            {'tipo': 'dissertativa', 'enunciado': 'Escreva uma funcao em Python que receba uma lista de numeros e retorne o maior e o menor valor.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual o resultado de: 10 // 3 em Python?', 'alternativas': ['a) 3.33', 'b) 3', 'c) 4', 'd) 1'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Pratique todos os dias — programacao se aprende fazendo, nao apenas lendo.',
            'Use o interpretador interativo do Python (REPL) para testar pequenos trechos de codigo.',
            'Resolva exercicios em plataformas como HackerRank, LeetCode e URI Online Judge.',
            'Leia codigo de outros programadores no GitHub para aprender diferentes abordagens.',
            'Nao tenha medo de errar — os erros sao a melhor forma de aprender.',
        ],
        'glossario': [
            'Algoritmo: sequencia finita de instrucoes para resolver um problema.',
            'Variavel: espaco na memoria que armazena um valor que pode mudar.',
            'Funcao: bloco de codigo reutilizavel que realiza uma tarefa especifica.',
            'Lista: colecao ordenada e mutavel de elementos em Python.',
            'Dicionario: colecao de pares chave-valor em Python.',
            'String: sequencia imutavel de caracteres.',
            'Loop: estrutura que repete um bloco de codigo (for, while).',
            'Excecao: erro que ocorre durante a execucao do programa.',
            'Modulo: arquivo Python que contem funcoes e classes reutilizaveis.',
            'Indentacao: espacos no inicio da linha que definem blocos de codigo em Python.',
        ],
    },
    'Logica Matematica': {
        'ementa': 'Proposicoes e conectivos logicos. Tabelas-verdade. Equivalencias e implicacoes logicas. Quantificadores. Metodos de demonstracao. Logica de predicados. Algebra booleana. Aplicacoes em computacao.',
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
        'introducao': (
            'A logica matematica e o alicerce do raciocinio computacional. Ela fornece as '
            'ferramentas formais para analisar argumentos, projetar circuitos digitais, '
            'verificar a corretude de programas e construir sistemas de inteligencia artificial. '
            'Dominar logica e essencial para qualquer engenheiro de software que deseja escrever '
            'codigo correto e eficiente.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Proposicoes e Conectivos Logicos',
                'explicacao': (
                    'Uma proposicao e uma sentenca declarativa que pode ser verdadeira (V) ou falsa (F). '
                    'Conectivos logicos combinam proposicoes: negacao (~p), conjuncao (p ^ q), '
                    'disjuncao (p v q), condicional (p -> q) e bicondicional (p <-> q). '
                    'A tabela-verdade lista todas as combinacoes possiveis de valores logicos.'
                ),
                'exemplo': (
                    'Tabela-verdade da Condicional (p -> q):\n'
                    'p=V, q=V => p->q = V\n'
                    'p=V, q=F => p->q = F\n'
                    'p=F, q=V => p->q = V\n'
                    'p=F, q=F => p->q = V\n\n'
                    'A condicional so e falsa quando a hipotese e V e a conclusao e F.'
                ),
            },
            {
                'titulo': 'Leis de De Morgan e Equivalencias',
                'explicacao': (
                    'As Leis de De Morgan sao equivalencias fundamentais: ~(p ^ q) = (~p v ~q) e '
                    '~(p v q) = (~p ^ ~q). Em programacao, isso significa que "not (A and B)" '
                    'equivale a "(not A) or (not B)". Essas leis sao essenciais para simplificar '
                    'condicoes complexas em codigo.'
                ),
                'exemplo': (
                    'Aplicacao em Python:\n'
                    '# Original\n'
                    'if not (idade >= 18 and tem_carteira):\n'
                    '    print("Nao pode dirigir")\n\n'
                    '# Equivalente (De Morgan)\n'
                    'if idade < 18 or not tem_carteira:\n'
                    '    print("Nao pode dirigir")'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual e o valor logico de "Se 2+2=5, entao a Lua e feita de queijo"?', 'alternativas': ['a) Verdadeiro', 'b) Falso', 'c) Indeterminado', 'd) Nenhuma das anteriores'], 'resposta': 'a'},
            {'tipo': 'dissertativa', 'enunciado': 'Construa a tabela-verdade para a expressao: (p ^ q) -> (p v r).'},
            {'tipo': 'multipla_escolha', 'enunciado': 'A negacao de "p ^ q" segundo De Morgan e:', 'alternativas': ['a) ~p ^ ~q', 'b) ~p v ~q', 'c) p v q', 'd) ~(p v q)'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Simplifique a expressao logica: ~(~p v (q ^ ~r)) usando as leis de equivalencia.'},
        ],
        'dicas_estudo': [
            'Pratique construindo tabelas-verdade para diferentes expressoes.',
            'Relacione os conectivos logicos com operadores de programacao (and, or, not).',
            'Use as Leis de De Morgan para simplificar condicoes em seus programas.',
            'Estude inducao matematica — e a base de muitas provas em computacao.',
        ],
        'glossario': [
            'Proposicao: sentenca declarativa com valor logico definido (V ou F).',
            'Tautologia: proposicao que e sempre verdadeira.',
            'Contradicao: proposicao que e sempre falsa.',
            'Contingencia: proposicao que pode ser V ou F dependendo dos valores.',
            'Quantificador universal: "para todo" (simbolo: inverted A).',
            'Quantificador existencial: "existe" (simbolo: reversed E).',
            'Algebra booleana: sistema algebrico com operacoes AND, OR, NOT.',
            'Modus Ponens: regra de inferencia: se p->q e p, entao q.',
        ],
    },
    'Calculo I': {
        'ementa': 'Funcoes reais de uma variavel. Limites e continuidade. Derivadas e aplicacoes. Integrais definidas e indefinidas. Teorema fundamental do calculo. Tecnicas de integracao.',
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
        'introducao': (
            'O Calculo Diferencial e Integral e uma das ferramentas matematicas mais poderosas '
            'ja desenvolvidas. Para engenheiros de software, o calculo e fundamental para '
            'compreender algoritmos de otimizacao, machine learning, computacao grafica e '
            'analise de complexidade. Os conceitos de limite, derivada e integral aparecem '
            'em diversas areas da computacao moderna.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Limites e Continuidade',
                'explicacao': (
                    'O limite descreve o comportamento de uma funcao quando a variavel se aproxima '
                    'de um determinado valor. Uma funcao e continua em um ponto se o limite existe, '
                    'a funcao esta definida naquele ponto e ambos sao iguais. Limites sao a base '
                    'para definir derivadas e integrais.'
                ),
                'exemplo': (
                    'Exemplo: lim(x->2) (x^2 - 4)/(x - 2)\n'
                    'Fatorando: (x-2)(x+2)/(x-2) = x+2\n'
                    'Portanto: lim(x->2) = 2+2 = 4\n\n'
                    'Mesmo que a funcao nao esteja definida em x=2,\n'
                    'o limite existe e vale 4.'
                ),
            },
            {
                'titulo': 'Derivadas e Aplicacoes',
                'explicacao': (
                    'A derivada mede a taxa de variacao instantanea de uma funcao. Geometricamente, '
                    'e a inclinacao da reta tangente ao grafico. Regras basicas: derivada de x^n = n*x^(n-1), '
                    'regra da cadeia, regra do produto e do quociente. Aplicacoes incluem encontrar '
                    'maximos e minimos de funcoes (otimizacao).'
                ),
                'exemplo': (
                    'Exemplo: f(x) = 3x^2 + 2x - 5\n'
                    'f\'(x) = 6x + 2\n\n'
                    'Para encontrar o minimo: f\'(x) = 0\n'
                    '6x + 2 = 0 => x = -1/3\n'
                    'f(-1/3) = 3(1/9) + 2(-1/3) - 5 = -16/3'
                ),
            },
            {
                'titulo': 'Integrais',
                'explicacao': (
                    'A integral e a operacao inversa da derivada. A integral indefinida encontra a '
                    'funcao original (antiderivada). A integral definida calcula a area sob a curva '
                    'entre dois pontos. O Teorema Fundamental do Calculo conecta derivadas e integrais, '
                    'sendo um dos resultados mais importantes da matematica.'
                ),
                'exemplo': (
                    'Integral indefinida: integral de x^2 dx = x^3/3 + C\n\n'
                    'Integral definida (area sob f(x)=x^2 de 0 a 3):\n'
                    'integral de 0 a 3 de x^2 dx = [x^3/3] de 0 a 3\n'
                    '= 27/3 - 0 = 9'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual e a derivada de f(x) = 5x^3 - 2x + 1?', 'alternativas': ['a) 15x^2 - 2', 'b) 5x^2 - 2', 'c) 15x^3 - 2x', 'd) 15x^2 + 1'], 'resposta': 'a'},
            {'tipo': 'dissertativa', 'enunciado': 'Calcule o limite: lim(x->0) sen(x)/x. Explique o resultado.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'A integral de 2x dx e:', 'alternativas': ['a) 2x + C', 'b) x^2 + C', 'c) x^2/2 + C', 'd) 2x^2 + C'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Encontre os pontos de maximo e minimo da funcao f(x) = x^3 - 3x + 2.'},
        ],
        'dicas_estudo': [
            'Domine as regras de derivacao antes de avancar para integrais.',
            'Pratique muitos exercicios — calculo exige treino constante.',
            'Use ferramentas como Wolfram Alpha ou GeoGebra para visualizar graficos.',
            'Relacione os conceitos com aplicacoes em computacao (otimizacao, ML).',
        ],
        'glossario': [
            'Limite: valor que uma funcao se aproxima quando x tende a um ponto.',
            'Derivada: taxa de variacao instantanea de uma funcao.',
            'Integral: operacao inversa da derivada; calcula areas sob curvas.',
            'Continuidade: funcao sem "saltos" ou "buracos" em seu dominio.',
            'Teorema Fundamental do Calculo: conecta derivadas e integrais.',
            'Maximos e minimos: pontos onde a funcao atinge valores extremos.',
            'Regra da cadeia: regra para derivar funcoes compostas.',
        ],
    },
    'Comunicacao e Expressao': {
        'ementa': 'Leitura e interpretacao de textos tecnicos e academicos. Producao textual: relatorios, artigos, documentacao tecnica. Comunicacao oral: apresentacoes e seminarios. Normas ABNT para trabalhos academicos.',
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
        'introducao': (
            'A comunicacao eficaz e uma competencia essencial para qualquer profissional. '
            'Na engenharia de software, a capacidade de redigir documentacao clara, apresentar '
            'projetos de forma convincente e comunicar ideias tecnicas para diferentes publicos '
            'e tao importante quanto saber programar. Esta disciplina desenvolve habilidades '
            'de leitura critica, escrita tecnica e comunicacao oral.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Coesao e Coerencia Textual',
                'explicacao': (
                    'Coesao refere-se aos mecanismos linguisticos que conectam as partes do texto '
                    '(pronomes, conjuncoes, sinonimos). Coerencia e a logica interna do texto — '
                    'as ideias devem fazer sentido juntas e seguir uma progressao logica. Um texto '
                    'coeso e coerente e facil de ler e entender.'
                ),
                'exemplo': (
                    'Sem coesao: "Python e popular. Java e usado em empresas. Programar e importante."\n\n'
                    'Com coesao: "Python e uma linguagem popular, especialmente para iniciantes. '
                    'Ja o Java, por sua vez, e amplamente utilizado em ambientes corporativos. '
                    'Ambas as linguagens demonstram como programar e uma habilidade cada vez mais importante."'
                ),
            },
            {
                'titulo': 'Documentacao Tecnica de Software',
                'explicacao': (
                    'A documentacao tecnica inclui especificacoes de requisitos (SRS), documentos de '
                    'design (SDD), manuais de usuario e READMEs. Uma boa documentacao facilita a '
                    'manutencao do software, o onboarding de novos desenvolvedores e a comunicacao '
                    'entre equipes. Deve ser clara, objetiva e atualizada.'
                ),
                'exemplo': (
                    'Estrutura de um README.md:\n'
                    '1. Nome do projeto e descricao breve\n'
                    '2. Pre-requisitos e instalacao\n'
                    '3. Como usar (exemplos)\n'
                    '4. Estrutura do projeto\n'
                    '5. Como contribuir\n'
                    '6. Licenca'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'dissertativa', 'enunciado': 'Reescreva o seguinte trecho melhorando a coesao: "O sistema falhou. O usuario perdeu dados. A equipe corrigiu o bug."'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual norma ABNT trata da formatacao de trabalhos academicos?', 'alternativas': ['a) NBR 6023', 'b) NBR 14724', 'c) NBR 10520', 'd) NBR 6028'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Escreva um resumo tecnico (5-8 linhas) sobre a importancia da documentacao em projetos de software.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e coerencia textual?', 'alternativas': ['a) Uso correto de conectivos', 'b) Logica interna e sentido do texto', 'c) Formatacao segundo ABNT', 'd) Uso de linguagem formal'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Leia textos tecnicos regularmente (artigos, documentacoes, blogs de engenharia).',
            'Pratique escrevendo READMEs e documentacao para seus projetos pessoais.',
            'Revise seus textos pelo menos duas vezes antes de entregar.',
            'Aprenda as normas ABNT basicas — serao uteis durante todo o curso.',
        ],
        'glossario': [
            'Coesao: mecanismos linguisticos que conectam as partes do texto.',
            'Coerencia: logica interna e sentido global do texto.',
            'ABNT: Associacao Brasileira de Normas Tecnicas.',
            'SRS: Software Requirements Specification (especificacao de requisitos).',
            'SDD: Software Design Document (documento de design).',
            'README: arquivo de apresentacao e instrucoes de um projeto.',
            'Resenha: texto critico que analisa e avalia uma obra.',
        ],
    },
    'Fundamentos de Computacao': {
        'ementa': 'Historia da computacao. Arquitetura de computadores (Von Neumann). Representacao de dados (binario, hexadecimal). Sistemas operacionais basicos. Redes de computadores (introducao). Etica e sociedade digital.',
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
        'introducao': (
            'Fundamentos de Computacao apresenta os conceitos essenciais que todo profissional '
            'de tecnologia precisa dominar. Desde a historia da computacao ate a arquitetura '
            'dos computadores modernos, esta disciplina fornece a base para compreender como '
            'o hardware e o software trabalham juntos. Entender esses fundamentos e crucial '
            'para tomar decisoes tecnicas informadas ao longo da carreira.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Arquitetura de Von Neumann',
                'explicacao': (
                    'A arquitetura de Von Neumann e o modelo basico dos computadores modernos. '
                    'Ela consiste em: CPU (Unidade de Controle + ULA), Memoria Principal, '
                    'Dispositivos de Entrada/Saida e Barramento. O conceito-chave e que dados '
                    'e instrucoes sao armazenados na mesma memoria, permitindo que programas '
                    'sejam modificados como dados.'
                ),
                'exemplo': (
                    'Ciclo de execucao de uma instrucao:\n'
                    '1. Busca (Fetch): CPU busca instrucao na memoria\n'
                    '2. Decodificacao (Decode): interpreta a instrucao\n'
                    '3. Execucao (Execute): realiza a operacao\n'
                    '4. Armazenamento (Store): salva o resultado\n\n'
                    'Este ciclo se repete bilhoes de vezes por segundo em CPUs modernas.'
                ),
            },
            {
                'titulo': 'Representacao de Dados em Binario',
                'explicacao': (
                    'Computadores usam o sistema binario (base 2) internamente. Cada digito binario '
                    '(bit) pode ser 0 ou 1. Um byte = 8 bits = 256 valores possiveis (0 a 255). '
                    'O sistema hexadecimal (base 16) e usado como atalho para representar binario. '
                    'Conversoes entre bases sao fundamentais para entender como dados sao armazenados.'
                ),
                'exemplo': (
                    'Conversao decimal -> binario:\n'
                    '42 em binario: 42/2=21 r0, 21/2=10 r1, 10/2=5 r0,\n'
                    '5/2=2 r1, 2/2=1 r0, 1/2=0 r1 => 101010\n\n'
                    'Conversao binario -> hexadecimal:\n'
                    '1010 1010 = A A => 0xAA\n'
                    '(1010 = 10 = A em hex)'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Quantos valores diferentes podem ser representados com 1 byte (8 bits)?', 'alternativas': ['a) 8', 'b) 128', 'c) 256', 'd) 512'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Converta o numero decimal 200 para binario e hexadecimal.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual componente da CPU realiza operacoes aritmeticas e logicas?', 'alternativas': ['a) Unidade de Controle', 'b) Registradores', 'c) ULA (Unidade Logica e Aritmetica)', 'd) Cache'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique o conceito de "programa armazenado" na arquitetura de Von Neumann e por que ele foi revolucionario.'},
        ],
        'dicas_estudo': [
            'Pratique conversoes entre binario, decimal e hexadecimal ate ficar natural.',
            'Explore o interior de um computador (videos de desmontagem sao otimos).',
            'Relacione os conceitos com o que voce ve no dia a dia (RAM, SSD, CPU).',
            'Estude a historia da computacao — entender o passado ajuda a prever o futuro.',
        ],
        'glossario': [
            'CPU: Unidade Central de Processamento — o "cerebro" do computador.',
            'RAM: Memoria de Acesso Aleatorio — memoria volatil e rapida.',
            'Bit: menor unidade de informacao (0 ou 1).',
            'Byte: conjunto de 8 bits.',
            'Barramento: canal de comunicacao entre componentes do computador.',
            'ULA: Unidade Logica e Aritmetica — realiza calculos na CPU.',
            'Sistema operacional: software que gerencia hardware e recursos.',
            'Hexadecimal: sistema numerico de base 16 (0-9, A-F).',
        ],
    },
    # ---- Semestre 2 ----
    'Estrutura de Dados': {
        'ementa': 'Listas, pilhas e filas. Arvores binarias e de busca. Grafos. Tabelas hash. Algoritmos de ordenacao e busca. Complexidade de algoritmos (notacao Big-O). Recursividade.',
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
        'introducao': (
            'Estrutura de Dados e uma das disciplinas mais importantes da computacao. '
            'Ela ensina como organizar e armazenar dados de forma eficiente para que '
            'operacoes como busca, insercao e remocao sejam rapidas. A escolha da estrutura '
            'de dados correta pode fazer a diferenca entre um programa que roda em milissegundos '
            'e um que leva horas. Todo engenheiro de software precisa dominar esse tema.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Listas, Pilhas e Filas',
                'explicacao': (
                    'Listas encadeadas armazenam elementos em nos conectados por ponteiros. '
                    'Pilhas (LIFO - Last In, First Out) permitem insercao e remocao apenas no topo. '
                    'Filas (FIFO - First In, First Out) inserem no final e removem do inicio. '
                    'Cada estrutura tem aplicacoes especificas: pilhas para desfazer acoes, '
                    'filas para processamento de tarefas.'
                ),
                'exemplo': (
                    'Pilha (LIFO) - exemplo com lista Python:\n'
                    'pilha = []\n'
                    'pilha.append("A")  # push\n'
                    'pilha.append("B")\n'
                    'pilha.append("C")\n'
                    'topo = pilha.pop()  # "C" (ultimo a entrar)\n\n'
                    'Fila (FIFO) - exemplo com deque:\n'
                    'from collections import deque\n'
                    'fila = deque()\n'
                    'fila.append("A")  # enqueue\n'
                    'fila.append("B")\n'
                    'primeiro = fila.popleft()  # "A" (primeiro a entrar)'
                ),
            },
            {
                'titulo': 'Complexidade de Algoritmos (Big-O)',
                'explicacao': (
                    'A notacao Big-O descreve o comportamento de um algoritmo conforme o tamanho '
                    'da entrada cresce. O(1) = constante, O(log n) = logaritmico, O(n) = linear, '
                    'O(n log n) = linearitmico, O(n^2) = quadratico. Entender complexidade permite '
                    'escolher o algoritmo mais eficiente para cada situacao.'
                ),
                'exemplo': (
                    'Complexidades comuns:\n'
                    'O(1): acesso a elemento por indice em array\n'
                    'O(log n): busca binaria\n'
                    'O(n): busca linear em lista\n'
                    'O(n log n): mergesort, quicksort (caso medio)\n'
                    'O(n^2): bubble sort, selection sort\n\n'
                    'Para n=1.000.000:\n'
                    'O(n) = 1.000.000 operacoes\n'
                    'O(n^2) = 1.000.000.000.000 operacoes!'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual estrutura de dados segue o principio LIFO?', 'alternativas': ['a) Fila', 'b) Lista', 'c) Pilha', 'd) Arvore'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique a diferenca entre uma arvore binaria de busca (BST) e uma arvore AVL.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual e a complexidade media do quicksort?', 'alternativas': ['a) O(n)', 'b) O(n log n)', 'c) O(n^2)', 'd) O(log n)'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva como funciona uma tabela hash e como colisoes sao tratadas.'},
        ],
        'dicas_estudo': [
            'Implemente cada estrutura de dados do zero — nao apenas use bibliotecas prontas.',
            'Visualize as estruturas com desenhos e diagramas.',
            'Pratique analise de complexidade em todos os algoritmos que escrever.',
            'Resolva problemas no LeetCode focando em estruturas de dados.',
        ],
        'glossario': [
            'LIFO: Last In, First Out — principio da pilha.',
            'FIFO: First In, First Out — principio da fila.',
            'Big-O: notacao que descreve a complexidade de tempo/espaco de um algoritmo.',
            'Arvore binaria: estrutura hierarquica onde cada no tem no maximo 2 filhos.',
            'Hash: funcao que mapeia dados de tamanho variavel para tamanho fixo.',
            'Grafo: estrutura com vertices (nos) e arestas (conexoes).',
            'Recursividade: tecnica onde uma funcao chama a si mesma.',
        ],
    },
    'Programacao Orientada a Objetos': {
        'ementa': 'Paradigma orientado a objetos. Classes, objetos, atributos e metodos. Encapsulamento, heranca e polimorfismo. Classes abstratas e interfaces. Padroes de projeto basicos.',
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
        'introducao': (
            'A Programacao Orientada a Objetos (POO) e o paradigma dominante no desenvolvimento '
            'de software moderno. Ela organiza o codigo em torno de objetos que combinam dados '
            'e comportamentos, facilitando a modelagem de problemas do mundo real. Os pilares '
            'da POO — encapsulamento, heranca e polimorfismo — sao fundamentais para criar '
            'sistemas flexiveis, reutilizaveis e faceis de manter.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Encapsulamento, Heranca e Polimorfismo',
                'explicacao': (
                    'Encapsulamento esconde detalhes internos e expoe apenas uma interface publica. '
                    'Heranca permite criar classes filhas que herdam atributos e metodos da classe pai. '
                    'Polimorfismo permite que objetos de classes diferentes respondam a mesma mensagem '
                    'de formas diferentes. Juntos, esses pilares permitem criar sistemas modulares.'
                ),
                'exemplo': (
                    'class Animal:\n'
                    '    def __init__(self, nome):\n'
                    '        self._nome = nome  # encapsulamento\n'
                    '    def falar(self):\n'
                    '        pass  # polimorfismo\n\n'
                    'class Cachorro(Animal):  # heranca\n'
                    '    def falar(self):\n'
                    '        return f"{self._nome} diz: Au au!"\n\n'
                    'class Gato(Animal):\n'
                    '    def falar(self):\n'
                    '        return f"{self._nome} diz: Miau!"'
                ),
            },
            {
                'titulo': 'Padroes de Projeto Basicos',
                'explicacao': (
                    'Padroes de projeto sao solucoes reutilizaveis para problemas comuns. '
                    'Singleton garante uma unica instancia de uma classe. Factory encapsula a '
                    'criacao de objetos. Observer notifica objetos sobre mudancas de estado. '
                    'Strategy permite trocar algoritmos em tempo de execucao.'
                ),
                'exemplo': (
                    '# Singleton em Python\n'
                    'class Database:\n'
                    '    _instance = None\n'
                    '    def __new__(cls):\n'
                    '        if cls._instance is None:\n'
                    '            cls._instance = super().__new__(cls)\n'
                    '        return cls._instance\n\n'
                    'db1 = Database()\n'
                    'db2 = Database()\n'
                    'print(db1 is db2)  # True (mesma instancia)'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual pilar da POO permite que uma classe filha herde atributos da classe pai?', 'alternativas': ['a) Encapsulamento', 'b) Polimorfismo', 'c) Heranca', 'd) Abstracao'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique a diferenca entre classe abstrata e interface. Quando usar cada uma?'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O padrao Singleton garante:', 'alternativas': ['a) Multiplas instancias', 'b) Uma unica instancia', 'c) Heranca multipla', 'd) Polimorfismo'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Implemente uma hierarquia de classes para um sistema de formas geometricas (Forma, Circulo, Retangulo) com calculo de area.'},
        ],
        'dicas_estudo': [
            'Pense em classes como substantivos e metodos como verbos.',
            'Pratique modelando sistemas do mundo real com classes.',
            'Estude os padroes de projeto do livro "Gang of Four" (GoF).',
            'Aplique o principio SOLID desde o inicio dos seus projetos.',
        ],
        'glossario': [
            'Classe: molde que define atributos e metodos de um tipo de objeto.',
            'Objeto: instancia de uma classe com valores proprios.',
            'Encapsulamento: ocultar detalhes internos, expor interface publica.',
            'Heranca: mecanismo para criar classes derivadas de outras.',
            'Polimorfismo: capacidade de objetos diferentes responderem a mesma mensagem.',
            'Interface: contrato que define metodos que uma classe deve implementar.',
            'Padrao de projeto: solucao reutilizavel para problemas recorrentes.',
        ],
    },
    'Calculo II': {
        'ementa': 'Funcoes de varias variaveis. Derivadas parciais. Integrais duplas e triplas. Equacoes diferenciais ordinarias. Transformada de Laplace (introducao).',
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
        'introducao': (
            'Calculo II estende os conceitos de Calculo I para funcoes de varias variaveis '
            'e equacoes diferenciais. Esses topicos sao essenciais para areas como computacao '
            'grafica (transformacoes 3D), machine learning (gradiente descendente), simulacoes '
            'fisicas e processamento de sinais. O dominio dessas ferramentas matematicas '
            'diferencia engenheiros de software capazes de resolver problemas complexos.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Derivadas Parciais e Gradiente',
                'explicacao': (
                    'Para funcoes de varias variaveis, a derivada parcial mede a taxa de variacao '
                    'em relacao a uma variavel, mantendo as outras constantes. O gradiente e o vetor '
                    'de todas as derivadas parciais e aponta na direcao de maior crescimento da funcao. '
                    'Em machine learning, o gradiente descendente usa esse conceito para minimizar funcoes de custo.'
                ),
                'exemplo': (
                    'f(x,y) = x^2 + 3xy + y^2\n\n'
                    'Derivada parcial em x: df/dx = 2x + 3y\n'
                    'Derivada parcial em y: df/dy = 3x + 2y\n\n'
                    'Gradiente: grad(f) = (2x + 3y, 3x + 2y)\n\n'
                    'No ponto (1,2): grad(f) = (8, 7)\n'
                    'A funcao cresce mais rapido na direcao (8,7).'
                ),
            },
            {
                'titulo': 'Equacoes Diferenciais Ordinarias',
                'explicacao': (
                    'Uma EDO e uma equacao que envolve uma funcao e suas derivadas. EDOs modelam '
                    'fenomenos que mudam ao longo do tempo: crescimento populacional, circuitos '
                    'eletricos, sistemas mecanicos. Em computacao, EDOs aparecem em simulacoes, '
                    'animacoes fisicas e modelagem de sistemas dinamicos.'
                ),
                'exemplo': (
                    'EDO de 1a ordem: dy/dx = 2x\n'
                    'Solucao: y = x^2 + C (integrando ambos os lados)\n\n'
                    'Aplicacao: crescimento exponencial\n'
                    'dP/dt = kP => P(t) = P0 * e^(kt)\n'
                    'Modela crescimento de usuarios de um app!'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'O gradiente de f(x,y) = x^2 + y^2 no ponto (3,4) e:', 'alternativas': ['a) (3, 4)', 'b) (6, 8)', 'c) (9, 16)', 'd) (2, 2)'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Resolva a EDO: dy/dx = 3x^2, com condicao inicial y(0) = 5.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Derivadas parciais sao usadas em machine learning para:', 'alternativas': ['a) Classificar dados', 'b) Calcular o gradiente descendente', 'c) Armazenar dados', 'd) Criar redes neurais'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Visualize funcoes de varias variaveis com graficos 3D (GeoGebra, Matplotlib).',
            'Relacione gradiente descendente com otimizacao em machine learning.',
            'Pratique EDOs separaveis e lineares — sao as mais comuns.',
            'Revise Calculo I antes de comecar — os conceitos se constroem.',
        ],
        'glossario': [
            'Derivada parcial: derivada em relacao a uma variavel, mantendo as outras fixas.',
            'Gradiente: vetor de derivadas parciais; aponta na direcao de maior crescimento.',
            'Integral dupla: integral sobre uma regiao do plano (calcula volumes).',
            'EDO: Equacao Diferencial Ordinaria — envolve funcao e suas derivadas.',
            'Curva de nivel: conjunto de pontos onde f(x,y) = constante.',
            'Transformada de Laplace: ferramenta para resolver EDOs no dominio da frequencia.',
        ],
    },
    'Banco de Dados I': {
        'ementa': 'Conceitos de banco de dados. Modelo entidade-relacionamento. Modelo relacional. SQL (DDL, DML, DQL). Normalizacao. Indices e otimizacao basica. Transacoes e controle de concorrencia.',
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
        'introducao': (
            'Bancos de dados sao o coracao de praticamente toda aplicacao moderna. '
            'Nesta disciplina, voce aprendera a projetar, implementar e consultar bancos '
            'de dados relacionais usando SQL. Desde redes sociais ate sistemas bancarios, '
            'todo software precisa armazenar e recuperar dados de forma eficiente e segura. '
            'O dominio de banco de dados e uma das habilidades mais valorizadas no mercado.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Modelo Relacional e SQL',
                'explicacao': (
                    'O modelo relacional organiza dados em tabelas (relacoes) com linhas (tuplas) '
                    'e colunas (atributos). SQL (Structured Query Language) e a linguagem padrao '
                    'para interagir com bancos relacionais. DDL define estrutura (CREATE TABLE), '
                    'DML manipula dados (INSERT, UPDATE, DELETE) e DQL consulta dados (SELECT).'
                ),
                'exemplo': (
                    'CREATE TABLE alunos (\n'
                    '    id INT PRIMARY KEY,\n'
                    '    nome VARCHAR(100) NOT NULL,\n'
                    '    email VARCHAR(100) UNIQUE,\n'
                    '    curso_id INT REFERENCES cursos(id)\n'
                    ');\n\n'
                    'SELECT a.nome, c.nome AS curso\n'
                    'FROM alunos a\n'
                    'JOIN cursos c ON a.curso_id = c.id\n'
                    'WHERE c.nome = \'Eng. Software\';'
                ),
            },
            {
                'titulo': 'Normalizacao',
                'explicacao': (
                    'Normalizacao e o processo de organizar tabelas para eliminar redundancias '
                    'e anomalias. 1FN: atributos atomicos. 2FN: sem dependencias parciais. '
                    '3FN: sem dependencias transitivas. BCNF: todo determinante e chave candidata. '
                    'Normalizar melhora a integridade dos dados e facilita a manutencao.'
                ),
                'exemplo': (
                    'Tabela NAO normalizada:\n'
                    'Pedido(id, cliente, telefone, produto, preco)\n'
                    'Problema: se o cliente muda de telefone, precisa atualizar em todos os pedidos.\n\n'
                    'Apos normalizacao (3FN):\n'
                    'Cliente(id, nome, telefone)\n'
                    'Produto(id, nome, preco)\n'
                    'Pedido(id, cliente_id, produto_id, data)'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual comando SQL e usado para consultar dados?', 'alternativas': ['a) INSERT', 'b) UPDATE', 'c) SELECT', 'd) CREATE'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Projete um modelo ER para um sistema de biblioteca com livros, autores e emprestimos.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'A propriedade ACID que garante que transacoes sao "tudo ou nada" e:', 'alternativas': ['a) Atomicidade', 'b) Consistencia', 'c) Isolamento', 'd) Durabilidade'], 'resposta': 'a'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique o que e normalizacao e por que a 3FN e geralmente suficiente na pratica.'},
        ],
        'dicas_estudo': [
            'Pratique SQL em ambientes online como SQLFiddle ou DB Fiddle.',
            'Modele bancos de dados para projetos pessoais (loja, blog, etc.).',
            'Entenda bem JOINs — sao a base de consultas complexas.',
            'Estude o conceito ACID — e fundamental para transacoes.',
        ],
        'glossario': [
            'SQL: Structured Query Language — linguagem para bancos relacionais.',
            'DDL: Data Definition Language — comandos de estrutura (CREATE, ALTER).',
            'DML: Data Manipulation Language — comandos de dados (INSERT, UPDATE).',
            'Normalizacao: processo de eliminar redundancias em tabelas.',
            'Chave primaria: identificador unico de cada registro na tabela.',
            'Chave estrangeira: referencia a chave primaria de outra tabela.',
            'ACID: Atomicidade, Consistencia, Isolamento, Durabilidade.',
            'JOIN: operacao que combina dados de duas ou mais tabelas.',
        ],
    },
    'Sistemas Operacionais': {
        'ementa': 'Conceitos de sistemas operacionais. Processos e threads. Escalonamento de CPU. Gerenciamento de memoria. Sistemas de arquivos. Virtualizacao e containers.',
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
            'STALLINGS, W. Operating Systems. Pearson, 2018.',
        ],
        'introducao': (
            'O sistema operacional e o software mais importante do computador — ele gerencia '
            'todos os recursos de hardware e fornece servicos para os programas. Entender como '
            'processos, memoria e E/S sao gerenciados e essencial para escrever software '
            'eficiente e diagnosticar problemas de performance. Com a popularizacao de containers '
            'e cloud computing, esse conhecimento e mais relevante do que nunca.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Processos, Threads e Escalonamento',
                'explicacao': (
                    'Um processo e um programa em execucao com seu proprio espaco de memoria. '
                    'Threads sao fluxos de execucao dentro de um processo que compartilham memoria. '
                    'O escalonador de CPU decide qual processo/thread executa a cada momento. '
                    'Algoritmos comuns: FCFS, SJF, Round Robin e prioridade.'
                ),
                'exemplo': (
                    'Estados de um processo:\n'
                    'Novo -> Pronto -> Executando -> Bloqueado -> Pronto\n'
                    '                  Executando -> Terminado\n\n'
                    'Round Robin (quantum = 4ms):\n'
                    'P1(8ms), P2(4ms), P3(2ms)\n'
                    'Execucao: P1(4) -> P2(4) -> P3(2) -> P1(4)\n'
                    'Tempo total: 14ms'
                ),
            },
            {
                'titulo': 'Gerenciamento de Memoria e Memoria Virtual',
                'explicacao': (
                    'O SO gerencia a memoria RAM alocando espacos para processos. Paginacao divide '
                    'a memoria em paginas de tamanho fixo. Memoria virtual permite que programas '
                    'usem mais memoria do que a RAM fisica, usando disco como extensao. Algoritmos '
                    'de substituicao (FIFO, LRU, Otimo) decidem qual pagina remover quando a memoria esta cheia.'
                ),
                'exemplo': (
                    'Memoria virtual com paginacao:\n'
                    'RAM: 4 frames de 4KB cada = 16KB\n'
                    'Processo precisa de 32KB (8 paginas)\n\n'
                    'Apenas 4 paginas ficam na RAM por vez.\n'
                    'Quando acessa pagina ausente: PAGE FAULT\n'
                    'SO carrega pagina do disco e remove outra (LRU).'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual algoritmo de escalonamento atribui um tempo fixo para cada processo?', 'alternativas': ['a) FCFS', 'b) SJF', 'c) Round Robin', 'd) Prioridade'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique o que e um deadlock e quais sao as 4 condicoes necessarias para que ocorra.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que acontece quando um processo acessa uma pagina que nao esta na RAM?', 'alternativas': ['a) Segmentation fault', 'b) Page fault', 'c) Stack overflow', 'd) Buffer overflow'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Use o Linux como ambiente de estudo — explore comandos como ps, top, htop.',
            'Experimente Docker para entender containers na pratica.',
            'Simule algoritmos de escalonamento com papel e caneta.',
            'Relacione os conceitos com problemas reais de performance.',
        ],
        'glossario': [
            'Processo: programa em execucao com espaco de memoria proprio.',
            'Thread: fluxo de execucao dentro de um processo.',
            'Escalonamento: algoritmo que decide qual processo usa a CPU.',
            'Deadlock: situacao onde processos ficam bloqueados mutuamente.',
            'Paginacao: divisao da memoria em blocos de tamanho fixo.',
            'Page fault: acesso a pagina que nao esta na RAM.',
            'Container: ambiente isolado e leve para executar aplicacoes.',
        ],
    },
    # ---- Semestre 3 ----
    'Engenharia de Software I': {
        'ementa': 'Processos de desenvolvimento de software. Engenharia de requisitos. Modelagem UML. Ciclo de vida do software. Metodologias tradicionais (cascata, espiral). Qualidade de software.',
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
        'introducao': (
            'A Engenharia de Software aplica principios de engenharia ao desenvolvimento de software, '
            'buscando produzir sistemas de alta qualidade dentro do prazo e orcamento. Esta disciplina '
            'ensina processos, tecnicas e ferramentas para planejar, projetar, implementar e manter '
            'software de forma sistematica. E a base para trabalhar em equipes e projetos reais.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Processos de Software e Ciclo de Vida',
                'explicacao': (
                    'Um processo de software define as atividades necessarias para desenvolver um sistema. '
                    'O modelo cascata segue fases sequenciais (requisitos, design, implementacao, teste). '
                    'O modelo incremental entrega o software em partes. O modelo espiral combina iteracao '
                    'com analise de riscos. A escolha do processo depende do projeto e da equipe.'
                ),
                'exemplo': (
                    'Modelo Cascata:\n'
                    '1. Requisitos -> 2. Design -> 3. Implementacao\n'
                    '-> 4. Testes -> 5. Manutencao\n\n'
                    'Vantagem: simples e bem documentado\n'
                    'Desvantagem: dificil voltar a fases anteriores\n\n'
                    'Modelo Incremental:\n'
                    'Incremento 1: funcionalidades basicas\n'
                    'Incremento 2: funcionalidades intermediarias\n'
                    'Incremento 3: funcionalidades avancadas'
                ),
            },
            {
                'titulo': 'Engenharia de Requisitos',
                'explicacao': (
                    'Requisitos definem O QUE o sistema deve fazer (funcionais) e COMO deve se comportar '
                    '(nao-funcionais: performance, seguranca, usabilidade). A elicitacao coleta requisitos '
                    'com stakeholders. A especificacao documenta em formato padrao (SRS). Requisitos mal '
                    'definidos sao a principal causa de falha em projetos de software.'
                ),
                'exemplo': (
                    'Requisito funcional:\n'
                    '"O sistema deve permitir que o aluno consulte suas notas por disciplina."\n\n'
                    'Requisito nao-funcional:\n'
                    '"O tempo de resposta para consultas deve ser inferior a 2 segundos."\n'
                    '"O sistema deve suportar 1000 usuarios simultaneos."'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual modelo de processo segue fases estritamente sequenciais?', 'alternativas': ['a) Espiral', 'b) Cascata', 'c) Agil', 'd) Incremental'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Diferencie requisitos funcionais de nao-funcionais. De 2 exemplos de cada para um sistema de e-commerce.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual diagrama UML representa a interacao entre usuario e sistema?', 'alternativas': ['a) Diagrama de classes', 'b) Diagrama de sequencia', 'c) Diagrama de casos de uso', 'd) Diagrama de atividades'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Pratique modelagem UML com ferramentas como draw.io ou StarUML.',
            'Escreva requisitos para projetos pessoais antes de comecar a programar.',
            'Estude casos reais de falhas em projetos de software.',
            'Leia o livro do Sommerville — e a referencia classica da area.',
        ],
        'glossario': [
            'Requisito funcional: o que o sistema deve fazer.',
            'Requisito nao-funcional: como o sistema deve se comportar (performance, seguranca).',
            'UML: Unified Modeling Language — linguagem de modelagem visual.',
            'SRS: Software Requirements Specification.',
            'Stakeholder: qualquer pessoa interessada ou afetada pelo sistema.',
            'Ciclo de vida: fases pelas quais o software passa, do inicio ao fim.',
        ],
    },
    'Redes de Computadores': {
        'ementa': 'Modelo OSI e TCP/IP. Camada fisica e enlace. Protocolos de rede (IP, ICMP). Camada de transporte (TCP, UDP). Camada de aplicacao (HTTP, DNS, SMTP). Seguranca em redes.',
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
        'introducao': (
            'Redes de computadores sao a infraestrutura que conecta o mundo digital. '
            'Toda aplicacao moderna depende de redes — desde um simples acesso a web ate '
            'sistemas distribuidos em nuvem. Entender protocolos como TCP/IP, HTTP e DNS '
            'e fundamental para desenvolver aplicacoes web, APIs e microsservicos. '
            'Esta disciplina fornece a base para trabalhar com qualquer tecnologia de rede.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Modelo TCP/IP e Camadas',
                'explicacao': (
                    'O modelo TCP/IP organiza a comunicacao em 4 camadas: Aplicacao (HTTP, DNS), '
                    'Transporte (TCP, UDP), Rede (IP) e Enlace (Ethernet, Wi-Fi). Cada camada '
                    'tem responsabilidades especificas e se comunica com as camadas adjacentes. '
                    'Dados sao encapsulados ao descer as camadas e desencapsulados ao subir.'
                ),
                'exemplo': (
                    'Quando voce acessa um site:\n'
                    '1. Aplicacao: navegador envia requisicao HTTP\n'
                    '2. Transporte: TCP divide em segmentos, garante entrega\n'
                    '3. Rede: IP adiciona enderecos origem/destino\n'
                    '4. Enlace: Ethernet encapsula em frames\n\n'
                    'No destino, o processo e invertido (desencapsulamento).'
                ),
            },
            {
                'titulo': 'HTTP e DNS',
                'explicacao': (
                    'HTTP (HyperText Transfer Protocol) e o protocolo da web. Usa metodos como '
                    'GET (buscar), POST (enviar), PUT (atualizar) e DELETE (remover). DNS (Domain '
                    'Name System) traduz nomes de dominio (google.com) em enderecos IP (142.250.80.46). '
                    'Entender HTTP e DNS e essencial para desenvolvimento web e APIs.'
                ),
                'exemplo': (
                    'Requisicao HTTP:\n'
                    'GET /api/alunos HTTP/1.1\n'
                    'Host: api.escola.com\n'
                    'Authorization: Bearer token123\n\n'
                    'Resposta:\n'
                    'HTTP/1.1 200 OK\n'
                    'Content-Type: application/json\n'
                    '{"alunos": [{"nome": "Ana", "curso": "ES"}]}'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual protocolo de transporte garante entrega ordenada dos dados?', 'alternativas': ['a) UDP', 'b) IP', 'c) TCP', 'd) HTTP'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique o processo de resolucao DNS quando voce digita "www.google.com" no navegador.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual camada do modelo TCP/IP e responsavel pelo roteamento?', 'alternativas': ['a) Aplicacao', 'b) Transporte', 'c) Rede', 'd) Enlace'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Use Wireshark para capturar e analisar pacotes de rede.',
            'Pratique com comandos: ping, traceroute, nslookup, curl.',
            'Entenda bem HTTP — e o protocolo mais usado em desenvolvimento web.',
            'Configure uma rede local virtual para praticar.',
        ],
        'glossario': [
            'TCP: Transmission Control Protocol — transporte confiavel.',
            'UDP: User Datagram Protocol — transporte rapido sem garantia.',
            'IP: Internet Protocol — enderecamento e roteamento.',
            'DNS: Domain Name System — traduz nomes em enderecos IP.',
            'HTTP: HyperText Transfer Protocol — protocolo da web.',
            'Firewall: sistema que filtra trafego de rede.',
            'VPN: Virtual Private Network — tunel seguro pela internet.',
        ],
    },
    'Estatistica': {
        'ementa': 'Estatistica descritiva. Probabilidade. Distribuicoes de probabilidade. Amostragem. Estimacao e intervalos de confianca. Testes de hipoteses. Regressao linear.',
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
        'introducao': (
            'A Estatistica e a ciencia de coletar, analisar e interpretar dados. Na engenharia '
            'de software, ela e usada para estimar prazos, medir qualidade, analisar performance '
            'e tomar decisoes baseadas em dados. Com o crescimento de data science e machine '
            'learning, o dominio de estatistica tornou-se ainda mais valioso para profissionais '
            'de tecnologia.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Estatistica Descritiva',
                'explicacao': (
                    'Estatistica descritiva resume e descreve dados. Medidas de tendencia central: '
                    'media (soma/n), mediana (valor central) e moda (mais frequente). Medidas de '
                    'dispersao: variancia, desvio padrao e amplitude. Graficos como histogramas '
                    'e boxplots ajudam a visualizar a distribuicao dos dados.'
                ),
                'exemplo': (
                    'Notas de uma turma: [6, 7, 7, 8, 8, 8, 9, 9, 10]\n\n'
                    'Media = (6+7+7+8+8+8+9+9+10)/9 = 8.0\n'
                    'Mediana = 8 (valor central)\n'
                    'Moda = 8 (mais frequente)\n'
                    'Desvio padrao = 1.15 (dispersao em torno da media)'
                ),
            },
            {
                'titulo': 'Distribuicao Normal e Testes de Hipoteses',
                'explicacao': (
                    'A distribuicao normal (curva de Gauss) e a mais importante da estatistica. '
                    'Cerca de 68% dos dados ficam a 1 desvio padrao da media, 95% a 2 desvios. '
                    'Testes de hipoteses permitem tomar decisoes sobre populacoes com base em amostras. '
                    'O p-valor indica a probabilidade de observar os dados se a hipotese nula for verdadeira.'
                ),
                'exemplo': (
                    'Teste de hipotese:\n'
                    'H0: a media de bugs por sprint = 5\n'
                    'H1: a media de bugs por sprint != 5\n\n'
                    'Amostra de 30 sprints: media = 6.2, desvio = 1.5\n'
                    'Calcula-se a estatistica t e o p-valor.\n'
                    'Se p-valor < 0.05: rejeita H0 (media e diferente de 5).'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual medida de tendencia central e mais afetada por valores extremos (outliers)?', 'alternativas': ['a) Mediana', 'b) Moda', 'c) Media', 'd) Amplitude'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Calcule a media, mediana e desvio padrao do conjunto: {4, 6, 7, 8, 10, 12, 15}.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Na distribuicao normal, aproximadamente que percentual dos dados esta a 2 desvios padrao da media?', 'alternativas': ['a) 68%', 'b) 95%', 'c) 99.7%', 'd) 50%'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Use Python (pandas, numpy, scipy) para praticar analise estatistica.',
            'Visualize dados com matplotlib e seaborn — graficos ajudam a entender.',
            'Relacione estatistica com metricas de software (bugs, tempo de resposta).',
            'Pratique interpretacao de resultados, nao apenas calculos.',
        ],
        'glossario': [
            'Media: soma dos valores dividida pela quantidade.',
            'Mediana: valor central quando os dados estao ordenados.',
            'Desvio padrao: medida de dispersao dos dados em torno da media.',
            'Distribuicao normal: distribuicao simetrica em forma de sino.',
            'Hipotese nula (H0): afirmacao que se deseja testar.',
            'P-valor: probabilidade de observar os dados se H0 for verdadeira.',
            'Regressao linear: modelo que relaciona duas variaveis com uma reta.',
        ],
    },
    'Banco de Dados II': {
        'ementa': 'Bancos de dados NoSQL. MongoDB, DynamoDB, Redis. Modelagem de dados NoSQL. Bancos de dados distribuidos. Replicacao e sharding. Data warehousing. Introducao a Big Data.',
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
        'introducao': (
            'Banco de Dados II explora o mundo alem do modelo relacional. Com o crescimento '
            'de aplicacoes web, mobile e IoT, bancos NoSQL como MongoDB, DynamoDB e Redis '
            'tornaram-se essenciais. Esta disciplina ensina quando e como usar cada tipo de '
            'banco, modelagem para NoSQL e conceitos de bancos distribuidos que sao a base '
            'da computacao em nuvem moderna.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Bancos NoSQL: Tipos e Casos de Uso',
                'explicacao': (
                    'NoSQL ("Not Only SQL") engloba bancos que nao seguem o modelo relacional. '
                    'Tipos principais: chave-valor (Redis, DynamoDB) para cache e sessoes; '
                    'documentos (MongoDB) para dados semi-estruturados; colunares (Cassandra) '
                    'para analytics; grafos (Neo4j) para relacionamentos complexos.'
                ),
                'exemplo': (
                    'DynamoDB (chave-valor/documento):\n'
                    '{\n'
                    '  "cpf": "123.456.789-00",  // Partition Key\n'
                    '  "nome": "Wembley",\n'
                    '  "disciplinas_atuais": [\n'
                    '    {"nome": "DevOps", "nota_p1": 8.5},\n'
                    '    {"nome": "IA", "nota_p1": 7.5}\n'
                    '  ]\n'
                    '}\n\n'
                    'Tudo em um unico item — sem JOINs necessarios!'
                ),
            },
            {
                'titulo': 'Teorema CAP e Bancos Distribuidos',
                'explicacao': (
                    'O Teorema CAP afirma que um sistema distribuido pode garantir no maximo 2 de 3 '
                    'propriedades: Consistencia (todos veem os mesmos dados), Disponibilidade (toda '
                    'requisicao recebe resposta) e Tolerancia a Particao (funciona mesmo com falhas '
                    'de rede). Na pratica, como particoes acontecem, a escolha e entre CP ou AP.'
                ),
                'exemplo': (
                    'Exemplos de escolhas CAP:\n'
                    'CP (Consistencia + Particao): MongoDB, HBase\n'
                    '  -> Pode ficar indisponivel para manter consistencia\n\n'
                    'AP (Disponibilidade + Particao): DynamoDB, Cassandra\n'
                    '  -> Sempre responde, mas dados podem estar desatualizados\n'
                    '  -> "Consistencia eventual"'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual tipo de banco NoSQL e mais adequado para armazenar sessoes de usuario?', 'alternativas': ['a) Grafo', 'b) Colunar', 'c) Chave-valor', 'd) Documento'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique o Teorema CAP e de um exemplo pratico de quando voce escolheria AP sobre CP.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'DynamoDB e classificado como banco:', 'alternativas': ['a) Relacional', 'b) Grafo', 'c) Chave-valor/Documento', 'd) Colunar'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Instale MongoDB e DynamoDB Local para praticar.',
            'Compare modelagem relacional vs NoSQL para o mesmo problema.',
            'Entenda o Teorema CAP — e a base de sistemas distribuidos.',
            'Estude casos reais: como Netflix, Amazon e Uber usam NoSQL.',
        ],
        'glossario': [
            'NoSQL: categoria de bancos que nao usam modelo relacional.',
            'Chave-valor: banco que armazena pares chave-valor simples.',
            'Documento: banco que armazena documentos JSON/BSON.',
            'CAP: Consistencia, Disponibilidade, Tolerancia a Particao.',
            'Sharding: distribuicao de dados entre multiplos servidores.',
            'Replicacao: copia de dados em multiplos nos para redundancia.',
            'Consistencia eventual: dados convergem para o mesmo estado com o tempo.',
        ],
    },
    'Desenvolvimento Web': {
        'ementa': 'HTML5, CSS3 e JavaScript. Frameworks front-end (React). APIs REST. Node.js e Express. Autenticacao e autorizacao. Deploy e hospedagem.',
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
        'introducao': (
            'O Desenvolvimento Web e uma das areas mais dinamicas e demandadas da tecnologia. '
            'Nesta disciplina, voce aprendera a criar aplicacoes web completas, do front-end '
            '(HTML, CSS, JavaScript, React) ao back-end (Node.js, Express, APIs REST). '
            'Com bilhoes de usuarios na web, dominar desenvolvimento web abre portas para '
            'inumeras oportunidades profissionais.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'HTML, CSS e JavaScript',
                'explicacao': (
                    'HTML define a estrutura da pagina (titulos, paragrafos, formularios). '
                    'CSS controla a aparencia (cores, layout, animacoes). JavaScript adiciona '
                    'interatividade (eventos, manipulacao do DOM, requisicoes assincronas). '
                    'Juntos, formam a base de toda aplicacao web.'
                ),
                'exemplo': (
                    'HTML + CSS + JS basico:\n'
                    '<button id="btn">Clique aqui</button>\n'
                    '<p id="msg"></p>\n\n'
                    '<style>\n'
                    '  button { background: #1a5276; color: white; padding: 10px; }\n'
                    '</style>\n\n'
                    '<script>\n'
                    '  document.getElementById("btn").onclick = () => {\n'
                    '    document.getElementById("msg").textContent = "Ola, Web!";\n'
                    '  };\n'
                    '</script>'
                ),
            },
            {
                'titulo': 'APIs REST e Back-end',
                'explicacao': (
                    'APIs REST (Representational State Transfer) sao a forma padrao de comunicacao '
                    'entre front-end e back-end. Usam metodos HTTP (GET, POST, PUT, DELETE) e '
                    'retornam dados em JSON. Node.js com Express e uma stack popular para criar '
                    'APIs rapidas e escaláveis.'
                ),
                'exemplo': (
                    'API REST com Express:\n'
                    'const express = require("express");\n'
                    'const app = express();\n\n'
                    'app.get("/api/alunos", (req, res) => {\n'
                    '  res.json([{nome: "Ana"}, {nome: "Bruno"}]);\n'
                    '});\n\n'
                    'app.listen(3000, () => console.log("API rodando!"));'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual metodo HTTP e usado para criar um novo recurso?', 'alternativas': ['a) GET', 'b) POST', 'c) PUT', 'd) DELETE'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique a diferenca entre Flexbox e Grid no CSS. Quando usar cada um?'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e o DOM (Document Object Model)?', 'alternativas': ['a) Um banco de dados', 'b) Uma linguagem de programacao', 'c) Uma representacao em arvore da pagina HTML', 'd) Um protocolo de rede'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Crie projetos pessoais — um portfolio, um blog, uma to-do list.',
            'Use o DevTools do navegador (F12) para inspecionar e debugar.',
            'Aprenda React apos dominar JavaScript puro.',
            'Pratique criando APIs REST para seus projetos front-end.',
        ],
        'glossario': [
            'HTML: HyperText Markup Language — estrutura da pagina web.',
            'CSS: Cascading Style Sheets — estilizacao visual.',
            'DOM: Document Object Model — representacao da pagina em arvore.',
            'API REST: interface de comunicacao baseada em HTTP e JSON.',
            'SPA: Single Page Application — aplicacao que roda em uma unica pagina.',
            'JWT: JSON Web Token — token para autenticacao.',
            'Responsividade: design que se adapta a diferentes tamanhos de tela.',
        ],
    },
    # ---- Semestre 4 ----
    'Engenharia de Software II': {
        'ementa': 'Padroes de projeto avancados. Refatoracao. Principios SOLID. Clean Architecture. Domain-Driven Design (DDD). Revisao de codigo.',
        'topicos': [
            'Unidade 1: Principios SOLID - SRP, OCP, LSP, ISP, DIP',
            'Unidade 2: Padroes de projeto - Adapter, Decorator, Facade, Proxy',
            'Unidade 3: Padroes de projeto - Command, Template Method, Chain of Responsibility',
            'Unidade 4: Refatoracao - code smells e tecnicas de refatoracao',
            'Unidade 5: Clean Architecture - camadas e dependencias',
            'Unidade 6: Domain-Driven Design - entidades, value objects, agregados',
            'Unidade 7: Documentacao tecnica avancada e ADRs',
            'Unidade 8: Code review e boas praticas de equipe',
        ],
        'bibliografia': [
            'MARTIN, R. Codigo Limpo. Alta Books, 2009.',
            'MARTIN, R. Arquitetura Limpa. Alta Books, 2019.',
            'GAMMA, E. et al. Padroes de Projeto. Bookman, 2000.',
        ],
        'introducao': (
            'Engenharia de Software II aprofunda os conceitos de design e arquitetura de software. '
            'Os principios SOLID, padroes de projeto avancados e Clean Architecture sao ferramentas '
            'essenciais para criar sistemas que escalam, sao faceis de manter e resistem a mudancas. '
            'Esta disciplina prepara voce para trabalhar em projetos reais de grande porte.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Principios SOLID',
                'explicacao': (
                    'SOLID e um acronimo para 5 principios de design orientado a objetos: '
                    'S - Single Responsibility (uma classe, uma responsabilidade), '
                    'O - Open/Closed (aberto para extensao, fechado para modificacao), '
                    'L - Liskov Substitution (subclasses substituem a classe pai), '
                    'I - Interface Segregation (interfaces pequenas e especificas), '
                    'D - Dependency Inversion (dependa de abstracoes, nao de implementacoes).'
                ),
                'exemplo': (
                    '# Violacao do SRP (Single Responsibility)\n'
                    'class Relatorio:\n'
                    '    def calcular(self): ...\n'
                    '    def formatar_html(self): ...\n'
                    '    def enviar_email(self): ...\n\n'
                    '# Corrigido: cada classe com uma responsabilidade\n'
                    'class CalculadorRelatorio:\n'
                    '    def calcular(self): ...\n'
                    'class FormatadorHTML:\n'
                    '    def formatar(self, dados): ...\n'
                    'class EnviadorEmail:\n'
                    '    def enviar(self, conteudo): ...'
                ),
            },
            {
                'titulo': 'Clean Architecture',
                'explicacao': (
                    'Clean Architecture organiza o codigo em camadas concentricas: Entidades (regras '
                    'de negocio), Casos de Uso (logica da aplicacao), Adaptadores (controllers, '
                    'gateways) e Frameworks (banco, web, UI). A regra de dependencia diz que camadas '
                    'internas nunca dependem de camadas externas. Isso torna o sistema testavel e '
                    'independente de frameworks.'
                ),
                'exemplo': (
                    'Camadas da Clean Architecture:\n'
                    '1. Entidades: Aluno, Disciplina, Nota\n'
                    '2. Casos de Uso: MatricularAluno, CalcularMedia\n'
                    '3. Adaptadores: AlunoController, AlunoRepository\n'
                    '4. Frameworks: Express, PostgreSQL, React\n\n'
                    'Dependencia: 4 -> 3 -> 2 -> 1 (nunca o contrario!)'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'O principio "S" do SOLID significa:', 'alternativas': ['a) Segregacao de Interface', 'b) Substituicao de Liskov', 'c) Responsabilidade Unica', 'd) Inversao de Dependencia'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique o principio Open/Closed com um exemplo pratico de codigo.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Na Clean Architecture, qual camada contem as regras de negocio?', 'alternativas': ['a) Frameworks', 'b) Adaptadores', 'c) Casos de Uso', 'd) Entidades'], 'resposta': 'd'},
        ],
        'dicas_estudo': [
            'Leia "Codigo Limpo" e "Arquitetura Limpa" do Robert C. Martin.',
            'Pratique refatoracao em projetos existentes.',
            'Aplique SOLID gradualmente — nao tente tudo de uma vez.',
            'Faca code reviews com colegas para aprender diferentes perspectivas.',
        ],
        'glossario': [
            'SOLID: cinco principios de design orientado a objetos.',
            'Refatoracao: melhorar a estrutura do codigo sem alterar seu comportamento.',
            'Code smell: indicador de problema no design do codigo.',
            'Clean Architecture: arquitetura em camadas com regra de dependencia.',
            'DDD: Domain-Driven Design — design guiado pelo dominio do negocio.',
            'ADR: Architecture Decision Record — registro de decisoes arquiteturais.',
        ],
    },
    'Arquitetura de Software': {
        'ementa': 'Estilos arquiteturais. Microsservicos. Monolitos. Event-driven architecture. Arquitetura em camadas. Documentacao arquitetural (C4 model). Atributos de qualidade.',
        'topicos': [
            'Unidade 1: Introducao a arquitetura de software - conceitos e importancia',
            'Unidade 2: Estilos arquiteturais - camadas, pipes-and-filters, cliente-servidor',
            'Unidade 3: Arquitetura monolitica vs microsservicos',
            'Unidade 4: Event-driven architecture e mensageria',
            'Unidade 5: APIs e integracao entre sistemas',
            'Unidade 6: Atributos de qualidade - escalabilidade, disponibilidade, seguranca',
            'Unidade 7: Documentacao arquitetural - C4 model, diagramas',
            'Unidade 8: Decisoes arquiteturais e trade-offs',
        ],
        'bibliografia': [
            'RICHARDS, M. Fundamentals of Software Architecture. O\'Reilly, 2020.',
            'NEWMAN, S. Building Microservices. O\'Reilly, 2021.',
            'BASS, L. Software Architecture in Practice. Addison-Wesley, 2021.',
        ],
        'introducao': (
            'Arquitetura de Software define a estrutura de alto nivel de um sistema — como os '
            'componentes se organizam, comunicam e evoluem. Decisoes arquiteturais impactam '
            'escalabilidade, performance, manutencao e custo. Esta disciplina ensina a avaliar '
            'trade-offs e escolher a arquitetura certa para cada contexto, desde monolitos '
            'simples ate microsservicos distribuidos.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Monolito vs Microsservicos',
                'explicacao': (
                    'Um monolito e uma aplicacao unica que contem toda a logica. Microsservicos '
                    'dividem o sistema em servicos independentes, cada um com seu banco de dados. '
                    'Monolitos sao mais simples de desenvolver e deployar. Microsservicos escalam '
                    'melhor mas adicionam complexidade (rede, consistencia, monitoramento).'
                ),
                'exemplo': (
                    'Monolito:\n'
                    '[App Unica] -> [Banco Unico]\n'
                    'Tudo junto: usuarios, pedidos, pagamentos\n\n'
                    'Microsservicos:\n'
                    '[Servico Usuarios] -> [DB Usuarios]\n'
                    '[Servico Pedidos] -> [DB Pedidos]\n'
                    '[Servico Pagamentos] -> [DB Pagamentos]\n'
                    'Comunicacao via API/mensageria'
                ),
            },
            {
                'titulo': 'Atributos de Qualidade e Trade-offs',
                'explicacao': (
                    'Atributos de qualidade definem COMO o sistema se comporta: escalabilidade '
                    '(suportar mais usuarios), disponibilidade (estar sempre no ar), performance '
                    '(responder rapido), seguranca (proteger dados). Toda decisao arquitetural '
                    'envolve trade-offs — melhorar um atributo pode piorar outro.'
                ),
                'exemplo': (
                    'Trade-off classico:\n'
                    'Consistencia vs Disponibilidade (CAP)\n\n'
                    'Exemplo pratico:\n'
                    'Cache melhora performance mas pode servir dados desatualizados.\n'
                    'Microsservicos melhoram escalabilidade mas aumentam complexidade.\n'
                    'Criptografia melhora seguranca mas reduz performance.'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual estilo arquitetural divide o sistema em servicos independentes?', 'alternativas': ['a) Monolito', 'b) Camadas', 'c) Microsservicos', 'd) Pipes-and-filters'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Compare monolito e microsservicos. Em que cenario voce recomendaria cada um?'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O modelo C4 de documentacao arquitetural tem quantos niveis?', 'alternativas': ['a) 2', 'b) 3', 'c) 4', 'd) 5'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Estude arquiteturas de empresas reais (Netflix, Uber, Spotify).',
            'Pratique documentando arquiteturas com o modelo C4.',
            'Sempre considere trade-offs — nao existe arquitetura perfeita.',
            'Comece com monolito e evolua para microsservicos quando necessario.',
        ],
        'glossario': [
            'Monolito: aplicacao unica com toda a logica em um so deploy.',
            'Microsservico: servico independente com responsabilidade especifica.',
            'Escalabilidade: capacidade de suportar aumento de carga.',
            'Disponibilidade: percentual de tempo que o sistema esta operacional.',
            'Trade-off: compromisso entre duas qualidades conflitantes.',
            'C4 model: modelo de documentacao com 4 niveis de detalhe.',
            'Event-driven: arquitetura baseada em eventos assincronos.',
        ],
    },
    'Testes de Software': {
        'ementa': 'Fundamentos de testes. Testes unitarios, integracao e E2E. TDD e BDD. Automacao de testes. Testes de performance e seguranca. Cobertura de codigo.',
        'topicos': [
            'Unidade 1: Fundamentos de testes - niveis, tipos, estrategias',
            'Unidade 2: Testes unitarios - JUnit, pytest, Jest',
            'Unidade 3: TDD (Test-Driven Development) na pratica',
            'Unidade 4: Testes de integracao e mocks',
            'Unidade 5: BDD (Behavior-Driven Development) e Gherkin',
            'Unidade 6: Testes E2E - Selenium, Cypress, Playwright',
            'Unidade 7: Testes de performance (JMeter) e seguranca (OWASP ZAP)',
            'Unidade 8: Cobertura de codigo, CI/CD e qualidade continua',
        ],
        'bibliografia': [
            'BECK, K. TDD: Desenvolvimento Guiado por Testes. Bookman, 2010.',
            'ANICHE, M. Testes Automatizados de Software. Casa do Codigo, 2015.',
            'HUMBLE, J.; FARLEY, D. Entrega Continua. Bookman, 2014.',
        ],
        'introducao': (
            'Testes de software sao essenciais para garantir que o codigo funciona corretamente '
            'e continua funcionando apos mudancas. Esta disciplina ensina desde testes unitarios '
            'ate testes end-to-end, passando por TDD, BDD e automacao. Empresas de tecnologia '
            'valorizam profissionais que escrevem testes — e uma habilidade que diferencia '
            'engenheiros juniores de seniors.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Piramide de Testes e TDD',
                'explicacao': (
                    'A piramide de testes sugere: muitos testes unitarios (rapidos, baratos), '
                    'alguns testes de integracao e poucos testes E2E (lentos, caros). TDD '
                    '(Test-Driven Development) inverte o fluxo: primeiro escreve o teste, '
                    'depois o codigo que faz o teste passar, e por fim refatora. Ciclo: Red -> Green -> Refactor.'
                ),
                'exemplo': (
                    'TDD em Python com pytest:\n\n'
                    '# 1. RED - escreve teste que falha\n'
                    'def test_soma():\n'
                    '    assert soma(2, 3) == 5\n\n'
                    '# 2. GREEN - implementa o minimo\n'
                    'def soma(a, b):\n'
                    '    return a + b\n\n'
                    '# 3. REFACTOR - melhora o codigo\n'
                    '# (neste caso simples, nada a refatorar)'
                ),
            },
            {
                'titulo': 'Testes de Integracao e E2E',
                'explicacao': (
                    'Testes de integracao verificam que componentes funcionam juntos (ex: API + banco). '
                    'Testes E2E (end-to-end) simulam o usuario real interagindo com o sistema completo. '
                    'Mocks e stubs substituem dependencias externas em testes de integracao. '
                    'Ferramentas: Cypress e Playwright para E2E, pytest-mock para mocks.'
                ),
                'exemplo': (
                    'Teste de integracao (API + banco):\n'
                    'def test_criar_aluno(client, db):\n'
                    '    response = client.post("/api/alunos",\n'
                    '        json={"nome": "Ana", "curso": "ES"})\n'
                    '    assert response.status_code == 201\n'
                    '    aluno = db.query(Aluno).first()\n'
                    '    assert aluno.nome == "Ana"'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'No TDD, qual e a ordem correta do ciclo?', 'alternativas': ['a) Green -> Red -> Refactor', 'b) Red -> Green -> Refactor', 'c) Refactor -> Red -> Green', 'd) Red -> Refactor -> Green'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique a piramide de testes e por que testes unitarios devem ser a maioria.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual ferramenta e usada para testes E2E em aplicacoes web?', 'alternativas': ['a) pytest', 'b) JUnit', 'c) Cypress', 'd) Mockito'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Pratique TDD em projetos pessoais — comece com funcoes simples.',
            'Escreva testes ANTES de corrigir bugs — garante que o bug nao volta.',
            'Aprenda a usar mocks, mas nao abuse — prefira testes sem mock.',
            'Configure CI/CD para rodar testes automaticamente a cada commit.',
        ],
        'glossario': [
            'Teste unitario: testa uma unidade isolada de codigo (funcao, classe).',
            'Teste de integracao: testa a interacao entre componentes.',
            'Teste E2E: testa o sistema completo do ponto de vista do usuario.',
            'TDD: Test-Driven Development — testes antes do codigo.',
            'BDD: Behavior-Driven Development — testes baseados em comportamento.',
            'Mock: objeto falso que simula uma dependencia em testes.',
            'Cobertura: percentual do codigo exercitado pelos testes.',
        ],
    },
    'Desenvolvimento Mobile': {
        'ementa': 'Plataformas mobile (Android, iOS). Desenvolvimento nativo vs cross-platform. React Native e Flutter. UI/UX mobile. Armazenamento local. Consumo de APIs. Publicacao em lojas.',
        'topicos': [
            'Unidade 1: Introducao ao desenvolvimento mobile - plataformas e ecossistema',
            'Unidade 2: Nativo vs cross-platform - quando usar cada abordagem',
            'Unidade 3: React Native - componentes, navegacao, estado',
            'Unidade 4: Flutter - widgets, layout, gerenciamento de estado',
            'Unidade 5: UI/UX mobile - Material Design, Human Interface Guidelines',
            'Unidade 6: Armazenamento local - SQLite, AsyncStorage, SharedPreferences',
            'Unidade 7: Consumo de APIs REST e autenticacao mobile',
            'Unidade 8: Publicacao - Google Play Store e Apple App Store',
        ],
        'bibliografia': [
            'EISENMAN, B. Learning React Native. O\'Reilly, 2017.',
            'WINDMILL, E. Flutter in Action. Manning, 2020.',
            'GOOGLE. Material Design Guidelines. material.io, 2024.',
        ],
        'introducao': (
            'O desenvolvimento mobile e uma das areas mais dinamicas da tecnologia, com bilhoes '
            'de smartphones no mundo. Esta disciplina ensina a criar aplicativos para Android e '
            'iOS usando frameworks cross-platform como React Native e Flutter, que permitem '
            'escrever codigo uma vez e rodar em ambas as plataformas. Voce aprendera desde '
            'a criacao da interface ate a publicacao nas lojas de aplicativos.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Nativo vs Cross-Platform',
                'explicacao': (
                    'Desenvolvimento nativo usa a linguagem da plataforma (Kotlin/Java para Android, '
                    'Swift para iOS) e oferece melhor performance e acesso a recursos. Cross-platform '
                    '(React Native, Flutter) usa uma unica base de codigo para ambas as plataformas, '
                    'reduzindo custo e tempo. A escolha depende do projeto: apps simples se beneficiam '
                    'de cross-platform; apps complexos podem precisar de nativo.'
                ),
                'exemplo': (
                    'React Native (JavaScript):\n'
                    'const App = () => (\n'
                    '  <View style={{flex: 1, justifyContent: "center"}}>\n'
                    '    <Text>Ola, Mobile!</Text>\n'
                    '    <Button title="Clique" onPress={() => alert("Oi!")} />\n'
                    '  </View>\n'
                    ');\n\n'
                    'Roda em Android E iOS com o mesmo codigo!'
                ),
            },
            {
                'titulo': 'UI/UX Mobile e Design Patterns',
                'explicacao': (
                    'Apps mobile seguem guidelines especificas: Material Design (Android) e Human '
                    'Interface Guidelines (iOS). Padroes comuns incluem: navegacao por tabs, '
                    'listas com scroll, pull-to-refresh, bottom sheets. A experiencia do usuario '
                    'e crucial — apps com UX ruim sao desinstalados rapidamente.'
                ),
                'exemplo': (
                    'Padroes de navegacao mobile:\n'
                    '1. Tab Navigation: abas na parte inferior (Instagram)\n'
                    '2. Stack Navigation: telas empilhadas (voltar com swipe)\n'
                    '3. Drawer Navigation: menu lateral (Gmail)\n\n'
                    'Regra de ouro: o usuario deve conseguir\n'
                    'realizar qualquer acao em no maximo 3 toques.'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual framework cross-platform usa a linguagem Dart?', 'alternativas': ['a) React Native', 'b) Xamarin', 'c) Flutter', 'd) Ionic'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Compare React Native e Flutter. Quais sao as vantagens e desvantagens de cada um?'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Material Design e o guia de design do:', 'alternativas': ['a) Apple', 'b) Google', 'c) Microsoft', 'd) Facebook'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Instale um emulador Android e/ou simulador iOS para testar.',
            'Comece com React Native se ja sabe JavaScript, ou Flutter se quer aprender Dart.',
            'Estude os guidelines de design (Material Design, HIG) antes de criar interfaces.',
            'Publique um app simples na Play Store — o processo ensina muito.',
        ],
        'glossario': [
            'Nativo: desenvolvimento especifico para uma plataforma (Android ou iOS).',
            'Cross-platform: codigo unico que roda em multiplas plataformas.',
            'React Native: framework cross-platform baseado em JavaScript/React.',
            'Flutter: framework cross-platform do Google baseado em Dart.',
            'Widget: componente visual reutilizavel (Flutter).',
            'Material Design: sistema de design do Google para interfaces.',
            'APK/IPA: formatos de pacote de app para Android e iOS.',
        ],
    },
    'Projeto Integrador I': {
        'ementa': 'Projeto pratico integrando disciplinas dos semestres 1-4. Trabalho em equipe. Metodologias ageis (Scrum). Gestao de projeto. Apresentacao e defesa do projeto.',
        'topicos': [
            'Unidade 1: Definicao do projeto e formacao de equipes',
            'Unidade 2: Levantamento de requisitos e escopo',
            'Unidade 3: Planejamento com Scrum - backlog, sprints, daily',
            'Unidade 4: Arquitetura e design do sistema',
            'Unidade 5: Implementacao - Sprint 1 (MVP)',
            'Unidade 6: Implementacao - Sprint 2 (funcionalidades adicionais)',
            'Unidade 7: Testes, integracao e deploy',
            'Unidade 8: Apresentacao final e defesa do projeto',
        ],
        'bibliografia': [
            'SCHWABER, K.; SUTHERLAND, J. Guia do Scrum. scrumguides.org, 2020.',
            'COHN, M. Desenvolvimento de Software com Scrum. Bookman, 2011.',
            'SUTHERLAND, J. Scrum: A Arte de Fazer o Dobro do Trabalho na Metade do Tempo. Sextante, 2016.',
        ],
        'introducao': (
            'O Projeto Integrador I e a oportunidade de aplicar tudo que voce aprendeu nos '
            'primeiros 4 semestres em um projeto real. Trabalhando em equipe com metodologias '
            'ageis, voce vai planejar, desenvolver e apresentar um sistema completo. Esta '
            'experiencia simula o ambiente profissional e desenvolve habilidades tecnicas '
            'e interpessoais essenciais para a carreira.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Scrum e Metodologias Ageis',
                'explicacao': (
                    'Scrum e um framework agil que organiza o trabalho em sprints (ciclos de 1-4 semanas). '
                    'Papeis: Product Owner (define o que fazer), Scrum Master (facilita o processo), '
                    'Time de Desenvolvimento (executa). Artefatos: Product Backlog (lista de funcionalidades), '
                    'Sprint Backlog (tarefas da sprint), Incremento (produto entregue).'
                ),
                'exemplo': (
                    'Fluxo de uma Sprint (2 semanas):\n'
                    '1. Sprint Planning: equipe seleciona itens do backlog\n'
                    '2. Daily Standup (15min): o que fiz, o que farei, impedimentos\n'
                    '3. Desenvolvimento: equipe implementa as tarefas\n'
                    '4. Sprint Review: demonstra o que foi feito\n'
                    '5. Sprint Retrospective: o que melhorar\n\n'
                    'Repete a cada sprint ate o projeto estar completo.'
                ),
            },
            {
                'titulo': 'MVP e Entrega Incremental',
                'explicacao': (
                    'MVP (Minimum Viable Product) e a versao mais simples do produto que entrega '
                    'valor ao usuario. Em vez de tentar construir tudo de uma vez, entregue '
                    'incrementalmente: primeiro o MVP, depois funcionalidades adicionais. '
                    'Isso permite obter feedback cedo e ajustar o rumo do projeto.'
                ),
                'exemplo': (
                    'Projeto: Sistema de Gestao Academica\n\n'
                    'MVP (Sprint 1):\n'
                    '- Login de aluno\n'
                    '- Consulta de notas\n'
                    '- Consulta de horarios\n\n'
                    'Sprint 2:\n'
                    '- Matricula em disciplinas\n'
                    '- Historico academico\n'
                    '- Notificacoes'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'No Scrum, quem e responsavel por definir as prioridades do backlog?', 'alternativas': ['a) Scrum Master', 'b) Product Owner', 'c) Time de Desenvolvimento', 'd) Stakeholders'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva como voce organizaria um projeto integrador usando Scrum. Defina os papeis, sprints e entregas.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e um MVP?', 'alternativas': ['a) O produto final completo', 'b) A versao mais simples que entrega valor', 'c) Um prototipo visual', 'd) Um documento de requisitos'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Use ferramentas como Trello, Jira ou GitHub Projects para gerenciar tarefas.',
            'Pratique daily standups mesmo em projetos pessoais.',
            'Defina um MVP claro antes de comecar a implementar.',
            'Documente decisoes e aprendizados ao longo do projeto.',
        ],
        'glossario': [
            'Scrum: framework agil para gestao de projetos.',
            'Sprint: ciclo de trabalho com duracao fixa (1-4 semanas).',
            'Product Backlog: lista priorizada de funcionalidades do produto.',
            'MVP: Minimum Viable Product — versao minima viavel.',
            'Daily Standup: reuniao diaria de 15 minutos.',
            'Sprint Review: demonstracao do que foi entregue na sprint.',
            'Retrospectiva: reflexao sobre o que melhorar no processo.',
        ],
    },
}


# ============================================================
# Estilos de PDF (mesmos de gerar_apostilas.py)
# ============================================================
def get_styles():
    """Retorna estilos customizados para os PDFs de material didatico."""
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
        name='MaterialTitulo',
        parent=styles['Title'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=8,
        textColor=colors.HexColor('#1a5276'),
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
        name='SubSecao',
        parent=styles['Heading3'],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor('#2c3e50'),
        keepWithNext=True,
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
        name='CorpoMaterial',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        leading=15,
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
        name='GlossarioTermo',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=15,
        spaceAfter=3,
        leading=12,
    ))
    styles.add(ParagraphStyle(
        name='Rodape',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.grey,
    ))
    return styles


def sanitize_filename(nome):
    """Converte nome de disciplina em nome de arquivo seguro."""
    nome = nome.lower()
    nome = nome.replace('(', '').replace(')', '').replace('/', '_')
    nome = re.sub(r'[^a-z0-9_]', '_', nome)
    nome = re.sub(r'_+', '_', nome).strip('_')
    return nome


# ============================================================
# Geracao de PDF de Material Didatico
# ============================================================
def gerar_material_pdf(disciplina, semestre_num, output_path, styles):
    """Gera PDF de material didatico (~5-8 paginas) para uma disciplina."""
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

    # ---- 1. Cabecalho / Capa ----
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph(INSTITUICAO, styles['TituloInstituicao']))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f'Curso: {CURSO_GRAD}', styles['SubtituloCurso']))
    story.append(Paragraph(f'{semestre_num}o Semestre', styles['SubtituloCurso']))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph('Material de Estudo', styles['MaterialTitulo']))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(disciplina, styles['DisciplinaTitulo']))
    story.append(Spacer(1, 1.5*cm))

    # Linha separadora
    line_data = [['']]
    line_table = Table(line_data, colWidths=[doc.width])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor('#1a5276')),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.8*cm))

    # ---- 2. Introducao ao tema ----
    story.append(Paragraph('1. INTRODUCAO', styles['Secao']))
    story.append(Paragraph(conteudo.get('introducao', ''), styles['CorpoMaterial']))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f'<b>Ementa:</b> {conteudo["ementa"]}',
        styles['CorpoMaterial']
    ))

    story.append(PageBreak())

    # ---- 3. Conceitos Fundamentais ----
    story.append(Paragraph('2. CONCEITOS FUNDAMENTAIS', styles['Secao']))
    story.append(Paragraph(
        'A seguir, apresentamos os conceitos-chave desta disciplina com explicacoes '
        'didaticas e exemplos praticos para facilitar o aprendizado.',
        styles['CorpoMaterial']
    ))
    story.append(Spacer(1, 6))

    for i, conceito in enumerate(conteudo.get('conceitos_fundamentais', []), 1):
        story.append(Paragraph(f'2.{i} {conceito["titulo"]}', styles['SubSecao']))
        story.append(Paragraph(conceito['explicacao'], styles['CorpoMaterial']))

        # Exemplo
        story.append(Paragraph('<b>Exemplo:</b>', styles['CorpoMaterial']))
        exemplo = conceito.get('exemplo', '')
        # Escapar caracteres HTML no exemplo
        code_escaped = exemplo.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        for line in code_escaped.split('\n'):
            story.append(Paragraph(line if line.strip() else '&nbsp;', styles['Codigo']))
        story.append(Spacer(1, 8))

    story.append(PageBreak())

    # ---- 4. Resumo dos Principais Topicos ----
    story.append(Paragraph('3. RESUMO DOS PRINCIPAIS TOPICOS', styles['Secao']))
    story.append(Paragraph(
        'O conteudo programatico da disciplina esta organizado nas seguintes unidades:',
        styles['CorpoMaterial']
    ))
    story.append(Spacer(1, 4))
    for topico in conteudo.get('topicos', []):
        story.append(Paragraph(f'\u2022 {topico}', styles['ItemLista']))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        'Cada unidade aborda um aspecto fundamental da disciplina, construindo '
        'progressivamente o conhecimento necessario para dominar o tema. '
        'Recomenda-se estudar as unidades na ordem apresentada.',
        styles['CorpoMaterial']
    ))

    story.append(PageBreak())

    # ---- 5. Exercicios de Fixacao ----
    story.append(Paragraph('4. EXERCICIOS DE FIXACAO', styles['Secao']))
    story.append(Paragraph(
        'Resolva os exercicios abaixo para verificar seu entendimento dos conceitos apresentados.',
        styles['CorpoMaterial']
    ))
    story.append(Spacer(1, 6))

    for i, ex in enumerate(conteudo.get('exercicios', []), 1):
        tipo_label = 'Multipla Escolha' if ex.get('tipo') == 'multipla_escolha' else 'Dissertativa'
        story.append(Paragraph(
            f'<b>Questao {i}</b> ({tipo_label})',
            styles['Exercicio']
        ))
        story.append(Paragraph(ex['enunciado'], styles['CorpoMaterial']))

        if ex.get('alternativas'):
            for alt in ex['alternativas']:
                story.append(Paragraph(f'    {alt}', styles['ItemLista']))

        story.append(Spacer(1, 6))

    # ---- 6. Dicas de Estudo e Recursos Adicionais ----
    story.append(Paragraph('5. DICAS DE ESTUDO E RECURSOS ADICIONAIS', styles['Secao']))
    story.append(Paragraph(
        'Para maximizar seu aprendizado nesta disciplina, siga estas recomendacoes:',
        styles['CorpoMaterial']
    ))
    for dica in conteudo.get('dicas_estudo', []):
        story.append(Paragraph(f'\u2022 {dica}', styles['ItemLista']))

    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>Bibliografia Recomendada:</b>', styles['CorpoMaterial']))
    for ref in conteudo.get('bibliografia', []):
        story.append(Paragraph(f'\u2022 {ref}', styles['ItemLista']))

    story.append(PageBreak())

    # ---- 7. Glossario de Termos Importantes ----
    story.append(Paragraph('6. GLOSSARIO DE TERMOS IMPORTANTES', styles['Secao']))
    story.append(Paragraph(
        'Consulte este glossario sempre que encontrar um termo desconhecido durante seus estudos.',
        styles['CorpoMaterial']
    ))
    story.append(Spacer(1, 6))

    for termo in conteudo.get('glossario', []):
        if ':' in termo:
            parts = termo.split(':', 1)
            story.append(Paragraph(
                f'\u2022 <b>{parts[0].strip()}</b>: {parts[1].strip()}',
                styles['GlossarioTermo']
            ))
        else:
            story.append(Paragraph(f'\u2022 {termo}', styles['GlossarioTermo']))

    # Rodape
    story.append(Spacer(1, 20))
    line_data2 = [['']]
    line_table2 = Table(line_data2, colWidths=[doc.width])
    line_table2.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1, colors.HexColor('#1a5276')),
    ]))
    story.append(line_table2)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f'{INSTITUICAO} - {CURSO_GRAD} - Material de Estudo: {disciplina}',
        styles['Rodape']
    ))

    doc.build(story)
    return True


# ============================================================
# Main
# ============================================================
def main():
    styles = get_styles()
    total = 0

    print('=== Gerando material didatico de graduacao — Semestres 1 a 4 ===')
    print(f'Disciplinas: {sum(len(d) for d in GRADE_SEM1A4.values())}')
    print(f'Saida: {os.path.join(OUTPUT_DIR, "privado", "graduacao", CURSO_ID_GRAD)}')
    print()

    for semestre_key, disciplinas in GRADE_SEM1A4.items():
        semestre_num = int(semestre_key.split('_')[0])
        print(f'--- {semestre_num}o Semestre ---')

        for disciplina in disciplinas:
            filename = sanitize_filename(disciplina) + '_material.pdf'
            out_dir = os.path.join(OUTPUT_DIR, 'privado', 'graduacao', CURSO_ID_GRAD)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, filename)

            ok = gerar_material_pdf(disciplina, semestre_num, out_path, styles)
            if ok:
                total += 1
                print(f'  [{semestre_num}o sem] {disciplina} -> {filename}')
            else:
                print(f'  [{semestre_num}o sem] FALHA: {disciplina}')

    print(f'\nDone!')
    print(f'  Total de PDFs gerados: {total}')
    print(f'  Diretorio: {os.path.join(OUTPUT_DIR, "privado", "graduacao", CURSO_ID_GRAD)}')


if __name__ == '__main__':
    main()
