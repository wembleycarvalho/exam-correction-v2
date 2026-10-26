"""
Gera PDFs de EMAIL/NEWSLETTER resumo para cursos de extensao.
Estilo newsletter academica — 1 pagina max, leitura rapida.

Cada PDF tem:
1. Header: "Newsletter - Extensao - {Curso}" com info de area/modalidade
2. "Destaques do Curso" — 3-4 bullet points
3. "O que voce vai aprender" — paragrafo resumo
4. "Dica do Instrutor" — dica pratica
5. "Recursos Recomendados" — 2-3 links/livros
6. "Para quem e este curso" — publico-alvo
7. Footer institucional

Saida: output/apostilas/privado/extensao/{curso_id}/{course_name}_email.pdf

Uso: source .env && python3 scripts/gerar_email_extensao.py
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

# ============================================================
# Cursos de extensao — 15 cursos
# ============================================================
CURSOS_EXTENSAO = [
    {'curso_id': 'ext-ia-aplicada', 'nome': 'Inteligencia Artificial Aplicada', 'area': 'Tecnologia', 'modalidade': 'EAD'},
    {'curso_id': 'ext-cybersecurity', 'nome': 'Cybersecurity Essentials', 'area': 'Tecnologia', 'modalidade': 'EAD'},
    {'curso_id': 'ext-data-science', 'nome': 'Data Science com Python', 'area': 'Tecnologia', 'modalidade': 'EAD'},
    {'curso_id': 'ext-cloud-aws', 'nome': 'Cloud Computing com AWS', 'area': 'Tecnologia', 'modalidade': 'EAD'},
    {'curso_id': 'ext-ux-design', 'nome': 'UX/UI Design', 'area': 'Design', 'modalidade': 'EAD'},
    {'curso_id': 'ext-gestao-projetos', 'nome': 'Gestao de Projetos e Metodologias Ageis', 'area': 'Negocios', 'modalidade': 'EAD'},
    {'curso_id': 'ext-marketing-digital', 'nome': 'Marketing Digital e Analytics', 'area': 'Negocios', 'modalidade': 'EAD'},
    {'curso_id': 'ext-devops', 'nome': 'DevOps e CI/CD', 'area': 'Tecnologia', 'modalidade': 'EAD'},
    {'curso_id': 'ext-blockchain', 'nome': 'Blockchain e Web3', 'area': 'Tecnologia', 'modalidade': 'EAD'},
    {'curso_id': 'ext-lideranca', 'nome': 'Lideranca e Gestao de Pessoas', 'area': 'Negocios', 'modalidade': 'EAD'},
    {'curso_id': 'ext-saude-mental', 'nome': 'Saude Mental no Trabalho', 'area': 'Saude', 'modalidade': 'EAD'},
    {'curso_id': 'ext-primeiros-socorros', 'nome': 'Primeiros Socorros e Urgencias', 'area': 'Saude', 'modalidade': 'Presencial'},
    {'curso_id': 'ext-nutricao-esportiva', 'nome': 'Nutricao Esportiva', 'area': 'Saude', 'modalidade': 'EAD'},
    {'curso_id': 'ext-direito-digital', 'nome': 'Direito Digital e LGPD', 'area': 'Humanas', 'modalidade': 'EAD'},
    {'curso_id': 'ext-ingles-negocios', 'nome': 'Ingles para Negocios', 'area': 'Negocios', 'modalidade': 'EAD'},
]


# ============================================================
# Conteudo de email/newsletter por curso de extensao
# Cada entrada: destaques, resumo, dica, recursos, publico_alvo
# ============================================================
EMAIL_CONTENT = {
    'Inteligencia Artificial Aplicada': {
        'destaques': [
            'Aprenda a usar ChatGPT, visao computacional e NLP em projetos reais',
            'Crie chatbots, sistemas de recomendacao e automacoes inteligentes',
            'Ferramentas praticas: OpenAI API, Hugging Face, LangChain',
            'Curso 100% pratico com projetos entregaveis a cada modulo',
        ],
        'resumo': (
            'Este curso de extensao ensina como aplicar Inteligencia Artificial no dia a dia '
            'profissional. Voce vai trabalhar com APIs de IA generativa, construir chatbots, '
            'implementar visao computacional e processar linguagem natural. O foco e pratico: '
            'cada modulo termina com um projeto aplicavel ao seu trabalho ou negocio.'
        ),
        'dica': (
            'Comece automatizando uma tarefa repetitiva do seu trabalho com IA. Pode ser '
            'classificacao de emails, resumo de documentos ou analise de sentimento em feedbacks. '
            'Quando a IA resolve um problema real seu, o aprendizado acelera muito.'
        ),
        'recursos': [
            'Plataforma: Hugging Face — modelos de IA prontos para usar',
            'Documentacao: platform.openai.com — API da OpenAI',
            'Curso complementar: DeepLearning.AI Short Courses (gratuitos)',
        ],
        'publico_alvo': (
            'Profissionais de tecnologia, analistas de dados, gestores e empreendedores '
            'que querem aplicar IA em seus projetos e processos. Conhecimento basico de '
            'programacao (Python) e recomendado.'
        ),
    },
    'Cybersecurity Essentials': {
        'destaques': [
            'OWASP Top 10, pentest basico e analise de vulnerabilidades',
            'Laboratorios virtuais com cenarios reais de ataque e defesa',
            'Preparatorio para certificacao CompTIA Security+',
            'Area com deficit de profissionais e salarios acima da media',
        ],
        'resumo': (
            'Cybersecurity Essentials oferece uma base solida em seguranca da informacao. '
            'Voce vai aprender a identificar vulnerabilidades, realizar testes de penetracao '
            'basicos, configurar firewalls e implementar politicas de seguranca. O curso '
            'inclui laboratorios praticos que simulam cenarios reais de ataque e defesa.'
        ),
        'dica': (
            'Pratique em ambientes controlados como OWASP WebGoat e Hack The Box. Nunca '
            'teste em sistemas sem autorizacao. A melhor forma de aprender defesa e entender '
            'como os ataques funcionam — de forma etica e legal.'
        ),
        'recursos': [
            'Pratica: Hack The Box — laboratorios de pentest',
            'Site: OWASP.org — guias e ferramentas de seguranca',
            'Certificacao: CompTIA Security+ Study Guide',
        ],
        'publico_alvo': (
            'Profissionais de TI, administradores de rede, desenvolvedores e qualquer pessoa '
            'interessada em seguranca cibernetica. Conhecimento basico de redes e sistemas '
            'operacionais e recomendado.'
        ),
    },
    'Data Science com Python': {
        'destaques': [
            'Pandas, NumPy, Matplotlib, Scikit-learn — o toolkit completo',
            'Projetos com datasets reais do Kaggle e fontes publicas',
            'Da analise exploratoria ao modelo preditivo em producao',
            'Uma das carreiras mais demandadas e bem remuneradas em TI',
        ],
        'resumo': (
            'Data Science com Python ensina o ciclo completo de ciencia de dados: coleta, '
            'limpeza, analise exploratoria, visualizacao, modelagem preditiva e comunicacao '
            'de resultados. Usando Python e suas bibliotecas mais populares, voce vai '
            'transformar dados brutos em insights acionaveis para tomada de decisao.'
        ),
        'dica': (
            'Escolha um tema que voce gosta e faca um projeto completo de data science com ele. '
            'Futebol, musica, clima, financas — quando os dados sao interessantes para voce, '
            'o aprendizado flui naturalmente. Publique no Kaggle para receber feedback.'
        ),
        'recursos': [
            'Plataforma: Kaggle.com — datasets, competicoes e notebooks',
            'Livro: "Python para Analise de Dados" - Wes McKinney',
            'Ferramenta: Google Colab — notebooks Python gratuitos na nuvem',
        ],
        'publico_alvo': (
            'Analistas de negocios, profissionais de BI, desenvolvedores e qualquer pessoa '
            'que trabalhe com dados e queira extrair insights. Conhecimento basico de Python '
            'e estatistica e recomendado.'
        ),
    },
    'Cloud Computing com AWS': {
        'destaques': [
            'EC2, S3, Lambda, RDS, VPC — os servicos essenciais da AWS',
            'Preparatorio para certificacao AWS Solutions Architect Associate',
            'Laboratorios praticos com conta AWS Free Tier',
            'Cloud e onde toda a tecnologia moderna roda — habilidade essencial',
        ],
        'resumo': (
            'Cloud Computing com AWS ensina a projetar, implantar e gerenciar infraestrutura '
            'na nuvem da Amazon. Voce vai dominar os servicos fundamentais (EC2, S3, Lambda, '
            'RDS, VPC), aprender arquitetura well-architected e se preparar para a certificacao '
            'AWS Solutions Architect Associate, uma das mais valorizadas do mercado.'
        ),
        'dica': (
            'Crie uma conta AWS Free Tier e faca todos os laboratorios na pratica. Nada substitui '
            'a experiencia de configurar servicos reais. Sempre destrua os recursos apos praticar '
            'para evitar custos inesperados. Use o AWS Cost Explorer para monitorar.'
        ),
        'recursos': [
            'Certificacao: AWS Solutions Architect Associate — guia oficial',
            'Plataforma: A Cloud Guru — cursos e laboratorios AWS',
            'Documentacao: docs.aws.amazon.com — referencia completa',
        ],
        'publico_alvo': (
            'Desenvolvedores, administradores de sistemas, DevOps engineers e profissionais '
            'de TI que querem dominar cloud computing. Conhecimento basico de redes e Linux '
            'e recomendado.'
        ),
    },
    'UX/UI Design': {
        'destaques': [
            'Figma, pesquisa com usuarios, wireframes e prototipos interativos',
            'Design centrado no usuario — crie interfaces que as pessoas amam',
            'Construa um portfolio profissional durante o curso',
            'Habilidade valorizada em todas as empresas de tecnologia',
        ],
        'resumo': (
            'UX/UI Design ensina a criar experiencias digitais intuitivas e agradaveis. '
            'Voce vai aprender pesquisa com usuarios, arquitetura de informacao, wireframing, '
            'prototipacao no Figma, design systems e testes de usabilidade. O curso foca '
            'na construcao de um portfolio profissional com projetos reais.'
        ),
        'dica': (
            'Redesenhe um app que voce usa no dia a dia — identifique 3 problemas de UX e '
            'proponha solucoes com prototipos no Figma. Esse exercicio treina seu olhar critico '
            'e gera pecas para o portfolio. Teste seus prototipos com usuarios reais.'
        ),
        'recursos': [
            'Ferramenta: Figma (figma.com) — gratuito para uso pessoal',
            'Livro: "Nao Me Faca Pensar" - Steve Krug',
            'Curso complementar: Google UX Design Certificate (Coursera)',
        ],
        'publico_alvo': (
            'Designers graficos, desenvolvedores frontend, product managers e profissionais '
            'em transicao de carreira para design digital. Nao e necessario conhecimento '
            'previo em design.'
        ),
    },
    'Gestao de Projetos e Metodologias Ageis': {
        'destaques': [
            'Scrum, Kanban, XP — os frameworks que o mercado usa',
            'Preparatorio para certificacao PSM I (Professional Scrum Master)',
            'Ferramentas praticas: Jira, Trello, Monday.com',
            '90%+ das empresas de TI adotam metodologias ageis',
        ],
        'resumo': (
            'Este curso ensina a gerenciar projetos de qualquer tamanho usando metodologias '
            'ageis e tradicionais. Voce vai dominar Scrum (sprints, papeis, cerimonias), '
            'Kanban (fluxo continuo, WIP limits), tecnicas do PMBOK e ferramentas de gestao. '
            'O curso prepara para a certificacao PSM I da Scrum.org.'
        ),
        'dica': (
            'Aplique Scrum no seu proximo projeto, mesmo que seja pessoal. Use um quadro Kanban '
            '(Trello ou post-its na parede) para organizar suas tarefas. A melhor forma de '
            'aprender agil e praticando, nao apenas lendo sobre.'
        ),
        'recursos': [
            'Guia: Scrum Guide oficial (scrumguides.org) — leitura obrigatoria',
            'Certificacao: PSM I — Professional Scrum Master (Scrum.org)',
            'Ferramenta: Jira — gestao de projetos ageis',
        ],
        'publico_alvo': (
            'Gerentes de projeto, coordenadores, lideres de equipe, desenvolvedores e qualquer '
            'profissional que trabalhe com projetos. Nao e necessario experiencia previa em '
            'gestao de projetos.'
        ),
    },
    'Marketing Digital e Analytics': {
        'destaques': [
            'Google Ads, SEO, redes sociais e analytics na pratica',
            'Aprenda a medir ROI e tomar decisoes baseadas em dados',
            'Ferramentas: Google Analytics, Meta Ads, SEMrush',
            'Marketing digital e essencial para qualquer negocio moderno',
        ],
        'resumo': (
            'Marketing Digital e Analytics ensina a planejar, executar e medir campanhas '
            'de marketing online. Voce vai dominar Google Ads, SEO, marketing de conteudo, '
            'redes sociais e analytics. O foco e em resultados mensuráveis: cada acao de '
            'marketing deve ser rastreavel e otimizavel com base em dados.'
        ),
        'dica': (
            'Crie um blog ou perfil profissional e aplique as tecnicas do curso nele. '
            'Nada ensina mais sobre marketing digital do que gerenciar sua propria presenca '
            'online. Acompanhe as metricas no Google Analytics e otimize semanalmente.'
        ),
        'recursos': [
            'Certificacao: Google Analytics Individual Qualification (gratuita)',
            'Ferramenta: Google Search Console — monitore seu SEO',
            'Curso complementar: Google Digital Garage (gratuito)',
        ],
        'publico_alvo': (
            'Empreendedores, profissionais de marketing, gestores de negocios e qualquer '
            'pessoa que queira promover produtos ou servicos online. Nao e necessario '
            'conhecimento tecnico previo.'
        ),
    },
    'DevOps e CI/CD': {
        'destaques': [
            'Docker, Kubernetes, Jenkins, GitHub Actions e Terraform',
            'Automatize o ciclo de vida do software do commit a producao',
            'Infraestrutura como codigo — reprodutibilidade e escalabilidade',
            'Uma das areas com maiores salarios em tecnologia',
        ],
        'resumo': (
            'DevOps e CI/CD ensina a automatizar todo o ciclo de vida do software. Voce vai '
            'aprender containers (Docker), orquestracao (Kubernetes), pipelines CI/CD '
            '(GitHub Actions, Jenkins), infraestrutura como codigo (Terraform) e monitoramento. '
            'DevOps e a ponte entre desenvolvimento e operacoes que acelera entregas.'
        ),
        'dica': (
            'Comece com Docker: containerize uma aplicacao sua e crie um docker-compose.yml. '
            'Depois, configure um pipeline CI/CD no GitHub Actions que faca build, teste e '
            'deploy automaticamente. Essa experiencia pratica vale mais que qualquer teoria.'
        ),
        'recursos': [
            'Livro: "The Phoenix Project" - Gene Kim (DevOps em forma de romance)',
            'Pratica: KodeKloud — laboratorios praticos de DevOps',
            'Ferramenta: GitHub Actions — CI/CD gratuito para repositorios GitHub',
        ],
        'publico_alvo': (
            'Desenvolvedores, administradores de sistemas, SREs e profissionais de TI que '
            'querem automatizar processos de desenvolvimento e deploy. Conhecimento basico '
            'de Linux e Git e recomendado.'
        ),
    },
    'Blockchain e Web3': {
        'destaques': [
            'Smart contracts com Solidity, DeFi, NFTs e DAOs',
            'Entenda a tecnologia por tras de criptomoedas e muito mais',
            'Aplicacoes empresariais: supply chain, identidade, votacao',
            'Tecnologia disruptiva com demanda crescente por profissionais',
        ],
        'resumo': (
            'Blockchain e Web3 ensina os fundamentos e aplicacoes praticas da tecnologia '
            'blockchain. Voce vai entender hashing, consenso distribuido, criar smart contracts '
            'em Solidity, explorar DeFi e NFTs, e conhecer aplicacoes empresariais como '
            'rastreamento de supply chain e identidade digital descentralizada.'
        ),
        'dica': (
            'Implemente uma blockchain simples em Python para entender os conceitos fundamentais. '
            'Depois, escreva um smart contract basico em Solidity e faca deploy na testnet do '
            'Ethereum (gratuito). A experiencia pratica desmistifica a tecnologia rapidamente.'
        ),
        'recursos': [
            'Ferramenta: Remix IDE — ambiente online para smart contracts Solidity',
            'Curso complementar: Blockchain Specialization (Coursera, University at Buffalo)',
            'Documentacao: ethereum.org/developers — guia oficial do Ethereum',
        ],
        'publico_alvo': (
            'Desenvolvedores, empreendedores, profissionais de financas e qualquer pessoa '
            'interessada em tecnologias descentralizadas. Conhecimento basico de programacao '
            'e recomendado para os modulos praticos.'
        ),
    },
    'Lideranca e Gestao de Pessoas': {
        'destaques': [
            'Coaching, feedback eficaz, gestao de conflitos e motivacao',
            'Lideranca situacional — adapte seu estilo ao contexto',
            'Soft skills que diferenciam profissionais em cargos de gestao',
            'Aplicavel em qualquer area — tecnologia, saude, negocios',
        ],
        'resumo': (
            'Lideranca e Gestao de Pessoas desenvolve as competencias essenciais para liderar '
            'equipes de alto desempenho. Voce vai aprender tecnicas de coaching, feedback '
            'construtivo, gestao de conflitos, motivacao e lideranca situacional. O curso '
            'combina teoria com exercicios praticos e estudos de caso reais.'
        ),
        'dica': (
            'Pratique dar feedback construtivo toda semana — comece com elogios especificos '
            'e depois avance para feedback de melhoria. Use a tecnica SBI (Situacao, Comportamento, '
            'Impacto) para estruturar suas conversas. Lideranca se desenvolve na pratica diaria.'
        ),
        'recursos': [
            'Livro: "O Monge e o Executivo" - James C. Hunter',
            'Livro: "Comece pelo Porque" - Simon Sinek',
            'Ferramenta: 15Five — plataforma de feedback e gestao de performance',
        ],
        'publico_alvo': (
            'Gestores, coordenadores, supervisores, lideres de equipe e profissionais que '
            'aspiram a cargos de lideranca. Aplicavel a qualquer area de atuacao. Nao e '
            'necessario experiencia previa em gestao.'
        ),
    },
    'Saude Mental no Trabalho': {
        'destaques': [
            'Burnout, ansiedade, estresse — identifique e previna',
            'Mindfulness e tecnicas de bem-estar aplicadas ao trabalho',
            'NR-1 atualizada exige gestao de riscos psicossociais',
            'Tema prioritario para empresas e profissionais de RH',
        ],
        'resumo': (
            'Saude Mental no Trabalho aborda os principais desafios psicologicos do ambiente '
            'corporativo: burnout, ansiedade, estresse cronico e assedio. Voce vai aprender a '
            'identificar sinais de alerta, aplicar tecnicas de mindfulness, promover qualidade '
            'de vida e implementar programas de bem-estar organizacional.'
        ),
        'dica': (
            'Comece por voce: pratique 5 minutos de mindfulness por dia usando apps como Headspace '
            'ou Calm. Observe como pequenas pausas conscientes durante o trabalho melhoram sua '
            'produtividade e bem-estar. Depois, compartilhe essas praticas com sua equipe.'
        ),
        'recursos': [
            'App: Headspace ou Calm — meditacao guiada para iniciantes',
            'Livro: "O Poder do Habito" - Charles Duhigg',
            'Guia: OMS — Diretrizes sobre Saude Mental no Trabalho (2022)',
        ],
        'publico_alvo': (
            'Profissionais de RH, gestores, lideres de equipe, psicologos organizacionais '
            'e qualquer profissional interessado em saude mental e bem-estar no trabalho. '
            'Nao e necessario formacao em saude.'
        ),
    },
    'Primeiros Socorros e Urgencias': {
        'destaques': [
            'Atendimento de emergencia: parada cardiaca, engasgamento, hemorragias',
            'Pratica em manequins com certificado de socorrista',
            'Curso presencial com simulacoes realistas',
            'Conhecimento que pode salvar vidas no trabalho e em casa',
        ],
        'resumo': (
            'Primeiros Socorros e Urgencias ensina tecnicas essenciais de atendimento '
            'pre-hospitalar. Voce vai aprender RCP (ressuscitacao cardiopulmonar), manobra '
            'de Heimlich, controle de hemorragias, imobilizacao de fraturas e triagem de '
            'vitimas. O curso e presencial com pratica em manequins e simulacoes.'
        ),
        'dica': (
            'Mantenha um kit de primeiros socorros no carro e no trabalho. Revise as tecnicas '
            'a cada 6 meses — em emergencias, a memoria muscular e o que salva. Ensine o basico '
            'para familiares: saber chamar o SAMU (192) ja e um grande primeiro passo.'
        ),
        'recursos': [
            'App: Primeiros Socorros — Cruz Vermelha (iOS e Android)',
            'Manual: Manual de Primeiros Socorros do Ministerio da Saude',
            'Emergencia: SAMU 192 — servico de atendimento movel de urgencia',
        ],
        'publico_alvo': (
            'Profissionais de saude, bombeiros, brigadistas, professores, pais e qualquer '
            'pessoa que queira estar preparada para emergencias. Nao e necessario formacao '
            'previa em saude.'
        ),
    },
    'Nutricao Esportiva': {
        'destaques': [
            'Suplementacao, periodizacao nutricional e composicao corporal',
            'Nutricao baseada em evidencias para performance esportiva',
            'Planejamento alimentar para diferentes modalidades esportivas',
            'Area em crescimento com o boom do fitness e wellness',
        ],
        'resumo': (
            'Nutricao Esportiva ensina os principios da alimentacao voltada para performance '
            'fisica. Voce vai aprender sobre macronutrientes, micronutrientes, hidratacao, '
            'suplementacao esportiva, periodizacao nutricional e composicao corporal. O curso '
            'aborda nutricao para diferentes modalidades: musculacao, corrida, esportes coletivos.'
        ),
        'dica': (
            'Comece registrando sua propria alimentacao por uma semana usando o app MyFitnessPal. '
            'Voce vai se surpreender com a diferenca entre o que acha que come e o que realmente '
            'come. Esse autoconhecimento e o primeiro passo para otimizar a nutricao.'
        ),
        'recursos': [
            'App: MyFitnessPal — rastreamento nutricional',
            'Livro: "Nutricao Esportiva" - Lancha Jr. & Campos-Ferraz',
            'Site: examine.com — suplementos baseados em evidencias',
        ],
        'publico_alvo': (
            'Nutricionistas, personal trainers, educadores fisicos, atletas amadores e '
            'profissionais, e entusiastas de fitness que querem otimizar sua alimentacao '
            'para performance. Conhecimento basico de biologia e recomendado.'
        ),
    },
    'Direito Digital e LGPD': {
        'destaques': [
            'LGPD, Marco Civil da Internet, crimes digitais e contratos eletronicos',
            'Compliance digital — como adequar empresas a legislacao',
            'Formacao de DPO (Data Protection Officer)',
            'Area em alta demanda com a vigencia da LGPD',
        ],
        'resumo': (
            'Direito Digital e LGPD aborda o marco regulatorio da tecnologia no Brasil. '
            'Voce vai estudar a Lei Geral de Protecao de Dados (LGPD), Marco Civil da Internet, '
            'crimes ciberneticos, contratos eletronicos, propriedade intelectual digital e '
            'compliance. O curso prepara para atuar como DPO ou consultor de privacidade.'
        ),
        'dica': (
            'Faca um mapeamento de dados pessoais na sua empresa ou projeto pessoal. Identifique '
            'quais dados sao coletados, onde sao armazenados, quem tem acesso e qual a base legal. '
            'Esse exercicio pratico e o primeiro passo para adequacao a LGPD.'
        ),
        'recursos': [
            'Lei: LGPD (Lei 13.709/2018) — texto completo no planalto.gov.br',
            'Guia: ANPD — Guias Orientativos sobre LGPD',
            'Certificacao: EXIN Privacy and Data Protection Foundation',
        ],
        'publico_alvo': (
            'Advogados, profissionais de TI, compliance officers, gestores e qualquer '
            'profissional que lide com dados pessoais. Nao e necessario formacao em Direito '
            'para os modulos de compliance e LGPD.'
        ),
    },
    'Ingles para Negocios': {
        'destaques': [
            'Business English: reunioes, apresentacoes, negociacoes e emails',
            'Vocabulario especifico para ambientes corporativos internacionais',
            'Pratica de conversacao com cenarios reais de negocios',
            'Ingles e requisito obrigatorio em empresas multinacionais',
        ],
        'resumo': (
            'Ingles para Negocios desenvolve as habilidades de comunicacao em ingles no contexto '
            'corporativo. Voce vai praticar reunioes, apresentacoes, negociacoes, redacao de '
            'emails profissionais e small talk. O curso foca em situacoes reais do ambiente '
            'de trabalho internacional, com vocabulario especifico de negocios.'
        ),
        'dica': (
            'Mude o idioma do seu celular e computador para ingles. Assista reunioes e '
            'apresentacoes em ingles no YouTube (TED Talks sao otimas). Pratique escrever '
            'emails em ingles mesmo que nao precise — a fluencia vem com a pratica constante.'
        ),
        'recursos': [
            'App: Duolingo Business — ingles para negocios',
            'Site: BBC Learning English — Business English',
            'Livro: "Business Vocabulary in Use" - Bill Mascull (Cambridge)',
        ],
        'publico_alvo': (
            'Executivos, gestores, profissionais em empresas multinacionais e qualquer pessoa '
            'que precise se comunicar em ingles no ambiente de trabalho. Nivel intermediario '
            'de ingles e recomendado.'
        ),
    },
}


# ============================================================
# Funcoes auxiliares
# ============================================================

def sanitize_filename(nome):
    """Converte nome de curso em nome de arquivo seguro."""
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

    # Subtitulo com info de area/modalidade
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

    # Dica do instrutor — destaque
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

    # Publico-alvo
    styles.add(ParagraphStyle(
        name='PublicoAlvoEmail',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        leading=14,
        fontName='Helvetica',
        textColor=colors.HexColor('#2c3e50'),
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


def gerar_email_pdf(curso_info, output_path, styles):
    """Gera PDF estilo newsletter/email para um curso de extensao."""
    nome = curso_info['nome']
    conteudo = EMAIL_CONTENT.get(nome)
    if not conteudo:
        print(f'  WARN: Sem conteudo de email para "{nome}", pulando.')
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
        'Newsletter - Extensao',
        styles['NewsletterHeader'],
    ))
    story.append(Paragraph(
        nome,
        styles['NewsletterHeader'],
    ))
    story.append(Paragraph(
        f'Area: {curso_info["area"]} | Modalidade: {curso_info["modalidade"]} | Extensao',
        styles['NewsletterSub'],
    ))

    # ---- Linha separadora ----
    story.append(HRFlowable(
        width='100%', thickness=1, color=colors.HexColor('#d5dbdb'),
        spaceAfter=6, spaceBefore=2,
    ))

    # ---- Destaques do Curso ----
    story.append(Paragraph('Destaques do Curso', styles['SecaoEmail']))
    for destaque in conteudo['destaques']:
        story.append(Paragraph(
            f'\u2022 {destaque}',
            styles['BulletEmail'],
        ))
    story.append(Spacer(1, 4))

    # ---- O que voce vai aprender ----
    story.append(Paragraph('O que voce vai aprender', styles['SecaoEmail']))
    story.append(Paragraph(conteudo['resumo'], styles['CorpoEmail']))

    # ---- Dica do Instrutor ----
    story.append(Paragraph('Dica do Instrutor', styles['SecaoEmail']))
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

    # ---- Para quem e este curso ----
    story.append(HRFlowable(
        width='60%', thickness=0.5, color=colors.HexColor('#d5dbdb'),
        spaceAfter=6, spaceBefore=6,
    ))
    story.append(Paragraph('Para quem e este curso', styles['SecaoEmail']))
    story.append(Paragraph(conteudo['publico_alvo'], styles['PublicoAlvoEmail']))

    # ---- Footer ----
    story.append(Spacer(1, 10))
    story.append(HRFlowable(
        width='100%', thickness=1, color=colors.HexColor('#1a5276'),
        spaceAfter=6, spaceBefore=4,
    ))
    story.append(Paragraph(
        f'{INSTITUICAO} | Cursos de Extensao',
        styles['FooterEmail'],
    ))
    story.append(Paragraph(
        'Este e um resumo academico gerado automaticamente. '
        'Para conteudo completo, consulte o material didatico do curso.',
        styles['FooterEmail'],
    ))
    story.append(Paragraph(
        'Todos os direitos reservados',
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

    print('=== Gerando emails/newsletters de extensao ===')
    for curso in CURSOS_EXTENSAO:
        curso_id = curso['curso_id']
        nome = curso['nome']
        filename = sanitize_filename(nome) + '_email.pdf'
        out_dir = os.path.join(OUTPUT_DIR, 'privado', 'extensao', curso_id)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)

        ok = gerar_email_pdf(curso, out_path, styles)
        if ok:
            total += 1
            print(f'  [{curso_id}] {nome} -> {filename}')

    print(f'\nDone!')
    print(f'  Total emails gerados: {total} PDFs')
    print(f'  Diretorio: {os.path.join(OUTPUT_DIR, "privado", "extensao")}')


if __name__ == '__main__':
    main()
