"""
Gera PDFs de EMAIL/NEWSLETTER resumo para disciplinas de graduacao.
Estilo newsletter academica — 1-2 paginas max, leitura rapida.

Cada PDF tem:
1. Header: "Newsletter Academica - {Disciplina}" com info do semestre
2. "Destaques da Disciplina" — 3-4 bullet points
3. "O que voce vai aprender" — paragrafo resumo
4. "Dica do Professor" — dica pratica
5. "Recursos Recomendados" — 2-3 links/livros
6. "Proximo Passo" — proxima disciplina no curriculo
7. Footer institucional

Saida: output/apostilas/privado/graduacao/eng-software/{disciplina}_email.pdf

Uso: source .env && python3 scripts/gerar_email_graduacao.py
"""
import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors

# ============================================================
# Constantes
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output', 'apostilas')

INSTITUICAO = 'Instituicao de Ensino Demo'
CURSO_GRAD = 'Engenharia de Software'
CURSO_ID_GRAD = 'eng-software'
SEMESTRE_INFO = '2026.1'

# ============================================================
# Grade curricular — 8 semestres, 40 disciplinas
# ============================================================
GRADE_CURRICULAR = {
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
    '5_semestre': [
        'DevOps e Cloud Computing',
        'Inteligencia Artificial',
        'Seguranca da Informacao',
        'Metodologias Ageis',
        'Estagio Supervisionado I',
    ],
    '6_semestre': [
        'Microsservicos e APIs',
        'Machine Learning',
        'Gestao de Projetos',
        'UX/UI Design',
        'Estagio Supervisionado II',
    ],
    '7_semestre': [
        'Computacao em Nuvem Avancada',
        'Big Data',
        'Empreendedorismo Digital',
        'Etica em TI',
        'TCC I',
    ],
    '8_semestre': [
        'IoT e Sistemas Embarcados',
        'Blockchain',
        'Inovacao Tecnologica',
        'TCC II',
        'Projeto Final',
    ],
}


