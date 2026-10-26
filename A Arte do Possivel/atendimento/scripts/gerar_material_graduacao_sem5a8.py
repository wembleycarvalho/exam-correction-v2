"""
Gera PDFs de MATERIAL DIDATICO (estudo) para disciplinas de graduacao - Semestres 5 a 8.
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

Uso: source .env && python3 scripts/gerar_material_graduacao_sem5a8.py
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
# Grade curricular — apenas semestres 5 a 8 (20 disciplinas)
# ============================================================
GRADE_SEM5A8 = {
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
# Conteudo detalhado por disciplina
# ============================================================
CONTEUDO_DISCIPLINAS = {
    # ---- Semestre 5 ----
    'DevOps e Cloud Computing': {
        'ementa': 'Cultura DevOps e integracao continua. Containers e Docker. Orquestracao com Kubernetes. Infraestrutura como codigo (Terraform). Pipelines CI/CD. Monitoramento e observabilidade. Provedores de nuvem (AWS, Azure, GCP). Servicos gerenciados.',
        'topicos': [
            'Unidade 1: Cultura DevOps - principios, praticas e ferramentas',
            'Unidade 2: Containers com Docker - imagens, volumes, redes',
            'Unidade 3: Orquestracao com Kubernetes - pods, services, deployments',
            'Unidade 4: Infraestrutura como Codigo - Terraform e CloudFormation',
            'Unidade 5: Pipelines CI/CD - GitHub Actions, Jenkins, GitLab CI',
            'Unidade 6: Monitoramento e observabilidade - Prometheus, Grafana, ELK',
            'Unidade 7: AWS - EC2, S3, Lambda, RDS, ECS, EKS',
            'Unidade 8: Arquiteturas cloud-native e serverless',
        ],
        'bibliografia': [
            'KIM, G. et al. O Projeto Phoenix. Alta Books, 2016.',
            'MORRIS, K. Infrastructure as Code. O\'Reilly, 2020.',
            'BURNS, B. Kubernetes: Tudo Sobre Orquestracao de Containers. Novatec, 2019.',
        ],
        'introducao': (
            'DevOps e Cloud Computing sao pilares da engenharia de software moderna. '
            'DevOps une desenvolvimento e operacoes para entregar software de forma rapida, '
            'confiavel e automatizada. Cloud Computing permite escalar aplicacoes globalmente '
            'sem gerenciar infraestrutura fisica. Juntos, esses conceitos transformaram a forma '
            'como software e construido, testado e implantado, sendo habilidades essenciais '
            'para qualquer engenheiro de software no mercado atual.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Containers e Docker',
                'explicacao': (
                    'Containers sao ambientes isolados e leves que empacotam uma aplicacao com todas '
                    'as suas dependencias. Docker e a plataforma mais popular para criar e gerenciar '
                    'containers. Diferente de maquinas virtuais, containers compartilham o kernel do '
                    'sistema operacional, sendo muito mais eficientes. Um Dockerfile define como '
                    'construir a imagem, e o Docker Compose orquestra multiplos containers.'
                ),
                'exemplo': (
                    'Dockerfile para aplicacao Python:\n'
                    'FROM python:3.11-slim\n'
                    'WORKDIR /app\n'
                    'COPY requirements.txt .\n'
                    'RUN pip install -r requirements.txt\n'
                    'COPY . .\n'
                    'EXPOSE 8000\n'
                    'CMD ["python", "app.py"]\n\n'
                    'Comandos basicos:\n'
                    'docker build -t minha-app .\n'
                    'docker run -p 8000:8000 minha-app\n'
                    'docker-compose up -d'
                ),
            },
            {
                'titulo': 'CI/CD e Pipelines de Entrega',
                'explicacao': (
                    'CI (Integracao Continua) automatiza a compilacao e testes a cada commit. '
                    'CD (Entrega Continua) automatiza o deploy em ambientes de staging e producao. '
                    'Pipelines CI/CD garantem que o codigo e testado e implantado de forma consistente '
                    'e rapida. Ferramentas populares incluem GitHub Actions, Jenkins e GitLab CI.'
                ),
                'exemplo': (
                    'Exemplo de GitHub Actions (.github/workflows/ci.yml):\n'
                    'name: CI Pipeline\n'
                    'on: [push, pull_request]\n'
                    'jobs:\n'
                    '  test:\n'
                    '    runs-on: ubuntu-latest\n'
                    '    steps:\n'
                    '      - uses: actions/checkout@v3\n'
                    '      - uses: actions/setup-python@v4\n'
                    '      - run: pip install -r requirements.txt\n'
                    '      - run: pytest tests/'
                ),
            },
            {
                'titulo': 'Infraestrutura como Codigo (IaC)',
                'explicacao': (
                    'IaC permite definir e gerenciar infraestrutura usando arquivos de configuracao '
                    'em vez de processos manuais. Terraform e a ferramenta mais popular, suportando '
                    'multiplos provedores de nuvem. CloudFormation e a opcao nativa da AWS. '
                    'IaC traz versionamento, reproducibilidade e automacao para a infraestrutura.'
                ),
                'exemplo': (
                    'Exemplo Terraform (main.tf):\n'
                    'resource "aws_instance" "web" {\n'
                    '  ami           = "ami-0c55b159cbfafe1f0"\n'
                    '  instance_type = "t2.micro"\n'
                    '  tags = {\n'
                    '    Name = "WebServer"\n'
                    '  }\n'
                    '}\n\n'
                    'terraform init\n'
                    'terraform plan\n'
                    'terraform apply'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual a principal diferenca entre containers e maquinas virtuais?', 'alternativas': ['a) Containers sao mais seguros', 'b) Containers compartilham o kernel do SO host', 'c) VMs sao mais rapidas', 'd) Containers precisam de mais memoria'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique o conceito de CI/CD e como ele melhora o processo de desenvolvimento de software.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual ferramenta e usada para orquestracao de containers em larga escala?', 'alternativas': ['a) Docker Compose', 'b) Terraform', 'c) Kubernetes', 'd) Ansible'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva as vantagens de usar Infraestrutura como Codigo (IaC) em comparacao com configuracao manual.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e um Dockerfile?', 'alternativas': ['a) Um container em execucao', 'b) Um arquivo que define como construir uma imagem Docker', 'c) Um servico de orquestracao', 'd) Um arquivo de configuracao do Kubernetes'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Instale Docker e pratique criando containers para seus projetos.',
            'Crie pipelines CI/CD para seus repositorios no GitHub.',
            'Explore o free tier da AWS para praticar servicos de nuvem.',
            'Estude para certificacoes como AWS Cloud Practitioner ou Docker Certified Associate.',
            'Leia o livro "O Projeto Phoenix" para entender a cultura DevOps.',
        ],
        'glossario': [
            'Container: ambiente isolado e leve para executar aplicacoes.',
            'Docker: plataforma para criar, distribuir e executar containers.',
            'Kubernetes: sistema de orquestracao de containers em larga escala.',
            'CI/CD: Integracao Continua / Entrega Continua.',
            'Terraform: ferramenta de Infraestrutura como Codigo (IaC).',
            'Pipeline: sequencia automatizada de etapas (build, test, deploy).',
            'Serverless: modelo onde o provedor gerencia a infraestrutura automaticamente.',
            'Observabilidade: capacidade de entender o estado interno de um sistema.',
            'IaC: Infrastructure as Code — infraestrutura definida em arquivos de configuracao.',
        ],
    },
    'Inteligencia Artificial': {
        'ementa': 'Fundamentos de IA. Agentes inteligentes. Busca e otimizacao. Representacao de conhecimento. Aprendizado de maquina (introducao). Redes neurais artificiais. Processamento de linguagem natural. Etica em IA.',
        'topicos': [
            'Unidade 1: Historia e fundamentos da Inteligencia Artificial',
            'Unidade 2: Agentes inteligentes - tipos e arquiteturas',
            'Unidade 3: Busca em espacos de estados - BFS, DFS, A*',
            'Unidade 4: Representacao de conhecimento e raciocinio',
            'Unidade 5: Introducao ao aprendizado de maquina - supervisionado e nao-supervisionado',
            'Unidade 6: Redes neurais artificiais e deep learning (introducao)',
            'Unidade 7: Processamento de linguagem natural (NLP)',
            'Unidade 8: Etica, vieses e impactos sociais da IA',
        ],
        'bibliografia': [
            'RUSSELL, S.; NORVIG, P. Inteligencia Artificial. Elsevier, 2022.',
            'FACELI, K. et al. Inteligencia Artificial: Uma Abordagem de Aprendizado de Maquina. LTC, 2021.',
            'GOODFELLOW, I. et al. Deep Learning. MIT Press, 2016.',
        ],
        'introducao': (
            'A Inteligencia Artificial e uma das areas mais transformadoras da computacao. '
            'Ela busca criar sistemas capazes de realizar tarefas que normalmente requerem '
            'inteligencia humana: reconhecer padroes, tomar decisoes, entender linguagem natural '
            'e aprender com experiencia. De assistentes virtuais a carros autonomos, a IA esta '
            'revolucionando todos os setores. Para engenheiros de software, entender IA e '
            'fundamental para construir a proxima geracao de aplicacoes inteligentes.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Agentes Inteligentes e Busca',
                'explicacao': (
                    'Um agente inteligente percebe o ambiente atraves de sensores e age sobre ele '
                    'atraves de atuadores. Agentes podem ser reativos simples, baseados em modelo, '
                    'baseados em objetivos ou baseados em utilidade. Algoritmos de busca (BFS, DFS, A*) '
                    'permitem que agentes encontrem solucoes em espacos de estados complexos. '
                    'O algoritmo A* combina custo real e heuristica para encontrar caminhos otimos.'
                ),
                'exemplo': (
                    'Algoritmo A* para encontrar caminho:\n'
                    'f(n) = g(n) + h(n)\n'
                    'g(n) = custo real do inicio ate n\n'
                    'h(n) = heuristica (estimativa ate o objetivo)\n\n'
                    'Exemplo: GPS encontrando rota mais curta\n'
                    'g(n) = distancia ja percorrida\n'
                    'h(n) = distancia em linha reta ate o destino\n'
                    'A* expande o no com menor f(n) primeiro.'
                ),
            },
            {
                'titulo': 'Redes Neurais e Deep Learning',
                'explicacao': (
                    'Redes neurais artificiais sao modelos inspirados no cerebro humano. '
                    'Cada neuronio recebe entradas, aplica pesos, soma e passa por uma funcao '
                    'de ativacao. Deep Learning usa redes com muitas camadas (profundas) para '
                    'aprender representacoes complexas. CNNs processam imagens, RNNs processam '
                    'sequencias e Transformers revolucionaram o NLP (GPT, BERT).'
                ),
                'exemplo': (
                    'Neuronio artificial:\n'
                    'entradas: x1, x2, x3\n'
                    'pesos: w1, w2, w3\n'
                    'soma = w1*x1 + w2*x2 + w3*x3 + bias\n'
                    'saida = funcao_ativacao(soma)\n\n'
                    'Funcoes de ativacao comuns:\n'
                    'ReLU: f(x) = max(0, x)\n'
                    'Sigmoid: f(x) = 1 / (1 + e^(-x))\n'
                    'Softmax: para classificacao multiclasse'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual algoritmo de busca usa heuristica para encontrar caminhos otimos?', 'alternativas': ['a) BFS', 'b) DFS', 'c) A*', 'd) Dijkstra'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique a diferenca entre aprendizado supervisionado e nao-supervisionado, dando exemplos de cada.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual arquitetura de rede neural e mais adequada para processamento de imagens?', 'alternativas': ['a) RNN', 'b) CNN', 'c) GAN', 'd) Autoencoder'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Discuta os desafios eticos da Inteligencia Artificial, incluindo vieses algoritmicos e privacidade.'},
        ],
        'dicas_estudo': [
            'Comece com algoritmos classicos de IA antes de pular para deep learning.',
            'Pratique implementando algoritmos de busca (A*, minimax) do zero.',
            'Use bibliotecas como scikit-learn e TensorFlow para experimentar.',
            'Acompanhe conferencias como NeurIPS e ICML para tendencias.',
            'Estude os aspectos eticos — IA responsavel e cada vez mais importante.',
        ],
        'glossario': [
            'Agente inteligente: sistema que percebe o ambiente e age para atingir objetivos.',
            'Heuristica: estimativa usada para guiar a busca de solucoes.',
            'Rede neural: modelo computacional inspirado no cerebro humano.',
            'Deep learning: aprendizado com redes neurais de muitas camadas.',
            'NLP: Processamento de Linguagem Natural.',
            'CNN: Rede Neural Convolucional — especializada em imagens.',
            'Transformer: arquitetura que revolucionou NLP (base do GPT, BERT).',
            'Vies algoritmico: tendencia sistematica em decisoes de IA que pode ser injusta.',
        ],
    },
    'Seguranca da Informacao': {
        'ementa': 'Principios de seguranca (CIA). Criptografia simetrica e assimetrica. Autenticacao e controle de acesso. Vulnerabilidades e ataques comuns (OWASP). Seguranca em redes. Seguranca em aplicacoes web. Gestao de riscos. Conformidade e LGPD.',
        'topicos': [
            'Unidade 1: Principios de seguranca - Confidencialidade, Integridade, Disponibilidade',
            'Unidade 2: Criptografia simetrica (AES) e assimetrica (RSA)',
            'Unidade 3: Hashing, assinaturas digitais e certificados',
            'Unidade 4: Autenticacao, autorizacao e controle de acesso (RBAC, OAuth)',
            'Unidade 5: Vulnerabilidades web - OWASP Top 10 (SQL Injection, XSS, CSRF)',
            'Unidade 6: Seguranca em redes - firewalls, IDS/IPS, VPN',
            'Unidade 7: Gestao de riscos e resposta a incidentes',
            'Unidade 8: Conformidade, LGPD e normas (ISO 27001)',
        ],
        'bibliografia': [
            'STALLINGS, W. Criptografia e Seguranca de Redes. Pearson, 2015.',
            'TANENBAUM, A. Redes de Computadores. Pearson, 2011.',
            'OWASP Foundation. OWASP Top 10 - 2021. owasp.org.',
        ],
        'introducao': (
            'A Seguranca da Informacao e uma area critica na engenharia de software. '
            'Com o aumento de ataques ciberneticos e vazamentos de dados, proteger sistemas '
            'e informacoes e uma responsabilidade de todo desenvolvedor. Esta disciplina '
            'aborda desde criptografia e autenticacao ate vulnerabilidades comuns e conformidade '
            'legal (LGPD). Entender seguranca nao e opcional — e uma competencia essencial '
            'para construir software confiavel e proteger usuarios.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Triade CIA e Criptografia',
                'explicacao': (
                    'A triade CIA define os tres pilares da seguranca: Confidencialidade (apenas '
                    'autorizados acessam), Integridade (dados nao sao alterados indevidamente) e '
                    'Disponibilidade (sistema acessivel quando necessario). Criptografia simetrica '
                    '(AES) usa a mesma chave para cifrar e decifrar. Criptografia assimetrica (RSA) '
                    'usa par de chaves publica/privada. Hashing (SHA-256) gera resumo irreversivel.'
                ),
                'exemplo': (
                    'Criptografia simetrica (AES):\n'
                    'Chave: "minha-chave-secreta"\n'
                    'Texto: "dados sensiveis" -> cifrar -> "x7f2a9..."\n'
                    'Mesma chave para decifrar.\n\n'
                    'Criptografia assimetrica (RSA):\n'
                    'Chave publica: cifra (qualquer um pode cifrar)\n'
                    'Chave privada: decifra (so o dono pode ler)\n\n'
                    'Hash SHA-256:\n'
                    '"senha123" -> "ef92b778bafe771e89245b89ecbc08a44a4e166c..."'
                ),
            },
            {
                'titulo': 'OWASP Top 10 e Seguranca Web',
                'explicacao': (
                    'O OWASP Top 10 lista as vulnerabilidades mais criticas em aplicacoes web. '
                    'SQL Injection permite executar comandos SQL maliciosos. XSS (Cross-Site Scripting) '
                    'injeta scripts no navegador do usuario. CSRF forca acoes nao autorizadas. '
                    'Prevencao inclui: validacao de entrada, queries parametrizadas, tokens CSRF, '
                    'Content Security Policy e sanitizacao de saida.'
                ),
                'exemplo': (
                    'SQL Injection - VULNERAVEL:\n'
                    'query = f"SELECT * FROM users WHERE name=\'{input}\'"\n'
                    'Input malicioso: \' OR 1=1 --\n\n'
                    'SEGURO (query parametrizada):\n'
                    'cursor.execute("SELECT * FROM users WHERE name=?", (input,))\n\n'
                    'XSS - VULNERAVEL:\n'
                    'document.innerHTML = userInput\n\n'
                    'SEGURO:\n'
                    'document.textContent = userInput'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual pilar da triade CIA garante que dados nao sejam alterados indevidamente?', 'alternativas': ['a) Confidencialidade', 'b) Integridade', 'c) Disponibilidade', 'd) Autenticidade'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique a diferenca entre criptografia simetrica e assimetrica. Quando usar cada uma?'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual vulnerabilidade permite executar comandos SQL maliciosos no banco de dados?', 'alternativas': ['a) XSS', 'b) CSRF', 'c) SQL Injection', 'd) Buffer Overflow'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva 3 medidas praticas que um desenvolvedor deve adotar para prevenir vulnerabilidades do OWASP Top 10.'},
        ],
        'dicas_estudo': [
            'Estude o OWASP Top 10 e pratique identificando vulnerabilidades.',
            'Use ferramentas como Burp Suite e OWASP ZAP para testes de seguranca.',
            'Aprenda sobre LGPD — e obrigatorio para sistemas que tratam dados pessoais no Brasil.',
            'Pratique criptografia com bibliotecas como cryptography (Python).',
            'Participe de CTFs (Capture The Flag) para aprender seguranca na pratica.',
        ],
        'glossario': [
            'CIA: Confidencialidade, Integridade, Disponibilidade — pilares da seguranca.',
            'Criptografia simetrica: mesma chave para cifrar e decifrar (ex: AES).',
            'Criptografia assimetrica: par de chaves publica/privada (ex: RSA).',
            'Hash: funcao que gera resumo de tamanho fixo (irreversivel).',
            'SQL Injection: ataque que injeta comandos SQL maliciosos.',
            'XSS: Cross-Site Scripting — injeta scripts no navegador.',
            'LGPD: Lei Geral de Protecao de Dados Pessoais.',
            'OWASP: Open Web Application Security Project.',
            'Firewall: dispositivo que filtra trafego de rede.',
        ],
    },
    'Metodologias Ageis': {
        'ementa': 'Manifesto Agil e principios. Scrum - papeis, eventos e artefatos. Kanban e fluxo continuo. Extreme Programming (XP). Lean Software Development. Estimativas ageis. Metricas e melhoria continua. Escalando agil (SAFe, LeSS).',
        'topicos': [
            'Unidade 1: Manifesto Agil - valores, principios e contexto historico',
            'Unidade 2: Scrum - papeis (PO, SM, Dev Team), eventos e artefatos',
            'Unidade 3: Kanban - quadro, WIP limits, fluxo continuo',
            'Unidade 4: Extreme Programming (XP) - praticas tecnicas',
            'Unidade 5: User stories, criterios de aceitacao e Definition of Done',
            'Unidade 6: Estimativas ageis - Planning Poker, story points',
            'Unidade 7: Metricas ageis - velocity, lead time, cycle time, burndown',
            'Unidade 8: Escalando agil - SAFe, LeSS, Nexus',
        ],
        'bibliografia': [
            'SCHWABER, K.; SUTHERLAND, J. O Guia do Scrum. Scrum.org, 2020.',
            'BECK, K. Extreme Programming Explained. Addison-Wesley, 2004.',
            'ANDERSON, D. Kanban: Mudanca Evolucionaria de Sucesso. Blue Hole Press, 2010.',
        ],
        'introducao': (
            'Metodologias Ageis revolucionaram o desenvolvimento de software ao priorizar '
            'pessoas, colaboracao, software funcionando e resposta a mudancas. Em vez de '
            'planos rigidos e documentacao excessiva, equipes ageis trabalham em ciclos curtos '
            '(sprints), entregando valor incrementalmente e adaptando-se ao feedback. '
            'Scrum, Kanban e XP sao os frameworks mais utilizados no mercado, e domina-los '
            'e essencial para trabalhar em equipes de desenvolvimento modernas.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Scrum Framework',
                'explicacao': (
                    'Scrum e o framework agil mais popular. Define tres papeis: Product Owner '
                    '(prioriza o backlog), Scrum Master (facilita o processo) e Dev Team (executa). '
                    'Eventos: Sprint Planning, Daily Scrum, Sprint Review e Sprint Retrospective. '
                    'Artefatos: Product Backlog, Sprint Backlog e Incremento. Sprints duram 1-4 semanas '
                    'e entregam um incremento potencialmente utilizavel do produto.'
                ),
                'exemplo': (
                    'Fluxo de uma Sprint (2 semanas):\n'
                    '1. Sprint Planning (4h): PO apresenta itens, time seleciona\n'
                    '2. Daily Scrum (15min/dia): O que fiz? O que farei? Impedimentos?\n'
                    '3. Desenvolvimento: time trabalha nos itens do Sprint Backlog\n'
                    '4. Sprint Review (2h): demonstracao do incremento\n'
                    '5. Sprint Retrospective (1.5h): o que melhorar?\n\n'
                    'Artefatos:\n'
                    'Product Backlog: lista priorizada de tudo que o produto precisa\n'
                    'Sprint Backlog: itens selecionados para a sprint atual\n'
                    'Incremento: software funcionando entregue ao final da sprint'
                ),
            },
            {
                'titulo': 'Kanban e Fluxo Continuo',
                'explicacao': (
                    'Kanban visualiza o fluxo de trabalho em um quadro com colunas (To Do, In Progress, '
                    'Done). O principio central e limitar o Work In Progress (WIP) para evitar '
                    'sobrecarga e melhorar o fluxo. Diferente do Scrum, Kanban nao tem sprints fixas — '
                    'o trabalho flui continuamente. Metricas como lead time e cycle time medem a '
                    'eficiencia do processo.'
                ),
                'exemplo': (
                    'Quadro Kanban:\n'
                    'Backlog | To Do | In Progress (WIP: 3) | Review | Done\n'
                    '  [E]   | [D]   | [A] [B] [C]          | [F]    | [G] [H]\n\n'
                    'Regra WIP: maximo 3 itens em "In Progress"\n'
                    'Se alguem termina [A], puxa [D] de "To Do"\n'
                    'Se "In Progress" esta cheio, ajude a terminar antes de comecar novo'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual e o papel responsavel por priorizar o Product Backlog no Scrum?', 'alternativas': ['a) Scrum Master', 'b) Product Owner', 'c) Dev Team', 'd) Stakeholder'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Compare Scrum e Kanban: quando usar cada um? Quais as principais diferencas?'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que significa WIP no contexto do Kanban?', 'alternativas': ['a) Work In Production', 'b) Work In Progress', 'c) Weekly Iteration Plan', 'd) Work Item Priority'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva os 4 valores do Manifesto Agil e explique como eles se aplicam no dia a dia de uma equipe de desenvolvimento.'},
        ],
        'dicas_estudo': [
            'Leia o Guia do Scrum oficial (scrum.org) — e curto e essencial.',
            'Pratique Scrum em projetos academicos com colegas.',
            'Use ferramentas como Jira, Trello ou Azure DevOps para gerenciar backlogs.',
            'Estude para a certificacao PSM I (Professional Scrum Master).',
            'Participe de comunidades ageis e meetups locais.',
        ],
        'glossario': [
            'Sprint: ciclo de trabalho com duracao fixa (1-4 semanas).',
            'Product Backlog: lista priorizada de requisitos do produto.',
            'Sprint Backlog: itens selecionados para a sprint atual.',
            'Daily Scrum: reuniao diaria de 15 minutos para sincronizacao.',
            'Retrospectiva: reuniao para identificar melhorias no processo.',
            'WIP: Work In Progress — quantidade de trabalho em andamento.',
            'Story Points: unidade de estimativa relativa de esforco.',
            'Velocity: quantidade de story points entregues por sprint.',
            'Definition of Done: criterios que definem quando um item esta pronto.',
        ],
    },
    'Estagio Supervisionado I': {
        'ementa': 'Introducao ao estagio supervisionado. Mercado de trabalho em TI. Elaboracao de curriculo e portfolio. Etica profissional. Relatorio de atividades. Integracao teoria-pratica. Supervisao academica.',
        'topicos': [
            'Unidade 1: O estagio na formacao do engenheiro de software',
            'Unidade 2: Mercado de trabalho em TI - areas e tendencias',
            'Unidade 3: Elaboracao de curriculo tecnico e portfolio no GitHub',
            'Unidade 4: Processos seletivos - entrevistas tecnicas e comportamentais',
            'Unidade 5: Etica profissional e codigo de conduta',
            'Unidade 6: Planejamento de atividades e objetivos do estagio',
            'Unidade 7: Relatorio parcial de atividades',
            'Unidade 8: Integracao teoria-pratica e reflexao critica',
        ],
        'bibliografia': [
            'BIANCHI, A. Manual de Orientacao: Estagio Supervisionado. Cengage, 2012.',
            'CRACKING THE CODING INTERVIEW. McDowell, G. CareerCup, 2015.',
            'MARTIN, R. O Codificador Limpo. Alta Books, 2012.',
        ],
        'introducao': (
            'O Estagio Supervisionado I e o primeiro contato formal do aluno com o mercado '
            'de trabalho em tecnologia. Esta disciplina prepara o estudante para ingressar '
            'em uma empresa, desenvolvendo habilidades profissionais como comunicacao, trabalho '
            'em equipe e etica. Alem disso, o estagio permite aplicar na pratica os conhecimentos '
            'adquiridos nas disciplinas anteriores, consolidando a formacao academica e '
            'construindo experiencia profissional.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Portfolio Profissional e GitHub',
                'explicacao': (
                    'O portfolio e a principal ferramenta de um desenvolvedor para demonstrar '
                    'suas habilidades. O GitHub funciona como portfolio tecnico, mostrando projetos, '
                    'contribuicoes e qualidade de codigo. Um bom perfil inclui: README bem escrito, '
                    'projetos variados, commits regulares, codigo limpo e documentacao. '
                    'Recrutadores avaliam o GitHub antes mesmo da entrevista.'
                ),
                'exemplo': (
                    'Estrutura de um bom perfil GitHub:\n'
                    '1. README do perfil com apresentacao pessoal\n'
                    '2. Projetos pinados (3-6 melhores)\n'
                    '3. Cada projeto com:\n'
                    '   - README detalhado (descricao, setup, uso)\n'
                    '   - Codigo limpo e organizado\n'
                    '   - Testes automatizados\n'
                    '   - CI/CD configurado\n'
                    '4. Contribuicoes em projetos open source\n'
                    '5. Commits regulares (grafico de contribuicoes verde)'
                ),
            },
            {
                'titulo': 'Entrevistas Tecnicas em TI',
                'explicacao': (
                    'Entrevistas tecnicas em TI geralmente incluem: triagem por telefone, '
                    'desafio de codigo (HackerRank, LeetCode), entrevista tecnica ao vivo '
                    '(whiteboard ou pair programming), entrevista de design de sistema e '
                    'entrevista comportamental. Preparacao inclui praticar algoritmos, '
                    'estruturas de dados, design patterns e comunicacao clara de raciocinio.'
                ),
                'exemplo': (
                    'Etapas tipicas de processo seletivo em tech:\n'
                    '1. Triagem de curriculo/LinkedIn\n'
                    '2. Teste online (1-2h): algoritmos e logica\n'
                    '3. Entrevista tecnica (1h): resolver problema ao vivo\n'
                    '4. System design (1h): projetar sistema escalavel\n'
                    '5. Entrevista comportamental: situacoes passadas\n'
                    '6. Oferta e negociacao\n\n'
                    'Dica: use o metodo STAR para respostas comportamentais\n'
                    'Situacao -> Tarefa -> Acao -> Resultado'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'dissertativa', 'enunciado': 'Elabore um plano de desenvolvimento do seu portfolio no GitHub, listando 3 projetos que voce criaria para demonstrar suas habilidades.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual metodo e recomendado para responder perguntas comportamentais em entrevistas?', 'alternativas': ['a) SOLID', 'b) STAR', 'c) SCRUM', 'd) SWOT'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva 3 competencias tecnicas e 3 competencias comportamentais importantes para um estagiario em engenharia de software.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e mais valorizado por recrutadores de tecnologia ao avaliar candidatos?', 'alternativas': ['a) Apenas o diploma', 'b) Portfolio e projetos praticos', 'c) Numero de certificacoes', 'd) Tempo de experiencia'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Comece a construir seu portfolio no GitHub desde ja.',
            'Pratique algoritmos no LeetCode ou HackerRank regularmente.',
            'Participe de projetos open source para ganhar experiencia.',
            'Prepare-se para entrevistas comportamentais com o metodo STAR.',
            'Faca networking em eventos de tecnologia e comunidades online.',
        ],
        'glossario': [
            'Portfolio: colecao de projetos que demonstra habilidades profissionais.',
            'GitHub: plataforma de hospedagem de codigo e colaboracao.',
            'README: arquivo de documentacao principal de um projeto.',
            'Open source: software com codigo-fonte aberto e livre.',
            'Metodo STAR: Situacao, Tarefa, Acao, Resultado — para entrevistas.',
            'Pair programming: programacao em dupla para resolver problemas.',
            'Networking: construcao de rede de contatos profissionais.',
        ],
    },
    # ---- Semestre 6 ----
    'Microsservicos e APIs': {
        'ementa': 'Arquitetura de microsservicos. Design de APIs RESTful. GraphQL. Comunicacao sincrona e assincrona. API Gateway. Service mesh. Documentacao com OpenAPI/Swagger. Versionamento e evolucao de APIs.',
        'topicos': [
            'Unidade 1: Monolitos vs microsservicos - vantagens e desafios',
            'Unidade 2: Design de APIs RESTful - recursos, verbos HTTP, status codes',
            'Unidade 3: GraphQL - queries, mutations, subscriptions',
            'Unidade 4: Comunicacao entre servicos - REST, gRPC, mensageria (RabbitMQ, Kafka)',
            'Unidade 5: API Gateway e service mesh (Istio, Envoy)',
            'Unidade 6: Autenticacao em APIs - JWT, OAuth 2.0, API Keys',
            'Unidade 7: Documentacao com OpenAPI/Swagger e versionamento',
            'Unidade 8: Padroes de resiliencia - Circuit Breaker, Retry, Bulkhead',
        ],
        'bibliografia': [
            'NEWMAN, S. Construindo Microsservicos. Novatec, 2022.',
            'RICHARDSON, C. Microsservicos: Padroes e Aplicacoes. Alta Books, 2019.',
            'MASSE, M. REST API Design Rulebook. O\'Reilly, 2011.',
        ],
        'introducao': (
            'Microsservicos e APIs sao a base da arquitetura de software moderna. '
            'Em vez de um unico sistema monolitico, aplicacoes sao decompostas em servicos '
            'pequenos e independentes que se comunicam via APIs. Isso permite que equipes '
            'trabalhem de forma autonoma, escalem servicos individualmente e usem tecnologias '
            'diferentes para cada servico. APIs RESTful e GraphQL sao os padroes dominantes '
            'para comunicacao entre sistemas na web.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'APIs RESTful e Boas Praticas',
                'explicacao': (
                    'REST (Representational State Transfer) e o estilo arquitetural mais usado para APIs web. '
                    'Recursos sao identificados por URLs, operacoes usam verbos HTTP (GET, POST, PUT, DELETE) '
                    'e respostas usam status codes padrao (200 OK, 201 Created, 404 Not Found, 500 Error). '
                    'Boas praticas incluem: nomes de recursos no plural, versionamento na URL, paginacao, '
                    'HATEOAS e documentacao com OpenAPI.'
                ),
                'exemplo': (
                    'API RESTful para gerenciar alunos:\n'
                    'GET    /api/v1/alunos          -> lista alunos\n'
                    'GET    /api/v1/alunos/123       -> detalhe do aluno 123\n'
                    'POST   /api/v1/alunos           -> cria novo aluno\n'
                    'PUT    /api/v1/alunos/123       -> atualiza aluno 123\n'
                    'DELETE /api/v1/alunos/123       -> remove aluno 123\n\n'
                    'Resposta JSON:\n'
                    '{"id": 123, "nome": "Maria", "curso": "Eng. Software"}'
                ),
            },
            {
                'titulo': 'Padroes de Microsservicos',
                'explicacao': (
                    'Microsservicos trazem desafios que exigem padroes especificos. '
                    'API Gateway centraliza o acesso externo. Circuit Breaker evita cascata de falhas. '
                    'Saga gerencia transacoes distribuidas. Event Sourcing registra mudancas como eventos. '
                    'CQRS separa leitura e escrita. Service Discovery permite que servicos se encontrem '
                    'dinamicamente.'
                ),
                'exemplo': (
                    'Circuit Breaker (3 estados):\n'
                    'FECHADO: requisicoes passam normalmente\n'
                    '  -> se falhas > limite: abre o circuito\n'
                    'ABERTO: requisicoes falham imediatamente (fast fail)\n'
                    '  -> apos timeout: vai para meio-aberto\n'
                    'MEIO-ABERTO: permite uma requisicao de teste\n'
                    '  -> se sucesso: fecha o circuito\n'
                    '  -> se falha: abre novamente'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual verbo HTTP e usado para criar um novo recurso em uma API REST?', 'alternativas': ['a) GET', 'b) PUT', 'c) POST', 'd) PATCH'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Compare REST e GraphQL: vantagens e desvantagens de cada abordagem.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual padrao evita cascata de falhas entre microsservicos?', 'alternativas': ['a) Singleton', 'b) Circuit Breaker', 'c) Observer', 'd) Factory'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Projete uma API RESTful para um sistema de e-commerce com recursos: produtos, pedidos e clientes.'},
        ],
        'dicas_estudo': [
            'Construa APIs RESTful com Flask ou FastAPI (Python) para praticar.',
            'Estude autenticacao com JWT e OAuth 2.0 na pratica.',
            'Use Postman ou Insomnia para testar suas APIs.',
            'Leia o livro "Construindo Microsservicos" de Sam Newman.',
            'Documente suas APIs com Swagger/OpenAPI desde o inicio.',
        ],
        'glossario': [
            'API: Application Programming Interface — interface de comunicacao entre sistemas.',
            'REST: Representational State Transfer — estilo arquitetural para APIs web.',
            'GraphQL: linguagem de consulta para APIs desenvolvida pelo Facebook.',
            'Microsservico: servico pequeno e independente com responsabilidade unica.',
            'API Gateway: ponto de entrada unico para todas as requisicoes externas.',
            'Circuit Breaker: padrao que evita cascata de falhas entre servicos.',
            'JWT: JSON Web Token — padrao para autenticacao stateless.',
            'gRPC: framework de RPC de alta performance do Google.',
        ],
    },
    'Machine Learning': {
        'ementa': 'Fundamentos de aprendizado de maquina. Aprendizado supervisionado: regressao e classificacao. Aprendizado nao-supervisionado: clustering e reducao de dimensionalidade. Avaliacao de modelos. Feature engineering. Redes neurais e deep learning. Aplicacoes praticas.',
        'topicos': [
            'Unidade 1: Fundamentos de ML - tipos de aprendizado, pipeline de dados',
            'Unidade 2: Regressao linear e logistica',
            'Unidade 3: Arvores de decisao, Random Forest e Gradient Boosting',
            'Unidade 4: SVM, KNN e Naive Bayes',
            'Unidade 5: Clustering - K-Means, DBSCAN, hierarquico',
            'Unidade 6: Avaliacao de modelos - metricas, validacao cruzada, overfitting',
            'Unidade 7: Feature engineering e selecao de features',
            'Unidade 8: Introducao a deep learning - redes neurais com TensorFlow/PyTorch',
        ],
        'bibliografia': [
            'GERON, A. Maos a Obra: Aprendizado de Maquina com Scikit-Learn, Keras e TensorFlow. Alta Books, 2021.',
            'FACELI, K. et al. Inteligencia Artificial: Uma Abordagem de Aprendizado de Maquina. LTC, 2021.',
            'BISHOP, C. Pattern Recognition and Machine Learning. Springer, 2006.',
        ],
        'introducao': (
            'Machine Learning e a area da IA que permite que computadores aprendam a partir '
            'de dados sem serem explicitamente programados. Em vez de regras fixas, algoritmos '
            'de ML identificam padroes nos dados e fazem previsoes. Aplicacoes incluem '
            'recomendacao de conteudo (Netflix, Spotify), deteccao de fraudes, diagnostico '
            'medico, traducao automatica e muito mais. Para engenheiros de software, ML e '
            'uma habilidade cada vez mais demandada pelo mercado.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Aprendizado Supervisionado',
                'explicacao': (
                    'No aprendizado supervisionado, o modelo aprende a partir de dados rotulados '
                    '(entrada + saida esperada). Regressao preve valores continuos (preco de imovel). '
                    'Classificacao preve categorias (spam ou nao-spam). Algoritmos populares: '
                    'Regressao Linear, Regressao Logistica, Arvores de Decisao, Random Forest, '
                    'SVM e KNN. O modelo e treinado em dados de treino e avaliado em dados de teste.'
                ),
                'exemplo': (
                    'Regressao Linear - prever preco de imovel:\n'
                    'preco = w1*area + w2*quartos + w3*localizacao + b\n\n'
                    'Em Python com scikit-learn:\n'
                    'from sklearn.linear_model import LinearRegression\n'
                    'modelo = LinearRegression()\n'
                    'modelo.fit(X_treino, y_treino)\n'
                    'previsao = modelo.predict(X_teste)\n\n'
                    'Classificacao - spam ou nao-spam:\n'
                    'from sklearn.ensemble import RandomForestClassifier\n'
                    'clf = RandomForestClassifier()\n'
                    'clf.fit(X_treino, y_treino)\n'
                    'resultado = clf.predict(novo_email)'
                ),
            },
            {
                'titulo': 'Avaliacao de Modelos e Overfitting',
                'explicacao': (
                    'Avaliar modelos corretamente e crucial. Metricas de regressao: MAE, MSE, R2. '
                    'Metricas de classificacao: acuracia, precisao, recall, F1-score, AUC-ROC. '
                    'Overfitting ocorre quando o modelo memoriza os dados de treino mas nao generaliza. '
                    'Solucoes: validacao cruzada, regularizacao (L1/L2), mais dados, early stopping.'
                ),
                'exemplo': (
                    'Validacao cruzada (5-fold):\n'
                    'Dados divididos em 5 partes iguais\n'
                    'Rodada 1: treina em 2,3,4,5 - testa em 1\n'
                    'Rodada 2: treina em 1,3,4,5 - testa em 2\n'
                    '...\n'
                    'Rodada 5: treina em 1,2,3,4 - testa em 5\n'
                    'Resultado: media das 5 avaliacoes\n\n'
                    'from sklearn.model_selection import cross_val_score\n'
                    'scores = cross_val_score(modelo, X, y, cv=5)\n'
                    'print(f"Acuracia media: {scores.mean():.2f}")'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual tipo de aprendizado usa dados rotulados para treinar o modelo?', 'alternativas': ['a) Nao-supervisionado', 'b) Supervisionado', 'c) Por reforco', 'd) Semi-supervisionado'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique o que e overfitting e cite 3 tecnicas para evita-lo.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual algoritmo e mais adequado para agrupar dados sem rotulos?', 'alternativas': ['a) Regressao Linear', 'b) Random Forest', 'c) K-Means', 'd) Regressao Logistica'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva o pipeline completo de um projeto de Machine Learning, desde a coleta de dados ate o deploy do modelo.'},
        ],
        'dicas_estudo': [
            'Comece com scikit-learn antes de ir para TensorFlow ou PyTorch.',
            'Pratique com datasets do Kaggle — participe de competicoes.',
            'Entenda a matematica por tras dos algoritmos (algebra linear, estatistica).',
            'Leia o livro "Maos a Obra" de Aurelien Geron — e o melhor guia pratico.',
            'Construa projetos end-to-end: coleta, limpeza, treino, avaliacao, deploy.',
        ],
        'glossario': [
            'Aprendizado supervisionado: treino com dados rotulados (entrada + saida).',
            'Aprendizado nao-supervisionado: treino sem rotulos (encontra padroes).',
            'Overfitting: modelo memoriza treino mas nao generaliza para novos dados.',
            'Feature: variavel de entrada usada pelo modelo para fazer previsoes.',
            'Validacao cruzada: tecnica para avaliar modelos dividindo dados em folds.',
            'Acuracia: proporcao de previsoes corretas sobre o total.',
            'F1-score: media harmonica entre precisao e recall.',
            'Clustering: agrupamento de dados similares sem rotulos.',
        ],
    },
    'Gestao de Projetos': {
        'ementa': 'Fundamentos de gestao de projetos. PMBOK e areas de conhecimento. Escopo, tempo, custo e qualidade. Gestao de riscos. Gestao de stakeholders. Ferramentas de gestao. Lideranca e comunicacao. Projetos de software.',
        'topicos': [
            'Unidade 1: Fundamentos de gestao de projetos - conceitos e ciclo de vida',
            'Unidade 2: PMBOK - areas de conhecimento e grupos de processos',
            'Unidade 3: Gestao de escopo - WBS, requisitos, controle de mudancas',
            'Unidade 4: Gestao de tempo - cronograma, caminho critico, Gantt',
            'Unidade 5: Gestao de custos - orcamento, valor agregado (EVM)',
            'Unidade 6: Gestao de riscos - identificacao, analise, resposta',
            'Unidade 7: Gestao de stakeholders e comunicacao',
            'Unidade 8: Lideranca, motivacao e gestao de equipes de software',
        ],
        'bibliografia': [
            'PMI. Guia PMBOK. Project Management Institute, 2021.',
            'KERZNER, H. Gestao de Projetos: As Melhores Praticas. Bookman, 2017.',
            'PRESSMAN, R. Engenharia de Software. McGraw-Hill, 2021.',
        ],
        'introducao': (
            'A Gestao de Projetos e a disciplina que garante que projetos de software sejam '
            'entregues no prazo, dentro do orcamento e com a qualidade esperada. Mesmo com '
            'metodologias ageis, habilidades de gestao sao essenciais: planejar escopo, '
            'gerenciar riscos, comunicar com stakeholders e liderar equipes. O PMBOK fornece '
            'um framework abrangente, enquanto abordagens ageis complementam com flexibilidade. '
            'Um bom gestor de projetos e a ponte entre a equipe tecnica e o negocio.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Triplice Restricao e Gestao de Escopo',
                'explicacao': (
                    'A triplice restricao (escopo, tempo, custo) define os limites de um projeto. '
                    'Alterar um afeta os outros. A WBS (Work Breakdown Structure) decompoe o projeto '
                    'em entregas menores e gerenciaveis. O controle de mudancas garante que alteracoes '
                    'no escopo sejam avaliadas quanto ao impacto em prazo e custo antes de serem aprovadas.'
                ),
                'exemplo': (
                    'WBS para um projeto de e-commerce:\n'
                    '1. E-commerce\n'
                    '   1.1 Frontend\n'
                    '       1.1.1 Pagina inicial\n'
                    '       1.1.2 Catalogo de produtos\n'
                    '       1.1.3 Carrinho de compras\n'
                    '       1.1.4 Checkout\n'
                    '   1.2 Backend\n'
                    '       1.2.1 API de produtos\n'
                    '       1.2.2 API de pedidos\n'
                    '       1.2.3 Integracao pagamento\n'
                    '   1.3 Infraestrutura\n'
                    '       1.3.1 Servidor\n'
                    '       1.3.2 Banco de dados\n'
                    '       1.3.3 CI/CD'
                ),
            },
            {
                'titulo': 'Gestao de Riscos',
                'explicacao': (
                    'Riscos sao eventos incertos que podem impactar o projeto positiva ou negativamente. '
                    'O processo inclui: identificacao (brainstorming, checklists), analise qualitativa '
                    '(probabilidade x impacto), analise quantitativa (simulacao Monte Carlo), '
                    'planejamento de respostas (evitar, mitigar, transferir, aceitar) e monitoramento. '
                    'Uma matriz de riscos prioriza os riscos mais criticos.'
                ),
                'exemplo': (
                    'Matriz de Riscos (Probabilidade x Impacto):\n'
                    'Risco: "Desenvolvedor-chave sair do projeto"\n'
                    'Probabilidade: Media (3/5)\n'
                    'Impacto: Alto (4/5)\n'
                    'Score: 12/25 -> Prioridade ALTA\n\n'
                    'Resposta: Mitigar\n'
                    '- Documentar conhecimento critico\n'
                    '- Fazer pair programming para compartilhar conhecimento\n'
                    '- Ter plano de backup com outro desenvolvedor'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Quais sao os tres elementos da triplice restricao de projetos?', 'alternativas': ['a) Pessoas, processos, tecnologia', 'b) Escopo, tempo, custo', 'c) Qualidade, risco, comunicacao', 'd) Planejamento, execucao, controle'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Crie uma WBS simplificada para um projeto de aplicativo mobile de delivery de comida.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual estrategia de resposta a riscos envolve contratar um seguro?', 'alternativas': ['a) Evitar', 'b) Mitigar', 'c) Transferir', 'd) Aceitar'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Identifique 3 riscos comuns em projetos de software e proponha estrategias de mitigacao para cada um.'},
        ],
        'dicas_estudo': [
            'Estude o PMBOK como referencia, mas foque nos conceitos praticos.',
            'Use ferramentas como MS Project, Asana ou Monday.com para praticar.',
            'Pratique criando WBS e cronogramas para projetos pessoais.',
            'Estude para a certificacao CAPM (Certified Associate in Project Management).',
            'Desenvolva habilidades de comunicacao e lideranca — sao tao importantes quanto as tecnicas.',
        ],
        'glossario': [
            'PMBOK: Project Management Body of Knowledge — guia de gestao de projetos.',
            'WBS: Work Breakdown Structure — decomposicao do projeto em entregas.',
            'Caminho critico: sequencia mais longa de atividades que determina a duracao minima.',
            'EVM: Earned Value Management — tecnica para medir desempenho do projeto.',
            'Stakeholder: qualquer pessoa ou grupo afetado pelo projeto.',
            'Risco: evento incerto que pode impactar o projeto.',
            'Escopo: todo o trabalho necessario para entregar o produto do projeto.',
            'Milestone: marco importante no cronograma do projeto.',
        ],
    },
    'UX/UI Design': {
        'ementa': 'Fundamentos de UX (User Experience). Pesquisa com usuarios. Arquitetura de informacao. Wireframes e prototipos. Design de interfaces (UI). Principios de usabilidade. Design responsivo. Testes de usabilidade. Ferramentas (Figma).',
        'topicos': [
            'Unidade 1: Fundamentos de UX - o que e, por que importa, processo de design',
            'Unidade 2: Pesquisa com usuarios - entrevistas, personas, jornada do usuario',
            'Unidade 3: Arquitetura de informacao e fluxos de navegacao',
            'Unidade 4: Wireframes - baixa e alta fidelidade',
            'Unidade 5: Design de interfaces (UI) - tipografia, cores, espacamento, grid',
            'Unidade 6: Prototipos interativos com Figma',
            'Unidade 7: Principios de usabilidade e heuristicas de Nielsen',
            'Unidade 8: Testes de usabilidade e iteracao baseada em feedback',
        ],
        'bibliografia': [
            'NORMAN, D. O Design do Dia a Dia. Rocco, 2006.',
            'KRUG, S. Nao Me Faca Pensar. Alta Books, 2014.',
            'GARRETT, J. The Elements of User Experience. New Riders, 2010.',
        ],
        'introducao': (
            'UX/UI Design e a disciplina que garante que software seja facil de usar, '
            'agradavel e eficiente. UX (User Experience) foca na experiencia completa do '
            'usuario, desde a descoberta ate o uso diario. UI (User Interface) foca no design '
            'visual da interface. Para engenheiros de software, entender UX/UI e essencial '
            'para construir produtos que as pessoas realmente querem usar. Um software '
            'tecnicamente perfeito mas dificil de usar e um fracasso.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Processo de Design Centrado no Usuario',
                'explicacao': (
                    'O design centrado no usuario (DCU) coloca as necessidades do usuario no centro '
                    'de todas as decisoes. O processo inclui: pesquisa (entender usuarios e problemas), '
                    'definicao (personas, jornadas), ideacao (brainstorming, sketches), prototipacao '
                    '(wireframes, prototipos) e teste (usabilidade). O ciclo e iterativo — cada rodada '
                    'de feedback melhora o design.'
                ),
                'exemplo': (
                    'Processo DCU para um app de banco:\n'
                    '1. Pesquisa: entrevistar 10 usuarios sobre dificuldades\n'
                    '2. Persona: "Maria, 35 anos, usa celular para tudo"\n'
                    '3. Jornada: descobrir que transferencia PIX tem 7 passos\n'
                    '4. Ideacao: redesenhar para 3 passos\n'
                    '5. Wireframe: esbocar nova tela de transferencia\n'
                    '6. Prototipo: criar prototipo clicavel no Figma\n'
                    '7. Teste: 5 usuarios testam, 4 completam em menos de 30s\n'
                    '8. Iterar: ajustar com base no feedback'
                ),
            },
            {
                'titulo': 'Heuristicas de Usabilidade de Nielsen',
                'explicacao': (
                    'Jakob Nielsen definiu 10 heuristicas de usabilidade que sao referencia mundial: '
                    '1) Visibilidade do status do sistema, 2) Correspondencia com o mundo real, '
                    '3) Controle e liberdade do usuario, 4) Consistencia e padroes, '
                    '5) Prevencao de erros, 6) Reconhecimento em vez de memorizacao, '
                    '7) Flexibilidade e eficiencia, 8) Design estetico e minimalista, '
                    '9) Ajuda para reconhecer e recuperar erros, 10) Ajuda e documentacao.'
                ),
                'exemplo': (
                    'Exemplos praticos das heuristicas:\n'
                    '1. Visibilidade: barra de progresso ao fazer upload\n'
                    '2. Mundo real: icone de lixeira para deletar\n'
                    '3. Controle: botao "Desfazer" apos excluir email\n'
                    '4. Consistencia: botao "Salvar" sempre no mesmo lugar\n'
                    '5. Prevencao: confirmar antes de deletar arquivo\n'
                    '6. Reconhecimento: menu com icones + texto\n'
                    '7. Eficiencia: atalhos de teclado para usuarios avancados\n'
                    '8. Minimalismo: mostrar apenas informacoes essenciais'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual heuristica de Nielsen recomenda mostrar o progresso de uma operacao ao usuario?', 'alternativas': ['a) Prevencao de erros', 'b) Visibilidade do status do sistema', 'c) Consistencia e padroes', 'd) Design minimalista'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Crie uma persona para um aplicativo de gestao financeira pessoal, incluindo nome, idade, objetivos e frustrações.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual ferramenta e mais usada atualmente para design de interfaces e prototipos?', 'alternativas': ['a) Photoshop', 'b) Sketch', 'c) Figma', 'd) InVision'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Avalie a usabilidade de um aplicativo que voce usa diariamente usando 3 heuristicas de Nielsen.'},
        ],
        'dicas_estudo': [
            'Aprenda Figma — e a ferramenta padrao do mercado e e gratuita.',
            'Leia "Nao Me Faca Pensar" de Steve Krug — e curto e essencial.',
            'Pratique avaliando a usabilidade de apps que voce usa no dia a dia.',
            'Crie wireframes e prototipos para seus projetos de programacao.',
            'Faca testes de usabilidade com colegas — 5 usuarios ja revelam 85% dos problemas.',
        ],
        'glossario': [
            'UX: User Experience — experiencia completa do usuario com o produto.',
            'UI: User Interface — design visual da interface.',
            'Persona: personagem ficticio que representa um grupo de usuarios.',
            'Wireframe: esboco de baixa fidelidade de uma interface.',
            'Prototipo: versao interativa e navegavel do design.',
            'Usabilidade: facilidade com que usuarios realizam tarefas no sistema.',
            'Heuristica: principio ou regra geral de usabilidade.',
            'Figma: ferramenta colaborativa de design de interfaces.',
        ],
    },
    'Estagio Supervisionado II': {
        'ementa': 'Aprofundamento da experiencia profissional. Gestao de tempo e produtividade. Trabalho em equipe e colaboracao. Resolucao de problemas complexos. Relatorio final de estagio. Apresentacao de resultados. Reflexao sobre carreira.',
        'topicos': [
            'Unidade 1: Revisao e aprofundamento da experiencia de estagio',
            'Unidade 2: Gestao de tempo e produtividade no ambiente profissional',
            'Unidade 3: Trabalho em equipe - comunicacao, conflitos, colaboracao',
            'Unidade 4: Resolucao de problemas complexos e pensamento critico',
            'Unidade 5: Boas praticas de desenvolvimento em equipe (code review, git flow)',
            'Unidade 6: Documentacao e transferencia de conhecimento',
            'Unidade 7: Elaboracao do relatorio final de estagio',
            'Unidade 8: Apresentacao de resultados e planejamento de carreira',
        ],
        'bibliografia': [
            'BIANCHI, A. Manual de Orientacao: Estagio Supervisionado. Cengage, 2012.',
            'COVEY, S. Os 7 Habitos das Pessoas Altamente Eficazes. Best Seller, 2017.',
            'MARTIN, R. O Codificador Limpo. Alta Books, 2012.',
        ],
        'introducao': (
            'O Estagio Supervisionado II aprofunda a experiencia profissional iniciada no '
            'Estagio I. Nesta fase, o aluno ja esta integrado ao ambiente de trabalho e '
            'assume responsabilidades maiores. O foco e no desenvolvimento de competencias '
            'avancadas como resolucao de problemas complexos, trabalho em equipe eficaz, '
            'gestao de tempo e comunicacao profissional. O relatorio final documenta toda '
            'a experiencia e as licoes aprendidas durante o estagio.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Code Review e Colaboracao em Equipe',
                'explicacao': (
                    'Code review e a pratica de revisar codigo de colegas antes de integra-lo ao '
                    'projeto. Beneficios: encontra bugs cedo, compartilha conhecimento, melhora '
                    'qualidade do codigo e mantem padroes. Git Flow define um fluxo de branches: '
                    'main, develop, feature, release e hotfix. Pull Requests sao o mecanismo '
                    'principal para code review em plataformas como GitHub e GitLab.'
                ),
                'exemplo': (
                    'Fluxo de Code Review:\n'
                    '1. Desenvolvedor cria branch: feature/nova-funcionalidade\n'
                    '2. Implementa e faz commits\n'
                    '3. Abre Pull Request (PR) para develop\n'
                    '4. Reviewer analisa: logica, estilo, testes, seguranca\n'
                    '5. Comentarios e sugestoes de melhoria\n'
                    '6. Desenvolvedor ajusta\n'
                    '7. Aprovacao e merge\n\n'
                    'Boas praticas de review:\n'
                    '- Seja construtivo, nao critico\n'
                    '- Foque em logica e design, nao estilo pessoal\n'
                    '- Sugira melhorias com exemplos'
                ),
            },
            {
                'titulo': 'Gestao de Tempo e Produtividade',
                'explicacao': (
                    'Gestao de tempo e essencial para equilibrar estagio, faculdade e vida pessoal. '
                    'Tecnicas populares: Pomodoro (25min foco + 5min pausa), Eisenhower Matrix '
                    '(urgente vs importante), time blocking (blocos de tempo dedicados) e GTD '
                    '(Getting Things Done). No contexto de desenvolvimento, inclui estimar tarefas '
                    'com precisao e evitar multitasking excessivo.'
                ),
                'exemplo': (
                    'Matriz de Eisenhower:\n'
                    'Urgente + Importante: Bug em producao -> FAZER AGORA\n'
                    'Importante + Nao urgente: Estudar nova tecnologia -> AGENDAR\n'
                    'Urgente + Nao importante: Email de reuniao -> DELEGAR\n'
                    'Nao urgente + Nao importante: Redes sociais -> ELIMINAR\n\n'
                    'Tecnica Pomodoro:\n'
                    '25 min: foco total em uma tarefa\n'
                    '5 min: pausa curta\n'
                    'A cada 4 pomodoros: pausa longa (15-30 min)'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'dissertativa', 'enunciado': 'Descreva o processo de code review em uma equipe de desenvolvimento e explique por que e importante.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual tecnica de gestao de tempo usa ciclos de 25 minutos de foco?', 'alternativas': ['a) GTD', 'b) Pomodoro', 'c) Eisenhower', 'd) Time blocking'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Reflita sobre sua experiencia de estagio: quais foram os 3 maiores aprendizados e como eles complementaram sua formacao academica?'},
            {'tipo': 'multipla_escolha', 'enunciado': 'No Git Flow, qual branch e usada para desenvolvimento de novas funcionalidades?', 'alternativas': ['a) main', 'b) develop', 'c) feature/*', 'd) hotfix/*'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Documente tudo que aprender no estagio — sera util para o relatorio e para a carreira.',
            'Pratique code review com colegas em projetos academicos.',
            'Use a tecnica Pomodoro para manter o foco durante os estudos.',
            'Peca feedback regularmente ao seu supervisor de estagio.',
            'Comece a planejar sua carreira: areas de interesse, certificacoes, pos-graduacao.',
        ],
        'glossario': [
            'Code review: revisao de codigo por pares antes da integracao.',
            'Pull Request: solicitacao de merge de uma branch para outra.',
            'Git Flow: modelo de branching para gerenciar desenvolvimento.',
            'Pomodoro: tecnica de gestao de tempo com ciclos de 25 minutos.',
            'Eisenhower Matrix: ferramenta para priorizar tarefas por urgencia e importancia.',
            'GTD: Getting Things Done — metodologia de produtividade.',
            'Feedback: retorno construtivo sobre desempenho ou trabalho.',
        ],
    },
    # ---- Semestre 7 ----
    'Computacao em Nuvem Avancada': {
        'ementa': 'Arquiteturas cloud-native. Serverless computing. Servicos gerenciados avancados. Multi-cloud e cloud hibrida. Otimizacao de custos. Alta disponibilidade e disaster recovery. Seguranca em nuvem. Well-Architected Framework.',
        'topicos': [
            'Unidade 1: Arquiteturas cloud-native - 12-factor apps, microservicos',
            'Unidade 2: Serverless - AWS Lambda, API Gateway, Step Functions',
            'Unidade 3: Servicos gerenciados - bancos de dados, filas, cache',
            'Unidade 4: Containers na nuvem - ECS, EKS, Fargate',
            'Unidade 5: Alta disponibilidade - multi-AZ, auto scaling, load balancing',
            'Unidade 6: Disaster recovery - estrategias (backup, pilot light, warm standby)',
            'Unidade 7: Seguranca em nuvem - IAM, VPC, encryption, compliance',
            'Unidade 8: Well-Architected Framework e otimizacao de custos',
        ],
        'bibliografia': [
            'WITTIG, M.; WITTIG, A. Amazon Web Services in Action. Manning, 2023.',
            'BURNS, B. Designing Distributed Systems. O\'Reilly, 2018.',
            'AWS. AWS Well-Architected Framework. docs.aws.amazon.com.',
        ],
        'introducao': (
            'Computacao em Nuvem Avancada aprofunda os conceitos de cloud computing para '
            'arquiteturas de producao. Alem de usar servicos basicos, engenheiros de software '
            'precisam projetar sistemas altamente disponiveis, escalaveis, seguros e otimizados '
            'em custo. O Well-Architected Framework da AWS fornece pilares para avaliar e '
            'melhorar arquiteturas. Serverless, containers gerenciados e servicos de IA/ML '
            'na nuvem sao ferramentas poderosas para construir aplicacoes modernas.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Serverless e Funcoes como Servico (FaaS)',
                'explicacao': (
                    'Serverless permite executar codigo sem gerenciar servidores. O provedor aloca '
                    'recursos automaticamente e cobra apenas pelo tempo de execucao. AWS Lambda e '
                    'o servico FaaS mais popular. Combinado com API Gateway, S3, DynamoDB e Step '
                    'Functions, permite construir aplicacoes completas sem servidores. Vantagens: '
                    'zero administracao, escalabilidade automatica, custo por uso.'
                ),
                'exemplo': (
                    'AWS Lambda + API Gateway:\n'
                    'Usuario -> API Gateway -> Lambda -> DynamoDB\n\n'
                    'Lambda function (Python):\n'
                    'def handler(event, context):\n'
                    '    body = json.loads(event["body"])\n'
                    '    table.put_item(Item=body)\n'
                    '    return {\n'
                    '        "statusCode": 200,\n'
                    '        "body": json.dumps({"message": "Salvo!"})\n'
                    '    }\n\n'
                    'Custo: ~$0.20 por 1 milhao de invocacoes'
                ),
            },
            {
                'titulo': 'Well-Architected Framework',
                'explicacao': (
                    'O AWS Well-Architected Framework define 6 pilares para avaliar arquiteturas: '
                    '1) Excelencia operacional, 2) Seguranca, 3) Confiabilidade, 4) Eficiencia '
                    'de performance, 5) Otimizacao de custos, 6) Sustentabilidade. Cada pilar '
                    'tem principios de design e melhores praticas. O Well-Architected Review '
                    'ajuda equipes a identificar riscos e melhorias em suas arquiteturas.'
                ),
                'exemplo': (
                    '6 Pilares do Well-Architected:\n'
                    '1. Operacional: automatizar deploys, monitorar tudo\n'
                    '2. Seguranca: principio do menor privilegio, criptografia\n'
                    '3. Confiabilidade: multi-AZ, auto scaling, backups\n'
                    '4. Performance: escolher servico certo, cache, CDN\n'
                    '5. Custos: right-sizing, reserved instances, spot\n'
                    '6. Sustentabilidade: eficiencia energetica, regiao verde'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual servico AWS permite executar codigo sem gerenciar servidores?', 'alternativas': ['a) EC2', 'b) ECS', 'c) Lambda', 'd) Lightsail'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Projete uma arquitetura serverless na AWS para um sistema de encurtamento de URLs (como bit.ly).'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Quantos pilares tem o AWS Well-Architected Framework?', 'alternativas': ['a) 4', 'b) 5', 'c) 6', 'd) 7'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Compare as estrategias de disaster recovery: backup/restore, pilot light e warm standby.'},
        ],
        'dicas_estudo': [
            'Use o AWS Free Tier para praticar servicos de nuvem gratuitamente.',
            'Estude para a certificacao AWS Solutions Architect Associate.',
            'Leia o Well-Architected Framework — e gratuito e essencial.',
            'Construa projetos serverless completos (API + Lambda + DynamoDB).',
            'Pratique estimando custos com a AWS Pricing Calculator.',
        ],
        'glossario': [
            'Serverless: modelo onde o provedor gerencia toda a infraestrutura.',
            'FaaS: Functions as a Service — execucao de funcoes sob demanda.',
            'Lambda: servico serverless da AWS para executar codigo.',
            'Multi-AZ: implantacao em multiplas zonas de disponibilidade.',
            'Auto Scaling: ajuste automatico de capacidade conforme demanda.',
            'Well-Architected: framework da AWS para avaliar arquiteturas.',
            'Disaster Recovery: estrategias para recuperacao apos falhas.',
            'IAM: Identity and Access Management — controle de acesso na AWS.',
        ],
    },
    'Big Data': {
        'ementa': 'Fundamentos de Big Data. Os 5 Vs (Volume, Velocidade, Variedade, Veracidade, Valor). Ecossistema Hadoop. Apache Spark. Data lakes e data warehouses. ETL e pipelines de dados. Processamento em tempo real. Visualizacao de dados.',
        'topicos': [
            'Unidade 1: Fundamentos de Big Data - os 5 Vs e desafios',
            'Unidade 2: Ecossistema Hadoop - HDFS, MapReduce, YARN',
            'Unidade 3: Apache Spark - RDDs, DataFrames, Spark SQL',
            'Unidade 4: Data lakes vs data warehouses',
            'Unidade 5: ETL e pipelines de dados - Airflow, Glue',
            'Unidade 6: Processamento em tempo real - Kafka, Spark Streaming, Kinesis',
            'Unidade 7: Bancos NoSQL para Big Data - Cassandra, MongoDB, DynamoDB',
            'Unidade 8: Visualizacao de dados - dashboards, storytelling com dados',
        ],
        'bibliografia': [
            'WHITE, T. Hadoop: The Definitive Guide. O\'Reilly, 2015.',
            'CHAMBERS, B.; ZAHARIA, M. Spark: The Definitive Guide. O\'Reilly, 2018.',
            'KLEPPMANN, M. Designing Data-Intensive Applications. O\'Reilly, 2017.',
        ],
        'introducao': (
            'Big Data refere-se ao processamento e analise de conjuntos de dados massivos '
            'que excedem a capacidade de ferramentas tradicionais. Com a explosao de dados '
            'gerados por redes sociais, IoT, transacoes financeiras e sensores, a capacidade '
            'de processar e extrair valor desses dados e uma competencia critica. '
            'Tecnologias como Hadoop, Spark e Kafka permitem processar petabytes de dados '
            'de forma distribuida e eficiente.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Apache Spark e Processamento Distribuido',
                'explicacao': (
                    'Apache Spark e o framework mais popular para processamento de Big Data. '
                    'Diferente do MapReduce (Hadoop), Spark processa dados em memoria, sendo ate '
                    '100x mais rapido. Suporta batch e streaming. DataFrames oferecem API similar '
                    'a SQL. Spark SQL permite consultas SQL em dados distribuidos. MLlib fornece '
                    'algoritmos de machine learning escalaveis.'
                ),
                'exemplo': (
                    'PySpark - processando dados de vendas:\n'
                    'from pyspark.sql import SparkSession\n\n'
                    'spark = SparkSession.builder.appName("vendas").getOrCreate()\n'
                    'df = spark.read.csv("vendas.csv", header=True)\n\n'
                    '# Total de vendas por regiao\n'
                    'df.groupBy("regiao").sum("valor").show()\n\n'
                    '# SQL\n'
                    'df.createOrReplaceTempView("vendas")\n'
                    'spark.sql("SELECT regiao, SUM(valor) FROM vendas GROUP BY regiao").show()'
                ),
            },
            {
                'titulo': 'Data Lakes e Pipelines de Dados',
                'explicacao': (
                    'Um data lake armazena dados brutos em qualquer formato (estruturado, '
                    'semi-estruturado, nao-estruturado). Diferente do data warehouse, que armazena '
                    'dados ja processados e estruturados. Pipelines de dados (ETL) extraem dados '
                    'de fontes, transformam e carregam no destino. Ferramentas como Apache Airflow '
                    'orquestram pipelines complexos com dependencias e agendamento.'
                ),
                'exemplo': (
                    'Pipeline ETL com Airflow:\n'
                    '1. Extract: ler dados de API, banco, arquivos\n'
                    '2. Transform: limpar, validar, agregar\n'
                    '3. Load: salvar no data warehouse\n\n'
                    'Data Lake (S3):\n'
                    's3://meu-data-lake/\n'
                    '  raw/          -> dados brutos (JSON, CSV, logs)\n'
                    '  processed/    -> dados limpos e transformados\n'
                    '  curated/      -> dados prontos para analise'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Quais sao os 5 Vs do Big Data?', 'alternativas': ['a) Volume, Velocidade, Variedade, Veracidade, Valor', 'b) Volume, Velocidade, Visao, Verificacao, Valor', 'c) Volume, Versatilidade, Variedade, Veracidade, Velocidade', 'd) Volume, Velocidade, Variedade, Virtualizacao, Valor'], 'resposta': 'a'},
            {'tipo': 'dissertativa', 'enunciado': 'Compare data lake e data warehouse: quando usar cada um?'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual framework processa Big Data em memoria, sendo mais rapido que MapReduce?', 'alternativas': ['a) Hadoop', 'b) Hive', 'c) Spark', 'd) Pig'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Projete um pipeline de dados para processar logs de acesso de um site com milhoes de visitas diarias.'},
        ],
        'dicas_estudo': [
            'Instale PySpark localmente e pratique com datasets do Kaggle.',
            'Estude o livro "Designing Data-Intensive Applications" de Martin Kleppmann.',
            'Explore servicos de Big Data na AWS: EMR, Glue, Athena, Kinesis.',
            'Pratique SQL avancado — e a base para trabalhar com dados.',
            'Aprenda a criar dashboards com ferramentas como Metabase ou Superset.',
        ],
        'glossario': [
            'Big Data: dados massivos que excedem capacidade de ferramentas tradicionais.',
            'Hadoop: framework open source para processamento distribuido.',
            'Spark: framework rapido para processamento de Big Data em memoria.',
            'Data Lake: repositorio de dados brutos em qualquer formato.',
            'Data Warehouse: repositorio de dados estruturados e processados.',
            'ETL: Extract, Transform, Load — pipeline de processamento de dados.',
            'Kafka: plataforma de streaming de eventos distribuida.',
            'MapReduce: modelo de programacao para processamento paralelo.',
        ],
    },
    'Empreendedorismo Digital': {
        'ementa': 'Fundamentos de empreendedorismo. Startups e modelos de negocio. Lean Startup e MVP. Business Model Canvas. Marketing digital. Financiamento e investimento. Propriedade intelectual. Ecossistema de inovacao.',
        'topicos': [
            'Unidade 1: Fundamentos de empreendedorismo e mentalidade empreendedora',
            'Unidade 2: Identificacao de oportunidades e validacao de ideias',
            'Unidade 3: Lean Startup - Build, Measure, Learn',
            'Unidade 4: MVP (Minimum Viable Product) e prototipacao rapida',
            'Unidade 5: Business Model Canvas e proposta de valor',
            'Unidade 6: Marketing digital e growth hacking',
            'Unidade 7: Financiamento - bootstrapping, anjos, venture capital',
            'Unidade 8: Aspectos legais - MEI, CNPJ, propriedade intelectual, LGPD',
        ],
        'bibliografia': [
            'RIES, E. A Startup Enxuta. Leya, 2012.',
            'OSTERWALDER, A. Business Model Generation. Alta Books, 2011.',
            'BLANK, S. Do Sonho a Realizacao em 4 Passos. Evora, 2012.',
        ],
        'introducao': (
            'Empreendedorismo Digital e a capacidade de criar negocios inovadores usando '
            'tecnologia. Para engenheiros de software, empreender e uma opcao natural — '
            'voce tem as habilidades tecnicas para construir produtos digitais. Esta disciplina '
            'ensina a transformar ideias em negocios viaveis usando metodologias como Lean '
            'Startup, validacao com MVP e modelagem de negocios com Canvas. O ecossistema '
            'de startups brasileiro esta em crescimento e oferece muitas oportunidades.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Lean Startup e MVP',
                'explicacao': (
                    'A metodologia Lean Startup propoe um ciclo rapido de Build-Measure-Learn. '
                    'Em vez de gastar meses construindo um produto completo, crie um MVP (Minimum '
                    'Viable Product) — a versao mais simples que entrega valor e permite aprender '
                    'com usuarios reais. Metricas de vaidade (likes, pageviews) devem ser substituidas '
                    'por metricas acionaveis (conversao, retencao, receita).'
                ),
                'exemplo': (
                    'Ciclo Lean Startup:\n'
                    '1. IDEIA: "App de delivery de comida saudavel"\n'
                    '2. BUILD: MVP = pagina no Instagram + WhatsApp\n'
                    '3. MEASURE: 50 pedidos na primeira semana?\n'
                    '4. LEARN: clientes querem opcoes veganas\n'
                    '5. PIVOTAR ou PERSEVERAR\n\n'
                    'MVP nao precisa ser um app!\n'
                    'Dropbox: video demonstrativo\n'
                    'Zappos: fotos de sapatos de lojas fisicas\n'
                    'Airbnb: site simples com fotos do proprio apartamento'
                ),
            },
            {
                'titulo': 'Business Model Canvas',
                'explicacao': (
                    'O Business Model Canvas e uma ferramenta visual com 9 blocos que descrevem '
                    'o modelo de negocio: 1) Segmentos de clientes, 2) Proposta de valor, '
                    '3) Canais, 4) Relacionamento com clientes, 5) Fontes de receita, '
                    '6) Recursos-chave, 7) Atividades-chave, 8) Parcerias-chave, 9) Estrutura '
                    'de custos. Permite visualizar e iterar o modelo de negocio rapidamente.'
                ),
                'exemplo': (
                    'Canvas para um SaaS de gestao de projetos:\n'
                    'Segmentos: startups e PMEs de tecnologia\n'
                    'Proposta de valor: gestao agil simples e acessivel\n'
                    'Canais: site, Google Ads, marketing de conteudo\n'
                    'Receita: assinatura mensal (freemium + premium)\n'
                    'Recursos: plataforma web, equipe de dev\n'
                    'Atividades: desenvolvimento, suporte, marketing\n'
                    'Parcerias: integradores, influenciadores tech\n'
                    'Custos: servidores, salarios, marketing'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'O que significa MVP no contexto de startups?', 'alternativas': ['a) Most Valuable Player', 'b) Minimum Viable Product', 'c) Maximum Value Proposition', 'd) Minimum Validated Process'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Preencha um Business Model Canvas para uma startup de sua escolha na area de tecnologia.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual e o ciclo principal da metodologia Lean Startup?', 'alternativas': ['a) Plan-Do-Check-Act', 'b) Build-Measure-Learn', 'c) Design-Develop-Deploy', 'd) Ideate-Prototype-Test'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Proponha um MVP para um aplicativo que resolve um problema real que voce identifica no dia a dia. Descreva o problema, a solucao e como validaria a ideia.'},
        ],
        'dicas_estudo': [
            'Leia "A Startup Enxuta" de Eric Ries — e o livro fundamental.',
            'Participe de hackathons e competicoes de startups.',
            'Converse com empreendedores e mentores em eventos de inovacao.',
            'Valide suas ideias antes de construir — fale com potenciais clientes.',
            'Estude casos de sucesso e fracasso de startups brasileiras.',
        ],
        'glossario': [
            'Startup: empresa em fase inicial com modelo de negocio escalavel.',
            'MVP: Minimum Viable Product — versao minima viavel do produto.',
            'Lean Startup: metodologia de criacao de startups com ciclos rapidos.',
            'Canvas: Business Model Canvas — ferramenta visual de modelo de negocio.',
            'Pivot: mudanca de direcao estrategica baseada em aprendizado.',
            'Growth hacking: estrategias criativas de crescimento rapido.',
            'Venture capital: investimento de risco em startups com alto potencial.',
            'Bootstrapping: financiar a startup com recursos proprios.',
        ],
    },
    'Etica em TI': {
        'ementa': 'Etica profissional em tecnologia. Privacidade e protecao de dados (LGPD/GDPR). Propriedade intelectual e software livre. Vieses algoritmicos e IA responsavel. Impactos sociais da tecnologia. Seguranca cibernetica e responsabilidade. Codigo de etica profissional.',
        'topicos': [
            'Unidade 1: Fundamentos de etica e etica profissional em TI',
            'Unidade 2: Privacidade digital e protecao de dados pessoais',
            'Unidade 3: LGPD - principios, bases legais, direitos dos titulares',
            'Unidade 4: Propriedade intelectual - direitos autorais, patentes, licencas de software',
            'Unidade 5: Software livre e open source - licencas (MIT, GPL, Apache)',
            'Unidade 6: Vieses algoritmicos e IA responsavel',
            'Unidade 7: Impactos sociais da tecnologia - inclusao digital, fake news, vigilancia',
            'Unidade 8: Responsabilidade profissional e codigo de etica (ACM, IEEE)',
        ],
        'bibliografia': [
            'PINHEIRO, P. Direito Digital. Saraiva, 2021.',
            'DONEDA, D. Da Privacidade a Protecao de Dados Pessoais. RT, 2019.',
            'O\'NEIL, C. Algoritmos de Destruicao em Massa. Rua do Sabao, 2020.',
        ],
        'introducao': (
            'A Etica em TI e uma disciplina fundamental em um mundo cada vez mais digital. '
            'Engenheiros de software tomam decisoes que afetam milhoes de pessoas: como dados '
            'sao coletados e usados, como algoritmos tomam decisoes, quem tem acesso a tecnologia. '
            'A LGPD no Brasil e o GDPR na Europa estabelecem regras para protecao de dados. '
            'Vieses em algoritmos de IA podem perpetuar discriminacao. Entender essas questoes '
            'e responsabilidade de todo profissional de tecnologia.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'LGPD e Protecao de Dados',
                'explicacao': (
                    'A Lei Geral de Protecao de Dados (LGPD - Lei 13.709/2018) regula o tratamento '
                    'de dados pessoais no Brasil. Principios: finalidade, adequacao, necessidade, '
                    'transparencia, seguranca. Bases legais: consentimento, contrato, obrigacao legal, '
                    'interesse legitimo. Direitos dos titulares: acesso, correcao, exclusao, '
                    'portabilidade. Empresas devem ter um DPO (Encarregado de Dados).'
                ),
                'exemplo': (
                    'Aplicacao da LGPD em um sistema web:\n'
                    '1. Consentimento: checkbox claro para coleta de dados\n'
                    '2. Finalidade: coletar apenas dados necessarios\n'
                    '3. Transparencia: politica de privacidade acessivel\n'
                    '4. Seguranca: criptografia, controle de acesso\n'
                    '5. Direito de exclusao: botao "Excluir minha conta"\n'
                    '6. Portabilidade: exportar dados em formato padrao\n\n'
                    'Multa por descumprimento: ate 2% do faturamento\n'
                    '(maximo R$ 50 milhoes por infracao)'
                ),
            },
            {
                'titulo': 'Vieses Algoritmicos e IA Responsavel',
                'explicacao': (
                    'Algoritmos de IA podem perpetuar e amplificar preconceitos presentes nos dados '
                    'de treinamento. Exemplos: sistemas de recrutamento que discriminam mulheres, '
                    'reconhecimento facial com menor acuracia para pessoas negras, algoritmos de '
                    'credito que penalizam minorias. IA responsavel exige: diversidade nos dados, '
                    'auditoria de vieses, transparencia nas decisoes e accountability.'
                ),
                'exemplo': (
                    'Caso real: Amazon descartou ferramenta de recrutamento com IA\n'
                    'Problema: treinada com curriculos de 10 anos (maioria homens)\n'
                    'Resultado: penalizava curriculos com palavras como "feminino"\n'
                    'Solucao: descartaram a ferramenta\n\n'
                    'Checklist de IA Responsavel:\n'
                    '1. Dados de treino sao representativos e diversos?\n'
                    '2. O modelo foi testado para vieses?\n'
                    '3. As decisoes sao explicaveis?\n'
                    '4. Existe supervisao humana?\n'
                    '5. Impactos negativos foram avaliados?'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual lei brasileira regula a protecao de dados pessoais?', 'alternativas': ['a) Marco Civil da Internet', 'b) LGPD', 'c) Lei de Acesso a Informacao', 'd) Codigo de Defesa do Consumidor'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Analise um caso real de vies algoritmico e proponha medidas para evita-lo.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual licenca de software livre exige que derivados tambem sejam open source?', 'alternativas': ['a) MIT', 'b) Apache 2.0', 'c) GPL', 'd) BSD'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Como um engenheiro de software deve aplicar os principios da LGPD ao desenvolver um aplicativo que coleta dados de saude?'},
        ],
        'dicas_estudo': [
            'Leia a LGPD na integra — e uma lei relativamente curta e acessivel.',
            'Acompanhe decisoes da ANPD (Autoridade Nacional de Protecao de Dados).',
            'Estude casos reais de vieses algoritmicos e suas consequencias.',
            'Conheca as diferentes licencas de software (MIT, GPL, Apache).',
            'Reflita sobre o impacto etico das tecnologias que voce desenvolve.',
        ],
        'glossario': [
            'LGPD: Lei Geral de Protecao de Dados Pessoais (Lei 13.709/2018).',
            'GDPR: General Data Protection Regulation — lei europeia de protecao de dados.',
            'DPO: Data Protection Officer — encarregado de protecao de dados.',
            'Vies algoritmico: tendencia sistematica em decisoes automatizadas.',
            'Software livre: software com liberdade de uso, estudo, modificacao e distribuicao.',
            'GPL: General Public License — licenca copyleft que exige codigo aberto.',
            'MIT License: licenca permissiva que permite uso quase irrestrito.',
            'IA Responsavel: desenvolvimento de IA com etica, transparencia e accountability.',
        ],
    },
    'TCC I': {
        'ementa': 'Metodologia de pesquisa cientifica. Definicao de tema e problema de pesquisa. Revisao bibliografica. Projeto de pesquisa. Escrita academica. Normas ABNT. Orientacao academica. Proposta de TCC.',
        'topicos': [
            'Unidade 1: Metodologia cientifica - tipos de pesquisa e metodos',
            'Unidade 2: Escolha do tema e definicao do problema de pesquisa',
            'Unidade 3: Revisao bibliografica e estado da arte',
            'Unidade 4: Objetivos, justificativa e hipoteses',
            'Unidade 5: Metodologia - como sera conduzida a pesquisa/desenvolvimento',
            'Unidade 6: Cronograma e planejamento do TCC',
            'Unidade 7: Escrita academica e normas ABNT (citacoes, referencias)',
            'Unidade 8: Apresentacao da proposta de TCC (banca de qualificacao)',
        ],
        'bibliografia': [
            'GIL, A. Como Elaborar Projetos de Pesquisa. Atlas, 2019.',
            'WAZLAWICK, R. Metodologia de Pesquisa para Ciencia da Computacao. Elsevier, 2014.',
            'ASSOCIACAO BRASILEIRA DE NORMAS TECNICAS. NBR 14724. ABNT, 2011.',
        ],
        'introducao': (
            'O TCC I (Trabalho de Conclusao de Curso - Parte 1) e o inicio do projeto final '
            'de graduacao. Nesta fase, o aluno define o tema, realiza a revisao bibliografica, '
            'elabora a proposta de pesquisa e planeja o desenvolvimento. O TCC e a oportunidade '
            'de aplicar todos os conhecimentos adquiridos ao longo do curso em um projeto '
            'significativo. Uma boa proposta e a base para um TCC de qualidade.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Metodologia de Pesquisa em Computacao',
                'explicacao': (
                    'Pesquisa em computacao pode ser: experimental (implementar e avaliar), '
                    'estudo de caso (analisar situacao real), survey (questionarios), '
                    'pesquisa-acao (intervir e observar) ou prova de conceito (demonstrar viabilidade). '
                    'O metodo cientifico exige: problema claro, revisao da literatura, metodologia '
                    'definida, resultados mensuraveis e conclusoes fundamentadas.'
                ),
                'exemplo': (
                    'Estrutura de uma proposta de TCC:\n'
                    '1. Titulo: claro e especifico\n'
                    '2. Introducao: contexto e motivacao\n'
                    '3. Problema: pergunta de pesquisa\n'
                    '4. Objetivos: geral e especificos\n'
                    '5. Justificativa: por que e relevante\n'
                    '6. Revisao bibliografica: o que ja existe\n'
                    '7. Metodologia: como sera feito\n'
                    '8. Cronograma: quando cada etapa sera realizada\n'
                    '9. Referencias: fontes consultadas'
                ),
            },
            {
                'titulo': 'Revisao Bibliografica e Estado da Arte',
                'explicacao': (
                    'A revisao bibliografica mapeia o que ja foi pesquisado sobre o tema. '
                    'Fontes: artigos cientificos (Google Scholar, IEEE, ACM), livros, '
                    'dissertacoes e teses. O estado da arte identifica as solucoes mais recentes '
                    'e as lacunas que seu trabalho pode preencher. Use ferramentas como Mendeley '
                    'ou Zotero para gerenciar referencias.'
                ),
                'exemplo': (
                    'Busca bibliografica sistematica:\n'
                    '1. Definir palavras-chave: "machine learning" AND "fraud detection"\n'
                    '2. Buscar em bases: Google Scholar, IEEE Xplore, ACM DL\n'
                    '3. Filtrar por ano (ultimos 5 anos) e relevancia\n'
                    '4. Ler abstracts e selecionar 20-30 artigos\n'
                    '5. Ler completos e fichá-los\n'
                    '6. Identificar: abordagens, resultados, lacunas\n'
                    '7. Escrever a revisao organizando por temas'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'dissertativa', 'enunciado': 'Proponha 3 temas de TCC na area de engenharia de software, definindo problema e objetivo para cada um.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual norma ABNT trata da formatacao de trabalhos academicos?', 'alternativas': ['a) NBR 6023', 'b) NBR 14724', 'c) NBR 10520', 'd) NBR 6028'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Realize uma mini-revisao bibliografica sobre um tema de seu interesse, citando pelo menos 3 fontes.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual tipo de pesquisa envolve implementar uma solucao e avaliar seus resultados?', 'alternativas': ['a) Survey', 'b) Estudo de caso', 'c) Experimental', 'd) Documental'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Comece a pensar no tema do TCC desde cedo — converse com professores.',
            'Use Google Scholar para encontrar artigos cientificos relevantes.',
            'Aprenda a usar Mendeley ou Zotero para gerenciar referencias.',
            'Leia TCCs de alunos anteriores para entender o formato esperado.',
            'Escreva regularmente — a escrita academica melhora com pratica.',
        ],
        'glossario': [
            'TCC: Trabalho de Conclusao de Curso.',
            'Revisao bibliografica: levantamento do que ja foi pesquisado sobre o tema.',
            'Estado da arte: solucoes mais recentes e avancadas sobre o tema.',
            'Metodologia: conjunto de metodos e procedimentos da pesquisa.',
            'ABNT: Associacao Brasileira de Normas Tecnicas.',
            'Hipotese: suposicao a ser testada pela pesquisa.',
            'Qualificacao: apresentacao da proposta de TCC para banca avaliadora.',
        ],
    },
    # ---- Semestre 8 ----
    'IoT e Sistemas Embarcados': {
        'ementa': 'Fundamentos de IoT. Arquitetura de sistemas IoT. Sensores e atuadores. Protocolos de comunicacao (MQTT, CoAP). Plataformas IoT (AWS IoT, Azure IoT). Sistemas embarcados (Arduino, Raspberry Pi). Edge computing. Seguranca em IoT.',
        'topicos': [
            'Unidade 1: Fundamentos de IoT - conceitos, aplicacoes e desafios',
            'Unidade 2: Arquitetura de sistemas IoT - camadas e componentes',
            'Unidade 3: Sensores, atuadores e microcontroladores (Arduino, ESP32)',
            'Unidade 4: Protocolos de comunicacao - MQTT, CoAP, HTTP, WebSocket',
            'Unidade 5: Plataformas IoT na nuvem - AWS IoT Core, Azure IoT Hub',
            'Unidade 6: Edge computing e fog computing',
            'Unidade 7: Processamento e analise de dados IoT',
            'Unidade 8: Seguranca em IoT - autenticacao, criptografia, atualizacoes OTA',
        ],
        'bibliografia': [
            'MCEWEN, A.; CASSIMALLY, H. Designing the Internet of Things. Wiley, 2013.',
            'SCHWARTZ, M. Internet of Things with ESP32. Packt, 2019.',
            'AWS. AWS IoT Developer Guide. docs.aws.amazon.com.',
        ],
        'introducao': (
            'A Internet das Coisas (IoT) conecta dispositivos fisicos a internet, permitindo '
            'coleta de dados, monitoramento e controle remoto. De casas inteligentes a fabricas '
            'automatizadas, IoT esta transformando todos os setores. Para engenheiros de software, '
            'IoT combina hardware (sensores, microcontroladores), software (firmware, backend) '
            'e nuvem (processamento, armazenamento). Entender essa integracao e essencial '
            'para construir solucoes IoT completas e seguras.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Arquitetura IoT e Protocolos',
                'explicacao': (
                    'Uma arquitetura IoT tipica tem 4 camadas: dispositivos (sensores/atuadores), '
                    'conectividade (rede), processamento (nuvem/edge) e aplicacao (dashboard/API). '
                    'MQTT e o protocolo mais usado em IoT: leve, publish/subscribe, ideal para '
                    'dispositivos com recursos limitados. CoAP e similar ao HTTP mas otimizado '
                    'para IoT. AWS IoT Core gerencia milhoes de dispositivos na nuvem.'
                ),
                'exemplo': (
                    'Arquitetura IoT com MQTT:\n'
                    'Sensor (ESP32) -> MQTT Broker -> Backend -> Dashboard\n\n'
                    'MQTT Publish/Subscribe:\n'
                    'Sensor publica: topic="casa/sala/temperatura", payload="25.3"\n'
                    'Backend assina: topic="casa/sala/temperatura"\n'
                    'Recebe automaticamente quando sensor publica\n\n'
                    'AWS IoT Core:\n'
                    'Dispositivo -> MQTT -> IoT Core -> Rule -> Lambda -> DynamoDB'
                ),
            },
            {
                'titulo': 'Edge Computing e Processamento Local',
                'explicacao': (
                    'Edge computing processa dados proximo a fonte (no dispositivo ou gateway local) '
                    'em vez de enviar tudo para a nuvem. Vantagens: menor latencia, economia de '
                    'banda, funcionamento offline, privacidade. AWS IoT Greengrass permite executar '
                    'Lambda functions e modelos de ML diretamente em dispositivos edge. '
                    'Ideal para aplicacoes que exigem resposta em tempo real.'
                ),
                'exemplo': (
                    'Cenario: camera de seguranca com deteccao de intrusos\n\n'
                    'SEM edge: camera -> nuvem -> ML -> alerta (latencia: 2-5s)\n'
                    'COM edge: camera -> ML local -> alerta (latencia: 100ms)\n\n'
                    'AWS IoT Greengrass:\n'
                    '- Executa Lambda no dispositivo\n'
                    '- Roda modelos ML localmente (SageMaker Neo)\n'
                    '- Sincroniza com nuvem quando conectado\n'
                    '- Funciona offline'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual protocolo e mais usado em IoT por ser leve e baseado em publish/subscribe?', 'alternativas': ['a) HTTP', 'b) MQTT', 'c) FTP', 'd) SMTP'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Projete uma arquitetura IoT para monitoramento de temperatura e umidade em uma estufa agricola.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e edge computing?', 'alternativas': ['a) Processamento na nuvem', 'b) Processamento proximo a fonte de dados', 'c) Armazenamento em disco', 'd) Comunicacao via satelite'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Discuta os desafios de seguranca em dispositivos IoT e proponha 3 medidas de protecao.'},
        ],
        'dicas_estudo': [
            'Compre um kit Arduino ou ESP32 e faca projetos praticos.',
            'Explore o AWS IoT Core com o free tier.',
            'Pratique com MQTT usando o broker publico test.mosquitto.org.',
            'Construa um projeto IoT completo: sensor -> nuvem -> dashboard.',
            'Estude seguranca em IoT — dispositivos conectados sao alvos frequentes.',
        ],
        'glossario': [
            'IoT: Internet of Things — rede de dispositivos fisicos conectados.',
            'MQTT: Message Queuing Telemetry Transport — protocolo leve para IoT.',
            'Sensor: dispositivo que mede grandezas fisicas (temperatura, umidade).',
            'Atuador: dispositivo que realiza acoes fisicas (motor, rele, LED).',
            'Edge computing: processamento de dados proximo a fonte.',
            'Microcontrolador: computador em um unico chip (Arduino, ESP32).',
            'OTA: Over-The-Air — atualizacao remota de firmware.',
            'Broker: servidor intermediario no protocolo MQTT.',
        ],
    },
    'Blockchain': {
        'ementa': 'Fundamentos de blockchain. Criptografia aplicada. Consenso distribuido. Bitcoin e criptomoedas. Ethereum e smart contracts. Solidity. DeFi e NFTs. Aplicacoes empresariais. Web3.',
        'topicos': [
            'Unidade 1: Fundamentos de blockchain - historia, conceitos, tipos',
            'Unidade 2: Criptografia aplicada - hash, assinaturas digitais, Merkle trees',
            'Unidade 3: Mecanismos de consenso - PoW, PoS, DPoS, PBFT',
            'Unidade 4: Bitcoin - arquitetura, mineracao, transacoes',
            'Unidade 5: Ethereum e smart contracts - EVM, gas, Solidity',
            'Unidade 6: Desenvolvimento de smart contracts com Solidity',
            'Unidade 7: DeFi, NFTs e tokens (ERC-20, ERC-721)',
            'Unidade 8: Aplicacoes empresariais - supply chain, identidade, votacao',
        ],
        'bibliografia': [
            'ANTONOPOULOS, A. Mastering Bitcoin. O\'Reilly, 2017.',
            'ANTONOPOULOS, A.; WOOD, G. Mastering Ethereum. O\'Reilly, 2018.',
            'TAPSCOTT, D. Blockchain Revolution. Senai-SP, 2016.',
        ],
        'introducao': (
            'Blockchain e uma tecnologia de registro distribuido que permite transacoes seguras '
            'e transparentes sem intermediarios. Originalmente criada para o Bitcoin, a blockchain '
            'evoluiu para suportar smart contracts (Ethereum), financas descentralizadas (DeFi), '
            'tokens nao-fungiveis (NFTs) e aplicacoes empresariais. Para engenheiros de software, '
            'entender blockchain abre portas para uma nova geracao de aplicacoes descentralizadas '
            '(dApps) e a Web3.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Como Funciona a Blockchain',
                'explicacao': (
                    'Uma blockchain e uma cadeia de blocos onde cada bloco contem: hash do bloco '
                    'anterior, timestamp, dados (transacoes) e nonce. O hash do bloco anterior '
                    'cria uma cadeia imutavel — alterar um bloco invalida todos os seguintes. '
                    'Mecanismos de consenso (Proof of Work, Proof of Stake) garantem que todos '
                    'os nos concordem sobre o estado da blockchain sem uma autoridade central.'
                ),
                'exemplo': (
                    'Estrutura de um bloco:\n'
                    'Bloco #42:\n'
                    '  hash_anterior: "0x7f3a..."\n'
                    '  timestamp: 2024-01-15 10:30:00\n'
                    '  transacoes: [\n'
                    '    {de: "Alice", para: "Bob", valor: 1.5 ETH},\n'
                    '    {de: "Carol", para: "Dave", valor: 0.3 ETH}\n'
                    '  ]\n'
                    '  nonce: 48291\n'
                    '  hash: "0x00003b..." (comeca com zeros = PoW)\n\n'
                    'Alterar transacao no bloco #42 muda seu hash,\n'
                    'invalidando bloco #43, #44, ... toda a cadeia!'
                ),
            },
            {
                'titulo': 'Smart Contracts e Solidity',
                'explicacao': (
                    'Smart contracts sao programas que executam automaticamente na blockchain '
                    'quando condicoes pre-definidas sao atendidas. Ethereum e a principal plataforma '
                    'para smart contracts. Solidity e a linguagem de programacao mais usada. '
                    'Smart contracts sao imutaveis apos o deploy — bugs nao podem ser corrigidos '
                    'facilmente, tornando auditoria e testes essenciais.'
                ),
                'exemplo': (
                    'Smart contract simples em Solidity:\n'
                    'pragma solidity ^0.8.0;\n\n'
                    'contract Votacao {\n'
                    '    mapping(string => uint) public votos;\n'
                    '    mapping(address => bool) public jaVotou;\n\n'
                    '    function votar(string memory candidato) public {\n'
                    '        require(!jaVotou[msg.sender], "Ja votou!");\n'
                    '        votos[candidato]++;\n'
                    '        jaVotou[msg.sender] = true;\n'
                    '    }\n'
                    '}'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'O que garante a imutabilidade da blockchain?', 'alternativas': ['a) Criptografia simetrica', 'b) Hash do bloco anterior encadeado', 'c) Servidor central', 'd) Backup automatico'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Compare Proof of Work (PoW) e Proof of Stake (PoS): vantagens e desvantagens de cada mecanismo de consenso.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual linguagem e mais usada para escrever smart contracts na Ethereum?', 'alternativas': ['a) Python', 'b) JavaScript', 'c) Solidity', 'd) Rust'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Proponha uma aplicacao de blockchain para resolver um problema real (fora de criptomoedas). Descreva a arquitetura.'},
        ],
        'dicas_estudo': [
            'Comece entendendo Bitcoin antes de ir para Ethereum e smart contracts.',
            'Pratique Solidity no Remix IDE (remix.ethereum.org) — e online e gratuito.',
            'Estude os ataques mais comuns em smart contracts (reentrancy, overflow).',
            'Explore testnets (Goerli, Sepolia) para testar sem gastar dinheiro real.',
            'Leia "Mastering Ethereum" para uma compreensao profunda.',
        ],
        'glossario': [
            'Blockchain: cadeia de blocos com registros imutaveis e distribuidos.',
            'Smart contract: programa que executa automaticamente na blockchain.',
            'Solidity: linguagem de programacao para smart contracts na Ethereum.',
            'PoW: Proof of Work — consenso por poder computacional (mineracao).',
            'PoS: Proof of Stake — consenso por participacao (staking).',
            'DeFi: Financas Descentralizadas — servicos financeiros sem intermediarios.',
            'NFT: Non-Fungible Token — token unico e nao-intercambiavel.',
            'Gas: taxa paga para executar operacoes na Ethereum.',
            'dApp: aplicacao descentralizada que roda em blockchain.',
        ],
    },
    'Inovacao Tecnologica': {
        'ementa': 'Conceitos de inovacao. Tipos de inovacao (incremental, radical, disruptiva). Gestao da inovacao. Design Thinking. Tendencias tecnologicas. Transformacao digital. Inovacao aberta. Ecossistemas de inovacao.',
        'topicos': [
            'Unidade 1: Fundamentos de inovacao - conceitos e tipos',
            'Unidade 2: Inovacao disruptiva e o dilema do inovador',
            'Unidade 3: Design Thinking - empatia, definicao, ideacao, prototipacao, teste',
            'Unidade 4: Gestao da inovacao em empresas de tecnologia',
            'Unidade 5: Tendencias tecnologicas - IA generativa, quantum computing, metaverso',
            'Unidade 6: Transformacao digital - estrategia e implementacao',
            'Unidade 7: Inovacao aberta e ecossistemas de inovacao',
            'Unidade 8: Futuro da tecnologia e impactos na sociedade',
        ],
        'bibliografia': [
            'CHRISTENSEN, C. O Dilema da Inovacao. M.Books, 2012.',
            'BROWN, T. Design Thinking. Elsevier, 2010.',
            'TIDD, J.; BESSANT, J. Gestao da Inovacao. Bookman, 2015.',
        ],
        'introducao': (
            'Inovacao Tecnologica e a capacidade de criar solucoes novas que geram valor. '
            'Nao se trata apenas de inventar tecnologias, mas de aplica-las para resolver '
            'problemas reais de forma melhor, mais rapida ou mais barata. Design Thinking, '
            'inovacao disruptiva e transformacao digital sao conceitos essenciais para '
            'engenheiros de software que querem liderar mudancas e criar impacto. '
            'Entender tendencias como IA generativa, computacao quantica e Web3 prepara '
            'o profissional para o futuro da tecnologia.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Design Thinking',
                'explicacao': (
                    'Design Thinking e uma abordagem centrada no ser humano para resolver problemas '
                    'complexos. O processo tem 5 etapas: Empatia (entender o usuario), Definicao '
                    '(definir o problema), Ideacao (gerar solucoes criativas), Prototipacao '
                    '(construir versoes rapidas) e Teste (validar com usuarios). O processo e '
                    'iterativo — cada rodada de feedback melhora a solucao.'
                ),
                'exemplo': (
                    'Design Thinking para melhorar fila de restaurante:\n'
                    '1. EMPATIA: observar clientes, entrevistar, mapear dores\n'
                    '   Descoberta: "Esperar sem saber quanto tempo falta e frustrante"\n'
                    '2. DEFINICAO: "Como podemos reduzir a percepcao de espera?"\n'
                    '3. IDEACAO: brainstorming de solucoes\n'
                    '   - App com tempo estimado\n'
                    '   - Cardapio digital na fila\n'
                    '   - Notificacao por WhatsApp\n'
                    '4. PROTOTIPO: mockup do app de fila virtual\n'
                    '5. TESTE: 10 clientes testam por 1 semana'
                ),
            },
            {
                'titulo': 'Inovacao Disruptiva',
                'explicacao': (
                    'Inovacao disruptiva (Clayton Christensen) ocorre quando uma tecnologia simples '
                    'e acessivel substitui gradualmente solucoes estabelecidas. Exemplos classicos: '
                    'Netflix vs Blockbuster, Uber vs taxis, smartphones vs cameras digitais. '
                    'Empresas estabelecidas frequentemente ignoram inovacoes disruptivas porque '
                    'inicialmente atendem apenas mercados de nicho ou de baixo custo.'
                ),
                'exemplo': (
                    'Exemplos de inovacao disruptiva:\n'
                    'Netflix: streaming simples -> destruiu locadoras\n'
                    'Uber: app de transporte -> transformou mobilidade\n'
                    'Airbnb: alugar quartos -> desafiou hoteis\n'
                    'Spotify: streaming de musica -> substituiu CDs e downloads\n'
                    'ChatGPT: IA generativa -> transformando busca e criacao\n\n'
                    'Padrao: comeca simples e barato, melhora rapidamente,\n'
                    'eventualmente supera a solucao estabelecida.'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Quais sao as 5 etapas do Design Thinking?', 'alternativas': ['a) Planejar, Executar, Testar, Entregar, Manter', 'b) Empatia, Definicao, Ideacao, Prototipacao, Teste', 'c) Pesquisar, Analisar, Projetar, Implementar, Avaliar', 'd) Descobrir, Definir, Desenvolver, Entregar, Medir'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Aplique o processo de Design Thinking para resolver um problema real que voce identifica no campus da universidade.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual conceito descreve quando uma tecnologia simples substitui gradualmente solucoes estabelecidas?', 'alternativas': ['a) Inovacao incremental', 'b) Inovacao radical', 'c) Inovacao disruptiva', 'd) Inovacao aberta'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Escolha uma tendencia tecnologica atual (IA generativa, computacao quantica, metaverso) e analise seu potencial de disrupcao nos proximos 5 anos.'},
        ],
        'dicas_estudo': [
            'Pratique Design Thinking em workshops e projetos academicos.',
            'Leia "O Dilema da Inovacao" de Clayton Christensen.',
            'Acompanhe tendencias em sites como TechCrunch, Wired e MIT Technology Review.',
            'Participe de hackathons e desafios de inovacao.',
            'Estude casos de empresas que falharam por nao inovar (Kodak, Nokia, Blockbuster).',
        ],
        'glossario': [
            'Inovacao disruptiva: tecnologia simples que substitui solucoes estabelecidas.',
            'Design Thinking: abordagem centrada no usuario para resolver problemas.',
            'MVP: Minimum Viable Product — versao minima para validar uma ideia.',
            'Transformacao digital: integracao de tecnologia em todas as areas do negocio.',
            'Inovacao aberta: colaboracao com parceiros externos para inovar.',
            'IA generativa: IA capaz de criar conteudo (texto, imagem, codigo).',
            'Computacao quantica: computacao baseada em principios da mecanica quantica.',
        ],
    },
    'TCC II': {
        'ementa': 'Desenvolvimento do TCC. Implementacao da solucao proposta. Coleta e analise de resultados. Escrita do documento final. Revisao e formatacao. Preparacao para defesa. Apresentacao para banca examinadora.',
        'topicos': [
            'Unidade 1: Revisao da proposta e ajustes no planejamento',
            'Unidade 2: Desenvolvimento/implementacao da solucao',
            'Unidade 3: Testes e validacao da solucao',
            'Unidade 4: Coleta e analise de resultados',
            'Unidade 5: Escrita dos capitulos de resultados e discussao',
            'Unidade 6: Conclusao, trabalhos futuros e revisao final',
            'Unidade 7: Formatacao ABNT e preparacao do documento final',
            'Unidade 8: Preparacao e realizacao da defesa perante banca',
        ],
        'bibliografia': [
            'GIL, A. Como Elaborar Projetos de Pesquisa. Atlas, 2019.',
            'WAZLAWICK, R. Metodologia de Pesquisa para Ciencia da Computacao. Elsevier, 2014.',
            'ECO, U. Como se Faz uma Tese. Perspectiva, 2014.',
        ],
        'introducao': (
            'O TCC II e a fase de execucao e conclusao do Trabalho de Conclusao de Curso. '
            'Com a proposta aprovada no TCC I, o aluno agora implementa a solucao, coleta '
            'resultados, analisa dados e escreve o documento final. A defesa perante uma '
            'banca examinadora e o momento culminante da graduacao, onde o aluno demonstra '
            'dominio do tema e capacidade de pesquisa. Um bom TCC pode abrir portas para '
            'pos-graduacao, publicacoes e oportunidades profissionais.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Analise de Resultados e Discussao',
                'explicacao': (
                    'A analise de resultados apresenta os dados obtidos de forma objetiva, usando '
                    'tabelas, graficos e metricas. A discussao interpreta os resultados a luz da '
                    'revisao bibliografica: como seus resultados se comparam com trabalhos anteriores? '
                    'O que funcionou? O que nao funcionou? Por que? A honestidade sobre limitacoes '
                    'e tao importante quanto destacar conquistas.'
                ),
                'exemplo': (
                    'Estrutura de Resultados e Discussao:\n'
                    '1. Apresentar resultados com dados concretos\n'
                    '   "O sistema processou 1000 requisicoes com latencia\n'
                    '    media de 45ms e taxa de erro de 0.2%"\n\n'
                    '2. Comparar com trabalhos relacionados\n'
                    '   "Comparado ao sistema X (120ms), nossa solucao\n'
                    '    reduziu a latencia em 62.5%"\n\n'
                    '3. Discutir limitacoes\n'
                    '   "O teste foi realizado com dados sinteticos;\n'
                    '    resultados podem variar com dados reais"\n\n'
                    '4. Implicacoes praticas\n'
                    '   "A solucao e viavel para ambientes com ate\n'
                    '    10.000 usuarios simultaneos"'
                ),
            },
            {
                'titulo': 'Preparacao para a Defesa',
                'explicacao': (
                    'A defesa do TCC e uma apresentacao oral (15-20 minutos) seguida de arguicao '
                    'pela banca (2-3 professores). Dicas: conheca profundamente seu trabalho, '
                    'prepare slides claros e visuais, pratique a apresentacao varias vezes, '
                    'antecipe perguntas da banca, seja honesto sobre limitacoes e mantenha a calma. '
                    'A banca avalia: dominio do tema, qualidade tecnica, clareza e capacidade de argumentacao.'
                ),
                'exemplo': (
                    'Estrutura da apresentacao de defesa (15-20 min):\n'
                    '1. Introducao e motivacao (2 min)\n'
                    '2. Problema e objetivos (2 min)\n'
                    '3. Revisao bibliografica resumida (3 min)\n'
                    '4. Metodologia (2 min)\n'
                    '5. Implementacao/desenvolvimento (3 min)\n'
                    '6. Resultados e discussao (4 min)\n'
                    '7. Conclusao e trabalhos futuros (2 min)\n'
                    '8. Agradecimentos (1 min)\n\n'
                    'Dica: maximo 1 slide por minuto\n'
                    'Use imagens, diagramas e graficos — evite texto excessivo'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'dissertativa', 'enunciado': 'Elabore um plano de testes para validar a solucao proposta no seu TCC, incluindo metricas de avaliacao.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual secao do TCC interpreta os dados obtidos a luz da literatura?', 'alternativas': ['a) Metodologia', 'b) Revisao bibliografica', 'c) Discussao', 'd) Introducao'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Prepare um roteiro de apresentacao de 15 minutos para um TCC ficticio sobre "Deteccao de fraudes com Machine Learning".'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Quanto tempo tipicamente dura a apresentacao oral de um TCC?', 'alternativas': ['a) 5-10 minutos', 'b) 15-20 minutos', 'c) 30-45 minutos', 'd) 60 minutos'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Comece a escrever o documento final desde o inicio do desenvolvimento.',
            'Mantenha um diario de pesquisa com decisoes, problemas e solucoes.',
            'Peca feedback do orientador regularmente — nao espere o final.',
            'Pratique a apresentacao pelo menos 5 vezes antes da defesa.',
            'Prepare-se para perguntas dificeis — a banca testa seu conhecimento.',
        ],
        'glossario': [
            'Defesa: apresentacao oral do TCC perante banca examinadora.',
            'Banca: grupo de professores que avalia o TCC.',
            'Arguicao: perguntas e questionamentos feitos pela banca.',
            'Trabalhos futuros: sugestoes de continuidade da pesquisa.',
            'Metricas: medidas quantitativas para avaliar resultados.',
            'Limitacoes: restricoes e pontos fracos reconhecidos no trabalho.',
        ],
    },
    'Projeto Final': {
        'ementa': 'Projeto integrador de conclusao de curso. Desenvolvimento completo de um sistema de software. Aplicacao de todas as disciplinas do curso. Trabalho em equipe. Metodologia agil. Apresentacao e demonstracao do projeto.',
        'topicos': [
            'Unidade 1: Definicao do projeto - escopo, requisitos, equipe',
            'Unidade 2: Arquitetura e design do sistema',
            'Unidade 3: Sprint 1 - setup, infraestrutura, MVP',
            'Unidade 4: Sprint 2 - funcionalidades core',
            'Unidade 5: Sprint 3 - funcionalidades avancadas e integracoes',
            'Unidade 6: Sprint 4 - testes, seguranca, performance',
            'Unidade 7: Deploy, documentacao e preparacao para apresentacao',
            'Unidade 8: Apresentacao final e demonstracao do projeto',
        ],
        'bibliografia': [
            'MARTIN, R. Arquitetura Limpa. Alta Books, 2019.',
            'FOWLER, M. Refactoring. Addison-Wesley, 2018.',
            'HUMBLE, J.; FARLEY, D. Entrega Continua. Bookman, 2014.',
        ],
        'introducao': (
            'O Projeto Final e a disciplina culminante do curso de Engenharia de Software. '
            'Aqui, voce aplica tudo que aprendeu em 8 semestres para construir um sistema '
            'de software completo, do levantamento de requisitos ao deploy em producao. '
            'Trabalhando em equipe com metodologia agil, voce vivencia o ciclo completo '
            'de desenvolvimento profissional. O projeto demonstra sua capacidade de entregar '
            'software de qualidade e e um diferencial importante no portfolio.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Desenvolvimento Completo de Software',
                'explicacao': (
                    'O Projeto Final integra todas as disciplinas: requisitos (Eng. Software), '
                    'arquitetura (Arquitetura de Software), banco de dados (BD I e II), '
                    'frontend (Dev Web/Mobile), backend (Microsservicos), testes (Testes de Software), '
                    'deploy (DevOps), seguranca (Seguranca da Informacao) e gestao (Metodologias Ageis). '
                    'O resultado e um sistema funcional que demonstra competencia profissional.'
                ),
                'exemplo': (
                    'Stack tipica de um Projeto Final:\n'
                    'Frontend: React ou Next.js\n'
                    'Backend: Python (FastAPI) ou Node.js (Express)\n'
                    'Banco: PostgreSQL + Redis (cache)\n'
                    'Infra: Docker + AWS (EC2 ou Lambda)\n'
                    'CI/CD: GitHub Actions\n'
                    'Monitoramento: CloudWatch + Grafana\n\n'
                    'Entregas por sprint:\n'
                    'Sprint 1: Setup + autenticacao + CRUD basico\n'
                    'Sprint 2: Funcionalidades core do negocio\n'
                    'Sprint 3: Integracoes e features avancadas\n'
                    'Sprint 4: Testes, seguranca, performance, deploy'
                ),
            },
            {
                'titulo': 'Trabalho em Equipe e Metodologia Agil',
                'explicacao': (
                    'O Projeto Final e desenvolvido em equipe (3-5 pessoas) usando Scrum. '
                    'Cada membro tem responsabilidades definidas. Sprints de 2 semanas com '
                    'planning, daily, review e retrospectiva. O Product Backlog e priorizado '
                    'pelo time. Code review, pair programming e CI/CD garantem qualidade. '
                    'A comunicacao eficaz e tao importante quanto a habilidade tecnica.'
                ),
                'exemplo': (
                    'Organizacao da equipe (4 pessoas):\n'
                    'Ana: Frontend + UX/UI\n'
                    'Bruno: Backend + APIs\n'
                    'Carlos: DevOps + Infra + Banco\n'
                    'Diana: Testes + Seguranca + Docs\n\n'
                    'Ferramentas:\n'
                    'Comunicacao: Slack ou Discord\n'
                    'Gestao: Jira ou Trello\n'
                    'Codigo: GitHub (monorepo ou multi-repo)\n'
                    'Docs: Notion ou Confluence\n'
                    'Design: Figma'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'dissertativa', 'enunciado': 'Proponha um projeto de software completo: defina o problema, os requisitos principais, a arquitetura e a stack tecnologica.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual metodologia e mais adequada para o desenvolvimento do Projeto Final em equipe?', 'alternativas': ['a) Cascata', 'b) Scrum', 'c) Espiral', 'd) Prototipacao'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Crie um Product Backlog com 10 user stories priorizadas para um sistema de gestao de biblioteca.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que deve ser entregue ao final do Projeto Final?', 'alternativas': ['a) Apenas o codigo-fonte', 'b) Sistema funcionando + documentacao + apresentacao', 'c) Apenas a documentacao', 'd) Apenas a apresentacao'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Escolha um projeto que voce tenha paixao — a motivacao faz diferenca.',
            'Defina o escopo com cuidado — e melhor entregar menos com qualidade.',
            'Use Git Flow e code review desde o primeiro dia.',
            'Documente decisoes arquiteturais (ADRs) ao longo do projeto.',
            'Pratique a apresentacao final com demonstracao ao vivo do sistema.',
        ],
        'glossario': [
            'Projeto integrador: projeto que aplica conhecimentos de multiplas disciplinas.',
            'Sprint: ciclo de desenvolvimento com duracao fixa.',
            'Product Backlog: lista priorizada de funcionalidades do produto.',
            'Code review: revisao de codigo por pares.',
            'CI/CD: Integracao Continua / Entrega Continua.',
            'Deploy: implantacao do sistema em ambiente de producao.',
            'Stack: conjunto de tecnologias usadas no projeto.',
            'ADR: Architecture Decision Record — registro de decisoes arquiteturais.',
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

    print('=== Gerando material didatico de graduacao — Semestres 5 a 8 ===')
    print(f'Disciplinas: {sum(len(d) for d in GRADE_SEM5A8.values())}')
    print(f'Saida: {os.path.join(OUTPUT_DIR, "privado", "graduacao", CURSO_ID_GRAD)}')
    print()

    for semestre_key, disciplinas in GRADE_SEM5A8.items():
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
