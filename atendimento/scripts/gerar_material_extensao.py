"""
Gera PDFs de MATERIAL DIDATICO (estudo) para os 15 cursos de extensao.
Diferente das ementas (gerar_apostilas.py), este script gera conteudo educacional
simplificado que um aluno usaria para estudar.

Cada PDF tem ~5-8 paginas com:
1. Cabecalho institucional (nome do curso, area, modalidade, duracao)
2. Introducao ao tema
3. Conceitos fundamentais (2-3 conceitos-chave com exemplos)
4. Resumo dos principais topicos (modulos)
5. Exercicios de fixacao (3-5 questoes)
6. Dicas de estudo e recursos adicionais
7. Glossario de termos importantes (5-10 termos)

Saida: output/apostilas/privado/extensao/{curso_id}/{course_name}_material.pdf

Uso: source .env && python3 scripts/gerar_material_extensao.py
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

# ============================================================
# Constantes
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output', 'apostilas')

INSTITUICAO = 'Instituicao de Ensino Demo'

# ============================================================
# 15 Cursos de Extensao
# ============================================================
CURSOS_EXTENSAO = [
    {
        'curso_id': 'ext-ia-aplicada',
        'nome': 'Inteligencia Artificial Aplicada',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'duracao_horas': 60,
        'duracao_meses': 3,
    },
    {
        'curso_id': 'ext-cybersecurity',
        'nome': 'Cybersecurity Essentials',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'duracao_horas': 40,
        'duracao_meses': 2,
    },
    {
        'curso_id': 'ext-data-science',
        'nome': 'Data Science com Python',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'duracao_horas': 80,
        'duracao_meses': 4,
    },
    {
        'curso_id': 'ext-cloud-aws',
        'nome': 'Cloud Computing com AWS',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'duracao_horas': 60,
        'duracao_meses': 3,
    },
    {
        'curso_id': 'ext-ux-design',
        'nome': 'UX/UI Design',
        'area': 'Design',
        'modalidade': 'EAD',
        'duracao_horas': 50,
        'duracao_meses': 3,
    },
    {
        'curso_id': 'ext-gestao-projetos',
        'nome': 'Gestao de Projetos e Metodologias Ageis',
        'area': 'Negocios',
        'modalidade': 'EAD',
        'duracao_horas': 40,
        'duracao_meses': 2,
    },
    {
        'curso_id': 'ext-marketing-digital',
        'nome': 'Marketing Digital e Analytics',
        'area': 'Negocios',
        'modalidade': 'EAD',
        'duracao_horas': 45,
        'duracao_meses': 2,
    },
    {
        'curso_id': 'ext-devops',
        'nome': 'DevOps e CI/CD',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'duracao_horas': 60,
        'duracao_meses': 3,
    },
    {
        'curso_id': 'ext-blockchain',
        'nome': 'Blockchain e Web3',
        'area': 'Tecnologia',
        'modalidade': 'EAD',
        'duracao_horas': 40,
        'duracao_meses': 2,
    },
    {
        'curso_id': 'ext-lideranca',
        'nome': 'Lideranca e Gestao de Pessoas',
        'area': 'Negocios',
        'modalidade': 'EAD',
        'duracao_horas': 30,
        'duracao_meses': 2,
    },
    {
        'curso_id': 'ext-saude-mental',
        'nome': 'Saude Mental no Trabalho',
        'area': 'Saude',
        'modalidade': 'EAD',
        'duracao_horas': 30,
        'duracao_meses': 2,
    },
    {
        'curso_id': 'ext-primeiros-socorros',
        'nome': 'Primeiros Socorros e Urgencias',
        'area': 'Saude',
        'modalidade': 'Presencial',
        'duracao_horas': 20,
        'duracao_meses': 1,
    },
    {
        'curso_id': 'ext-nutricao-esportiva',
        'nome': 'Nutricao Esportiva',
        'area': 'Saude',
        'modalidade': 'EAD',
        'duracao_horas': 40,
        'duracao_meses': 2,
    },
    {
        'curso_id': 'ext-direito-digital',
        'nome': 'Direito Digital e LGPD',
        'area': 'Humanas',
        'modalidade': 'EAD',
        'duracao_horas': 30,
        'duracao_meses': 2,
    },
    {
        'curso_id': 'ext-ingles-negocios',
        'nome': 'Ingles para Negocios',
        'area': 'Negocios',
        'modalidade': 'EAD',
        'duracao_horas': 60,
        'duracao_meses': 3,
    },
]


# ============================================================
# Conteudo detalhado por curso de extensao
# ============================================================
CONTEUDO_EXTENSAO = {
    'Inteligencia Artificial Aplicada': {
        'ementa': 'Fundamentos de IA e Machine Learning. Redes neurais e deep learning. Processamento de linguagem natural (NLP). Visao computacional. IA generativa e modelos de linguagem. Aplicacoes praticas de IA em negocios.',
        'topicos': [
            'Modulo 1: Fundamentos de IA - historia, conceitos e tipos de aprendizado',
            'Modulo 2: Machine Learning supervisionado - regressao e classificacao',
            'Modulo 3: Redes neurais artificiais e deep learning',
            'Modulo 4: Processamento de linguagem natural (NLP)',
            'Modulo 5: Visao computacional e reconhecimento de imagens',
            'Modulo 6: IA generativa - ChatGPT, DALL-E, Midjourney',
            'Modulo 7: Etica em IA e vieses algoritmicos',
            'Modulo 8: Projeto pratico - aplicando IA a um problema real',
        ],
        'bibliografia': [
            'GERON, A. Maos a Obra: Aprendizado de Maquina com Scikit-Learn, Keras e TensorFlow. Alta Books, 2021.',
            'RUSSELL, S.; NORVIG, P. Inteligencia Artificial. Elsevier, 2022.',
            'CHOLLET, F. Deep Learning with Python. Manning, 2021.',
        ],
        'introducao': (
            'A Inteligencia Artificial esta transformando todos os setores da economia. '
            'Neste curso de extensao, voce aprendera os fundamentos de IA e Machine Learning '
            'de forma pratica, com projetos reais usando ferramentas como Python, Scikit-learn '
            'e TensorFlow. Ao final, voce sera capaz de identificar oportunidades de aplicacao '
            'de IA no seu dia a dia profissional e implementar solucoes basicas.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Machine Learning e Tipos de Aprendizado',
                'explicacao': (
                    'Machine Learning (ML) e um subcampo da IA que permite que sistemas aprendam '
                    'a partir de dados sem serem explicitamente programados. Existem tres tipos '
                    'principais: supervisionado (dados rotulados), nao supervisionado (sem rotulos) '
                    'e por reforco (aprendizado por tentativa e erro). O aprendizado supervisionado '
                    'e o mais comum e inclui tarefas de classificacao e regressao.'
                ),
                'exemplo': (
                    'Exemplo de classificacao com Scikit-learn:\n'
                    'from sklearn.tree import DecisionTreeClassifier\n'
                    'modelo = DecisionTreeClassifier()\n'
                    'modelo.fit(X_treino, y_treino)\n'
                    'previsao = modelo.predict(X_teste)\n\n'
                    'Aplicacoes: deteccao de spam, diagnostico medico, recomendacao de produtos.'
                ),
            },
            {
                'titulo': 'Redes Neurais e Deep Learning',
                'explicacao': (
                    'Redes neurais artificiais sao modelos inspirados no cerebro humano, compostos '
                    'por camadas de neuronios interconectados. Deep Learning usa redes com muitas '
                    'camadas (profundas) para aprender representacoes complexas dos dados. '
                    'Aplicacoes incluem reconhecimento de imagens, traducao automatica e geracao de texto.'
                ),
                'exemplo': (
                    'Estrutura basica de uma rede neural:\n'
                    'Camada de entrada -> Camadas ocultas -> Camada de saida\n\n'
                    'Cada neuronio: saida = funcao_ativacao(soma_ponderada + bias)\n'
                    'Treinamento: ajuste dos pesos via backpropagation e gradiente descendente.'
                ),
            },
            {
                'titulo': 'IA Generativa e Modelos de Linguagem',
                'explicacao': (
                    'IA generativa cria conteudo novo (texto, imagens, codigo) a partir de padroes '
                    'aprendidos. Modelos de linguagem como GPT usam a arquitetura Transformer para '
                    'gerar texto coerente. Ferramentas como ChatGPT, DALL-E e Midjourney democratizaram '
                    'o acesso a IA generativa, permitindo aplicacoes em diversas areas.'
                ),
                'exemplo': (
                    'Exemplos de uso de IA generativa:\n'
                    '- ChatGPT: assistente de escrita, programacao, analise de dados\n'
                    '- DALL-E/Midjourney: geracao de imagens a partir de descricoes textuais\n'
                    '- GitHub Copilot: assistente de programacao com sugestoes de codigo\n'
                    '- Whisper: transcricao de audio para texto'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual tipo de aprendizado de maquina utiliza dados rotulados para treinamento?', 'alternativas': ['a) Nao supervisionado', 'b) Por reforco', 'c) Supervisionado', 'd) Semi-supervisionado'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique a diferenca entre classificacao e regressao em Machine Learning, dando um exemplo pratico de cada.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e backpropagation em redes neurais?', 'alternativas': ['a) Tecnica de coleta de dados', 'b) Algoritmo de ajuste de pesos baseado no erro', 'c) Metodo de validacao cruzada', 'd) Tipo de funcao de ativacao'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Cite tres aplicacoes praticas de IA generativa no ambiente corporativo e explique como cada uma pode aumentar a produtividade.'},
        ],
        'dicas_estudo': [
            'Comece com Python e bibliotecas como NumPy, Pandas e Scikit-learn antes de avancar para deep learning.',
            'Pratique com datasets publicos do Kaggle para ganhar experiencia pratica.',
            'Acompanhe blogs como Towards Data Science e papers no arXiv para se manter atualizado.',
            'Experimente ferramentas de IA generativa (ChatGPT, Midjourney) para entender suas capacidades e limitacoes.',
            'Foque em entender os conceitos antes de memorizar formulas matematicas.',
        ],
        'glossario': [
            'Machine Learning: subcampo da IA que permite aprendizado a partir de dados.',
            'Deep Learning: ML com redes neurais de muitas camadas.',
            'NLP: Processamento de Linguagem Natural - IA aplicada a texto e fala.',
            'Transformer: arquitetura de rede neural base dos modelos GPT.',
            'Overfitting: modelo que memoriza os dados de treino mas nao generaliza.',
            'Dataset: conjunto de dados usado para treinar e avaliar modelos.',
            'Backpropagation: algoritmo de ajuste de pesos em redes neurais.',
            'Prompt: instrucao dada a um modelo de IA generativa.',
        ],
    },
    'Cybersecurity Essentials': {
        'ementa': 'Fundamentos de seguranca da informacao. Ameacas e vulnerabilidades. Criptografia basica. Seguranca de redes. Pentest e ethical hacking. Conformidade e frameworks de seguranca. Resposta a incidentes.',
        'topicos': [
            'Modulo 1: Fundamentos de seguranca - CIA triad, ameacas e riscos',
            'Modulo 2: Criptografia - simetrica, assimetrica, hashing',
            'Modulo 3: Seguranca de redes - firewalls, IDS/IPS, VPN',
            'Modulo 4: Vulnerabilidades web - OWASP Top 10',
            'Modulo 5: Pentest e ethical hacking - metodologias e ferramentas',
            'Modulo 6: Seguranca em nuvem e DevSecOps',
            'Modulo 7: Conformidade - ISO 27001, NIST, LGPD',
            'Modulo 8: Resposta a incidentes e forense digital',
        ],
        'bibliografia': [
            'STALLINGS, W. Criptografia e Seguranca de Redes. Pearson, 2020.',
            'WEIDMAN, G. Testes de Invasao. Novatec, 2014.',
            'KIM, D.; SOLOMON, M. Fundamentos de Seguranca de Sistemas de Informacao. LTC, 2014.',
        ],
        'introducao': (
            'A seguranca cibernetica e uma das areas mais criticas e demandadas da tecnologia. '
            'Com o aumento de ataques digitais, profissionais qualificados em cybersecurity sao '
            'essenciais para proteger organizacoes. Este curso aborda desde fundamentos de seguranca '
            'ate tecnicas de pentest e resposta a incidentes, preparando voce para atuar na defesa '
            'de sistemas e dados.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Triade CIA e Gestao de Riscos',
                'explicacao': (
                    'A triade CIA (Confidencialidade, Integridade, Disponibilidade) e o pilar da seguranca '
                    'da informacao. Confidencialidade garante que dados sejam acessados apenas por autorizados. '
                    'Integridade assegura que dados nao sejam alterados indevidamente. Disponibilidade garante '
                    'que sistemas estejam acessiveis quando necessario. A gestao de riscos identifica, avalia '
                    'e mitiga ameacas a esses pilares.'
                ),
                'exemplo': (
                    'Exemplos praticos da triade CIA:\n'
                    '- Confidencialidade: criptografia de dados, controle de acesso\n'
                    '- Integridade: checksums, assinaturas digitais, controle de versao\n'
                    '- Disponibilidade: redundancia, backups, balanceamento de carga\n\n'
                    'Risco = Probabilidade x Impacto'
                ),
            },
            {
                'titulo': 'Criptografia e Protecao de Dados',
                'explicacao': (
                    'Criptografia transforma dados legiveis em formato ilegivel para protege-los. '
                    'Criptografia simetrica usa a mesma chave para cifrar e decifrar (AES, DES). '
                    'Criptografia assimetrica usa par de chaves publica/privada (RSA, ECC). '
                    'Hashing gera um resumo unico de tamanho fixo (SHA-256, bcrypt) e e irreversivel.'
                ),
                'exemplo': (
                    'Tipos de criptografia:\n'
                    '- Simetrica (AES-256): rapida, usada para dados em repouso\n'
                    '- Assimetrica (RSA): usada para troca de chaves e assinaturas\n'
                    '- Hashing (SHA-256): verificacao de integridade, armazenamento de senhas\n\n'
                    'HTTPS = HTTP + TLS (usa ambas: assimetrica para handshake, simetrica para dados)'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'O que significa a sigla CIA na seguranca da informacao?', 'alternativas': ['a) Central Intelligence Agency', 'b) Confidencialidade, Integridade, Disponibilidade', 'c) Controle, Inspecao, Auditoria', 'd) Criptografia, Identidade, Autenticacao'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique a diferenca entre criptografia simetrica e assimetrica. Em que situacoes cada uma e mais adequada?'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual das seguintes e uma vulnerabilidade do OWASP Top 10?', 'alternativas': ['a) Buffer overflow', 'b) SQL Injection', 'c) Stack smashing', 'd) Race condition'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva as etapas de um teste de penetracao (pentest) e a importancia de cada fase.'},
        ],
        'dicas_estudo': [
            'Monte um laboratorio virtual com VirtualBox ou VMware para praticar seguranca.',
            'Pratique em plataformas como TryHackMe e HackTheBox.',
            'Estude para certificacoes como CompTIA Security+ e CEH.',
            'Acompanhe noticias de seguranca em sites como Krebs on Security e The Hacker News.',
        ],
        'glossario': [
            'CIA Triad: Confidencialidade, Integridade e Disponibilidade.',
            'Pentest: teste de penetracao para identificar vulnerabilidades.',
            'Firewall: dispositivo que filtra trafego de rede.',
            'IDS/IPS: sistemas de deteccao/prevencao de intrusao.',
            'OWASP: Open Web Application Security Project.',
            'Zero-day: vulnerabilidade desconhecida pelo fabricante.',
            'Phishing: ataque de engenharia social via email/mensagem.',
            'Ransomware: malware que criptografa dados e exige resgate.',
        ],
    },
    'Data Science com Python': {
        'ementa': 'Fundamentos de Data Science. Python para analise de dados. Pandas e NumPy. Visualizacao de dados. Estatistica aplicada. Machine Learning basico. Projetos com dados reais.',
        'topicos': [
            'Modulo 1: Introducao a Data Science e o ecossistema Python',
            'Modulo 2: NumPy - arrays, operacoes vetorizadas, algebra linear',
            'Modulo 3: Pandas - DataFrames, limpeza e transformacao de dados',
            'Modulo 4: Visualizacao com Matplotlib e Seaborn',
            'Modulo 5: Estatistica descritiva e inferencial',
            'Modulo 6: Machine Learning com Scikit-learn',
            'Modulo 7: Analise exploratoria de dados (EDA) com datasets reais',
            'Modulo 8: Projeto final - pipeline completo de Data Science',
        ],
        'bibliografia': [
            'MCKINNEY, W. Python para Analise de Dados. Novatec, 2019.',
            'GRUS, J. Data Science do Zero. Alta Books, 2021.',
            'VANDERPLAS, J. Python Data Science Handbook. O\'Reilly, 2016.',
        ],
        'introducao': (
            'Data Science e a ciencia de extrair conhecimento e insights a partir de dados. '
            'Com Python como ferramenta principal, voce aprendera a coletar, limpar, analisar '
            'e visualizar dados, alem de construir modelos preditivos com Machine Learning. '
            'Este curso e ideal para quem deseja tomar decisoes baseadas em dados e ingressar '
            'em uma das carreiras mais promissoras do mercado.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Pandas e Manipulacao de Dados',
                'explicacao': (
                    'Pandas e a biblioteca Python mais importante para analise de dados. O DataFrame '
                    'e sua estrutura principal: uma tabela com linhas e colunas rotuladas. Com Pandas, '
                    'voce pode ler dados de CSV, Excel, SQL e JSON, filtrar, agrupar, transformar '
                    'e exportar dados de forma eficiente.'
                ),
                'exemplo': (
                    'import pandas as pd\n'
                    'df = pd.read_csv("vendas.csv")\n'
                    'df.head()                    # primeiras 5 linhas\n'
                    'df.describe()                # estatisticas descritivas\n'
                    'df.groupby("regiao")["valor"].sum()  # total por regiao\n'
                    'df[df["valor"] > 1000]       # filtrar vendas > 1000'
                ),
            },
            {
                'titulo': 'Visualizacao de Dados',
                'explicacao': (
                    'A visualizacao transforma dados em graficos que facilitam a compreensao de padroes '
                    'e tendencias. Matplotlib e a base para graficos em Python, enquanto Seaborn oferece '
                    'graficos estatisticos mais elegantes. Escolher o tipo certo de grafico e essencial: '
                    'barras para comparacoes, linhas para tendencias, scatter para correlacoes.'
                ),
                'exemplo': (
                    'import matplotlib.pyplot as plt\n'
                    'import seaborn as sns\n\n'
                    '# Grafico de barras\n'
                    'df.groupby("regiao")["valor"].sum().plot(kind="bar")\n'
                    'plt.title("Vendas por Regiao")\n'
                    'plt.show()\n\n'
                    '# Heatmap de correlacao\n'
                    'sns.heatmap(df.corr(), annot=True, cmap="coolwarm")'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual biblioteca Python e mais usada para manipulacao de dados tabulares?', 'alternativas': ['a) NumPy', 'b) Matplotlib', 'c) Pandas', 'd) Scikit-learn'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva as etapas de um pipeline de Data Science, desde a coleta ate a apresentacao dos resultados.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual tipo de grafico e mais adequado para mostrar a correlacao entre duas variaveis numericas?', 'alternativas': ['a) Grafico de barras', 'b) Grafico de pizza', 'c) Scatter plot', 'd) Histograma'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique o que e analise exploratoria de dados (EDA) e por que ela e importante antes de construir modelos de ML.'},
        ],
        'dicas_estudo': [
            'Pratique com datasets do Kaggle - comece com o Titanic e o Iris.',
            'Domine Pandas antes de avancar para Machine Learning.',
            'Crie notebooks Jupyter para documentar suas analises.',
            'Aprenda SQL em paralelo - e essencial para acessar dados em bancos.',
        ],
        'glossario': [
            'DataFrame: estrutura tabular do Pandas (linhas e colunas).',
            'EDA: Analise Exploratoria de Dados.',
            'Feature Engineering: criacao de novas variaveis a partir dos dados existentes.',
            'Outlier: valor atipico que se distancia significativamente dos demais.',
            'Correlacao: medida da relacao linear entre duas variaveis.',
            'Pipeline: sequencia de etapas de processamento de dados.',
            'Overfitting: modelo que se ajusta demais aos dados de treino.',
        ],
    },
    'Cloud Computing com AWS': {
        'ementa': 'Fundamentos de computacao em nuvem. Servicos AWS essenciais (EC2, S3, RDS, Lambda). Arquitetura em nuvem. Seguranca e IAM. Serverless. Preparatorio AWS Solutions Architect.',
        'topicos': [
            'Modulo 1: Fundamentos de cloud - IaaS, PaaS, SaaS, modelos de implantacao',
            'Modulo 2: AWS Core - EC2, VPC, Security Groups',
            'Modulo 3: Armazenamento - S3, EBS, EFS, Glacier',
            'Modulo 4: Banco de dados - RDS, DynamoDB, ElastiCache',
            'Modulo 5: Serverless - Lambda, API Gateway, Step Functions',
            'Modulo 6: IAM, seguranca e conformidade na AWS',
            'Modulo 7: Arquitetura Well-Architected e alta disponibilidade',
            'Modulo 8: Projeto pratico - deploy de aplicacao completa na AWS',
        ],
        'bibliografia': [
            'AMAZON WEB SERVICES. AWS Well-Architected Framework. AWS, 2023.',
            'WITTIG, M.; WITTIG, A. Amazon Web Services in Action. Manning, 2018.',
            'BARON, J. et al. AWS Certified Solutions Architect Study Guide. Sybex, 2022.',
        ],
        'introducao': (
            'Cloud Computing revolucionou a forma como empresas consomem recursos de TI. '
            'A AWS (Amazon Web Services) e a plataforma de nuvem lider de mercado, com mais '
            'de 200 servicos. Neste curso, voce aprendera a projetar, implantar e gerenciar '
            'aplicacoes na AWS, desde servicos basicos como EC2 e S3 ate arquiteturas serverless '
            'com Lambda. O curso tambem prepara para a certificacao AWS Solutions Architect.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Modelos de Servico em Nuvem',
                'explicacao': (
                    'Cloud computing oferece tres modelos de servico: IaaS (Infrastructure as a Service) '
                    'fornece recursos de infraestrutura como servidores virtuais (EC2). PaaS (Platform as '
                    'a Service) oferece plataformas para desenvolvimento (Elastic Beanstalk). SaaS (Software '
                    'as a Service) entrega aplicacoes prontas (Gmail, Office 365). O modelo de responsabilidade '
                    'compartilhada define o que a AWS gerencia e o que o cliente gerencia.'
                ),
                'exemplo': (
                    'Comparacao de modelos:\n'
                    '- IaaS (EC2): voce gerencia SO, aplicacao, dados\n'
                    '- PaaS (Beanstalk): voce gerencia apenas a aplicacao\n'
                    '- SaaS (Gmail): voce so usa o servico\n'
                    '- Serverless (Lambda): voce gerencia apenas o codigo'
                ),
            },
            {
                'titulo': 'Serverless com AWS Lambda',
                'explicacao': (
                    'Serverless permite executar codigo sem gerenciar servidores. O AWS Lambda executa '
                    'funcoes em resposta a eventos (HTTP, S3, DynamoDB, etc.) e cobra apenas pelo tempo '
                    'de execucao. Combinado com API Gateway e DynamoDB, permite construir APIs completas '
                    'sem provisionar nenhum servidor.'
                ),
                'exemplo': (
                    'Exemplo de Lambda em Python:\n'
                    'def lambda_handler(event, context):\n'
                    '    nome = event.get("nome", "Mundo")\n'
                    '    return {\n'
                    '        "statusCode": 200,\n'
                    '        "body": f"Ola, {nome}!"\n'
                    '    }\n\n'
                    'Trigger: API Gateway, S3, DynamoDB Streams, CloudWatch Events'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual servico AWS e usado para armazenamento de objetos?', 'alternativas': ['a) EC2', 'b) RDS', 'c) S3', 'd) Lambda'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique o modelo de responsabilidade compartilhada da AWS e de exemplos do que e responsabilidade do cliente vs. da AWS.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e AWS Lambda?', 'alternativas': ['a) Servico de banco de dados', 'b) Servico serverless de execucao de codigo', 'c) Servico de armazenamento', 'd) Servico de rede'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva uma arquitetura serverless na AWS para uma API REST, incluindo os servicos utilizados.'},
        ],
        'dicas_estudo': [
            'Crie uma conta AWS Free Tier e pratique com servicos reais.',
            'Use o AWS Skill Builder para cursos gratuitos oficiais.',
            'Estude o Well-Architected Framework - e a base da certificacao.',
            'Pratique com laboratorios hands-on antes de fazer a prova de certificacao.',
        ],
        'glossario': [
            'IaaS: Infrastructure as a Service - infraestrutura sob demanda.',
            'Serverless: modelo onde o provedor gerencia toda a infraestrutura.',
            'EC2: Elastic Compute Cloud - servidores virtuais na AWS.',
            'S3: Simple Storage Service - armazenamento de objetos.',
            'Lambda: servico serverless de execucao de funcoes.',
            'IAM: Identity and Access Management - controle de acesso.',
            'VPC: Virtual Private Cloud - rede virtual isolada.',
            'Region/AZ: regiao geografica e zona de disponibilidade.',
        ],
    },
    'UX/UI Design': {
        'ementa': 'Fundamentos de UX e UI. Pesquisa com usuarios. Arquitetura de informacao. Wireframes e prototipos. Design visual e sistemas de design. Testes de usabilidade. Ferramentas (Figma).',
        'topicos': [
            'Modulo 1: Fundamentos de UX - experiencia do usuario e design centrado no usuario',
            'Modulo 2: Pesquisa com usuarios - entrevistas, personas, jornada do usuario',
            'Modulo 3: Arquitetura de informacao e fluxos de navegacao',
            'Modulo 4: Wireframes e prototipos de baixa fidelidade',
            'Modulo 5: Design visual - tipografia, cores, grid, hierarquia',
            'Modulo 6: Prototipos de alta fidelidade com Figma',
            'Modulo 7: Sistemas de design e design tokens',
            'Modulo 8: Testes de usabilidade e iteracao',
        ],
        'bibliografia': [
            'NORMAN, D. O Design do Dia a Dia. Rocco, 2006.',
            'KRUG, S. Nao Me Faca Pensar. Alta Books, 2014.',
            'GOTHELF, J. Lean UX. O\'Reilly, 2021.',
        ],
        'introducao': (
            'UX/UI Design e a disciplina que garante que produtos digitais sejam uteis, usaveis '
            'e agradaveis. UX (User Experience) foca na experiencia completa do usuario, enquanto '
            'UI (User Interface) trata da interface visual. Neste curso, voce aprendera a pesquisar '
            'necessidades de usuarios, criar wireframes e prototipos, e validar solucoes com testes '
            'de usabilidade, usando Figma como ferramenta principal.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Design Centrado no Usuario (DCU)',
                'explicacao': (
                    'O Design Centrado no Usuario coloca as necessidades, desejos e limitacoes dos '
                    'usuarios no centro do processo de design. O ciclo DCU envolve: pesquisa (entender '
                    'o usuario), ideacao (gerar solucoes), prototipacao (materializar ideias) e teste '
                    '(validar com usuarios reais). Personas e jornadas do usuario sao ferramentas '
                    'essenciais para manter o foco no usuario.'
                ),
                'exemplo': (
                    'Exemplo de Persona:\n'
                    'Nome: Ana, 28 anos, gerente de marketing\n'
                    'Objetivo: agendar reunioes rapidamente pelo celular\n'
                    'Frustracao: apps com muitos passos para agendar\n'
                    'Necessidade: interface simples com 3 cliques para agendar\n\n'
                    'A persona guia todas as decisoes de design do produto.'
                ),
            },
            {
                'titulo': 'Prototipacao e Testes de Usabilidade',
                'explicacao': (
                    'Prototipos sao representacoes do produto em diferentes niveis de fidelidade. '
                    'Baixa fidelidade: esbocos em papel ou wireframes simples. Alta fidelidade: '
                    'prototipos interativos no Figma que simulam o produto final. Testes de usabilidade '
                    'observam usuarios reais interagindo com o prototipo para identificar problemas '
                    'antes do desenvolvimento.'
                ),
                'exemplo': (
                    'Etapas de um teste de usabilidade:\n'
                    '1. Definir tarefas para o usuario realizar\n'
                    '2. Recrutar 5 participantes (suficiente para 85% dos problemas)\n'
                    '3. Observar sem interferir\n'
                    '4. Registrar dificuldades e comentarios\n'
                    '5. Analisar e priorizar melhorias'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual a diferenca principal entre UX e UI?', 'alternativas': ['a) UX e visual, UI e funcional', 'b) UX foca na experiencia completa, UI na interface visual', 'c) UX e para web, UI e para mobile', 'd) Nao ha diferenca'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Crie uma persona para um aplicativo de delivery de comida saudavel, incluindo nome, idade, objetivos e frustracoes.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Quantos participantes sao recomendados para um teste de usabilidade segundo Nielsen?', 'alternativas': ['a) 1', 'b) 5', 'c) 20', 'd) 50'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Aprenda Figma - e a ferramenta padrao do mercado para design de interfaces.',
            'Pratique redesenhando apps que voce usa no dia a dia.',
            'Leia "Nao Me Faca Pensar" de Steve Krug - e a biblia da usabilidade.',
            'Faca testes de usabilidade informais com amigos e familiares.',
        ],
        'glossario': [
            'UX: User Experience - experiencia do usuario com o produto.',
            'UI: User Interface - interface visual do produto.',
            'Persona: representacao ficticia do usuario ideal.',
            'Wireframe: esqueleto visual de uma interface (baixa fidelidade).',
            'Prototipo: representacao interativa do produto.',
            'Usabilidade: facilidade de uso de um produto.',
            'Design System: conjunto de componentes e padroes reutilizaveis.',
        ],
    },
    'Gestao de Projetos e Metodologias Ageis': {
        'ementa': 'Fundamentos de gestao de projetos. PMBOK e ciclo de vida do projeto. Metodologias ageis: Scrum, Kanban, XP. Ferramentas de gestao. Metricas e indicadores. Lideranca de equipes ageis.',
        'topicos': [
            'Modulo 1: Fundamentos de gestao de projetos e PMBOK',
            'Modulo 2: Scrum - papeis, eventos e artefatos',
            'Modulo 3: Kanban - fluxo continuo e WIP limits',
            'Modulo 4: Extreme Programming (XP) e praticas tecnicas',
            'Modulo 5: Estimativas ageis - Planning Poker, story points',
            'Modulo 6: Metricas ageis - velocity, burndown, lead time',
            'Modulo 7: Ferramentas - Jira, Trello, Azure DevOps',
            'Modulo 8: Escalando agil - SAFe, LeSS, Nexus',
        ],
        'bibliografia': [
            'SCHWABER, K.; SUTHERLAND, J. Guia do Scrum. Scrum.org, 2020.',
            'ANDERSON, D. Kanban: Mudanca Evolucionaria de Sucesso. Blue Hole Press, 2010.',
            'COHN, M. Desenvolvimento de Software com Scrum. Bookman, 2011.',
        ],
        'introducao': (
            'A gestao de projetos e essencial para entregar resultados com qualidade, no prazo '
            'e dentro do orcamento. As metodologias ageis revolucionaram a forma como equipes '
            'trabalham, priorizando entregas incrementais, colaboracao e adaptacao a mudancas. '
            'Neste curso, voce dominara Scrum, Kanban e outras praticas ageis, preparando-se '
            'para liderar equipes e projetos com eficiencia.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Scrum Framework',
                'explicacao': (
                    'Scrum e o framework agil mais utilizado no mundo. Ele organiza o trabalho em '
                    'Sprints (ciclos de 1-4 semanas) com papeis definidos: Product Owner (prioriza o backlog), '
                    'Scrum Master (facilita o processo) e Developers (executam o trabalho). Os eventos '
                    'incluem Sprint Planning, Daily Scrum, Sprint Review e Sprint Retrospective.'
                ),
                'exemplo': (
                    'Fluxo de uma Sprint:\n'
                    '1. Sprint Planning: equipe seleciona itens do Product Backlog\n'
                    '2. Daily Scrum (15 min): o que fiz, o que farei, impedimentos\n'
                    '3. Desenvolvimento: equipe trabalha nos itens selecionados\n'
                    '4. Sprint Review: demonstracao do incremento para stakeholders\n'
                    '5. Sprint Retrospective: o que melhorar no proximo ciclo'
                ),
            },
            {
                'titulo': 'Kanban e Fluxo Continuo',
                'explicacao': (
                    'Kanban e um metodo visual para gerenciar trabalho em fluxo continuo. O quadro '
                    'Kanban mostra o status de cada tarefa (To Do, In Progress, Done). O conceito-chave '
                    'e o WIP Limit (Work In Progress): limitar o numero de tarefas simultaneas para '
                    'reduzir multitasking e aumentar o foco e a vazao.'
                ),
                'exemplo': (
                    'Quadro Kanban basico:\n'
                    '| To Do (5) | In Progress (3) | Review (2) | Done |\n'
                    '|-----------|-----------------|------------|------|\n'
                    '| Task A    | Task D          | Task F     | Task H|\n'
                    '| Task B    | Task E          | Task G     | Task I|\n'
                    '| Task C    |                 |            |      |\n\n'
                    'WIP Limit: maximo de tarefas em cada coluna'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual e o papel do Product Owner no Scrum?', 'alternativas': ['a) Gerenciar a equipe', 'b) Priorizar o Product Backlog', 'c) Escrever codigo', 'd) Facilitar os eventos'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Compare Scrum e Kanban: em que situacoes cada abordagem e mais adequada?'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e WIP Limit no Kanban?', 'alternativas': ['a) Limite de horas de trabalho', 'b) Limite de tarefas simultaneas em andamento', 'c) Limite de membros na equipe', 'd) Limite de sprints'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Leia o Guia do Scrum oficial (scrum.org) - sao apenas 13 paginas.',
            'Pratique com um quadro Kanban pessoal (Trello e gratuito).',
            'Estude para a certificacao PSM I (Professional Scrum Master).',
            'Participe de comunidades ageis locais e meetups.',
        ],
        'glossario': [
            'Sprint: ciclo de trabalho com duracao fixa no Scrum.',
            'Product Backlog: lista priorizada de funcionalidades do produto.',
            'Scrum Master: facilitador do processo Scrum.',
            'Product Owner: responsavel por maximizar o valor do produto.',
            'WIP Limit: limite de trabalho em progresso no Kanban.',
            'Velocity: quantidade de trabalho entregue por sprint.',
            'Burndown Chart: grafico que mostra trabalho restante na sprint.',
            'Story Points: unidade de estimativa de esforco relativo.',
        ],
    },
    'Marketing Digital e Analytics': {
        'ementa': 'Fundamentos de marketing digital. SEO e SEM. Redes sociais e conteudo. Email marketing. Google Analytics e metricas. Funil de vendas digital. Growth hacking.',
        'topicos': [
            'Modulo 1: Fundamentos de marketing digital e transformacao digital',
            'Modulo 2: SEO - otimizacao para mecanismos de busca',
            'Modulo 3: SEM - Google Ads e midia paga',
            'Modulo 4: Marketing de conteudo e redes sociais',
            'Modulo 5: Email marketing e automacao',
            'Modulo 6: Google Analytics e metricas de performance',
            'Modulo 7: Funil de vendas e conversao',
            'Modulo 8: Growth hacking e experimentacao',
        ],
        'bibliografia': [
            'KOTLER, P. Marketing 5.0. Sextante, 2021.',
            'RESULTADOS DIGITAIS. Marketing Digital na Pratica. RD Station, 2020.',
            'ELLIS, S. Se Manda: Growth Hacking. HSM, 2017.',
        ],
        'introducao': (
            'O marketing digital e essencial para qualquer negocio na era digital. Com ferramentas '
            'de analytics, e possivel medir o retorno de cada acao e otimizar investimentos. '
            'Neste curso, voce aprendera desde SEO e Google Ads ate estrategias de conteudo '
            'e growth hacking, com foco em dados e resultados mensuraveis.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'SEO e Marketing de Busca',
                'explicacao': (
                    'SEO (Search Engine Optimization) e o conjunto de tecnicas para melhorar o '
                    'posicionamento organico de um site nos mecanismos de busca. Envolve otimizacao '
                    'on-page (conteudo, meta tags, URLs), off-page (backlinks, autoridade) e tecnica '
                    '(velocidade, mobile-friendly, estrutura). SEM (Search Engine Marketing) inclui '
                    'tambem anuncios pagos como Google Ads.'
                ),
                'exemplo': (
                    'Checklist basico de SEO on-page:\n'
                    '- Titulo da pagina com palavra-chave principal (ate 60 caracteres)\n'
                    '- Meta description atrativa (ate 160 caracteres)\n'
                    '- URL amigavel e curta\n'
                    '- Headings hierarquicos (H1, H2, H3)\n'
                    '- Imagens otimizadas com alt text\n'
                    '- Conteudo original e relevante (minimo 300 palavras)'
                ),
            },
            {
                'titulo': 'Analytics e Metricas de Performance',
                'explicacao': (
                    'Google Analytics e a ferramenta padrao para medir o desempenho de sites e campanhas. '
                    'Metricas essenciais incluem: sessoes, usuarios, taxa de rejeicao, tempo na pagina, '
                    'conversoes e ROI. O funil de conversao mostra a jornada do usuario desde a descoberta '
                    'ate a compra, permitindo identificar onde os usuarios abandonam o processo.'
                ),
                'exemplo': (
                    'Metricas-chave de marketing digital:\n'
                    '- CAC (Custo de Aquisicao de Cliente): quanto custa conquistar um cliente\n'
                    '- LTV (Lifetime Value): quanto um cliente gera de receita ao longo do tempo\n'
                    '- ROI: (Receita - Custo) / Custo x 100\n'
                    '- Taxa de conversao: visitantes que realizaram a acao desejada\n'
                    '- Regra de ouro: LTV > 3x CAC'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'O que significa SEO?', 'alternativas': ['a) Social Engine Optimization', 'b) Search Engine Optimization', 'c) Site Enhancement Operation', 'd) Search Email Outreach'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique a diferenca entre trafego organico e trafego pago. Quais as vantagens e desvantagens de cada um?'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual metrica indica o custo para adquirir um novo cliente?', 'alternativas': ['a) LTV', 'b) ROI', 'c) CAC', 'd) CTR'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Crie um blog ou site pessoal para praticar SEO na pratica.',
            'Obtenha a certificacao Google Analytics (gratuita).',
            'Acompanhe blogs como Neil Patel, Moz e RD Station.',
            'Pratique com Google Ads usando cupons de credito gratuitos.',
        ],
        'glossario': [
            'SEO: Search Engine Optimization - otimizacao para buscadores.',
            'SEM: Search Engine Marketing - marketing em mecanismos de busca.',
            'CAC: Custo de Aquisicao de Cliente.',
            'LTV: Lifetime Value - valor do cliente ao longo do tempo.',
            'CTR: Click-Through Rate - taxa de cliques.',
            'ROI: Return on Investment - retorno sobre investimento.',
            'Funil de vendas: jornada do cliente da descoberta a compra.',
            'Growth Hacking: estrategias de crescimento rapido baseadas em experimentacao.',
        ],
    },
    'DevOps e CI/CD': {
        'ementa': 'Cultura DevOps. Integracao e entrega continua. Containers e Docker. Orquestracao com Kubernetes. Infraestrutura como codigo. Monitoramento e observabilidade.',
        'topicos': [
            'Modulo 1: Cultura DevOps - principios, praticas e beneficios',
            'Modulo 2: Controle de versao avancado com Git e GitHub',
            'Modulo 3: CI/CD - Jenkins, GitHub Actions, GitLab CI',
            'Modulo 4: Containers com Docker',
            'Modulo 5: Orquestracao com Kubernetes',
            'Modulo 6: Infraestrutura como codigo - Terraform e CloudFormation',
            'Modulo 7: Monitoramento - Prometheus, Grafana, ELK Stack',
            'Modulo 8: Projeto pratico - pipeline CI/CD completo',
        ],
        'bibliografia': [
            'KIM, G. et al. O Projeto Fenix. Alta Books, 2016.',
            'HUMBLE, J.; FARLEY, D. Entrega Continua. Bookman, 2014.',
            'BURNS, B. Kubernetes: Tudo Sobre Orquestracao de Conteineres. Novatec, 2019.',
        ],
        'introducao': (
            'DevOps e a uniao de desenvolvimento (Dev) e operacoes (Ops) para entregar software '
            'com mais velocidade, qualidade e confiabilidade. CI/CD (Integracao Continua e Entrega '
            'Continua) automatiza o processo de build, teste e deploy. Neste curso, voce aprendera '
            'Docker, Kubernetes, Terraform e ferramentas de CI/CD, habilidades essenciais para '
            'qualquer profissional de tecnologia moderno.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Containers e Docker',
                'explicacao': (
                    'Containers sao ambientes isolados e leves que empacotam uma aplicacao com todas '
                    'as suas dependencias. Docker e a plataforma mais popular para criar e gerenciar '
                    'containers. Um Dockerfile define como construir a imagem, e o Docker Compose '
                    'orquestra multiplos containers. Containers garantem que a aplicacao funcione '
                    'da mesma forma em qualquer ambiente.'
                ),
                'exemplo': (
                    'Dockerfile basico para Python:\n'
                    'FROM python:3.11-slim\n'
                    'WORKDIR /app\n'
                    'COPY requirements.txt .\n'
                    'RUN pip install -r requirements.txt\n'
                    'COPY . .\n'
                    'CMD ["python", "app.py"]\n\n'
                    'Comandos: docker build -t minha-app .\n'
                    '          docker run -p 8080:8080 minha-app'
                ),
            },
            {
                'titulo': 'CI/CD Pipeline',
                'explicacao': (
                    'CI (Integracao Continua) automatiza a compilacao e testes a cada commit. '
                    'CD (Entrega Continua) automatiza o deploy para ambientes de staging/producao. '
                    'Um pipeline tipico inclui: checkout do codigo, build, testes unitarios, '
                    'testes de integracao, analise de qualidade, deploy em staging e deploy em producao.'
                ),
                'exemplo': (
                    'Pipeline GitHub Actions basico:\n'
                    'name: CI/CD\n'
                    'on: push\n'
                    'jobs:\n'
                    '  build:\n'
                    '    runs-on: ubuntu-latest\n'
                    '    steps:\n'
                    '      - uses: actions/checkout@v3\n'
                    '      - run: pip install -r requirements.txt\n'
                    '      - run: pytest tests/\n'
                    '      - run: docker build -t app .'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e um container Docker?', 'alternativas': ['a) Uma maquina virtual completa', 'b) Um ambiente isolado e leve para executar aplicacoes', 'c) Um tipo de banco de dados', 'd) Um servico de nuvem'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva as etapas de um pipeline CI/CD completo, desde o commit ate o deploy em producao.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual ferramenta e usada para orquestrar containers em escala?', 'alternativas': ['a) Docker Compose', 'b) Terraform', 'c) Kubernetes', 'd) Jenkins'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Instale Docker Desktop e pratique criando containers localmente.',
            'Crie um pipeline CI/CD no GitHub Actions para um projeto pessoal.',
            'Estude Kubernetes com Minikube para praticar localmente.',
            'Leia "O Projeto Fenix" para entender a cultura DevOps.',
        ],
        'glossario': [
            'DevOps: uniao de desenvolvimento e operacoes.',
            'CI: Integracao Continua - build e testes automaticos a cada commit.',
            'CD: Entrega Continua - deploy automatizado.',
            'Container: ambiente isolado e leve para executar aplicacoes.',
            'Docker: plataforma para criar e gerenciar containers.',
            'Kubernetes: orquestrador de containers em escala.',
            'Terraform: ferramenta de infraestrutura como codigo.',
            'Pipeline: sequencia automatizada de etapas de build, teste e deploy.',
        ],
    },
    'Blockchain e Web3': {
        'ementa': 'Fundamentos de blockchain. Criptografia e consenso. Smart contracts com Solidity. Ethereum e DeFi. NFTs e tokens. Web3 e aplicacoes descentralizadas (dApps).',
        'topicos': [
            'Modulo 1: Fundamentos de blockchain - blocos, cadeia, mineracao',
            'Modulo 2: Criptografia aplicada - hash, assinaturas digitais, Merkle trees',
            'Modulo 3: Mecanismos de consenso - PoW, PoS, DPoS',
            'Modulo 4: Ethereum e smart contracts',
            'Modulo 5: Solidity - programacao de smart contracts',
            'Modulo 6: DeFi - financas descentralizadas',
            'Modulo 7: NFTs, tokens ERC-20 e ERC-721',
            'Modulo 8: Web3 - dApps, wallets e o futuro da internet',
        ],
        'bibliografia': [
            'ANTONOPOULOS, A. Mastering Bitcoin. O\'Reilly, 2017.',
            'ANTONOPOULOS, A.; WOOD, G. Mastering Ethereum. O\'Reilly, 2018.',
            'TAPSCOTT, D. Blockchain Revolution. Senai-SP, 2016.',
        ],
        'introducao': (
            'Blockchain e a tecnologia por tras das criptomoedas, mas suas aplicacoes vao muito '
            'alem do Bitcoin. Smart contracts, DeFi, NFTs e aplicacoes descentralizadas estao '
            'criando uma nova internet (Web3). Neste curso, voce entendera como blockchain funciona, '
            'aprendera a programar smart contracts em Solidity e explorara o ecossistema Web3.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Como Funciona o Blockchain',
                'explicacao': (
                    'Blockchain e um livro-razao distribuido e imutavel. Cada bloco contem um conjunto '
                    'de transacoes, o hash do bloco anterior e um nonce. A mineracao (Proof of Work) '
                    'ou validacao (Proof of Stake) garante que novos blocos sejam adicionados de forma '
                    'segura. A descentralizacao elimina a necessidade de intermediarios confiaveis.'
                ),
                'exemplo': (
                    'Estrutura de um bloco:\n'
                    '- Hash do bloco anterior: 0x7f3a...\n'
                    '- Timestamp: 2024-01-15 10:30:00\n'
                    '- Transacoes: [Alice->Bob: 1 ETH, Carol->Dave: 0.5 ETH]\n'
                    '- Nonce: 48291\n'
                    '- Hash do bloco: 0x0000a3b...\n\n'
                    'Se qualquer dado for alterado, o hash muda e a cadeia quebra.'
                ),
            },
            {
                'titulo': 'Smart Contracts e Solidity',
                'explicacao': (
                    'Smart contracts sao programas que executam automaticamente quando condicoes '
                    'pre-definidas sao atendidas, sem intermediarios. Solidity e a linguagem principal '
                    'para programar smart contracts na Ethereum. Uma vez implantado, o contrato e '
                    'imutavel e transparente, garantindo confianca entre as partes.'
                ),
                'exemplo': (
                    'Smart contract basico em Solidity:\n'
                    'pragma solidity ^0.8.0;\n'
                    'contract Saudacao {\n'
                    '    string public mensagem;\n'
                    '    constructor(string memory _msg) {\n'
                    '        mensagem = _msg;\n'
                    '    }\n'
                    '    function atualizar(string memory _msg) public {\n'
                    '        mensagem = _msg;\n'
                    '    }\n'
                    '}'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'O que garante a imutabilidade do blockchain?', 'alternativas': ['a) Senhas fortes', 'b) Encadeamento de hashes entre blocos', 'c) Firewalls', 'd) Backups regulares'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique a diferenca entre Proof of Work e Proof of Stake como mecanismos de consenso.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e um smart contract?', 'alternativas': ['a) Um contrato juridico digital', 'b) Um programa auto-executavel no blockchain', 'c) Um tipo de criptomoeda', 'd) Um protocolo de rede'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Use Remix IDE (remix.ethereum.org) para praticar Solidity gratuitamente.',
            'Crie uma carteira MetaMask e interaja com testnets.',
            'Estude os padroes ERC-20 (tokens) e ERC-721 (NFTs).',
            'Acompanhe projetos DeFi para entender aplicacoes reais.',
        ],
        'glossario': [
            'Blockchain: livro-razao distribuido e imutavel.',
            'Smart Contract: programa auto-executavel no blockchain.',
            'Solidity: linguagem de programacao para smart contracts Ethereum.',
            'DeFi: Financas Descentralizadas.',
            'NFT: Token Nao Fungivel - ativo digital unico.',
            'Wallet: carteira digital para armazenar criptomoedas.',
            'Gas: taxa paga para executar transacoes na Ethereum.',
            'dApp: aplicacao descentralizada que roda no blockchain.',
        ],
    },
    'Lideranca e Gestao de Pessoas': {
        'ementa': 'Teorias de lideranca. Estilos de lideranca situacional. Comunicacao e feedback. Gestao de conflitos. Motivacao e engajamento. Coaching e mentoring. Diversidade e inclusao.',
        'topicos': [
            'Modulo 1: Teorias de lideranca - de trait theory a lideranca transformacional',
            'Modulo 2: Lideranca situacional - adaptando o estilo ao contexto',
            'Modulo 3: Comunicacao eficaz e escuta ativa',
            'Modulo 4: Feedback construtivo e conversas dificeis',
            'Modulo 5: Gestao de conflitos e negociacao',
            'Modulo 6: Motivacao, engajamento e retencao de talentos',
            'Modulo 7: Coaching e mentoring para desenvolvimento de equipes',
            'Modulo 8: Diversidade, inclusao e lideranca etica',
        ],
        'bibliografia': [
            'BLANCHARD, K. Lideranca de Alto Nivel. Bookman, 2019.',
            'GOLEMAN, D. Inteligencia Emocional. Objetiva, 2011.',
            'SINEK, S. Comece pelo Porque. Sextante, 2018.',
        ],
        'introducao': (
            'Lideranca nao e apenas um cargo, e uma habilidade que pode ser desenvolvida. '
            'Bons lideres inspiram, motivam e desenvolvem suas equipes para alcancarem resultados '
            'extraordinarios. Neste curso, voce aprendera diferentes estilos de lideranca, '
            'tecnicas de comunicacao e feedback, gestao de conflitos e como criar um ambiente '
            'de trabalho inclusivo e engajador.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Lideranca Situacional',
                'explicacao': (
                    'A lideranca situacional, de Hersey e Blanchard, propoe que nao existe um unico '
                    'estilo de lideranca ideal. O lider deve adaptar seu estilo ao nivel de maturidade '
                    'do liderado: direcionar (baixa maturidade), orientar, apoiar ou delegar (alta '
                    'maturidade). A chave e diagnosticar corretamente o nivel de cada pessoa e tarefa.'
                ),
                'exemplo': (
                    'Estilos de lideranca situacional:\n'
                    '- S1 Direcionar: alta tarefa, baixo relacionamento (novatos)\n'
                    '- S2 Orientar: alta tarefa, alto relacionamento (em desenvolvimento)\n'
                    '- S3 Apoiar: baixa tarefa, alto relacionamento (competentes mas inseguros)\n'
                    '- S4 Delegar: baixa tarefa, baixo relacionamento (autonomos)\n\n'
                    'O mesmo lider pode usar S1 com um estagiario e S4 com um senior.'
                ),
            },
            {
                'titulo': 'Feedback Construtivo',
                'explicacao': (
                    'Feedback e uma ferramenta essencial para o desenvolvimento de pessoas. O modelo '
                    'SBI (Situacao-Comportamento-Impacto) estrutura o feedback de forma objetiva: '
                    'descreva a situacao, o comportamento observado e o impacto causado. Feedback '
                    'deve ser especifico, oportuno, equilibrado e focado em comportamentos, nao em '
                    'personalidade.'
                ),
                'exemplo': (
                    'Modelo SBI de feedback:\n'
                    'Situacao: "Na reuniao de ontem com o cliente..."\n'
                    'Comportamento: "...voce apresentou os dados de forma clara e respondeu\n'
                    '  todas as perguntas com seguranca..."\n'
                    'Impacto: "...o que transmitiu confianca e ajudou a fechar o contrato."\n\n'
                    'Evite: "Voce e muito bom" (vago)\n'
                    'Prefira: feedback especifico com SBI'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Na lideranca situacional, qual estilo e mais adequado para um colaborador novato?', 'alternativas': ['a) Delegar', 'b) Apoiar', 'c) Direcionar', 'd) Orientar'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Usando o modelo SBI, escreva um feedback construtivo para um colega que chegou atrasado em tres reunioes consecutivas.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e inteligencia emocional segundo Goleman?', 'alternativas': ['a) QI elevado', 'b) Capacidade de reconhecer e gerenciar emocoes proprias e dos outros', 'c) Habilidade tecnica superior', 'd) Capacidade de memorizar informacoes'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Pratique dar feedback usando o modelo SBI no dia a dia.',
            'Leia "Comece pelo Porque" de Simon Sinek para entender lideranca inspiradora.',
            'Desenvolva sua inteligencia emocional com autoconhecimento e empatia.',
            'Observe lideres que voce admira e identifique seus estilos.',
        ],
        'glossario': [
            'Lideranca situacional: adaptar o estilo ao nivel de maturidade do liderado.',
            'Feedback SBI: Situacao-Comportamento-Impacto.',
            'Inteligencia emocional: capacidade de reconhecer e gerenciar emocoes.',
            'Coaching: processo de desenvolvimento focado em metas especificas.',
            'Mentoring: orientacao baseada na experiencia do mentor.',
            'Engajamento: nivel de comprometimento e motivacao do colaborador.',
            'Empowerment: delegacao de autoridade e responsabilidade.',
        ],
    },
    'Saude Mental no Trabalho': {
        'ementa': 'Saude mental e trabalho. Estresse e burnout. Ansiedade e depressao no ambiente corporativo. Mindfulness e tecnicas de relaxamento. Qualidade de vida. Politicas organizacionais de saude mental.',
        'topicos': [
            'Modulo 1: Saude mental no contexto do trabalho moderno',
            'Modulo 2: Estresse ocupacional - causas, sintomas e consequencias',
            'Modulo 3: Sindrome de Burnout - identificacao e prevencao',
            'Modulo 4: Ansiedade e depressao no ambiente de trabalho',
            'Modulo 5: Mindfulness e tecnicas de gestao emocional',
            'Modulo 6: Equilibrio trabalho-vida e qualidade de vida',
            'Modulo 7: Politicas organizacionais de saude mental',
            'Modulo 8: Primeiros socorros psicologicos e encaminhamento',
        ],
        'bibliografia': [
            'ZANELLI, J. Estresse nas Organizacoes de Trabalho. Artmed, 2010.',
            'KABAT-ZINN, J. Atencao Plena para Iniciantes. Sextante, 2017.',
            'MASLACH, C.; LEITER, M. Burnout: The Cost of Caring. Malor Books, 2015.',
        ],
        'introducao': (
            'A saude mental no trabalho e um tema cada vez mais relevante. O estresse cronico, '
            'a pressao por resultados e a dificuldade de equilibrar vida pessoal e profissional '
            'afetam milhoes de trabalhadores. Neste curso, voce aprendera a identificar sinais '
            'de burnout e ansiedade, tecnicas de mindfulness e gestao emocional, e como promover '
            'um ambiente de trabalho mais saudavel.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Sindrome de Burnout',
                'explicacao': (
                    'Burnout e uma sindrome resultante do estresse cronico no trabalho que nao foi '
                    'gerenciado adequadamente. Caracteriza-se por tres dimensoes: exaustao emocional '
                    '(esgotamento), despersonalizacao (cinismo e distanciamento) e reducao da realizacao '
                    'profissional. Desde 2022, a OMS reconhece burnout como fenomeno ocupacional na CID-11.'
                ),
                'exemplo': (
                    'Sinais de alerta de burnout:\n'
                    '- Cansaco constante, mesmo apos descanso\n'
                    '- Irritabilidade e impaciencia com colegas\n'
                    '- Dificuldade de concentracao\n'
                    '- Sensacao de incompetencia\n'
                    '- Isolamento social\n'
                    '- Dores de cabeca e problemas de sono frequentes\n\n'
                    'Se identificar 3+ sinais, procure ajuda profissional.'
                ),
            },
            {
                'titulo': 'Mindfulness e Gestao Emocional',
                'explicacao': (
                    'Mindfulness (atencao plena) e a pratica de estar presente no momento atual, '
                    'sem julgamento. Estudos mostram que a pratica regular reduz estresse, ansiedade '
                    'e melhora o foco e a tomada de decisao. Tecnicas simples como respiracao consciente '
                    'e body scan podem ser praticadas em poucos minutos durante o dia de trabalho.'
                ),
                'exemplo': (
                    'Tecnica de respiracao 4-7-8:\n'
                    '1. Inspire pelo nariz contando ate 4\n'
                    '2. Segure a respiracao contando ate 7\n'
                    '3. Expire pela boca contando ate 8\n'
                    '4. Repita 3-4 vezes\n\n'
                    'Pratique antes de reunioes importantes ou em momentos de estresse.'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Quais sao as tres dimensoes da Sindrome de Burnout?', 'alternativas': ['a) Tristeza, raiva, medo', 'b) Exaustao emocional, despersonalizacao, reducao da realizacao', 'c) Ansiedade, depressao, estresse', 'd) Insonia, fadiga, irritabilidade'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva tres acoes que uma empresa pode implementar para promover a saude mental dos colaboradores.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'O que e mindfulness?', 'alternativas': ['a) Tecnica de memorizacao', 'b) Pratica de atencao plena ao momento presente', 'c) Tipo de meditacao religiosa', 'd) Metodo de produtividade'], 'resposta': 'b'},
        ],
        'dicas_estudo': [
            'Pratique mindfulness por 5 minutos diarios usando apps como Headspace ou Calm.',
            'Estabeleca limites claros entre trabalho e vida pessoal.',
            'Faca pausas regulares durante o dia de trabalho (tecnica Pomodoro).',
            'Nao hesite em buscar ajuda profissional se necessario.',
        ],
        'glossario': [
            'Burnout: sindrome de esgotamento profissional cronico.',
            'Mindfulness: pratica de atencao plena ao momento presente.',
            'Estresse ocupacional: resposta do organismo a demandas excessivas do trabalho.',
            'Resiliencia: capacidade de se recuperar de adversidades.',
            'Ergonomia: adaptacao do trabalho as capacidades do trabalhador.',
            'Qualidade de vida: equilibrio entre saude fisica, mental e social.',
        ],
    },
    'Primeiros Socorros e Urgencias': {
        'ementa': 'Principios de primeiros socorros. Avaliacao da vitima. Suporte basico de vida (BLS). Engasgamento e obstrucao de vias aereas. Hemorragias e fraturas. Queimaduras e intoxicacoes. Emergencias clinicas.',
        'topicos': [
            'Modulo 1: Principios gerais de primeiros socorros e seguranca do socorrista',
            'Modulo 2: Avaliacao primaria e secundaria da vitima',
            'Modulo 3: Suporte basico de vida (BLS) e RCP',
            'Modulo 4: Uso do DEA (Desfibrilador Externo Automatico)',
            'Modulo 5: Engasgamento - manobra de Heimlich',
            'Modulo 6: Hemorragias, fraturas e imobilizacoes',
            'Modulo 7: Queimaduras, intoxicacoes e picadas de animais',
            'Modulo 8: Emergencias clinicas - desmaio, convulsao, AVC, infarto',
        ],
        'bibliografia': [
            'AMERICAN HEART ASSOCIATION. BLS Provider Manual. AHA, 2020.',
            'BERGERON, J. Primeiros Socorros. Atheneu, 2017.',
            'MINISTERIO DA SAUDE. Manual de Primeiros Socorros. MS, 2003.',
        ],
        'introducao': (
            'Saber prestar primeiros socorros pode salvar vidas. Em situacoes de emergencia, '
            'os primeiros minutos sao cruciais e a acao correta de um socorrista leigo pode '
            'fazer a diferenca entre a vida e a morte. Neste curso presencial, voce aprendera '
            'tecnicas de suporte basico de vida, RCP, uso do DEA e como agir em diversas '
            'situacoes de urgencia ate a chegada do socorro especializado.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Suporte Basico de Vida (BLS) e RCP',
                'explicacao': (
                    'O Suporte Basico de Vida (BLS) e o conjunto de acoes realizadas para manter '
                    'a vida de uma pessoa em parada cardiorrespiratoria ate a chegada do socorro. '
                    'A RCP (Ressuscitacao Cardiopulmonar) combina compressoes toracicas e ventilacoes. '
                    'A cadeia de sobrevivencia inclui: reconhecer a parada, ligar 192/SAMU, iniciar '
                    'RCP, usar DEA e transferir para cuidados avancados.'
                ),
                'exemplo': (
                    'Passos da RCP em adultos:\n'
                    '1. Verifique a seguranca do local\n'
                    '2. Verifique responsividade (toque e chame)\n'
                    '3. Ligue 192 (SAMU) e peca um DEA\n'
                    '4. Verifique respiracao (10 segundos)\n'
                    '5. Inicie compressoes: 30 compressoes x 2 ventilacoes\n'
                    '6. Frequencia: 100-120 compressoes/minuto\n'
                    '7. Profundidade: 5-6 cm\n'
                    '8. Use o DEA assim que disponivel'
                ),
            },
            {
                'titulo': 'Manobra de Heimlich (Engasgamento)',
                'explicacao': (
                    'A manobra de Heimlich e a tecnica de desobstrucao de vias aereas em caso de '
                    'engasgamento. Posicione-se atras da vitima, coloque o punho fechado acima do '
                    'umbigo e abaixo do esterno, e realize compressoes abdominais rapidas para cima '
                    'e para dentro. Em bebes, a tecnica e diferente: 5 tapas nas costas + 5 compressoes '
                    'toracicas.'
                ),
                'exemplo': (
                    'Sinais de engasgamento grave:\n'
                    '- Vitima nao consegue falar, tossir ou respirar\n'
                    '- Leva as maos ao pescoco (sinal universal)\n'
                    '- Labios e unhas ficam azulados (cianose)\n\n'
                    'Acao: Heimlich ate o objeto sair ou a vitima perder a consciencia.\n'
                    'Se inconsciente: inicie RCP e verifique a boca a cada ciclo.'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual a frequencia recomendada de compressoes toracicas na RCP?', 'alternativas': ['a) 60-80 por minuto', 'b) 80-100 por minuto', 'c) 100-120 por minuto', 'd) 120-140 por minuto'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Descreva os passos da cadeia de sobrevivencia em caso de parada cardiorrespiratoria.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual o numero do SAMU no Brasil?', 'alternativas': ['a) 190', 'b) 191', 'c) 192', 'd) 193'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique como realizar a manobra de Heimlich em um adulto consciente com engasgamento grave.'},
        ],
        'dicas_estudo': [
            'Pratique RCP em manequins sempre que possivel.',
            'Saiba onde estao os DEAs nos locais que voce frequenta.',
            'Mantenha um kit de primeiros socorros em casa e no carro.',
            'Renove seus conhecimentos anualmente - protocolos podem mudar.',
        ],
        'glossario': [
            'BLS: Basic Life Support - Suporte Basico de Vida.',
            'RCP: Ressuscitacao Cardiopulmonar.',
            'DEA: Desfibrilador Externo Automatico.',
            'SAMU: Servico de Atendimento Movel de Urgencia (192).',
            'Heimlich: manobra de desobstrucao de vias aereas.',
            'Cianose: coloracao azulada da pele por falta de oxigenio.',
            'Triagem: classificacao de vitimas por gravidade.',
        ],
    },
    'Nutricao Esportiva': {
        'ementa': 'Fundamentos de nutricao. Macronutrientes e micronutrientes. Nutricao para performance esportiva. Suplementacao. Composicao corporal. Periodizacao nutricional. Hidratacao.',
        'topicos': [
            'Modulo 1: Fundamentos de nutricao - macro e micronutrientes',
            'Modulo 2: Metabolismo energetico e gasto calorico',
            'Modulo 3: Nutricao para hipertrofia e ganho de massa muscular',
            'Modulo 4: Nutricao para emagrecimento e definicao',
            'Modulo 5: Suplementacao esportiva baseada em evidencias',
            'Modulo 6: Hidratacao e reposicao de eletrolitros',
            'Modulo 7: Periodizacao nutricional e timing de nutrientes',
            'Modulo 8: Composicao corporal - avaliacao e monitoramento',
        ],
        'bibliografia': [
            'MCARDLE, W. Fisiologia do Exercicio. Guanabara Koogan, 2016.',
            'KLEINER, S. Nutricao para o Treinamento de Forca. Manole, 2015.',
            'SOCIEDADE BRASILEIRA DE MEDICINA DO EXERCICIO. Diretrizes de Nutricao Esportiva. SBME, 2021.',
        ],
        'introducao': (
            'A nutricao esportiva e a ciencia que estuda a relacao entre alimentacao e performance '
            'fisica. Uma dieta adequada pode melhorar o desempenho, acelerar a recuperacao e '
            'otimizar a composicao corporal. Neste curso, voce aprendera sobre macronutrientes, '
            'suplementacao baseada em evidencias, periodizacao nutricional e estrategias para '
            'diferentes objetivos (hipertrofia, emagrecimento, performance).'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Macronutrientes e Suas Funcoes',
                'explicacao': (
                    'Os tres macronutrientes sao: proteinas (4 kcal/g) - construcao e reparo muscular; '
                    'carboidratos (4 kcal/g) - principal fonte de energia; gorduras (9 kcal/g) - '
                    'producao hormonal e absorcao de vitaminas. Para atletas, a distribuicao ideal '
                    'depende do tipo de esporte, fase de treinamento e objetivos individuais.'
                ),
                'exemplo': (
                    'Recomendacoes para praticantes de musculacao:\n'
                    '- Proteina: 1.6-2.2g por kg de peso corporal/dia\n'
                    '- Carboidrato: 4-7g por kg/dia (varia com intensidade)\n'
                    '- Gordura: 0.5-1.5g por kg/dia\n\n'
                    'Exemplo para pessoa de 80kg em fase de hipertrofia:\n'
                    'Proteina: 160g | Carboidrato: 400g | Gordura: 80g\n'
                    'Total: ~2960 kcal/dia'
                ),
            },
            {
                'titulo': 'Suplementacao Baseada em Evidencias',
                'explicacao': (
                    'A maioria dos suplementos nao tem evidencia cientifica solida. Os suplementos '
                    'com maior nivel de evidencia sao: creatina monohidratada (forca e hipertrofia), '
                    'whey protein (conveniencia proteica), cafeina (performance) e vitamina D '
                    '(quando deficiente). Suplementos nao substituem uma alimentacao equilibrada.'
                ),
                'exemplo': (
                    'Suplementos com forte evidencia cientifica:\n'
                    '- Creatina: 3-5g/dia, todos os dias (nao precisa ciclar)\n'
                    '- Whey Protein: 20-40g pos-treino (conveniencia)\n'
                    '- Cafeina: 3-6mg/kg, 30-60 min antes do treino\n'
                    '- Vitamina D: 1000-2000 UI/dia (se deficiente)\n\n'
                    'Sem evidencia suficiente: BCAA, glutamina, tribulus, HMB'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual macronutriente fornece mais calorias por grama?', 'alternativas': ['a) Proteina (4 kcal/g)', 'b) Carboidrato (4 kcal/g)', 'c) Gordura (9 kcal/g)', 'd) Todos fornecem igual'], 'resposta': 'c'},
            {'tipo': 'dissertativa', 'enunciado': 'Calcule as necessidades proteicas diarias de um atleta de 75kg em fase de hipertrofia, considerando a recomendacao de 2g/kg.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual suplemento tem a maior evidencia cientifica para ganho de forca?', 'alternativas': ['a) BCAA', 'b) Glutamina', 'c) Creatina', 'd) Tribulus'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Aprenda a ler rotulos nutricionais e tabelas de composicao de alimentos.',
            'Use aplicativos como MyFitnessPal para rastrear sua alimentacao.',
            'Baseie-se em evidencias cientificas, nao em modismos.',
            'Consulte um nutricionista esportivo para orientacao personalizada.',
        ],
        'glossario': [
            'Macronutrientes: proteinas, carboidratos e gorduras.',
            'Micronutrientes: vitaminas e minerais.',
            'Metabolismo basal: energia gasta em repouso para funcoes vitais.',
            'Superavit calorico: consumir mais calorias do que gasta (ganho de peso).',
            'Deficit calorico: consumir menos calorias do que gasta (perda de peso).',
            'Periodizacao nutricional: ajustar a dieta conforme fases do treinamento.',
            'Creatina: suplemento que aumenta a disponibilidade de energia muscular.',
        ],
    },
    'Direito Digital e LGPD': {
        'ementa': 'Fundamentos de direito digital. Marco Civil da Internet. LGPD e protecao de dados. Crimes digitais. Contratos eletronicos. Propriedade intelectual digital. Compliance digital.',
        'topicos': [
            'Modulo 1: Fundamentos de direito digital e sociedade da informacao',
            'Modulo 2: Marco Civil da Internet - principios e direitos',
            'Modulo 3: LGPD - principios, bases legais e direitos dos titulares',
            'Modulo 4: LGPD na pratica - adequacao e programa de privacidade',
            'Modulo 5: Crimes digitais - tipificacao e investigacao',
            'Modulo 6: Contratos eletronicos e assinaturas digitais',
            'Modulo 7: Propriedade intelectual no ambiente digital',
            'Modulo 8: Compliance digital e governanca de dados',
        ],
        'bibliografia': [
            'PINHEIRO, P. Direito Digital. Saraiva, 2021.',
            'BIONI, B. Protecao de Dados Pessoais: A Funcao e os Limites do Consentimento. Forense, 2019.',
            'BRASIL. Lei 13.709/2018 - Lei Geral de Protecao de Dados Pessoais.',
        ],
        'introducao': (
            'O direito digital e uma area em rapida expansao que regula as relacoes juridicas '
            'no ambiente digital. Com a LGPD (Lei Geral de Protecao de Dados), todas as '
            'organizacoes que tratam dados pessoais precisam se adequar. Neste curso, voce '
            'aprendera sobre Marco Civil da Internet, LGPD, crimes digitais e contratos '
            'eletronicos, conhecimentos essenciais para profissionais de TI, direito e compliance.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'LGPD - Lei Geral de Protecao de Dados',
                'explicacao': (
                    'A LGPD (Lei 13.709/2018) regula o tratamento de dados pessoais no Brasil. '
                    'Dados pessoais sao informacoes que identificam ou podem identificar uma pessoa. '
                    'A lei estabelece 10 bases legais para tratamento (consentimento, contrato, '
                    'obrigacao legal, etc.), direitos dos titulares (acesso, correcao, exclusao) '
                    'e a figura do DPO (Encarregado de Protecao de Dados).'
                ),
                'exemplo': (
                    'Bases legais da LGPD mais comuns:\n'
                    '- Consentimento: titular autoriza expressamente\n'
                    '- Execucao de contrato: necessario para cumprir contrato\n'
                    '- Obrigacao legal: exigido por lei (ex: nota fiscal)\n'
                    '- Legitimo interesse: interesse do controlador, respeitando direitos\n\n'
                    'Direitos do titular: acesso, correcao, anonimizacao, portabilidade, exclusao'
                ),
            },
            {
                'titulo': 'Crimes Digitais',
                'explicacao': (
                    'Crimes digitais sao condutas ilicitas praticadas por meio de dispositivos '
                    'eletronicos ou contra sistemas informaticos. A Lei Carolina Dieckmann '
                    '(12.737/2012) tipificou a invasao de dispositivos. O Marco Civil da Internet '
                    '(12.965/2014) estabelece principios como neutralidade de rede e privacidade. '
                    'Crimes comuns incluem phishing, ransomware, fraude eletronica e cyberbullying.'
                ),
                'exemplo': (
                    'Tipos de crimes digitais:\n'
                    '- Invasao de dispositivo informatico (Art. 154-A CP)\n'
                    '- Estelionato digital / fraude eletronica (Art. 171 CP)\n'
                    '- Crimes contra a honra online (difamacao, calúnia)\n'
                    '- Pornografia infantil (ECA)\n'
                    '- Ransomware (extorsao digital)\n\n'
                    'Preservacao de evidencias: prints com metadados, ata notarial'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'O que sao dados pessoais segundo a LGPD?', 'alternativas': ['a) Apenas CPF e RG', 'b) Informacoes que identificam ou podem identificar uma pessoa', 'c) Apenas dados digitais', 'd) Dados de empresas'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Explique tres bases legais da LGPD para tratamento de dados pessoais e de um exemplo pratico de cada.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'Qual lei brasileira tipificou a invasao de dispositivos informaticos?', 'alternativas': ['a) LGPD', 'b) Marco Civil da Internet', 'c) Lei Carolina Dieckmann', 'd) Codigo de Defesa do Consumidor'], 'resposta': 'c'},
        ],
        'dicas_estudo': [
            'Leia a LGPD na integra - sao apenas 65 artigos.',
            'Acompanhe as decisoes da ANPD (Autoridade Nacional de Protecao de Dados).',
            'Estude casos reais de vazamento de dados e suas consequencias juridicas.',
            'Considere a certificacao EXIN Privacy and Data Protection.',
        ],
        'glossario': [
            'LGPD: Lei Geral de Protecao de Dados (Lei 13.709/2018).',
            'DPO: Data Protection Officer / Encarregado de Protecao de Dados.',
            'ANPD: Autoridade Nacional de Protecao de Dados.',
            'Dado pessoal: informacao que identifica ou pode identificar uma pessoa.',
            'Dado sensivel: dado sobre origem racial, saude, religiao, biometria, etc.',
            'Controlador: quem decide sobre o tratamento de dados pessoais.',
            'Operador: quem realiza o tratamento em nome do controlador.',
            'Marco Civil: Lei 12.965/2014 - principios da internet no Brasil.',
        ],
    },
    'Ingles para Negocios': {
        'ementa': 'Business English fundamentals. Vocabulario corporativo. Emails e comunicacao escrita profissional. Apresentacoes em ingles. Reunioes e negociacoes. Entrevistas de emprego em ingles.',
        'topicos': [
            'Modulo 1: Business English - vocabulario e expressoes corporativas',
            'Modulo 2: Email writing - estrutura, tom e etiqueta profissional',
            'Modulo 3: Telephone and video calls - expressoes e praticas',
            'Modulo 4: Presentations - estrutura, transicoes e dicas',
            'Modulo 5: Meetings - participacao, opinioes e tomada de decisao',
            'Modulo 6: Negotiations - estrategias e linguagem diplomatica',
            'Modulo 7: Job interviews - perguntas comuns e respostas eficazes',
            'Modulo 8: Cross-cultural communication e ingles global',
        ],
        'bibliografia': [
            'COTTON, D. Market Leader: Business English. Pearson, 2016.',
            'MASCULL, B. Business Vocabulary in Use. Cambridge, 2017.',
            'POWELL, M. Presenting in English. Cengage, 2011.',
        ],
        'introducao': (
            'O ingles e a lingua franca dos negocios globais. Dominar o Business English '
            'abre portas para oportunidades internacionais, melhores salarios e comunicacao '
            'eficaz com equipes globais. Neste curso, voce desenvolvera habilidades praticas '
            'para escrever emails profissionais, fazer apresentacoes, participar de reunioes '
            'e negociacoes, e se preparar para entrevistas de emprego em ingles.'
        ),
        'conceitos_fundamentais': [
            {
                'titulo': 'Professional Email Writing',
                'explicacao': (
                    'Emails profissionais em ingles seguem uma estrutura clara: greeting (saudacao), '
                    'purpose (objetivo), body (detalhes), action required (proximos passos) e closing '
                    '(encerramento). O tom deve ser formal mas amigavel, direto e conciso. Evite '
                    'girias, abreviacoes e emojis em comunicacoes formais.'
                ),
                'exemplo': (
                    'Exemplo de email profissional:\n'
                    'Subject: Q3 Sales Report - Action Required\n\n'
                    'Dear Mr. Johnson,\n\n'
                    'I hope this email finds you well.\n\n'
                    'I am writing to share the Q3 sales report (attached).\n'
                    'Key highlights:\n'
                    '- Revenue increased by 15% compared to Q2\n'
                    '- New client acquisition exceeded targets\n\n'
                    'Could you please review and share your feedback by Friday?\n\n'
                    'Best regards,\n'
                    'Ana Silva'
                ),
            },
            {
                'titulo': 'Presentations and Public Speaking',
                'explicacao': (
                    'Apresentacoes em ingles seguem a estrutura: opening (captar atencao), '
                    'outline (agenda), main body (conteudo com transicoes claras), summary '
                    '(resumo) e Q&A (perguntas). Use signposting language para guiar a audiencia: '
                    '"First, I\'d like to...", "Moving on to...", "To sum up...". Pratique a '
                    'pronuncia e o ritmo para transmitir confianca.'
                ),
                'exemplo': (
                    'Expressoes uteis para apresentacoes:\n'
                    'Opening: "Good morning. Today I\'d like to talk about..."\n'
                    'Outline: "I\'ve divided my presentation into three parts..."\n'
                    'Transition: "Now, let\'s move on to..."\n'
                    'Emphasis: "I\'d like to draw your attention to..."\n'
                    'Summary: "To sum up, the key takeaways are..."\n'
                    'Q&A: "I\'d be happy to answer any questions."'
                ),
            },
        ],
        'exercicios': [
            {'tipo': 'multipla_escolha', 'enunciado': 'Which is the most appropriate email closing for a formal business email?', 'alternativas': ['a) Cheers', 'b) Best regards', 'c) See ya', 'd) XOXO'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Write a professional email requesting a meeting with a potential client to discuss a new product launch.'},
            {'tipo': 'multipla_escolha', 'enunciado': 'What does "signposting language" mean in presentations?', 'alternativas': ['a) Using signs and posters', 'b) Phrases that guide the audience through the presentation', 'c) Speaking loudly', 'd) Using bullet points'], 'resposta': 'b'},
            {'tipo': 'dissertativa', 'enunciado': 'Prepare a 2-minute opening for a presentation about your company\'s annual results, including greeting, agenda and first key point.'},
        ],
        'dicas_estudo': [
            'Assista a TED Talks em ingles para melhorar listening e aprender vocabulario.',
            'Pratique escrevendo emails em ingles no dia a dia.',
            'Use apps como Duolingo e BBC Learning English para pratica diaria.',
            'Participe de grupos de conversacao em ingles (presencial ou online).',
        ],
        'glossario': [
            'Business English: ingles voltado para o ambiente corporativo.',
            'Signposting: expressoes que guiam a audiencia em apresentacoes.',
            'Stakeholder: parte interessada em um projeto ou empresa.',
            'KPI: Key Performance Indicator - indicador de desempenho.',
            'ROI: Return on Investment - retorno sobre investimento.',
            'Deadline: prazo final para entrega.',
            'Follow-up: acompanhamento apos uma reuniao ou contato.',
            'Small talk: conversa informal antes de reunioes de negocios.',
        ],
    },
}


# ============================================================
# Estilos de PDF (mesmos de gerar_material_graduacao_sem1a4.py)
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
    """Converte nome de curso em nome de arquivo seguro."""
    nome = nome.lower()
    nome = nome.replace('(', '').replace(')', '').replace('/', '_')
    nome = re.sub(r'[^a-z0-9_]', '_', nome)
    nome = re.sub(r'_+', '_', nome).strip('_')
    return nome


# ============================================================
# Geracao de PDF de Material Didatico para Extensao
# ============================================================
def gerar_material_pdf(curso_info, output_path, styles):
    """Gera PDF de material didatico (~5-8 paginas) para um curso de extensao."""
    nome = curso_info['nome']
    conteudo = CONTEUDO_EXTENSAO.get(nome)
    if not conteudo:
        print(f'  WARN: Sem conteudo para "{nome}", pulando.')
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
    story.append(Paragraph(f'Curso de Extensao', styles['SubtituloCurso']))
    story.append(Paragraph(
        f'Area: {curso_info["area"]} | Modalidade: {curso_info["modalidade"]}',
        styles['SubtituloCurso']
    ))
    story.append(Paragraph(
        f'Duracao: {curso_info["duracao_horas"]}h ({curso_info["duracao_meses"]} {"mes" if curso_info["duracao_meses"] == 1 else "meses"})',
        styles['SubtituloCurso']
    ))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph('Material de Estudo', styles['MaterialTitulo']))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(nome, styles['DisciplinaTitulo']))
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
        'A seguir, apresentamos os conceitos-chave deste curso com explicacoes '
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

    # ---- 4. Resumo dos Principais Topicos (Modulos) ----
    story.append(Paragraph('3. RESUMO DOS PRINCIPAIS TOPICOS', styles['Secao']))
    story.append(Paragraph(
        'O conteudo programatico do curso esta organizado nos seguintes modulos:',
        styles['CorpoMaterial']
    ))
    story.append(Spacer(1, 4))
    for topico in conteudo.get('topicos', []):
        story.append(Paragraph(f'\u2022 {topico}', styles['ItemLista']))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        'Cada modulo aborda um aspecto fundamental do curso, construindo '
        'progressivamente o conhecimento necessario para dominar o tema. '
        'Recomenda-se estudar os modulos na ordem apresentada.',
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
        'Para maximizar seu aprendizado neste curso, siga estas recomendacoes:',
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
        f'{INSTITUICAO} - Extensao: {nome} - Material de Estudo',
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

    print('=== Gerando material didatico de extensao — 15 cursos ===')
    print(f'Cursos: {len(CURSOS_EXTENSAO)}')
    print(f'Saida: {os.path.join(OUTPUT_DIR, "privado", "extensao")}')
    print()

    for curso in CURSOS_EXTENSAO:
        curso_id = curso['curso_id']
        nome = curso['nome']
        filename = sanitize_filename(nome) + '_material.pdf'
        out_dir = os.path.join(OUTPUT_DIR, 'privado', 'extensao', curso_id)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)

        ok = gerar_material_pdf(curso, out_path, styles)
        if ok:
            total += 1
            print(f'  [{curso_id}] {nome} -> {filename}')
        else:
            print(f'  [{curso_id}] FALHA: {nome}')

    print(f'\nDone!')
    print(f'  Total de PDFs gerados: {total}')
    print(f'  Diretorio: {os.path.join(OUTPUT_DIR, "privado", "extensao")}')


if __name__ == '__main__':
    main()