# ============================================================
# Conteudo de email/newsletter por disciplina
# Cada entrada: destaques, resumo, dica, recursos, proximo_passo
# ============================================================
EMAIL_CONTENT = {
    # ---- SEMESTRE 1 ----
    'Introducao a Programacao (Python)': {
        'destaques': [
            'Linguagem mais usada no mundo para iniciantes e profissionais',
            'Base para todas as disciplinas de programacao do curso',
            'Python e usado em IA, web, automacao, data science e muito mais',
            'Voce vai criar seus primeiros programas funcionais desde a semana 1',
        ],
        'resumo': (
            'Nesta disciplina voce vai aprender os fundamentos da programacao usando Python, '
            'uma das linguagens mais versateis e demandadas do mercado. Comecando por variaveis, '
            'tipos de dados e estruturas de controle, voce avanca ate funcoes, listas, dicionarios '
            'e manipulacao de arquivos. Ao final, estara apto a resolver problemas computacionais '
            'e construir pequenos projetos.'
        ),
        'dica': (
            'Pratique todos os dias, mesmo que por 20 minutos. Programacao e como um idioma: '
            'quanto mais voce pratica, mais fluente fica. Use o Python Tutor (pythontutor.com) '
            'para visualizar a execucao do seu codigo passo a passo.'
        ),
        'recursos': [
            'Livro: "Automatize Tarefas Macantes com Python" - Al Sweigart (gratuito online)',
            'Site: realpython.com — tutoriais praticos e atualizados',
            'Plataforma: HackerRank Python Track — exercicios progressivos',
        ],
        'proximo_passo': 'Estrutura de Dados (2o semestre) — onde voce vai organizar dados de forma eficiente',
    },
    'Logica Matematica': {
        'destaques': [
            'Fundamento essencial para algoritmos e resolucao de problemas',
            'Proposicoes, tabelas-verdade e algebra booleana',
            'Base para circuitos digitais e banco de dados',
            'Desenvolve o raciocinio logico que todo programador precisa',
        ],
        'resumo': (
            'Logica Matematica ensina voce a pensar de forma estruturada e rigorosa. '
            'Voce vai dominar proposicoes, conectivos logicos, tabelas-verdade, quantificadores '
            'e tecnicas de demonstracao. Esses conceitos sao a base para entender como computadores '
            'tomam decisoes e como construir algoritmos corretos.'
        ),
        'dica': (
            'Sempre que estiver em duvida sobre um problema logico, monte a tabela-verdade. '
            'Parece trabalhoso, mas e o metodo mais seguro para verificar se seu raciocinio esta correto. '
            'Com o tempo, voce vai internalizar os padroes.'
        ),
        'recursos': [
            'Livro: "Logica de Programacao" - Andre Forbellone',
            'Video: Canal Neso Academy — Logic Gates e Boolean Algebra',
            'Ferramenta: truth-table-generator.com para praticar',
        ],
        'proximo_passo': 'Fundamentos de Computacao (1o semestre) — complementa com arquitetura de hardware',
    },
    'Calculo I': {
        'destaques': [
            'Limites, derivadas e integrais — a matematica por tras da tecnologia',
            'Essencial para otimizacao, machine learning e computacao grafica',
            'Desenvolve pensamento analitico e resolucao de problemas complexos',
            'Pre-requisito para Calculo II e Estatistica',
        ],
        'resumo': (
            'Calculo I apresenta os conceitos fundamentais de limites, continuidade, derivadas '
            'e integrais. Embora pareca abstrato, esses conceitos sao aplicados em otimizacao de '
            'algoritmos, machine learning (gradiente descendente), computacao grafica e analise '
            'de desempenho de sistemas. E a matematica que faz a tecnologia funcionar.'
        ),
        'dica': (
            'Nao decore formulas — entenda o conceito por tras. Derivada e taxa de variacao, '
            'integral e acumulo. Quando voce entende o "por que", as formulas fazem sentido. '
            'Use o Wolfram Alpha para verificar seus calculos.'
        ),
        'recursos': [
            'Livro: "Calculo Vol. 1" - James Stewart',
            'Video: Khan Academy — Calculus (legendas em portugues)',
            'App: Photomath — resolve e explica passo a passo',
        ],
        'proximo_passo': 'Calculo II (2o semestre) — integrais avancadas e series',
    },
    'Comunicacao e Expressao': {
        'destaques': [
            'Comunicacao clara e diferencial competitivo na area de TI',
            'Redacao tecnica, apresentacoes e documentacao de projetos',
            'Habilidade essencial para trabalho em equipe e lideranca',
            'Melhora sua capacidade de argumentacao e escrita profissional',
        ],
        'resumo': (
            'Esta disciplina desenvolve suas habilidades de comunicacao escrita e oral no contexto '
            'profissional de TI. Voce vai aprender a redigir documentacao tecnica, emails profissionais, '
            'relatorios de projeto e a fazer apresentacoes eficazes. Saber comunicar ideias complexas '
            'de forma simples e o que diferencia bons profissionais de excelentes profissionais.'
        ),
        'dica': (
            'Leia bastante — artigos tecnicos, blogs de engenharia de grandes empresas (Netflix, Google, '
            'Spotify). Alem de aprender tecnologia, voce absorve bons padroes de escrita tecnica. '
            'Pratique explicar conceitos complexos em 3 frases simples.'
        ),
        'recursos': [
            'Livro: "Comunicacao e Expressao" - Maria Margarida de Andrade',
            'Blog: engineering.atspotify.com — exemplos de escrita tecnica',
            'Ferramenta: Grammarly (versao gratuita) para revisar textos em ingles',
        ],
        'proximo_passo': 'Metodologias Ageis (5o semestre) — comunicacao aplicada em times de desenvolvimento',
    },
    'Fundamentos de Computacao': {
        'destaques': [
            'Entenda como o computador funciona por dentro',
            'Arquitetura de Von Neumann, binario, portas logicas',
            'Base para Sistemas Operacionais e Redes',
            'Conecta hardware e software de forma pratica',
        ],
        'resumo': (
            'Fundamentos de Computacao apresenta a base de como os computadores funcionam: '
            'representacao binaria, arquitetura de processadores, memoria, entrada/saida e '
            'a evolucao historica da computacao. Entender o hardware e essencial para escrever '
            'software eficiente e tomar decisoes arquiteturais informadas.'
        ),
        'dica': (
            'Converta numeros entre binario, octal, decimal e hexadecimal ate virar automatico. '
            'Isso vai te ajudar em debugging, redes, seguranca e programacao de baixo nivel. '
            'Tente montar um computador virtual no simulador Logisim.'
        ),
        'recursos': [
            'Livro: "Organizacao Estruturada de Computadores" - Tanenbaum',
            'Simulador: Logisim — monte circuitos logicos visualmente',
            'Video: Crash Course Computer Science (YouTube, legendado)',
        ],
        'proximo_passo': 'Sistemas Operacionais (2o semestre) — como o SO gerencia o hardware',
    },
    # ---- SEMESTRE 2 ----
    'Estrutura de Dados': {
        'destaques': [
            'Listas, pilhas, filas, arvores e grafos — organize dados como um pro',
            'Disciplina mais cobrada em entrevistas tecnicas de emprego',
            'Melhora drasticamente a qualidade do seu codigo',
            'Base para algoritmos eficientes e sistemas escaláveis',
        ],
        'resumo': (
            'Estrutura de Dados ensina como organizar e manipular dados de forma eficiente. '
            'Voce vai implementar listas encadeadas, pilhas, filas, arvores binarias, tabelas hash '
            'e grafos. Entender quando usar cada estrutura e o que separa um programador junior '
            'de um senior. E tambem o tema mais cobrado em processos seletivos de big techs.'
        ),
        'dica': (
            'Implemente cada estrutura do zero, sem copiar codigo. Depois compare com implementacoes '
            'prontas. Resolva pelo menos 2 problemas por semana no LeetCode focando em estruturas '
            'de dados. Isso vai acelerar muito seu aprendizado.'
        ),
        'recursos': [
            'Livro: "Estruturas de Dados e Algoritmos em Python" - Goodrich',
            'Plataforma: LeetCode.com — problemas organizados por estrutura',
            'Visualizador: visualgo.net — animacoes de estruturas de dados',
        ],
        'proximo_passo': 'Banco de Dados I (2o semestre) — armazenamento persistente de dados',
    },
    'Programacao Orientada a Objetos': {
        'destaques': [
            'Paradigma dominante no desenvolvimento de software corporativo',
            'Classes, heranca, polimorfismo, encapsulamento e abstracao',
            'Padrao em Java, C#, Python e praticamente toda linguagem moderna',
            'Fundamental para frameworks como Spring, Django e .NET',
        ],
        'resumo': (
            'POO e o paradigma de programacao mais usado no mercado. Voce vai aprender a modelar '
            'problemas do mundo real usando classes e objetos, aplicar heranca e polimorfismo para '
            'reutilizar codigo, e usar encapsulamento para proteger dados. Esses conceitos sao a base '
            'de frameworks modernos e arquiteturas de software profissionais.'
        ),
        'dica': (
            'Pense em objetos do mundo real antes de codar. Um "Carro" tem atributos (cor, modelo) '
            'e metodos (acelerar, frear). Quando voce modela bem, o codigo praticamente se escreve. '
            'Pratique com projetos pequenos: um sistema de biblioteca, um jogo simples.'
        ),
        'recursos': [
            'Livro: "Use a Cabeca! Padroes de Projetos" - Freeman & Robson',
            'Curso: MOOC da USP sobre POO em Java (Coursera)',
            'Pratica: Codewars.com — katas de OOP',
        ],
        'proximo_passo': 'Engenharia de Software I (3o semestre) — aplicar OOP em projetos reais',
    },
    'Calculo II': {
        'destaques': [
            'Integrais multiplas, series e equacoes diferenciais',
            'Aplicacoes em simulacao, modelagem e computacao cientifica',
            'Complementa Calculo I com ferramentas matematicas avancadas',
            'Importante para areas como computacao grafica e IA',
        ],
        'resumo': (
            'Calculo II aprofunda os conceitos de integracao e introduz series infinitas, '
            'sequencias e equacoes diferenciais. Esses topicos sao aplicados em modelagem '
            'computacional, simulacoes fisicas, processamento de sinais e algoritmos de '
            'otimizacao avancados usados em inteligencia artificial.'
        ),
        'dica': (
            'Revise bem Calculo I antes de comecar. Series e integrais multiplas constroem '
            'sobre derivadas e integrais simples. Faca muitos exercicios — em calculo, '
            'a pratica e mais importante que a teoria.'
        ),
        'recursos': [
            'Livro: "Calculo Vol. 2" - James Stewart',
            'Video: 3Blue1Brown — Essence of Calculus (YouTube)',
            'Ferramenta: Wolfram Alpha para verificar integrais',
        ],
        'proximo_passo': 'Estatistica (3o semestre) — analise de dados e probabilidade',
    },
    'Banco de Dados I': {
        'destaques': [
            'SQL e o idioma universal dos dados — toda empresa usa',
            'Modelagem relacional, normalizacao e consultas complexas',
            'Habilidade obrigatoria para qualquer desenvolvedor',
            'Base para Banco de Dados II e desenvolvimento backend',
        ],
        'resumo': (
            'Banco de Dados I ensina a projetar, criar e consultar bancos de dados relacionais. '
            'Voce vai dominar SQL (SELECT, JOIN, GROUP BY, subqueries), modelagem ER, normalizacao '
            'e transacoes. Praticamente todo sistema de software precisa de um banco de dados, '
            'tornando essa uma das habilidades mais valorizadas do mercado.'
        ),
        'dica': (
            'Instale o PostgreSQL ou MySQL no seu computador e pratique com dados reais. '
            'Crie um banco para algo que voce gosta: filmes, jogos, receitas. Quando os dados '
            'sao interessantes, aprender SQL fica muito mais divertido.'
        ),
        'recursos': [
            'Livro: "Sistemas de Banco de Dados" - Elmasri & Navathe',
            'Pratica: SQLZoo.net — exercicios interativos de SQL',
            'Ferramenta: DBeaver — cliente SQL gratuito e poderoso',
        ],
        'proximo_passo': 'Banco de Dados II (3o semestre) — NoSQL, indexacao e otimizacao',
    },
    'Sistemas Operacionais': {
        'destaques': [
            'Entenda como Linux, Windows e macOS gerenciam recursos',
            'Processos, threads, memoria virtual e sistemas de arquivos',
            'Essencial para DevOps, cloud computing e programacao de sistemas',
            'Conhecimento que diferencia desenvolvedores de alto nivel',
        ],
        'resumo': (
            'Sistemas Operacionais revela como o SO gerencia processos, memoria, armazenamento '
            'e dispositivos de E/S. Voce vai entender escalonamento de processos, sincronizacao, '
            'deadlocks, memoria virtual e sistemas de arquivos. Esse conhecimento e crucial para '
            'otimizar aplicacoes, trabalhar com containers e entender infraestrutura cloud.'
        ),
        'dica': (
            'Use Linux no dia a dia (pode ser WSL no Windows). Explore comandos como ps, top, '
            'htop, strace e lsof. Entender o SO na pratica e muito mais eficaz do que so ler teoria. '
            'Tente compilar o kernel do Linux pelo menos uma vez.'
        ),
        'recursos': [
            'Livro: "Sistemas Operacionais Modernos" - Tanenbaum',
            'Pratica: OverTheWire Bandit — desafios Linux progressivos',
            'Distro: Ubuntu ou Fedora para uso diario',
        ],
        'proximo_passo': 'Redes de Computadores (3o semestre) — como maquinas se comunicam',
    },
    # ---- SEMESTRE 3 ----
    'Engenharia de Software I': {
        'destaques': [
            'Aprenda a desenvolver software de forma profissional e organizada',
            'Requisitos, modelagem UML, ciclo de vida de software',
            'Metodologias de desenvolvimento: cascata, iterativo, agil',
            'Base para trabalhar em equipes de desenvolvimento reais',
        ],
        'resumo': (
            'Engenharia de Software I ensina os processos e praticas para desenvolver software '
            'de qualidade. Voce vai aprender a levantar requisitos, modelar sistemas com UML, '
            'escolher metodologias de desenvolvimento e gerenciar o ciclo de vida do software. '
            'E a disciplina que transforma programadores em engenheiros de software.'
        ),
        'dica': (
            'Participe de projetos open source no GitHub. Voce vai ver na pratica como equipes '
            'reais organizam codigo, documentam requisitos e fazem code review. Comece com issues '
            'marcadas como "good first issue".'
        ),
        'recursos': [
            'Livro: "Engenharia de Software" - Ian Sommerville',
            'Ferramenta: draw.io — diagramas UML gratuitos',
            'Comunidade: GitHub — projetos open source para contribuir',
        ],
        'proximo_passo': 'Engenharia de Software II (4o semestre) — padroes de projeto e arquitetura',
    },
    'Redes de Computadores': {
        'destaques': [
            'TCP/IP, HTTP, DNS — entenda como a internet funciona',
            'Modelo OSI, roteamento, protocolos e seguranca de rede',
            'Essencial para desenvolvimento web, cloud e DevOps',
            'Conhecimento valorizado em todas as areas de TI',
        ],
        'resumo': (
            'Redes de Computadores explica como dispositivos se comunicam. Voce vai entender '
            'o modelo OSI/TCP-IP, protocolos (HTTP, DNS, DHCP, TCP, UDP), roteamento, switching '
            'e fundamentos de seguranca de rede. Esse conhecimento e indispensavel para '
            'desenvolvimento web, cloud computing e troubleshooting de sistemas.'
        ),
        'dica': (
            'Instale o Wireshark e capture pacotes da sua propria navegacao. Ver os pacotes HTTP, '
            'DNS e TCP em tempo real torna os conceitos abstratos muito concretos. '
            'Faca o laboratorio pratico do Cisco Packet Tracer (gratuito).'
        ),
        'recursos': [
            'Livro: "Redes de Computadores" - Kurose & Ross',
            'Ferramenta: Wireshark — analise de pacotes de rede',
            'Simulador: Cisco Packet Tracer — laboratorio virtual de redes',
        ],
        'proximo_passo': 'Seguranca da Informacao (5o semestre) — proteger redes e sistemas',
    },
    'Estatistica': {
        'destaques': [
            'Probabilidade, distribuicoes, testes de hipotese e regressao',
            'Base fundamental para Data Science e Machine Learning',
            'Tomada de decisao baseada em dados — habilidade do seculo XXI',
            'Aplicacoes em testes A/B, analise de desempenho e qualidade',
        ],
        'resumo': (
            'Estatistica ensina a coletar, analisar e interpretar dados de forma rigorosa. '
            'Voce vai aprender probabilidade, distribuicoes, intervalos de confianca, testes '
            'de hipotese e regressao. Esses conceitos sao a base de data science, machine learning '
            'e qualquer decisao baseada em dados no mundo corporativo.'
        ),
        'dica': (
            'Use Python (pandas + matplotlib) para praticar estatistica com dados reais. '
            'Baixe datasets do Kaggle e faca analises exploratórias. Estatistica so faz sentido '
            'quando voce aplica em dados de verdade, nao em exercicios artificiais.'
        ),
        'recursos': [
            'Livro: "Estatistica Basica" - Bussab & Morettin',
            'Plataforma: Kaggle.com — datasets e competicoes',
            'Curso: Statistics with Python (Coursera, University of Michigan)',
        ],
        'proximo_passo': 'Machine Learning (6o semestre) — estatistica aplicada a inteligencia artificial',
    },
    'Banco de Dados II': {
        'destaques': [
            'NoSQL (MongoDB, Redis, DynamoDB), indexacao e otimizacao',
            'Bancos distribuidos, replicacao e consistencia eventual',
            'Complementa BD I com tecnologias modernas de armazenamento',
            'Essencial para arquiteturas de microsservicos e big data',
        ],
        'resumo': (
            'Banco de Dados II vai alem do modelo relacional, apresentando bancos NoSQL '
            '(documento, chave-valor, colunar, grafo), tecnicas de indexacao avancada, '
            'otimizacao de queries, bancos distribuidos e o teorema CAP. Voce vai entender '
            'quando usar SQL vs NoSQL e como projetar para escala.'
        ),
        'dica': (
            'Crie um projeto que use tanto PostgreSQL quanto MongoDB. Compare as abordagens '
            'para o mesmo problema. Entender os trade-offs na pratica e muito mais valioso '
            'do que decorar teoria sobre CAP theorem.'
        ),
        'recursos': [
            'Livro: "Designing Data-Intensive Applications" - Martin Kleppmann',
            'Pratica: MongoDB University — cursos gratuitos oficiais',
            'Ferramenta: Redis — instale e experimente como cache',
        ],
        'proximo_passo': 'Desenvolvimento Web (3o semestre) — usar bancos em aplicacoes reais',
    },
    'Desenvolvimento Web': {
        'destaques': [
            'HTML, CSS, JavaScript — a triade da web moderna',
            'Frontend (React/Vue) e Backend (Node/Django) na pratica',
            'APIs REST, responsividade e deploy de aplicacoes',
            'Habilidade com alta demanda e muitas oportunidades',
        ],
        'resumo': (
            'Desenvolvimento Web ensina a criar aplicacoes web completas, do frontend ao backend. '
            'Voce vai dominar HTML5, CSS3, JavaScript moderno, frameworks frontend, APIs REST '
            'e integracao com banco de dados. A web e a plataforma mais universal de software '
            'e saber desenvolver para ela abre portas em praticamente qualquer empresa.'
        ),
        'dica': (
            'Crie um portfolio pessoal e publique no GitHub Pages. Cada projeto que voce faz '
            'e uma peca do seu portfolio. Recrutadores olham GitHub antes do curriculo. '
            'Comece simples e va adicionando complexidade aos poucos.'
        ),
        'recursos': [
            'Site: MDN Web Docs (developer.mozilla.org) — referencia completa',
            'Curso: The Odin Project — curriculo completo e gratuito',
            'Pratica: Frontend Mentor — desafios de UI com designs prontos',
        ],
        'proximo_passo': 'Desenvolvimento Mobile (4o semestre) — levar suas apps para celulares',
    },
    # ---- SEMESTRE 4 ----
    'Engenharia de Software II': {
        'destaques': [
            'Padroes de projeto (Design Patterns) — solucoes consagradas',
            'Refatoracao, code smells e qualidade de codigo',
            'Arquitetura de sistemas e decisoes de design',
            'Prepara para liderar projetos de software complexos',
        ],
        'resumo': (
            'Engenharia de Software II aprofunda os conceitos de design de software com padroes '
            'de projeto (GoF), principios SOLID, refatoracao e metricas de qualidade. Voce vai '
            'aprender a tomar decisoes arquiteturais informadas e a evoluir sistemas existentes '
            'sem quebrar funcionalidades. E o que transforma codigo em software de qualidade.'
        ),
        'dica': (
            'Estude os padroes de projeto mais usados: Strategy, Observer, Factory, Singleton '
            'e Decorator. Nao tente decorar todos os 23 do GoF — foque nos que voce vai usar '
            'no dia a dia. Identifique padroes em frameworks que voce ja usa.'
        ),
        'recursos': [
            'Livro: "Padroes de Projetos" - Gamma, Helm, Johnson, Vlissides (GoF)',
            'Site: refactoring.guru — padroes explicados com exemplos visuais',
            'Livro: "Clean Code" - Robert C. Martin',
        ],
        'proximo_passo': 'Arquitetura de Software (4o semestre) — visao macro de sistemas',
    },
    'Arquitetura de Software': {
        'destaques': [
            'Monolito vs microsservicos vs serverless — quando usar cada um',
            'Estilos arquiteturais: MVC, hexagonal, event-driven, CQRS',
            'Decisoes que impactam escalabilidade, custo e manutencao',
            'Habilidade de arquiteto — uma das mais valorizadas em TI',
        ],
        'resumo': (
            'Arquitetura de Software ensina a projetar a estrutura macro de sistemas. Voce vai '
            'estudar estilos arquiteturais (camadas, microsservicos, event-driven, serverless), '
            'atributos de qualidade (escalabilidade, disponibilidade, seguranca) e como documentar '
            'decisoes arquiteturais. E a disciplina que prepara voce para cargos de lideranca tecnica.'
        ),
        'dica': (
            'Leia postmortem de incidentes de grandes empresas (Google SRE book, Netflix tech blog). '
            'Entender o que deu errado em sistemas reais ensina mais sobre arquitetura do que '
            'qualquer livro teorico. Desenhe diagramas de arquitetura para tudo que voce constroi.'
        ),
        'recursos': [
            'Livro: "Fundamentals of Software Architecture" - Richards & Ford',
            'Blog: Netflix Tech Blog — arquitetura em escala',
            'Ferramenta: C4 Model (c4model.com) — diagramas de arquitetura',
        ],
        'proximo_passo': 'Microsservicos e APIs (6o semestre) — implementar arquiteturas distribuidas',
    },
    'Testes de Software': {
        'destaques': [
            'Testes unitarios, integracao, E2E e TDD na pratica',
            'Qualidade de software e responsabilidade de todo desenvolvedor',
            'Ferramentas: pytest, JUnit, Selenium, Jest',
            'Empresas top exigem cobertura de testes — diferencial competitivo',
        ],
        'resumo': (
            'Testes de Software ensina a garantir que seu codigo funciona corretamente. Voce vai '
            'aprender testes unitarios, de integracao, end-to-end, TDD (Test-Driven Development) '
            'e BDD. Vai usar ferramentas profissionais como pytest, JUnit e Selenium. Testar '
            'nao e opcional — e parte essencial do desenvolvimento profissional.'
        ),
        'dica': (
            'Adote TDD em pelo menos um projeto: escreva o teste antes do codigo. No inicio '
            'parece lento, mas rapidamente voce percebe que produz codigo mais limpo e com menos '
            'bugs. Comece com testes unitarios simples e va aumentando a complexidade.'
        ),
        'recursos': [
            'Livro: "Test Driven Development" - Kent Beck',
            'Ferramenta: pytest — framework de testes Python mais popular',
            'Curso: "Testing JavaScript" - Kent C. Dodds (testingjavascript.com)',
        ],
        'proximo_passo': 'DevOps e Cloud Computing (5o semestre) — automatizar testes no pipeline CI/CD',
    },
    'Desenvolvimento Mobile': {
        'destaques': [
            'Apps nativas (Swift/Kotlin) e cross-platform (Flutter/React Native)',
            'UI/UX mobile, gestos, notificacoes e armazenamento local',
            'Mercado mobile continua crescendo — bilhoes de dispositivos',
            'Publique seu primeiro app nas lojas (Play Store / App Store)',
        ],
        'resumo': (
            'Desenvolvimento Mobile ensina a criar aplicativos para smartphones e tablets. '
            'Voce vai aprender desenvolvimento nativo e cross-platform, design de interfaces '
            'mobile, gerenciamento de estado, consumo de APIs, armazenamento local e publicacao '
            'nas lojas. O mobile e a plataforma onde as pessoas passam mais tempo.'
        ),
        'dica': (
            'Escolha Flutter ou React Native para comecar — voce cria apps para Android e iOS '
            'com um unico codigo. Publique pelo menos um app na Play Store (custa $25 uma vez). '
            'Ter um app publicado no curriculo impressiona muito recrutadores.'
        ),
        'recursos': [
            'Documentacao: flutter.dev — guia oficial do Flutter',
            'Curso: CS193p Stanford — desenvolvimento iOS (gratuito)',
            'Comunidade: r/FlutterDev — dicas e projetos da comunidade',
        ],
        'proximo_passo': 'UX/UI Design (6o semestre) — design profissional para suas apps',
    },
    'Projeto Integrador I': {
        'destaques': [
            'Primeiro projeto real integrando multiplas disciplinas',
            'Trabalho em equipe com metodologia agil',
            'Desenvolvimento completo: requisitos, codigo, testes, apresentacao',
            'Experiencia pratica que simula o ambiente profissional',
        ],
        'resumo': (
            'O Projeto Integrador I e sua primeira experiencia de desenvolvimento completo em equipe. '
            'Voce vai aplicar conhecimentos de programacao, banco de dados, engenharia de software '
            'e testes para construir um sistema funcional. O projeto segue metodologia agil com '
            'sprints, entregas parciais e apresentacao final.'
        ),
        'dica': (
            'Defina bem o escopo no inicio — projetos integradores falham mais por escopo ambicioso '
            'do que por falta de habilidade tecnica. Use Git desde o dia 1, faca commits frequentes '
            'e documente tudo. A organizacao da equipe e tao importante quanto o codigo.'
        ),
        'recursos': [
            'Ferramenta: Trello ou Jira — gerenciamento de tarefas',
            'Ferramenta: Git + GitHub — controle de versao colaborativo',
            'Template: README.md padrao para projetos academicos',
        ],
        'proximo_passo': 'Estagio Supervisionado I (5o semestre) — experiencia no mercado real',
    },
    # ---- SEMESTRE 5 ----
    'DevOps e Cloud Computing': {
        'destaques': [
            'CI/CD, Docker, Kubernetes — automatize tudo',
            'AWS, Azure, GCP — as 3 grandes plataformas cloud',
            'Infraestrutura como codigo (Terraform, CloudFormation)',
            'Uma das areas com maiores salarios em TI atualmente',
        ],
        'resumo': (
            'DevOps e Cloud Computing ensina a automatizar o ciclo de vida do software, '
            'desde o commit ate a producao. Voce vai aprender CI/CD, containers (Docker), '
            'orquestracao (Kubernetes), infraestrutura como codigo e servicos cloud. '
            'DevOps e a ponte entre desenvolvimento e operacoes, e cloud e onde tudo roda.'
        ),
        'dica': (
            'Crie uma conta gratuita na AWS (Free Tier) e faca deploy de uma aplicacao real. '
            'Nada substitui a experiencia de configurar um pipeline CI/CD de verdade. '
            'Comece com GitHub Actions — e gratuito e integrado ao GitHub.'
        ),
        'recursos': [
            'Certificacao: AWS Cloud Practitioner (nivel inicial)',
            'Livro: "The Phoenix Project" - Gene Kim (DevOps em forma de romance)',
            'Pratica: KodeKloud — laboratorios praticos de DevOps',
        ],
        'proximo_passo': 'Computacao em Nuvem Avancada (7o semestre) — arquiteturas cloud complexas',
    },
    'Inteligencia Artificial': {
        'destaques': [
            'Busca, logica, aprendizado de maquina e redes neurais',
            'A area mais quente da tecnologia — oportunidades explosivas',
            'Aplicacoes: chatbots, visao computacional, NLP, robotica',
            'Base para Machine Learning e Deep Learning',
        ],
        'resumo': (
            'Inteligencia Artificial apresenta os fundamentos de sistemas inteligentes: '
            'agentes, busca, representacao de conhecimento, aprendizado de maquina e redes '
            'neurais. Voce vai entender como funcionam chatbots, sistemas de recomendacao, '
            'carros autonomos e assistentes virtuais. E a disciplina que abre portas para '
            'o futuro da tecnologia.'
        ),
        'dica': (
            'Comece com projetos praticos usando APIs de IA (OpenAI, Hugging Face). '
            'Nao espere dominar toda a matematica antes de comecar — aprenda fazendo. '
            'Participe de competicoes no Kaggle para ganhar experiencia real.'
        ),
        'recursos': [
            'Curso: CS50 AI with Python (Harvard, gratuito)',
            'Livro: "Inteligencia Artificial" - Stuart Russell & Peter Norvig',
            'Plataforma: Hugging Face — modelos de IA prontos para usar',
        ],
        'proximo_passo': 'Machine Learning (6o semestre) — aprofundar em aprendizado de maquina',
    },
    'Seguranca da Informacao': {
        'destaques': [
            'Criptografia, autenticacao, OWASP Top 10 e pentest',
            'Seguranca e responsabilidade de todo desenvolvedor',
            'Area com deficit de profissionais — alta empregabilidade',
            'Proteja sistemas contra ataques reais',
        ],
        'resumo': (
            'Seguranca da Informacao ensina a proteger sistemas, dados e redes contra ameacas. '
            'Voce vai estudar criptografia, autenticacao, autorizacao, vulnerabilidades web '
            '(OWASP Top 10), pentest basico e politicas de seguranca. Todo software precisa '
            'ser seguro, e essa responsabilidade comeca no desenvolvedor.'
        ),
        'dica': (
            'Pratique no OWASP WebGoat e no Hack The Box. Aprender seguranca atacando (de forma '
            'etica e legal) e muito mais eficaz do que so ler sobre defesa. Sempre pense: '
            '"como alguem poderia explorar isso?" ao escrever codigo.'
        ),
        'recursos': [
            'Site: OWASP.org — guias e ferramentas de seguranca',
            'Pratica: Hack The Box — laboratorios de pentest',
            'Certificacao: CompTIA Security+ (nivel inicial)',
        ],
        'proximo_passo': 'Computacao em Nuvem Avancada (7o semestre) — seguranca em ambientes cloud',
    },
    'Metodologias Ageis': {
        'destaques': [
            'Scrum, Kanban, XP — as metodologias que o mercado usa',
            'Sprints, daily standups, retrospectivas e planning poker',
            'Habilidade obrigatoria — 90%+ das empresas de TI sao ageis',
            'Prepara para certificacoes PSM e CSPO',
        ],
        'resumo': (
            'Metodologias Ageis ensina os frameworks e praticas usados por times de desenvolvimento '
            'no mundo todo. Voce vai aprender Scrum (sprints, papeis, cerimonias), Kanban '
            '(fluxo continuo, WIP limits), XP (pair programming, TDD) e como adaptar '
            'metodologias ao contexto do seu time. Agilidade nao e velocidade — e adaptabilidade.'
        ),
        'dica': (
            'Aplique Scrum no seu proximo projeto academico, mesmo que seja individual. '
            'Use um quadro Kanban (Trello) para organizar suas tarefas. A melhor forma de '
            'aprender agil e praticando, nao lendo sobre.'
        ),
        'recursos': [
            'Guia: Scrum Guide oficial (scrumguides.org) — leitura obrigatoria',
            'Certificacao: PSM I (Professional Scrum Master) — Scrum.org',
            'Livro: "Scrum: A Arte de Fazer o Dobro na Metade do Tempo" - Jeff Sutherland',
        ],
        'proximo_passo': 'Gestao de Projetos (6o semestre) — gerenciar projetos completos',
    },
    'Estagio Supervisionado I': {
        'destaques': [
            'Primeira experiencia profissional supervisionada',
            'Aplique na pratica o que aprendeu em 4 semestres',
            'Networking, mentoria e vivencia corporativa',
            'Muitos estagios se convertem em emprego efetivo',
        ],
        'resumo': (
            'O Estagio Supervisionado I e sua porta de entrada para o mercado de trabalho. '
            'Voce vai atuar em uma empresa real, aplicando conhecimentos de programacao, '
            'banco de dados, engenharia de software e metodologias ageis. Alem da experiencia '
            'tecnica, voce desenvolve soft skills essenciais: comunicacao, trabalho em equipe '
            'e gestao de tempo.'
        ),
        'dica': (
            'Seja proativo no estagio — nao espere tarefas, peca. Faca perguntas, anote tudo '
            'e busque um mentor. O estagio e tanto sobre aprender tecnologia quanto sobre '
            'entender como empresas funcionam. Documente suas contribuicoes para o relatorio.'
        ),
        'recursos': [
            'Plataforma: LinkedIn — networking e vagas de estagio',
            'Site: Glassdoor — avaliacoes de empresas por estagiarios',
            'Livro: "O Programador Pragmatico" - Hunt & Thomas',
        ],
        'proximo_passo': 'Estagio Supervisionado II (6o semestre) — aprofundar a experiencia profissional',
    },
    # ---- SEMESTRE 6 ----
    'Microsservicos e APIs': {
        'destaques': [
            'REST, GraphQL, gRPC — os protocolos de comunicacao modernos',
            'Arquitetura de microsservicos: design, deploy e monitoramento',
            'API Gateway, service mesh, circuit breaker e resiliencia',
            'Padrao dominante em empresas de tecnologia de ponta',
        ],
        'resumo': (
            'Microsservicos e APIs ensina a projetar e implementar sistemas distribuidos modernos. '
            'Voce vai aprender a criar APIs RESTful, usar GraphQL, implementar microsservicos '
            'com comunicacao sincrona e assincrona, e aplicar padroes de resiliencia. '
            'E a arquitetura que Netflix, Amazon e Spotify usam para escalar.'
        ),
        'dica': (
            'Construa um sistema com pelo menos 3 microsservicos que se comunicam. Use Docker '
            'Compose para orquestrar localmente. Implemente um API Gateway simples. A experiencia '
            'pratica com os desafios de sistemas distribuidos e insubstituivel.'
        ),
        'recursos': [
            'Livro: "Building Microservices" - Sam Newman',
            'Ferramenta: Postman — teste e documente suas APIs',
            'Padrao: OpenAPI/Swagger — especificacao de APIs',
        ],
        'proximo_passo': 'Computacao em Nuvem Avancada (7o semestre) — microsservicos em escala cloud',
    },
    'Machine Learning': {
        'destaques': [
            'Regressao, classificacao, clustering e redes neurais',
            'Scikit-learn, TensorFlow, PyTorch — as ferramentas do mercado',
            'Aplicacoes: recomendacao, deteccao de fraude, NLP, visao computacional',
            'Uma das especializacoes mais bem pagas em tecnologia',
        ],
        'resumo': (
            'Machine Learning aprofunda os algoritmos de aprendizado de maquina: regressao linear '
            'e logistica, arvores de decisao, SVM, redes neurais, CNN e RNN. Voce vai implementar '
            'modelos, avaliar performance e fazer deploy. ML esta transformando todas as industrias '
            'e profissionais qualificados sao extremamente demandados.'
        ),
        'dica': (
            'Participe de competicoes no Kaggle — comece com as de nivel "Getting Started". '
            'Nao se preocupe em ganhar, foque em aprender. Leia os notebooks dos vencedores '
            'para entender as melhores praticas. Use Google Colab para treinar modelos de graca.'
        ),
        'recursos': [
            'Curso: Machine Learning (Andrew Ng, Coursera) — o classico',
            'Livro: "Hands-On Machine Learning" - Aurelien Geron',
            'Plataforma: Google Colab — GPUs gratuitas para treinar modelos',
        ],
        'proximo_passo': 'Big Data (7o semestre) — processar dados em escala para ML',
    },
    'Gestao de Projetos': {
        'destaques': [
            'PMBOK, Scrum, Kanban — gerenciar projetos de qualquer tamanho',
            'Escopo, cronograma, custos, riscos e qualidade',
            'Habilidade de lideranca tecnica e gestao de equipes',
            'Prepara para certificacoes PMP e PMI-ACP',
        ],
        'resumo': (
            'Gestao de Projetos ensina a planejar, executar e entregar projetos de software '
            'com sucesso. Voce vai aprender tecnicas do PMBOK (escopo, tempo, custo, qualidade, '
            'riscos) combinadas com praticas ageis. Saber gerenciar projetos e o que leva '
            'desenvolvedores a cargos de lideranca e gestao.'
        ),
        'dica': (
            'Gerencie seu TCC como um projeto real: defina escopo, crie cronograma, identifique '
            'riscos e faca acompanhamento semanal. Use ferramentas como MS Project ou Monday.com. '
            'A pratica de gestao comeca nos seus proprios projetos.'
        ),
        'recursos': [
            'Guia: PMBOK Guide (PMI) — referencia mundial em gestao de projetos',
            'Ferramenta: Monday.com ou Asana — gestao de projetos moderna',
            'Certificacao: CAPM (PMI) — certificacao inicial em gestao de projetos',
        ],
        'proximo_passo': 'Empreendedorismo Digital (7o semestre) — gerenciar seu proprio negocio',
    },
    'UX/UI Design': {
        'destaques': [
            'Design centrado no usuario — crie interfaces que as pessoas amam',
            'Figma, wireframes, prototipos e testes de usabilidade',
            'Habilidade que complementa perfeitamente o perfil de desenvolvedor',
            'Produtos com bom UX vendem mais e retêm mais usuarios',
        ],
        'resumo': (
            'UX/UI Design ensina a criar interfaces digitais intuitivas e agradaveis. Voce vai '
            'aprender pesquisa com usuarios, arquitetura de informacao, wireframing, prototipacao '
            'no Figma, design systems e testes de usabilidade. Um desenvolvedor que entende '
            'design cria produtos melhores e se destaca no mercado.'
        ),
        'dica': (
            'Redesenhe apps que voce usa no dia a dia — identifique problemas de UX e proponha '
            'solucoes. Crie um portfolio no Behance ou Dribbble. Mesmo que voce nao va ser designer, '
            'entender UX faz de voce um desenvolvedor muito melhor.'
        ),
        'recursos': [
            'Ferramenta: Figma (figma.com) — gratuito para uso pessoal',
            'Livro: "Nao Me Faca Pensar" - Steve Krug',
            'Curso: Google UX Design Certificate (Coursera)',
        ],
        'proximo_passo': 'Projeto Final (8o semestre) — aplicar UX no seu projeto de conclusao',
    },
    'Estagio Supervisionado II': {
        'destaques': [
            'Aprofundamento da experiencia profissional',
            'Maior autonomia e responsabilidade no trabalho',
            'Possibilidade de efetivacao e crescimento na empresa',
            'Desenvolvimento de especializacao tecnica',
        ],
        'resumo': (
            'O Estagio Supervisionado II da continuidade a sua experiencia profissional com '
            'maior autonomia e responsabilidade. Voce ja conhece o ambiente corporativo e agora '
            'pode contribuir de forma mais significativa, assumir tarefas complexas e desenvolver '
            'uma area de especializacao. Muitos alunos sao efetivados nesta fase.'
        ),
        'dica': (
            'Proponha melhorias e projetos na empresa — nao espere que te digam o que fazer. '
            'Documente suas contribuicoes com metricas (ex: "reduzi tempo de deploy em 40%"). '
            'Isso fortalece seu curriculo e aumenta chances de efetivacao.'
        ),
        'recursos': [
            'Livro: "O Programador Apaixonado" - Chad Fowler',
            'Plataforma: LinkedIn Learning — cursos para desenvolvimento profissional',
            'Comunidade: Meetups locais de tecnologia — networking presencial',
        ],
        'proximo_passo': 'TCC I (7o semestre) — comecar seu trabalho de conclusao de curso',
    },
    # ---- SEMESTRE 7 ----
    'Computacao em Nuvem Avancada': {
        'destaques': [
            'Arquiteturas serverless, multi-cloud e cloud-native',
            'AWS avancado: Lambda, ECS, EKS, Step Functions, CDK',
            'FinOps — otimizacao de custos em cloud',
            'Certificacoes cloud sao das mais valorizadas do mercado',
        ],
        'resumo': (
            'Computacao em Nuvem Avancada vai alem do basico de cloud, explorando arquiteturas '
            'serverless, containers em producao (ECS/EKS), multi-cloud, disaster recovery, '
            'observabilidade e otimizacao de custos (FinOps). Voce vai projetar e implementar '
            'solucoes cloud de nivel empresarial.'
        ),
        'dica': (
            'Tire pelo menos uma certificacao cloud (AWS Solutions Architect Associate e a mais '
            'reconhecida). Use o Free Tier da AWS para praticar e destrua os recursos depois '
            'para nao gerar custos. Documente suas arquiteturas com diagramas.'
        ),
        'recursos': [
            'Certificacao: AWS Solutions Architect Associate',
            'Plataforma: A Cloud Guru — cursos e laboratorios cloud',
            'Ferramenta: AWS CDK — infraestrutura como codigo em Python/TypeScript',
        ],
        'proximo_passo': 'IoT e Sistemas Embarcados (8o semestre) — cloud + dispositivos fisicos',
    },
    'Big Data': {
        'destaques': [
            'Hadoop, Spark, Kafka — processamento de dados em escala',
            'Data lakes, data warehouses e pipelines de dados',
            'Complementa Machine Learning com dados em volume',
            'Area em crescimento explosivo — toda empresa gera big data',
        ],
        'resumo': (
            'Big Data ensina a processar, armazenar e analisar grandes volumes de dados. '
            'Voce vai aprender ecossistema Hadoop, Apache Spark, Kafka para streaming, '
            'data lakes e data warehouses. Com o volume de dados crescendo exponencialmente, '
            'profissionais de big data sao essenciais em qualquer organizacao data-driven.'
        ),
        'dica': (
            'Instale o Apache Spark localmente e processe um dataset grande (>1GB) do Kaggle. '
            'Compare o tempo de processamento com pandas puro. Essa experiencia pratica '
            'demonstra o valor de ferramentas de big data de forma concreta.'
        ),
        'recursos': [
            'Curso: Big Data Specialization (UC San Diego, Coursera)',
            'Ferramenta: Apache Spark — processamento distribuido',
            'Livro: "Designing Data-Intensive Applications" - Martin Kleppmann',
        ],
        'proximo_passo': 'Blockchain (8o semestre) — dados distribuidos e imutaveis',
    },
    'Empreendedorismo Digital': {
        'destaques': [
            'Lean Startup, MVP, product-market fit e growth hacking',
            'Transforme suas ideias tecnicas em negocios viaveis',
            'Pitch, modelo de negocios (Canvas) e captacao de investimento',
            'Muitas startups de sucesso nasceram em universidades',
        ],
        'resumo': (
            'Empreendedorismo Digital ensina a transformar ideias em negocios de tecnologia. '
            'Voce vai aprender a validar hipoteses com MVP, criar modelos de negocio (Business '
            'Model Canvas), fazer pitch para investidores e aplicar growth hacking. '
            'Mesmo que voce nao abra uma startup, pensar como empreendedor te torna um '
            'profissional mais completo.'
        ),
        'dica': (
            'Identifique um problema real que voce tem e construa um MVP em um fim de semana. '
            'Nao precisa ser perfeito — precisa resolver o problema. Mostre para 10 pessoas '
            'e colete feedback. Esse ciclo de validacao e a essencia do empreendedorismo.'
        ),
        'recursos': [
            'Livro: "A Startup Enxuta" - Eric Ries',
            'Ferramenta: Business Model Canvas (strategyzer.com)',
            'Comunidade: Startup Weekend — eventos de empreendedorismo',
        ],
        'proximo_passo': 'Inovacao Tecnologica (8o semestre) — tendencias e futuro da tecnologia',
    },
    'Etica em TI': {
        'destaques': [
            'LGPD, privacidade, vies algoritmico e responsabilidade social',
            'Dilemas eticos reais: IA, vigilancia, fake news, automacao',
            'Profissionais eticos sao mais valorizados e confiaveis',
            'Regulamentacoes como LGPD e GDPR exigem conhecimento etico',
        ],
        'resumo': (
            'Etica em TI aborda os dilemas morais e legais da tecnologia: privacidade de dados '
            '(LGPD/GDPR), vies em algoritmos de IA, impacto social da automacao, propriedade '
            'intelectual e responsabilidade do desenvolvedor. Em um mundo cada vez mais digital, '
            'profissionais eticos sao essenciais para construir tecnologia que beneficie a todos.'
        ),
        'dica': (
            'Antes de implementar qualquer feature, pergunte: "isso pode prejudicar alguem?" '
            'Leia sobre casos reais de falhas eticas em tecnologia (Cambridge Analytica, '
            'vies racial em IA). Conhecer os erros do passado ajuda a evitar repeti-los.'
        ),
        'recursos': [
            'Lei: LGPD (Lei 13.709/2018) — leitura obrigatoria para profissionais de TI',
            'Documentario: "O Dilema das Redes" (Netflix)',
            'Livro: "Weapons of Math Destruction" - Cathy O\'Neil',
        ],
        'proximo_passo': 'TCC I (7o semestre) — aplicar principios eticos no seu projeto',
    },
    'TCC I': {
        'destaques': [
            'Inicio do Trabalho de Conclusao de Curso',
            'Definicao do tema, revisao bibliografica e metodologia',
            'Orientacao academica individualizada',
            'Oportunidade de se aprofundar em um tema que voce ama',
        ],
        'resumo': (
            'TCC I e o inicio do seu Trabalho de Conclusao de Curso. Voce vai definir o tema, '
            'fazer revisao bibliografica, estabelecer a metodologia e desenvolver o projeto '
            'inicial. E a oportunidade de se aprofundar em uma area que voce gosta e produzir '
            'conhecimento original. O TCC e seu cartao de visita academico.'
        ),
        'dica': (
            'Escolha um tema que voce realmente gosta — voce vai conviver com ele por meses. '
            'Converse com seu orientador regularmente, nao espere a ultima semana. '
            'Comece a escrever desde o primeiro dia — a escrita academica leva tempo.'
        ),
        'recursos': [
            'Ferramenta: Overleaf (LaTeX online) — formatacao academica profissional',
            'Base: Google Scholar — artigos academicos para revisao bibliografica',
            'Ferramenta: Zotero — gerenciador de referencias bibliograficas',
        ],
        'proximo_passo': 'TCC II (8o semestre) — desenvolvimento e defesa do trabalho',
    },
    # ---- SEMESTRE 8 ----
    'IoT e Sistemas Embarcados': {
        'destaques': [
            'Arduino, Raspberry Pi, ESP32 — hardware acessivel',
            'Sensores, atuadores, protocolos IoT (MQTT, CoAP)',
            'Integracao com cloud (AWS IoT, Azure IoT Hub)',
            'Mercado IoT projetado para trilhoes de dolares',
        ],
        'resumo': (
            'IoT e Sistemas Embarcados conecta o mundo fisico ao digital. Voce vai aprender '
            'a programar microcontroladores, usar sensores e atuadores, implementar protocolos '
            'IoT e integrar dispositivos com plataformas cloud. De casas inteligentes a '
            'industria 4.0, IoT esta transformando todos os setores.'
        ),
        'dica': (
            'Compre um kit Arduino ou ESP32 (menos de R$50) e faca projetos praticos: '
            'sensor de temperatura com alerta no celular, irrigacao automatica, etc. '
            'IoT so faz sentido quando voce mexe com hardware de verdade.'
        ),
        'recursos': [
            'Plataforma: Arduino.cc — tutoriais e projetos para iniciantes',
            'Servico: AWS IoT Core — conecte dispositivos a nuvem',
            'Comunidade: Instructables.com — projetos IoT passo a passo',
        ],
        'proximo_passo': 'Projeto Final (8o semestre) — integre IoT no seu projeto de conclusao',
    },
    'Blockchain': {
        'destaques': [
            'Criptografia, consenso distribuido e imutabilidade',
            'Smart contracts com Solidity e Ethereum',
            'Aplicacoes alem de cripto: supply chain, identidade, votacao',
            'Tecnologia disruptiva com aplicacoes em multiplos setores',
        ],
        'resumo': (
            'Blockchain ensina a tecnologia por tras de criptomoedas e muito mais. Voce vai '
            'entender hashing, consenso distribuido, smart contracts, DeFi e aplicacoes '
            'empresariais de blockchain. Alem de cripto, blockchain e usado em rastreamento '
            'de supply chain, identidade digital e sistemas de votacao.'
        ),
        'dica': (
            'Implemente uma blockchain simples em Python para entender os conceitos. '
            'Depois, escreva um smart contract basico em Solidity e faca deploy na testnet '
            'do Ethereum (gratuito). A experiencia pratica desmistifica a tecnologia.'
        ),
        'recursos': [
            'Curso: Blockchain Specialization (University at Buffalo, Coursera)',
            'Ferramenta: Remix IDE — ambiente online para smart contracts Solidity',
            'Livro: "Mastering Blockchain" - Imran Bashir',
        ],
        'proximo_passo': 'Projeto Final (8o semestre) — aplique blockchain se relevante ao seu projeto',
    },
    'Inovacao Tecnologica': {
        'destaques': [
            'Tendencias: IA generativa, computacao quantica, Web3, metaverso',
            'Design thinking e metodologias de inovacao',
            'Como avaliar e adotar novas tecnologias estrategicamente',
            'Visao de futuro para tomar decisoes de carreira informadas',
        ],
        'resumo': (
            'Inovacao Tecnologica explora as tendencias que estao moldando o futuro da tecnologia: '
            'IA generativa, computacao quantica, realidade aumentada, Web3 e sustentabilidade '
            'digital. Voce vai aprender a avaliar tecnologias emergentes, aplicar design thinking '
            'e desenvolver uma mentalidade de inovacao continua.'
        ),
        'dica': (
            'Assine newsletters de tecnologia (The Pragmatic Engineer, TLDR, Hacker News Digest). '
            'Dedique 30 minutos por semana para explorar uma tecnologia nova. '
            'Profissionais que se mantem atualizados tem vantagem competitiva enorme.'
        ),
        'recursos': [
            'Newsletter: The Pragmatic Engineer — tendencias em engenharia',
            'Site: Hacker News (news.ycombinator.com) — noticias de tecnologia',
            'Livro: "O Dilema da Inovacao" - Clayton Christensen',
        ],
        'proximo_passo': 'Projeto Final (8o semestre) — aplique inovacao no seu projeto de conclusao',
    },
    'TCC II': {
        'destaques': [
            'Desenvolvimento completo e defesa do TCC',
            'Implementacao, testes, resultados e conclusoes',
            'Apresentacao para banca avaliadora',
            'Culminacao de 4 anos de aprendizado',
        ],
        'resumo': (
            'TCC II e a conclusao do seu Trabalho de Conclusao de Curso. Voce vai implementar '
            'a solucao proposta no TCC I, realizar testes e validacoes, documentar resultados '
            'e defender o trabalho perante uma banca avaliadora. E o momento de demonstrar '
            'tudo que voce aprendeu ao longo do curso.'
        ),
        'dica': (
            'Comece a preparar a apresentacao com antecedencia — pratique pelo menos 5 vezes. '
            'Antecipe perguntas da banca e prepare respostas. Mantenha slides limpos e objetivos. '
            'A banca quer ver que voce domina o tema, nao que voce decorou slides.'
        ),
        'recursos': [
            'Ferramenta: Overleaf — finalize a monografia em LaTeX',
            'Dica: Grave sua apresentacao e assista — identifique pontos de melhoria',
            'Template: Canva — slides profissionais para a defesa',
        ],
        'proximo_passo': 'Projeto Final (8o semestre) — seu ultimo projeto antes da formatura',
    },
    'Projeto Final': {
        'destaques': [
            'Projeto completo de software do inicio ao fim',
            'Integra todas as disciplinas do curso em um unico projeto',
            'Trabalho em equipe com entrega profissional',
            'Peca central do seu portfolio para o mercado de trabalho',
        ],
        'resumo': (
            'O Projeto Final e a culminacao do curso de Engenharia de Software. Voce vai '
            'desenvolver um sistema completo em equipe, aplicando engenharia de requisitos, '
            'arquitetura, desenvolvimento, testes, deploy e documentacao. E a oportunidade '
            'de criar algo que voce pode mostrar com orgulho para qualquer empregador.'
        ),
        'dica': (
            'Escolha um projeto que resolva um problema real — isso impressiona recrutadores '
            'muito mais do que projetos academicos genericos. Documente tudo no GitHub com '
            'README profissional, screenshots e instrucoes de deploy. Esse projeto pode ser '
            'o diferencial na sua primeira entrevista.'
        ),
        'recursos': [
            'Template: GitHub README templates para projetos profissionais',
            'Deploy: Vercel, Railway ou AWS Free Tier para hospedar o projeto',
            'Portfolio: Crie uma pagina pessoal linkando todos os seus projetos',
        ],
        'proximo_passo': 'Parabens! Voce concluiu o curso de Engenharia de Software. O proximo passo e sua carreira!',
    },
}


# ============================================================
# Funcoes auxiliares
# ============================================================

def sanitize_filename(nome):
    """Converte nome de disciplina em nome de arquivo seguro."""
    nome = nome.lower()
    nome = nome.replace('(', '').replace(')', '').replace('/', '_')
    nome = re.sub(r'[^a-z0-9_]', '_', nome)
    nome = re.sub(r'_+', '_', nome).strip('_')
    return nome


def get_email_styles():
    """Retorna estilos customizados para PDFs estilo newsletter/email."""
    styles = getSampleStyleSheet()

    # Header principal — newsletter title
    styles.add(ParagraphStyle(
        name='NewsletterHeader',
        parent=styles['Title'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=2,
        textColor=colors.HexColor('#1a5276'),
        fontName='Helvetica-Bold',
    ))

    # Subtitulo com info do semestre
    styles.add(ParagraphStyle(
        name='NewsletterSub',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        spaceAfter=8,
        textColor=colors.HexColor('#5d6d7e'),
        fontName='Helvetica',
    ))

    # Titulo de secao (Destaques, O que voce vai aprender, etc.)
    styles.add(ParagraphStyle(
        name='SecaoEmail',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor('#1a5276'),
        fontName='Helvetica-Bold',
    ))

    # Corpo de texto
    styles.add(ParagraphStyle(
        name='CorpoEmail',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        leading=14,
        fontName='Helvetica',
    ))

    # Bullet point / item de lista
    styles.add(ParagraphStyle(
        name='BulletEmail',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=15,
        spaceAfter=3,
        leading=13,
        fontName='Helvetica',
    ))

    # Dica do professor — destaque
    styles.add(ParagraphStyle(
        name='DicaEmail',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=15,
        rightIndent=15,
        spaceAfter=8,
        spaceBefore=4,
        leading=14,
        fontName='Helvetica-Oblique',
        backColor=colors.HexColor('#eaf2f8'),
        borderColor=colors.HexColor('#2980b9'),
        borderWidth=1,
        borderPadding=8,
    ))

    # Recurso recomendado
    styles.add(ParagraphStyle(
        name='RecursoEmail',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=15,
        spaceAfter=3,
        leading=12,
        fontName='Helvetica',
        textColor=colors.HexColor('#2c3e50'),
    ))

    # Proximo passo
    styles.add(ParagraphStyle(
        name='ProximoPassoEmail',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        spaceAfter=6,
        spaceBefore=4,
        leading=14,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a5276'),
    ))

    # Footer
    styles.add(ParagraphStyle(
        name='FooterEmail',
        parent=styles['Normal'],
        fontSize=7,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#95a5a6'),
        fontName='Helvetica',
    ))

    return styles


def gerar_email_pdf(disciplina, semestre_num, output_path, styles):
    """Gera PDF estilo newsletter/email para uma disciplina de graduacao."""
    conteudo = EMAIL_CONTENT.get(disciplina)
    if not conteudo:
        print(f'  WARN: Sem conteudo de email para "{disciplina}", pulando.')
        return False

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    story = []

    # ---- Linha decorativa superior ----
    story.append(HRFlowable(
        width='100%', thickness=2, color=colors.HexColor('#1a5276'),
        spaceAfter=8, spaceBefore=0,
    ))

    # ---- Header ----
    story.append(Paragraph(
        f'Newsletter Academica',
        styles['NewsletterHeader'],
    ))
    story.append(Paragraph(
        disciplina,
        styles['NewsletterHeader'],
    ))
    story.append(Paragraph(
        f'{CURSO_GRAD} | {semestre_num}o Semestre | {SEMESTRE_INFO}',
        styles['NewsletterSub'],
    ))

    # ---- Linha separadora ----
    story.append(HRFlowable(
        width='100%', thickness=1, color=colors.HexColor('#d5dbdb'),
        spaceAfter=6, spaceBefore=2,
    ))

    # ---- Destaques da Disciplina ----
    story.append(Paragraph('Destaques da Disciplina', styles['SecaoEmail']))
    for destaque in conteudo['destaques']:
        story.append(Paragraph(
            f'\u2022 {destaque}',
            styles['BulletEmail'],
        ))
    story.append(Spacer(1, 4))

    # ---- O que voce vai aprender ----
    story.append(Paragraph('O que voce vai aprender', styles['SecaoEmail']))
    story.append(Paragraph(conteudo['resumo'], styles['CorpoEmail']))

    # ---- Dica do Professor ----
    story.append(Paragraph('Dica do Professor', styles['SecaoEmail']))
    story.append(Paragraph(
        f'\U0001f4a1 {conteudo["dica"]}',
        styles['DicaEmail'],
    ))

    # ---- Recursos Recomendados ----
    story.append(Paragraph('Recursos Recomendados', styles['SecaoEmail']))
    for recurso in conteudo['recursos']:
        story.append(Paragraph(
            f'\u2023 {recurso}',
            styles['RecursoEmail'],
        ))
    story.append(Spacer(1, 6))

    # ---- Proximo Passo ----
    story.append(HRFlowable(
        width='60%', thickness=0.5, color=colors.HexColor('#d5dbdb'),
        spaceAfter=6, spaceBefore=6,
    ))
    story.append(Paragraph('Proximo Passo', styles['SecaoEmail']))
    story.append(Paragraph(
        f'\u27a1 {conteudo["proximo_passo"]}',
        styles['ProximoPassoEmail'],
    ))

    # ---- Footer ----
    story.append(Spacer(1, 10))
    story.append(HRFlowable(
        width='100%', thickness=1, color=colors.HexColor('#1a5276'),
        spaceAfter=6, spaceBefore=4,
    ))
    story.append(Paragraph(
        f'{INSTITUICAO} | {CURSO_GRAD}',
        styles['FooterEmail'],
    ))
    story.append(Paragraph(
        'Este e um resumo academico gerado automaticamente. '
        'Para conteudo completo, consulte o material didatico da disciplina.',
        styles['FooterEmail'],
    ))
    story.append(Paragraph(
        f'Semestre {SEMESTRE_INFO} | Todos os direitos reservados',
        styles['FooterEmail'],
    ))

    doc.build(story)
    return True


# ============================================================
# Main
# ============================================================
def main():
    styles = get_email_styles()
    total = 0

    print('=== Gerando emails/newsletters de graduacao (Eng. Software) ===')
    for semestre_key, disciplinas in GRADE_CURRICULAR.items():
        semestre_num = int(semestre_key.split('_')[0])
        for disciplina in disciplinas:
            filename = sanitize_filename(disciplina) + '_email.pdf'
            out_dir = os.path.join(OUTPUT_DIR, 'privado', 'graduacao', CURSO_ID_GRAD)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, filename)

            ok = gerar_email_pdf(disciplina, semestre_num, out_path, styles)
            if ok:
                total += 1
                print(f'  [{semestre_num}o sem] {disciplina} -> {filename}')

    print(f'\nDone!')
    print(f'  Total emails gerados: {total} PDFs')
    print(f'  Diretorio: {os.path.join(OUTPUT_DIR, "privado", "graduacao", CURSO_ID_GRAD)}')


if __name__ == '__main__':
    main()
